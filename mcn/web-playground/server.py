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

# MCN Simulator States
_SIMULATED_DEVICES = {
    "office_temp": {"type": "temperature_sensor", "value": 22.5, "unit": "°C"},
    "office_occupancy": {"type": "motion_sensor", "value": 0, "unit": "active"},
    "hvac_system": {"type": "hvac_controller", "value": "idle", "unit": "status"}
}
_DEVICE_COMMANDS = []
_AI_TRACE_LOGS = []

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


# ── Secrets endpoints ─────────────────────────────────────────────────────────

_SECRETS_FILE = _WORKSPACES_DIR / ".mcn_secrets.json"

def _load_secrets() -> dict:
    if _SECRETS_FILE.exists():
        try: return json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def _save_secrets(data: dict):
    _SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

# Inject secrets into the process environment so MCN `env_get` can read them
_secrets = _load_secrets()
for k, v in _secrets.items():
    os.environ[k] = str(v)

@app.route("/api/secrets", methods=["GET"])
def get_secrets():
    secrets = _load_secrets()
    # Mask values for security
    masked = {k: ("*" * len(str(v)) if len(str(v)) <= 4 else str(v)[:2] + "*" * 6 + str(v)[-2:]) for k, v in secrets.items()}
    return jsonify({"success": True, "secrets": masked})

@app.route("/api/secrets", methods=["POST"])
def set_secret():
    data = request.get_json(silent=True) or {}
    key = data.get("key", "").strip()
    value = data.get("value", "")
    if not key:
        return jsonify({"error": "Key is required"}), 400
    secrets = _load_secrets()
    secrets[key] = value
    _save_secrets(secrets)
    os.environ[key] = str(value)  # Inject into current process
    return jsonify({"success": True})

@app.route("/api/secrets/<key>", methods=["DELETE"])
def delete_secret(key):
    secrets = _load_secrets()
    if key in secrets:
        del secrets[key]
        _save_secrets(secrets)
        os.environ.pop(key, None)
    return jsonify({"success": True})


# ── Version Control endpoints ─────────────────────────────────────────────────

@app.route("/api/git/status", methods=["GET"])
def git_status():
    import subprocess
    try:
        # Assuming we init git if it doesn't exist
        if not (_WORKSPACES_DIR / ".git").exists():
            subprocess.check_call(["git", "init"], cwd=_WORKSPACES_DIR)
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=_WORKSPACES_DIR, text=True)
        return jsonify({"success": True, "status": out.splitlines()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/git/commit", methods=["POST"])
def git_commit():
    import subprocess
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "Auto-commit from MCN")
    try:
        if not (_WORKSPACES_DIR / ".git").exists():
            subprocess.check_call(["git", "init"], cwd=_WORKSPACES_DIR)
        subprocess.check_call(["git", "add", "."], cwd=_WORKSPACES_DIR)
        # ignore errors if nothing to commit
        subprocess.call(["git", "commit", "-m", msg], cwd=_WORKSPACES_DIR)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/git/push", methods=["POST"])
def git_push():
    import subprocess
    try:
        subprocess.check_call(["git", "push"], cwd=_WORKSPACES_DIR)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Workspace endpoints ───────────────────────────────────────────────────────

_DEFAULT_BACKEND = '''\
// MCN Backend — write your services and endpoints here
service api
    port 8080
    endpoint hello()
        return {message: "Hello World"}
'''

_DEFAULT_UI = '''\
// MCN UI — write your components and apps here
component Home
    render
        div
            h1 "Welcome to MCN"
            p "Start editing backend/main.mcn and ui/app.mcn to build your app."

app MainApp
    title "MCN Application"
    layout
        main
            Home
'''

_ITEM_MANAGER_BACKEND = '''\
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

_ITEM_MANAGER_UI = '''\
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

        # 1. Pre-populate IoT devices with simulated states from playground
        interp._ensure_v3_systems()
        for dev_id, dev in _SIMULATED_DEVICES.items():
            interp.iot_connector.devices[dev_id] = {
                "type": dev["type"],
                "connection": {},
                "override_value": dev["value"],
                "status": "registered"
            }

        # 2. Intercept IoT command requests to capture logs
        _orig_cmd = interp.iot_connector.send_command
        def _intercept_cmd(device_id, command, params=None):
            res = _orig_cmd(device_id, command, params)
            _DEVICE_COMMANDS.append({
                "device_id": device_id,
                "command": command,
                "params": params,
                "timestamp": time.time()
            })
            if device_id in _SIMULATED_DEVICES:
                _SIMULATED_DEVICES[device_id]["value"] = f"{command} ({json.dumps(params or {})})"
            return res
        interp.iot_connector.send_command = _intercept_cmd

        # 3. Intercept AI model execution to trace prompts
        _orig_ai = interp.runtime.ai
        def _intercept_ai(prompt, *args, **kwargs):
            res = _orig_ai(prompt, *args, **kwargs)
            _AI_TRACE_LOGS.append({
                "type": "AI Request",
                "prompt": prompt,
                "response": res,
                "timestamp": time.time()
            })
            return res
        interp.runtime.ai = _intercept_ai

        # 4. Intercept RAG queries
        _orig_rag = interp.datasource_system.query_rag
        def _intercept_rag(name, query):
            res = _orig_rag(name, query)
            _AI_TRACE_LOGS.append({
                "type": "RAG Query",
                "prompt": f"DataSource '{name}' query: {query}",
                "response": res,
                "timestamp": time.time()
            })
            return res
        interp.datasource_system.query_rag = _intercept_rag

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


# ── DB, IoT, and AI Trace Simulator Endpoints ─────────────────────────────────

def get_sqlite_schema():
    import sqlite3
    db_path = WORKSPACE / "mcn_data.db"
    if not db_path.exists():
        db_path = Path("mcn_data.db")
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall() if r[0] != "sqlite_sequence"]
        schema = []
        for tbl in tables:
            cursor.execute(f"PRAGMA table_info({tbl})")
            cols = [f"{c[1]} ({c[2]})" for c in cursor.fetchall()]
            schema.append({"table": tbl, "columns": cols})
        conn.close()
        return schema
    except Exception as e:
        return [{"error": str(e)}]

def run_sqlite_query(sql: str):
    import sqlite3
    db_path = WORKSPACE / "mcn_data.db"
    if not db_path.exists():
        db_path = Path("mcn_data.db")
    if not db_path.exists():
        raise Exception("Database file does not exist yet. Run some database operations first.")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(sql)
    if sql.strip().upper().startswith("SELECT"):
        cols = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(cols, row)) for row in rows]
    else:
        conn.commit()
        result = [{"affected_rows": cursor.rowcount}]
    conn.close()
    return result


@app.route("/api/db/schema", methods=["GET"])
def get_db_schema():
    try:
        schema = get_sqlite_schema()
        return jsonify({"success": True, "schema": schema})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/db/query", methods=["POST"])
def exec_db_query():
    try:
        data = request.get_json(silent=True) or {}
        sql = data.get("sql", "")
        if not sql:
            return jsonify({"success": False, "error": "No SQL query provided"})
        result = run_sqlite_query(sql)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/iot/devices", methods=["GET"])
def get_iot_devices():
    return jsonify({"success": True, "devices": _SIMULATED_DEVICES})

@app.route("/api/iot/device/value", methods=["POST"])
def set_iot_device_value():
    try:
        data = request.get_json(silent=True) or {}
        device_id = data.get("device_id")
        val = data.get("value")
        if not device_id or device_id not in _SIMULATED_DEVICES:
            return jsonify({"success": False, "error": "Invalid device ID"})
        
        dtype = _SIMULATED_DEVICES[device_id]["type"]
        if dtype == "temperature_sensor" or dtype == "humidity_sensor":
            _SIMULATED_DEVICES[device_id]["value"] = float(val)
        elif dtype == "motion_sensor":
            _SIMULATED_DEVICES[device_id]["value"] = int(val)
        else:
            _SIMULATED_DEVICES[device_id]["value"] = val
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/iot/commands", methods=["GET"])
def get_iot_commands():
    return jsonify({"success": True, "commands": _DEVICE_COMMANDS})

@app.route("/api/agent/enhance", methods=["POST"])
def agent_enhance_ui():
    data    = request.get_json(silent=True) or {}
    rel_path = data.get("path", "").strip()
    prompt   = data.get("prompt", "").strip()
    mode     = data.get("mode", "mcn").strip()
    
    api_key  = (data.get("api_key") or "").strip() \
               or _load_config().get("api_key") \
               or os.getenv("ANTHROPIC_API_KEY") \
               or os.getenv("OPENAI_API_KEY")
               
    if not rel_path or not prompt:
        return jsonify({"success": False, "error": "Missing 'path' or 'prompt'"}), 400
    if not api_key:
        return jsonify({"success": False, "error": "No API key found. Enter your Claude API key to proceed."}), 400
        
    ws = _request_workspace()
    try:
        try:
            from mcn.ai.mcn_coding_agent import MCNCodingAgent
        except ImportError:
            from ai.mcn_coding_agent import MCNCodingAgent  # type: ignore

        agent = MCNCodingAgent(api_key=api_key, model="claude-opus-4-6")

        if mode == "generate_backend":
            # Fresh generation — no existing file required
            enhanced_code = agent.generate_backend_code(prompt)
            p = _safe_path_for(rel_path or "backend/main.mcn", ws)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(enhanced_code, encoding="utf-8")
            return jsonify({
                "success": True,
                "content": enhanced_code,
                "path": rel_path or "backend/main.mcn",
                "message": f"Backend code generated and written to {p.name}."
            })

        # All other modes require the target file to exist
        p = _safe_path_for(rel_path, ws)
        if not p.exists():
            return jsonify({"success": False, "error": f"File does not exist: {rel_path}"}), 404

        file_content = p.read_text(encoding="utf-8")

        if mode == "backend":
            enhanced_code = agent.enhance_backend_code(file_content, prompt)
        elif mode == "mcn":
            enhanced_code = agent.enhance_mcn_code(file_content, prompt)
        else:
            enhanced_code = agent.enhance_compiled_code(file_content, str(p), prompt)

        # Write back the enhanced code
        p.write_text(enhanced_code, encoding="utf-8")

        return jsonify({
            "success": True,
            "content": enhanced_code,
            "message": f"Successfully enhanced {rel_path} using MCN Coding Agent."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


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

        # Automatically install shadcn components mentioned in stdout
        import re
        m = re.search(r"npx shadcn@latest add (.+)", stdout)
        if m:
            pkgs = m.group(1).strip().split()
            if pkgs:
                subprocess.run(
                    ["npx", "shadcn@latest", "add", "-y"] + pkgs,
                    cwd=str(out_path),
                    capture_output=True,
                    text=True
                )

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
                b_out = open(ws / "backend_stdout.log", "w", encoding="utf-8")
                b_err = open(ws / "backend_stderr.log", "w", encoding="utf-8")
                _mcn_backend = subprocess.Popen(
                    [sys.executable, "-m", "mcn.core_engine.mcn_cli", "serve",
                     "--file", str(backend_file), "--host", "0.0.0.0",
                     "--port", str(_BACKEND_PORT)],
                    cwd=str(_ROOT_DIR),
                    stdout=b_out,
                    stderr=b_err,
                )
                b_out.close()
                b_err.close()
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
    stdout_file = ws / "vite_stdout.log"
    stderr_file = ws / "vite_stderr.log"
    try:
        f_out = open(stdout_file, "w", encoding="utf-8")
        f_err = open(stderr_file, "w", encoding="utf-8")
        _dev_server = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(_DEV_PORT), "--host", "--strictPort"],
            cwd=str(frontend),
            stdout=f_out,
            stderr=f_err,
        )
        f_out.close()
        f_err.close()
        import time; time.sleep(2)
        if _dev_server.poll() is not None:
            stderr = stderr_file.read_text(encoding="utf-8") if stderr_file.exists() else ""
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
'var count_deals = query("SELECT COUNT(*) as cnt FROM deals")[0].cnt\n'
'if count_deals == 0\n'
'    query("INSERT INTO companies (name, industry, size) VALUES (\'Acme Corp\', \'Tech\', \'11-50\')")\n'
'    query("INSERT INTO companies (name, industry, size) VALUES (\'Initech\', \'Software\', \'51-200\')")\n'
'    query("INSERT INTO contacts (name, email, company, phone) VALUES (\'Alice Smith\', \'alice@acme.com\', \'Acme Corp\', \'555-0199\')")\n'
'    query("INSERT INTO contacts (name, email, company, phone) VALUES (\'Bob Gibbons\', \'bob@initech.com\', \'Initech\', \'555-0288\')")\n'
'    query("INSERT INTO deals (title, value, stage, contact) VALUES (\'Acme Software Suite\', 25000, \'Proposal\', \'Alice Smith\')")\n'
'    query("INSERT INTO deals (title, value, stage, contact) VALUES (\'Initech Support Deal\', 8500, \'Negotiation\', \'Bob Gibbons\')")\n'
'    query("INSERT INTO activities (title, type, contact, due_date) VALUES (\'Follow up call\', \'Call\', \'Alice Smith\', \'2026-07-01\')")\n'
'    query("INSERT INTO activities (title, type, contact, due_date) VALUES (\'Send proposal\', \'Email\', \'Bob Gibbons\', \'2026-06-30\')")\n'
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
'            div grid_cols=2\n'
'                card\n'
'                    card_header "Deals Value Distribution"\n'
'                    bar_chart data=deals x_key="title" y_key="value" height=300\n'
'                card\n'
'                    card_header "Recent Deals"\n'
'                    table data=deals\n'
'                        table_header\n'
'                            table_row\n'
'                                table_head "title"\n'
'                                table_head "value"\n'
'                                table_head "stage"\n'
'                                table_head "contact"\n'
'                        table_body\n'
'            card\n'
'                card_header "Recent Activities"\n'
'                table data=activities\n'
'                    table_header\n'
'                        table_row\n'
'                            table_head "title"\n'
'                            table_head "type"\n'
'                            table_head "contact"\n'
'                            table_head "due_date"\n'
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
'    state title           = ""\n'
'    state value           = 0\n'
'    state stage           = "Prospecting"\n'
'    state contact         = ""\n'
'    state contact_names   = []\n'
'\n'
'    on load\n'
'        var resp = list_deals()\n'
'        items = resp.data\n'
'        var c_resp = list_contacts()\n'
'        var list = []\n'
'        for c in c_resp.data\n'
'            list = list + [c.name]\n'
'        contact_names = list\n'
'\n'
'    on submit\n'
'        var result = create_deal(title, value, stage, contact)\n'
'        if result.success\n'
'            var resp = list_deals()\n'
'            items = resp.data\n'
'            title = ""\n'
'            value = 0\n'
'            stage = "Prospecting"\n'
'            contact = ""\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Deal"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=title label="Deal Title"\n'
'                        input bind=value label="Value ($)" type="number"\n'
'                    div grid_cols=2\n'
'                        select bind=stage options=["Prospecting","Qualification","Proposal","Negotiation","Won","Lost"] label="Stage"\n'
'                        select bind=contact options=contact_names label="Contact Name"\n'
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
'                select bind=edit_contact options=contact_names label="Contact"\n'
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
'    state name            = ""\n'
'    state email           = ""\n'
'    state company         = ""\n'
'    state phone           = ""\n'
'    state company_names   = []\n'
'\n'
'    on load\n'
'        var resp = list_contacts()\n'
'        items = resp.data\n'
'        var co_resp = list_companies()\n'
'        var list = []\n'
'        for co in co_resp.data\n'
'            list = list + [co.name]\n'
'        company_names = list\n'
'\n'
'    on submit\n'
'        var result = create_contact(name, email, company, phone)\n'
'        if result.success\n'
'            var resp = list_contacts()\n'
'            items = resp.data\n'
'            name = ""\n'
'            email = ""\n'
'            company = ""\n'
'            phone = ""\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Contact"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=name label="Full Name"\n'
'                        input bind=email label="Email" type="email"\n'
'                    div grid_cols=2\n'
'                        select bind=company options=company_names label="Company"\n'
'                        input bind=phone label="Phone"\n'
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
'                select bind=edit_company options=company_names label="Company"\n'
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
'    state name            = ""\n'
'    state industry        = ""\n'
'    state size            = "11-50"\n'
'\n'
'    on load\n'
'        var resp = list_companies()\n'
'        items = resp.data\n'
'\n'
'    on submit\n'
'        var result = create_company(name, industry, size)\n'
'        if result.success\n'
'            var resp = list_companies()\n'
'            items = resp.data\n'
'            name = ""\n'
'            industry = ""\n'
'            size = "11-50"\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Add Company"\n'
'                form on_submit=submit\n'
'                    div grid_cols=3\n'
'                        input bind=name label="Company Name"\n'
'                        input bind=industry label="Industry"\n'
'                        select bind=size options=["1-10","11-50","51-200","201-500","500+"] label="Size"\n'
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
'                select bind=edit_size options=["1-10","11-50","51-200","201-500","500+"] label="Size"\n'
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
'    state title           = ""\n'
'    state type            = "Call"\n'
'    state contact         = ""\n'
'    state due_date        = ""\n'
'    state contact_names   = []\n'
'\n'
'    on load\n'
'        var resp = list_activities()\n'
'        items = resp.data\n'
'        var c_resp = list_contacts()\n'
'        var list = []\n'
'        for c in c_resp.data\n'
'            list = list + [c.name]\n'
'        contact_names = list\n'
'\n'
'    on submit\n'
'        var result = create_activity(title, type, contact, due_date)\n'
'        if result.success\n'
'            var resp = list_activities()\n'
'            items = resp.data\n'
'            title = ""\n'
'            type = "Call"\n'
'            contact = ""\n'
'            due_date = ""\n'
'\n'
'    render\n'
'        div\n'
'            card\n'
'                card_header "Log Activity"\n'
'                form on_submit=submit\n'
'                    div grid_cols=2\n'
'                        input bind=title label="Activity Title"\n'
'                        select bind=type options=["Call","Email","Meeting","Task","Note"] label="Type"\n'
'                    div grid_cols=2\n'
'                        select bind=contact options=contact_names label="Contact Name"\n'
'                        input bind=due_date label="Due Date" type="date"\n'
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
'                select bind=edit_type options=["Call","Email","Meeting","Task","Note"] label="Type"\n'
'                select bind=edit_contact options=contact_names label="Contact"\n'
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


_CONSTRUCTION_BACKEND = '''\
// Construction Management Backend Script
contract Property
    name: str
    location: str
    units: int
    status: str

contract Project
    name: str
    prop_id: int
    budget: float
    status: str
    start_date: str
    end_date: str

contract Job
    project_id: int
    title: str
    assigned_to: str
    status: str
    progress: int
    start_day: int
    duration: int

contract Resource
    name: str
    role: str
    rate: float
    availability: str

contract Material
    name: str
    unit: str
    stock: int
    reorder_level: int

contract Asset
    name: str
    type: str
    status: str
    location: str

contract Incident
    project_id: int
    title: str
    severity: str
    status: str
    reported_by: str

contract Document
    name: str
    type: str
    uploaded_at: str

contract Procurement
    material_id: int
    qty: int
    cost: float
    status: str
    requested_by: str

contract Approval
    type: str
    item_id: int
    status: str
    requested_by: str

// Tables initialization
query("CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, location TEXT, units INTEGER, status TEXT)")
query("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prop_id INTEGER, budget REAL, status TEXT, start_date TEXT, end_date TEXT)")
query("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, title TEXT, assigned_to TEXT, status TEXT, progress INTEGER, start_day INTEGER, duration INTEGER)")
query("CREATE TABLE IF NOT EXISTS resources (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, role TEXT, rate REAL, availability TEXT)")
query("CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, unit TEXT, stock INTEGER, reorder_level INTEGER)")
query("CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, status TEXT, location TEXT)")
query("CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, title TEXT, severity TEXT, status TEXT, reported_by TEXT, reported_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, uploaded_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS procurements (id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER, qty INTEGER, cost REAL, status TEXT, requested_by TEXT)")
query("CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, item_id INTEGER, status TEXT, requested_by TEXT)")

// Populate initial data if empty
var count_projects = query("SELECT COUNT(*) as cnt FROM projects")[0].cnt
if count_projects == 0
    query("INSERT INTO properties (name, location, units, status) VALUES ('Skyline Residency', 'Downtown Hub', 120, 'Under Construction')")
    query("INSERT INTO properties (name, location, units, status) VALUES ('Oakwood Villas', 'West Suburbs', 15, 'Planning')")
    query("INSERT INTO projects (name, prop_id, budget, status, start_date, end_date) VALUES ('Foundation & Structural Build', 1, 450000.0, 'Active', '2026-01-10', '2026-06-30')")
    query("INSERT INTO projects (name, prop_id, budget, status, start_date, end_date) VALUES ('Interior Fitouts & Finishing', 1, 150000.0, 'Planning', '2026-07-01', '2026-12-15')")
    query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (1, 'Excavation & Earthwork', 'Concrete Co', 'Completed', 100, 1, 5)")
    query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (1, 'Steel Reinforcement', 'Apex Builders', 'Active', 60, 6, 8)")
    query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (1, 'Concrete Pouring', 'Apex Builders', 'Active', 40, 10, 12)")
    query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (1, 'Masonry & Walling', 'Civic Contractors', 'Pending', 0, 20, 10)")
    query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (1, 'Roof Framing', 'Civic Contractors', 'Pending', 0, 28, 7)")
    query("INSERT INTO resources (name, role, rate, availability) VALUES ('John Mason', 'Site Supervisor', 65.0, 'Available')")
    query("INSERT INTO resources (name, role, rate, availability) VALUES ('Sarah Steel', 'Structural Engineer', 95.0, 'Available')")
    query("INSERT INTO materials (name, unit, stock, reorder_level) VALUES ('Cement', 'bags', 350, 100)")
    query("INSERT INTO materials (name, unit, stock, reorder_level) VALUES ('Steel Rebar', 'tons', 12, 5)")
    query("INSERT INTO assets (name, type, status, location) VALUES ('Caterpillar Excavator', 'Heavy Equipment', 'In Use', 'Skyline Site')")
    query("INSERT INTO assets (name, type, status, location) VALUES ('Tower Crane A', 'Crane', 'Maintenance', 'Skyline Site')")
    query("INSERT INTO incidents (project_id, title, severity, status, reported_by) VALUES (1, 'Minor concrete spill at Sector B', 'Low', 'Resolved', 'John Mason')")
    query("INSERT INTO documents (name, type) VALUES ('skyline_blueprint_v2.pdf', 'Blueprint')")
    query("INSERT INTO documents (name, type) VALUES ('permit_approval_final.pdf', 'Permit')")
    query("INSERT INTO procurements (material_id, qty, cost, status, requested_by) VALUES (1, 150, 1500.0, 'Approved', 'John Mason')")
    query("INSERT INTO approvals (type, item_id, status, requested_by) VALUES ('Procurement Request #1', 1, 'Approved', 'John Mason')")

service construction_api
    port 8080

    endpoint list_properties()
        var items = query("SELECT * FROM properties")
        return {success: true, data: items}

    endpoint create_property(name, location, units, status)
        query("INSERT INTO properties (name, location, units, status) VALUES (?, ?, ?, ?)", (name, location, units, status))
        return {success: true}

    endpoint delete_property(id)
        query("DELETE FROM properties WHERE id=?", (id,))
        return {success: true}

    endpoint list_projects()
        var items = query("SELECT * FROM projects")
        return {success: true, data: items}

    endpoint create_project(name, prop_id, budget, status, start_date, end_date)
        query("INSERT INTO projects (name, prop_id, budget, status, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)", (name, prop_id, budget, status, start_date, end_date))
        return {success: true}

    endpoint delete_project(id)
        query("DELETE FROM projects WHERE id=?", (id,))
        return {success: true}

    endpoint list_jobs()
        var items = query("SELECT * FROM jobs")
        return {success: true, data: items}

    endpoint create_job(project_id, title, assigned_to, status, progress, start_day, duration)
        query("INSERT INTO jobs (project_id, title, assigned_to, status, progress, start_day, duration) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, title, assigned_to, status, progress, start_day, duration))
        return {success: true}

    endpoint delete_job(id)
        query("DELETE FROM jobs WHERE id=?", (id,))
        return {success: true}

    endpoint update_job_progress(id, progress, status)
        query("UPDATE jobs SET progress=?, status=? WHERE id=?", (progress, status, id))
        return {success: true}

    endpoint list_resources()
        var items = query("SELECT * FROM resources")
        return {success: true, data: items}

    endpoint create_resource(name, role, rate, availability)
        query("INSERT INTO resources (name, role, rate, availability) VALUES (?, ?, ?, ?)", (name, role, rate, availability))
        return {success: true}

    endpoint delete_resource(id)
        query("DELETE FROM resources WHERE id=?", (id,))
        return {success: true}

    endpoint list_materials()
        var items = query("SELECT * FROM materials")
        return {success: true, data: items}

    endpoint create_material(name, unit, stock, reorder_level)
        query("INSERT INTO materials (name, unit, stock, reorder_level) VALUES (?, ?, ?, ?)", (name, unit, stock, reorder_level))
        return {success: true}

    endpoint delete_material(id)
        query("DELETE FROM materials WHERE id=?", (id,))
        return {success: true}

    endpoint list_assets()
        var items = query("SELECT * FROM assets")
        return {success: true, data: items}

    endpoint create_asset(name, type, status, location)
        query("INSERT INTO assets (name, type, status, location) VALUES (?, ?, ?, ?)", (name, type, status, location))
        return {success: true}

    endpoint delete_asset(id)
        query("DELETE FROM assets WHERE id=?", (id,))
        return {success: true}

    endpoint list_incidents()
        var items = query("SELECT * FROM incidents")
        return {success: true, data: items}

    endpoint create_incident(project_id, title, severity, status, reported_by)
        query("INSERT INTO incidents (project_id, title, severity, status, reported_by) VALUES (?, ?, ?, ?, ?)", (project_id, title, severity, status, reported_by))
        return {success: true}

    endpoint delete_incident(id)
        query("DELETE FROM incidents WHERE id=?", (id,))
        return {success: true}

    endpoint list_documents()
        var items = query("SELECT * FROM documents")
        return {success: true, data: items}

    endpoint create_document(name, type)
        query("INSERT INTO documents (name, type) VALUES (?, ?)", (name, type))
        return {success: true}

    endpoint delete_document(id)
        query("DELETE FROM documents WHERE id=?", (id,))
        return {success: true}

    endpoint list_procurements()
        var items = query("SELECT p.*, m.name as material_name FROM procurements p JOIN materials m ON p.material_id = m.id")
        return {success: true, data: items}

    endpoint create_procurement(material_name, qty, cost, requested_by)
        var mat = query("SELECT id FROM materials WHERE name=?", (material_name,))[0]
        query("INSERT INTO procurements (material_id, qty, cost, status, requested_by) VALUES (?, ?, ?, 'Pending', ?)", (mat.id, qty, cost, requested_by))
        var pid = query("SELECT last_insert_rowid() as id")[0].id
        query("INSERT INTO approvals (type, item_id, status, requested_by) VALUES (?, ?, 'Pending', ?)", ("Procurement Request #" + pid, pid, requested_by))
        return {success: true}

    endpoint list_approvals()
        var items = query("SELECT * FROM approvals")
        return {success: true, data: items}

    endpoint handle_approval(id, status, approved_by)
        query("UPDATE approvals SET status=? WHERE id=?", (status, id))
        var app = query("SELECT * FROM approvals WHERE id=?", (id,))[0]
        if status == "Approved"
            if app.type == "Procurement Request #" + app.item_id
                query("UPDATE procurements SET status='Approved' WHERE id=?", (app.item_id,))
                var req = query("SELECT * FROM procurements WHERE id=?", (app.item_id,))[0]
                query("UPDATE materials SET stock = stock + ? WHERE id=?", (req.qty, req.material_id))
        else
            if app.type == "Procurement Request #" + app.item_id
                query("UPDATE procurements SET status='Rejected' WHERE id=?", (app.item_id,))
        return {success: true}
'''

_CONSTRUCTION_UI = '''\
component Dashboard
    state properties = []
    state projects = []
    state incidents = []
    state approvals = []

    on load
        var pr = list_properties()
        properties = pr.data
        var p = list_projects()
        projects = p.data
        var i = list_incidents()
        incidents = i.data
        var a = list_approvals()
        approvals = a.data

    render
        div
            h2 "Construction Management Dashboard"
            p className="text-muted mb-6" "Configure property sites, track jobs, monitor Gantt scheduling timelines, manage material stock, file safety logs, and grant workflows approvals."
            div grid_cols=4
                stat_card label="Total Properties" value=properties.length icon="Building" color="blue"
                stat_card label="Active Projects" value=projects.length icon="Wrench" color="green"
                stat_card label="Safety Incidents" value=incidents.length icon="ShieldAlert" color="red"
                stat_card label="Pending Approvals" value=approvals.length icon="CheckCircle" color="amber"
            div grid_cols=2
                card
                    card_header "Project Budget Overview ($)"
                    bar_chart data=projects x_key="name" y_key="budget" height=300
                card
                    card_header "Safety Log Details"
                    table data=incidents
                        table_header
                            table_row
                                table_head "title"
                                table_head "severity"
                                table_head "status"
                                table_head "reported_by"
                        table_body

component PropertiesTable
    state items = []
    state edit_item = null
    state name = ""
    state location = ""
    state units = 0
    state status = "Under Construction"

    on load
        var resp = list_properties()
        items = resp.data

    on submit
        var r = create_property(name, location, units, status)
        if r.success
            var resp = list_properties()
            items = resp.data
            name = ""
            location = ""
            units = 0

    render
        div
            card
                card_header "Register Construction Site"
                form on_submit=submit
                    div grid_cols=2
                        input bind=name label="Property Name"
                        input bind=location label="Site Location"
                    div grid_cols=2
                        input bind=units label="Units Planned" type="number"
                        select bind=status options=["Planning", "Under Construction", "Completed"] label="Status"
                    button "Add Property Site" variant="default"
            card
                card_header "Active Properties"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "location"
                            table_head "units"
                            table_head "status"
                    table_body

component ProjectsTable
    state items = []
    state edit_item = null
    state name = ""
    state budget = 0.0
    state status = "Active"
    state start_date = ""
    state end_date = ""
    state prop_id = 1

    on load
        var pr = list_projects()
        items = pr.data

    on submit
        var r = create_project(name, prop_id, budget, status, start_date, end_date)
        if r.success
            var pr = list_projects()
            items = pr.data
            name = ""
            budget = 0.0
            start_date = ""
            end_date = ""

    render
        div
            card
                card_header "Track Project Budget & Goals"
                form on_submit=submit
                    div grid_cols=2
                        input bind=name label="Project Phase Name"
                        input bind=budget label="Financial Budget ($)" type="number"
                    div grid_cols=3
                        select bind=status options=["Planning", "Active", "Completed", "Suspended"] label="Status"
                        input bind=start_date label="Start Date (YYYY-MM-DD)"
                        input bind=end_date label="End Date (YYYY-MM-DD)"
                    button "Register Project" variant="default"
            card
                card_header "Active Construction Projects"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "budget"
                            table_head "status"
                            table_head "start_date"
                            table_head "end_date"
                    table_body

component GanttChart
    state jobs = []

    on load
        var resp = list_jobs()
        jobs = resp.data

    render
        div
            card
                card_header "Visual Project Schedule (Timeline Day 1 to 30)"
                div className="space-y-6 mt-4"
                    for j in jobs
                        div className="border-b pb-4 last:border-b-0"
                            div className="flex justify-between items-center mb-2"
                                span className="font-semibold text-sm" {j.title}
                                span className="text-xs text-muted" {"Contractor: " + j.assigned_to + " | Progress: " + j.progress + "%"}
                            div className="w-full bg-slate-100 rounded-full h-8 relative overflow-hidden flex"
                                div style={{"width": (j.start_day * 3.3) + "%"}} className="h-full bg-transparent flex-shrink-0"
                                div style={{"width": (j.duration * 3.3) + "%"}} className="h-full bg-indigo-600 rounded-md text-white flex items-center justify-between px-3 text-xs font-semibold shadow-sm"
                                    span {j.progress + "%"}
                                    span {j.duration + " d"}

component JobsTable
    state items = []
    state edit_item = null
    state title = ""
    state assigned_to = ""
    state status = "Pending"
    state progress = 0
    state start_day = 1
    state duration = 5
    state project_id = 1

    on load
        var resp = list_jobs()
        items = resp.data

    on submit
        var r = create_job(project_id, title, assigned_to, status, progress, start_day, duration)
        if r.success
            var resp = list_jobs()
            items = resp.data
            title = ""
            assigned_to = ""
            progress = 0
            start_day = 1
            duration = 5

    render
        div
            card
                card_header "Dispatch Job Order"
                form on_submit=submit
                    div grid_cols=2
                        input bind=title label="Job/Task Title"
                        input bind=assigned_to label="Assign Contractor"
                    div grid_cols=4
                        select bind=status options=["Pending", "Active", "Completed"] label="Status"
                        input bind=progress label="Progress (%)" type="number"
                        input bind=start_day label="Timeline Start Day" type="number"
                        input bind=duration label="Duration (days)" type="number"
                    button "Add Job Order" variant="default"
            card
                card_header "All Job Orders"
                table data=items
                    table_header
                        table_row
                            table_head "title"
                            table_head "assigned_to"
                            table_head "status"
                            table_head "progress"
                            table_head "start_day"
                            table_head "duration"
                    table_body

component ResourcesTable
    state items = []
    state edit_item = null
    state name = ""
    state role = ""
    state rate = 0.0
    state availability = "Available"

    on load
        var resp = list_resources()
        items = resp.data

    on submit
        var r = create_resource(name, role, rate, availability)
        if r.success
            var resp = list_resources()
            items = resp.data
            name = ""
            role = ""
            rate = 0.0

    render
        div
            card
                card_header "Onboard Site Supervisor or Resource"
                form on_submit=submit
                    div grid_cols=2
                        input bind=name label="Supervisor Name"
                        input bind=role label="Job Role"
                    div grid_cols=2
                        input bind=rate label="Hourly Rate ($)" type="number"
                        select bind=availability options=["Available", "Busy", "Off-site"] label="Availability"
                    button "Onboard Resource" variant="default"
            card
                card_header "Onboarded Site Staff"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "role"
                            table_head "rate"
                            table_head "availability"
                    table_body

component MaterialsTable
    state items = []
    state edit_item = null
    state list_m = []
    state material_name = "Cement"
    state qty = 0
    state cost = 0.0
    state requested_by = "John Supervisor"

    on load
        var resp = list_materials()
        items = resp.data
        var list = []
        for m in resp.data
            list = list + [m.name]
        list_m = list

    on submit
        var r = create_procurement(material_name, qty, cost, requested_by)
        if r.success
            toast("Procurement request dispatched for PM approvals")
            qty = 0
            cost = 0.0

    render
        div
            card
                card_header "Procure Construction Supplies"
                form on_submit=submit
                    div grid_cols=3
                        select bind=material_name options=list_m label="Select Supply Item"
                        input bind=qty label="Quantity" type="number"
                        input bind=cost label="Estimate Cost ($)" type="number"
                    button "Submit Purchase Request" variant="default"
            card
                card_header "Supply Materials Stock Inventory"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "unit"
                            table_head "stock"
                            table_head "reorder_level"
                    table_body

component AssetsTable
    state items = []
    state edit_item = null
    state name = ""
    state type = "Heavy Equipment"
    state status = "In Use"
    state location = ""

    on load
        var resp = list_assets()
        items = resp.data

    on submit
        var r = create_asset(name, type, status, location)
        if r.success
            var resp = list_assets()
            items = resp.data
            name = ""
            location = ""

    render
        div
            card
                card_header "Register Heavy Equipment / Asset"
                form on_submit=submit
                    div grid_cols=2
                        input bind=name label="Asset Name"
                        input bind=location label="Location Assigned"
                    div grid_cols=2
                        select bind=type options=["Heavy Equipment", "Vehicles", "Tools", "Power Systems"] label="Category"
                        select bind=status options=["In Use", "Available", "Maintenance", "Off-site"] label="Status"
                    button "Add Asset" variant="default"
            card
                card_header "Tracked Equipment Assets"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "type"
                            table_head "status"
                            table_head "location"
                    table_body

component IncidentsTable
    state items = []
    state edit_item = null
    state title = ""
    state severity = "Low"
    state status = "Open"
    state reported_by = ""
    state project_id = 1

    on load
        var resp = list_incidents()
        items = resp.data

    on submit
        var r = create_incident(project_id, title, severity, status, reported_by)
        if r.success
            var resp = list_incidents()
            items = resp.data
            title = ""
            reported_by = ""

    render
        div
            card
                card_header "Log Safety Site Incident"
                form on_submit=submit
                    div grid_cols=2
                        input bind=title label="Incident Description"
                        input bind=reported_by label="Reporter Name"
                    div grid_cols=2
                        select bind=severity options=["Low", "Medium", "High", "Critical"] label="Severity"
                        select bind=status options=["Open", "Investigation", "Resolved"] label="Status"
                    button "Log Incident" variant="default"
            card
                card_header "Safety Log"
                table data=items
                    table_header
                        table_row
                            table_head "title"
                            table_head "severity"
                            table_head "status"
                            table_head "reported_by"
                    table_body

component ProcurementTable
    state items = []

    on load
        var resp = list_procurements()
        items = resp.data

    render
        div
            card
                card_header "Procurement Purchases Log"
                table data=items
                    table_header
                        table_row
                            table_head "material_name"
                            table_head "qty"
                            table_head "cost"
                            table_head "status"
                            table_head "requested_by"
                    table_body

component ApprovalsTable
    state items = []
    state edit_item = null
    state edit_status = "Pending"
    state show_edit_modal = false

    on load
        var resp = list_approvals()
        items = resp.data

    render
        div
            card
                card_header "Project Approvals Required"
                table data=items
                    table_header
                        table_row
                            table_head "type"
                            table_head "status"
                            table_head "requested_by"
                    table_body
        modal show=show_edit_modal
            card_header "Grant Approval"
            form on_submit=handleSave
                select bind=edit_status options=["Pending", "Approved", "Rejected"] label="Status Decision"
                button "Save Decision" variant="default"


component DocumentsTable
    state items = []
    state edit_item = null
    state name = ""
    state type = "Blueprint"

    on load
        var resp = list_documents()
        items = resp.data

    on submit
        var r = create_document(name, type)
        if r.success
            var resp = list_documents()
            items = resp.data
            name = ""

    render
        div
            card
                card_header "Compliance & Blueprint Repository"
                form on_submit=submit
                    div grid_cols=2
                        input bind=name label="File/Document Name"
                        select bind=type options=["Blueprint", "Permit", "Contract", "Invoice", "Report"] label="Document Type"
                    button "Upload Document Metadata" variant="default"
            card
                card_header "Stored Project Documents"
                table data=items
                    table_header
                        table_row
                            table_head "name"
                            table_head "type"
                            table_head "uploaded_at"
                    table_body

app Construction
    title "Construction Manager"
    theme "professional"
    layout
        sidebar
            nav "Overview" Dashboard
            nav "Properties" PropertiesTable
            nav "Projects" ProjectsTable
            nav "Gantt Chart" GanttChart
            nav "Job Orders" JobsTable
            nav "Resources" ResourcesTable
            nav "Materials" MaterialsTable
            nav "Assets Log" AssetsTable
            nav "Incidents" IncidentsTable
            nav "Procurement" ProcurementTable
            nav "Approvals" ApprovalsTable
            nav "Documents" DocumentsTable
'''



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
        {"id": "item_manager", "name": "Item Manager", "project": True,
         "open": "ui/app.mcn",
         "files": [
             {"path": "backend/main.mcn", "content": _ITEM_MANAGER_BACKEND},
             {"path": "ui/app.mcn",       "content": _ITEM_MANAGER_UI},
         ]},
        {"id": "crm", "name": "CRM App", "project": True,
         "open": "ui/app.mcn",
         "files": [
             {"path": "backend/main.mcn", "content": _CRM_BACKEND},
             {"path": "ui/app.mcn",       "content": _CRM_UI},
         ]},
        {"id": "construction", "name": "Construction Management", "project": True,
         "open": "ui/app.mcn",
         "files": [
             {"path": "backend/main.mcn", "content": _CONSTRUCTION_BACKEND},
             {"path": "ui/app.mcn",       "content": _CONSTRUCTION_UI},
         ]},
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _seed_workspace()
    port = int(os.environ.get("MCN_PLAYGROUND_PORT", 5003))
    print(f"MCN Web Playground v2.2 — http://localhost:{port}")
    print(f"Workspace: {WORKSPACE}")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
