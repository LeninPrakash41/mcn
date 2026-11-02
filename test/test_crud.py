"""
Contract-driven CRUD: contract fields, `crud` in a service, `crud_table` in
the UI, and the helpers around them.
"""

import json
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from mcn.core_engine.lexer import Lexer
from mcn.core_engine.parser import Parser, ParseError
from mcn.core_engine.mcn_interpreter import MCNInterpreter

MODELS = '''
contract Lead
    name:      str
    email:     str unique
    phone:     str?
    stage:     choice("new", "won", "lost") = "new"
    value:     float = 0
    vip:       bool = false
    follow_up: date?

service crm
    crud Lead
        search name, email
        sort created_at desc
        page_size 2
'''


@pytest.fixture
def crm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)            # mcn_data.db lives in the working dir
    interp = MCNInterpreter()
    interp.execute(MODELS, quiet=True)
    return interp


def fn(interp, name):
    return interp._evaluator.functions[name]


# ── contract syntax ───────────────────────────────────────────────────────────

def test_contract_field_syntax():
    decl = Parser(Lexer(MODELS).tokenize()).parse().body[0]
    f = {x.name: x for x in decl.fields}
    assert f["email"].unique and not f["email"].optional
    assert f["phone"].optional
    assert f["stage"].choices == ["new", "won", "lost"] and f["stage"].default is not None
    assert f["follow_up"].type_name == "date" and f["follow_up"].optional


def test_unknown_field_type_is_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception, match="Unknown type 'strng'"):
        MCNInterpreter().execute("contract A\n    name: strng\n", quiet=True)


def test_unknown_service_line_is_a_syntax_error():
    with pytest.raises(ParseError, match="Expected 'port', 'endpoint' or 'crud'"):
        Parser(Lexer("service s\n    endpont x()\n        return 1\n").tokenize()).parse()


# ── backend crud ──────────────────────────────────────────────────────────────

def test_create_applies_defaults_and_coerces(crm):
    row = fn(crm, "create_lead")({"name": "Asha", "email": "a@x.in",
                                   "value": "1200.5", "vip": "true"})
    assert row["id"] == 1 and row["stage"] == "new"
    assert row["value"] == 1200.5 and row["vip"] is True
    assert row["created_at"] and row["updated_at"]


def test_validation_reports_every_field_at_once(crm):
    from mcn.core_engine.crud import BadRequest
    fn(crm, "create_lead")({"name": "Asha", "email": "a@x.in"})
    with pytest.raises(BadRequest) as exc:
        fn(crm, "create_lead")({"email": "a@x.in", "stage": "maybe",
                                "value": "lots", "follow_up": "tomorrow", "bogus": 1})
    assert exc.value.payload["errors"] == {
        "bogus": "is not a field", "name": "is required",
        "stage": "must be one of new, won, lost", "value": "must be a number",
        "follow_up": "must be a date like 2026-01-31", "email": "already exists",
    }


def test_list_search_filter_sort_paginate(crm):
    create = fn(crm, "create_lead")
    create({"name": "Asha", "email": "a@x.in", "value": 10})
    create({"name": "Ravi", "email": "r@x.in", "value": 30, "stage": "won"})
    create({"name": "Meera", "email": "m@x.in", "value": 20})
    lst = fn(crm, "list_leads")
    page1 = lst({})
    assert page1["total"] == 3 and page1["page_size"] == 2
    assert [r["name"] for r in page1["items"]] == ["Meera", "Ravi"]   # created_at desc
    assert [r["name"] for r in lst({"page": 2})["items"]] == ["Asha"]
    assert [r["name"] for r in lst({"search": "ra"})["items"]] == ["Meera", "Ravi"]
    assert [r["name"] for r in lst({"stage": "won"})["items"]] == ["Ravi"]
    assert [r["value"] for r in lst({"sort": "value desc", "page_size": 5})["items"]] == [30, 20, 10]


def test_update_get_delete(crm):
    from mcn.core_engine.crud import BadRequest, NotFound
    a = fn(crm, "create_lead")({"name": "Asha", "email": "a@x.in"})
    fn(crm, "create_lead")({"name": "Ravi", "email": "r@x.in"})
    updated = fn(crm, "update_lead")({"id": a["id"], "stage": "won"})
    assert updated["stage"] == "won" and updated["name"] == "Asha"   # partial update
    with pytest.raises(BadRequest):
        fn(crm, "update_lead")({"id": a["id"], "email": "r@x.in"})   # unique
    assert fn(crm, "get_lead")(a["id"])["stage"] == "won"
    assert fn(crm, "delete_lead")({"id": a["id"]}) == {"deleted": True, "id": a["id"]}
    with pytest.raises(NotFound):
        fn(crm, "get_lead")({"id": a["id"]})


def test_unsafe_sort_is_rejected(crm):
    from mcn.core_engine.crud import BadRequest
    with pytest.raises(BadRequest):
        fn(crm, "list_leads")({"sort": "name; DROP TABLE leads"})


def test_new_contract_field_adds_a_column(crm):
    fn(crm, "create_lead")({"name": "Asha", "email": "a@x.in"})
    grown = MODELS.replace("    follow_up: date?", "    follow_up: date?\n    city: str?")
    interp = MCNInterpreter()
    interp.execute(grown, quiet=True)
    rows = fn(interp, "list_leads")({})["items"]
    assert rows[0]["name"] == "Asha" and rows[0]["city"] is None      # data kept
    assert fn(interp, "create_lead")({"name": "R", "email": "r@x.in",
                                       "city": "Pune"})["city"] == "Pune"


def test_crud_names_for_multiword_contracts(tmp_path, monkeypatch):
    from mcn.core_engine.crud import crud_names
    n = crud_names("FollowUp")
    assert (n["list"], n["create"], n["table"]) == ("list_follow_ups", "create_follow_up", "follow_ups")
    assert crud_names("Category")["list"] == "list_categories"


def test_crud_for_unknown_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception, match="no contract named 'Leed'.*Did you mean 'Lead'"):
        MCNInterpreter().execute(
            "contract Lead\n    name: str\nservice s\n    crud Leed\n", quiet=True)


# ── HTTP ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def server(crm):
    from mcn.core_engine.mcn_server import _make_handler
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(crm._evaluator))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_crud_status_codes(server):
    status, row = _call(server + "/create_lead", {"name": "Asha", "email": "a@x.in"})
    assert status == 200 and row["id"] == 1
    status, err = _call(server + "/create_lead", {"name": "Dup", "email": "a@x.in"})
    assert status == 400 and err["errors"] == {"email": "already exists"}
    assert _call(server + "/list_leads?search=ash&page=1")[1]["total"] == 1
    assert _call(server + "/get_lead/1")[1]["name"] == "Asha"
    assert _call(server + "/get_lead/99")[0] == 404
    assert _call(server + "/update_lead", {"id": 1, "stage": "won"})[1]["stage"] == "won"
    assert _call(server + "/delete_lead", {"id": 1}) == (200, {"deleted": True, "id": 1})


# ── include ───────────────────────────────────────────────────────────────────

def test_include_is_relative_to_the_file_and_runs_once(tmp_path, monkeypatch):
    (tmp_path / "models.mcn").write_text("contract Lead\n    name: str\nvar loads = (loads or 0) + 1\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "main.mcn").write_text('var loads = 0\ninclude "../models.mcn"\ninclude "../models.mcn"\n')
    monkeypatch.chdir(tmp_path / "sub")
    interp = MCNInterpreter()
    interp.execute((sub / "main.mcn").read_text(), str(sub / "main.mcn"), quiet=True)
    assert interp.variables["loads"] == 1 and "Lead" in interp.variables


# ── UI: crud_table ────────────────────────────────────────────────────────────

UI = '''
contract Lead
    name:  str
    email: str unique
    stage: choice("new", "won") = "new"

component Leads
    render
        crud_table Lead columns=["name", "stage"] title="My leads"
'''


def _build(tmp_path, src):
    from mcn.core_engine.ui_compiler import UICompiler
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    UICompiler(output_dir=tmp_path).compile(interp._evaluator)
    return UICompiler


def test_crud_table_compiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build(tmp_path / "fe", UI)
    src = tmp_path / "fe" / "src"
    comp = (src / "components" / "Leads.tsx").read_text()
    assert ('<CrudTable resource={LeadResource} columns={["name", "stage"]} '
            'title={"My leads"} />') in comp
    assert 'import { LeadResource } from "../models"' in comp
    models = (src / "models.ts").read_text()
    assert '"list": "/list_leads"' in models and '"choices": [' in models
    assert '"pluralLabel": "Stages"' in models
    assert (src / "components" / "CrudTable.tsx").exists()
    assert "export class ApiError" in (src / "services" / "api.ts").read_text()


def test_crud_table_errors(tmp_path, monkeypatch):
    from mcn.core_engine.ui_compiler import UICompileError
    monkeypatch.chdir(tmp_path)
    with pytest.raises(UICompileError, match="no contract named 'Leed'"):
        _build(tmp_path / "a", "component X\n    render\n        crud_table Leed\n")
    with pytest.raises(UICompileError, match="unknown column 'nme'"):
        _build(tmp_path / "b", UI.replace('"name", "stage"', '"nme"'))


def test_tailwind_config_maps_all_shadcn_colors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build(tmp_path / "fe", UI)
    cfg = (tmp_path / "fe" / "tailwind.config.ts").read_text()
    for token in ("card", "popover", "muted", "destructive", "secondary", "input", "ring"):
        assert f"--{token}" in cfg


# ── stdlib ────────────────────────────────────────────────────────────────────

def test_format_number_and_currency():
    from mcn.core_engine.stdlib_builtins import mcn_format_number as num, mcn_format_currency as cur
    assert num(1234567) == "12,34,567"
    assert num(1234567, 0, "intl") == "1,234,567"
    assert num(1234.5, 2) == "1,234.50"
    assert cur(123456) == "₹1,23,456"
    assert cur(-1500000) == "-₹15,00,000"
    assert cur(99.5, "$", 2) == "$99.50"
