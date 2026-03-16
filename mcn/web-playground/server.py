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

# Seed empty project files on first run
for _seed in ("backend/main.mcn", "ui/app.mcn"):
    _p = WORKSPACE / _seed
    if not _p.exists():
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(f"// {_seed}\n", encoding="utf-8")

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

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=".")
CORS(app)

_MAX_CODE_BYTES = 128 * 1024   # 128 KB
_EXEC_TIMEOUT_S = 10

# Dev server process (module-level singleton)
_dev_server: subprocess.Popen | None = None
_DEV_PORT = 5174


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
    return jsonify({"status": "ok", "version": "2.2"})


# ── Workspace endpoints ───────────────────────────────────────────────────────

@app.route("/api/workspace/files")
def workspace_files():
    """Return file tree of the workspace (mcn + generated frontend files)."""
    files = []
    for p in sorted(WORKSPACE.rglob("*")):
        if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
            rel = str(p.relative_to(WORKSPACE))
            files.append({"path": rel, "type": "file"})
    return jsonify({"files": files})


@app.route("/api/workspace/file")
def get_workspace_file():
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


@app.route("/api/workspace/file", methods=["POST"])
def save_workspace_file():
    data = request.get_json(silent=True) or {}
    rel  = data.get("path", "")
    content = data.get("content", "")
    if not rel:
        return jsonify({"error": "Missing 'path'"}), 400
    try:
        p = _safe_path(rel)
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
        return jsonify({"success": True, "code": formatted, "changed": formatted != data["code"]})
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
        return jsonify({
            "success": True,
            "issues": [{"severity": i.severity.value, "line": i.line,
                        "col": i.col, "message": i.message} for i in issues],
            "error_count":   sum(1 for i in issues if i.severity == Severity.ERROR),
            "warning_count": sum(1 for i in issues if i.severity == Severity.WARNING),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/test", methods=["POST"])
def test_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        runner  = TestRunner(verbose=False)
        results = runner.run_source(data["code"], label="<playground>")
        passed  = sum(1 for r in results if r.passed)
        return jsonify({
            "success": (len(results) - passed) == 0,
            "total": len(results), "passed": passed, "failed": len(results) - passed,
            "results": [{"description": r.description, "passed": r.passed,
                         "error": r.error if not r.passed else None,
                         "elapsed_ms": round(r.elapsed * 1000, 2)} for r in results],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── AI Generate (SSE) ─────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate_mcn():
    data        = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    api_key     = data.get("api_key", "").strip() or _load_config().get("api_key") or os.getenv("ANTHROPIC_API_KEY")

    if not description:
        return jsonify({"error": "Missing 'description'"}), 400
    if not api_key:
        return jsonify({"error": "No Claude API key. Set it via mcn config set api_key ..."}), 400

    token_queue: queue.Queue = queue.Queue()
    result_box  = [None]   # {"backend": ..., "ui": ..., "attempts": N} or {"error": ...}

    def _agent_thread():
        try:
            from mcn.ai.mcn_agent import MCNAgent, _extract_blocks, _validate_mcn
            from mcn.ai.mcn_spec  import MCN_SYSTEM_PROMPT, MCN_FIX_PROMPT

            client_kw = dict(api_key=api_key, model="claude-opus-4-6")
            agent = MCNAgent(**client_kw)

            # Override _call_claude to pipe tokens into the queue
            def _streaming_call(prompt, system, verbose):
                chunks = []
                with agent.client.messages.stream(
                    model=agent.model,
                    max_tokens=8192,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                        token_queue.put({"type": "token", "text": text})
                return "".join(chunks)

            agent._call_claude = _streaming_call

            token_queue.put({"type": "status", "text": "Generating MCN…"})
            result = agent.generate(
                description=description,
                output_dir=str(WORKSPACE),
                verbose=False,
            )

            token_queue.put({"type": "status", "text": f"Validated in {result['attempts']} attempt(s)"})
            result_box[0] = {
                "backend":  result["backend_mcn"],
                "ui":       result["ui_mcn"],
                "attempts": result["attempts"],
            }
        except Exception as e:
            result_box[0] = {"error": str(e)}
        finally:
            token_queue.put(None)   # sentinel

    threading.Thread(target=_agent_thread, daemon=True).start()

    def _stream():
        while True:
            try:
                item = token_queue.get(timeout=120)
            except queue.Empty:
                yield _sse({"type": "error", "message": "Generation timed out"})
                return

            if item is None:
                # Generation done
                r = result_box[0] or {}
                if "error" in r:
                    yield _sse({"type": "error", "message": r["error"]})
                else:
                    yield _sse({"type": "done", **r})
                return

            yield _sse(item)

    resp = Response(stream_with_context(_stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"]    = "no-cache"
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

@app.route("/api/devserver/start", methods=["POST"])
def devserver_start():
    global _dev_server
    frontend = WORKSPACE / "frontend"

    if not (frontend / "package.json").exists():
        return jsonify({"success": False, "error": "frontend/package.json not found. Run Build first."}), 400

    if _dev_server and _dev_server.poll() is None:
        return jsonify({"success": True, "port": _DEV_PORT, "pid": _dev_server.pid, "already_running": True})

    # npm install if needed
    if not (frontend / "node_modules").exists():
        proc = subprocess.run(["npm", "install"], cwd=str(frontend),
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return jsonify({"success": False, "error": f"npm install failed:\n{proc.stderr}"}), 500

    try:
        _dev_server = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(_DEV_PORT), "--host"],
            cwd=str(frontend),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give Vite a moment to start
        import time; time.sleep(2)
        return jsonify({"success": True, "port": _DEV_PORT, "pid": _dev_server.pid})
    except FileNotFoundError:
        return jsonify({"success": False, "error": "npm not found. Install Node.js to use the live preview."}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/devserver/stop", methods=["POST"])
def devserver_stop():
    global _dev_server
    if _dev_server:
        try:
            _dev_server.terminate()
            _dev_server.wait(timeout=5)
        except Exception:
            _dev_server.kill()
        _dev_server = None
    return jsonify({"success": True})


@app.route("/api/devserver/status")
def devserver_status():
    global _dev_server
    running = _dev_server is not None and _dev_server.poll() is None
    return jsonify({
        "running": running,
        "port":    _DEV_PORT if running else None,
        "pid":     _dev_server.pid if running else None,
    })


# ── Examples ──────────────────────────────────────────────────────────────────

@app.route("/api/examples")
def get_examples():
    return jsonify([
        {"id": "hello",    "name": "Hello World",         "file": "backend/main.mcn",
         "code": 'var name = "MCN"\nlog("Hello from {name}!")\n\nvar nums = [1, 2, 3]\nfor n in nums\n    log("  {n}")\n'},
        {"id": "ai",       "name": "AI Primitives",        "file": "backend/main.mcn",
         "code": '// Classify user intent\nvar message = "I want to return my order"\nvar intent  = classify(message, ["buy", "return", "support"])\nlog("Intent: {intent}")\n\n// Generate a response\nvar reply = ai("Write a one-sentence response for a \'{intent}\' request")\nlog("Reply: {reply}")\n'},
        {"id": "contract", "name": "Contracts & Extraction","file": "backend/main.mcn",
         "code": 'contract Order\n    id:     int\n    item:   str\n    amount: float\n\nvar raw   = "Order #42: Laptop, $1299.99"\nvar order = extract(raw, Order)\nlog("Order ID: {order.id}")\nlog("Item:     {order.item}")\nlog("Amount:   {order.amount}")\n'},
        {"id": "pipeline", "name": "Pipeline",             "file": "backend/main.mcn",
         "code": 'pipeline etl\n    stage extract\n        var records = [{name: "Alice", score: 88}, {name: "Bob", score: 72}]\n        return records\n\n    stage transform(data)\n        var summary = ai("Summarize these scores: {data}")\n        return summary\n\n    stage load(report)\n        log("Report ready: {report}")\n'},
        {"id": "tests",    "name": "Testing",              "file": "backend/main.mcn",
         "code": 'function add(a, b)\n    return a + b\n\nfunction clamp(val, lo, hi)\n    if val < lo\n        return lo\n    if val > hi\n        return hi\n    return val\n\ntest "basic addition"\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n\ntest "clamping"\n    assert clamp(5, 0, 10) == 5\n    assert clamp(-5, 0, 10) == 0\n    assert clamp(15, 0, 10) == 10\n'},
        {"id": "crud_backend", "name": "CRUD Backend",     "file": "backend/main.mcn",
         "code": 'contract Item\n    name: str\n    price: float\n\nquery("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, created_at TEXT DEFAULT (datetime(\'now\')))")\n\nservice items_api\n    port 8080\n\n    endpoint create_item(name, price)\n        query("INSERT INTO items (name, price) VALUES (?, ?)", (name, price))\n        var id = query("SELECT last_insert_rowid() as id")[0].id\n        return {success: true, id: id}\n\n    endpoint list_items(limit = 50, offset = 0)\n        var items = query("SELECT * FROM items ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))\n        var insight = ai("Give a one-sentence business insight on these records: {items}")\n        return {success: true, data: items, total: items, insight: insight}\n\n    endpoint delete_item(id)\n        query("DELETE FROM items WHERE id = ?", (id,))\n        return {success: true}\n'},
        {"id": "crud_ui",  "name": "CRUD UI (app.mcn)",    "file": "ui/app.mcn",
         "code": 'component ItemForm\n    state name    = ""\n    state price   = 0\n    state message = ""\n    state loading = false\n\n    on submit\n        loading = true\n        var result = create_item(name, price)\n        if result.success\n            message = "Created! ID: " + result.id\n        loading = false\n\n    render\n        card\n            card_header "Add Item"\n            form on_submit=submit\n                input bind=name label="Name"\n                input bind=price label="Price" type="number"\n                button "Add Item" variant="default" disabled=loading\n                div\n                    text message\n\ncomponent ItemTable\n    state items           = []\n    state insight         = ""\n    state edit_name       = ""\n    state edit_price      = 0\n    state edit_item       = null\n    state show_edit_modal = false\n\n    on load\n        var response = list_items()\n        items   = response.data\n        insight = response.insight\n\n    render\n        card\n            card_header "All Items"\n            div\n                text insight\n            table\n                table_header\n                    table_row\n                        table_head "id"\n                        table_head "name"\n                        table_head "price"\n                        table_head "created_at"\n                table_body\n        modal show=show_edit_modal\n            card_header "Edit Item"\n            form on_submit=handleSave\n                input bind=edit_name label="Name"\n                input bind=edit_price label="Price" type="number"\n                button "Save Changes" variant="default"\n\napp ItemManager\n    title  "Item Manager"\n    theme  "professional"\n    layout\n        tabs\n            tab "Add Item"   ItemForm\n            tab "All Items"  ItemTable\n'},
        {"id": "crm_backend", "name": "CRM Backend",      "file": "backend/main.mcn",
         "code": 'contract Deal\n    title: str\n    value: float\n    stage: str\n    contact: str\n\ncontract Contact\n    name: str\n    email: str\n    company: str\n    phone: str\n\ncontract Company\n    name: str\n    industry: str\n    size: str\n\ncontract Activity\n    title: str\n    type: str\n    contact: str\n    due_date: str\n\nquery("CREATE TABLE IF NOT EXISTS deals (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, value REAL, stage TEXT, contact TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\nquery("CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, company TEXT, phone TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\nquery("CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, industry TEXT, size TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\nquery("CREATE TABLE IF NOT EXISTS activities (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, type TEXT, contact TEXT, due_date TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n\nservice crm_api\n    port 8080\n\n    endpoint create_deal(title, value, stage, contact)\n        query("INSERT INTO deals (title, value, stage, contact) VALUES (?, ?, ?, ?)", (title, value, stage, contact))\n        var id = query("SELECT last_insert_rowid() as id")[0].id\n        return {success: true, id: id}\n\n    endpoint list_deals(limit = 50, offset = 0)\n        var items = query("SELECT * FROM deals ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))\n        return {success: true, data: items}\n\n    endpoint update_deal(id, title, value, stage, contact)\n        query("UPDATE deals SET title=?, value=?, stage=?, contact=? WHERE id=?", (title, value, stage, contact, id))\n        return {success: true}\n\n    endpoint delete_deal(id)\n        query("DELETE FROM deals WHERE id=?", (id,))\n        return {success: true}\n\n    endpoint create_contact(name, email, company, phone)\n        query("INSERT INTO contacts (name, email, company, phone) VALUES (?, ?, ?, ?)", (name, email, company, phone))\n        var id = query("SELECT last_insert_rowid() as id")[0].id\n        return {success: true, id: id}\n\n    endpoint list_contacts(limit = 50, offset = 0)\n        var items = query("SELECT * FROM contacts ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))\n        return {success: true, data: items}\n\n    endpoint update_contact(id, name, email, company, phone)\n        query("UPDATE contacts SET name=?, email=?, company=?, phone=? WHERE id=?", (name, email, company, phone, id))\n        return {success: true}\n\n    endpoint delete_contact(id)\n        query("DELETE FROM contacts WHERE id=?", (id,))\n        return {success: true}\n\n    endpoint create_company(name, industry, size)\n        query("INSERT INTO companies (name, industry, size) VALUES (?, ?, ?)", (name, industry, size))\n        var id = query("SELECT last_insert_rowid() as id")[0].id\n        return {success: true, id: id}\n\n    endpoint list_companies(limit = 50, offset = 0)\n        var items = query("SELECT * FROM companies ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))\n        return {success: true, data: items}\n\n    endpoint update_company(id, name, industry, size)\n        query("UPDATE companies SET name=?, industry=?, size=? WHERE id=?", (name, industry, size, id))\n        return {success: true}\n\n    endpoint delete_company(id)\n        query("DELETE FROM companies WHERE id=?", (id,))\n        return {success: true}\n\n    endpoint create_activity(title, type, contact, due_date)\n        query("INSERT INTO activities (title, type, contact, due_date) VALUES (?, ?, ?, ?)", (title, type, contact, due_date))\n        var id = query("SELECT last_insert_rowid() as id")[0].id\n        return {success: true, id: id}\n\n    endpoint list_activities(limit = 50, offset = 0)\n        var items = query("SELECT * FROM activities ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))\n        return {success: true, data: items}\n\n    endpoint update_activity(id, title, type, contact, due_date)\n        query("UPDATE activities SET title=?, type=?, contact=?, due_date=? WHERE id=?", (title, type, contact, due_date, id))\n        return {success: true}\n\n    endpoint delete_activity(id)\n        query("DELETE FROM activities WHERE id=?", (id,))\n        return {success: true}\n'},
        {"id": "crm_ui",      "name": "CRM UI (app.mcn)", "file": "ui/app.mcn",
         "code": 'component DealsTable\n    state items           = []\n    state edit_item       = null\n    state edit_title      = ""\n    state edit_value      = 0\n    state edit_stage      = ""\n    state edit_contact    = ""\n    state show_edit_modal = false\n    state new_title       = ""\n    state new_value       = 0\n    state new_stage       = "Prospecting"\n    state new_contact     = ""\n\n    on load\n        var resp = list_deals()\n        items = resp.data\n\n    on submit\n        var result = create_deal(new_title, new_value, new_stage, new_contact)\n        if result.success\n            var resp = list_deals()\n            items = resp.data\n\n    render\n        div\n            card\n                card_header "Add Deal"\n                form on_submit=submit\n                    div grid_cols=2\n                        input bind=new_title label="Deal Title"\n                        input bind=new_value label="Value ($)" type="number"\n                    div grid_cols=2\n                        select bind=new_stage options=["Prospecting", "Qualification", "Proposal", "Negotiation", "Won", "Lost"] label="Stage"\n                        input bind=new_contact label="Contact Name"\n                    button "Add Deal" variant="default"\n            card\n                card_header "All Deals"\n                table\n                    table_header\n                        table_row\n                            table_head "title"\n                            table_head "value"\n                            table_head "stage"\n                            table_head "contact"\n                    table_body\n        modal show=show_edit_modal\n            card_header "Edit Deal"\n            form on_submit=handleSave\n                input bind=edit_title label="Title"\n                input bind=edit_value label="Value" type="number"\n                select bind=edit_stage options=["Prospecting", "Qualification", "Proposal", "Negotiation", "Won", "Lost"] label="Stage"\n                input bind=edit_contact label="Contact"\n                button "Save Changes" variant="default"\n\ncomponent ContactsTable\n    state items           = []\n    state edit_item       = null\n    state edit_name       = ""\n    state edit_email      = ""\n    state edit_company    = ""\n    state edit_phone      = ""\n    state show_edit_modal = false\n    state new_name        = ""\n    state new_email       = ""\n    state new_company     = ""\n    state new_phone       = ""\n\n    on load\n        var resp = list_contacts()\n        items = resp.data\n\n    on submit\n        var result = create_contact(new_name, new_email, new_company, new_phone)\n        if result.success\n            var resp = list_contacts()\n            items = resp.data\n\n    render\n        div\n            card\n                card_header "Add Contact"\n                form on_submit=submit\n                    div grid_cols=2\n                        input bind=new_name label="Full Name"\n                        input bind=new_email label="Email" type="email"\n                    div grid_cols=2\n                        input bind=new_company label="Company"\n                        input bind=new_phone label="Phone"\n                    button "Add Contact" variant="default"\n            card\n                card_header "All Contacts"\n                table\n                    table_header\n                        table_row\n                            table_head "name"\n                            table_head "email"\n                            table_head "company"\n                            table_head "phone"\n                    table_body\n        modal show=show_edit_modal\n            card_header "Edit Contact"\n            form on_submit=handleSave\n                input bind=edit_name label="Name"\n                input bind=edit_email label="Email"\n                input bind=edit_company label="Company"\n                input bind=edit_phone label="Phone"\n                button "Save Changes" variant="default"\n\ncomponent CompaniesTable\n    state items           = []\n    state edit_item       = null\n    state edit_name       = ""\n    state edit_industry   = ""\n    state edit_size       = ""\n    state show_edit_modal = false\n    state new_name        = ""\n    state new_industry    = ""\n    state new_size        = ""\n\n    on load\n        var resp = list_companies()\n        items = resp.data\n\n    on submit\n        var result = create_company(new_name, new_industry, new_size)\n        if result.success\n            var resp = list_companies()\n            items = resp.data\n\n    render\n        div\n            card\n                card_header "Add Company"\n                form on_submit=submit\n                    div grid_cols=3\n                        input bind=new_name label="Company Name"\n                        input bind=new_industry label="Industry"\n                        select bind=new_size options=["1-10", "11-50", "51-200", "201-500", "500+"] label="Size"\n                    button "Add Company" variant="default"\n            card\n                card_header "All Companies"\n                table\n                    table_header\n                        table_row\n                            table_head "name"\n                            table_head "industry"\n                            table_head "size"\n                    table_body\n        modal show=show_edit_modal\n            card_header "Edit Company"\n            form on_submit=handleSave\n                input bind=edit_name label="Name"\n                input bind=edit_industry label="Industry"\n                input bind=edit_size label="Size"\n                button "Save Changes" variant="default"\n\ncomponent ActivitiesTable\n    state items           = []\n    state edit_item       = null\n    state edit_title      = ""\n    state edit_type       = ""\n    state edit_contact    = ""\n    state edit_due_date   = ""\n    state show_edit_modal = false\n    state new_title       = ""\n    state new_type        = "Call"\n    state new_contact     = ""\n    state new_due_date    = ""\n\n    on load\n        var resp = list_activities()\n        items = resp.data\n\n    on submit\n        var result = create_activity(new_title, new_type, new_contact, new_due_date)\n        if result.success\n            var resp = list_activities()\n            items = resp.data\n\n    render\n        div\n            card\n                card_header "Log Activity"\n                form on_submit=submit\n                    div grid_cols=2\n                        input bind=new_title label="Activity Title"\n                        select bind=new_type options=["Call", "Email", "Meeting", "Task", "Note"] label="Type"\n                    div grid_cols=2\n                        input bind=new_contact label="Contact Name"\n                        input bind=new_due_date label="Due Date" type="date"\n                    button "Log Activity" variant="default"\n            card\n                card_header "All Activities"\n                table\n                    table_header\n                        table_row\n                            table_head "title"\n                            table_head "type"\n                            table_head "contact"\n                            table_head "due_date"\n                    table_body\n        modal show=show_edit_modal\n            card_header "Edit Activity"\n            form on_submit=handleSave\n                input bind=edit_title label="Title"\n                input bind=edit_type label="Type"\n                input bind=edit_contact label="Contact"\n                input bind=edit_due_date label="Due Date"\n                button "Save Changes" variant="default"\n\napp CRM\n    title  "CRM Dashboard"\n    theme  "professional"\n    layout\n        sidebar\n            nav "Deals"      DealsTable\n            nav "Contacts"   ContactsTable\n            nav "Companies"  CompaniesTable\n            nav "Activities" ActivitiesTable\n'},
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("MCN_PLAYGROUND_PORT", 5003))
    print(f"MCN Web Playground v2.2 — http://localhost:{port}")
    print(f"Workspace: {WORKSPACE}")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
