"""
The student pilot kit must keep working as MCN changes: reference solutions
pass their own tests, exercise 3's bugs produce the intended error sequence,
exercise 6 builds, and the starter guide's code runs.
"""
import contextlib
import io
import re
from pathlib import Path

import pytest

from playground_app import ROOT, load, quiet
from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.core_engine.test_runner import TestRunner as MCNTestRunner

PILOT = ROOT / "docs" / "pilot"
SOLUTIONS = sorted((PILOT / "solutions").glob("ex*.mcn"))


def run(src):
    with contextlib.redirect_stdout(io.StringIO()):
        MCNInterpreter().execute(src, quiet=True)


def first_error(src):
    try:
        run(src)
    except Exception as e:
        return e.diagnostic
    return None


@pytest.mark.parametrize("path", SOLUTIONS, ids=[p.stem for p in SOLUTIONS])
def test_solution_runs_and_passes_its_tests(path, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)   # mock AI, no network
    monkeypatch.chdir(tmp_path)                               # the sqlite file goes in a temp dir
    source = path.read_text()
    run(source)
    with contextlib.redirect_stdout(io.StringIO()):
        results = MCNTestRunner().run_source(source, label=path.name)
    assert results, "solution should include test blocks"
    failed = [r for r in results if not r.passed]
    assert not failed, failed


def test_exercise3_errors_appear_in_order():
    exercise = (PILOT / "EXERCISES.md").read_text()
    broken = re.search(r"## 3\..*?```mcn\n(.*?)```", exercise, re.S).group(1)

    step1 = first_error(broken)
    assert step1.kind == "Syntax error" and "indented block after 'function'" in step1.message

    fixed1 = broken.replace("\nreturn celsius", "\n    return celsius")
    step2 = first_error(fixed1)
    assert "never closed" in step2.message

    fixed2 = fixed1.replace('str(to_farenheit(c) + "°F")', 'str(to_farenheit(c)) + "°F")')
    step3 = first_error(fixed2)
    assert step3.kind == "Name error" and step3.hint == "Did you mean 'to_fahrenheit'?"

    assert first_error(fixed2.replace("to_farenheit", "to_fahrenheit")) is None


@pytest.mark.parametrize("platform", ["react", "flutter"])
def test_exercise6_app_builds(platform):
    _, client = load()
    base = PILOT / "solutions" / "ex6_expense_app"
    files = [{"path": str(p.relative_to(base)), "content": p.read_text()} for p in sorted(base.rglob("*.mcn"))]
    quiet(client.post, "/api/workspace/reset", json={"files": files})
    res = quiet(client.post, "/api/build", json={"platform": platform}).get_json()
    assert res["success"] is True, res.get("error")


def test_starter_guide_language_tour_runs(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    guide = (PILOT / "STARTER_GUIDE.md").read_text()
    blocks = re.findall(r"```mcn\n(.*?)```", guide, re.S)
    tour = next(b for b in blocks if "Variables and text" in b)
    run(tour)
