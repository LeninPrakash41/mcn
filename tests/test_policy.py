"""
Control policies: policy(...) declares what a device may do, the runtime enforces it on
every change whoever asks (code, an AI agent, Studio), and emergency_stop() makes every
output safe and refuses changes until it's released.
"""
import contextlib
import io
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import iot_lab  # noqa: E402
from mcn.core_engine.iot import device, shared_registry  # noqa: E402
from mcn.core_engine.iot_lab import lab  # noqa: E402
from mcn.core_engine.iot_policy import ApprovalPending, PolicyError, emergency_stop, policy  # noqa: E402


@pytest.fixture(autouse=True)
def clean():
    reg = shared_registry()
    reg.policies.emergency_stop(False)
    reg.policies.rules.clear()
    reg.policies.pending.clear()
    reg.policies.on_since.clear()
    reg.policies.off_since.clear()
    reg.policies.changes.clear()
    for d in ("p_pump", "p_motor", "p_lock", "p_vent", "p_light"):
        reg.remove(d)
    device("register", "p_pump", {"type": "pump"})
    device("register", "p_motor", {"type": "motor"})
    device("register", "p_lock", {"type": "lock"})
    device("register", "p_vent", {"type": "servo", "default": 0})
    device("register", "p_light", {"type": "light"})
    yield
    reg.policies.emergency_stop(False)
    reg.policies.rules.clear()
    for name in list(iot_lab.shared_lab().worlds):
        lab("remove", name)


def test_ranges_are_enforced_not_clamped():
    policy("p_motor", {"min": 10, "max": 70})
    device("write", "p_motor", 50)
    with pytest.raises(PolicyError, match="can't go above 70 \\(asked for 90\\)"):
        device("write", "p_motor", 90)
    with pytest.raises(PolicyError, match="can't go below 10"):
        device("write", "p_motor", 5)
    assert device("read", "p_motor")["value"] == 50          # unchanged
    log = list(shared_registry().command_log)[-1]
    assert log["command"] == "refused" and "below 10" in log["params"]["reason"]


def test_max_on_switches_off_and_cooldown_waits():
    policy("p_pump", {"max_on": 0.3, "cooldown": 0.6})
    device("on", "p_pump")
    time.sleep(0.6)
    assert device("read", "p_pump")["value"] == 0             # switched off by the policy
    assert any(c["command"] == "switched off by policy" for c in shared_registry().command_log)
    with pytest.raises(PolicyError, match="must rest"):
        device("on", "p_pump")
    time.sleep(0.5)
    device("on", "p_pump")                                     # rested long enough
    assert device("read", "p_pump")["value"] == 1


def test_rate_limit():
    policy("p_light", {"rate": 3})
    for _ in range(3):
        device("toggle", "p_light")
    with pytest.raises(PolicyError, match="at most 3 times a minute"):
        device("toggle", "p_light")


def test_hours_follow_the_lab_clock():
    lab("greenhouse")
    policy("grow_light", {"hours": [6, 20]})
    device("on", "grow_light")                                 # 08:00 in the greenhouse
    device("off", "grow_light")
    iot_lab.shared_lab().worlds["greenhouse"].clock = 15 * 3600   # 23:00
    with pytest.raises(PolicyError, match="only be switched on between 6:00 and 20:00 \\(it's 23:00\\)"):
        device("on", "grow_light")
    device("off", "grow_light")                                # turning off is always allowed


def test_a_check_function_decides():
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    src = '''
var raining = true
function vent_allowed(value)
    if raining and value > 30
        return "it's raining, the vent may open 30° at most"
    return true
policy("p_vent", {check: vent_allowed})
device("write", "p_vent", 20)
var refused = ""
try
    device("write", "p_vent", 90)
catch e
    refused = e.message
'''
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
    assert device("read", "p_vent")["value"] == 20
    assert "it's raining" in interp._evaluator.variables["refused"]


def test_approval_holds_the_action_until_a_person_decides():
    policy("p_lock", {"approve": True})
    with pytest.raises(ApprovalPending, match="Waiting for a person to approve"):
        device("on", "p_lock")
    assert device("read", "p_lock")["value"] == 0
    with pytest.raises(ApprovalPending):
        device("on", "p_lock")                                 # asking again doesn't duplicate it
    pending = policy("approvals")
    assert len(pending) == 1 and pending[0]["device"] == "p_lock"
    policy("reject", pending[0]["id"])
    assert device("read", "p_lock")["value"] == 0 and policy("approvals") == []
    with pytest.raises(ApprovalPending):
        device("on", "p_lock")
    assert policy("approve", policy("approvals")[0]["id"])["approved"]
    assert device("read", "p_lock")["value"] == 1


def test_emergency_stop_makes_everything_safe_and_blocks_changes():
    policy("p_vent", {"safe": 45})
    device("on", "p_pump")
    device("write", "p_motor", 80)
    device("write", "p_vent", 120)
    result = emergency_stop()
    assert result["stopped"] and {"p_pump", "p_motor", "p_vent"} <= set(result["made_safe"])
    assert device("read", "p_pump")["value"] == 0 and device("read", "p_motor")["value"] == 0
    assert device("read", "p_vent")["value"] == 45                    # its declared safe value
    with pytest.raises(PolicyError, match="Emergency stop is on"):
        device("on", "p_pump")
    device("off", "p_pump")                                            # the safe value is still allowed
    assert emergency_stop(False)["stopped"] is False
    device("on", "p_pump")
    assert device("read", "p_pump")["value"] == 1


def test_policies_apply_to_studio_and_agents_too():
    from mcn.core_engine.agent_tools import ToolSpec, _run_tool
    policy("p_motor", {"max": 50})
    with pytest.raises(PolicyError):
        shared_registry().write("p_motor", 90, source="simulator")    # someone in Studio's IoT panel
    spec = ToolSpec(name="set_motor", description="", params=["speed"], required=["speed"],
                    fn=lambda speed: device("write", "p_motor", speed))
    log = []
    content, is_error = _run_tool(spec, {"speed": 95}, log)
    assert is_error and "can't go above 50" in content and "can't go above 50" in log[0]["error"]


def test_policy_describes_itself_and_rejects_bad_rules():
    info = policy("p_pump", {"max_on": 600, "cooldown": 300, "hours": [6, 20]})
    assert info["summary"] == "on for at most 10 minutes, 5 minutes rest between runs, on between 6:00 and 20:00"
    assert device("list")["p_pump"]["policy"] == info["summary"]
    assert "p_pump" in policy("list")["policies"]
    with pytest.raises(PolicyError, match="unknown policy rule 'speed_limit'"):
        policy("p_motor", {"speed_limit": 3})
    with pytest.raises(PolicyError, match="hours is \\[start, end\\]"):
        policy("p_light", {"hours": 9})
    assert policy("remove", "p_pump")["success"]


def test_studio_stop_button_and_approvals():
    from playground_app import load
    _, client = load()
    policy("p_lock", {"approve": True})
    with pytest.raises(ApprovalPending):
        device("on", "p_lock")
    state = client.get("/api/iot/policy").get_json()
    req = next(p for p in state["pending"] if p["device"] == "p_lock")
    assert req["origin"] == "studio" and req["source"] == "code"
    assert client.post("/api/iot/approval", json={"id": req["id"], "approve": True}).get_json()["approved"]
    assert device("read", "p_lock")["value"] == 1
    res = client.post("/api/iot/estop", json={"on": True}).get_json()
    assert res["stopped"] and "p_lock" in res["made_safe"]
    assert client.get("/api/iot/policy").get_json()["stopped"] is True
    assert client.post("/api/iot/estop", json={"on": False}).get_json()["stopped"] is False


def test_backend_takes_studio_stop_and_approvals(monkeypatch):
    from mcn.core_engine import mcn_server, security
    monkeypatch.setenv("MCN_DEV_TOOLS", "1")
    monkeypatch.setattr(security, "check_auth", lambda mode, header: (True, {}, ""))
    device("on", "p_pump")
    status, body = mcn_server._dev_iot("POST", "/_mcn/iot/estop", {"on": True}, "Bearer x")
    assert status == 200 and "p_pump" in body["made_safe"]
    status, body = mcn_server._dev_iot("GET", "/_mcn/iot/policy", {}, "Bearer x")
    assert status == 200 and body["stopped"] is True
