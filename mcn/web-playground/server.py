#!/usr/bin/env python3
"""
MCN Web Playground Server v2.2

Endpoints:
  GET  /                          — serve the playground UI
  GET  /api/health                — liveness check
  GET  /api/examples              — bundled example snippets

  # Workspace (project files)
  GET  /api/workspace/files       — list project files
  GET  /api/workspace/file        — get file content  (?path=...)
  POST /api/workspace/file        — save file content {path, content}

  # MCN operations
  POST /api/execute               — run MCN code
  POST /api/format                — format MCN code
  POST /api/check                 — type-check MCN code
  POST /api/test                  — run test blocks

  # AI Agent
  POST /api/generate              — stream MCN generation via SSE

  # Compiler + preview
  POST /api/build                 — compile ui/app.mcn → React project
  GET  /api/frontend/file         — read generated file (?path=...)
  POST /api/devserver/start       — start Vite dev server
  POST /api/devserver/stop        — stop Vite dev server
  GET  /api/devserver/status      — poll dev server health
"""

import sys
import os
import io
import json
import queue
import signal
import subprocess
import threading
import traceback
import contextlib
import zipfile
from pathlib import Path

# ── Workspace ─────────────────────────────────────────────────────────────────

WORKSPACE = Path.home() / ".mcn" / "playground"
WORKSPACE.mkdir(parents=True, exist_ok=True)

# ── Path helper ───────────────────────────────────────────────────────────────

def _safe_path(rel: str) -> Path:
    """Resolve a relative path against WORKSPACE; raise ValueError on traversal."""
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f"Path traversal attempt: {rel!r}")
    return p

# ── Package root in sys.path ──────────────────────────────────────────────────

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_DIR = os.path.dirname(_THIS_DIR)
_ROOT_DIR    = os.path.dirname(_PACKAGE_DIR)
for _p in (_PACKAGE_DIR, _ROOT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Flask ─────────────────────────────────────────────────────────────────────

try:
    from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
    from flask_cors import CORS
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors", "-q"])
    from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
    from flask_cors import CORS

# ── MCN imports ───────────────────────────────────────────────────────────────

try:
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.core_engine.formatter       import format_source
    from mcn.core_engine.type_checker    import check_source, Severity
    from mcn.core_engine.test_runner     import TestRunner
    from mcn.core_engine.mcn_cli         import _load_config
except ImportError:
    from core_engine.mcn_interpreter import MCNInterpreter
    from core_engine.formatter       import format_source
    from core_engine.type_checker    import check_source, Severity
    from core_engine.test_runner     import TestRunner
    def _load_config(): return {}

# ── Auth (optional — anonymous users share the default workspace) ──────────────

try:
    from mcn.core_engine.auth_primitives import (
        auth_create_user, auth_login, auth_verify_token,
        auth_get_user, auth_require
    )
    _AUTH_AVAILABLE = True
except ImportError:
    try:
        from core_engine.auth_primitives import (  # type: ignore
            auth_create_user, auth_login, auth_verify_token,
            auth_get_user, auth_require
        )
        _AUTH_AVAILABLE = True
    except ImportError:
        _AUTH_AVAILABLE = False

_WORKSPACES_DIR = Path.home() / ".mcn" / "workspaces"
_WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)


def _bearer_token() -> str:
    """Extract Bearer token from Authorization header (or empty string)."""
    hdr = request.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip()
    return ""


def _current_user() -> dict | None:
    """Return decoded token payload for the current request, or None."""
    if not _AUTH_AVAILABLE:
        return None
    tok = _bearer_token()
    if not tok:
        return None
    return auth_verify_token(tok)


def _request_workspace() -> Path:
    """Return the workspace directory for the current request.
    Authenticated users get their own isolated dir; anonymous share the default."""
    user = _current_user()
    if user and user.get("sub"):
        ws = _WORKSPACES_DIR / user["sub"]
        ws.mkdir(parents=True, exist_ok=True)
        return ws
    return WORKSPACE


def _safe_path_for(rel: str, ws: Path) -> Path:
    """Resolve rel against ws; raise on traversal."""
    p = (ws / rel).resolve()
    if not str(p).startswith(str(ws.resolve())):
        raise ValueError(f"Path traversal attempt: {rel!r}")
    return p


# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=".")
CORS(app)

_MAX_CODE_BYTES = 128 * 1024   # 128 KB
_EXEC_TIMEOUT_S = 10

# Dev server process (module-level singleton)
_dev_server: subprocess.Popen | None = None
_mcn_backend: subprocess.Popen | None = None
_DEV_PORT     = 5174
_BACKEND_PORT = 8080

# ── npm availability check ────────────────────────────────────────────────────
def _npm_available() -> bool:
    try:
        subprocess.run(["npm", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

_NPM_AVAILABLE = _npm_available()


# ── Shared helpers ────────────────────────────────────────────────────────────

@contextlib.contextmanager
def _capture_stdout():
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old


def _run_with_timeout(fn, timeout: float):
    result, exc_box, finished = [None], [None], threading.Event()
    def _t():
        try:    result[0] = fn()
        except Exception as e: exc_box[0] = e
        finally: finished.set()
    threading.Thread(target=_t, daemon=True).start()
    if not finished.wait(timeout):
        raise TimeoutError(f"Execution exceeded {timeout}s")
    if exc_box[0]:
        raise exc_box[0]
    return result[0]


def _validate_code(data) -> str | None:
    if not data or "code" not in data:
        return "Missing 'code' field"
    if not isinstance(data["code"], str):
        return "'code' must be a string"
    if len(data["code"].encode()) > _MAX_CODE_BYTES:
        return f"Code exceeds {_MAX_CODE_BYTES // 1024} KB limit"
    return None


def _sse(event_dict: dict) -> str:
    return f"data: {json.dumps(event_dict)}\n\n"


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(_THIS_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "2.2", "auth": _AUTH_AVAILABLE})


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    if not _AUTH_AVAILABLE:
        return jsonify({"error": "Auth not available"}), 503
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    try:
        user  = auth_create_user(email, password)
        token = auth_login(email, password)
        # Decode token to get user id for workspace dir
        payload = auth_verify_token(token) or {}
        user_id = payload.get("sub") or user.get("id") or email
        ws = _WORKSPACES_DIR / str(user_id)
        ws.mkdir(parents=True, exist_ok=True)
        _seed_workspace(ws)
        safe_user = {"id": user_id, "email": email, "roles": payload.get("roles", [])}
        return jsonify({"success": True, "token": token, "user": safe_user})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/api/auth/login", methods=["POST"])
def auth_login_endpoint():
    if not _AUTH_AVAILABLE:
        return jsonify({"error": "Auth not available"}), 503
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    try:
        token   = auth_login(email, password)
        payload = auth_verify_token(token) or {}
        user_id = payload.get("sub") or email
        # Ensure workspace exists for returning users
        ws = _WORKSPACES_DIR / str(user_id)
        if not ws.exists():
            ws.mkdir(parents=True, exist_ok=True)
            _seed_workspace(ws)
        return jsonify({
            "success": True,
            "token":   token,
            "user":    {"id": user_id, "email": payload.get("email", email),
                        "roles": payload.get("roles", [])},
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 401


@app.route("/api/auth/me")
def auth_me():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        full = auth_get_user(user["sub"]) if _AUTH_AVAILABLE else user
    except Exception:
        full = user
    safe = {
        "id":    user.get("sub"),
        "email": user.get("email", ""),
        "roles": user.get("roles", []),
    }
    if isinstance(full, dict):
        safe.update({k: v for k, v in full.items() if k not in ("password", "hash")})
    return jsonify({"success": True, "user": safe})


# ── Workspace endpoints ───────────────────────────────────────────────────────

_DEFAULT_BACKEND = '''\
// MCN Backend — edit me and click ⚡ Build
contract Item
    name: str
    price: float

query("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, created_at TEXT DEFAULT (datetime('now')))")

service items_api
    port 8080

    endpoint list_items()
        var items = query("SELECT * FROM items ORDER BY created_at DESC")
        return {success: true, data: items}

    endpoint create_item(name, price)
        query("INSERT INTO items (name, price) VALUES (?, ?)", (name, price))
        var id = query("SELECT last_insert_rowid() as id")[0].id
        return {success: true, id: id}

    endpoint delete_item(id)
        query("DELETE FROM items WHERE id=?", (id,))
        return {success: true}
'''

_DEFAULT_UI = '''\
component ItemForm
    state name    = ""
    state price   = 0
    state message = ""

    on submit
        var result = create_item(name, price)
        if result.success
            message = "Created item!"

    render
        card
            card_header "Add Item"
            form on_submit=submit
                input bind=name label="Name"
                input bind=price label="Price" type="number"
                button "Add Item" variant="default"
                div
                    text message

component ItemTable
    state items = []

    on load
        var resp = list_items()
        items = resp.data

    render
        card
            card_header "All Items"
            table
                table_header
                    table_row
                        table_head "name"
                        table_head "price"
                        table_head "created_at"
                table_body

app ItemManager
    title  "Item Manager"
    layout
        tabs
            tab "Add Item"  ItemForm
            tab "All Items" ItemTable
'''


def _seed_workspace(ws: Path | None = None):
    """Write default starter files if workspace is empty or missing MCN files."""
    ws = ws or WORKSPACE
    backend_dir = ws / "backend"
    ui_dir      = ws / "ui"
    backend_dir.mkdir(parents=True, exist_ok=True)
    ui_dir.mkdir(parents=True, exist_ok=True)
    backend_file = backend_dir / "main.mcn"
    ui_file      = ui_dir / "app.mcn"
    if not backend_file.exists():
        backend_file.write_text(_DEFAULT_BACKEND, encoding="utf-8")
    if not ui_file.exists():
        ui_file.write_text(_DEFAULT_UI, encoding="utf-8")


@app.route("/api/workspace/reset", methods=["POST"])
def workspace_reset():
    """Wipe workspace MCN source files and re-seed with defaults (keeps frontend/)."""
    import shutil
    ws   = _request_workspace()
    data = request.get_json(silent=True) or {}
    files_payload = data.get("files")  # [{path, content}, ...] for project templates
    try:
        # Stop any running dev server and backend before wiping the workspace
        global _dev_server, _mcn_backend
        _stop_process(_dev_server);  _dev_server  = None
        _stop_process(_mcn_backend); _mcn_backend = None

        # Remove source dirs and generated frontend
        for d in ("backend", "ui"):
            p = ws / d
            if p.exists():
                shutil.rmtree(p)
        # Also clear old frontend build
        frontend = ws / "frontend"
        if frontend.exists():
            shutil.rmtree(frontend)
        if files_payload:
            # Write each file from the template
            written = []
            for item in files_payload:
                rel  = item.get("path", "")
                code = item.get("content", "")
                if not rel:
                    continue
                p = _safe_path_for(rel, ws)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(code, encoding="utf-8")
                written.append(rel)
            return jsonify({"success": True, "written": written})
        else:
            _seed_workspace(ws)
            return jsonify({"success": True, "written": ["backend/main.mcn", "ui/app.mcn"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/workspace/files")
def workspace_files():
    """Return file tree of the workspace (mcn + generated frontend files)."""
    ws    = _request_workspace()
    files = []
    for p in sorted(ws.rglob("*")):
        if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
            rel = str(p.relative_to(ws))
            files.append({"path": rel, "type": "file"})
    if not files:
        _seed_workspace(ws)
        files = [{"path": "backend/main.mcn", "type": "file"},
                 {"path": "ui/app.mcn",       "type": "file"}]
    return jsonify({"files": files, "user": _current_user()})


@app.route("/api/workspace/file")
def get_workspace_file():
    ws  = _request_workspace()
    rel = request.args.get("path", "")
    if not rel:
        return jsonify({"error": "Missing ?path"}), 400
    try:
        p = _safe_path_for(rel, ws)
        if not p.exists():
            return jsonify({"error": "File not found"}), 404
        return jsonify({"path": rel, "content": p.read_text(encoding="utf-8")})
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@app.route("/api/workspace/file", methods=["POST"])
def save_workspace_file():
    ws   = _request_workspace()
    data = request.get_json(silent=True) or {}
    rel  = data.get("path", "")
    content = data.get("content", "")
    if not rel:
        return jsonify({"error": "Missing 'path'"}), 400
    try:
        p = _safe_path_for(rel, ws)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


# ── MCN execute / format / check / test ───────────────────────────────────────

@app.route("/api/execute", methods=["POST"])
def execute_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err, "output": []}), 400

    code, output_lines = data["code"], []

    def run():
        interp = MCNInterpreter()
        def _capture_log(*args):
            output_lines.append(" ".join(str(a) for a in args))
        interp._functions["log"]  = _capture_log
        interp._functions["echo"] = _capture_log
        with _capture_stdout() as buf:
            result = interp.execute(code, quiet=True)
            printed = buf.getvalue()
        if printed:
            output_lines.extend(printed.splitlines())
        return result

    try:
        result = _run_with_timeout(run, _EXEC_TIMEOUT_S)
        return jsonify({"success": True, "output": output_lines,
                        "result": str(result) if result is not None else None})
    except TimeoutError as e:
        return jsonify({"success": False, "error": str(e), "output": output_lines}), 408
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "output": output_lines})


@app.route("/api/format", methods=["POST"])
def fmt_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        formatted = format_source(data["code"])
        return jsonify({"success": True, "formatted": formatted, "changed": formatted != data["code"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/check", methods=["POST"])
def check_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        issues = check_source(data["code"])
        error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
        return jsonify({
            "success":       True,
            "ok":            error_count == 0,
            "errors":        [f"Line {i.line}: {i.message}" for i in issues if i.severity == Severity.ERROR],
            "warnings":      [f"Line {i.line}: {i.message}" for i in issues if i.severity == Severity.WARNING],
            "issues":        [{"severity": i.severity.value, "line": i.line,
                               "col": i.col, "message": i.message} for i in issues],
            "error_count":   error_count,
            "warning_count": sum(1 for i in issues if i.severity == Severity.WARNING),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/test", methods=["POST"])
def test_mcn():
    """Batch test endpoint (non-streaming, for CLI / simple clients)."""
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        runner  = TestRunner(verbose=False)
        results = runner.run_source(data["code"], label="<playground>")
        passed  = sum(1 for r in results if r.passed)
        failed  = len(results) - passed
        output  = []
        for r in results:
            status = "✓" if r.passed else "✗"
            output.append(f"{status} {r.description}")
            if not r.passed and r.error:
                output.append(f"  {r.error}")
        if not results:
            output.append("(no tests found)")
        return jsonify({
            "success": failed == 0,
            "total": len(results), "passed": passed, "failed": failed,
            "output": output,
            "results": [{"description": r.description, "passed": r.passed,
                         "error": r.error if not r.passed else None,
                         "elapsed_ms": round(r.elapsed * 1000, 2)} for r in results],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/test/stream", methods=["POST"])
def test_mcn_stream():
    """Streaming SSE endpoint — emits each test result as it completes."""
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return Response(_sse({"type": "error", "message": err}),
                        mimetype="text/event-stream"), 400

    code = data["code"]

    # Run tests in a background thread; feed results into a queue for SSE yield
    result_q: queue.Queue = queue.Queue()

    def _run_tests():
        runner = TestRunner(verbose=False)
        try:
            # Parse manually so we can stream per-test
            from mcn.core_engine.lexer    import Lexer as _L
            from mcn.core_engine.parser   import Parser as _P
            from mcn.core_engine.evaluator import Evaluator as _E
            import mcn.core_engine.ast_nodes as _ast
        except ImportError:
            try:
                from core_engine.lexer    import Lexer as _L    # type: ignore
                from core_engine.parser   import Parser as _P   # type: ignore
                from core_engine.evaluator import Evaluator as _E  # type: ignore
                import core_engine.ast_nodes as _ast             # type: ignore
            except ImportError:
                result_q.put({"type": "error", "message": "Cannot import MCN core"})
                result_q.put(None)
                return

        try:
            tokens  = _L(code).tokenize()
            program = _P(tokens).parse()
        except Exception as exc:
            result_q.put({"type": "error", "message": str(exc)})
            result_q.put(None)
            return

        setup_stmts = [s for s in program.body if not isinstance(s, _ast.TestDecl)]
        test_decls  = [s for s in program.body if isinstance(s, _ast.TestDecl)]

        if not test_decls:
            result_q.put({"type": "done", "total": 0, "passed": 0, "failed": 0})
            result_q.put(None)
            return

        result_q.put({"type": "start", "total": len(test_decls)})

        functions: dict = {}
        runner._register_builtins(functions)
        evaluator = _E(functions)
        try:
            evaluator._exec_block(setup_stmts, evaluator.globals)
        except Exception as exc:
            result_q.put({"type": "result", "description": "<setup>", "passed": False,
                          "error": f"Setup failed: {exc}", "elapsed_ms": 0})
            result_q.put({"type": "done", "total": 1, "passed": 0, "failed": 1})
            result_q.put(None)
            return

        passed = 0
        failed = 0
        for decl in test_decls:
            r = runner._run_test(decl, evaluator)
            passed += r.passed
            failed += not r.passed
            result_q.put({
                "type":        "result",
                "description": r.description,
                "passed":      r.passed,
                "error":       r.error if not r.passed else None,
                "elapsed_ms":  round(r.elapsed * 1000, 2),
            })

        result_q.put({"type": "done",
                      "total": len(test_decls), "passed": passed, "failed": failed})
        result_q.put(None)  # sentinel

    threading.Thread(target=_run_tests, daemon=True).start()

    def generate():
        while True:
            try:
                item = result_q.get(timeout=30)
            except queue.Empty:
                yield _sse({"type": "error", "message": "Test timeout"})
                break
            if item is None:
                break
            yield _sse(item)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── AI Generate (SSE) ─────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate_mcn():
    data        = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    api_key     = (data.get("api_key") or "").strip() \
                  or _load_config().get("api_key") \
                  or os.getenv("ANTHROPIC_API_KEY") \
                  or os.getenv("OPENAI_API_KEY")

    if not description:
        return jsonify({"error": "Missing 'description'"}), 400
    if not api_key:
        return jsonify({"error": "No API key found. Enter your Claude API key in the modal or run: mcn config set api_key sk-ant-..."}), 400

    ws = _request_workspace()
    token_queue: queue.Queue = queue.Queue()
    result_box = [None]  # filled by thread: {backend, ui, attempts} or {error}

    def _agent_thread():
        try:
            try:
                from mcn.ai.mcn_agent import MCNAgent
                from mcn.ai.mcn_spec  import MCN_SYSTEM_PROMPT
            except ImportError:
                from ai.mcn_agent import MCNAgent          # type: ignore
                from ai.mcn_spec  import MCN_SYSTEM_PROMPT  # type: ignore

            agent = MCNAgent(api_key=api_key, model="claude-opus-4-6")

            # ── Patch _call_claude so every token goes into the SSE queue ──
            original_call = agent._call_claude.__func__  # unbound method

            def _streaming_call(self_inner, prompt, system, verbose):
                chunks = []
                with self_inner.client.messages.stream(
                    model=self_inner.model,
                    max_tokens=8192,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                        token_queue.put({"type": "token", "text": text})
                return "".join(chunks)

            import types
            agent._call_claude = types.MethodType(_streaming_call, agent)

            token_queue.put({"type": "status", "text": "Generating MCN app…"})

            result = agent.generate(
                description=description,
                output_dir=str(ws),
                verbose=False,
            )

            token_queue.put({"type": "status",
                             "text": f"✓ Validated in {result['attempts']} attempt(s)"})
            result_box[0] = {
                "backend":  result["backend_mcn"],
                "ui":       result["ui_mcn"],
                "attempts": result["attempts"],
            }
        except Exception as exc:
            import traceback as _tb
            result_box[0] = {"error": str(exc), "trace": _tb.format_exc()}
        finally:
            token_queue.put(None)  # sentinel — always sent

    threading.Thread(target=_agent_thread, daemon=True).start()

    def _stream():
        while True:
            try:
                item = token_queue.get(timeout=120)
            except queue.Empty:
                yield _sse({"type": "error", "message": "Generation timed out after 120s"})
                return
            if item is None:
                r = result_box[0] or {}
                if "error" in r:
                    yield _sse({"type": "error", "message": r["error"]})
                else:
                    yield _sse({"type": "done", **r})
                return
            yield _sse(item)

    resp = Response(stream_with_context(_stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"]     = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ── Build ─────────────────────────────────────────────────────────────────────

@app.route("/api/build", methods=["POST"])
def build_mcn():
    data = request.get_json(silent=True) or {}

    # Optionally pre-save both files from the request body
    for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
        if key in data and data[key]:
            (WORKSPACE / rel).parent.mkdir(parents=True, exist_ok=True)
            (WORKSPACE / rel).write_text(data[key], encoding="utf-8")

    ui_path  = WORKSPACE / "ui" / "app.mcn"
    out_path = WORKSPACE / "frontend"

    if not ui_path.exists():
        return jsonify({"success": False, "error": "ui/app.mcn not found"}), 400

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mcn.core_engine.mcn_cli", "build",
             str(ui_path), "--out", str(out_path)],
            capture_output=True, text=True,
            cwd=str(_ROOT_DIR),
        )
        stdout = proc.stdout
        stderr = proc.stderr

        if proc.returncode != 0:
            return jsonify({"success": False, "error": stderr or stdout})

        # Collect generated files
        files = []
        if out_path.exists():
            for p in sorted(out_path.rglob("*")):
                if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
                    files.append(str(p.relative_to(WORKSPACE)))

        return jsonify({"success": True, "files": files, "stdout": stdout, "stderr": stderr})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/download")
def download_project():
    """Zip the generated frontend directory and return as a download."""
    frontend = WORKSPACE / "frontend"
    if not frontend.exists():
        return jsonify({"error": "No built frontend. Run Build first."}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(frontend.rglob("*")):
            if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
                zf.write(p, p.relative_to(WORKSPACE))
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=mcn-frontend.zip"},
    )


@app.route("/api/deploy", methods=["POST"])
def deploy_project():
    """Package the workspace into a Docker-ready zip and return it as base64 JSON."""
    data     = request.get_json(silent=True) or {}
    app_name = (data.get("app_name") or "mcn-app").strip().replace(" ", "-") or "mcn-app"
    target   = data.get("target", "zip")

    try:
        try:
            from mcn.core_engine.mcn_deployer import deploy_workspace
        except ImportError:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from core_engine.mcn_deployer import deploy_workspace  # type: ignore

        result   = deploy_workspace(WORKSPACE, app_name=app_name, target=target)
        import base64
        zip_b64  = base64.b64encode(result["zip_bytes"]).decode()
        return jsonify({
            "success":        True,
            "app_name":       app_name,
            "target":         target,
            "files_included": result["files_included"],
            "docker_cmd":     result["docker_cmd"],
            "cloud_url":      result.get("cloud_url"),
            "zip_b64":        zip_b64,
            "zip_filename":   f"{app_name}.zip",
            "size_kb":        len(result["zip_bytes"]) // 1024,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/frontend/file")
def get_frontend_file():
    rel = request.args.get("path", "")
    if not rel:
        return jsonify({"error": "Missing ?path"}), 400
    try:
        p = _safe_path(rel)
        if not p.exists():
            return jsonify({"error": "File not found"}), 404
        return jsonify({"path": rel, "content": p.read_text(encoding="utf-8")})
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


# ── Dev server ────────────────────────────────────────────────────────────────

def _stop_process(proc):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


@app.route("/api/devserver/start", methods=["POST"])
def devserver_start():
    global _dev_server, _mcn_backend
    ws           = _request_workspace()
    frontend     = ws / "frontend"
    backend_file = ws / "backend" / "main.mcn"

    if not (frontend / "package.json").exists():
        return jsonify({"success": False, "error": "frontend/package.json not found. Run ⚡ Build first."}), 400

    if _dev_server and _dev_server.poll() is None:
        return jsonify({"success": True, "port": _DEV_PORT, "pid": _dev_server.pid, "already_running": True})

    # ── 1. Start MCN backend (if backend/main.mcn has a service declaration) ─
    if backend_file.exists():
        backend_src = backend_file.read_text(encoding="utf-8")
        if "service " in backend_src:
            _stop_process(_mcn_backend)
            try:
                _mcn_backend = subprocess.Popen(
                    [sys.executable, "-m", "mcn.core_engine.mcn_cli", "serve",
                     "--file", str(backend_file), "--host", "0.0.0.0",
                     "--port", str(_BACKEND_PORT)],
                    cwd=str(_ROOT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                import time; time.sleep(1)
            except Exception:
                pass  # Non-fatal

    # ── 2. npm not available → serve built files via Flask static ─────────────
    if not _NPM_AVAILABLE:
        # Serve the built frontend/dist or frontend/src statically via Flask
        dist = frontend / "dist"
        serve_dir = dist if dist.exists() else frontend
        app.static_folder = str(serve_dir)
        app.static_url_path = "/preview"
        return jsonify({
            "success":      True,
            "port":         None,
            "mode":         "static",
            "preview_url":  "/preview/index.html",
            "backend_port": _BACKEND_PORT if (_mcn_backend and _mcn_backend.poll() is None) else None,
            "npm_missing":  True,
            "message":      "npm not found — serving built files statically at /preview/index.html",
        })

    # ── 3. npm install if needed ──────────────────────────────────────────────
    if not (frontend / "node_modules").exists():
        proc = subprocess.run(["npm", "install"], cwd=str(frontend),
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return jsonify({"success": False,
                            "error": f"npm install failed:\n{proc.stderr[-2000:]}"}), 500

    # ── 4. Start Vite dev server ──────────────────────────────────────────────
    try:
        _dev_server = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(_DEV_PORT), "--host"],
            cwd=str(frontend),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        import time; time.sleep(2)
        if _dev_server.poll() is not None:
            stderr = _dev_server.stderr.read().decode(errors="replace")
            return jsonify({"success": False, "error": f"Vite failed to start:\n{stderr[-1000:]}"}), 500
        return jsonify({
            "success":      True,
            "port":         _DEV_PORT,
            "pid":          _dev_server.pid,
            "mode":         "vite",
            "preview_url":  f"http://localhost:{_DEV_PORT}",
            "backend_port": _BACKEND_PORT if (_mcn_backend and _mcn_backend.poll() is None) else None,
        })
    except FileNotFoundError:
        return jsonify({"success": False,
                        "error": "npm not found. Install Node.js or use the static preview."}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/devserver/stop", methods=["POST"])
def devserver_stop():
    global _dev_server, _mcn_backend
    _stop_process(_dev_server)
    _dev_server = None
    _stop_process(_mcn_backend)
    _mcn_backend = None
    return jsonify({"success": True})


@app.route("/api/devserver/status")
def devserver_status():
    global _dev_server, _mcn_backend
    running         = _dev_server is not None and _dev_server.poll() is None
    backend_running = _mcn_backend is not None and _mcn_backend.poll() is None
    return jsonify({
        "running":         running,
        "port":            _DEV_PORT if running else None,
        "pid":             _dev_server.pid if running else None,
        "backend_running": backend_running,
        "backend_port":    _BACKEND_PORT if backend_running else None,
        "npm_available":   _NPM_AVAILABLE,
    })


# ── Examples ──────────────────────────────────────────────────────────────────

_CRM_BACKEND = (
'contract Deal\n'
'    title: str\n'
'    value: float\n'
'    stage: str\n'
'    contact: str\n'
'\n'
'contract Contact\n'
'    name: str\n'
'    email: str\n'
'    company: str\n'
'    phone: str\n'
'\n'
'contract Company\n'
'    name: str\n'
'    industry: str\n'
'    size: str\n'
'\n'
'contract Activity\n'
'    title: str\n'
'    type: str\n'
'    contact: str\n'
'    due_date: str\n'
'\n'
'query("CREATE TABLE IF NOT EXISTS deals (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, value REAL, stage TEXT, contact TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n'
'query("CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, company TEXT, phone TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n'
'query("CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, industry TEXT, size TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n'
'query("CREATE TABLE IF NOT EXISTS activities (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, type TEXT, contact TEXT, due_date TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n'
'\n'
'service crm_api\n'
'    port 8080\n'
'\n'
'    endpoint list_deals(limit = 50)\n'
'        var items = query("SELECT * FROM deals ORDER BY created_at DESC LIMIT ?", (limit,))\n'
'        return {success: true, data: items}\n'
'\n'
'    endpoint create_deal(title, value, stage, contact)\n'
'        query("INSERT INTO deals (title, value, stage, contact) VALUES (?, ?, ?, ?)", (title, value, stage, contact))\n'
'        var id = query("SELECT last_insert_rowid() as id")[0].id\n'
'        return {success: true, id: id}\n'
'\n'
'    endpoint update_deal(id, title, value, stage, contact)\n'
'        query("UPDATE deals SET title=?, value=?, stage=?, contact=? WHERE id=?", (title, value, stage, contact, id))\n'
'        return {success: true}\n'
'\n'
'    endpoint delete_deal(id)\n'
'        query("DELETE FROM deals WHERE id=?", (id,))\n'
'        return {success: true}\n'
'\n'
'    endpoint list_contacts(limit = 50)\n'
'        var items = query("SELECT * FROM contacts ORDER BY created_at DESC LIMIT ?", (limit,))\n'
'        return {success: true, data: items}\n'
'\n'
'    endpoint create_contact(name, email, company, phone)\n'
'        query("INSERT INTO contacts (name, email, company, phone) VALUES (?, ?, ?, ?)", (name, email, company, phone))\n'
'        var id = query("SELECT last_insert_rowid() as id")[0].id\n'
'        return {success: true, id: id}\n'
'\n'
'    endpoint update_contact(id, name, email, company, phone)\n'
'        query("UPDATE contacts SET name=?, email=?, company=?, phone=? WHERE id=?", (name, email, company, phone, id))\n'
'        return {success: true}\n'
'\n'
'    endpoint delete_contact(id)\n'
'        query("DELETE FROM contacts WHERE id=?", (id,))\n'
'        return {success: true}\n'
'\n'
'    endpoint list_companies(limit = 50)\n'
'        var items = query("SELECT * FROM companies ORDER BY created_at DESC LIMIT ?", (limit,))\n'
'        return {success: true, data: items}\n'
'\n'
'    endpoint create_company(name, industry, size)\n'
'        query("INSERT INTO companies (name, industry, size) VALUES (?, ?, ?)", (name, industry, size))\n'
'        var id = query("SELECT last_insert_rowid() as id")[0].id\n'
'        return {success: true, id: id}\n'
'\n'
'    endpoint update_company(id, name, industry, size)\n'
'        query("UPDATE companies SET name=?, industry=?, size=? WHERE id=?", (name, industry, size, id))\n'
'        return {success: true}\n'
'\n'
'    endpoint delete_company(id)\n'
'        query("DELETE FROM companies WHERE id=?", (id,))\n'
'        return {success: true}\n'
'\n'
'    endpoint list_activities(limit = 50)\n'
'        var items = query("SELECT * FROM activities ORDER BY created_at DESC LIMIT ?", (limit,))\n'
'        return {success: true, data: items}\n'
'\n'
'    endpoint create_activity(title, type, contact, due_date)\n'
'        query("INSERT INTO activities (title, type, contact, due_date) VALUES (?, ?, ?, ?)", (title, type, contact, due_date))\n'
'        var id = query("SELECT last_insert_rowid() as id")[0].id\n'
'        return {success: true, id: id}\n'
'\n'
'    endpoint update_activity(id, title, type, contact, due_date)\n'
'        query("UPDATE activities SET title=?, type=?, contact=?, due_date=? WHERE id=?", (title, type, contact, due_date, id))\n'
'        return {success: true}\n'
'\n'
'    endpoint delete_activity(id)\n'
'        query("DELETE FROM activities WHERE id=?", (id,))\n'
'        return {success: true}\n'
)

_CRM_UI = (
'component Dashboard\n'
'    state deals       = []\n'
'    state contacts    = []\n'
'    state companies   = []\n'
'    state activities  = []\n'
'\n'
'    on load\n'
'        var d = list_deals()\n'
'        deals = d.data\n'
'        var c = list_contacts()\n'
'        contacts = c.data\n'
'        var co = list_companies()\n'
'        companies = co.data\n'
'        var a = list_activities()\n'
'        activities = a.data\n'
'\n'
'    render\n'
'        div\n'
'            h2 "Overview"\n'
'            div grid_cols=4\n'
'                stat_card label="Total Deals"     value=deals.length     icon="TrendingUp"   color="blue"\n'
'                stat_card label="Contacts"        value=contacts.length  icon="Users"        color="green"\n'
'                stat_card label="Companies"       value=companies.length icon="Building2"    color="purple"\n'
'                stat_card label="Activities"      value=activities.length icon="Calendar"    color="amber"\n'
'            card\n'
'                card_header "Recent Deals"\n'
'                table\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "title"\n'
'                            table_head "value"\n'
'                            table_head "stage"\n'
'                            table_head "contact"\n'
'                    table_body\n'
'\n'
'component DealsTable\n'
'    state items           = []\n'
'    state edit_item       = null\n'
'    state edit_title      = ""\n'
'    state edit_value      = 0\n'
'    state edit_stage      = ""\n'
'    state edit_contact    = ""\n'
'    state show_edit_modal = false\n'
'    state new_title       = ""\n'
'    state new_value       = 0\n'
'    state new_stage       = "Prospecting"\n'
'    state new_contact     = ""\n'
'\n'
'    on load\n'
'        var resp = list_deals()\n'
'        items = resp.data\n'
'\n'
'    on submit\n'
'        var result = create_deal(new_title, new_value, new_stage, new_contact)\n'
'        if result.success\n'
'            var resp = list_deals()\n'
'            items = resp.data\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Deal"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=new_title label="Deal Title"\n'
'                        input bind=new_value label="Value ($)" type="number"\n'
'                    div grid_cols=2\n'
'                        select bind=new_stage options=["Prospecting","Qualification","Proposal","Negotiation","Won","Lost"] label="Stage"\n'
'                        input bind=new_contact label="Contact Name"\n'
'                    button "Add Deal" variant="default"\n'
'            card\n'
'                card_header "All Deals"\n'
'                table\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "title"\n'
'                            table_head "value"\n'
'                            table_head "stage"\n'
'                            table_head "contact"\n'
'                    table_body\n'
'        modal show=show_edit_modal\n'
'            card_header "Edit Deal"\n'
'            form on_submit=handleSave\n'
'                input bind=edit_title label="Title"\n'
'                input bind=edit_value label="Value" type="number"\n'
'                select bind=edit_stage options=["Prospecting","Qualification","Proposal","Negotiation","Won","Lost"] label="Stage"\n'
'                input bind=edit_contact label="Contact"\n'
'                button "Save Changes" variant="default"\n'
'\n'
'component ContactsTable\n'
'    state items           = []\n'
'    state edit_item       = null\n'
'    state edit_name       = ""\n'
'    state edit_email      = ""\n'
'    state edit_company    = ""\n'
'    state edit_phone      = ""\n'
'    state show_edit_modal = false\n'
'    state new_name        = ""\n'
'    state new_email       = ""\n'
'    state new_company     = ""\n'
'    state new_phone       = ""\n'
'\n'
'    on load\n'
'        var resp = list_contacts()\n'
'        items = resp.data\n'
'\n'
'    on submit\n'
'        var result = create_contact(new_name, new_email, new_company, new_phone)\n'
'        if result.success\n'
'            var resp = list_contacts()\n'
'            items = resp.data\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Contact"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=new_name label="Full Name"\n'
'                        input bind=new_email label="Email" type="email"\n'
'                    div grid_cols=2\n'
'                        input bind=new_company label="Company"\n'
'                        input bind=new_phone label="Phone"\n'
'                    button "Add Contact" variant="default"\n'
'            card\n'
'                card_header "All Contacts"\n'
'                table\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "name"\n'
'                            table_head "email"\n'
'                            table_head "company"\n'
'                            table_head "phone"\n'
'                    table_body\n'
'        modal show=show_edit_modal\n'
'            card_header "Edit Contact"\n'
'            form on_submit=handleSave\n'
'                input bind=edit_name label="Name"\n'
'                input bind=edit_email label="Email"\n'
'                input bind=edit_company label="Company"\n'
'                input bind=edit_phone label="Phone"\n'
'                button "Save Changes" variant="default"\n'
'\n'
'component CompaniesTable\n'
'    state items           = []\n'
'    state edit_item       = null\n'
'    state edit_name       = ""\n'
'    state edit_industry   = ""\n'
'    state edit_size       = ""\n'
'    state show_edit_modal = false\n'
'    state new_name        = ""\n'
'    state new_industry    = ""\n'
'    state new_size        = ""\n'
'\n'
'    on load\n'
'        var resp = list_companies()\n'
'        items = resp.data\n'
'\n'
'    on submit\n'
'        var result = create_company(new_name, new_industry, new_size)\n'
'        if result.success\n'
'            var resp = list_companies()\n'
'            items = resp.data\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Company"\n'
'                form on_submit=submit\n'
'                    div grid_cols=3\n'
'                        input bind=new_name label="Company Name"\n'
'                        input bind=new_industry label="Industry"\n'
'                        select bind=new_size options=["1-10","11-50","51-200","201-500","500+"] label="Size"\n'
'                    button "Add Company" variant="default"\n'
'            card\n'
'                card_header "All Companies"\n'
'                table\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "name"\n'
'                            table_head "industry"\n'
'                            table_head "size"\n'
'                    table_body\n'
'        modal show=show_edit_modal\n'
'            card_header "Edit Company"\n'
'            form on_submit=handleSave\n'
'                input bind=edit_name label="Name"\n'
'                input bind=edit_industry label="Industry"\n'
'                input bind=edit_size label="Size"\n'
'                button "Save Changes" variant="default"\n'
'\n'
'component ActivitiesTable\n'
'    state items           = []\n'
'    state edit_item       = null\n'
'    state edit_title      = ""\n'
'    state edit_type       = ""\n'
'    state edit_contact    = ""\n'
'    state edit_due_date   = ""\n'
'    state show_edit_modal = false\n'
'    state new_title       = ""\n'
'    state new_type        = "Call"\n'
'    state new_contact     = ""\n'
'    state new_due_date    = ""\n'
'\n'
'    on load\n'
'        var resp = list_activities()\n'
'        items = resp.data\n'
'\n'
'    on submit\n'
'        var result = create_activity(new_title, new_type, new_contact, new_due_date)\n'
'        if result.success\n'
'            var resp = list_activities()\n'
'            items = resp.data\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Log Activity"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=new_title label="Activity Title"\n'
'                        select bind=new_type options=["Call","Email","Meeting","Task","Note"] label="Type"\n'
'                    div grid_cols=2\n'
'                        input bind=new_contact label="Contact Name"\n'
'                        input bind=new_due_date label="Due Date" type="date"\n'
'                    button "Log Activity" variant="default"\n'
'            card\n'
'                card_header "All Activities"\n'
'                table\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "title"\n'
'                            table_head "type"\n'
'                            table_head "contact"\n'
'                            table_head "due_date"\n'
'                    table_body\n'
'        modal show=show_edit_modal\n'
'            card_header "Edit Activity"\n'
'            form on_submit=handleSave\n'
'                input bind=edit_title label="Title"\n'
'                input bind=edit_type label="Type"\n'
'                input bind=edit_contact label="Contact"\n'
'                input bind=edit_due_date label="Due Date"\n'
'                button "Save Changes" variant="default"\n'
'\n'
'app CRM\n'
'    title  "CRM"\n'
'    theme  "professional"\n'
'    layout\n'
'        sidebar\n'
'            nav "Dashboard"  Dashboard\n'
'            nav "Deals"      DealsTable\n'
'            nav "Contacts"   ContactsTable\n'
'            nav "Companies"  CompaniesTable\n'
'            nav "Activities" ActivitiesTable\n'
)


@app.route("/api/examples")
def get_examples():
    return jsonify([
        # ── Single-file snippets (writes to one workspace file) ─────────────────
        {"id": "hello", "name": "Hello World", "file": "backend/main.mcn", "code": (
'// Hello World — click ▶ Run\n'
'var name = "MCN"\n'
'log("Hello from {name}!")\n'
'\n'
'var nums = [1, 2, 3, 4, 5]\n'
'var total = 0\n'
'for n in nums\n'
'    total = total + n\n'
'    log("  item: {n}")\n'
'\n'
'log("Sum: {total}")\n'
'\n'
'// Conditionals\n'
'if total > 10\n'
'    log("Total is large")\n'
'else\n'
'    log("Total is small")\n'
)},
        {"id": "functions", "name": "Functions & Logic", "file": "backend/main.mcn", "code": (
'// Functions — click ▶ Run\n'
'function greet(name, greeting = "Hello")\n'
'    return "{greeting}, {name}!"\n'
'\n'
'function factorial(n)\n'
'    if n <= 1\n'
'        return 1\n'
'    return n * factorial(n - 1)\n'
'\n'
'function clamp(val, lo, hi)\n'
'    if val < lo\n'
'        return lo\n'
'    if val > hi\n'
'        return hi\n'
'    return val\n'
'\n'
'log(greet("MCN"))\n'
'log(greet("World", "Hi"))\n'
'log("5! = {factorial(5)}")\n'
'log("clamp(15, 0, 10) = {clamp(15, 0, 10)}")\n'
'\n'
'// List processing\n'
'var scores = [88, 72, 95, 61, 80]\n'
'var passing = []\n'
'for s in scores\n'
'    if s >= 70\n'
'        passing = passing + [s]\n'
'log("Passing scores: {passing}")\n'
)},
        {"id": "pipeline", "name": "Pipeline", "file": "backend/main.mcn", "code": (
'// Data Pipeline — click ▶ Run\n'
'pipeline etl\n'
'    stage extract\n'
'        var records = [\n'
'            {name: "Alice", score: 88, dept: "Eng"},\n'
'            {name: "Bob",   score: 72, dept: "Sales"},\n'
'            {name: "Carol", score: 95, dept: "Eng"}\n'
'        ]\n'
'        log("Extracted {records.length} records")\n'
'        return records\n'
'\n'
'    stage transform(data)\n'
'        var total = 0\n'
'        for r in data\n'
'            total = total + r.score\n'
'        var avg = total / data.length\n'
'        log("Average score: {avg}")\n'
'        return {records: data, average: avg, count: data.length}\n'
'\n'
'    stage load(report)\n'
'        log("Pipeline complete!")\n'
'        log("  Records:  {report.count}")\n'
'        log("  Average:  {report.average}")\n'
'\n'
'// Run the pipeline — each stage output feeds the next\n'
'etl.run()\n'
)},
        {"id": "tests", "name": "Testing", "file": "backend/main.mcn", "code": (
'// Tests — click ⚗ Test button (not ▶ Run)\n'
'function add(a, b)\n'
'    return a + b\n'
'\n'
'function clamp(val, lo, hi)\n'
'    if val < lo\n'
'        return lo\n'
'    if val > hi\n'
'        return hi\n'
'    return val\n'
'\n'
'function is_even(n)\n'
'    return n % 2 == 0\n'
'\n'
'test "basic addition"\n'
'    assert add(2, 3) == 5\n'
'    assert add(-1, 1) == 0\n'
'    assert add(0, 0) == 0\n'
'\n'
'test "clamping"\n'
'    assert clamp(5, 0, 10) == 5\n'
'    assert clamp(-5, 0, 10) == 0\n'
'    assert clamp(15, 0, 10) == 10\n'
'\n'
'test "even/odd"\n'
'    assert is_even(4) == true\n'
'    assert is_even(7) == false\n'
)},
        # ── Full-stack project templates (writes backend + UI together) ──────────
        {"id": "item_manager", "name": "📦 Item Manager", "project": True,
         "open": "ui/app.mcn",
         "files": [
             {"path": "backend/main.mcn", "content": _DEFAULT_BACKEND},
             {"path": "ui/app.mcn",       "content": _DEFAULT_UI},
         ]},
        {"id": "crm", "name": "🏢 CRM App", "project": True,
         "open": "ui/app.mcn",
         "files": [
             {"path": "backend/main.mcn", "content": _CRM_BACKEND},
             {"path": "ui/app.mcn",       "content": _CRM_UI},
         ]},
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _seed_workspace()
    port = int(os.environ.get("MCN_PLAYGROUND_PORT", 5003))
    print(f"MCN Web Playground v2.2 — http://localhost:{port}")
    print(f"Workspace: {WORKSPACE}")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
