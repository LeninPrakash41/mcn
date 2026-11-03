"""
The developer workflow: `mcn init` → test → check → serve → build, and the
static checks that back `mcn check` and the VS Code extension.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from playground_app import load, quiet
from mcn.core_engine.diagnostics import check

ROOT = Path(__file__).resolve().parent.parent


def mcn(*args, cwd):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "MCN_HOME": str(Path(cwd) / ".mcn-home")}
    env.pop("ANTHROPIC_API_KEY", None)
    return subprocess.run([sys.executable, "-m", "mcn.core_engine.mcn_cli", *args],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    base = tmp_path_factory.mktemp("init")
    res = mcn("init", "my-app", cwd=base)
    assert res.returncode == 0, res.stdout + res.stderr
    return base / "my-app"


def test_init_creates_a_working_project(project):
    assert {p.name for p in project.iterdir()} >= {"backend", "ui", "README.md", ".gitignore", "mcn.json"}
    assert mcn("test", "backend/main.mcn", cwd=project).returncode == 0
    assert mcn("validate", cwd=project).returncode == 0


def test_init_refuses_a_non_empty_folder(project):
    assert mcn("init", "my-app", cwd=project.parent).returncode == 1


def test_running_leaves_only_the_apps_database_in_the_project(project):
    mcn("run", "backend/main.mcn", cwd=project)
    extra = {p.name for p in project.iterdir()} - {"backend", "ui", "README.md", ".gitignore", "mcn.json", ".mcn-home"}
    assert extra <= {"mcn_data.db"}


@pytest.mark.parametrize("platform", ["react", "flutter"])
def test_init_project_builds(project, platform):
    _, client = load()
    files = [{"path": str(p.relative_to(project)), "content": p.read_text()} for p in project.rglob("*.mcn")]
    quiet(client.post, "/api/workspace/reset", json={"files": files})
    res = quiet(client.post, "/api/build", json={"platform": platform}).get_json()
    assert res["success"] is True, res.get("error")


def test_check_json_reports_location_and_hint(tmp_path):
    (tmp_path / "bad.mcn").write_text("var total = 1\nlog(totl)\n")
    res = mcn("check", "--json", "bad.mcn", cwd=tmp_path)
    assert res.returncode == 1
    [d] = json.loads(res.stdout)["diagnostics"]
    assert (d["kind"], d["line"], d["col"], d["length"], d["hint"]) == \
        ("Name error", 2, 5, 4, "Did you mean 'total'?")


@pytest.mark.parametrize("source", [
    "var o = {success: true, data: [1]}\nlog(o)",                                   # object keys
    "function f(x)\n    return x\nlog(f(1))",                                        # params, any order
    "try\n    throw \"x\"\ncatch\n    log(error)",                                   # bare catch binds error
    "for i, v in [1, 2]\n    log(i + v)",                                            # loop variables
    "log(g())\nfunction g()\n    return 1",                                          # declared later
    'use "healthcare"\nlog(admit_patient({id: "1", name: "a"}))',                    # package exports
    "component C\n    state n = 0\n    on submit\n        save_item(n)\n    render\n        form on_submit=submit\n            text \"x\"",  # UI calls backend
])
def test_check_has_no_false_positives(source):
    assert check(source) == []


def test_check_reports_syntax_error_before_names():
    [d] = check("function f()\nreturn nope\n")
    assert d.kind == "Syntax error" and "indented block" in d.message


def test_methods_fall_back_to_builtins(tmp_path):
    (tmp_path / "m.mcn").write_text('var s = "hello"\nassert s.contains("ell")\nassert s.upper() == "HELLO"\n')
    assert mcn("run", "m.mcn", cwd=tmp_path).returncode == 0
    (tmp_path / "m.mcn").write_text('var s = "hello"\nlog(s.contanis("x"))\n')
    res = mcn("run", "m.mcn", cwd=tmp_path)
    assert "has no method 'contanis'" in res.stderr and "Did you mean 'contains'?" in res.stderr


def test_tasks_run_in_parallel_and_await_by_name_or_position(tmp_path):
    (tmp_path / "t.mcn").write_text(
        "function slow(n)\n    sleep(0.5)\n    return n * 2\n"
        'task "a" slow 1\ntask "b" slow 2\n'
        "var start = now_ms()\n"
        'var r = await("a", "b")\n'
        "assert r.a == 2\nassert r[1] == 4\nassert now_ms() - start < 900\n")
    res = mcn("run", "t.mcn", cwd=tmp_path)
    assert res.returncode == 0, res.stderr


def test_server_get_args_from_path_and_query():
    from mcn.core_engine.mcn_server import _get_args, declared_port
    assert _get_args(["id", "expand"], "42", {"expand": "true"}) == [42, "true"]
    assert _get_args(["limit", "offset"], None, {"limit": "10"}) == [10]
    assert declared_port(str(ROOT / "docs/pilot/solutions/ex5_expenses_api.mcn")) == 8080
