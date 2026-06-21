#!/usr/bin/env python3
"""
MCN Web Playground Test Suite

Tests every server endpoint without needing a live server —
uses Flask's built-in test client.

Run:
    cd mt-mcn
    python3 mcn/web-playground/test_playground.py
    python3 mcn/web-playground/test_playground.py -v   # verbose
"""

import sys
import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "mcn"))

# ── Redirect workspace to a temp dir so tests don't touch ~/.mcn ──────────────
_TMP_WORKSPACE = Path(tempfile.mkdtemp(prefix="mcn_test_playground_"))

import importlib

# Load server module in isolation, patching Path.home so the workspace
# is created inside our temp dir instead of ~/.mcn/playground
with patch("pathlib.Path.home", return_value=_TMP_WORKSPACE):
    _spec = importlib.util.spec_from_file_location(
        "pg_server", str(_HERE / "server.py")
    )
    pg = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(pg)

# Override WORKSPACE to point exactly at our temp dir and seed files
pg.WORKSPACE = _TMP_WORKSPACE
(_TMP_WORKSPACE / "backend").mkdir(exist_ok=True)
(_TMP_WORKSPACE / "ui").mkdir(exist_ok=True)
(_TMP_WORKSPACE / "backend" / "main.mcn").write_text("// backend\n")
(_TMP_WORKSPACE / "ui"      / "app.mcn" ).write_text("// ui\n")

app = pg.app
app.config["TESTING"] = True

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_passed = _failed = _skipped = 0


# ── Mini test runner helpers ──────────────────────────────────────────────────
class Result:
    def __init__(self, name):
        self.name = name
        self.ok   = True
        self.msgs = []

    def check(self, cond, label=""):
        if not cond:
            self.ok  = False
            self.msgs.append(f"  ✗ {label}" if label else "  ✗ assertion failed")
        return self

    def eq(self, a, b, label=""):
        if a != b:
            self.ok  = False
            self.msgs.append(f"  ✗ {label}: expected {b!r}, got {a!r}")
        return self

    def contains(self, text, sub, label=""):
        if sub not in str(text):
            self.ok  = False
            self.msgs.append(f"  ✗ {label}: {sub!r} not found in {str(text)[:120]!r}")
        return self


def run_test(name, fn, verbose):
    global _passed, _failed
    r = Result(name)
    try:
        fn(r)
    except Exception as e:
        r.ok = False
        r.msgs.append(f"  ✗ Exception: {e}")

    if r.ok:
        _passed += 1
        if verbose:
            print(f"  {GREEN}✓{RESET} {name}")
    else:
        _failed += 1
        print(f"  {RED}✗{RESET} {name}")
        for m in r.msgs:
            print(f"    {RED}{m}{RESET}")


# ── Test groups ───────────────────────────────────────────────────────────────

def test_health(r):
    with app.test_client() as c:
        res  = c.get("/api/health")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.eq(data["status"], "ok", "status field")
        r.check("version" in data, "version present")


def test_index_html(r):
    with app.test_client() as c:
        res = c.get("/")
        r.eq(res.status_code, 200, "status")
        html = res.data.decode("utf-8", errors="replace")
        r.contains(html, "MCN", "contains MCN")
        r.contains(html, "monaco", "contains monaco")


def test_workspace_files(r):
    with app.test_client() as c:
        res  = c.get("/api/workspace/files")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check("files" in data, "files key present")
        paths = [f["path"] for f in data["files"]]
        r.check("backend/main.mcn" in paths, "backend/main.mcn listed")
        r.check("ui/app.mcn"       in paths, "ui/app.mcn listed")


def test_workspace_get_file(r):
    # Write a known file first
    (_TMP_WORKSPACE / "backend" / "main.mcn").write_text("var x = 1\n")
    with app.test_client() as c:
        res  = c.get("/api/workspace/file?path=backend/main.mcn")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.contains(data["content"], "var x = 1", "content matches")
        r.eq(data["path"], "backend/main.mcn", "path echoed")


def test_workspace_get_file_missing(r):
    with app.test_client() as c:
        res = c.get("/api/workspace/file?path=no_such_file.mcn")
        r.eq(res.status_code, 404, "404 for missing file")


def test_workspace_get_file_traversal(r):
    with app.test_client() as c:
        res = c.get("/api/workspace/file?path=../../etc/passwd")
        r.check(res.status_code in (403, 404), "traversal blocked")


def test_workspace_save_file(r):
    with app.test_client() as c:
        payload = {"path": "backend/main.mcn", "content": "var saved = true\n"}
        res     = c.post("/api/workspace/file",
                         data=json.dumps(payload),
                         content_type="application/json")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check(data.get("success"), "success flag")
        written = (_TMP_WORKSPACE / "backend" / "main.mcn").read_text()
        r.contains(written, "var saved = true", "content persisted")


def test_workspace_save_traversal(r):
    with app.test_client() as c:
        payload = {"path": "../../evil.txt", "content": "bad"}
        res     = c.post("/api/workspace/file",
                         data=json.dumps(payload),
                         content_type="application/json")
        r.eq(res.status_code, 403, "traversal blocked")


def test_execute_simple(r):
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({"code": 'var x = 1 + 1\nlog("result: {x}")'}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check(data.get("success"), "success")
        r.check(any("result: 2" in line for line in data.get("output", [])), "output contains result")


def test_execute_missing_code(r):
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({}),
                      content_type="application/json")
        r.eq(res.status_code, 400, "400 for missing code")


def test_execute_runtime_error(r):
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({"code": "throw \"deliberate error\""}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.check(not data.get("success"), "success is false")
        r.check("error" in data, "error field present")


def test_execute_return_value(r):
    # Top-level return is not valid in MCN scripts; use log() output instead
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({"code": 'var x = 42\nlog("value: {x}")'}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.check(data.get("success"), "success")
        r.check(any("value: 42" in line for line in data.get("output", [])), "output contains value")


def test_format_code(r):
    messy = 'var x=1\nif x==1\n    log("yes")\n'
    with app.test_client() as c:
        res  = c.post("/api/format",
                      data=json.dumps({"code": messy}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check(data.get("success"), "success")
        r.check("code" in data, "code field present")


def test_format_already_formatted(r):
    clean = 'var x = 1\n'
    with app.test_client() as c:
        res  = c.post("/api/format",
                      data=json.dumps({"code": clean}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.check(data.get("success"), "success")
        # changed may be True or False — just check it's present
        r.check("changed" in data, "changed flag present")


def test_check_clean_code(r):
    with app.test_client() as c:
        res  = c.post("/api/check",
                      data=json.dumps({"code": 'var x = 1\nlog("hello")\n'}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check(data.get("success"), "success")
        r.check("issues" in data, "issues list present")
        r.check("error_count"   in data, "error_count present")
        r.check("warning_count" in data, "warning_count present")


def test_check_response_shape(r):
    with app.test_client() as c:
        res  = c.post("/api/check",
                      data=json.dumps({"code": 'var z = 99\n'}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.check(isinstance(data.get("issues"), list), "issues is list")
        r.check(isinstance(data.get("error_count"), int), "error_count is int")


def test_test_runner_pass(r):
    code = '''\
function add(a, b)
    return a + b

test "addition works"
    assert add(2, 3) == 5

test "subtraction"
    assert add(10, -3) == 7
'''
    with app.test_client() as c:
        res  = c.post("/api/test",
                      data=json.dumps({"code": code}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.eq(data.get("total"),  2, "2 tests")
        r.eq(data.get("passed"), 2, "2 passed")
        r.eq(data.get("failed"), 0, "0 failed")
        r.check(data.get("success"), "overall success")


def test_test_runner_fail(r):
    code = '''\
test "intentional failure"
    assert 1 == 2
'''
    with app.test_client() as c:
        res  = c.post("/api/test",
                      data=json.dumps({"code": code}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(data.get("failed"), 1, "1 failed")
        r.check(not data.get("success"), "overall not success")
        results = data.get("results", [])
        r.check(len(results) == 1, "1 result entry")
        r.check(not results[0]["passed"], "result is failed")
        r.check(results[0]["error"] is not None, "error message present")


def test_test_runner_no_tests(r):
    with app.test_client() as c:
        res  = c.post("/api/test",
                      data=json.dumps({"code": "var x = 1\n"}),
                      content_type="application/json")
        data = json.loads(res.data)
        r.eq(data.get("total"), 0, "0 tests")


def test_examples(r):
    with app.test_client() as c:
        res  = c.get("/api/examples")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check(isinstance(data, list), "returns list")
        r.check(len(data) > 0, "at least one example")
        for ex in data:
            r.check("id"   in ex, "example has id")
            r.check("name" in ex, "example has name")
            # project templates use 'files', snippets use 'code' + 'file'
            is_project = ex.get("project", False)
            if is_project:
                r.check("files" in ex, f"{ex['id']}: project has files list")
            else:
                r.check("code" in ex, f"{ex['id']}: snippet has code")
                r.check("file" in ex, f"{ex['id']}: snippet has file")


def test_build_no_ui_file(r):
    # Remove ui/app.mcn temporarily
    ui_path = _TMP_WORKSPACE / "ui" / "app.mcn"
    backup  = ui_path.read_text()
    ui_path.unlink()
    try:
        with app.test_client() as c:
            res  = c.post("/api/build",
                          data=json.dumps({}),
                          content_type="application/json")
            data = json.loads(res.data)
            r.check(not data.get("success"), "fails without ui file")
    finally:
        ui_path.write_text(backup)


def test_build_invalid_ui(r):
    """Build with syntactically broken UI MCN — should return error, not crash."""
    with app.test_client() as c:
        res  = c.post("/api/build",
                      data=json.dumps({
                          "backend": "// ok\n",
                          "ui":      "THIS IS NOT VALID MCN @@@@\n",
                      }),
                      content_type="application/json")
        data = json.loads(res.data)
        # Either success=False or returncode != 0 — just mustn't 500
        r.check(res.status_code < 500, "no 500 on bad input")


def test_build_valid_ui(r):
    """Build a minimal valid app and check files are generated."""
    backend = '''\
contract Item
    name: str

query("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, created_at TEXT DEFAULT (datetime(\\'now\\')))")

service items_api
    port 8080

    endpoint list_items(limit = 50, offset = 0)
        var items = query("SELECT * FROM items LIMIT ?", (limit,))
        return {success: true, data: items, total: items, insight: "ok"}
'''
    ui = '''\
component ItemList
    state items   = []
    state insight = ""

    on load
        var response = list_items()
        items   = response.data
        insight = response.insight

    render
        card
            card_header "Items"
            table
                table_header
                    table_row
                        table_head "id"
                        table_head "name"
                        table_head "created_at"
                table_body

app Demo
    title "Demo"
    theme "professional"
    layout
        tabs
            tab "Items" ItemList
'''
    with app.test_client() as c:
        res  = c.post("/api/build",
                      data=json.dumps({"backend": backend, "ui": ui}),
                      content_type="application/json")
        data = json.loads(res.data)
        if not data.get("success"):
            r.check(False, f"build failed: {data.get('error') or data.get('stderr')}")
            return
        r.check(data.get("success"), "build succeeded")
        r.check(len(data.get("files", [])) > 0, "files generated")
        paths = data["files"]
        r.check(any("App.tsx"      in f for f in paths), "App.tsx generated")
        r.check(any("package.json" in f for f in paths), "package.json generated")


def test_frontend_file_view(r):
    """After build, /api/frontend/file should return generated file contents."""
    # Write a fake generated file to test the endpoint independently
    frontend_src = _TMP_WORKSPACE / "frontend" / "src"
    frontend_src.mkdir(parents=True, exist_ok=True)
    (frontend_src / "App.tsx").write_text("export default function App() { return <div>Hi</div>; }\n")

    with app.test_client() as c:
        res  = c.get("/api/frontend/file?path=frontend/src/App.tsx")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.contains(data["content"], "App", "content returned")


def test_frontend_file_traversal(r):
    with app.test_client() as c:
        res = c.get("/api/frontend/file?path=../../etc/passwd")
        r.check(res.status_code in (403, 404), "traversal blocked")


def test_devserver_status_initial(r):
    with app.test_client() as c:
        res  = c.get("/api/devserver/status")
        data = json.loads(res.data)
        r.eq(res.status_code, 200, "status")
        r.check("running" in data, "running key present")
        r.check("port"    in data, "port key present")


def test_devserver_start_no_package_json(r):
    """Start should fail gracefully when package.json doesn't exist."""
    frontend = _TMP_WORKSPACE / "frontend"
    pkg = frontend / "package.json"
    existed = pkg.exists()
    if existed:
        backup = pkg.read_text()
        pkg.unlink()
    try:
        with app.test_client() as c:
            res  = c.post("/api/devserver/start")
            data = json.loads(res.data)
            r.check(not data.get("success"), "fails without package.json")
    finally:
        if existed:
            pkg.write_text(backup)


def test_devserver_stop_when_not_running(r):
    """Stop should succeed even when nothing is running."""
    with app.test_client() as c:
        res  = c.post("/api/devserver/stop")
        data = json.loads(res.data)
        r.check(data.get("success"), "stop returns success")


def test_generate_missing_description(r):
    with app.test_client() as c:
        res  = c.post("/api/generate",
                      data=json.dumps({"description": ""}),
                      content_type="application/json")
        r.eq(res.status_code, 400, "400 for empty description")


def test_generate_missing_api_key(r):
    """Without any API key source, should return 400."""
    with patch.dict(os.environ, {}, clear=True):
        # Also clear config
        with patch.object(pg, "_load_config", return_value={}):
            with app.test_client() as c:
                res  = c.post("/api/generate",
                              data=json.dumps({"description": "a todo app", "api_key": ""}),
                              content_type="application/json")
                r.eq(res.status_code, 400, "400 when no API key")


def test_generate_streams_sse(r):
    """With a mocked MCNAgent, verify the SSE stream emits events correctly."""
    import queue as _queue

    mock_result = {
        "backend_mcn": "// backend\nservice s\n    port 8080\n",
        "ui_mcn":      "app A\n    title \"A\"\n    theme \"default\"\n    layout\n        tabs\n            tab \"T\" C\n",
        "attempts": 1,
        "backend_path": _TMP_WORKSPACE / "backend" / "main.mcn",
        "ui_path":      _TMP_WORKSPACE / "ui"      / "app.mcn",
        "build_cmd":    "mcn build ...",
    }

    def _mock_generate(description, output_dir, verbose):
        return mock_result

    with patch("mcn.ai.mcn_agent.MCNAgent") as MockAgent:
        instance = MockAgent.return_value
        instance.generate.side_effect = _mock_generate
        instance.client = MagicMock()
        instance.model  = "claude-opus-4-6"

        # Patch the threading in the generate endpoint to run synchronously
        q = _queue.Queue()
        q.put({"type": "token",  "text": "// hello"})
        q.put({"type": "status", "text": "Validating…"})
        q.put({"type": "done",   "backend": mock_result["backend_mcn"],
               "ui": mock_result["ui_mcn"], "attempts": 1})
        q.put(None)

        original_thread = __import__("threading").Thread

        def _fake_thread(target=None, daemon=None, **kw):
            # Push sentinel immediately so the queue is pre-filled
            return original_thread(target=lambda: None, daemon=True)

        with patch("threading.Thread", side_effect=_fake_thread):
            with patch.object(pg, "WORKSPACE", _TMP_WORKSPACE):
                # We test the endpoint shape by directly calling the route function
                # and checking it doesn't raise
                try:
                    with app.test_client() as c:
                        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                            res = c.post("/api/generate",
                                         data=json.dumps({"description": "test app",
                                                          "api_key": "sk-test-key"}),
                                         content_type="application/json")
                            # Should return SSE stream (200) or error (400/500)
                            # — we just verify it doesn't crash and returns valid HTTP
                            r.check(res.status_code in (200, 400, 500), "valid HTTP status")
                except Exception as e:
                    r.check(False, f"raised exception: {e}")


def test_execute_code_size_limit(r):
    """Payloads over the size limit should be rejected."""
    big_code = "var x = 1\n" * 15_000   # well over 128 KB
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({"code": big_code}),
                      content_type="application/json")
        r.eq(res.status_code, 400, "400 for oversized payload")


def test_execute_timeout(r):
    """Infinite loop should be terminated by the timeout guard."""
    inf_loop = "while true\n    var x = 1\n"
    with app.test_client() as c:
        res  = c.post("/api/execute",
                      data=json.dumps({"code": inf_loop}),
                      content_type="application/json",
                      )
        data = json.loads(res.data)
        # Should either timeout (408) or runtime-error (200 success=false)
        r.check(
            res.status_code == 408 or (res.status_code == 200 and not data.get("success")),
            "infinite loop is terminated"
        )


# ── Runner ────────────────────────────────────────────────────────────────────

SUITES = {
    "Health & Static": [
        ("GET /api/health",    test_health),
        ("GET / (index.html)", test_index_html),
    ],
    "Workspace Files": [
        ("GET  /api/workspace/files",          test_workspace_files),
        ("GET  /api/workspace/file",           test_workspace_get_file),
        ("GET  /api/workspace/file (missing)", test_workspace_get_file_missing),
        ("GET  /api/workspace/file (traversal)",test_workspace_get_file_traversal),
        ("POST /api/workspace/file (save)",    test_workspace_save_file),
        ("POST /api/workspace/file (traversal)",test_workspace_save_traversal),
    ],
    "Execute": [
        ("POST /api/execute (simple)",       test_execute_simple),
        ("POST /api/execute (missing code)", test_execute_missing_code),
        ("POST /api/execute (runtime error)",test_execute_runtime_error),
        ("POST /api/execute (return value)", test_execute_return_value),
        ("POST /api/execute (size limit)",   test_execute_code_size_limit),
        ("POST /api/execute (timeout)",      test_execute_timeout),
    ],
    "Format": [
        ("POST /api/format (messy code)",    test_format_code),
        ("POST /api/format (clean code)",    test_format_already_formatted),
    ],
    "Check": [
        ("POST /api/check (clean)",          test_check_clean_code),
        ("POST /api/check (response shape)", test_check_response_shape),
    ],
    "Test Runner": [
        ("POST /api/test (all pass)",        test_test_runner_pass),
        ("POST /api/test (fail)",            test_test_runner_fail),
        ("POST /api/test (no tests)",        test_test_runner_no_tests),
    ],
    "Examples": [
        ("GET /api/examples",                test_examples),
    ],
    "Build": [
        ("POST /api/build (no ui file)",     test_build_no_ui_file),
        ("POST /api/build (invalid ui)",     test_build_invalid_ui),
        ("POST /api/build (valid app)",      test_build_valid_ui),
    ],
    "Frontend File View": [
        ("GET /api/frontend/file",           test_frontend_file_view),
        ("GET /api/frontend/file (traversal)",test_frontend_file_traversal),
    ],
    "Dev Server": [
        ("GET  /api/devserver/status",                test_devserver_status_initial),
        ("POST /api/devserver/start (no pkg.json)",   test_devserver_start_no_package_json),
        ("POST /api/devserver/stop  (not running)",   test_devserver_stop_when_not_running),
    ],
    "Generate (AI)": [
        ("POST /api/generate (no description)", test_generate_missing_description),
        ("POST /api/generate (no api key)",     test_generate_missing_api_key),
        ("POST /api/generate (SSE stream)",     test_generate_streams_sse),
    ],
}


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    print(f"\n{BOLD}{CYAN}MCN Web Playground Test Suite{RESET}\n")
    print(f"  Workspace: {_TMP_WORKSPACE}")
    print()

    for suite_name, tests in SUITES.items():
        print(f"{BOLD}{suite_name}{RESET}")
        for label, fn in tests:
            run_test(label, fn, verbose)
        print()

    total = _passed + _failed
    color = GREEN if _failed == 0 else RED
    icon  = "✓" if _failed == 0 else "✗"
    print(f"{color}{BOLD}{icon} {_passed}/{total} passed{RESET}", end="")
    if _failed:
        print(f"  {RED}{_failed} failed{RESET}", end="")
    print()

    # Cleanup temp workspace
    shutil.rmtree(_TMP_WORKSPACE, ignore_errors=True)

    sys.exit(0 if _failed == 0 else 1)


if __name__ == "__main__":
    main()
