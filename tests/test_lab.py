"""
The virtual lab: lab("greenhouse") and lab("rover") worlds whose devices behave
like real ones, driven with device(...), and drawn by Studio's IoT panel.
"""
import contextlib
import io
import math
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import iot_lab  # noqa: E402
from mcn.core_engine.iot import device, shared_registry  # noqa: E402
from mcn.core_engine.iot_lab import Greenhouse, LabError, Rover, lab  # noqa: E402


@pytest.fixture(autouse=True)
def clean_lab():
    yield
    for name in list(iot_lab.shared_lab().worlds):
        lab("remove", name)


def run(world, seconds, step=0.1):
    """Move a world forward by simulated seconds, deterministically."""
    for _ in range(int(seconds / step)):
        world.step(step)


# ── Greenhouse ───────────────────────────────────────────────────────────────

def test_greenhouse_soil_dries_in_the_sun_and_the_pump_wets_it():
    g = Greenhouse()
    g.clock = 4 * 3600                         # noon
    start = g.soil
    run(g, 3600, step=10)
    assert g.soil < start - 3                  # an hour of sun dries it
    dry = g.soil
    g.write("pump", 1)
    run(g, 600, step=10)
    assert g.soil > dry + 15 and g.water_used > 0
    assert g.events[-1]["text"] == "Pump on"


def test_greenhouse_follows_the_day_and_the_fan_cools_it():
    g = Greenhouse()
    assert g.read("light") > 300                                  # 08:00, sun up
    g.clock = 15 * 3600                                           # 23:00
    assert g.sun() == 0 and g.read("light") == 0
    g.write("grow_light", 1)
    assert g.read("light") == 450
    noon_hot, noon_fan = Greenhouse(), Greenhouse()
    for w in (noon_hot, noon_fan):
        w.clock = 4 * 3600
    noon_fan.write("fan", 1)
    noon_fan.write("vent", 150)
    run(noon_hot, 3600, step=10)
    run(noon_fan, 3600, step=10)
    assert noon_fan.read("temperature") < noon_hot.read("temperature") - 3


def test_plants_suffer_when_the_soil_stays_dry():
    g = Greenhouse()
    g.soil = 5
    before = g.plant
    run(g, 3 * 3600, step=30)
    assert g.plant < before


# ── Rover ────────────────────────────────────────────────────────────────────

def test_rover_drives_turns_and_senses():
    r = Rover()
    front = r.read("front_distance")
    r.write("drive", 50)
    run(r, 1.5)
    assert r.x > 0.9 and abs(r.y - 0.6) < 0.01               # straight ahead
    assert r.read("front_distance") < front                  # closer to the obstacle ahead
    r.write("steering", 150)                                 # above 90 turns left (the y axis points down)
    run(r, 1.0)
    assert r.heading > math.pi                               # heading went anticlockwise on screen


def test_rover_bumps_backs_up_and_slides_along_walls():
    r = Rover()
    r.write("drive", 100)
    run(r, 6)
    assert r.read("bumper") == 1 and r.events[0]["text"] == "Bumped into something"
    stuck_x = r.x
    r.write("drive", -60)
    run(r, 1.0)
    assert r.read("bumper") == 0 and r.x < stuck_x           # reverse frees it
    # Driving diagonally into the top wall slides along it instead of stopping
    s = Rover()
    s.heading = -math.radians(30)
    s.write("drive", 80)
    run(s, 4)
    assert s.y == pytest.approx(s.RADIUS, abs=0.02) and s.x > 1.0


def test_rover_finds_the_charging_pad():
    r = Rover()
    r.x, r.y = 5.3, 2.6
    r.heading = math.pi / 2                                  # facing down, towards the pad
    r.write("drive", 40)
    run(r, 2)
    assert r.reached and any("charging pad" in e["text"] for e in r.events)


# ── lab() and devices ────────────────────────────────────────────────────────

def test_lab_adds_devices_that_device_reads_and_drives():
    res = lab("greenhouse", {"speed": 3600})
    assert res["world"] == "greenhouse" and "soil_moisture" in res["devices"] and res["speed"] == 3600
    info = device("list")["pump"]
    assert info["driver"] == "lab" and info["simulated"] and info["where"]["world"] == "greenhouse"
    device("on", "pump")
    world = iot_lab.shared_lab().worlds["greenhouse"]
    assert world.outputs["pump"] == 1
    soil = device("read", "soil_moisture")["value"]
    assert soil == world.read("soil_moisture")
    time.sleep(0.5)                                          # the lab thread runs the world at speed
    assert device("read", "soil_moisture")["value"] > soil
    scene = lab("state", "greenhouse")
    assert scene["outputs"]["pump"] == 1 and scene["time"].count(":") == 1


def test_lab_reset_speed_remove_and_errors():
    lab("rover")
    device("write", "drive", 80)
    time.sleep(0.4)
    assert lab("state", "rover")["x"] > 0.6
    lab("reset", "rover")
    assert lab("state", "rover")["x"] == 0.6 and lab("state", "rover")["outputs"]["drive"] == 0
    assert lab("speed", {"world": "rover", "speed": 3})["speed"] == 3
    assert device("read", "drive")["value"] == 0
    lab("remove", "rover")
    assert "drive" not in shared_registry().devices and lab("state") == {}
    with pytest.raises(LabError, match="unknown lab operation 'moon'"):
        lab("moon")
    with pytest.raises(LabError, match="isn't running"):
        lab("reset", "rover")


def test_a_watch_handler_may_take_no_parameters():
    """device("watch", id, steer) with `function steer()` used to fail on every change."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    src = '''
lab("rover")
var calls = 0
function steer()
    calls = calls + 1
    device("write", "steering", 120)
device("watch", "front_distance", steer, 0.05)
device("write", "drive", 60)
'''
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
    deadline = time.time() + 3
    while time.time() < deadline and device("read", "steering")["value"] != 120:
        time.sleep(0.05)
    assert device("read", "steering")["value"] == 120


def test_lab_templates_run_and_their_tests_pass():
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    for name in ("lab_greenhouse", "lab_rover"):
        src = (ROOT / f"mcn/web-playground/playground_server/templates/{name}/backend/main.mcn").read_text()
        interp = MCNInterpreter()
        with contextlib.redirect_stdout(io.StringIO()):
            interp.execute(src, quiet=True)
            results = interp.run_tests() if hasattr(interp, "run_tests") else None
        assert lab("state")                                  # the world is running
        if results is not None:
            assert all(r.get("passed", True) for r in results), results


# ── Studio ───────────────────────────────────────────────────────────────────

def test_studio_draws_and_controls_the_lab():
    from playground_app import load
    _, client = load()
    lab("greenhouse")
    labs = client.get("/api/iot/lab").get_json()["labs"]
    assert labs["greenhouse"]["source"] == "studio" and "soil_moisture" in labs["greenhouse"]
    assert client.post("/api/iot/lab", json={"world": "greenhouse", "action": "speed", "speed": 600}).get_json()["speed"] == 600
    assert client.post("/api/iot/lab", json={"world": "greenhouse", "action": "reset"}).get_json()["success"]
    assert client.post("/api/iot/lab", json={"world": "rover", "action": "reset"}).get_json()["success"] is False


def test_backend_reports_its_lab_to_studio(monkeypatch):
    from mcn.core_engine import mcn_server, security
    monkeypatch.setenv("MCN_DEV_TOOLS", "1")
    monkeypatch.setattr(security, "check_auth", lambda mode, header: (True, {}, ""))
    lab("rover")
    status, body = mcn_server._dev_iot("GET", "/_mcn/iot/lab", {}, "Bearer x")
    assert status == 200 and "rover" in body["labs"]
    status, body = mcn_server._dev_iot("POST", "/_mcn/iot/lab", {"world": "rover", "action": "speed", "speed": 2}, "Bearer x")
    assert status == 200 and body["speed"] == 2
