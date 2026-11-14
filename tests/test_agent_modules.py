"""
The agent team building an app as modules, one builder per module at the same time:
the architect's split, each builder's brief, putting the files together, the
ownership check between modules, and QA fixes sent only to the modules they name.
"""
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from test_agent_team import FakeClient, _message  # noqa: E402

from mcn.ai.agent_team import AgentTeam, assemble, fragment_errors, parse_modules  # noqa: E402
from mcn.core_engine.app_map import build_map  # noqa: E402

SPEC = {
    "app": {"name": "Shop", "title": "Shop"},
    "modules": [
        {"name": "billing", "about": "invoices", "owns": ["pm_invoices"], "depends_on": ["sales"],
         "endpoints": ["list_invoices()"], "screens": [{"component": "InvoicesTable", "label": "Invoices"}]},
        {"name": "sales", "about": "orders", "owns": ["pm_orders"],
         "endpoints": ["list_orders()", "place_order(total: float)"],
         "screens": [{"component": "OrdersTable", "label": "Orders"}]},
    ],
}

SALES = {
    "backend": '''query("CREATE TABLE IF NOT EXISTS pm_orders (id INTEGER PRIMARY KEY, total REAL)")

service sales_api
    endpoint list_orders()
        return {success: true, data: query("SELECT * FROM pm_orders")}

    endpoint place_order(total: float)
        query("INSERT INTO pm_orders (total) VALUES (?)", (total,))
        return {success: true}''',
    "ui": '''component OrdersTable
    state items = []

    on load
        items = list_orders().data

    render
        card title="Orders"
            text "Orders"''',
}

BILLING = {
    "backend": '''query("CREATE TABLE IF NOT EXISTS pm_invoices (id INTEGER PRIMARY KEY, order_id INTEGER, amount REAL)")

service billing_api
    endpoint list_invoices()
        var orders = query("SELECT * FROM pm_orders")
        return {success: true, data: query("SELECT * FROM pm_invoices"), orders: len(orders)}''',
    "ui": '''component InvoicesTable
    state items = []

    on load
        items = list_invoices().data

    render
        card title="Invoices"
            text "Invoices"''',
}

# billing writing sales' table: the ownership check must send it back to billing's builder
BILLING_BAD = dict(BILLING, backend=BILLING["backend"].replace(
    '        var orders', '        query("UPDATE pm_orders SET total = 0")\n        var orders'))


def _blocks(fragment):
    return f"<backend>{fragment['backend']}</backend>\n<ui>{fragment['ui']}</ui>"


class ModuleClient(FakeClient):
    """The architect splits the app into two modules; each module's builder answers for its module."""

    def __init__(self, billing_answers, qa_answers=None, delay=0.0):
        super().__init__(qa_answers=qa_answers)
        self.billing_answers = list(billing_answers)
        self.delay = delay
        self.active = 0
        self.most_at_once = 0
        self.lock = threading.Lock()

    def _answer(self, kwargs):
        system = kwargs["system"]
        if "software architect" in system:
            return _message(f"<plan>Tables pm_orders, pm_invoices.</plan>\n<modules>{json.dumps(SPEC)}</modules>")
        if "Build ONLY module" in system:
            with self.lock:
                self.active += 1
                self.most_at_once = max(self.most_at_once, self.active)
            time.sleep(self.delay)
            with self.lock:
                self.active -= 1
            if "Build ONLY module sales" in system:
                return _message(_blocks(SALES))
            return _message(_blocks(self.billing_answers.pop(0) if len(self.billing_answers) > 1
                                    else self.billing_answers[0]))
        return super()._answer(kwargs)


def builder_calls(client, module):
    return [c for c in client.calls if f"Build ONLY module {module}" in c["system"]]


def test_the_architects_split_is_checked():
    spec = parse_modules(f"<plan>x</plan><modules>{json.dumps(SPEC)}</modules>")
    assert [m["name"] for m in spec["modules"]] == ["billing", "sales"] and spec["auth"] is None
    assert parse_modules("<plan>no modules</plan>") is None
    one = dict(SPEC, modules=SPEC["modules"][:1])
    assert parse_modules(f"<modules>{json.dumps(one)}</modules>") is None          # one area: one builder
    shared = json.loads(json.dumps(SPEC))
    shared["modules"][1]["owns"] = ["pm_invoices"]
    assert parse_modules(f"<modules>{json.dumps(shared)}</modules>") is None       # a table with two owners
    assert parse_modules("<modules>{not json</modules>") is None


def test_each_builders_code_is_checked_on_its_own():
    module = SPEC["modules"][1]
    assert fragment_errors(SALES, module) == []
    assert "[ui] missing component(s): OrdersTable" in fragment_errors(dict(SALES, ui="component Other\n    render\n        text \"x\"\n"), module)
    wrapped = dict(SALES, backend="module sales\n    var x = 1\n")
    assert any("don't write a `module` line" in e for e in fragment_errors(wrapped, module))
    with_app = dict(SALES, ui=SALES["ui"] + '\n\napp X\n    title "X"\n')
    assert any("`app` block" in e for e in fragment_errors(with_app, module))


def test_assembled_files_have_modules_and_navigation(tmp_path):
    spec = parse_modules(f"<modules>{json.dumps(SPEC)}</modules>")
    backend, ui = assemble(spec, {"sales": SALES, "billing": BILLING})
    assert backend.index("module sales") < backend.index("module billing")         # billing reads sales' table
    assert "module billing\n    owns pm_invoices" in backend
    assert 'nav "Invoices" InvoicesTable' in ui and 'nav "Orders" OrdersTable' in ui
    (tmp_path / "backend").mkdir()
    (tmp_path / "ui").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text(backend)
    (tmp_path / "ui" / "app.mcn").write_text(ui)
    app = build_map(tmp_path)
    assert app["errors"] == [] and [i for i in app["issues"] if i.get("severity") != "note"] == []
    assert app["nodes"]["component:InvoicesTable"]["module"] == "billing"           # screens belong to modules too
    assert app["nodes"]["module:billing"]["files"] == ["backend/main.mcn", "ui/app.mcn"]
    assert app["nodes"]["module:billing"]["depends_on"] == ["sales"]


def test_modules_are_built_at_the_same_time(tmp_path):
    client = ModuleClient([BILLING], delay=0.3)
    events = []
    result = AgentTeam(client=client, emit=events.append, web_research=False).run("a shop", str(tmp_path))
    assert client.most_at_once == 2
    assert result["modules"] == ["billing", "sales"] and result["verdict"] == "pass"
    assert result["qa_report"]["types"] == [] and result["qa_report"]["ui_build"] == "ok"
    assert result["qa_report"]["app_map"]["issues"] == []
    assert "modules" in result["qa_report"]
    done = {e["name"] for e in events if e["type"] == "module" and e["status"] == "done"}
    assert done == {"billing", "sales"}
    assert (tmp_path / "backend" / "main.mcn").read_text() == result["backend_mcn"]
    brief = builder_calls(client, "billing")[0]["system"]
    assert "owns: pm_invoices" in brief and "module sales: owns pm_orders" in brief


def test_a_module_writing_another_modules_table_is_rebuilt(tmp_path):
    client = ModuleClient([BILLING_BAD, BILLING])
    result = AgentTeam(client=client, web_research=False).run("a shop", str(tmp_path))
    billing = builder_calls(client, "billing")
    assert len(billing) == 2 and len(builder_calls(client, "sales")) == 1          # only billing goes again
    assert "writes table 'pm_orders', which module sales owns" in billing[1]["messages"][0]["content"]
    assert "UPDATE pm_orders" not in result["backend_mcn"] and result["attempts"] == 2


def test_qa_fixes_go_only_to_the_modules_they_name(tmp_path):
    client = ModuleClient([BILLING], qa_answers=[
        "<verdict>fix</verdict><fixes>1. [billing] Show the invoice count</fixes>", "<verdict>pass</verdict>"])
    events = []
    result = AgentTeam(client=client, emit=events.append, web_research=False).run("a shop", str(tmp_path))
    billing = builder_calls(client, "billing")
    assert len(billing) == 2 and len(builder_calls(client, "sales")) == 1
    assert "1. Show the invoice count" in billing[1]["messages"][0]["content"]
    assert result["verdict"] == "pass"
    qa_prompt = [c for c in client.calls if "QA lead" in c["system"]][1]["messages"][0]["content"][-1]["text"]
    assert '"last_fix"' in qa_prompt


def test_untagged_fixes_rewrite_the_whole_app(tmp_path):
    from test_agent_team import BACKEND, UI
    client = ModuleClient([BILLING], qa_answers=[
        "<verdict>fix</verdict><fixes>1. Rename the app</fixes>", "<verdict>pass</verdict>"])
    original = client._answer

    def answer(kwargs):
        if "asks for these changes" in str(kwargs["messages"][0]["content"]):
            return _message(f"<backend>{BACKEND}</backend>\n<ui>{UI}</ui>")
        return original(kwargs)
    client._answer = answer
    result = AgentTeam(client=client, web_research=False).run("a shop", str(tmp_path))
    assert result["backend_mcn"] == BACKEND.strip()
