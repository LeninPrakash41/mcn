"""
Error messages are part of the product for students: each common mistake must
produce a located, plain-language report with a hint, never a silent no-op or
a Python traceback.
"""
import contextlib
import io

import pytest

from playground_app import ROOT, load  # noqa: F401  (adds the repo to sys.path)
from mcn.core_engine.diagnostics import diagnose, render
from mcn.core_engine.mcn_interpreter import MCNInterpreter


def error_for(src):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            MCNInterpreter().execute(src, quiet=True)
        except Exception as e:
            return e
    pytest.fail("expected an error")


@pytest.mark.parametrize("src, line, kind, text, hint", [
    ('var total = 10\nlog(totl)', 2, "Name error", "Undefined variable 'totl'", "'total'"),
    ('var x = summ([1, 2])', 1, "Name error", "Undefined function 'summ'", "'sum'"),
    ('var name = "Ada\nlog(name)', 1, "Syntax error", "Unterminated string", 'triple quotes'),
    ('log((1 + 2)\nvar y = 3', 1, "Syntax error", "never closed", ""),
    ('if 1 > 0\nlog("yes")', 2, "Syntax error", "indented block after 'if' on line 1", "indented"),
    ('if true\n    var a = 1\n  var b = 2', 3, "Syntax error", "indented 2 spaces", "4 spaces"),
    ('function add(a, b)\n    return a + b\nlog(add(1))', 3, "Runtime error", "add() is missing an argument: b", ""),
    ('function f(a)\n    return a\nlog(f(1, 2))', 3, "Runtime error", "f() takes 1 argument", ""),
    ('var n = 0\nlog(10 / n)', 2, "Runtime error", "Division by zero", "divisor"),
])
def test_common_mistakes(src, line, kind, text, hint):
    err = error_for(src)
    diag = err.diagnostic
    assert (diag.line, diag.kind) == (line, kind)
    assert text in diag.message
    assert hint in diag.hint
    report = str(err)
    assert report.splitlines()[0].startswith(f"{kind} on line {line}")
    assert "Traceback" not in report and "NoneType" not in report


def test_report_shows_source_and_caret():
    err = error_for('var total = 10\nlog(totl)')
    assert str(err).splitlines()[1:3] == ["   2 | log(totl)", "     |     ^^^^"]


def test_syntax_errors_are_never_skipped():
    # Previously the parser recovered silently and ran the rest of the file
    err = error_for('log("before")\nlog((1\nlog("after")')
    assert err.diagnostic.kind == "Syntax error"


def test_unknown_package_lists_real_packages():
    msg = str(error_for("use not_a_package"))
    assert "analytics" in msg and "rag" in msg


def test_diagnose_plain_runtime_message():
    diag = diagnose("Something broke")
    assert diag.kind == "Runtime error" and diag.line == 0
    assert render(diag) == "Runtime error: Something broke"


def test_execute_api_returns_diagnostic():
    _, client = load()
    res = client.post("/api/execute", json={"code": "var total = 1\nlog(totl)"}).get_json()
    assert res["success"] is False
    assert res["diagnostic"]["line"] == 2 and res["diagnostic"]["col"] == 5
    assert res["diagnostic"]["hint"] == "Did you mean 'total'?"


def test_cli_prints_only_the_report(tmp_path):
    import subprocess
    import sys
    bad = tmp_path / "bad.mcn"
    bad.write_text("var total = 10\nlog(totl)\n")
    proc = subprocess.run([sys.executable, "-m", "mcn.core_engine.mcn_cli", "run", str(bad)],
                          cwd=ROOT, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)})
    assert proc.returncode == 1
    out = (proc.stdout + proc.stderr).strip().splitlines()
    assert out[0] == "Name error on line 2, column 5: Undefined variable 'totl'"
    assert len(out) == 4   # message, source line, caret, hint
