"""
Typed endpoints (checked when called, required by `mcn check --strict`), modules that
own tables, and table screens that only offer the create/edit/delete actions the
backend really has.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.app_map import build_map, changed_targets, impact, outside_module  # noqa: E402
from mcn.core_engine.lexer import Lexer  # noqa: E402
from mcn.core_engine.mcn_interpreter import MCNInterpreter  # noqa: E402
from mcn.core_engine.mcn_server import _run_endpoint  # noqa: E402
from mcn.core_engine.parser import Parser  # noqa: E402
from mcn.core_engine.type_checker import Severity, check_source  # noqa: E402

TYPED = '''contract Customer
    name: str
    email: str

service billing
    endpoint add(customer: str, amount: float, paid: bool = false)
        return {customer: customer, amount: amount, paid: paid}

    endpoint count(n: int)
        return {n: n}

    endpoint signup(who: Customer)
        return {name: who.name}

    endpoint loose(x)
        return {x: x}
'''


@pytest.fixture(scope="module")
def evaluator():
    interp = MCNInterpreter()
    interp.execute(TYPED, quiet=True)
    return interp._evaluator


# ── Typed endpoints ───────────────────────────────────────────────────────────

def test_typed_values_are_converted(evaluator):
    assert _run_endpoint(evaluator, "add", ["Acme", "3", "true"], "t") == \
        (200, {"customer": "Acme", "amount": 3.0, "paid": True})
    assert _run_endpoint(evaluator, "count", ["42"], "t") == (200, {"n": 42})
    assert _run_endpoint(evaluator, "add", ["Acme", 2], "t")[1]["paid"] is False      # default kept
    assert _run_endpoint(evaluator, "loose", [[1, 2]], "t") == (200, {"x": [1, 2]})   # untyped: unchanged


@pytest.mark.parametrize("name, args, field, text", [
    ("add", ["Acme", "abc"], "amount", "'amount' must be float"),
    ("add", ["Acme"], "amount", "'amount' is required (float)"),
    ("add", [5, 1], "customer", "'customer' must be str, got a number"),
    ("count", ["4.5"], "n", "'n' must be int"),
    ("count", [True], "n", "'n' must be int"),
    ("signup", [{"name": "Ann"}], "who", "Missing field 'email'"),
    ("signup", ["Ann"], "who", "'who' must be Customer"),
])
def test_wrong_values_get_a_400(evaluator, name, args, field, text):
    status, body = _run_endpoint(evaluator, name, args, "t")
    assert status == 400 and body["field"] == field and text in body["error"]


def test_contracts_are_accepted(evaluator):
    assert _run_endpoint(evaluator, "signup", [{"name": "Ann", "email": "a@b.c"}], "t") == (200, {"name": "Ann"})


def test_direct_calls_and_tests_are_checked_too():
    interp = MCNInterpreter()
    interp.execute(TYPED, quiet=True)
    with pytest.raises(Exception, match="'n' must be int"):
        interp._evaluator.functions["count"]("many")


def test_strict_check_requires_types_and_unknown_types_are_errors():
    normal = check_source(TYPED)
    assert normal == []
    strict = check_source(TYPED, strict=True)
    assert [i.message for i in strict] == [
        "Endpoint 'loose' parameter 'x' has no type "
        "(strict mode: write x: str, int, float, bool, list, dict or a contract)"]
    bad = check_source("service s\n    endpoint f(x: money)\n        return x\n")
    assert bad[0].severity == Severity.ERROR and "unknown type 'money'" in bad[0].message


def test_typed_params_are_type_checked_in_the_body():
    issues = check_source("service s\n    endpoint f(n: int)\n        return n - \"x\"\n")
    assert any(i.severity == Severity.ERROR for i in issues)


def test_the_map_shows_types(tmp_path):
    (tmp_path / "main.mcn").write_text(TYPED)
    m = build_map(tmp_path)
    assert m["nodes"]["endpoint:add"]["types"] == {"customer": "str", "amount": "float", "paid": "bool"}


def test_templates_with_types_pass_strict():
    from mcn.core_engine.mcn_cli import check_file
    backend = ROOT / "mcn/web-playground/playground_server/templates/construction/backend/main.mcn"
    assert check_file(str(backend), strict=True) == 0


# ── Modules ───────────────────────────────────────────────────────────────────

MODULES = '''var module = 3

query("CREATE TABLE IF NOT EXISTS sm_orders (id INTEGER PRIMARY KEY, total REAL)")
query("CREATE TABLE IF NOT EXISTS sm_invoices (id INTEGER PRIMARY KEY, order_id INTEGER, amount REAL)")

module sales
    owns sm_orders

    service sales_api
        endpoint place_order(total: float)
            query("INSERT INTO sm_orders (total) VALUES (?)", (total,))
            return {success: true}

module billing
    owns sm_invoices

    function bill(order_id)
        query("INSERT INTO sm_invoices (order_id, amount) VALUES (?, 1)", (order_id,))

    service billing_api
        endpoint invoice(order_id: int)
            bill(order_id)
            return {success: true, orders: len(query("SELECT * FROM sm_orders"))}

test "modules run like top-level code"
    assert place_order(5).success == true
    assert invoice(1).success == true
    assert module == 3
'''


def _write(tmp_path, source):
    (tmp_path / "backend").mkdir(exist_ok=True)
    (tmp_path / "backend" / "main.mcn").write_text(source)
    return tmp_path


def test_modules_parse_and_run():
    parser = Parser(Lexer(MODULES).tokenize())
    program = parser.parse()
    assert parser.errors == []
    mods = [(s.name, s.owns, s.line, s.end_line) for s in program.body if type(s).__name__ == "ModuleDecl"]
    assert mods == [("sales", ["sm_orders"], 6, 12), ("billing", ["sm_invoices"], 14, 23)]
    interp = MCNInterpreter()
    interp.execute(MODULES.split("test ")[0], quiet=True)
    assert interp._evaluator.functions["invoice"](1)["success"] is True
    assert check_source(MODULES) == []


def test_modules_on_the_map(tmp_path):
    m = build_map(_write(tmp_path, MODULES))
    nodes = m["nodes"]
    assert nodes["function:bill"]["module"] == "billing" and nodes["endpoint:place_order"]["module"] == "sales"
    assert "module" not in nodes["test:modules run like top-level code"]
    assert nodes["table:sm_orders"]["owner"] == "sales"
    assert nodes["module:billing"]["members"] == ["endpoint:invoice", "function:bill", "service:billing_api"]
    assert nodes["module:billing"]["depends_on"] == ["sales"]          # invoice reads sales' table
    assert nodes["module:sales"]["depends_on"] == []
    assert m["issues"] == [] and m["summary"]["modules"] == 2


def test_only_the_owner_writes_its_tables(tmp_path):
    source = MODULES.replace('''        query("INSERT INTO sm_invoices (order_id, amount) VALUES (?, 1)", (order_id,))''',
                             '''        query("INSERT INTO sm_invoices (order_id, amount) VALUES (?, 1)", (order_id,))
        query("UPDATE sm_orders SET total = 0 WHERE id=?", (order_id,))''')
    source += '''
module reports
    owns sm_orders, sm_missing
'''
    messages = [i["message"] for i in build_map(_write(tmp_path, source))["issues"]]
    assert "function:bill (module billing) writes table 'sm_orders', which module sales owns" in messages
    assert "Table 'sm_orders' is owned by both module sales and module reports" in messages
    assert "module reports owns table 'sm_missing', which no CREATE TABLE defines" in messages


def test_impact_names_modules_and_a_module_can_be_a_target(tmp_path):
    m = build_map(_write(tmp_path, MODULES))
    result = impact(m, ["sm_orders"])
    assert result["modules"] == ["billing", "sales"]
    whole = impact(m, ["billing"])
    assert set(whole["targets"]) >= {"module:billing", "function:bill", "endpoint:invoice", "table:sm_invoices"}


def test_changes_outside_an_assigned_module_are_caught(tmp_path):
    app = _write(tmp_path, MODULES)
    git = lambda *a: subprocess.run(["git", *a], cwd=app, check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "init")
    main = app / "backend" / "main.mcn"
    main.write_text(main.read_text().replace("VALUES (?, 1)", "VALUES (?, 2)"))
    changed = changed_targets(app)
    assert changed == ["function:bill"]
    assert outside_module(build_map(app), changed, "billing") == []
    main.write_text(main.read_text().replace("return {success: true}\n", "return {success: true, ok: 1}\n", 1))
    assert outside_module(build_map(app), changed_targets(app), "billing") == ["endpoint:place_order"]


def test_cli_module_guard(tmp_path, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    app = _write(tmp_path, MODULES)
    monkeypatch.setattr(sys, "argv", ["mcn", "impact", "bill", "--dir", str(app), "--module", "billing"])
    assert main() == 0
    assert "Every change is inside module billing." in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["mcn", "impact", "place_order", "--dir", str(app), "--module", "billing", "--json"])
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["outside_module"] == ["endpoint:place_order"]
    monkeypatch.setattr(sys, "argv", ["mcn", "describe", str(app)])
    assert main() == 0
    assert "billing: owns sm_invoices; 2 declarations; depends on sales" in capsys.readouterr().out


# ── Table screens only offer actions the backend has ─────────────────────────

SCREEN = '''component OrdersTable
    state items = []

    on load
        items = list_orders().data

    render
        table data=items
            table_header
                table_row
                    table_head "total"
                    table_head "status"
            table_body
'''


def _compile(tmp_path, endpoints):
    from mcn.core_engine.ui_compiler import UICompiler
    interp = MCNInterpreter()
    interp.execute(SCREEN, quiet=True)
    UICompiler(output_dir=tmp_path, endpoints=endpoints).compile(interp._evaluator)
    return next(tmp_path.rglob("OrdersTable.tsx")).read_text()


def test_all_actions_when_the_backend_has_them(tmp_path):
    tsx = _compile(tmp_path, {"list_orders": [], "create_order": ["total", "status"],
                              "update_order": ["id", "total", "status"], "delete_order": ["id"]})
    for text in ('"/create_order"', '"/update_order"', '"/delete_order"', ">Edit<", ">Delete<", "New Order",
                 'notify(errorMessage(err), "error")'):
        assert text in tsx


def test_only_the_actions_whose_endpoints_exist_and_fit(tmp_path):
    # create_order needs a column the table doesn't have; there's no update_order
    tsx = _compile(tmp_path, {"list_orders": [], "create_order": ["total", "status", "customer_id"],
                              "delete_order": ["id"]})
    assert '"/delete_order"' in tsx and ">Delete<" in tsx
    for text in ('"/create_order"', '"/update_order"', ">Edit<", "New Order", "Sheet"):
        assert text not in tsx


def test_read_only_table_has_no_action_column(tmp_path):
    tsx = _compile(tmp_path, {"list_orders": []})
    assert "handleEdit" not in tsx and "handleDelete" not in tsx and "Actions" not in tsx
