"""
`mcn describe` and `mcn impact`: the app map read from source, problems it finds,
what a change affects, changes from git, and the agent team using both.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.app_map import build_map, changed_between, changed_targets, impact, resolve  # noqa: E402

TEMPLATES = ROOT / "mcn" / "web-playground" / "playground_server" / "templates"

APP_BACKEND = '''query("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, customer TEXT, amount REAL)")

function total_due()
    return query("SELECT SUM(amount) AS total FROM invoices")[0].total

service billing
    auth "sso"
    audit
    public health

    endpoint health()
        return {ok: true}

    endpoint list_invoices()
        return {success: true, data: query("SELECT * FROM invoices")}

    endpoint add_invoice(customer, amount)
        query("INSERT INTO invoices (customer, amount) VALUES (?, ?)", (customer, amount))
        return {success: true, due: total_due()}

    endpoint old_report()
        return query("SELECT * FROM payments")

test "adding an invoice works"
    assert add_invoice("Acme", 10).success == true
'''

APP_UI = '''component Invoices
    state items = []

    on load
        items = list_invoices().data

    on add
        add_invoice("Acme", 5)
        refund_all()

    render
        data_table title="Invoices"

app Billing
    layout
        sidebar
            nav "Invoices" Invoices
            nav "Reports" Reports
'''


@pytest.fixture
def app(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "ui").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text(APP_BACKEND)
    (tmp_path / "ui" / "app.mcn").write_text(APP_UI)
    return tmp_path


def edges_of(m, kind):
    return {(e["from"], e["to"]) for e in m["edges"] if e["kind"] == kind}


def test_the_map_has_every_part_and_connection(app):
    m = build_map(app)
    nodes = m["nodes"]
    assert nodes["endpoint:add_invoice"]["auth"] == "sso" and nodes["endpoint:health"]["auth"] is None
    assert nodes["endpoint:add_invoice"]["audited"] is True
    assert nodes["endpoint:add_invoice"]["writes"] == ["invoices"] and nodes["function:total_due"]["reads"] == ["invoices"]
    assert nodes["endpoint:add_invoice"]["file"] == "backend/main.mcn" and nodes["endpoint:add_invoice"]["line"] == 17
    assert ("component:Invoices", "endpoint:list_invoices") in edges_of(m, "calls")
    assert ("endpoint:add_invoice", "function:total_due") in edges_of(m, "calls")
    assert ("test:adding an invoice works", "endpoint:add_invoice") in edges_of(m, "covers")
    assert ("app:Billing", "component:Invoices") in edges_of(m, "shows")
    assert nodes["endpoint:add_invoice"]["tested"] and not nodes["endpoint:list_invoices"]["tested"]


def test_the_map_finds_problems(app):
    messages = [i["message"] for i in build_map(app)["issues"]]
    assert "component:Invoices calls 'refund_all', which isn't an endpoint or function" in messages
    assert "Navigation item 'Reports' shows 'Reports', which isn't a component" in messages
    assert "endpoint:old_report reads table 'payments', which no CREATE TABLE defines" in messages
    unused = [i for i in build_map(app)["issues"] if i["kind"] == "unused_endpoint"]
    assert {i["where"] for i in unused} == {"endpoint:health", "endpoint:old_report"}
    assert all(i["severity"] == "note" for i in unused)


def test_impact_of_a_table_change(app):
    m = build_map(app)
    result = impact(m, ["invoices"])
    assert result["targets"] == ["table:invoices"]
    assert {e["id"] for e in result["affected"]["endpoints"]} == {"endpoint:add_invoice", "endpoint:list_invoices"}
    assert {f["id"] for f in result["affected"]["functions"]} == {"function:total_due"}
    assert [s["id"] for s in result["affected"]["screens"]] == ["component:Invoices"]
    assert result["navigation"] == ["Invoices"]
    assert result["tests"] == ["test:adding an invoice works"]
    assert "endpoint:list_invoices" in result["untested"] and "endpoint:add_invoice" not in result["untested"]


def test_impact_by_name_kind_or_line(app):
    m = build_map(app)
    assert resolve(m, "endpoint:list_invoices") == ["endpoint:list_invoices"]
    assert resolve(m, "backend/main.mcn:17") == ["endpoint:add_invoice"]
    result = impact(m, ["total_due", "nonexistent"])
    assert result["unknown"] == ["nonexistent"]
    assert [e["id"] for e in result["affected"]["endpoints"]] == ["endpoint:add_invoice"]


def test_changed_declarations_from_git(app):
    git = lambda *a: subprocess.run(["git", *a], cwd=app, check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "init")
    main = app / "backend" / "main.mcn"
    main.write_text(main.read_text().replace('return {success: true, data: query("SELECT * FROM invoices")}',
                                             'return {success: true, data: query("SELECT * FROM invoices LIMIT 50")}'))
    assert changed_targets(app) == ["endpoint:list_invoices"]
    result = impact(build_map(app), changed_targets(app))
    assert [s["id"] for s in result["affected"]["screens"]] == ["component:Invoices"]


def test_changed_between_two_copies(app, tmp_path_factory):
    before = tmp_path_factory.mktemp("before")
    shutil.copytree(app / "backend", before / "backend")
    shutil.copytree(app / "ui", before / "ui")
    ui = app / "ui" / "app.mcn"
    ui.write_text(ui.read_text().replace("refund_all()", "notify(\"Added\")"))
    assert changed_between(before, app) == ["component:Invoices"]


def test_table_screens_count_the_compilers_crud_calls():
    m = build_map(TEMPLATES / "crm")
    assert not [i for i in m["issues"] if i["where"] == "endpoint:update_deal"]          # used by the deals table
    construction = build_map(TEMPLATES / "construction")
    jobs = construction["nodes"]["component:JobsTable"]["generated_calls"]
    assert jobs == ["delete_job", "list_jobs", "update_job"]      # no create: the table lacks project_id
    assert construction["issues"] == []


def test_table_buttons_only_for_endpoints_that_fit(app):
    ui = app / "ui" / "app.mcn"
    ui.write_text(ui.read_text() + """
component InvoicesTable
    state items = []

    render
        table data=items
            table_header
                table_row
                    table_head "customer"
            table_body
""")
    m = build_map(app)
    # add_invoice isn't create_invoice, and there's no update_/delete_invoice: no buttons, no false alarms
    assert m["nodes"]["component:InvoicesTable"]["generated_calls"] == []
    assert not [i for i in m["issues"] if i["where"] == "component:InvoicesTable"]


def test_every_template_maps_without_errors():
    for folder in TEMPLATES.iterdir():
        if (folder / "backend").exists() or (folder / "ui").exists():
            assert build_map(folder)["errors"] == [], folder.name


def test_cli(app, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    monkeypatch.setattr(sys, "argv", ["mcn", "describe", str(app), "--json"])
    assert main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["endpoints"] == 4 and data["summary"]["screens"] == 1
    monkeypatch.setattr(sys, "argv", ["mcn", "describe", str(app), "--strict"])
    assert main() == 1                                      # the map found real issues
    assert "Issues" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["mcn", "impact", "invoices", "--dir", str(app)])
    assert main() == 0
    out = capsys.readouterr().out
    assert "Changing table:invoices affects:" in out and "Tests to run: adding an invoice works" in out


def test_agent_team_qa_sees_the_map_and_the_last_fix(tmp_path):
    from test_agent_team import FakeClient, _message, BACKEND, UI
    from mcn.ai.agent_team import AgentTeam
    fixed_ui = UI.replace('"Operations"', '"Operations Hub"')
    client = FakeClient(qa_answers=["<verdict>fix</verdict><fixes>\n1. Rename the app\n</fixes>",
                                    "<verdict>pass</verdict>"])
    original = client._answer
    client._answer = lambda kw: (_message(f"<backend>{BACKEND}</backend><ui>{fixed_ui}</ui>")
                                 if "QA lead tested this MCN app" in str(kw["messages"][0]["content"]) else original(kw))
    events = []
    AgentTeam(client=client, emit=events.append, web_research=False).run("dashboard", str(tmp_path))
    reports = [e["report"] for e in events if e["type"] == "qa"]
    assert reports[0]["app_map"]["summary"]["endpoints"] == 8
    assert "last_fix" not in reports[0]
    assert reports[1]["last_fix"]["changed"] == ["app:Operations"]
