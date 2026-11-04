"""
Regression tests for launch-blocking bugs: generated Dart escaping, the Claude
provider behind ai(), and clean CLI output. Runs offline (no API key needed).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.fullstack.flutter_generator import FlutterProjectGenerator  # noqa: E402
import mcn.providers.anthropic_provider as anthropic_provider  # noqa: E402


# ── Flutter generator: user text must not break Dart string literals ─────────

@pytest.mark.parametrize("raw, escaped", [
    ("Pay $5", "Pay \\$5"),
    ('Say "hi"', 'Say \\"hi\\"'),
    ("back\\slash", "back\\\\slash"),
    ("two\nlines", "two\\nlines"),
])
def test_dart_escape(raw, escaped):
    assert FlutterProjectGenerator._dart_escape(raw) == escaped


def test_generated_button_escapes_dollar():
    dart = FlutterProjectGenerator()._component_to_dart({"type": "button", "props": {"text": "Buy $9"}})
    assert 'text: "Buy \\$9"' in dart


# ── Claude provider used by ai()/llm() ───────────────────────────────────────

def _fake_response(payload):
    return SimpleNamespace(status_code=200, json=lambda: payload)


def test_provider_uses_current_model_and_skips_thinking(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json)
        return _fake_response({
            "stop_reason": "end_turn",
            "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Hello!"}],
        })

    with mock.patch.object(anthropic_provider.requests, "post", fake_post):
        out = anthropic_provider.anthropic_complete("hi", model=None, max_tokens=1024, temperature=0.3)

    assert out == "Hello!"
    assert sent["model"] == anthropic_provider.DEFAULT_MODEL
    assert "temperature" not in sent  # current Claude models reject sampling params
    assert sent["max_tokens"] >= 4096  # room for thinking plus the answer


def test_provider_reports_refusal(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    refusal = {"stop_reason": "refusal", "stop_details": {"explanation": "policy"}, "content": []}
    with mock.patch.object(anthropic_provider.requests, "post", lambda *a, **k: _fake_response(refusal)):
        assert anthropic_provider.anthropic_complete("x").startswith("[Claude declined]")


def test_provider_mock_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert anthropic_provider.anthropic_complete("hello").startswith("[Claude Mock")


# ── CLI: program output only, no duplicated engine logs ──────────────────────

def test_cli_hello_output_is_clean():
    proc = subprocess.run(
        [sys.executable, "-m", "mcn.core_engine.mcn_cli", "run", "examples/hello.mcn"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr
    lines = [l for l in (proc.stdout + proc.stderr).splitlines() if l.strip()]
    assert lines == ["Output Hello World!", "Adult"]


# ── Parser: JSX-style attribute expressions ──────────────────────────────────

def _parse(src):
    from mcn.core_engine.lexer import Lexer
    from mcn.core_engine.parser import Parser
    parser = Parser(Lexer(src).tokenize())
    program = parser.parse()
    return parser, program


def test_jsx_style_attr_with_sibling_parses():
    # style={{...}} followed by a sibling used to swallow the sibling element
    parser, program = _parse(
        "component A\n"
        "    render\n"
        "        div\n"
        '            div style={{"width": "10%"}} className="bar"\n'
        '            div className="next"\n'
    )
    assert parser.errors == []
    outer = program.body[0].render.elements[0]
    assert [c.tag for c in outer.children] == ["div", "div"]


def test_object_literal_attr_still_parses():
    parser, _ = _parse('component A\n    render\n        div data={"k": 1}\n')
    assert parser.errors == []


# ── React compiler: handler statements and expressions ───────────────────────

def _ts(expr_src):
    from mcn.core_engine.ui_compiler import _expr_to_ts
    _, program = _parse(f"var x = {expr_src}\n")
    return _expr_to_ts(program.body[0].value)


@pytest.mark.parametrize("mcn, ts", [
    ("a + 1", "(a + 1)"),                        # numeric addition, not string concat
    ("items + [x]", "[...(items), ...([x])]"),   # list concatenation
    ("a == b and c != d", "((a === b) && (c !== d))"),
    ("len(items)", "(items).length"),            # builtin, not an API call
    ("str(n)", "String(n)"),
    ("not done", "!(done)"),
])
def test_expr_to_ts(mcn, ts):
    assert _ts(mcn) == ts


def test_handler_for_loop_and_local_reassignment():
    from mcn.core_engine.ui_compiler import UICompiler
    _, program = _parse(
        "var names = []\n"
        "for c in contacts\n"
        "    names = names + [c.name]\n"
        "if ok\n"
        "    total = 1\n"
        "else\n"
        "    total = 2\n"
    )
    ts = UICompiler(output_dir=Path("."))._stmts_to_ts(program.body)
    assert "let names: any[] = []" in ts
    assert "for (const c of (contacts ?? []))" in ts
    assert "names = [...(names), ...([c.name])]" in ts   # local var: no setter
    assert "} else {" in ts and "setTotal(2)" in ts


def test_values_print_as_mcn_writes_them(capsys):
    """true/false/null and lists/objects look like MCN, not like the host language."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    interp = MCNInterpreter()
    interp.execute('var f = true\n'
                   'echo(f)\n'
                   'echo("flag: " + false)\n'
                   'echo("{f}")\n'
                   'echo([1, true, null, "a"])\n'
                   'echo({name: "Ana", "full name": null})\n'
                   'echo(str(true))', quiet=True)
    assert capsys.readouterr().out.splitlines() == [
        "true", "flag: false", "true", '[1, true, null, "a"]', '{name: "Ana", "full name": null}', "true"]


def test_each_request_gets_its_own_step_budget(monkeypatch):
    """A server used to stop answering once all requests together passed the statement limit."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    monkeypatch.setenv("MCN_MAX_STEPS", "5000")
    interp = MCNInterpreter()
    interp.execute('service s\n    endpoint work()\n        var t = 0\n        for n in range(1000)\n            t = t + n\n        return t\n', quiet=True)
    work = interp._evaluator.functions["work"]
    for _ in range(50):                      # 50 × ~2000 statements, far past 5000 in total
        assert work() == 499500
    with pytest.raises(Exception, match="statement execution limit"):
        interp.execute('function f()\n    return 1\nvar t = 0\nwhile true\n    t = t + f()\n', quiet=True)


def test_flutter_state_named_like_a_handler_value(tmp_path):
    """State called `item` used to be shadowed by the handler's implicit `item`."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.fullstack.flutter_compiler import FlutterCompiler
    interp = MCNInterpreter()
    interp.execute('component Queue\n    state item = {id: 0}\n    on next\n        item = {id: item.id + 1}\n'
                   '    render\n        button "Next" on_click=next\n\napp A\n    nav "Queue" Queue\n', quiet=True)
    FlutterCompiler({}).compile(interp._evaluator, tmp_path, "a")
    assert "final dynamic item = e" not in (tmp_path / "lib" / "screens" / "queue.dart").read_text()
