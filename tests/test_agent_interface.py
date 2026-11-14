"""
The MCN agent interface: inspect, find, explain, then create / modify / remove
declarations as a patch that is validated, tested and only written when approved.
Also `mcn op`, and `mcn change` driving the interface with a fake Claude client.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.agent_interface import AGENT_TOOLS, InterfaceError, Workspace, call_tool  # noqa: E402

BACKEND = '''query("CREATE TABLE IF NOT EXISTS ai_customers (id INTEGER PRIMARY KEY, name TEXT, verified INTEGER)")
query("CREATE TABLE IF NOT EXISTS ai_orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL)")

module customers
    owns ai_customers

    service customers_api
        endpoint list_customers()
            return {success: true, data: query("SELECT * FROM ai_customers")}

        endpoint add_customer(name: str)
            query("INSERT INTO ai_customers (name, verified) VALUES (?, 0)", (name,))
            return {success: true}

module orders
    owns ai_orders

    service orders_api
        endpoint list_orders()
            return {success: true, data: query("SELECT * FROM ai_orders")}

        endpoint create_order(customer_id: int, total: float)
            query("INSERT INTO ai_orders (customer_id, total) VALUES (?, ?)", (customer_id, total))
            return {success: true}

test "orders can be created"
    add_customer("Ann")
    assert create_order(1, 10).success == true
'''

UI = '''component OrdersScreen
    state items = []

    on load
        items = list_orders().data

    render
        card title="Orders"
            text "Orders"

app Shop
    title "Shop"
    layout
        sidebar
            nav "Orders" OrdersScreen
'''

VERIFIED_ORDER = '''endpoint create_order(customer_id: int, total: float)
    var found = query("SELECT verified FROM ai_customers WHERE id = ?", (customer_id,))
    if len(found) == 0
        return {success: false, error: "Unknown customer"}
    query("INSERT INTO ai_orders (customer_id, total) VALUES (?, ?)", (customer_id, total))
    return {success: true}'''


@pytest.fixture
def app(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "ui").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text(BACKEND)
    (tmp_path / "ui" / "app.mcn").write_text(UI)
    return tmp_path


def text(app, part="backend/main.mcn"):
    return (app / part).read_text()


# ── inspect / find / explain ──────────────────────────────────────────────────

def test_inspect_gives_the_structure(app):
    info = Workspace(app).inspect()
    assert [m["name"] for m in info["modules"]] == ["customers", "orders"]
    assert "create_order(customer_id: int, total: float)" in [e["signature"] for e in info["endpoints"]]
    assert {"name": "ai_orders", "owner": "orders", "create": next(
        l for l in BACKEND.splitlines() if "ai_orders" in l)} in info["tables"]
    assert info["navigation"] == [{"label": "Orders", "screen": "OrdersScreen"}]
    assert info["issues"] == [] or all("Nothing calls" in i for i in info["issues"])


def test_find_by_name_then_by_code(app):
    ws = Workspace(app)
    hits = ws.find("order", "endpoint")
    assert [h["id"] for h in hits] == ["endpoint:create_order", "endpoint:list_orders"]
    assert hits[0]["source"].startswith("        endpoint create_order")
    by_code = ws.find("verified")
    assert {h["id"] for h in by_code} == {"endpoint:add_customer", "table:ai_customers"}
    assert by_code[0]["matched"] == "code"


def test_explain(app):
    info = Workspace(app).explain("create_order")
    assert info["module"] == "orders" and info["writes"] == ["ai_orders"]
    assert info["tests"] == ["test:orders can be created"]
    assert "Writes ai_orders." in info["text"] and "Covered by test:orders can be created." in info["text"]
    with pytest.raises(InterfaceError, match="Did you mean: create_order"):
        Workspace(app).explain("create_ordr")


# ── Patches ───────────────────────────────────────────────────────────────────

def test_a_patch_is_built_validated_tested_and_applied_only_when_approved(app):
    ws = Workspace(app)
    before = text(app)
    r = ws.modify("create_order", VERIFIED_ORDER, reason="check the customer first")
    pid = r["patch"]
    assert '+            var found = query("SELECT verified FROM ai_customers' in r["diff"]   # indentation kept
    ws.create("test", 'test "orders need a known customer"\n    assert create_order(999, 5).success == false', patch=pid)
    assert text(app) == before                                   # nothing written yet

    with pytest.raises(InterfaceError, match="must pass validate"):
        ws.execute(pid, approved=True)
    v = ws.validate(pid)
    assert v["ok"] and v["changed"] == ["endpoint:create_order", "test:orders need a known customer"]
    assert v["affects"] == {} and v["tests_to_run"] == ["test:orders can be created", "test:orders need a known customer"]
    with pytest.raises(InterfaceError, match="must pass test"):
        ws.execute(pid, approved=True)
    t = ws.test(pid)
    assert t["ok"] and t["total"] == 2, t
    with pytest.raises(InterfaceError, match="needs approval"):
        ws.execute(pid)
    assert ws.execute(pid, approved=True)["files"] == ["backend/main.mcn"]
    assert "Unknown customer" in text(app) and 'test "orders need a known customer"' in text(app)
    assert ws.patches()[0]["status"] == "applied"
    with pytest.raises(InterfaceError, match="already applied"):
        ws.execute(pid, approved=True)


def test_validate_catches_what_the_patch_breaks(app):
    ws = Workspace(app)
    pid = ws.remove("list_orders")["patch"]                       # the screen still calls it
    v = ws.validate(pid)
    assert not v["ok"] and any("calls 'list_orders'" in i for i in v["new_issues"])
    pid = ws.modify("create_order", 'endpoint create_order(customer_id: money)\n    return {success: true}')["patch"]
    assert any("unknown type 'money'" in e for e in ws.validate(pid)["type_errors"])
    with pytest.raises(InterfaceError, match="doesn't parse"):
        ws.modify("create_order", "endpoint create_order(\n    return 1")


def test_failing_tests_are_reported(app):
    ws = Workspace(app)
    pid = ws.modify("create_order", 'endpoint create_order(customer_id: int, total: float)\n    return {success: false}')["patch"]
    assert ws.validate(pid)["ok"]
    t = ws.test(pid)
    assert not t["ok"] and t["failed"][0]["test"] == "orders can be created"


def test_a_stale_patch_is_refused(app):
    ws = Workspace(app)
    pid = ws.modify("list_orders", 'endpoint list_orders()\n    return {success: true, data: []}')["patch"]
    ws.validate(pid)
    ws.test(pid)
    (app / "backend" / "main.mcn").write_text(text(app) + "\n// edited by someone else\n")
    with pytest.raises(InterfaceError, match="changed since the patch was made"):
        ws.execute(pid, approved=True)


def test_create_places_code_where_it_belongs(app):
    ws = Workspace(app)
    pid = ws.create("endpoint", 'endpoint verify_customer(id: int)\n    query("UPDATE ai_customers SET verified = 1 WHERE id = ?", (id,))\n    return {success: true}',
                    service="customers_api")["patch"]
    ws.create("table", 'query("CREATE TABLE IF NOT EXISTS ai_notes (id INTEGER PRIMARY KEY, body TEXT)")',
              module="customers", patch=pid)
    ws.create("function", 'function is_verified(id)\n    return len(query("SELECT id FROM ai_customers WHERE id = ? AND verified = 1", (id,))) > 0',
              module="customers", patch=pid)
    ws.create("component", 'component CustomersScreen\n    render\n        card title="Customers"\n            text "Customers"',
              module="customers", nav="Customers", patch=pid)
    v = ws.validate(pid)
    assert v["ok"], v
    patched = ws._patched_files(ws._load(pid))
    m = ws._map(patched)
    assert m["nodes"]["endpoint:verify_customer"]["service"] == "customers_api"
    assert m["nodes"]["endpoint:verify_customer"]["module"] == "customers"
    assert m["nodes"]["function:is_verified"]["module"] == "customers"
    assert m["nodes"]["table:ai_notes"]["owner"] == "customers"           # `owns` was extended
    assert m["nodes"]["component:CustomersScreen"]["module"] == "customers"
    assert {"label": "Customers", "screen": "CustomersScreen"} in m["nodes"]["app:Shop"]["navigation"]
    assert "    owns ai_customers, ai_notes" in patched["backend/main.mcn"]
    with pytest.raises(InterfaceError, match="already exists"):
        ws.create("endpoint", "endpoint list_orders()\n    return 1", service="orders_api")
    with pytest.raises(InterfaceError, match="Say which service"):
        ws.create("endpoint", "endpoint ping()\n    return 1")


def test_a_patch_for_one_module_stays_inside_it(app):
    ws = Workspace(app)
    pid = ws.create("function", 'function audit_order(id)\n    query("UPDATE ai_customers SET verified = 0")',
                    module="orders")["patch"]
    v = ws.validate(pid)
    assert not v["ok"] and any("which module customers owns" in i for i in v["new_issues"])
    pid = ws.create("function", "function helper()\n    return 1", module="orders")["patch"]
    ws.modify("list_customers", 'endpoint list_customers()\n    return {success: true, data: []}', patch=pid)
    v = ws.validate(pid)
    assert v["outside_module"] == ["endpoint:list_customers"] and not v["ok"]


def test_tools_for_claude(app):
    assert {t["name"] for t in AGENT_TOOLS} == {"inspect", "find", "explain", "create", "modify", "remove",
                                                "validate", "test"}          # execute is for people only
    ws = Workspace(app)
    assert call_tool(ws, "explain", {"target": "nope"})["error"].startswith("Nothing called 'nope'")
    assert call_tool(ws, "execute", {"patch": "x"}) == {"error": "Unknown operation 'execute'"}
    assert call_tool(ws, "find", {"query": "create_order"})[0]["id"] == "endpoint:create_order"


# ── mcn op ────────────────────────────────────────────────────────────────────

def test_cli(app, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    src = app / "new.txt"
    src.write_text(VERIFIED_ORDER)

    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["mcn", "op", *argv, "--dir", str(app)])
        code = main()
        return code, capsys.readouterr().out

    code, out = run("explain", "create_order")
    assert code == 0 and "Writes ai_orders." in out
    code, out = run("modify", "create_order", "--source", str(src), "--json")
    pid = json.loads(out)["patch"]
    code, out = run("validate", pid)
    assert code == 0 and "✓ Valid: changes endpoint:create_order" in out
    code, out = run("execute", pid, "--yes")
    assert code == 1 and "must pass test" in out
    code, out = run("test", pid)
    assert code == 0 and "1 of 1 test(s) passed" in out
    code, out = run("execute", pid)
    assert code == 1 and "needs approval" in out
    code, out = run("execute", pid, "--yes")
    assert code == 0 and "Unknown customer" in text(app)
    code, out = run("patches")
    assert pid in out and "applied" in out


# ── mcn change: Claude works only through the interface ──────────────────────

def _tool_use(i, name, args):
    return SimpleNamespace(type="tool_use", id=f"t{i}", name=name, input=args)


class ScriptedClaude:
    """Plays back a fixed sequence of tool calls; records what came back."""

    def __init__(self, steps):
        self.steps = steps
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        step = self.steps[len(self.requests) - 1]
        if callable(step):
            step = step(kwargs)
        if isinstance(step, str):
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=step)], stop_reason="end_turn",
                                   stop_details=None)
        return SimpleNamespace(content=[_tool_use(i, n, a) for i, (n, a) in enumerate(step)], stop_reason="tool_use",
                               stop_details=None)


def _last_patch(kwargs):
    for msg in reversed(kwargs["messages"]):
        if msg["role"] == "user" and isinstance(msg["content"], list):
            for block in msg["content"]:
                body = json.loads(block["content"])
                if isinstance(body, dict) and body.get("patch"):
                    return body["patch"]
    return None


def test_change_agent_works_through_the_interface(app):
    from mcn.ai.change_agent import ChangeAgent
    client = ScriptedClaude([
        [("inspect", {}), ("explain", {"target": "create_order"})],
        [("modify", {"target": "create_order", "source": VERIFIED_ORDER, "reason": "verify first"})],
        lambda kw: [("validate", {"patch": _last_patch(kw)}), ("test", {"patch": _last_patch(kw)})],
        lambda kw: f"Orders now check the customer exists.\nPATCH {_last_patch(kw)}",
    ])
    events = []
    result = ChangeAgent(client=client, emit=events.append).run("Verify the customer before creating an order", str(app))
    assert result["patch"] and result["summary"] == "Orders now check the customer exists."
    assert [o["name"] for o in result["operations"]] == ["inspect", "explain", "modify", "validate", "test"]
    assert "Unknown customer" not in text(app)                     # the agent can't apply anything
    assert client.requests[0]["tools"] == AGENT_TOOLS
    status = Workspace(app).show(result["patch"])
    assert status["status"] == "validated" and status["tests"]["ok"]


def test_mcn_change_asks_before_applying(app, capsys, monkeypatch):
    from mcn.ai import change_agent
    from mcn.core_engine.mcn_cli import main
    steps = [
        [("modify", {"target": "create_order", "source": VERIFIED_ORDER})],
        lambda kw: f"Done.\nPATCH {_last_patch(kw)}",
    ]
    monkeypatch.setattr(change_agent.anthropic, "Anthropic", lambda **kw: ScriptedClaude(list(steps)))
    monkeypatch.setattr(sys, "argv", ["mcn", "change", "verify customers", "--dir", str(app), "--api-key", "k"])
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert main() == 0
    out = capsys.readouterr().out
    assert "✓ Valid" in out and "1 of 1 test(s) passed" in out and "Not applied" in out
    assert "Unknown customer" not in text(app)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert main() == 0
    assert "Unknown customer" in text(app)
