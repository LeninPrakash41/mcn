"""
Regression tests for the full-stack toolchain: parser, lexer, formatter,
`mcn serve` routing and the MCN → React compiler.
"""

import io
import json
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from mcn.core_engine.lexer import Lexer
from mcn.core_engine.parser import Parser, ParseError
from mcn.core_engine.formatter import format_source
from mcn.core_engine.mcn_interpreter import MCNInterpreter


def run(src):
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    return interp.variables


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


# ── Language ──────────────────────────────────────────────────────────────────

def test_chained_ternary_in_function():
    v = run(
        'function grade(n)\n'
        '    return n >= 90 ? "A" : n >= 80 ? "B" : "C"\n'
        'var a = grade(95)\nvar b = grade(85)\nvar c = grade(10)\n'
    )
    assert (v["a"], v["b"], v["c"]) == ("A", "B", "C")


def test_parse_errors_are_raised_not_silently_dropped():
    with pytest.raises(ParseError) as exc:
        parse('var ok = 1\nvar = 2\nvar also_ok = 3\n')
    assert "[2:" in str(exc.value)


def test_multiline_call_list_object_and_string_in_brackets():
    v = run(
        'var cfg = {\n    name: "x",\n    tags: ["a",\n           "b"],\n}\n'
        'var m = max_val([1,\n    7,\n    3])\n'
        'var sql = upper("select *\nfrom t")\n'
    )
    assert v["cfg"]["tags"] == ["a", "b"]
    assert v["m"] == 7
    assert v["sql"] == "SELECT *\nFROM T"


def test_unterminated_string_outside_brackets_still_errors():
    with pytest.raises(Exception):
        Lexer('var s = "oops\nvar t = 1\n').tokenize()


def test_brace_block_with_else_on_next_line():
    v = run(
        'var r = ""\nvar y = 1\n'
        'if y > 5 {\n    r = "big"\n}\nelse {\n    r = "small"\n}\n'
    )
    assert v["r"] == "small"


def test_declaration_keyword_called_as_function_statement():
    program = parse('agent("create", "bot", {"model": "x"})\n')
    assert type(program.body[0]).__name__ == "ExprStmt"


def test_nav_component_positional_and_keyword_forms():
    program = parse(
        'app A\n    layout\n        sidebar\n'
        '            nav "One" OneView\n'
        '            nav "Two" icon="x" component=TwoView\n'
    )
    app = program.body[0]
    assert [n.component for n in app.layout.sidebar] == ["OneView", "TwoView"]


# ── Formatter ─────────────────────────────────────────────────────────────────

MESSY = '''// header
var x=1+2*3
var neg = -x   // trailing
var s="a\\nb {x}"
function   f(a,b)
  // inside
  return a>b?"yes":"no"
for i in [1,2]
  log(i)
component C
    render
        stat_card label="A" value=x
'''


def test_formatter_output():
    out = format_source(MESSY)
    assert "// header" in out and "// trailing" in out and "// inside" in out
    assert "var x = 1 + 2 * 3" in out
    assert "var neg = -x" in out
    assert 'var s = "a\\nb {x}"' in out          # escapes preserved verbatim
    assert '    return a > b ? "yes" : "no"' in out
    assert "for i in [1, 2]" in out
    assert 'stat_card label="A" value=x' in out  # UI attributes stay tight
    assert format_source(out) == out             # idempotent


def test_formatter_never_changes_tokens():
    out = format_source(MESSY)
    sig = lambda s: [(t.type, t.value) for t in Lexer(s).tokenize()
                     if t.type.name != "NEWLINE"]
    assert sig(out) == sig(MESSY)


# ── mcn serve ─────────────────────────────────────────────────────────────────

SERVICE = '''
service api
    endpoint add(a, b = 10)
        return {sum: a + b}
    endpoint get_echo(v)
        return {v: v}
'''


@pytest.fixture
def server():
    from mcn.core_engine.mcn_server import _make_handler
    interp = MCNInterpreter()
    interp.execute(SERVICE, quiet=True)
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(interp._evaluator))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
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


def test_serve_named_positional_and_get(server):
    assert _call(server + "/add", {"a": 1, "b": 2}) == (200, {"sum": 3})
    assert _call(server + "/add", {"_args": [5]}) == (200, {"sum": 15})
    assert _call(server + "/add", {"_args": [1, 2, 3]})[0] == 400
    assert _call(server + "/get_echo/hi") == (200, {"v": "hi"})


def test_serve_does_not_expose_builtins(server):
    assert _call(server + "/read_file?path=/etc/passwd")[0] == 404
    assert _call(server + "/query", {"sql": "select 1"})[0] == 404


def test_serve_script_detects_service(tmp_path):
    from mcn.core_engine.mcn_server import _declares_endpoints
    svc = tmp_path / "svc.mcn"
    svc.write_text(SERVICE)
    plain = tmp_path / "plain.mcn"
    plain.write_text('log("hi")\n')
    assert _declares_endpoints(str(svc)) is True
    assert _declares_endpoints(str(plain)) is False


# ── MCN → React compiler ──────────────────────────────────────────────────────

UI = '''
component LeadsTable
    state items = []
    state filter = "all"
    state msg = ""

    on filter_change
        if filter == "all"
            var res = list_leads()
        else
            var res = list_leads(filter)
        items = res.data

    render
        card
            p text=msg
            table
                table_header
                    table_row
                        table_head "Sent At"
                table_body

app A
    layout
        sidebar
            nav "Leads" icon="users" component=LeadsTable
'''


def test_ui_compiler_output(tmp_path):
    from mcn.core_engine.ui_compiler import UICompiler
    interp = MCNInterpreter()
    interp.execute(UI, quiet=True)
    UICompiler(output_dir=tmp_path).compile(interp._evaluator)

    comp = (tmp_path / "src/components/LeadsTable.tsx").read_text()
    app = (tmp_path / "src/App.tsx").read_text()
    assert "let res: any" in comp and "} else {" in comp
    assert "api.post('/list_leads', { _args: [filter] })" in comp
    assert 'row["sent_at"]' in comp
    assert "text=" not in comp
    assert "useState<any>([])" in comp
    assert "'/list_leadss'" not in comp
    assert "<LeadsTable />" in app
    assert (tmp_path / "src/vite-env.d.ts").exists()


# ── render: if / for / empty, handler params, interpolation ───────────────────

RENDER_UI = '''
component TaskBoard
    state tasks = []
    state loading = true
    state error = ""

    on remove(id)
        delete_task(id)
        tasks = list_tasks()

    render
        if loading
            p "Loading"
        else if error
            alert text=error
        else
            p "You have {tasks.length} tasks"
        for i, task in tasks
            card_header "{i}. {task.title}"
            button "Delete" on_click=remove(task.id)
            button "Raw" on_click=delete_task(task.id)
        empty
            p "No tasks yet"
        p "Unknown {stays} literal"
'''


def _compile(tmp_path, src, name):
    from mcn.core_engine.ui_compiler import UICompiler
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    UICompiler(output_dir=tmp_path).compile(interp._evaluator)
    return (tmp_path / f"src/components/{name}.tsx").read_text()


def test_render_if_for_empty_parse():
    import mcn.core_engine.ast_nodes as A
    comp = parse(RENDER_UI).body[0]
    roots = comp.render.elements
    assert isinstance(roots[0], A.UIIf)
    assert isinstance(roots[0].else_children[0], A.UIIf)          # else if
    loop = roots[1]
    assert isinstance(loop, A.UIFor)
    assert (loop.index_var, loop.variable) == ("i", "task")
    assert [e.tag for e in loop.empty] == ["p"]
    assert comp.handlers[0].params == ["id"]


def test_empty_is_only_special_after_for():
    comp = parse('component C\n    render\n        empty\n').body[0]
    assert comp.render.elements[0].tag == "empty"


def test_render_compiles_to_react(tmp_path):
    tsx = _compile(tmp_path, RENDER_UI, "TaskBoard")
    assert "{truthy(loading) ? (" in tsx and ") : truthy(error) ? (" in tsx
    assert "(tasks ?? []).map((task: any, i: number) => (" in tsx
    assert "<React.Fragment key={task?.id ?? i}>" in tsx
    assert "{truthy(tasks) ? (" in tsx                             # empty branch
    assert '`${i ?? ""}. ${task.title ?? ""}`' in tsx
    assert '`You have ${tasks.length ?? ""} tasks`' in tsx
    assert '"Unknown {stays} literal"' in tsx                      # unknown name untouched
    assert "const remove = useCallback(async (id: any) => {" in tsx
    assert "onClick={() => remove(task.id)}" in tsx
    assert "onClick={async () => { await api.post('/delete_task', { _args: [task.id] }) }}" in tsx
    assert 'import { truthy } from "@/lib/utils"' in tsx


def test_handler_reference_uses_generated_name(tmp_path):
    tsx = _compile(tmp_path,
                   'component F\n    state q = ""\n    on filter_change\n        q = "x"\n'
                   '    render\n        button "Go" on_click=filter_change\n', "F")
    assert "const filterChange = useCallback" in tsx
    assert "onClick={filterChange}" in tsx


def test_soft_keywords_as_names():
    v = run('var tasks = [{t: 1}, {t: 2}]\nvar total = 0\nfor task in tasks\n    total += task.t\n'
            'var state = {done: false}\nstate.done = true\n'
            'function f(test, step)\n    return test + step\nvar s = f(1, 2)\n'
            'test "still a test block"\n    assert true\n')
    assert (v["total"], v["state"]["done"], v["s"]) == (3, True, 3)
