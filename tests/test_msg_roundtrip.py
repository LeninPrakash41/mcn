"""
The MSG round trip: syntax tree → MCN source (unparse), an edited MSG written back
to the app with unchanged code kept as it was, and building straight from an MSG.
"""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.lexer import Lexer  # noqa: E402
from mcn.core_engine.msg import ast_from_json, ast_to_json, build_msg, materialise, rewrite, write_back  # noqa: E402
from mcn.core_engine.parser import Parser  # noqa: E402
from mcn.core_engine.unparse import same_tree, to_source  # noqa: E402

TEMPLATES = ROOT / "mcn" / "web-playground" / "playground_server" / "templates"
SOURCES = sorted(TEMPLATES.rglob("*.mcn")) + sorted(
    p for pat in ("examples/**/*.mcn", "use-cases/**/*.mcn") for p in ROOT.glob(pat) if "legacy" not in p.parts)


def parse(text):
    parser = Parser(Lexer(text).tokenize())
    tree = parser.parse()
    assert parser.errors == [], parser.errors[0]
    return tree


@pytest.mark.parametrize("path", SOURCES, ids=[str(p.relative_to(ROOT)) for p in SOURCES])
def test_printing_gives_back_the_same_program(path):
    tree = parse(path.read_text(encoding="utf-8"))
    printed = to_source(tree)
    assert same_tree(parse(printed), tree)
    assert to_source(parse(printed)) == printed                      # canonical: printing is stable


EVERYTHING = r'''include "shared.mcn"
use "stripe"

contract Order
    id: int
    total: float

var greeting: str = "He said \"hi\"\nthen left\t{name}"
var n = -3 + 2 * (4 - 1) % 5
var ok = not (a and b) or c == d and e != f
var pick = x if y > 0 else (p if q else r)
var shout = (s) => upper(s)
var add = (a, b) => a + b
var none = () => null
var pair = (1, "two")
var one = (1,)
var obj = {name: "x", "quoted key": 2, task: 3, nested: {list: [1, 2.5, -0.5]}}
var deep = a.b?.c[0](1, named = 2).d
total += 5
items[0] = 1
user.name = "Ann"
on "order_created" handle_order
task "nightly" cleanup 3 "now"
log("hi")

function score(x: int, y = 2): float
    if x > 10
        return 1.0
    else if x > 5
        return 0.5
    else
        return 0
    for i, item in items
        if item == null
            continue
        break
    while x < 3
        x += 1
    try
        throw "bad"
    catch e
        log(e)
    finally
        log("done")

function nothing() {}

test "it works"
    assert score(11) == 1.0, "big scores are 1"

pipeline etl
    stage extract
        var rows = query("SELECT 1")
    stage load(rows, mode = "append")
        return rows

workflow approve
    step check(order)
        return order.total > 0

schedule nightly at "0 0 * * *"
    log("tick")

prompt reply
    system "You help."
    user "Customer: {{message}}"
    format json

agent helper
    model "claude-opus-5-5"
    tools fetch, query
    memory session
    task answer(q)
        return ai(q)

mcp files
    transport "stdio"
    command "npx"
    args ["-y", "server"]
    tool read_file(path)
    tool list_dir

module billing
    owns invoices, payments

    service billing_api
        port 8080
        auth "jwt"
        public health
        audit

        endpoint health()
            return {ok: true}

        endpoint invoice(order_id: int, note: str = "")
            return {id: order_id}

    function bill()
        return 1

component Dashboard
    state count = 0
    state rows = []

    on load
        rows = list_rows().data

    render
        div grid_cols=2
            stat_card label="Rows" value=count icon="Hash"
            button "Go" variant="outline" disabled
            text {count + 1}
            card title={"Total: " + str(count)} style={x: 1}
        for r in rows
            text {r.name}

app Shop
    title "Shop"
    theme "modern"
    logo "Store"
    footer "© Shop"
    layout
        sidebar
            nav "Home" Dashboard icon="Home" group="Main"
            nav "Help"
        tabs
            tab "One" Dashboard
        main
            Dashboard
        routes
            route "/" Dashboard
'''


def test_every_construct_round_trips():
    tree = parse(EVERYTHING)
    printed = to_source(tree)
    assert same_tree(parse(printed), tree), printed
    assert to_source(parse(printed)) == printed
    assert same_tree(ast_from_json(json.loads(json.dumps(ast_to_json(tree)))), tree)


# ── Writing an edited MSG back ───────────────────────────────────────────────

@pytest.fixture
def app(tmp_path):
    shutil.copytree(TEMPLATES / "crm", tmp_path / "crm")
    backend = tmp_path / "crm" / "backend" / "main.mcn"
    backend.write_text("// CRM backend: deals, contacts, companies and activities\n\n" + backend.read_text())
    return tmp_path / "crm"


def endpoint(msg, name):
    from mcn.core_engine.msg import resolve_ref
    node = next(n for n in msg["nodes"] if n["id"] == f"endpoint:{name}")
    return resolve_ref(msg, node["ast_ref"])


def test_an_edited_msg_changes_only_what_was_edited(app):
    msg = build_msg(app)
    before = (app / "backend" / "main.mcn").read_text()
    # Edit one endpoint in the tree: list_deals returns at most 10 rows
    ep = endpoint(msg, "list_deals")
    sql = next(x for x in json.dumps(ep).split('"') if x.startswith("SELECT"))
    text = json.dumps(ep).replace(sql, sql + " LIMIT 10")
    ep.clear()
    ep.update(json.loads(text))
    result = write_back(msg, app)
    assert result == {"written": ["backend/main.mcn"], "unchanged": ["ui/app.mcn"], "conflicts": []}
    after = (app / "backend" / "main.mcn").read_text()
    assert "LIMIT 10" in after
    assert after.startswith("// CRM backend: deals, contacts")            # comments outside the change survive
    unchanged_part = before.split("service crm_api")[0]
    assert after.startswith(unchanged_part)                               # everything before the service is as it was
    assert same_tree(parse(after), ast_from_json(msg["files"]["backend/main.mcn"]["ast"]))


def test_adding_and_removing_declarations(app):
    msg = build_msg(app)
    tree = ast_from_json(msg["files"]["backend/main.mcn"]["ast"])
    extra = parse('function deal_count()\n    return len(query("SELECT * FROM deals"))\n').body[0]
    extra.line = 0
    tree.body.append(extra)
    tree.body = [s for s in tree.body if type(s).__name__ != "ContractDecl" or s.name != "Activity"]
    msg["files"]["backend/main.mcn"]["ast"] = ast_to_json(tree)
    write_back(msg, app)
    text = (app / "backend" / "main.mcn").read_text()
    assert "function deal_count()" in text and "contract Activity" not in text
    assert "contract Deal" in text and same_tree(parse(text), tree)


def test_stale_msgs_and_dry_runs(app):
    msg = build_msg(app)
    ep = endpoint(msg, "list_deals")
    ep["name"] = "all_deals"
    assert write_back(msg, app, dry_run=True)["written"] == ["backend/main.mcn"]
    assert "all_deals" not in (app / "backend" / "main.mcn").read_text()      # nothing written
    (app / "backend" / "main.mcn").write_text((app / "backend" / "main.mcn").read_text() + "\n// edited elsewhere\n")
    result = write_back(msg, app)
    assert result["conflicts"] == ["backend/main.mcn"] and result["written"] == []
    assert write_back(msg, app, force=True)["written"] == ["backend/main.mcn"]


def test_an_unchanged_msg_writes_nothing(app):
    assert write_back(build_msg(app), app) == {"written": [], "unchanged": ["backend/main.mcn", "ui/app.mcn"],
                                               "conflicts": []}


def test_rewrite_keeps_comments_next_to_unchanged_code():
    original = '// header\n\n// about a\nfunction a()\n    return 1\n\n// about b\nfunction b()\n    return 2\n'
    tree = parse(original)
    tree.body[1] = parse("function b()\n    return 3\n").body[0]
    out = rewrite(original, tree)
    assert out == '// header\n\n// about a\nfunction a()\n    return 1\n\nfunction b()\n    return 3\n'


# ── Building from an MSG ─────────────────────────────────────────────────────

def test_building_from_an_msg_matches_building_from_source(tmp_path, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    app = TEMPLATES / "voice_agent_builder"
    graph = tmp_path / "app.msg.json"
    graph.write_text(json.dumps(build_msg(app)))
    monkeypatch.setattr(sys, "argv", ["mcn", "msg", "build", str(graph), "--out", str(tmp_path / "from_msg")])
    assert main() == 0
    monkeypatch.setattr(sys, "argv", ["mcn", "build", str(app / "ui" / "app.mcn"), "--out", str(tmp_path / "from_src")])
    assert main() == 0
    capsys.readouterr()
    a = {p.relative_to(tmp_path / "from_msg"): p.read_bytes() for p in (tmp_path / "from_msg").rglob("*") if p.is_file()}
    b = {p.relative_to(tmp_path / "from_src"): p.read_bytes() for p in (tmp_path / "from_src").rglob("*") if p.is_file()}
    assert a.keys() == b.keys() and a == b and any(str(k).endswith("CallSimulator.tsx") for k in a)


def test_cli_apply(app, tmp_path, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    msg = build_msg(app)
    endpoint(msg, "list_deals")["name"] = "all_deals"
    graph = tmp_path / "edited.json"
    graph.write_text(json.dumps(msg))
    monkeypatch.setattr(sys, "argv", ["mcn", "msg", "apply", str(graph), "--dir", str(app), "--dry-run"])
    assert main() == 0 and "Would write: backend/main.mcn" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["mcn", "msg", "apply", str(graph), "--dir", str(app)])
    assert main() == 0 and "Wrote: backend/main.mcn" in capsys.readouterr().out
    assert "endpoint all_deals(" in (app / "backend" / "main.mcn").read_text()
    copy.deepcopy(msg)


def test_schedule_blocks_parse_and_run():
    """`schedule name at "cron"` crashed the parser (it had no code for it) before the printer's tests found it."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.core_engine.runtime_types import MCNSchedule
    interp = MCNInterpreter()
    interp.execute('var ticks = 0\nschedule nightly at "0 0 * * *"\n    ticks = ticks + 1\n    return ticks\n'
                   'schedule hourly "0 * * * *"\n    return 1\n', quiet=True)
    nightly = interp._evaluator.globals.get("nightly")
    assert isinstance(nightly, MCNSchedule) and nightly.cron_expr == "0 0 * * *" and nightly.fn() == 1
    assert interp._evaluator.globals.get("hourly").cron_expr == "0 * * * *"
