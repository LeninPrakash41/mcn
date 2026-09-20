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
import re
import json
import queue
import signal
import subprocess
import threading
import traceback
import contextlib
import zipfile
from datetime import datetime
from pathlib import Path

_DEFAULT_WORKSPACE = Path(__file__).resolve().parent / "workspace"
_ENV_WORKSPACE = os.environ.get("MCN_WORKSPACE")

if _ENV_WORKSPACE:
    WORKSPACE = Path(_ENV_WORKSPACE)
else:
    try:
        WORKSPACE = Path.home() / ".mcn" / "playground"
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        _test_file = WORKSPACE / ".perm_check"
        _test_file.touch()
        _test_file.unlink(missing_ok=True)
    except (PermissionError, OSError):
        WORKSPACE = _DEFAULT_WORKSPACE

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


# ── Static & Website ──────────────────────────────────────────────────────────

_WEBSITE_DIR = os.path.join(_ROOT_DIR, "website")

@app.after_request
def _add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
@app.route("/ide")
@app.route("/playground")
def index():
    return send_from_directory(_THIS_DIR, "index.html", max_age=0)


@app.route("/website")
@app.route("/website/")
def website_index():
    return send_from_directory(_WEBSITE_DIR, "index.html")


@app.route("/website/<path:filename>")
def website_static(filename):
    return send_from_directory(_WEBSITE_DIR, filename)


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


# ── Community Registration & Telemetry / Feedback ─────────────────────────────

_COMMUNITY_REG_FILE = Path.home() / ".mcn" / "community_registration.json"

def _get_local_registration() -> dict:
    if _COMMUNITY_REG_FILE.exists():
        try:
            return json.loads(_COMMUNITY_REG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_local_registration(data: dict):
    try:
        _COMMUNITY_REG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _COMMUNITY_REG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def _forward_telemetry_async(url: str, payload: dict):
    if not url:
        return
    def _send():
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "MCN-Studio/3.0.0"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            # Non-blocking graceful fallback
            pass
    t = threading.Thread(target=_send, daemon=True)
    t.start()

@app.route("/api/telemetry/status")
def telemetry_status():
    reg = _get_local_registration()
    return jsonify({
        "registered": bool(reg.get("email")),
        "user": reg
    })

@app.route("/api/telemetry/register", methods=["POST"])
def telemetry_register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email address required"}), 400

    profile = {
        "email": email,
        "name": (data.get("name") or "").strip(),
        "organization": (data.get("organization") or "").strip(),
        "platform": data.get("platform") or ("desktop_mac" if os.environ.get("MCN_DESKTOP") else "web"),
        "app_version": data.get("app_version") or "3.0.0",
        "newsletter_opt_in": bool(data.get("newsletter_opt_in", True)),
        "registered_at": datetime.now().isoformat()
    }
    _save_local_registration(profile)

    # Forward to remote PHP endpoint if configured
    remote_url = os.environ.get("MCN_TELEMETRY_ENDPOINT", "")
    _forward_telemetry_async(remote_url, profile)

    return jsonify({
        "success": True,
        "message": "Registration successful! Welcome to the MCN Developer Community.",
        "profile": profile
    })

@app.route("/api/telemetry/feedback", methods=["POST"])
def telemetry_feedback():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message description is required"}), 400

    reg = _get_local_registration()
    payload = {
        "email": data.get("email") or reg.get("email", ""),
        "feedback_type": data.get("feedback_type") or "feedback",
        "subject": data.get("subject") or "",
        "message": message,
        "error_logs": data.get("error_logs") or "",
        "system_info": {
            "platform": sys.platform,
            "python_version": sys.version,
            "desktop": bool(os.environ.get("MCN_DESKTOP")),
            "app_version": "3.0.0"
        },
        "platform": "desktop" if os.environ.get("MCN_DESKTOP") else "web",
        "app_version": "3.0.0",
        "created_at": datetime.now().isoformat()
    }

    # Forward to remote PHP endpoint if configured
    remote_url = os.environ.get("MCN_FEEDBACK_ENDPOINT", "")
    _forward_telemetry_async(remote_url, payload)

    return jsonify({
        "success": True,
        "message": "Thank you! Your feedback/error report has been recorded."
    })


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
// MCN Backend Service — click ▶ Run Backend [Ctrl+Enter] to test
service api
    port 8080

    endpoint get_dashboard()
        return {
            title: "Sales Intelligence Hub",
            active_deals: 14,
            pipeline_value: "$420,000",
            status: "online"
        }

    endpoint list_leads()
        return [
            {id: "L1", name: "Sarah Jenkins", company: "Acme Health", value: 75000, status: "Qualified"},
            {id: "L2", name: "David Lin", company: "Vertex AI", value: 140000, status: "Proposal"},
            {id: "L3", name: "Elena Rostova", company: "FinTech Cloud", value: 185000, status: "Closing"}
        ]

// Live startup script
var welcome = "MCN Studio Ready"
log("⚡ " + welcome)
var leads = list_leads()
log("✓ Loaded " + str(len(leads)) + " active sales pipeline leads")
for lead in leads
    log("  • " + lead.name + " (" + lead.company + ") - $" + str(lead.value))
'''

_DEFAULT_UI = '''\
// MCN UI — click ⚡ Build & Preview to compile to React & Flutter
component Dashboard
    state leads = []
    state total = "$420,000"

    on load
        leads = list_leads()

    render
        card
            card_header "Sales Intelligence & Pipeline"
            stat label="Active Pipeline" value=total change=14.2
            table data=leads
                table_header
                    table_row
                        table_head "id"
                        table_head "name"
                        table_head "company"
                        table_head "value"
                        table_head "status"
                table_body

app MainApp
    title "Sales Intelligence Hub"
    layout
        main
            Dashboard
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


_DEFAULT_MOBILE_DART = '''\
import 'package:flutter/material.dart';
import 'screens/dashboard.dart';

void main() {
  runApp(const MCNMobileApp());
}

class MCNMobileApp extends StatelessWidget {
  const MCNMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sales Intelligence Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0F1D),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          secondary: Color(0xFFFF6B6B),
          surface: Color(0xFF111C33),
          background: Color(0xFF0A0F1D),
        ),
        useMaterial3: true,
      ),
      home: const DashboardScreen(),
    );
  }
}
'''

_DEFAULT_MOBILE_SCREEN = '''\
import 'package:flutter/material.dart';
import '../widgets/mcn_widgets.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _activeDeals = 14;
  final String _pipelineValue = "$420,000";

  final List<Map<String, dynamic>> _leads = [
    {"name": "Sarah Jenkins", "company": "Acme Health", "value": "$75,000", "status": "Qualified"},
    {"name": "David Lin", "company": "Vertex AI", "value": "$140,000", "status": "Proposal"},
    {"name": "Elena Rostova", "company": "FinTech Cloud", "value": "$185,000", "status": "Closing"},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Sales Intelligence", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: const Color(0xFF111C33),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Color(0xFF38BDF8)),
            onPressed: () {
              setState(() {
                _activeDeals += 1;
              });
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // KPI Stat Row
            Row(
              children: [
                Expanded(
                  child: MCNStatCard(
                    label: "Active Deals",
                    value: "$_activeDeals",
                    change: "+12.5%",
                    isPositive: true,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: MCNStatCard(
                    label: "Pipeline Value",
                    value: _pipelineValue,
                    change: "+18.2%",
                    isPositive: true,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Section Header
            const Text(
              "Recent High-Value Leads",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 12),

            // Leads List
            ..._leads.map((lead) => MCNLeadTile(
              name: lead["name"],
              company: lead["company"],
              value: lead["value"],
              status: lead["status"],
            )),

            const SizedBox(height: 20),
            // Primary Action Button
            MCNButton(
              text: "+ Create New Deal Opportunity",
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("Opportunity created via MCN Mobile API!")),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
'''

_DEFAULT_MOBILE_WIDGETS = '''\
import 'package:flutter/material.dart';

class MCNStatCard extends StatelessWidget {
  final String label;
  final String value;
  final String change;
  final bool isPositive;

  const MCNStatCard({
    super.key,
    required this.label,
    required this.value,
    required this.change,
    this.isPositive = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14.0),
      decoration: BoxDecoration(
        color: const Color(0xFF111C33),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E2D4A)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 4),
          Text(
            change,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: isPositive ? const Color(0xFF10B981) : const Color(0xFFFF6B6B)),
          ),
        ],
      ),
    );
  }
}

class MCNLeadTile extends StatelessWidget {
  final String name;
  final String company;
  final String value;
  final String status;

  const MCNLeadTile({
    super.key,
    required this.name,
    required this.company,
    required this.value,
    required this.status,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF182442),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E2D4A)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white)),
              const SizedBox(height: 2),
              Text(company, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF38BDF8), fontSize: 13)),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0x2038BDF8),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0x4038BDF8)),
                ),
                child: Text(status, style: const TextStyle(fontSize: 10, color: Color(0xFF38BDF8), fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class MCNButton extends StatelessWidget {
  final String text;
  final VoidCallback onPressed;

  const MCNButton({
    super.key,
    required this.text,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF0284C7),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: onPressed,
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
      ),
    );
  }
}
'''

_DEFAULT_MOBILE_MCN = '''\
// MCN Mobile UI (Flutter Target)
// Click ⚡ Build Flutter Simulator to compile to mobile package

component MobileDashboard
    state active_deals = 14
    state pipeline_value = "$420,000"

    render
        card
            card_header "Sales Intelligence Mobile"
            stat label="Active Deals" value="14" change=12.5
            stat label="Pipeline Value" value="$420,000" change=18.2
            button "+ Create New Deal Opportunity"

app MobileSalesApp
    title "Sales Intelligence Mobile"
    target "flutter"
    layout
        main
            MobileDashboard
'''

_DEFAULT_PUBSPEC = '''\
name: mcn_mobile_app
description: MCN Model Context Native Mobile Application
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0

flutter:
  uses-material-design: true
'''

_DEFAULT_MOBILE_MANIFEST = {
    "name": "SalesMobileApp",
    "components": {
        "Dashboard": {
            "type": "container",
            "props": {"className": "column"},
            "children": [
                {"type": "text", "props": {"tag": "h1", "content": "Sales Intelligence Mobile"}},
                {"type": "card", "props": {"title": "Active Pipeline", "value": "$420,000"}},
                {"type": "button", "props": {"text": "⚡ Refresh Deals"}},
                {"type": "input", "props": {"placeholder": "Search leads..."}}
            ]
        }
    },
    "pages": {
        "Sales Intelligence": {
            "components": ["Dashboard"]
        }
    }
}

_DEFAULT_REPL_SCRIPT = '''\
// MCN REPL Script — Press Ctrl+Enter to execute expressions

var title = "MCN REPL Environment"
log("⚡ " + title)

function calculate_roi(revenue, cost)
    return ((revenue - cost) / cost) * 100

var revenue = 150000
var cost = 95000
var roi = calculate_roi(revenue, cost)

log("Revenue: $" + str(revenue))
log("Cost:    $" + str(cost))
log("ROI:     " + str(roi) + "%")

// Working with lists
var deals = [45000, 120000, 85000, 30000, 210000]
log("Total Pipeline: $" + str(sum(deals)))
log("Average Deal:   $" + str(avg(deals)))
log("Max Deal:       $" + str(max(deals)))
'''


def _seed_workspace(ws: Path | None = None):
    """Write default starter files if workspace is empty or missing MCN files."""
    ws = ws or WORKSPACE
    
    # 1. Web Workspace
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

    # 2. Mobile (Flutter) Workspace
    mobile_dir = ws / "mobile"
    mobile_lib = mobile_dir / "lib"
    mobile_screens = mobile_lib / "screens"
    mobile_widgets = mobile_lib / "widgets"
    mobile_screens.mkdir(parents=True, exist_ok=True)
    mobile_widgets.mkdir(parents=True, exist_ok=True)

    dart_main = mobile_lib / "main.dart"
    dart_screen = mobile_screens / "dashboard.dart"
    dart_widgets = mobile_widgets / "mcn_widgets.dart"
    mobile_mcn = mobile_dir / "ui.mcn"
    pubspec_file = mobile_dir / "pubspec.yaml"
    mobile_manifest = mobile_dir / "ui-manifest.json"

    if not dart_main.exists():
        dart_main.write_text(_DEFAULT_MOBILE_DART, encoding="utf-8")
    if not dart_screen.exists():
        dart_screen.write_text(_DEFAULT_MOBILE_SCREEN, encoding="utf-8")
    if not dart_widgets.exists():
        dart_widgets.write_text(_DEFAULT_MOBILE_WIDGETS, encoding="utf-8")
    if not mobile_mcn.exists():
        mobile_mcn.write_text(_DEFAULT_MOBILE_MCN, encoding="utf-8")
    if not pubspec_file.exists():
        pubspec_file.write_text(_DEFAULT_PUBSPEC, encoding="utf-8")
    if not mobile_manifest.exists():
        mobile_manifest.write_text(json.dumps(_DEFAULT_MOBILE_MANIFEST, indent=2), encoding="utf-8")

    # Clean up legacy flutter folder if present in workspace
    legacy_flutter = ws / "flutter"
    if legacy_flutter.exists():
        import shutil
        shutil.rmtree(legacy_flutter, ignore_errors=True)

    # 3. REPL Scripts Workspace
    scripts_dir = ws / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    repl_file = scripts_dir / "sandbox.mcn"
    if not repl_file.exists():
        repl_file.write_text(_DEFAULT_REPL_SCRIPT, encoding="utf-8")


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

        # Remove source dirs and generated frontend/mobile
        for d in ("backend", "ui", "mobile", "flutter", "frontend"):
            p = ws / d
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
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

_REPL_INTERPRETERS = {}

@app.route("/api/execute", methods=["POST"])
def execute_mcn():
    data = request.get_json(silent=True) or {}
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err, "output": []}), 400

    code = data.get("code", "")
    output_lines = []
    is_repl = bool(data.get("is_repl", False))
    session_id = data.get("session_id", "default")

    def run():
        if is_repl:
            if session_id not in _REPL_INTERPRETERS:
                _REPL_INTERPRETERS[session_id] = MCNInterpreter()
            interp = _REPL_INTERPRETERS[session_id]
        else:
            interp = MCNInterpreter()

        def _capture_log(*args):
            output_lines.append(" ".join(str(a) for a in args))
        interp._functions["log"]  = _capture_log
        interp._functions["echo"] = _capture_log

        # 1. Pre-populate IoT devices with simulated states if supported
        if hasattr(interp, "_ensure_v3_systems"):
            try:
                interp._ensure_v3_systems()
            except Exception:
                pass
        if hasattr(interp, "iot_connector") and hasattr(interp.iot_connector, "devices"):
            for dev_id, dev in _SIMULATED_DEVICES.items():
                interp.iot_connector.devices[dev_id] = {
                    "type": dev["type"],
                    "connection": {},
                    "override_value": dev["value"],
                    "status": "registered"
                }

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


@app.route("/api/repl/reset", methods=["POST"])
def repl_reset():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    if session_id in _REPL_INTERPRETERS:
        del _REPL_INTERPRETERS[session_id]
    return jsonify({"success": True})


_RESERVED_ENV_KEYS = {"true", "false", "null", "request_data"}

@app.route("/api/repl/vars", methods=["GET"])
def repl_vars():
    session_id = request.args.get("session_id", "default")
    interp = _REPL_INTERPRETERS.get(session_id)
    if not interp:
        return jsonify({"vars": {}})
    vars_dict = {}
    evaluator = getattr(interp, "_evaluator", None)
    if evaluator and hasattr(evaluator, "globals") and hasattr(evaluator.globals, "_vars"):
        for k, v in evaluator.globals._vars.items():
            if not k.startswith("_") and k not in _RESERVED_ENV_KEYS and not callable(v):
                vars_dict[k] = str(v)
    return jsonify({"vars": vars_dict})


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


@app.route("/api/agent/verify", methods=["POST"])
def agent_verify_endpoint():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"success": False, "error": "Missing 'code' field"}), 400
    try:
        from mcn.core_engine.agent_toolkit import verify_agent_code
    except ImportError:
        from core_engine.agent_toolkit import verify_agent_code
    result = verify_agent_code(code)
    return jsonify({"success": True, "result": result})


@app.route("/api/agent/repair", methods=["POST"])
def agent_repair_endpoint():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"success": False, "error": "Missing 'code' field"}), 400
    try:
        from mcn.core_engine.agent_toolkit import generate_repair_prompt
    except ImportError:
        from core_engine.agent_toolkit import generate_repair_prompt
    prompt = generate_repair_prompt(code)
    return jsonify({"success": True, "repair_prompt": prompt})


@app.route("/api/agent/scaffold", methods=["GET", "POST"])
def agent_scaffold_endpoint():
    template = "sales_calendar"
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        template = data.get("template", "sales_calendar")
    else:
        template = request.args.get("template", "sales_calendar")
    try:
        from mcn.core_engine.agent_toolkit import get_agent_scaffold
    except ImportError:
        from core_engine.agent_toolkit import get_agent_scaffold
    code = get_agent_scaffold(template)
    return jsonify({"success": True, "template": template, "code": code})


@app.route("/api/agent/explain", methods=["GET", "POST"])
def agent_explain_endpoint():
    query = ""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        query = data.get("query", "")
    else:
        query = request.args.get("query", "")
    if not query:
        return jsonify({"success": False, "error": "Missing 'query' parameter"}), 400
    try:
        from mcn.core_engine.agent_toolkit import explain_syntax
    except ImportError:
        from core_engine.agent_toolkit import explain_syntax
    info = explain_syntax(query)
    return jsonify({"success": True, "query": query, "info": info})


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
    attachments = data.get("attachments", []) or []
    api_key     = (data.get("api_key") or "").strip() \
                  or _load_config().get("api_key") \
                  or os.getenv("ANTHROPIC_API_KEY") \
                  or os.getenv("OPENAI_API_KEY")

    if not description and not attachments:
        return jsonify({"error": "Missing 'description' or 'attachments'"}), 400
    if not description and attachments:
        description = f"Build a complete full-stack application according to the {len(attachments)} attached specification documents, flowcharts, and Figma design mockups."
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

            status_msg = f"Generating MCN app with {len(attachments)} attachment(s)…" if attachments else "Generating MCN app…"
            token_queue.put({"type": "status", "text": status_msg})

            result = agent.generate(
                description=description,
                attachments=attachments,
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
    platform = data.get("platform", "react")

    # Optionally pre-save both files from the request body
    for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
        if key in data and data[key]:
            (WORKSPACE / rel).parent.mkdir(parents=True, exist_ok=True)
            (WORKSPACE / rel).write_text(data[key], encoding="utf-8")

    ui_path  = WORKSPACE / "ui" / "app.mcn"
    backend_path = WORKSPACE / "backend" / "main.mcn"

    if platform == "flutter":
        out_path = WORKSPACE / "mobile"
        out_path.mkdir(parents=True, exist_ok=True)
        manifest_path = out_path / "ui-manifest.json"
        
        # Ensure mobile/ui-manifest.json exists
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(_DEFAULT_MOBILE_MANIFEST, indent=2), encoding="utf-8")

        # Clean up legacy flutter dir if present
        legacy_flutter = WORKSPACE / "flutter"
        if legacy_flutter.exists():
            import shutil
            shutil.rmtree(legacy_flutter, ignore_errors=True)

        try:
            try:
                from mcn.fullstack.flutter_generator import FlutterProjectGenerator
            except ImportError:
                from fullstack.flutter_generator import FlutterProjectGenerator  # type: ignore
                
            gen = FlutterProjectGenerator()
            gen.generate_project(str(manifest_path), str(out_path), "mcn_mobile_app")

            
            files = []
            for p in sorted(out_path.rglob("*")):
                if p.is_file():
                    files.append(str(p.relative_to(WORKSPACE)))
                    
            return jsonify({
                "success": True,
                "platform": "flutter",
                "files": files,
                "stdout": f"✓ Generated Flutter mobile package with {len(files)} files in mobile/\n"
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()})

    # Default: React Compilation via UICompiler
    out_path = WORKSPACE / "frontend"
    if not ui_path.exists():
        return jsonify({"success": False, "error": "ui/app.mcn not found. Create or select a UI template."}), 400


    try:
        try:
            from mcn.core_engine.lexer import Lexer
            from mcn.core_engine.parser import Parser
            from mcn.core_engine.mcn_interpreter import MCNInterpreter
            from mcn.core_engine.ui_compiler import UICompiler
        except ImportError:
            from core_engine.lexer import Lexer  # type: ignore
            from core_engine.parser import Parser  # type: ignore
            from core_engine.mcn_interpreter import MCNInterpreter  # type: ignore
            from core_engine.ui_compiler import UICompiler  # type: ignore
        
        code = ui_path.read_text(encoding="utf-8")
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()
        interp = MCNInterpreter()
        evaluator = interp._evaluator
        evaluator.execute_program(program)
        
        out_path.mkdir(parents=True, exist_ok=True)
        compiler = UICompiler(output_dir=out_path)
        written = compiler.compile(evaluator)
        
        files = []
        if out_path.exists():
            for p in sorted(out_path.rglob("*")):
                if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
                    files.append(str(p.relative_to(WORKSPACE)))
                    
        stdout = f"✓ Compiled {len(written)} frontend components into frontend/\n"
        if compiler._shadcn_needed:
            stdout += f"Components included: {', '.join(sorted(compiler._shadcn_needed))}"
            
        return jsonify({
            "success": True,
            "platform": "react",
            "files": files,
            "stdout": stdout,
            "stderr": ""
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {str(e)}", "trace": traceback.format_exc()})


# ── Production Download & Scaffolds ───────────────────────────────────────────

@app.route("/api/download")
def download_project():
    """Zip the project with complete production Docker, Nginx, and CI/CD bundle."""
    platform = request.args.get("platform", "react").lower()
    frontend = WORKSPACE / "frontend"
    backend = WORKSPACE / "backend"
    
    scaffolds_dir = Path(__file__).parent / "scaffolds"
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Package Frontend if present
        if frontend.exists():
            for p in sorted(frontend.rglob("*")):
                if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
                    zf.write(p, p.relative_to(WORKSPACE))
        
        # 2. Package Backend if present
        if backend.exists():
            for p in sorted(backend.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    zf.write(p, p.relative_to(WORKSPACE))

        # 3. Package UI / MCN root files
        for p in sorted(WORKSPACE.glob("*.mcn")):
            if p.is_file():
                zf.write(p, p.relative_to(WORKSPACE))
        if (WORKSPACE / "ui").exists():
            for p in sorted((WORKSPACE / "ui").rglob("*.mcn")):
                if p.is_file():
                    zf.write(p, p.relative_to(WORKSPACE))

        # 4. Inject Production Deployment Bundle
        if scaffolds_dir.exists():
            for sc in scaffolds_dir.rglob("*"):
                if sc.is_file() and not sc.name.startswith(".DS_Store"):
                    arcname = str(sc.relative_to(scaffolds_dir))
                    zf.write(sc, arcname)
        else:
            # Fallback inline scaffolds
            zf.writestr("Dockerfile", "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nEXPOSE 8080\nCMD [\"python\", \"backend/main.mcn\"]\n")
            zf.writestr("docker-compose.yml", "version: '3.8'\nservices:\n  app:\n    build: .\n    ports:\n      - \"8080:8080\"\n")
            zf.writestr(".env.example", "PORT=8080\nJWT_SECRET=mcn-secret\n")

    buf.seek(0)
    filename = "mcn-flutter-app.zip" if platform == "flutter" else "mcn-fullstack-app.zip"
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
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


# ── OpenAPI 3.0 & Swagger Interactive Explorer ────────────────────────────────

def _generate_openapi_spec(ws: Path) -> dict:
    title = "MCN Full-Stack Application"
    description = "Auto-generated OpenAPI 3.0 specification for MCN services, contracts, and endpoints."
    version = "1.0.0"

    mcn_texts = []
    for f in sorted(ws.rglob("*.mcn")):
        if f.is_file() and not any(p in ("node_modules", "frontend", ".git", "__pycache__") for p in f.parts):
            try:
                mcn_texts.append(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    all_code = "\n".join(mcn_texts)

    tm = re.search(r'title\s+["\']([^"\']+)["\']', all_code)
    if tm:
        title = tm.group(1).strip()
    elif "app " in all_code:
        am = re.search(r'app\s+([A-Za-z0-9_]+)', all_code)
        if am:
            title = f"{am.group(1).strip()} API"

    schemas = {}
    for cm in re.finditer(r'contract\s+([A-Za-z0-9_]+)\s*\n((?:\s+[A-Za-z0-9_]+:\s*[A-Za-z0-9_\[\]]+\n*)+)', all_code):
        cname = cm.group(1).strip()
        body = cm.group(2)
        props = {}
        required = []
        for line in body.strip().splitlines():
            line = line.strip()
            if ":" in line:
                fname, ftype = line.split(":", 1)
                fname = fname.strip()
                ftype = ftype.strip().lower()
                required.append(fname)
                if ftype in ("int", "integer"):
                    props[fname] = {"type": "integer", "example": 1}
                elif ftype in ("float", "real", "number"):
                    props[fname] = {"type": "number", "format": "float", "example": 99.99}
                elif ftype in ("bool", "boolean"):
                    props[fname] = {"type": "boolean", "example": True}
                elif ftype.startswith("list") or ftype.startswith("array"):
                    props[fname] = {"type": "array", "items": {"type": "string"}}
                else:
                    props[fname] = {"type": "string", "example": f"Sample {fname}"}
        schemas[cname] = {
            "type": "object",
            "properties": props,
            "required": required
        }

    paths = {}
    ep_pattern = re.compile(r'(?:@guard\(([^)]*)\)\s*)?endpoint\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)', re.MULTILINE)
    for match in ep_pattern.finditer(all_code):
        guard_meta = match.group(1)
        ep_name = match.group(2).strip()
        params_str = match.group(3).strip()

        ep_path = f"/api/{ep_name}"
        params_list = [p.strip() for p in params_str.split(",") if p.strip()]

        method = "post" if any(k in ep_name.lower() for k in ("create", "save", "add", "update", "delete", "post", "run", "submit", "test", "publish")) or params_list else "get"
        
        tags = ["Core Services"]
        if "item" in ep_name.lower(): tags = ["Inventory"]
        elif "deal" in ep_name.lower() or "sales" in ep_name.lower(): tags = ["Sales & CRM"]
        elif "prompt" in ep_name.lower() or "workflow" in ep_name.lower(): tags = ["AI Marketplace"]
        elif "project" in ep_name.lower() or "job" in ep_name.lower(): tags = ["Construction"]
        elif "analytic" in ep_name.lower() or "report" in ep_name.lower() or "kpi" in ep_name.lower(): tags = ["Analytics & BI"]

        summary = ep_name.replace("_", " ").title()
        description = f"Execute MCN service endpoint `{ep_name}`."
        if guard_meta:
            description += f" **Guarded with RBAC**: `{guard_meta}`."

        op = {
            "summary": summary,
            "description": description,
            "tags": tags,
            "responses": {
                "200": {
                    "description": "Successful execution",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": True},
                                    "data": {"type": "array", "items": {"type": "object"}}
                                }
                            }
                        }
                    }
                }
            }
        }

        if guard_meta:
            op["security"] = [{"bearerAuth": []}]
            op["responses"]["401"] = {"description": "Missing or invalid JWT Bearer token"}
            op["responses"]["403"] = {"description": "Forbidden — Insufficient role permissions"}

        if method == "get" and params_list:
            op["parameters"] = [
                {
                    "name": p.split("=")[0].strip(),
                    "in": "query",
                    "required": "=" not in p,
                    "schema": {"type": "string"}
                }
                for p in params_list
            ]
        elif method == "post" and params_list:
            body_props = {}
            body_req = []
            for p in params_list:
                pname = p.split("=")[0].strip()
                body_props[pname] = {"type": "string", "example": pname}
                if "=" not in p:
                    body_req.append(pname)
            op["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": body_props,
                            "required": body_req
                        }
                    }
                }
            }

        paths[ep_path] = {method: op}

    if "/health" not in paths:
        paths["/health"] = {
            "get": {
                "summary": "Service Health Check",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {"status": {"type": "string", "example": "ok"}}}}}
                    }
                }
            }
        }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": description,
            "version": version
        },
        "servers": [
            {"url": "http://localhost:8080", "description": "Local MCN Backend Server"},
            {"url": "http://localhost:5003", "description": "MCN Web Playground API"}
        ],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Enter JWT token with role claims (Bearer <token>)"
                }
            }
        }
    }


@app.route("/api/openapi.json")
def get_openapi_spec():
    """Return auto-generated OpenAPI 3.0 specification."""
    return jsonify(_generate_openapi_spec(WORKSPACE))


@app.route("/docs")
def get_swagger_docs():
    """Render interactive Swagger UI documentation explorer."""
    swagger_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MCN API Documentation — Swagger UI</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin: 0; background: #0b132b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .swagger-ui .topbar { background-color: #080e21; border-bottom: 1px solid #1e293b; }
    .swagger-ui .info .title { color: #f8fafc; font-size: 24px; font-weight: 800; }
    .swagger-ui .info p, .swagger-ui .info li { color: #94a3b8; }
    .swagger-ui { color: #cbd5e1; }
    .swagger-ui .scheme-container { background: #0f172a; box-shadow: none; border-bottom: 1px solid #1e293b; }
    .swagger-ui .opblock { border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); background: #0f172a; }
    .swagger-ui .opblock .opblock-summary-path { color: #f8fafc; font-weight: 700; }
    .swagger-ui .opblock.opblock-post { border-color: rgba(56,189,248,0.4); background: rgba(56,189,248,0.04); }
    .swagger-ui .opblock.opblock-get { border-color: rgba(52,211,153,0.4); background: rgba(52,211,153,0.04); }
    .swagger-ui .btn.authorize { color: #38bdf8; border-color: #38bdf8; }
    .swagger-ui .btn.authorize svg { fill: #38bdf8; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" charset="UTF-8"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
  <script>
  window.onload = function() {
    window.ui = SwaggerUIBundle({
      url: "/api/openapi.json",
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      plugins: [
        SwaggerUIBundle.plugins.DownloadUrl
      ],
      layout: "StandaloneLayout"
    });
  };
  </script>
</body>
</html>"""
    return Response(swagger_html, mimetype="text/html")


# ── Declarative Auth & RBAC Guard Validator ───────────────────────────────────

@app.route("/api/auth/validate_guard", methods=["POST"])
def validate_auth_guard():
    """Validate a JWT token against required role(s)."""
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    required_role = data.get("required_role", "")

    try:
        from mcn.core_engine.auth_primitives import _decode_token, auth_require_role
        payload = _decode_token(token)
        if not payload:
            return jsonify({"valid": False, "error": "Invalid or expired token"}), 401
        
        user_roles = payload.get("roles", [])
        if isinstance(user_roles, str):
            user_roles = [user_roles]

        if required_role and required_role not in user_roles and "admin" not in user_roles:
            return jsonify({"valid": False, "error": f"Role '{required_role}' required", "user_roles": user_roles}), 403

        return jsonify({"valid": True, "user": payload, "user_roles": user_roles})
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 400


# ── Multi-Database SQL Migration Generator ────────────────────────────────────

@app.route("/api/database/export_migrations")
def export_database_migrations():
    """Translate workspace SQLite tables and contracts into PostgreSQL / Supabase DDL migrations."""
    dialect = request.args.get("dialect", "postgres").lower()
    
    mcn_texts = []
    for f in sorted(WORKSPACE.rglob("*.mcn")):
        if f.is_file() and not any(p in ("node_modules", "frontend", ".git", "__pycache__") for p in f.parts):
            try:
                mcn_texts.append(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    all_code = "\n".join(mcn_texts)
    
    lines = [
        f"-- =============================================================================",
        f"-- MCN Database Migration Schema ({dialect.upper()})",
        f"-- Generated at: {datetime.now().isoformat()}",
        f"-- =============================================================================\n",
    ]

    if dialect in ("postgres", "supabase"):
        lines.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";\n")

    # 1. Parse CREATE TABLE statements
    for m in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\(([^)]+)\)', all_code, re.IGNORECASE):
        tname = m.group(1).strip()
        body = m.group(2).strip()

        col_defs = []
        for col in body.split(","):
            col = col.strip()
            if not col: continue
            
            if dialect in ("postgres", "supabase"):
                col = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', col, flags=re.IGNORECASE)
                col = re.sub(r'\bTEXT\b', 'VARCHAR(255)', col, flags=re.IGNORECASE)
                col = re.sub(r'\bREAL\b', 'NUMERIC(12, 2)', col, flags=re.IGNORECASE)
                col = re.sub(r"DEFAULT\s*\(datetime\('now'\)\)", "DEFAULT NOW()", col, flags=re.IGNORECASE)
            col_defs.append(f"    {col}")

        lines.append(f"CREATE TABLE IF NOT EXISTS {tname} (\n" + ",\n".join(col_defs) + "\n);\n")

        if dialect == "supabase":
            lines.append(f"-- Enable Row Level Security for Supabase\nALTER TABLE {tname} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY \"Allow authenticated read\" ON {tname} FOR SELECT TO authenticated USING (true);\n")

    migration_sql = "\n".join(lines)
    return jsonify({
        "success": True,
        "dialect": dialect,
        "filename": "001_initial_schema.sql",
        "migration_sql": migration_sql
    })


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


def _generate_interactive_preview_html(ws: Path, app_code: str, components_code: dict) -> str:
    # ── 1. Extract App Title & Layout Type from ui/app.mcn and App.tsx ────────
    app_title = "MCN Application"
    layout_type = "single"
    nav_items = []

    ui_src = ""
    if (ws / "ui" / "app.mcn").exists():
        try:
            ui_src = (ws / "ui" / "app.mcn").read_text(encoding="utf-8")
        except Exception:
            ui_src = ""

    # App title
    atm = re.search(r'title\s+["\']([^"\']+)["\']', ui_src)
    if atm:
        app_title = atm.group(1).strip()
    else:
        tm = re.search(r'<h1[^>]*>([^<]+)</h1>', app_code)
        if tm:
            app_title = tm.group(1).strip()
        elif "app " in ui_src:
            m = re.search(r'app\s+([A-Za-z0-9_]+)', ui_src)
            if m:
                app_title = m.group(1).strip()

    # Detect Layout & Navigation
    if "sidebar" in ui_src.lower() or "<aside" in app_code:
        layout_type = "sidebar"
    elif "tabs" in ui_src.lower() or "<Tabs" in app_code:
        layout_type = "tabs"

    # Extract Nav Items from ui/app.mcn
    for match in re.finditer(r'(?:nav|tab)\s+["\']([^"\']+)["\']\s+([A-Za-z0-9_]+)', ui_src):
        nav_items.append({"label": match.group(1).strip(), "comp": match.group(2).strip()})

    # If no nav items from mcn, try extracting from App.tsx
    if not nav_items:
        for match in re.finditer(r'setActive\(["\']([^"\']+)["\']\)', app_code):
            lbl = match.group(1).strip()
            if not any(n["label"] == lbl for n in nav_items):
                comp_match = re.search(rf'active\s*===\s*["\']{re.escape(lbl)}["\']\s*&&\s*<([A-Za-z0-9_]+)', app_code)
                comp_name = comp_match.group(1) if comp_match else lbl
                nav_items.append({"label": lbl, "comp": comp_name})

        for match in re.finditer(r'<TabsTrigger\s+value=["\']([^"\']+)["\']', app_code):
            lbl = match.group(1).strip()
            if not any(n["label"] == lbl for n in nav_items):
                nav_items.append({"label": lbl, "comp": lbl})

    # If still no nav items, but we have components, create nav from components
    if not nav_items and components_code:
        comp_keys = list(components_code.keys())
        if "Dashboard" in comp_keys:
            comp_keys.remove("Dashboard")
            comp_keys.insert(0, "Dashboard")
        for ck in comp_keys:
            nav_items.append({"label": ck.replace("Table", "").replace("Form", " Form").strip() or ck, "comp": ck})
        if len(nav_items) > 1:
            layout_type = "sidebar" if len(nav_items) >= 3 else "tabs"

    tabs = [n["label"] for n in nav_items]

    # ── 2. Parse Component Metadata ───────────────────────────────────────────
    parsed_comps = {}
    for comp_name, comp_code in components_code.items():
        card_title = ""
        m = re.search(r'<CardTitle[^>]*>([^<]+)</CardTitle>', comp_code)
        if m:
            card_title = m.group(1).strip()
        if not card_title:
            m = re.search(r'<h[1-3][^>]*>\{?["\']?([^"\'<]+)["\']?\}?</h[1-3]>', comp_code)
            if m:
                card_title = m.group(1).strip()

        cols = []
        for match in re.finditer(r'<TableHead[^>]*>\{?["\']?([^"\'<]+)["\']?\}?</TableHead>', comp_code):
            c = match.group(1).strip()
            if c.lower() != "actions" and c not in cols:
                cols.append(c)

        fields = []
        for match in re.finditer(r'<label[^>]*>([^<]+)</label>', comp_code):
            lbl = match.group(1).strip()
            if lbl and lbl.lower() not in ["actions", "status"] and lbl not in fields:
                fields.append(lbl)

        stats = []
        for match in re.finditer(r'label=["\']([^"\']+)["\'][^>]*value=\{?([^\s">]+)\}?', comp_code):
            stats.append({"label": match.group(1), "value": match.group(2)})

        form_titles = []
        for match in re.finditer(r'card_header\s+["\'](Add[^"\']+|Create[^"\']+|Log[^"\']+|New[^"\']+|Publish[^"\']+)["\']', comp_code, re.IGNORECASE):
            form_titles.append(match.group(1).strip())

        parsed_comps[comp_name] = {
            "name": comp_name,
            "title": card_title or comp_name,
            "columns": cols,
            "fields": fields,
            "stats": stats,
            "form_titles": form_titles,
            "has_table": bool(cols),
            "has_form": bool(fields) or "form" in comp_code.lower() or "button" in comp_code.lower(),
        }

    # ── 3. Multi-Entity Seed Data Engine ───────────────────────────────────────
    datasets = {}

    for comp_name, comp_info in parsed_comps.items():
        cn_lower = comp_name.lower()
        cols = comp_info["columns"]

        # Prompt Marketplace Catalog
        if "market" in cn_lower or "catalog" in cn_lower or "promptitem" in cn_lower or "prompts" in cn_lower:
            datasets[comp_name] = [
                {
                    "id": "1",
                    "title": "Ultra-Realistic Cinematic Photography",
                    "category": "Image & Art",
                    "ai_tool": "Midjourney v6",
                    "prompt_template": "Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0",
                    "description": "Studio-quality portrait and landscape generator with cinematic depth-of-field, volumetric light rays, and hyper-realistic skin textures.",
                    "sample_output": "A hyper-detailed 35mm portrait with golden-hour edge lighting, photorealistic depth, and organic textures.",
                    "price": "$4.99",
                    "author": "AlexRivera",
                    "forks_count": 1420,
                    "avg_rating": 4.95,
                    "tags": "photography, cinematic, midjourney, lighting"
                },
                {
                    "id": "2",
                    "title": "Full-Stack Architecture & TypeScript Refactor",
                    "category": "Coding & Tech",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "Act as a Principal Software Architect. Review the following {{language}} component for {{framework}}. Apply clean architecture, strict typing, error boundaries, and return production-ready code with unit tests:\\n\\n{{code_snippet}}",
                    "description": "Enterprise-grade code reviewer and refactoring engine tailored for TypeScript, React, and microservices architecture.",
                    "sample_output": "Provides clean module interfaces, Zod schema validations, and 100% test coverage patterns.",
                    "price": "$9.99",
                    "author": "ElenaDev",
                    "forks_count": 3840,
                    "avg_rating": 4.99,
                    "tags": "typescript, react, architecture, clean-code"
                },
                {
                    "id": "3",
                    "title": "Viral LinkedIn & Twitter Thread Engine",
                    "category": "Marketing & SEO",
                    "ai_tool": "ChatGPT 4o",
                    "prompt_template": "Write a viral 7-part hook thread about {{topic}} targeting {{audience}}. Use punchy short sentences, contrarian insights, data-backed frameworks, and finish with a high-converting CTA.",
                    "description": "Transforms complex business lessons, tech breakthroughs, and founder stories into viral social engagement threads.",
                    "sample_output": "Hook: 90% of SaaS founders make this pricing mistake... (7-tweet breakdown with actionable takeaways)",
                    "price": "Free",
                    "author": "MarcusGrowth",
                    "forks_count": 6120,
                    "avg_rating": 4.88,
                    "tags": "social, marketing, growth, threads, free"
                },
                {
                    "id": "4",
                    "title": "Autonomous Research Agent System Prompt",
                    "category": "AI Agents",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "You are an Autonomous Research Analyst Agent. Given the research inquiry: {{inquiry}}, perform a 3-step synthesis: 1. Core thesis, 2. Key counter-arguments, 3. Strategic executive recommendations with citations.",
                    "description": "Complete system prompt definition for deploying autonomous market analysis and multi-source research agents.",
                    "sample_output": "Comprehensive executive brief structured with methodology, market sizing, risk matrix, and strategic bets.",
                    "price": "$14.99",
                    "author": "ElenaDev",
                    "forks_count": 890,
                    "avg_rating": 4.92,
                    "tags": "agent, research, system-prompt, langchain"
                },
                {
                    "id": "5",
                    "title": "Cyberpunk Isometric Game Asset Generator",
                    "category": "Image & Art",
                    "ai_tool": "Stable Diffusion XL",
                    "prompt_template": "Isometric 3D render of {{asset_name}}, cyberpunk futuristic aesthetic, neon glow, octane render, game-ready sprite asset on dark clean background",
                    "description": "Generate game-ready 3D isometric sprites, cyber-buildings, props, and UI items with clean alpha transparencies.",
                    "sample_output": "Isometric neon-lit cyber-cafe asset with transparent background alpha ready for Unity/Unreal.",
                    "price": "$2.99",
                    "author": "AlexRivera",
                    "forks_count": 740,
                    "avg_rating": 4.85,
                    "tags": "game-dev, isometric, sdxl, 3d, cyberpunk"
                }
            ]
        # Workflows Studio
        elif "workflow" in cn_lower or "pipeline" in cn_lower:
            datasets[comp_name] = [
                {
                    "id": "1",
                    "title": "End-to-End SEO Content Pipeline",
                    "category": "Marketing & SEO",
                    "description": "Multi-step pipeline that researches search intent, generates SEO outlines, writes 2,000-word authoritative drafts, and optimizes meta tags.",
                    "ai_tools_used": "Claude 3.5 + Perplexity",
                    "step_count": 3,
                    "author": "MarcusGrowth",
                    "price": "$19.99",
                    "forks_count": 1280,
                    "stages": [
                        {"stage": 1, "title": "Search Intent & Topic Cluster Research", "output": "1. Core Intent: High-intent B2B engineering decision makers.\n2. Subtopics: Total cost of ownership, edge latency, API reliability.\n3. Recommended Angle: Enterprise deployment checklist & comparison matrix."},
                        {"stage": 2, "title": "Long-form Structural Outline", "output": "• Section 1: The Modern AI Stack Paradigm Shift\n• Section 2: Security & Architecture Tradeoffs (SOC2, HIPAA)\n• Section 3: Real-World Case Study (40% cost reduction)\n• Section 4: Implementation Blueprint & Code Sandbox\n• Section 5: Executive FAQ"},
                        {"stage": 3, "title": "Production Draft & Meta Tag Optimization", "output": "Article Title: 'The 2026 Guide to Autonomous AI Deployment'\nMeta Description: Learn how leading engineering teams cut latency by 60% with edge pipelines.\nGenerated 2,140 words. Readability: 82.4 | SEO Score: 98.6/100"}
                    ]
                },
                {
                    "id": "2",
                    "title": "API Contract to Frontend Component Suite",
                    "category": "Coding & Tech",
                    "description": "Automated pipeline that transforms OpenAPI YAML specs into TypeScript types, Mock Service Worker handlers, and shadcn/ui components.",
                    "ai_tools_used": "Claude 3.5 + GPT-4o",
                    "step_count": 3,
                    "author": "ElenaDev",
                    "price": "$24.99",
                    "forks_count": 2150,
                    "stages": [
                        {"stage": 1, "title": "OpenAPI Specification Ingestion & Validation", "output": "Validated 14 endpoints and 8 schemas. Extracted User, Prompt, Workflow, Review contracts with 0 syntax errors."},
                        {"stage": 2, "title": "TypeScript Types & MSW Handlers Generation", "output": "Generated 12 TypeScript strict interface types and 6 MSW mock request interceptors with realistic test data."},
                        {"stage": 3, "title": "shadcn/ui Component Transpilation", "output": "Compiled 5 React views with table grids, dialog modals, responsive sidebar layout, and KPI stats cards."}
                    ]
                }
            ]
        # CRM Deals
        elif "deal" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Acme Corp Cloud Migration", "value": "$85,000", "stage": "Proposal", "contact": "Sarah Connor"},
                {"id": "2", "title": "Global Logistics Fleet IoT", "value": "$142,000", "stage": "Negotiation", "contact": "Alex Rivera"},
                {"id": "3", "title": "Apex FinTech Core Engine", "value": "$64,000", "stage": "Won", "contact": "Michael Scott"},
                {"id": "4", "title": "Starlight Retail POS Sync", "value": "$129,000", "stage": "Prospecting", "contact": "Elena Vance"},
                {"id": "5", "title": "Nexus BioTech R&D", "value": "$95,000", "stage": "Qualification", "contact": "David Kim"},
            ]
        # CRM Contacts
        elif "contact" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Sarah Connor", "email": "sarah@acme.com", "company": "Acme Corp", "phone": "+1 (555) 019-2834"},
                {"id": "2", "name": "Alex Rivera", "email": "alex@globallogistics.com", "company": "Global Logistics", "phone": "+1 (555) 028-4921"},
                {"id": "3", "name": "Michael Scott", "email": "mscott@apexfin.com", "company": "Apex FinTech", "phone": "+1 (555) 037-1829"},
                {"id": "4", "name": "Elena Vance", "email": "elena@starlight.io", "company": "Starlight Retail", "phone": "+1 (555) 046-5912"},
                {"id": "5", "name": "David Kim", "email": "dkim@nexusbio.org", "company": "Nexus BioTech", "phone": "+1 (555) 055-7381"},
            ]
        # CRM Companies
        elif "compan" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Acme Corp", "industry": "Cloud Infrastructure", "size": "500+"},
                {"id": "2", "name": "Global Logistics", "industry": "Transportation", "size": "201-500"},
                {"id": "3", "name": "Apex FinTech", "industry": "Financial Services", "size": "51-200"},
                {"id": "4", "name": "Starlight Retail", "industry": "E-Commerce", "size": "51-200"},
                {"id": "5", "name": "Nexus BioTech", "industry": "Biotechnology", "size": "11-50"},
            ]
        # CRM Activities
        elif "activit" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Q3 Deal Review Call", "type": "Call", "contact": "Sarah Connor", "due_date": "2026-09-15"},
                {"id": "2", "title": "Send Contract Draft", "type": "Email", "contact": "Alex Rivera", "due_date": "2026-09-16"},
                {"id": "3", "title": "Architecture Sync Meeting", "type": "Meeting", "contact": "Michael Scott", "due_date": "2026-09-18"},
                {"id": "4", "title": "Follow up on POC feedback", "type": "Task", "contact": "Elena Vance", "due_date": "2026-09-20"},
                {"id": "5", "title": "NDA signed by Legal", "type": "Note", "contact": "David Kim", "due_date": "2026-09-14"},
            ]
        # Construction Projects
        elif "project" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Downtown Metro Station Phase 2", "budget": "$4,200,000", "status": "In Progress", "site": "Site Alpha", "start_date": "2026-01-15", "end_date": "2026-11-30"},
                {"id": "2", "name": "Harbor Bridge Retrofit", "budget": "$1,850,000", "status": "Engineering Review", "site": "East Pier", "start_date": "2026-03-01", "end_date": "2026-08-15"},
                {"id": "3", "name": "Solar Array Substation", "budget": "$920,000", "status": "Completed", "site": "North Field", "start_date": "2025-09-10", "end_date": "2026-02-28"},
                {"id": "4", "name": "Logistics Hub Warehouse B", "budget": "$2,600,000", "status": "Permit Approved", "site": "Sector 4", "start_date": "2026-06-01", "end_date": "2027-01-20"},
            ]
        # Construction Jobs
        elif "job" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Foundation Concrete Pouring", "assigned_to": "Apex Structural", "status": "Completed"},
                {"id": "2", "title": "HVAC Ventilation Ducting", "assigned_to": "Breeze Mechanical", "status": "In Progress"},
                {"id": "3", "title": "High-Voltage Relay Wiring", "assigned_to": "VoltPower Inc", "status": "Pending"},
                {"id": "4", "title": "Fire Suppression Sprinkler Testing", "assigned_to": "SafetyFirst Co", "status": "Scheduled"},
            ]
        # Construction Compliance
        elif "compliance" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "requirement": "OSHA High-Elevation Fall Arrest", "authority": "OSHA", "status": "Certified", "inspected_at": "2026-08-10"},
                {"id": "2", "requirement": "EPA Runoff Containment", "authority": "EPA", "status": "Passed", "inspected_at": "2026-07-22"},
                {"id": "3", "requirement": "Municipal Seismic Reinforcement", "authority": "City Planning", "status": "Approved", "inspected_at": "2026-09-01"},
            ]
        # Materials
        elif "material" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "High-Tensile Grade 60 Rebar", "quantity": "500", "unit": "Tons", "status": "In Stock"},
                {"id": "2", "name": "Ready-Mix Portland Concrete", "quantity": "350", "unit": "m³", "status": "Delivered"},
                {"id": "3", "name": "Structural I-Beams (W14x90)", "quantity": "120", "unit": "Units", "status": "In Transit"},
                {"id": "4", "name": "Copper Electrical Conduit", "quantity": "80", "unit": "Rolls", "status": "Low Stock"},
            ]
        # Analytics Hub / Transactions
        elif "analytic" in cn_lower or "transaction" in cn_lower or "performance" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "customer": "Acme Corp", "region": "North America", "category": "Enterprise Software", "amount": "$48,000", "status": "closed", "created_at": "2026-01-15"},
                {"id": "2", "customer": "Globex Inc", "region": "Europe", "category": "Cloud Infrastructure", "amount": "$72,000", "status": "closed", "created_at": "2026-02-10"},
                {"id": "3", "customer": "Soylent Corp", "region": "Asia Pacific", "category": "Enterprise Software", "amount": "$31,500", "status": "closed", "created_at": "2026-02-28"},
                {"id": "4", "customer": "Initech", "region": "North America", "category": "Security & Compliance", "amount": "$19,000", "status": "pending", "created_at": "2026-03-05"},
                {"id": "5", "customer": "Umbrella Corp", "region": "Europe", "category": "Cloud Infrastructure", "amount": "$64,000", "status": "closed", "created_at": "2026-03-12"},
                {"id": "6", "customer": "Hooli", "region": "North America", "category": "AI Analytics", "amount": "$89,000", "status": "closed", "created_at": "2026-04-02"},
                {"id": "7", "customer": "Massive Dynamic", "region": "Asia Pacific", "category": "AI Analytics", "amount": "$55,000", "status": "pending", "created_at": "2026-04-18"},
                {"id": "8", "customer": "Stark Industries", "region": "North America", "category": "Cloud Infrastructure", "amount": "$98,000", "status": "closed", "created_at": "2026-05-01"},
            ]
        # Item / Inventory
        elif "item" in cn_lower or "product" in cn_lower or "inventory" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Industrial Sensor Node", "price": "$120.00", "stock": "45", "category": "Sensors"},
                {"id": "2", "name": "Edge AI Gateway Controller", "price": "$450.00", "stock": "18", "category": "Controllers"},
                {"id": "3", "name": "Smart Power Relay Switch", "price": "$38.50", "stock": "92", "category": "Switches"},
                {"id": "4", "name": "High-Precision Temperature Probe", "price": "$75.00", "stock": "34", "category": "Sensors"},
                {"id": "5", "name": "Wireless Mesh Beacon", "price": "$29.99", "stock": "150", "category": "Network"},
            ]
        elif cols:
            datasets[comp_name] = [
                {"id": str(i), **{col: f"{col.replace('_', ' ').title()} #{i}" if col != "id" else str(i) for col in cols}}
                for i in range(1, 6)
            ]
        else:
            datasets[comp_name] = [
                {"id": "1", "name": f"{comp_name} Item Alpha", "value": "Operational", "status": "Active"},
                {"id": "2", "name": f"{comp_name} Item Beta", "value": "High Velocity", "status": "Active"},
                {"id": "3", "name": f"{comp_name} Item Gamma", "value": "Pending Review", "status": "In Review"},
            ]

    # Ensure default prompt datasets exist if this is PromptMarketplace
    if any("prompt" in n["label"].lower() or "market" in n["label"].lower() or "workflow" in n["label"].lower() for n in nav_items):
        if "MarketplaceCatalog" not in datasets:
            catalog_key = next((n["comp"] for n in nav_items if "market" in n["label"].lower() or "catalog" in n["label"].lower()), "MarketplaceCatalog")
            datasets[catalog_key] = [
                {
                    "id": "1",
                    "title": "Ultra-Realistic Cinematic Photography",
                    "category": "Image & Art",
                    "ai_tool": "Midjourney v6",
                    "prompt_template": "Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0",
                    "description": "Studio-quality portrait and landscape generator with cinematic depth-of-field, volumetric light rays, and hyper-realistic skin textures.",
                    "sample_output": "A hyper-detailed 35mm portrait with golden-hour edge lighting, photorealistic depth, and organic textures.",
                    "price": "$4.99",
                    "author": "AlexRivera",
                    "forks_count": 1420,
                    "avg_rating": 4.95,
                    "tags": "photography, cinematic, midjourney, lighting"
                },
                {
                    "id": "2",
                    "title": "Full-Stack Architecture & TypeScript Refactor",
                    "category": "Coding & Tech",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "Act as a Principal Software Architect. Review the following {{language}} component for {{framework}}. Apply clean architecture, strict typing, error boundaries, and return production-ready code with unit tests:\\n\\n{{code_snippet}}",
                    "description": "Enterprise-grade code reviewer and refactoring engine tailored for TypeScript, React, and microservices architecture.",
                    "sample_output": "Provides clean module interfaces, Zod schema validations, and 100% test coverage patterns.",
                    "price": "$9.99",
                    "author": "ElenaDev",
                    "forks_count": 3840,
                    "avg_rating": 4.99,
                    "tags": "typescript, react, architecture, clean-code"
                },
                {
                    "id": "3",
                    "title": "Viral LinkedIn & Twitter Thread Engine",
                    "category": "Marketing & SEO",
                    "ai_tool": "ChatGPT 4o",
                    "prompt_template": "Write a viral 7-part hook thread about {{topic}} targeting {{audience}}. Use punchy short sentences, contrarian insights, data-backed frameworks, and finish with a high-converting CTA.",
                    "description": "Transforms complex business lessons, tech breakthroughs, and founder stories into viral social engagement threads.",
                    "sample_output": "Hook: 90% of SaaS founders make this pricing mistake... (7-tweet breakdown with actionable takeaways)",
                    "price": "Free",
                    "author": "MarcusGrowth",
                    "forks_count": 6120,
                    "avg_rating": 4.88,
                    "tags": "social, marketing, growth, threads, free"
                },
                {
                    "id": "4",
                    "title": "Autonomous Research Agent System Prompt",
                    "category": "AI Agents",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "You are an Autonomous Research Analyst Agent. Given the research inquiry: {{inquiry}}, perform a 3-step synthesis: 1. Core thesis, 2. Key counter-arguments, 3. Strategic executive recommendations with citations.",
                    "description": "Complete system prompt definition for deploying autonomous market analysis and multi-source research agents.",
                    "sample_output": "Comprehensive executive brief structured with methodology, market sizing, risk matrix, and strategic bets.",
                    "price": "$14.99",
                    "author": "ElenaDev",
                    "forks_count": 890,
                    "avg_rating": 4.92,
                    "tags": "agent, research, system-prompt, langchain"
                },
                {
                    "id": "5",
                    "title": "Cyberpunk Isometric Game Asset Generator",
                    "category": "Image & Art",
                    "ai_tool": "Stable Diffusion XL",
                    "prompt_template": "Isometric 3D render of {{asset_name}}, cyberpunk futuristic aesthetic, neon glow, octane render, game-ready sprite asset on dark clean background",
                    "description": "Generate game-ready 3D isometric sprites, cyber-buildings, props, and UI items with clean alpha transparencies.",
                    "sample_output": "Isometric neon-lit cyber-cafe asset with transparent background alpha ready for Unity/Unreal.",
                    "price": "$2.99",
                    "author": "AlexRivera",
                    "forks_count": 740,
                    "avg_rating": 4.85,
                    "tags": "game-dev, isometric, sdxl, 3d, cyberpunk"
                }
            ]

    project_payload = {
        "title": app_title,
        "layout": layout_type,
        "nav_items": nav_items,
        "tabs": tabs,
        "components": parsed_comps,
        "datasets": datasets,
    }

    project_json = json.dumps(project_payload)

    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{app_title} — MCN Live App</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            background: '#0B1120',
            foreground: '#F8FAFC',
            card: '#0F172A',
            'card-foreground': '#F8FAFC',
            muted: '#1E293B',
            'muted-foreground': '#94A3B8',
            primary: {{ DEFAULT: '#0284C7', foreground: '#FFFFFF' }},
            accent: {{ DEFAULT: '#38BDF8', foreground: '#0B1120' }},
            border: '#1E293B',
            input: '#1E293B',
          }},
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{
      background-color: #0B1120;
      color: #F8FAFC;
      font-family: 'Plus Jakarta Sans', sans-serif;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    /* Custom clean scrollbars */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #0B1120; }}
    ::-webkit-scrollbar-thumb {{ background: #1E293B; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #334155; }}
    .glow-hover:hover {{ box-shadow: 0 0 25px -5px rgba(56, 189, 248, 0.25); }}
  </style>
</head>
<body class="bg-background text-foreground min-h-screen antialiased">
  <div id="root" class="min-h-screen flex flex-col"></div>

  <script>
    const _PROJECT = {project_json};
    let _datasets = JSON.parse(JSON.stringify(_PROJECT.datasets));
    
    // Determine default active view
    let _activeNav = _PROJECT.nav_items.length > 0 ? _PROJECT.nav_items[0].label : (_PROJECT.tabs.length > 0 ? _PROJECT.tabs[0] : null);
    let _searchQuery = '';
    let _catalogCategory = 'All';
    let _currentPage = 1;
    const _pageSize = 5;
    let _showEditModal = false;
    let _showCreateModal = false;
    let _showReviewModal = false;
    let _reviewItemId = null;
    let _editItem = null;
    let _editCompName = '';
    let _toastMsg = '';
    let _toastTimer = null;

    // Prompt Tester State
    let _testerTemplate = "Cinematic shot of {{{{subject}}}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0";
    let _testerSubject = "Cyberpunk Samurai in Neon Rain";
    let _testerLanguage = "TypeScript";
    let _testerAudience = "SaaS Founders & Engineers";
    let _testerInquiry = "Autonomous Edge Computing";
    let _testerOutput = "";
    let _testerInterpolated = "";
    let _testerLoading = false;
    let _testerTokens = 284;
    let _testerLatency = 340;

    // Workflows Studio State
    let _selectedWorkflow = "End-to-End SEO Content Pipeline";
    let _workflowTopic = "Autonomous Agents in Financial Services";
    let _workflowRunning = false;
    let _workflowStage = 0;
    let _workflowStageOutputs = ["", "", ""];

    // Reviews State
    let _recentReviews = [
      {{ id: 1, prompt_title: "Ultra-Realistic Cinematic Photography", reviewer: "Sarah_K", rating: 5, comment: "The lighting parameters are unbelievable! Saved me hours of prompt tweaking in Midjourney v6." }},
      {{ id: 2, prompt_title: "Full-Stack Architecture & TypeScript Refactor", reviewer: "DevLead_Tom", rating: 5, comment: "Best architecture prompt on the market. Catching edge cases in our TypeScript stack effortlessly." }},
      {{ id: 3, prompt_title: "Viral LinkedIn & Twitter Thread Engine", reviewer: "GrowthHacker99", rating: 5, comment: "Used this for 3 client threads and impressions went up 400% in 2 weeks." }}
    ];

    function showToast(msg) {{
      _toastMsg = msg;
      clearTimeout(_toastTimer);
      _toastTimer = setTimeout(() => {{
        _toastMsg = '';
        render();
      }}, 3200);
      render();
    }}

    function handleNavSwitch(navLabel) {{
      _activeNav = navLabel;
      _searchQuery = '';
      _currentPage = 1;
      render();
    }}

    function getActiveComponentInfo() {{
      if (!_activeNav) {{
        const first = Object.keys(_PROJECT.components)[0];
        return first ? {{ name: first, info: _PROJECT.components[first] }} : null;
      }}
      const found = _PROJECT.nav_items.find(n => n.label === _activeNav);
      if (found && _PROJECT.components[found.comp]) {{
        return {{ name: found.comp, info: _PROJECT.components[found.comp], label: found.label }};
      }}
      const key = Object.keys(_PROJECT.components).find(k => 
        k.toLowerCase() === _activeNav.toLowerCase() || 
        k.toLowerCase().includes(_activeNav.toLowerCase()) || 
        _activeNav.toLowerCase().includes(k.toLowerCase())
      );
      if (key) {{
        return {{ name: key, info: _PROJECT.components[key], label: _activeNav }};
      }}
      const first = Object.keys(_PROJECT.components)[0];
      return first ? {{ name: first, info: _PROJECT.components[first], label: _activeNav }} : null;
    }}

    function getNavIconSvg(label) {{
      const l = (label || '').toLowerCase();
      if (l.includes('market') || l.includes('prompt') || l.includes('catalog') || l.includes('store') || l.includes('hub')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>';
      }}
      if (l.includes('play') || l.includes('test') || l.includes('term') || l.includes('code')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>';
      }}
      if (l.includes('flow') || l.includes('pipe') || l.includes('stage') || l.includes('chain')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>';
      }}
      if (l.includes('publish') || l.includes('create') || l.includes('add') || l.includes('upload')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>';
      }}
      if (l.includes('analytic') || l.includes('metric') || l.includes('insight') || l.includes('report') || l.includes('bi')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>';
      }}
      if (l.includes('dash') || l.includes('overview') || l.includes('home')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>';
      }}
      if (l.includes('deal') || l.includes('sale') || l.includes('rev') || l.includes('trend')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>';
      }}
      if (l.includes('contact') || l.includes('user') || l.includes('people') || l.includes('lead') || l.includes('team')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>';
      }}
      if (l.includes('compan') || l.includes('account') || l.includes('org') || l.includes('build')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="2"></line><line x1="15" y1="22" x2="15" y2="2"></line><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="10" x2="20" y2="10"></line><line x1="4" y1="14" x2="20" y2="14"></line><line x1="4" y1="18" x2="20" y2="18"></line></svg>';
      }}
      if (l.includes('activit') || l.includes('task') || l.includes('event') || l.includes('calendar') || l.includes('log')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
      }}
      if (l.includes('project') || l.includes('folder')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>';
      }}
      if (l.includes('job') || l.includes('tool') || l.includes('work') || l.includes('wrench')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>';
      }}
      if (l.includes('compliance') || l.includes('safety') || l.includes('audit') || l.includes('shield')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>';
      }}
      if (l.includes('material') || l.includes('item') || l.includes('product') || l.includes('inventory') || l.includes('box')) {{
        return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"></line><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>';
      }}
      return '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle></svg>';
    }}

    function copyToClipboard(text, successMsg) {{
      navigator.clipboard.writeText(text).then(() => {{
        showToast(successMsg || 'Copied to clipboard!');
      }}).catch(() => {{
        showToast('✓ ' + (successMsg || 'Copied!'));
      }});
    }}

    function highlightVariables(text) {{
      if (!text) return 'Prompt template ready.';
      return text.split('{{').join('<span class="text-sky-400 font-semibold bg-sky-500/10 px-1 rounded">{{').split('}}').join('}}</span>');
    }}

    function handleForkPrompt(promptId) {{
      const catalogKey = Object.keys(_datasets).find(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('catalog') || k.toLowerCase().includes('prompt')) || Object.keys(_datasets)[0];
      const prompts = _datasets[catalogKey] || [];
      const item = prompts.find(p => String(p.id) === String(promptId));
      if (item) {{
        item.forks_count = (parseInt(item.forks_count) || 0) + 1;
        showToast(`🍴 Forked "${{item.title}}" to your personal workspace!`);
      }}
    }}

    function loadPromptIntoTester(promptId) {{
      const catalogKey = Object.keys(_datasets).find(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('catalog') || k.toLowerCase().includes('prompt')) || Object.keys(_datasets)[0];
      const prompts = _datasets[catalogKey] || [];
      const item = prompts.find(p => String(p.id) === String(promptId));
      if (item) {{
        _testerTemplate = item.prompt_template || item.description;
        _testerOutput = item.sample_output || "AI Output ready for execution...";
        _testerInterpolated = "";
        const testerNav = _PROJECT.nav_items.find(n => n.label.toLowerCase().includes('play') || n.label.toLowerCase().includes('test') || n.comp.toLowerCase().includes('test'));
        if (testerNav) {{
          _activeNav = testerNav.label;
        }}
        showToast(`⚡ Loaded "${{item.title}}" into Prompt Playground!`);
      }}
    }}

    function runPromptExecution() {{
      _testerLoading = true;
      render();

      let inter = _testerTemplate;
      inter = inter.split('{{subject}}').join(_testerSubject || 'Cyberpunk Samurai in Neon Rain');
      inter = inter.split('{{language}}').join(_testerLanguage || 'TypeScript');
      inter = inter.split('{{framework}}').join('React 19 + Vite');
      inter = inter.split('{{code_snippet}}').join('export function useDataPipeline(query) {{ return fetch("/api/query?q=" + query); }}');
      inter = inter.split('{{topic}}').join(_testerSubject || 'Autonomous Edge Computing');
      inter = inter.split('{{audience}}').join(_testerAudience || 'Founders & Engineers');
      inter = inter.split('{{inquiry}}').join(_testerInquiry || 'Next-gen Agent Orchestration');
      inter = inter.split('{{asset_name}}').join(_testerSubject || 'Neon Cyber Cafe');

      setTimeout(() => {{
        _testerLoading = false;
        _testerInterpolated = inter;
        _testerTokens = Math.floor(Math.random() * 200) + 250;
        _testerLatency = Math.floor(Math.random() * 150) + 280;

        if (inter.includes('Cinematic') || inter.includes('v 6.0')) {{
          _testerOutput = '[Midjourney v6 Generated Prompt & Parameter Manifest]\\nPrompt: ' + _testerInterpolated + '\\nSeed: 84920194 | Sampler: Euler_A | Steps: 30 | Aspect: 16:9\\nVolumetric Lighting: Enabled | Photorealism Score: 99.4%\\nRender Status: Success (4 variants generated)';
        }} else if (inter.includes('Architect') || inter.includes('TypeScript')) {{
          _testerOutput = '[Claude 3.5 Sonnet Principal Code Review]\\n\\n```typescript\\n// Refactored with strict typing, error boundaries, and cache layer\\nexport interface PipelineConfig {{\\n  endpoint: string;\\n  retryAttempts?: number;\\n  timeoutMs?: number;\\n}}\\n\\nexport async function executeArchitectWorkflow<T>(\\n  config: PipelineConfig\\n): Promise<{{ success: boolean; data: T; latencyMs: number }}> {{\\n  const start = performance.now();\\n  try {{\\n    const res = await fetch(config.endpoint);\\n    if (!res.ok) throw new Error("HTTP error");\\n    const data = await res.json();\\n    return {{ success: true, data, latencyMs: Math.round(performance.now() - start) }};\\n  }} catch (err) {{\\n    return {{ success: false, data: null, latencyMs: 0 }};\\n  }}\\n}}\\n```\\n\\nQuality Summary: Zero any-casts, fully typed promise return, production ready.';
        }} else if (inter.includes('viral') || inter.includes('hook')) {{
          _testerOutput = '[ChatGPT 4o Viral Social Engine]\\n\\n🧵 Thread: 7 Contrarian Lessons for ' + (_testerAudience || 'Founders') + '\\n\\n1/7: Most teams overcomplicate AI pipelines.\\nHere is how top 1% engineers cut latency by 80% with zero additional infrastructure:\\n\\n2/7: The Secret is Prompt Modularity.\\nInstead of 4,000-token monolithic system prompts, split execution into 3 atomic micro-stages.\\n\\n3/7: Dynamic Variable Interpolation.\\nParameterize your variables (' + (_testerSubject || 'AI') + ') and bind directly to database models.\\n\\n4/7: Always measure token latency.\\nKeep per-run latency under 400ms for conversational flows.\\n\\n5/7: Bookmark this workflow for your next deployment 🚀';
        }} else {{
          _testerOutput = '[Autonomous AI Agent Output for ' + (_testerInquiry || _testerSubject || 'System') + ']\\n\\n1. Executive Summary: High market opportunity identified for modern autonomous agent stacks.\\n2. Architecture Blueprint: Event-driven pub/sub with SQLite persistence layer and fast transpilation.\\n3. Risk Analysis: 0 high-severity security vulnerabilities detected in schema.\\n4. Recommended Next Steps: Deploy pilot workflow into staging cluster.';
        }}
        showToast('✓ AI Execution completed in ' + _testerLatency + 'ms');
      }}, 650);
    }}

    function runWorkflowPipeline() {{
      _workflowRunning = true;
      _workflowStage = 1;
      _workflowStageOutputs = ["", "", ""];
      render();

      setTimeout(() => {{
        _workflowStage = 2;
        _workflowStageOutputs[0] = '[Stage 1: Intent & Market Intelligence Complete]\\n• Analyzed domain requirements for: ' + _workflowTopic + '\\n• High-intent keywords identified: enterprise security, latency benchmarks, SOC2 compliance.\\n• Target Audience: VP of Engineering, Enterprise Architects.';
        render();

        setTimeout(() => {{
          _workflowStage = 3;
          _workflowStageOutputs[1] = '[Stage 2: Architecture & Content Framework Complete]\\n• Generated multi-tier system outline with 5 structured modules.\\n• Formatted API contract specs, error boundaries, and integration tests.\\n• Verified SQLite schema compatibility.';
          render();

          setTimeout(() => {{
            _workflowRunning = false;
            _workflowStage = 3;
            _workflowStageOutputs[2] = '[Stage 3: Final Delivery & Quality Scoring Complete]\\n• Full executive deliverable synthesized successfully.\\n• Readability Index: 88.4/100 | Enterprise QA Score: 98.6/100\\n• Status: Production Ready for instant deployment.';
            showToast('✓ Multi-stage AI workflow pipeline completed successfully!');
          }}, 800);
        }}, 800);
      }}, 800);
    }}

    function handlePublishPromptSubmit(e) {{
      if (e) e.preventDefault();
      const title = document.getElementById('pub-title').value.trim();
      const category = document.getElementById('pub-category').value;
      const ai_tool = document.getElementById('pub-tool').value;
      const price = parseFloat(document.getElementById('pub-price').value) || 0;
      const prompt_template = document.getElementById('pub-template').value.trim();
      const description = document.getElementById('pub-desc').value.trim();
      const sample_output = document.getElementById('pub-sample').value.trim();
      const author = document.getElementById('pub-author').value.trim() || 'CommunityCreator';
      const tags = document.getElementById('pub-tags').value.trim() || 'ai, prompt, marketplace';

      if (!title || !prompt_template) {{
        showToast('Please provide both Title and Prompt Template.');
        return;
      }}

      const catalogKey = Object.keys(_datasets).find(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('catalog') || k.toLowerCase().includes('prompt')) || 'MarketplaceCatalog';
      if (!_datasets[catalogKey]) _datasets[catalogKey] = [];

      const newPrompt = {{
        id: String(Date.now()).slice(-4),
        title,
        category,
        ai_tool,
        prompt_template,
        description: description || 'High-performance prompt crafted for ' + ai_tool,
        sample_output: sample_output || 'Sample AI completion ready for execution.',
        price: price > 0 ? ('$' + price.toFixed(2)) : 'Free',
        author,
        forks_count: 1,
        avg_rating: 5.0,
        tags
      }};

      _datasets[catalogKey].unshift(newPrompt);
      showToast(`🎉 "${{title}}" published to Global Marketplace!`);

      // Switch to marketplace view
      const marketNav = _PROJECT.nav_items.find(n => n.label.toLowerCase().includes('market') || n.label.toLowerCase().includes('catalog'));
      if (marketNav) {{
        _activeNav = marketNav.label;
      }}
      render();
    }}

    function openReviewModal(itemId) {{
      _reviewItemId = itemId;
      _showReviewModal = true;
      render();
    }}

    function submitReview() {{
      const reviewer = document.getElementById('rev-author').value.trim() || 'CommunityUser';
      const rating = parseInt(document.getElementById('rev-rating').value) || 5;
      const comment = document.getElementById('rev-comment').value.trim() || 'Excellent prompt, works flawlessly in production!';

      const catalogKey = Object.keys(_datasets).find(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('catalog') || k.toLowerCase().includes('prompt')) || Object.keys(_datasets)[0];
      const prompts = _datasets[catalogKey] || [];
      const item = prompts.find(p => String(p.id) === String(_reviewItemId));

      _recentReviews.unshift({{
        id: Date.now(),
        prompt_title: item ? item.title : 'Marketplace Prompt',
        reviewer,
        rating,
        comment
      }});

      _showReviewModal = false;
      _reviewItemId = null;
      showToast('⭐ Thank you for your review!');
    }}

    function handleCatalogSearch(q) {{
      _searchQuery = q;
      render();
    }}

    function setCatalogCategory(cat) {{
      _catalogCategory = cat;
      render();
    }}

    function render() {{
      const root = document.getElementById('root');
      if (!root) return;

      const toastHtml = _toastMsg ? `
        <div class="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 border border-sky-500/50 shadow-2xl text-xs font-semibold text-sky-400 animate-bounce">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>${{_toastMsg}}</span>
        </div>
      ` : '';

      const activeObj = getActiveComponentInfo();
      const activeCompName = activeObj ? activeObj.name : '';
      const activeLabel = activeObj ? (activeObj.label || activeCompName) : _PROJECT.title;
      const actLower = activeLabel.toLowerCase() + ' ' + activeCompName.toLowerCase();

      let mainContentHtml = '';

      const isPromptMarketplace = _PROJECT.title.toLowerCase().includes('prompt') || _PROJECT.title.toLowerCase().includes('marketplace') || Object.keys(_PROJECT.components).some(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('promptitem'));
      const isAnalyticsHub = _PROJECT.title.toLowerCase().includes('executive analytics') || _PROJECT.title.toLowerCase().includes('bi hub') || _PROJECT.title.toLowerCase().includes('businessanalytics') || _PROJECT.title.toLowerCase().includes('analytics') || activeCompName === 'AnalyticsDashboard' || actLower.includes('executive overview');
      const isItemManager = _PROJECT.title.toLowerCase().includes('inventory') || _PROJECT.title.toLowerCase().includes('item') || activeCompName === 'ItemTable' || activeCompName === 'ItemForm' || activeCompName === 'ItemList' || actLower.includes('item') || actLower.includes('inventory');
      const isConstruction = _PROJECT.title.toLowerCase().includes('construct') || activeCompName.toLowerCase().includes('project') || activeCompName.toLowerCase().includes('job') || activeCompName.toLowerCase().includes('compliance') || activeCompName.toLowerCase().includes('material');

      // ── 1. PROMPT MARKETPLACE VIEWS ───────────────────────────────────────
      if (isPromptMarketplace && (actLower.includes('market') || actLower.includes('catalog') || actLower.includes('discover') || activeCompName === 'MarketplaceCatalog')) {{
        const catalogKey = Object.keys(_datasets).find(k => k.toLowerCase().includes('market') || k.toLowerCase().includes('catalog') || k.toLowerCase().includes('prompt')) || activeCompName;
        const allPrompts = _datasets[catalogKey] || [];

        const categories = ["All", "Image & Art", "Coding & Tech", "Marketing & SEO", "AI Agents"];

        const filtered = allPrompts.filter(p => {{
          const matchCat = (_catalogCategory === 'All') || (p.category === _catalogCategory);
          const q = _searchQuery.toLowerCase();
          const matchSearch = !q || (
            (p.title && p.title.toLowerCase().includes(q)) ||
            (p.description && p.description.toLowerCase().includes(q)) ||
            (p.ai_tool && p.ai_tool.toLowerCase().includes(q)) ||
            (p.tags && p.tags.toLowerCase().includes(q))
          );
          return matchCat && matchSearch;
        }});

        mainContentHtml = `
          <div class="space-y-6">
            <!-- Header Hero Banner -->
            <div class="rounded-2xl border border-border/80 bg-gradient-to-r from-slate-900 via-slate-900/90 to-sky-950/40 p-6 md:p-8 shadow-xl relative overflow-hidden">
              <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none"></div>
              <div class="relative z-10 max-w-2xl space-y-3">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span> Prompt &amp; Workflow Marketplace
                </div>
                <h2 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Discover, Test &amp; Fork Elite AI Prompts</h2>
                <p class="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Verified system prompts, multi-stage pipelines, and fine-tuned templates for Midjourney v6, Claude 3.5 Sonnet, ChatGPT 4o, and Cursor.
                </p>
              </div>

              <!-- Search & Filter Controls -->
              <div class="mt-6 pt-6 border-t border-border/60 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div class="relative w-full md:max-w-md">
                  <svg class="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                  <input
                    type="text"
                    placeholder="Search by keywords, tags, or AI tool…"
                    value="${{_searchQuery}}"
                    oninput="handleCatalogSearch(this.value)"
                    class="w-full rounded-xl border border-border bg-slate-950/80 pl-10 pr-4 py-2 text-xs text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
                <div class="flex flex-wrap items-center gap-1.5 w-full md:w-auto">
                  ${{categories.map(cat => `
                    <button
                      onclick="setCatalogCategory('${{cat}}')"
                      class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${{
                        _catalogCategory === cat
                          ? 'bg-primary text-white shadow-md shadow-primary/30'
                          : 'bg-slate-900/80 text-slate-300 hover:text-white hover:bg-slate-800 border border-border/80'
                      }}"
                    >${{cat}}</button>
                  `).join('')}}
                </div>
              </div>
            </div>

            <!-- Prompts Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              ${{filtered.length > 0 ? filtered.map(p => {{
                const toolLower = (p.ai_tool || '').toLowerCase();
                let toolBadge = 'bg-sky-500/15 text-sky-300 border-sky-500/30';
                if (toolLower.includes('midjourney')) toolBadge = 'bg-purple-500/15 text-purple-300 border-purple-500/30';
                else if (toolLower.includes('claude')) toolBadge = 'bg-amber-500/15 text-amber-300 border-amber-500/30';
                else if (toolLower.includes('gpt') || toolLower.includes('chatgpt')) toolBadge = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
                else if (toolLower.includes('sdxl') || toolLower.includes('stable')) toolBadge = 'bg-pink-500/15 text-pink-300 border-pink-500/30';

                const isFree = String(p.price).toLowerCase() === 'free' || parseFloat(String(p.price).replace(/[^0-9.]/g, '')) === 0;

                return `
                  <div class="rounded-2xl border border-border/80 bg-card p-5 shadow-sm hover:border-sky-500/50 transition-all flex flex-col justify-between glow-hover">
                    <div class="space-y-3">
                      <!-- Top Badges -->
                      <div class="flex items-center justify-between gap-2">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${{toolBadge}}">
                          ${{p.ai_tool || 'AI Tool'}}
                        </span>
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${{
                          isFree ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-sky-500/10 text-sky-400 border-sky-500/30 font-mono'
                        }}">
                          ${{p.price || 'Free'}}
                        </span>
                      </div>

                      <!-- Title & Author -->
                      <div>
                        <h3 class="text-base font-bold text-white tracking-tight leading-snug">${{p.title}}</h3>
                        <div class="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                          <span class="font-medium text-slate-300">@${{p.author || 'creator'}}</span>
                          <span>•</span>
                          <span class="text-amber-400 font-semibold flex items-center gap-0.5">★ ${{p.avg_rating || 5.0}}</span>
                          <span>•</span>
                          <span class="text-sky-400 font-medium">${{p.forks_count || 0}} forks</span>
                        </div>
                      </div>

                      <!-- Description -->
                      <p class="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                        ${{p.description || ''}}
                      </p>

                      <!-- Prompt Template Snippet Box -->
                      <div class="p-3 rounded-xl bg-slate-950/80 border border-border/80 text-[11px] font-mono text-slate-300 line-clamp-3 relative">
                        ${{highlightVariables(p.prompt_template)}}
                      </div>

                      <!-- Tags -->
                      <div class="flex flex-wrap gap-1.5 pt-1">
                        ${{(p.tags ? p.tags.split(',') : ['ai', 'prompt']).map(t => `
                          <span class="px-2 py-0.5 rounded-md bg-slate-900 text-[10px] font-medium text-slate-400 border border-border/60">#${{t.trim()}}</span>
                        `).join('')}}
                      </div>
                    </div>

                    <!-- Card Actions -->
                    <div class="pt-4 mt-4 border-t border-border/60 flex items-center justify-between gap-2">
                      <button
                        onclick="loadPromptIntoTester('${{p.id}}')"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        Test Live
                      </button>
                      <button
                        onclick="handleForkPrompt('${{p.id}}')"
                        class="px-2.5 py-2 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-border hover:border-sky-500/40 transition-all cursor-pointer flex items-center gap-1"
                        title="Fork prompt"
                      >
                        <span>🍴</span>
                        <span>${{p.forks_count || 0}}</span>
                      </button>
                      <button
                        onclick="copyToClipboard('${{encodeURIComponent(p.prompt_template || '')}}'.replace(/%0A/g, '\\n'), 'Prompt template copied!')"
                        class="p-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-border transition-all cursor-pointer"
                        title="Copy prompt text"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                      </button>
                      <button
                        onclick="openReviewModal('${{p.id}}')"
                        class="p-2 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-amber-400 border border-border transition-all cursor-pointer"
                        title="Write Review"
                      >
                        ★
                      </button>
                    </div>
                  </div>
                `;
              }}).join('') : `
                <div class="col-span-full py-16 text-center rounded-2xl border border-dashed border-border bg-card p-8">
                  <p class="text-sm font-semibold text-slate-300">No prompts found matching "${{_searchQuery}}" in ${{_catalogCategory}}</p>
                  <button onclick="setCatalogCategory('All'); handleCatalogSearch('');" class="mt-3 text-xs text-sky-400 hover:underline">Reset Filters</button>
                </div>
              `}}
            </div>
          </div>
        `;
      }}

      // ── 2. PROMPT PLAYGROUND / TESTER VIEW ────────────────────────────────
      else if (isPromptMarketplace && (actLower.includes('play') || actLower.includes('test') || actLower.includes('sandbox') || activeCompName === 'PromptTester')) {{
        mainContentHtml = `
          <div class="space-y-6">
            <!-- Playground Header -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-lg font-bold text-white tracking-tight">Live Prompt Playground</h2>
                  <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">AI Simulator Ready</span>
                </div>
                <p class="text-xs text-muted-foreground mt-1">Test prompt templates with dynamic variable placeholders ({{{{subject}}}}, {{{{language}}}}, {{{{topic}}}})</p>
              </div>

              <!-- Quick Presets -->
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-xs text-muted-foreground font-semibold">Load Preset:</span>
                <button onclick="loadPromptIntoTester('1')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Midjourney Cinematic</button>
                <button onclick="loadPromptIntoTester('2')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Claude TypeScript</button>
                <button onclick="loadPromptIntoTester('3')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Viral Social Thread</button>
                <button onclick="loadPromptIntoTester('4')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Research Agent</button>
              </div>
            </div>

            <!-- Split Playground Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <!-- Left: Inputs & Template Form -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">Prompt Template &amp; Variables</h3>
                  <span class="text-xs text-sky-400 font-mono">Syntax: {{{{var}}}}</span>
                </div>

                <div class="space-y-2">
                  <label class="text-xs font-semibold text-slate-300">Prompt Template</label>
                  <textarea
                    id="tester-template-input"
                    rows="4"
                    oninput="_testerTemplate = this.value"
                    class="w-full rounded-lg border border-border bg-slate-950 p-3 text-xs text-slate-200 font-mono focus:outline-none focus:ring-2 focus:ring-primary leading-relaxed"
                  >${{_testerTemplate}}</textarea>
                </div>

                <!-- Dynamic Variables Form -->
                <div class="space-y-3 pt-2">
                  <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Dynamic Interpolator Variables</p>
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div class="space-y-1">
                      <label class="text-[11px] font-semibold text-slate-300">Variable: {{{{subject}}}}</label>
                      <input
                        type="text"
                        value="${{_testerSubject}}"
                        oninput="_testerSubject = this.value"
                        class="w-full rounded-lg border border-border bg-slate-950 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div class="space-y-1">
                      <label class="text-[11px] font-semibold text-slate-300">Variable: {{{{language}}}} / Framework</label>
                      <input
                        type="text"
                        value="${{_testerLanguage}}"
                        oninput="_testerLanguage = this.value"
                        class="w-full rounded-lg border border-border bg-slate-950 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div class="space-y-1">
                      <label class="text-[11px] font-semibold text-slate-300">Variable: {{{{audience}}}}</label>
                      <input
                        type="text"
                        value="${{_testerAudience}}"
                        oninput="_testerAudience = this.value"
                        class="w-full rounded-lg border border-border bg-slate-950 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div class="space-y-1">
                      <label class="text-[11px] font-semibold text-slate-300">Variable: {{{{inquiry}}}}</label>
                      <input
                        type="text"
                        value="${{_testerInquiry}}"
                        oninput="_testerInquiry = this.value"
                        class="w-full rounded-lg border border-border bg-slate-950 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  </div>
                </div>

                <div class="pt-4 border-t border-border/60">
                  <button
                    onclick="runPromptExecution()"
                    ${{_testerLoading ? 'disabled' : ''}}
                    class="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer disabled:opacity-50"
                  >
                    ${{_testerLoading ? `
                      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
                      Simulating AI Execution…
                    ` : `
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                      Execute Prompt with AI Simulator
                    `}}
                  </button>
                </div>
              </div>

              <!-- Right: Execution Telemetry & Result Output -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm flex flex-col justify-between space-y-4">
                <div class="space-y-4">
                  <div class="flex items-center justify-between pb-3 border-b border-border/60">
                    <h3 class="text-sm font-bold text-white">Execution Telemetry &amp; AI Output</h3>
                    <span class="text-xs text-emerald-400 font-semibold font-mono">STATUS: 200 OK</span>
                  </div>

                  <!-- Telemetry Stats -->
                  <div class="grid grid-cols-3 gap-3">
                    <div class="p-3 rounded-xl bg-slate-900/80 border border-border/60">
                      <p class="text-[10px] font-bold text-muted-foreground uppercase">Tokens</p>
                      <p class="text-lg font-bold text-white font-mono mt-0.5">${{_testerTokens}} tok</p>
                    </div>
                    <div class="p-3 rounded-xl bg-slate-900/80 border border-border/60">
                      <p class="text-[10px] font-bold text-muted-foreground uppercase">Latency</p>
                      <p class="text-lg font-bold text-sky-400 font-mono mt-0.5">${{_testerLatency}} ms</p>
                    </div>
                    <div class="p-3 rounded-xl bg-slate-900/80 border border-border/60">
                      <p class="text-[10px] font-bold text-muted-foreground uppercase">Model Target</p>
                      <p class="text-xs font-bold text-emerald-400 mt-1 truncate">Claude 3.5 Sonnet</p>
                    </div>
                  </div>

                  <!-- Output Area -->
                  <div class="space-y-2">
                    <div class="flex items-center justify-between text-xs">
                      <span class="font-semibold text-slate-300">Generated Output:</span>
                      <button
                        onclick="copyToClipboard(document.getElementById('tester-output-box').innerText, 'Response copied!')"
                        class="text-sky-400 hover:underline text-[11px]"
                      >Copy Response</button>
                    </div>
                    <div
                      id="tester-output-box"
                      class="p-4 rounded-xl bg-slate-950 border border-border text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed min-h-[180px] max-h-[280px] overflow-y-auto"
                    >${{_testerOutput || "Click 'Execute Prompt with AI Simulator' to run prompt..."}}</div>
                  </div>
                </div>

                <div class="pt-3 border-t border-border/60 text-[11px] text-muted-foreground flex items-center justify-between">
                  <span>Interpolated parameters verified</span>
                  <span class="text-emerald-400 font-mono">100% Contract Match</span>
                </div>
              </div>
            </div>
          </div>
        `;
      }}

      // ── 3. WORKFLOWS STUDIO VIEW ──────────────────────────────────────────
      else if (isPromptMarketplace && (actLower.includes('workflow') || actLower.includes('pipe') || activeCompName === 'WorkflowsStudio')) {{
        mainContentHtml = `
          <div class="space-y-6">
            <!-- Header -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/60">
                <div>
                  <h2 class="text-lg font-bold text-white">Multi-Stage AI Workflow Orchestrator</h2>
                  <p class="text-xs text-muted-foreground mt-1">Execute sequential, chained prompts where stage outputs feed downstream AI models</p>
                </div>
                <button
                  onclick="runWorkflowPipeline()"
                  ${{_workflowRunning ? 'disabled' : ''}}
                  class="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer disabled:opacity-50"
                >
                  ${{_workflowRunning ? `
                    <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
                    Running Pipeline Stages…
                  ` : `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Run Multi-Stage Workflow
                  `}}
                </button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-1.5">
                  <label class="text-xs font-semibold text-slate-300">Select Workflow Pipeline</label>
                  <select
                    id="wf-select"
                    onchange="_selectedWorkflow = this.value"
                    class="w-full rounded-lg border border-border bg-slate-950 px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="End-to-End SEO Content Pipeline">End-to-End SEO Content Pipeline (3 Stages)</option>
                    <option value="API Contract to Frontend Component Suite">API Contract to Frontend Component Suite (3 Stages)</option>
                    <option value="Autonomous Market Research &amp; Synthesis">Autonomous Market Research &amp; Synthesis (3 Stages)</option>
                  </select>
                </div>

                <div class="space-y-1.5">
                  <label class="text-xs font-semibold text-slate-300">Execution Subject / Topic</label>
                  <input
                    type="text"
                    value="${{_workflowTopic}}"
                    oninput="_workflowTopic = this.value"
                    class="w-full rounded-lg border border-border bg-slate-950 px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
            </div>

            <!-- 3-Stage Visual Progress Timeline -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <!-- Stage 1 -->
              <div class="rounded-xl border ${{
                _workflowStage >= 1 ? 'border-sky-500/60 bg-slate-900/90' : 'border-border/80 bg-card'
              }} p-5 shadow-sm space-y-3 transition-all">
                <div class="flex items-center justify-between">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${{
                    _workflowStage >= 1 ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'bg-slate-800 text-slate-400'
                  }}">STAGE 1</span>
                  <span class="text-xs font-mono text-muted-foreground">${{_workflowStage >= 1 ? '✓ Complete' : 'Pending'}}</span>
                </div>
                <h3 class="text-sm font-bold text-white">Intent &amp; Market Intelligence</h3>
                <p class="text-[11px] text-muted-foreground">Scans domain taxonomy, high-value keywords, and customer intent clusters.</p>
                <div class="p-3 rounded-lg bg-slate-950 border border-border text-[11px] font-mono text-slate-300 min-h-[140px] whitespace-pre-wrap">
                  ${{_workflowStageOutputs[0] || "Waiting for pipeline trigger..."}}
                </div>
              </div>

              <!-- Stage 2 -->
              <div class="rounded-xl border ${{
                _workflowStage >= 2 ? 'border-sky-500/60 bg-slate-900/90' : 'border-border/80 bg-card'
              }} p-5 shadow-sm space-y-3 transition-all">
                <div class="flex items-center justify-between">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${{
                    _workflowStage >= 2 ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'bg-slate-800 text-slate-400'
                  }}">STAGE 2</span>
                  <span class="text-xs font-mono text-muted-foreground">${{_workflowStage >= 2 ? '✓ Complete' : 'Pending'}}</span>
                </div>
                <h3 class="text-sm font-bold text-white">Architecture &amp; Framework Construction</h3>
                <p class="text-[11px] text-muted-foreground">Synthesizes Stage 1 findings into production outline and schemas.</p>
                <div class="p-3 rounded-lg bg-slate-950 border border-border text-[11px] font-mono text-slate-300 min-h-[140px] whitespace-pre-wrap">
                  ${{_workflowStageOutputs[1] || "Waiting for Stage 1..."}}
                </div>
              </div>

              <!-- Stage 3 -->
              <div class="rounded-xl border ${{
                _workflowStage >= 3 ? 'border-emerald-500/60 bg-slate-900/90' : 'border-border/80 bg-card'
              }} p-5 shadow-sm space-y-3 transition-all">
                <div class="flex items-center justify-between">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${{
                    _workflowStage >= 3 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'
                  }}">STAGE 3</span>
                  <span class="text-xs font-mono text-emerald-400">${{_workflowStage >= 3 ? '★ Score: 98.6' : 'Pending'}}</span>
                </div>
                <h3 class="text-sm font-bold text-white">Final Delivery &amp; Quality Scoring</h3>
                <p class="text-[11px] text-muted-foreground">Generates executive artifact with automated quality checks.</p>
                <div class="p-3 rounded-lg bg-slate-950 border border-border text-[11px] font-mono text-slate-300 min-h-[140px] whitespace-pre-wrap">
                  ${{_workflowStageOutputs[2] || "Waiting for Stage 2..."}}
                </div>
              </div>
            </div>
          </div>
        `;
      }}

      // ── 4. PUBLISH STUDIO VIEW ────────────────────────────────────────────
      else if (isPromptMarketplace && (actLower.includes('publish') || actLower.includes('submit') || activeCompName === 'PublishStudio')) {{
        mainContentHtml = `
          <div class="space-y-6 max-w-4xl mx-auto">
            <div class="rounded-2xl border border-border/80 bg-card p-6 md:p-8 shadow-xl space-y-6">
              <div class="pb-4 border-b border-border/60">
                <h2 class="text-xl font-bold text-white tracking-tight">Publish Prompt to Global Marketplace</h2>
                <p class="text-xs text-muted-foreground mt-1">Monetize your engineered prompts, share community workflows, and build creator reputation.</p>
              </div>

              <form onsubmit="handlePublishPromptSubmit(event)" class="space-y-5">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Prompt Title *</label>
                    <input
                      id="pub-title"
                      type="text"
                      placeholder="e.g. Autonomous SRE Incident Responder"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      required
                    />
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Category *</label>
                    <select
                      id="pub-category"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="Coding & Tech">Coding &amp; Tech</option>
                      <option value="Image & Art">Image &amp; Art</option>
                      <option value="Marketing & SEO">Marketing &amp; SEO</option>
                      <option value="AI Agents">AI Agents</option>
                    </select>
                  </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Target AI Model *</label>
                    <select
                      id="pub-tool"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="Claude 3.5 Sonnet">Claude 3.5 Sonnet</option>
                      <option value="Midjourney v6">Midjourney v6</option>
                      <option value="ChatGPT 4o">ChatGPT 4o</option>
                      <option value="Stable Diffusion XL">Stable Diffusion XL</option>
                      <option value="Cursor AI">Cursor AI</option>
                    </select>
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Price in USD ($0 for Free Community)</label>
                    <input
                      id="pub-price"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>

                <div class="space-y-1.5">
                  <div class="flex items-center justify-between">
                    <label class="text-xs font-semibold text-slate-300">Prompt Template (Use {{{{variable}}}} for inputs) *</label>
                    <div class="flex items-center gap-1.5 text-[11px] text-sky-400">
                      <span>Insert:</span>
                      <button type="button" onclick="document.getElementById('pub-template').value += ' {{{{subject}}}}'" class="hover:underline">{{{{subject}}}}</button>
                      <button type="button" onclick="document.getElementById('pub-template').value += ' {{{{language}}}}'" class="hover:underline">{{{{language}}}}</button>
                      <button type="button" onclick="document.getElementById('pub-template').value += ' {{{{topic}}}}'" class="hover:underline">{{{{topic}}}}</button>
                    </div>
                  </div>
                  <textarea
                    id="pub-template"
                    rows="4"
                    placeholder="Act as a senior DevOps engineer. Analyze the following {{{{incident_log}}}} and return a step-by-step remediation plan for {{{{infrastructure}}}}..."
                    class="w-full rounded-lg border border-border bg-slate-950 p-3 text-xs text-slate-200 font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                  ></textarea>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Description</label>
                    <textarea
                      id="pub-desc"
                      rows="2"
                      placeholder="Explain what makes this prompt unique and effective..."
                      class="w-full rounded-lg border border-border bg-slate-950 p-3 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary"
                    ></textarea>
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Sample Generated Output</label>
                    <textarea
                      id="pub-sample"
                      rows="2"
                      placeholder="Paste high-grade sample response from AI..."
                      class="w-full rounded-lg border border-border bg-slate-950 p-3 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary"
                    ></textarea>
                  </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Creator Handle</label>
                    <input
                      id="pub-author"
                      type="text"
                      placeholder="YourUsername"
                      value="AlexRivera"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Tags (comma separated)</label>
                    <input
                      id="pub-tags"
                      type="text"
                      placeholder="devops, sre, k8s, claude"
                      class="w-full rounded-lg border border-border bg-slate-950 px-3.5 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>

                <div class="pt-4 border-t border-border/60 flex items-center justify-end gap-3">
                  <button
                    type="submit"
                    class="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-bold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    Publish to Global Marketplace
                  </button>
                </div>
              </form>
            </div>
          </div>
        `;
      }}

      // ── 5. CREATOR & MARKETPLACE ANALYTICS VIEW (for Prompt Marketplace) ──
      else if (isPromptMarketplace && (actLower.includes('creator') || actLower.includes('analytic') || actLower.includes('insight') || activeCompName === 'CreatorAnalytics')) {{
        const reportMdText = `| Category | Sum Forks Count | Avg Rating | Share % |
| --- | --- | --- | --- |
| Marketing & SEO | 6,120 | 4.88 | 47.0% |
| Coding & Tech | 3,840 | 4.99 | 29.5% |
| Image & Art | 2,160 | 4.90 | 16.6% |
| AI Agents | 890 | 4.92 | 6.8% |`;

        mainContentHtml = `
          <div class="space-y-6">
            <!-- Executive KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Total Prompts</p>
                <p class="text-2xl font-extrabold text-white mt-1">5</p>
                <p class="text-xs text-emerald-400 mt-1">↑ +2 this week</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Community Forks</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">13,490</p>
                <p class="text-xs text-emerald-400 mt-1">↑ +18.4% growth</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Gross Platform Volume</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">$68,450.00</p>
                <p class="text-xs text-emerald-400 mt-1">↑ +24.1% MoM</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Average Rating</p>
                <p class="text-2xl font-extrabold text-amber-400 mt-1">4.93 ★</p>
                <p class="text-xs text-muted-foreground mt-1">From 482 verified reviews</p>
              </div>
            </div>

            <!-- Distribution Charts & AI Breakdown -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <!-- Category Distribution Bars -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">Forks by Category (Pareto Share)</h3>
                  <span class="text-xs text-muted-foreground font-mono">use analytics</span>
                </div>
                <div class="space-y-3.5 py-2">
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Marketing &amp; SEO</span>
                      <span class="text-sky-400 font-mono">6,120 forks (47.0%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-sky-500 to-emerald-400 rounded-full" style="width: 47%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Coding &amp; Tech</span>
                      <span class="text-sky-400 font-mono">3,840 forks (29.5%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-sky-500 to-indigo-400 rounded-full" style="width: 29.5%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Image &amp; Art</span>
                      <span class="text-sky-400 font-mono">2,160 forks (16.6%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-purple-500 to-pink-400 rounded-full" style="width: 16.6%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">AI Agents &amp; Logic</span>
                      <span class="text-sky-400 font-mono">890 forks (6.8%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full" style="width: 6.8%"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- AI Model Breakdown -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">AI Model Market Share</h3>
                  <span class="text-xs text-emerald-400 font-mono">Live Volume</span>
                </div>
                <div class="space-y-3.5 py-2">
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">ChatGPT 4o</span>
                      <span class="text-emerald-400 font-mono">47.0%</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-emerald-400 rounded-full" style="width: 47%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Claude 3.5 Sonnet</span>
                      <span class="text-amber-400 font-mono">36.3%</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-amber-400 rounded-full" style="width: 36.3%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Midjourney v6</span>
                      <span class="text-purple-400 font-mono">16.6%</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-purple-400 rounded-full" style="width: 16.6%"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Community Reviews Table -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
              <div class="flex items-center justify-between pb-3 border-b border-border/60">
                <h3 class="text-sm font-bold text-white">Community Reviews &amp; Feedback</h3>
                <span class="text-xs text-muted-foreground">${{_recentReviews.length}} recent verified ratings</span>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                  <thead class="text-muted-foreground uppercase font-semibold border-b border-border/60">
                    <tr>
                      <th class="py-2.5">Prompt Title</th>
                      <th class="py-2.5">Reviewer</th>
                      <th class="py-2.5">Rating</th>
                      <th class="py-2.5">Comment</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/40 text-slate-300">
                    ${{_recentReviews.map(r => `
                      <tr class="hover:bg-slate-800/30">
                        <td class="py-3 font-semibold text-white">${{r.prompt_title}}</td>
                        <td class="py-3 text-sky-400">@${{r.reviewer}}</td>
                        <td class="py-3 text-amber-400 font-bold">${{'★'.repeat(r.rating || 5)}}</td>
                        <td class="py-3 text-slate-300 italic">"${{r.comment}}"</td>
                      </tr>
                    `).join('')}}
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Formatted Markdown Report Export -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-3">
              <div class="flex items-center justify-between pb-3 border-b border-border/60">
                <h3 class="text-sm font-bold text-white">Executive Markdown Report (export_report)</h3>
                <button
                  onclick="copyToClipboard('${{encodeURIComponent(reportMdText)}}'.replace(/%0A/g, '\\n'), 'Markdown Report Copied!')"
                  class="text-xs text-sky-400 hover:underline flex items-center gap-1 font-semibold"
                >📋 Copy Markdown</button>
              </div>
              <pre class="p-4 rounded-xl bg-slate-950 border border-border text-xs font-mono text-slate-300 overflow-x-auto">${{reportMdText}}</pre>
            </div>
          </div>
        `;
      }}

      // ── 6. EXECUTIVE ANALYTICS & BI HUB (analytics_hub template) ───────────
      else if (isAnalyticsHub) {{
        const transactions = _datasets['AnalyticsDashboard'] || _datasets['Transactions'] || [
          {{ id: "1", customer: "Acme Corp", region: "North America", category: "Enterprise Software", amount: "$48,000", status: "closed", created_at: "2026-01-15" }},
          {{ id: "2", customer: "Globex Inc", region: "Europe", category: "Cloud Infrastructure", amount: "$72,000", status: "closed", created_at: "2026-02-10" }},
          {{ id: "3", customer: "Soylent Corp", region: "Asia Pacific", category: "Enterprise Software", amount: "$31,500", status: "closed", created_at: "2026-02-28" }},
          {{ id: "4", customer: "Initech", region: "North America", category: "Security & Compliance", amount: "$19,000", status: "pending", created_at: "2026-03-05" }},
          {{ id: "5", customer: "Umbrella Corp", region: "Europe", category: "Cloud Infrastructure", amount: "$64,000", status: "closed", created_at: "2026-03-12" }},
          {{ id: "6", customer: "Hooli", region: "North America", category: "AI Analytics", amount: "$89,000", status: "closed", created_at: "2026-04-02" }},
          {{ id: "7", customer: "Massive Dynamic", region: "Asia Pacific", category: "AI Analytics", amount: "$55,000", status: "pending", created_at: "2026-04-18" }},
          {{ id: "8", customer: "Stark Industries", region: "North America", category: "Cloud Infrastructure", amount: "$98,000", status: "closed", created_at: "2026-05-01" }},
        ];

        const analyticsReportMd = `# Executive Performance & Revenue BI Report
Generated by MCN 'use analytics' Engine (SQLite Relational Persistence)

## Executive Summary
- **Gross Revenue**: $476,500.00
- **Total Transactions**: 8 Deals (6 Closed, 2 Pending)
- **Average Deal Size**: $59,562.50
- **Closed Win Rate**: 75.0%

## Revenue by Category (Pareto Analysis)
| Category | Sum Amount | Avg Deal | Closed Deals | Share % |
| --- | --- | --- | --- | --- |
| Cloud Infrastructure | $234,000 | $78,000 | 3 | 49.1% |
| AI Analytics | $144,000 | $72,000 | 1 | 30.2% |
| Enterprise Software | $79,500 | $39,750 | 2 | 16.7% |
| Security & Compliance | $19,000 | $19,000 | 0 | 4.0% |

## Regional Performance Matrix
- **North America**: $254,000 (53.3% Market Share)
- **Europe**: $136,000 (28.5% Market Share)
- **Asia Pacific**: $86,500 (18.2% Market Share)`;

        mainContentHtml = `
          <div class="space-y-6">
            <!-- Top Hero Banner -->
            <div class="rounded-2xl border border-border/80 bg-gradient-to-r from-slate-900 via-slate-900/90 to-sky-950/40 p-6 md:p-8 shadow-xl relative overflow-hidden">
              <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none"></div>
              <div class="relative z-10 max-w-3xl space-y-3">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> MCN 'use analytics' Engine Online
                </div>
                <h2 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Executive Analytics &amp; Performance BI Hub</h2>
                <p class="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Real-time multi-dimensional SQLite intelligence: revenue velocity, 2D cross-tabulation pivot matrix, category Pareto distributions, and automated executive reports.
                </p>
              </div>
            </div>

            <!-- Executive KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm hover:border-sky-500/40 transition-all">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Gross Revenue</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">$476,500</p>
                <p class="text-xs text-emerald-400 mt-1 flex items-center gap-1 font-medium">
                  <span>↑ +24.8% YoY</span>
                  <span class="text-muted-foreground">(Q1-Q2 2026)</span>
                </p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm hover:border-sky-500/40 transition-all">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Transactions</p>
                <p class="text-2xl font-extrabold text-white mt-1">8 Deals</p>
                <p class="text-xs text-sky-400 mt-1 flex items-center gap-1 font-medium">
                  <span>6 Closed • 2 Pending</span>
                </p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm hover:border-sky-500/40 transition-all">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Avg Deal Size</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">$59,562</p>
                <p class="text-xs text-emerald-400 mt-1 flex items-center gap-1 font-medium">
                  <span>↑ +12.5% vs baseline</span>
                </p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm hover:border-sky-500/40 transition-all">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Win Rate</p>
                <p class="text-2xl font-extrabold text-emerald-400 mt-1">75.0%</p>
                <p class="text-xs text-muted-foreground mt-1">Target: 70.0% (+5.0% spread)</p>
              </div>
            </div>

            <!-- Charts Grid: Category Distribution & Monthly Revenue Trend -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <!-- Category Distribution Bar Chart -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">Revenue by Category (Pareto Share)</h3>
                  <span class="text-xs text-sky-400 font-mono">distribution()</span>
                </div>
                <div class="space-y-3.5 py-2">
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Cloud Infrastructure</span>
                      <span class="text-sky-400 font-mono">$234,000 (49.1%)</span>
                    </div>
                    <div class="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-sky-500 to-cyan-400 rounded-full" style="width: 49.1%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">AI Analytics</span>
                      <span class="text-sky-400 font-mono">$144,000 (30.2%)</span>
                    </div>
                    <div class="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-indigo-500 to-purple-400 rounded-full" style="width: 30.2%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Enterprise Software</span>
                      <span class="text-sky-400 font-mono">$79,500 (16.7%)</span>
                    </div>
                    <div class="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full" style="width: 16.7%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">Security &amp; Compliance</span>
                      <span class="text-sky-400 font-mono">$19,000 (4.0%)</span>
                    </div>
                    <div class="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full" style="width: 4.0%"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Monthly Revenue Trend -->
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">Monthly Revenue Trend (Jan–May 2026)</h3>
                  <span class="text-xs text-emerald-400 font-mono">trend(monthly)</span>
                </div>
                <div class="space-y-3 py-1">
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">2026-01 (Jan)</span>
                      <span class="text-sky-400 font-mono">$48,000</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-sky-500 rounded-full" style="width: 33%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">2026-02 (Feb)</span>
                      <span class="text-emerald-400 font-mono">$103,500 (+115.6%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-emerald-400 rounded-full" style="width: 72%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">2026-03 (Mar)</span>
                      <span class="text-sky-400 font-mono">$83,000 (-19.8%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-sky-400 rounded-full" style="width: 58%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">2026-04 (Apr)</span>
                      <span class="text-emerald-400 font-mono">$144,000 (+73.5%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-emerald-500 rounded-full" style="width: 100%"></div>
                    </div>
                  </div>
                  <div class="space-y-1">
                    <div class="flex justify-between text-xs font-semibold">
                      <span class="text-slate-300">2026-05 (May)</span>
                      <span class="text-sky-400 font-mono">$98,000 (-31.9%)</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div class="h-full bg-sky-400 rounded-full" style="width: 68%"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Cross-Tabulation 2D Pivot Matrix -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
              <div class="flex items-center justify-between pb-3 border-b border-border/60">
                <div>
                  <h3 class="text-sm font-bold text-white">2D Cross-Tabulation Pivot Matrix</h3>
                  <p class="text-xs text-muted-foreground mt-0.5">pivot("transactions", row="region", col="category", value="amount")</p>
                </div>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20">Grand Total: $476,500</span>
              </div>
              <div class="overflow-x-auto pt-1">
                <table class="w-full text-left text-xs font-mono">
                  <thead class="text-muted-foreground uppercase border-b border-border/60">
                    <tr>
                      <th class="py-2.5 font-sans font-semibold">Region / Market</th>
                      <th class="py-2.5 text-right">Enterprise SW</th>
                      <th class="py-2.5 text-right">Cloud Infra</th>
                      <th class="py-2.5 text-right">AI Analytics</th>
                      <th class="py-2.5 text-right">Security</th>
                      <th class="py-2.5 text-right font-bold text-white">Row Total</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/40 text-slate-300">
                    <tr class="hover:bg-slate-800/20">
                      <td class="py-3 text-white font-semibold font-sans">North America</td>
                      <td class="py-3 text-right text-slate-200">$48,000</td>
                      <td class="py-3 text-right text-slate-200">$98,000</td>
                      <td class="py-3 text-right text-slate-200">$89,000</td>
                      <td class="py-3 text-right text-slate-200">$19,000</td>
                      <td class="py-3 text-right text-emerald-400 font-bold">$254,000</td>
                    </tr>
                    <tr class="hover:bg-slate-800/20">
                      <td class="py-3 text-white font-semibold font-sans">Europe</td>
                      <td class="py-3 text-right text-slate-500">$0</td>
                      <td class="py-3 text-right text-slate-200">$136,000</td>
                      <td class="py-3 text-right text-slate-500">$0</td>
                      <td class="py-3 text-right text-slate-500">$0</td>
                      <td class="py-3 text-right text-emerald-400 font-bold">$136,000</td>
                    </tr>
                    <tr class="hover:bg-slate-800/20">
                      <td class="py-3 text-white font-semibold font-sans">Asia Pacific</td>
                      <td class="py-3 text-right text-slate-200">$31,500</td>
                      <td class="py-3 text-right text-slate-500">$0</td>
                      <td class="py-3 text-right text-slate-200">$55,000</td>
                      <td class="py-3 text-right text-slate-500">$0</td>
                      <td class="py-3 text-right text-emerald-400 font-bold">$86,500</td>
                    </tr>
                    <tr class="bg-slate-900/60 font-bold border-t-2 border-border/80">
                      <td class="py-3 text-sky-400 font-sans">Column Totals</td>
                      <td class="py-3 text-right text-sky-400">$79,500</td>
                      <td class="py-3 text-right text-sky-400">$234,000</td>
                      <td class="py-3 text-right text-sky-400">$144,000</td>
                      <td class="py-3 text-right text-sky-400">$19,000</td>
                      <td class="py-3 text-right text-emerald-400 font-extrabold">$476,500</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Recent Transactions Table -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-border/60">
                <div>
                  <h3 class="text-sm font-bold text-white">Recent Relational Transactions</h3>
                  <p class="text-xs text-muted-foreground mt-0.5">${{transactions.length}} total SQLite records</p>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-muted-foreground font-semibold">Filter:</span>
                  <button onclick="showToast('Filtered by Closed')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Closed (6)</button>
                  <button onclick="showToast('Filtered by Pending')" class="px-2.5 py-1 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border">Pending (2)</button>
                </div>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                  <thead class="text-muted-foreground uppercase font-semibold border-b border-border/60">
                    <tr>
                      <th class="py-2.5">ID</th>
                      <th class="py-2.5">Customer</th>
                      <th class="py-2.5">Region</th>
                      <th class="py-2.5">Category</th>
                      <th class="py-2.5 text-right">Amount</th>
                      <th class="py-2.5 text-center">Status</th>
                      <th class="py-2.5 text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/40 text-slate-300 font-mono">
                    ${{transactions.map(t => `
                      <tr class="hover:bg-slate-800/30 transition-colors">
                        <td class="py-3 text-muted-foreground font-semibold">#${{t.id}}</td>
                        <td class="py-3 text-white font-semibold font-sans">${{t.customer}}</td>
                        <td class="py-3 text-slate-300 font-sans">${{t.region}}</td>
                        <td class="py-3 text-sky-400 font-sans">${{t.category}}</td>
                        <td class="py-3 text-right font-bold text-white font-mono">${{t.amount}}</td>
                        <td class="py-3 text-center">
                          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold font-sans ${{
                            t.status === 'closed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                          }}">
                            ${{t.status.toUpperCase()}}
                          </span>
                        </td>
                        <td class="py-3 text-right text-muted-foreground font-mono">${{t.created_at}}</td>
                      </tr>
                    `).join('')}}
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Formatted Markdown Report Export -->
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-3">
              <div class="flex items-center justify-between pb-3 border-b border-border/60">
                <div>
                  <h3 class="text-sm font-bold text-white">Executive Markdown Report (export_executive_report)</h3>
                  <p class="text-xs text-muted-foreground mt-0.5">Automated report generated from SQLite aggregated metrics</p>
                </div>
                <button
                  onclick="copyToClipboard('${{encodeURIComponent(analyticsReportMd)}}'.replace(/%0A/g, '\\n'), 'Executive Report Copied!')"
                  class="text-xs text-sky-400 hover:underline flex items-center gap-1 font-semibold cursor-pointer"
                >📋 Copy Markdown</button>
              </div>
              <pre class="p-4 rounded-xl bg-slate-950 border border-border text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">${{analyticsReportMd}}</pre>
            </div>
          </div>
        `;
      }}

      // ── 7. INVENTORY & ITEM MANAGER (item_manager template) ────────────────
      else if (isItemManager) {{
        const items = _datasets['ItemTable'] || _datasets['ItemList'] || _datasets['ItemForm'] || _datasets['Items'] || [
          {{ id: "1", name: "Industrial Sensor Node", price: "$120.00", stock: "45", category: "Sensors" }},
          {{ id: "2", name: "Edge AI Gateway Controller", price: "$450.00", stock: "18", category: "Controllers" }},
          {{ id: "3", name: "Smart Power Relay Switch", price: "$38.50", stock: "92", category: "Switches" }},
          {{ id: "4", name: "High-Precision Temperature Probe", price: "$75.00", stock: "34", category: "Sensors" }},
          {{ id: "5", name: "Wireless Mesh Beacon", price: "$29.99", stock: "150", category: "Network" }},
        ];

        mainContentHtml = `
          <div class="space-y-6">
            <!-- Header Hero Banner -->
            <div class="rounded-2xl border border-border/80 bg-gradient-to-r from-slate-900 via-slate-900/90 to-sky-950/40 p-6 md:p-8 shadow-xl relative overflow-hidden">
              <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none"></div>
              <div class="relative z-10 max-w-2xl space-y-3">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> SQLite Inventory Storage
                </div>
                <h2 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Inventory &amp; SKU Manager</h2>
                <p class="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Real-time item tracking, low-stock threshold alerts, automatic reorder workflows, and relational SQLite inventory catalog.
                </p>
              </div>
            </div>

            <!-- Inventory KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Total SKUs</p>
                <p class="text-2xl font-extrabold text-white mt-1">${{items.length}} SKUs</p>
                <p class="text-xs text-emerald-400 mt-1">↑ +1 added this week</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Stock Units</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">339 Units</p>
                <p class="text-xs text-emerald-400 mt-1">98.2% In Stock</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-sky-400 uppercase tracking-wider">Inventory Valuation</p>
                <p class="text-2xl font-extrabold text-white mt-1 font-mono">$31,840.50</p>
                <p class="text-xs text-sky-400 mt-1">Avg SKU $6,368.10</p>
              </div>
              <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm">
                <p class="text-[11px] font-bold text-amber-400 uppercase tracking-wider">Low Stock Alerts</p>
                <p class="text-2xl font-extrabold text-amber-400 mt-1">1 SKU</p>
                <p class="text-xs text-amber-400/80 mt-1">Edge AI Gateway (18 units)</p>
              </div>
            </div>

            <!-- SKU Cards Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              ${{items.map(it => {{
                const stockNum = parseInt(it.stock) || 30;
                const isLow = stockNum < 25;
                const pct = Math.min(100, Math.round((stockNum / 150) * 100));

                return `
                  <div class="rounded-2xl border ${{isLow ? 'border-amber-500/50 bg-card' : 'border-border/80 bg-card'}} p-5 shadow-sm hover:border-sky-500/50 transition-all flex flex-col justify-between glow-hover">
                    <div class="space-y-3">
                      <div class="flex items-center justify-between">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                          ${{it.category || 'General'}}
                        </span>
                        <span class="text-xs font-mono font-bold text-emerald-400">${{it.price}}</span>
                      </div>
                      <div>
                        <h3 class="text-base font-bold text-white tracking-tight">${{it.name}}</h3>
                        <p class="text-xs text-muted-foreground mt-1">SKU ID: #00${{it.id}} • SQLite Entity</p>
                      </div>

                      <div class="space-y-1.5 pt-2">
                        <div class="flex justify-between text-xs">
                          <span class="text-slate-300 font-medium">Stock Level:</span>
                          <span class="font-mono font-bold ${{isLow ? 'text-amber-400' : 'text-slate-200'}}">${{it.stock}} units ${{isLow ? '⚠️ LOW' : ''}}</span>
                        </div>
                        <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                          <div class="h-full ${{isLow ? 'bg-amber-400' : 'bg-gradient-to-r from-sky-500 to-emerald-400'}} rounded-full" style="width: ${{pct}}%"></div>
                        </div>
                      </div>
                    </div>

                    <div class="pt-4 mt-4 border-t border-border/60 flex items-center justify-between gap-2">
                      <button
                        onclick="showToast('📦 Reordered 50 units of ${{it.name}}')"
                        class="flex-1 py-1.5 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 transition-all cursor-pointer text-center"
                      >
                        Reorder Stock
                      </button>
                      <button
                        onclick="showToast('✓ Stock verified in warehouse')"
                        class="px-3 py-1.5 text-xs rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-border"
                      >Audit</button>
                    </div>
                  </div>
                `;
              }}).join('')}}
            </div>
          </div>
        `;
      }}

      // ── 8. DASHBOARD VIEW (CRM / Construction) ───────────────────────────
      else if (activeCompName === 'Dashboard' || actLower === 'dashboard' || _PROJECT.title.toLowerCase().includes('crm') || _PROJECT.title.toLowerCase().includes('sales') || _PROJECT.title.toLowerCase().includes('construct')) {{
        const deals = _datasets['DealsTable'] || _datasets['Deals'] || _datasets['ProjectsTable'] || _datasets['Projects'] || [];
        const contacts = _datasets['ContactsTable'] || _datasets['Contacts'] || _datasets['JobsTable'] || _datasets['Jobs'] || [];
        const companies = _datasets['CompaniesTable'] || _datasets['Companies'] || _datasets['ComplianceTable'] || _datasets['Compliance'] || [];
        const activities = _datasets['ActivitiesTable'] || _datasets['Activities'] || _datasets['MaterialsTable'] || _datasets['Materials'] || [];

        let totalValueNum = 0;
        deals.forEach(d => {{
          const v = d.value || d.budget || '';
          totalValueNum += parseInt(String(v).replace(/[^0-9]/g, '')) || 0;
        }});
        const formattedTotalVal = totalValueNum > 0 ? ('$' + totalValueNum.toLocaleString()) : String(deals.length || 5);

        const isConstructionProject = _PROJECT.title.toLowerCase().includes('construct');

        const kpis = isConstructionProject ? [
          {{ label: "Total Budget", val: formattedTotalVal, sub: "+8.4% vs planned", icon: "DollarSign", color: "blue" }},
          {{ label: "Active Jobs", val: String(contacts.length || 4), sub: "All sites active", icon: "Wrench", color: "green" }},
          {{ label: "Compliance", val: "98.5%", sub: "Audits passed", icon: "Shield", color: "purple" }},
          {{ label: "Materials", val: String(activities.length || 4) + " SKU", sub: "Inventory in stock", icon: "Package", color: "amber" }}
        ] : [
          {{ label: "Total Deals", val: formattedTotalVal, sub: "+14.2% velocity", icon: "TrendingUp", color: "blue" }},
          {{ label: "Contacts", val: String(contacts.length || 5), sub: "Verified leads", icon: "Users", color: "green" }},
          {{ label: "Companies", val: String(companies.length || 5), sub: "Active accounts", icon: "Building2", color: "purple" }},
          {{ label: "Activities", val: String(activities.length || 5), sub: "Scheduled this week", icon: "Calendar", color: "amber" }}
        ];

        mainContentHtml = `
          <div class="space-y-6">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              ${{kpis.map(k => `
                <div class="rounded-xl border border-border/80 bg-slate-900/70 p-5 shadow-sm hover:border-primary/40 transition-all flex items-center justify-between">
                  <div>
                    <p class="text-xs font-bold text-sky-400 uppercase tracking-wider">${{k.label}}</p>
                    <p class="text-2xl font-extrabold text-white mt-1 tracking-tight">${{k.val}}</p>
                    <p class="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                      <span class="text-emerald-400 font-semibold">↑</span>
                      <span>${{k.sub}}</span>
                    </p>
                  </div>
                  <div class="p-3 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    ${{getNavIconSvg(k.label)}}
                  </div>
                </div>
              `).join('')}}
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm flex flex-col justify-between">
                <div class="flex items-center justify-between pb-4 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">${{isConstructionProject ? 'Project Budget Allocation' : 'Deals Value Distribution'}}</h3>
                  <span class="text-xs text-muted-foreground font-mono">Live Velocity</span>
                </div>
                <div class="py-6 space-y-3">
                  ${{(deals.slice(0, 4)).map((d, i) => {{
                    const pct = Math.min(100, Math.max(25, 95 - i * 18));
                    const valStr = d.value || d.budget || ('$' + (85 - i * 15) + ',000');
                    return `
                      <div class="space-y-1">
                        <div class="flex justify-between text-xs">
                          <span class="text-slate-300 font-medium truncate max-w-[200px]">${{d.name || d.title || 'Deal'}}</span>
                          <span class="font-mono text-sky-400 font-semibold">${{valStr}}</span>
                        </div>
                        <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                          <div class="h-full bg-gradient-to-r from-sky-500 to-emerald-400 rounded-full" style="width: ${{pct}}%"></div>
                        </div>
                      </div>
                    `;
                  }}).join('')}}
                </div>
                <div class="pt-3 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Aggregate Total</span>
                  <span class="font-mono font-bold text-white">${{formattedTotalVal}}</span>
                </div>
              </div>

              <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm flex flex-col justify-between">
                <div class="flex items-center justify-between pb-4 border-b border-border/60">
                  <h3 class="text-sm font-bold text-white">${{isConstructionProject ? 'Recent Job Milestones' : 'Recent Deals'}}</h3>
                  <button onclick="handleNavSwitch('${{isConstructionProject ? 'Projects' : 'Deals'}}')" class="text-xs text-sky-400 hover:underline">View All →</button>
                </div>
                <div class="py-2 divide-y divide-border/60">
                  ${{(deals.slice(0, 4)).map(d => `
                    <div class="py-2.5 flex items-center justify-between">
                      <div>
                        <p class="text-xs font-semibold text-white">${{d.title || d.name || 'Item'}}</p>
                        <p class="text-[11px] text-muted-foreground">${{d.contact || d.site || d.stage || 'Active'}}</p>
                      </div>
                      <span class="text-xs font-mono font-semibold text-emerald-400">${{d.value || d.budget || 'Won'}}</span>
                    </div>
                  `).join('')}}
                </div>
                <div class="pt-3 border-t border-border/40 text-xs text-muted-foreground">
                  Synchronized with backend SQLite schema
                </div>
              </div>
            </div>
          </div>
        `;
      }}

      // ── 9. GENERIC COMPONENT / TABLE FALLBACK VIEW ────────────────────────
      else if (activeInfo) {{
        const records = _datasets[activeCompName] || [];
        const tableCols = activeInfo.columns.length > 0 ? activeInfo.columns : (records.length > 0 ? Object.keys(records[0]).filter(k => k !== 'id') : ['name', 'value', 'status']);
        
        const filtered = records.filter(r => {{
          if (!_searchQuery) return true;
          const q = _searchQuery.toLowerCase();
          return Object.values(r).some(v => String(v).toLowerCase().includes(q));
        }});
        const totalPages = Math.ceil(filtered.length / _pageSize) || 1;
        const startIdx = (_currentPage - 1) * _pageSize;
        const paginated = filtered.slice(startIdx, startIdx + _pageSize);

        let formHtml = '';
        if (activeInfo.has_form && activeInfo.fields.length > 0) {{
          const formTitle = (activeInfo.form_titles && activeInfo.form_titles.length > 0) ? activeInfo.form_titles[0] : ('Add ' + activeLabel);
          formHtml = `
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm mb-6">
              <h3 class="text-base font-bold text-white mb-4 pb-2 border-b border-border/60">${{formTitle}}</h3>
              <form onsubmit="handleFormSubmit(event, '${{activeCompName}}')" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  ${{activeInfo.fields.map(f => {{
                    const key = f.toLowerCase().replace(/\\s+/g, '_');
                    const isNum = key.includes('price') || key.includes('amount') || key.includes('value') || key.includes('budget') || key.includes('quantity');
                    const isDate = key.includes('date');
                    return `
                      <div class="space-y-1.5">
                        <label class="text-xs font-semibold text-slate-300 capitalize">${{f}}</label>
                        <input
                          id="form-input-${{activeCompName}}-${{key}}"
                          type="${{isDate ? 'date' : (isNum ? 'number' : 'text')}}"
                          placeholder="Enter ${{f.toLowerCase()}}…"
                          class="flex h-10 w-full rounded-lg border border-border bg-slate-900/80 px-3 py-2 text-sm text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                          required
                        />
                      </div>
                    `;
                  }}).join('')}}
                </div>
                <div class="pt-2 flex items-center gap-3">
                  <button
                    type="submit"
                    class="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    ${{formTitle}}
                  </button>
                </div>
              </form>
            </div>
          `;
        }}

        let tableHtml = '';
        if (activeInfo.has_table || !activeInfo.has_form || records.length > 0) {{
          tableHtml = `
            <div class="rounded-xl border border-border/80 bg-card p-6 shadow-sm space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/60">
                <div>
                  <h3 class="text-base font-bold text-white">All ${{activeLabel}}</h3>
                  <p class="text-xs text-muted-foreground mt-0.5">${{records.length}} total records in database</p>
                </div>
                <div class="flex items-center gap-3">
                  <div class="relative max-w-xs w-full">
                    <svg class="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input
                      type="text"
                      placeholder="Search ${{activeLabel.toLowerCase()}}…"
                      value="${{_searchQuery}}"
                      oninput="_searchQuery = this.value; render();"
                      class="w-full rounded-lg border border-border bg-slate-900/80 pl-9 pr-3 py-1.5 text-xs text-white placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </div>
                  <button
                    onclick="openCreateModal('${{activeCompName}}')"
                    class="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md shadow-primary/20 transition-all cursor-pointer whitespace-nowrap"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    New
                  </button>
                </div>
              </div>

              <div class="rounded-lg border border-border overflow-x-auto bg-slate-900/40">
                <table class="w-full text-left text-xs">
                  <thead class="bg-slate-900/80 border-b border-border text-[11px] uppercase font-semibold text-muted-foreground">
                    <tr>
                      <th class="px-4 py-3">ID</th>
                      ${{tableCols.map(col => `<th class="px-4 py-3">${{col.replace(/_/g, ' ')}}</th>`).join('')}}
                      <th class="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/60">
                    ${{paginated.length > 0 ? paginated.map(row => `
                      <tr class="hover:bg-slate-800/40 transition-colors">
                        <td class="px-4 py-3 font-mono text-[11px] text-muted-foreground">${{row.id}}</td>
                        ${{renderRowCells(row, tableCols)}}
                        <td class="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                          <button onclick="openEditModal('${{activeCompName}}', '${{row.id}}')" class="px-2 py-0.5 text-xs rounded bg-slate-800 text-slate-200 hover:bg-slate-700 transition-colors">Edit</button>
                          <button onclick="handleDelete('${{activeCompName}}', '${{row.id}}')" class="px-2 py-0.5 text-xs rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors">Delete</button>
                        </td>
                      </tr>
                    `).join('') : `
                      <tr>
                        <td colspan="${{tableCols.length + 2}}" class="px-4 py-8 text-center text-muted-foreground text-xs">No records found matching "${{_searchQuery}}"</td>
                      </tr>
                    `}}
                  </tbody>
                </table>
              </div>

              <div class="flex items-center justify-between text-xs text-muted-foreground pt-1">
                <div>
                  Showing ${{filtered.length > 0 ? startIdx + 1 : 0}} to ${{Math.min(startIdx + _pageSize, filtered.length)}} of ${{filtered.length}} entries
                </div>
                <div class="flex items-center gap-2">
                  <button
                    onclick="changePage(-1)"
                    ${{_currentPage <= 1 ? 'disabled' : ''}}
                    class="px-2.5 py-1 rounded border border-border bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                  >Previous</button>
                  <span class="px-1.5 font-semibold text-slate-300">Page ${{_currentPage}} of ${{totalPages}}</span>
                  <button
                    onclick="changePage(1)"
                    ${{_currentPage >= totalPages ? 'disabled' : ''}}
                    class="px-2.5 py-1 rounded border border-border bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                  >Next</button>
                </div>
              </div>
            </div>
          `;
        }}

        mainContentHtml = `
          <div class="space-y-6">
            ${{formHtml}}
            ${{tableHtml}}
          </div>
        `;
      }}

      // ── Helper Modal: Write Review ─────────────────────────────────────────
      let reviewModalHtml = '';
      if (_showReviewModal) {{
        reviewModalHtml = `
          <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onclick="_showReviewModal = false; render();">
            <div class="relative w-full max-w-md bg-slate-900 border border-border rounded-2xl p-6 shadow-2xl space-y-4" onclick="event.stopPropagation()">
              <div class="flex items-center justify-between pb-3 border-b border-border/80">
                <h3 class="text-base font-bold text-white">Write Prompt Review</h3>
                <button onclick="_showReviewModal = false; render();" class="text-muted-foreground hover:text-white">✕</button>
              </div>
              <div class="space-y-3">
                <div class="space-y-1">
                  <label class="text-xs font-semibold text-slate-300">Your Name / Handle</label>
                  <input id="rev-author" type="text" value="PromptEngineer_Pro" class="w-full rounded-lg border border-border bg-slate-950 px-3 py-2 text-xs text-white" />
                </div>
                <div class="space-y-1">
                  <label class="text-xs font-semibold text-slate-300">Rating (1 to 5 Stars)</label>
                  <select id="rev-rating" class="w-full rounded-lg border border-border bg-slate-950 px-3 py-2 text-xs text-amber-400 font-bold">
                    <option value="5">★★★★★ (5 Stars - Exceptional)</option>
                    <option value="4">★★★★☆ (4 Stars - Very Good)</option>
                    <option value="3">★★★☆☆ (3 Stars - Average)</option>
                  </select>
                </div>
                <div class="space-y-1">
                  <label class="text-xs font-semibold text-slate-300">Feedback / Performance Review</label>
                  <textarea id="rev-comment" rows="3" placeholder="How did this prompt perform in your workflow?" class="w-full rounded-lg border border-border bg-slate-950 p-3 text-xs text-white"></textarea>
                </div>
              </div>
              <div class="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <button onclick="_showReviewModal = false; render();" class="px-4 py-2 text-xs rounded-lg border border-border text-slate-300">Cancel</button>
                <button onclick="submitReview()" class="px-4 py-2 text-xs font-bold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md">Submit Review</button>
              </div>
            </div>
          </div>
        `;
      }}

      // ── Edit Modal HTML ───────────────────────────────────────────────────
      let editModalHtml = '';
      if (_showEditModal && _editItem) {{
        editModalHtml = `
          <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex justify-end" onclick="closeModal()">
            <div class="relative w-full max-w-md bg-slate-900 border-l border-border p-6 shadow-2xl h-full flex flex-col" onclick="event.stopPropagation()">
              <div class="flex items-center justify-between pb-4 border-b border-border">
                <h3 class="text-base font-bold text-white">Edit Record</h3>
                <button onclick="closeModal()" class="text-muted-foreground hover:text-white text-base">✕</button>
              </div>
              <div class="space-y-4 py-6 flex-1 overflow-y-auto">
                ${{Object.keys(_editItem).filter(k => k !== 'id').map(k => `
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-muted-foreground uppercase">${{k.replace(/_/g, ' ')}}</label>
                    <input id="edit-field-${{k}}" type="text" value="${{_editItem[k] || ''}}" class="w-full rounded-md border border-border bg-slate-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary" />
                  </div>
                `).join('')}}
              </div>
              <div class="flex items-center justify-end gap-3 pt-4 border-t border-border">
                <button onclick="closeModal()" class="px-4 py-2 text-xs rounded-lg border border-border hover:bg-slate-800 text-slate-300">Cancel</button>
                <button onclick="handleSaveEdit()" class="px-4 py-2 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md">Save Changes</button>
              </div>
            </div>
          </div>
        `;
      }}

      // ── Create Modal HTML ─────────────────────────────────────────────────
      let createModalHtml = '';
      if (_showCreateModal && _editCompName) {{
        const comp = _PROJECT.components[_editCompName];
        const formFields = (comp && comp.columns.length > 0) ? comp.columns : ['name', 'value', 'status'];
        createModalHtml = `
          <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex justify-end" onclick="closeModal()">
            <div class="relative w-full max-w-md bg-slate-900 border-l border-border p-6 shadow-2xl h-full flex flex-col" onclick="event.stopPropagation()">
              <div class="flex items-center justify-between pb-4 border-b border-border">
                <h3 class="text-base font-bold text-white">Create Record</h3>
                <button onclick="closeModal()" class="text-muted-foreground hover:text-white text-base">✕</button>
              </div>
              <div class="space-y-4 py-6 flex-1 overflow-y-auto">
                ${{formFields.map(f => `
                  <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-muted-foreground uppercase">${{f.replace(/_/g, ' ')}}</label>
                    <input id="create-modal-field-${{f}}" type="text" placeholder="Enter ${{f.toLowerCase()}}…" class="w-full rounded-md border border-border bg-slate-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary" />
                  </div>
                `).join('')}}
              </div>
              <div class="flex items-center justify-end gap-3 pt-4 border-t border-border">
                <button onclick="closeModal()" class="px-4 py-2 text-xs rounded-lg border border-border hover:bg-slate-800 text-slate-300">Cancel</button>
                <button onclick="handleCreateModalSubmit()" class="px-4 py-2 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-sky-500 shadow-md">Create</button>
              </div>
            </div>
          </div>
        `;
      }}

      // ── Layout Assembly ───────────────────────────────────────────────────
      if (_PROJECT.layout === 'sidebar') {{
        root.innerHTML = `
          ${{toastHtml}}
          <div class="flex min-h-screen">
            <!-- Sidebar -->
            <aside class="w-60 border-r border-border bg-card flex flex-col justify-between shrink-0 shadow-lg">
              <div>
                <!-- Brand / Title -->
                <div class="flex items-center gap-3 px-5 py-4 border-b border-border/80">
                  <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-sky-400 flex items-center justify-center shadow-md shadow-sky-500/20 text-white font-extrabold text-sm">
                    ${{_PROJECT.title.charAt(0)}}
                  </div>
                  <div class="min-w-0">
                    <h2 class="text-xs font-bold text-white tracking-tight truncate">${{_PROJECT.title}}</h2>
                    <span class="text-[10px] text-sky-400 font-semibold tracking-wide">MCN Live App</span>
                  </div>
                </div>

                <!-- Nav Menu -->
                <nav class="p-3 space-y-1">
                  <p class="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-3 py-1.5">Navigation</p>
                  ${{_PROJECT.nav_items.map(n => `
                    <button
                      onclick="handleNavSwitch('${{n.label}}')"
                      class="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${{
                        _activeNav === n.label
                          ? 'bg-primary text-white shadow-md shadow-primary/30'
                          : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                      }}"
                    >
                      ${{getNavIconSvg(n.label)}}
                      <span>${{n.label}}</span>
                    </button>
                  `).join('')}}
                </nav>
              </div>

              <!-- User Footer -->
              <div class="p-3 border-t border-border/80">
                <div class="flex items-center gap-2.5 px-2 py-1.5 rounded-lg bg-slate-900/60 border border-border/40">
                  <div class="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold">
                    P
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-xs font-semibold text-white truncate">Creator Hub</p>
                    <p class="text-[10px] text-muted-foreground truncate">creator@promptverse.ai</p>
                  </div>
                </div>
              </div>
            </aside>

            <!-- Main Panel -->
            <main class="flex-1 flex flex-col min-w-0 bg-background overflow-y-auto">
              <!-- Top Header -->
              <header class="h-14 border-b border-border/80 bg-slate-900/40 px-6 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-muted-foreground">${{_PROJECT.title}}</span>
                  <span class="text-xs text-slate-600">/</span>
                  <h1 class="text-xs font-bold text-white uppercase tracking-wider">${{activeLabel}}</h1>
                </div>
                <div class="flex items-center gap-2">
                  <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> React Live App
                  </span>
                </div>
              </header>

              <!-- Body Content -->
              <div class="p-6 max-w-6xl w-full mx-auto space-y-6 flex-1">
                ${{mainContentHtml}}
              </div>
            </main>
          </div>

          ${{editModalHtml}}
          ${{createModalHtml}}
          ${{reviewModalHtml}}
        `;
      }} else {{
        let tabsNavHtml = '';
        if (_PROJECT.tabs.length > 1) {{
          tabsNavHtml = `
            <div class="inline-flex h-10 items-center justify-center rounded-xl bg-slate-900/90 p-1 text-muted-foreground border border-border gap-1 mb-4 shadow-inner">
              ${{_PROJECT.tabs.map(t => `
                <button
                  onclick="handleNavSwitch('${{t}}')"
                  class="inline-flex items-center justify-center whitespace-nowrap rounded-lg px-4 py-1.5 text-xs font-bold transition-all cursor-pointer ${{
                    _activeNav === t
                      ? 'bg-primary text-white shadow-md shadow-primary/30'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }}"
                >${{t}}</button>
              `).join('')}}
            </div>
          `;
        }}

        root.innerHTML = `
          ${{toastHtml}}
          <div class="max-w-6xl mx-auto p-6 space-y-6 w-full">
            <div class="flex items-center justify-between border-b border-border/80 pb-4">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-sky-400 flex items-center justify-center text-white font-extrabold text-sm shadow-md">
                  ${{_PROJECT.title.charAt(0)}}
                </div>
                <div>
                  <h1 class="text-xl font-bold tracking-tight text-white">${{_PROJECT.title}}</h1>
                  <p class="text-xs text-muted-foreground">Compiled from <code>ui/app.mcn</code> &amp; <code>backend/main.mcn</code></p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> React Live App
                </span>
              </div>
            </div>

            ${{tabsNavHtml}}

            <div>
              ${{mainContentHtml}}
            </div>
          </div>

          ${{editModalHtml}}
          ${{createModalHtml}}
          ${{reviewModalHtml}}
        `;
      }}
    }}

    render();
  </script>
</body>
</html>
"""


@app.route("/preview/<path:filename>")
def serve_preview_static_file(filename):
    ws = _request_workspace()
    frontend = ws / "frontend"
    dist = frontend / "dist"
    if dist.exists() and (dist / filename).exists():
        return send_from_directory(str(dist), filename)
    if (frontend / filename).exists():
        return send_from_directory(str(frontend), filename)
    return serve_preview_index()


@app.route("/preview/")
@app.route("/preview")
@app.route("/preview/index.html")
def serve_preview_index():
    ws = _request_workspace()
    frontend = ws / "frontend"
    dist = frontend / "dist"
    if dist.exists() and (dist / "index.html").exists():
        return send_from_directory(str(dist), "index.html")
    
    app_tsx = frontend / "src" / "App.tsx"
    comps_dir = frontend / "src" / "components"

    # Auto-compile ui/app.mcn on the fly if frontend files are not compiled yet
    if (not app_tsx.exists() or not app_tsx.read_text(encoding="utf-8").strip()) and (ws / "ui" / "app.mcn").exists():
        try:
            from mcn.core_engine.lexer import Lexer
            from mcn.core_engine.parser import Parser
            from mcn.core_engine.mcn_interpreter import MCNInterpreter
            from mcn.core_engine.ui_compiler import UICompiler
            
            ui_code = (ws / "ui" / "app.mcn").read_text(encoding="utf-8")
            tokens = Lexer(ui_code).tokenize()
            program = Parser(tokens).parse()
            interp = MCNInterpreter()
            evaluator = interp._evaluator
            evaluator.execute_program(program)
            compiler = UICompiler(output_dir=frontend)
            compiler.compile(evaluator)
        except Exception:
            pass
    
    app_code = app_tsx.read_text(encoding="utf-8") if app_tsx.exists() else ""
    
    components_code = {}
    if comps_dir.exists():
        for p in sorted(comps_dir.glob("*.tsx")):
            components_code[p.stem] = p.read_text(encoding="utf-8")

    return _generate_interactive_preview_html(ws, app_code, components_code)


@app.route("/api/devserver/start", methods=["POST"])
def devserver_start():
    global _dev_server, _mcn_backend
    ws           = _request_workspace()
    frontend     = ws / "frontend"
    backend_file = ws / "backend" / "main.mcn"

    if not (frontend / "package.json").exists():
        return jsonify({"success": False, "error": "frontend/package.json not found. Run ⚡ Build first."}), 400

    if _dev_server and _dev_server.poll() is None:
        return jsonify({
            "success": True,
            "port": _DEV_PORT,
            "pid": _dev_server.pid,
            "already_running": True,
            "mode": "vite",
            "preview_url": f"http://localhost:{_DEV_PORT}",
            "backend_port": _BACKEND_PORT if (_mcn_backend and _mcn_backend.poll() is None) else None,
        })

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

    # ── 2. If node_modules exists, start Vite dev server ───────────────────────
    if _NPM_AVAILABLE and (frontend / "node_modules").exists():
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
            if _dev_server.poll() is None:
                return jsonify({
                    "success":      True,
                    "port":         _DEV_PORT,
                    "pid":          _dev_server.pid,
                    "mode":         "vite",
                    "preview_url":  f"http://localhost:{_DEV_PORT}",
                    "backend_port": _BACKEND_PORT if (_mcn_backend and _mcn_backend.poll() is None) else None,
                })
        except Exception:
            pass

    # ── 3. Fallback: Fast, instant interactive React Preview ──────────────────
    return jsonify({
        "success":      True,
        "port":         None,
        "mode":         "static",
        "preview_url":  "/preview/index.html",
        "backend_port": _BACKEND_PORT if (_mcn_backend and _mcn_backend.poll() is None) else None,
        "message":      "Serving interactive React application at /preview/index.html",
    })


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



_ANALYTICS_BACKEND = (
'use analytics\n'
'\n'
'contract Transaction\n'
'    customer: str\n'
'    region: str\n'
'    category: str\n'
'    amount: float\n'
'    status: str\n'
'\n'
'query("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, region TEXT, category TEXT, amount REAL, status TEXT, created_at TEXT DEFAULT (datetime(\'now\')))")\n'
'\n'
'var count_tx = query("SELECT COUNT(*) as cnt FROM transactions")[0].cnt\n'
'if count_tx == 0\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Acme Corp\', \'North America\', \'Enterprise Software\', 48000, \'closed\', \'2026-01-15\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Globex Inc\', \'Europe\', \'Cloud Infrastructure\', 72000, \'closed\', \'2026-02-10\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Soylent Corp\', \'Asia Pacific\', \'Enterprise Software\', 31500, \'closed\', \'2026-02-28\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Initech\', \'North America\', \'Security & Compliance\', 19000, \'pending\', \'2026-03-05\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Umbrella Corp\', \'Europe\', \'Cloud Infrastructure\', 64000, \'closed\', \'2026-03-12\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Hooli\', \'North America\', \'AI Analytics\', 89000, \'closed\', \'2026-04-02\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Massive Dynamic\', \'Asia Pacific\', \'AI Analytics\', 55000, \'pending\', \'2026-04-18\')")\n'
'    query("INSERT INTO transactions (customer, region, category, amount, status, created_at) VALUES (\'Stark Industries\', \'North America\', \'Cloud Infrastructure\', 98000, \'closed\', \'2026-05-01\')")\n'
'\n'
'service analytics_api\n'
'    port 8080\n'
'\n'
'    endpoint get_dashboard()\n'
'        var kpis = kpi_summary("transactions", metrics=["sum:amount", "avg:amount", "count:*"])\n'
'        var trends = trend("transactions", date_field="created_at", value_field="amount", interval="monthly", agg="sum")\n'
'        var categories = distribution("transactions", category_field="category", value_field="amount")\n'
'        var regions = distribution("transactions", category_field="region", value_field="amount")\n'
'        var matrix = pivot("transactions", row_field="region", col_field="category", value_field="amount")\n'
'        var recent = query("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 10")\n'
'        return {success: true, kpis: kpis, trends: trends, categories: categories, regions: regions, pivot: matrix, data: recent}\n'
'\n'
'    endpoint export_executive_report(format = "markdown")\n'
'        var rep = report("transactions", metrics=["sum:amount", "avg:amount", "count:*"], group_by=["category"])\n'
'        var output = export_report(rep, format=format)\n'
'        return {success: true, report: output, format: format}\n'
'\n'
'    endpoint add_transaction(customer, region, category, amount, status)\n'
'        query("INSERT INTO transactions (customer, region, category, amount, status) VALUES (?, ?, ?, ?, ?)", (customer, region, category, amount, status))\n'
'        var id = query("SELECT last_insert_rowid() as id")[0].id\n'
'        return {success: true, id: id}\n'
)

_ANALYTICS_UI = (
'component AnalyticsDashboard\n'
'    state total_revenue = "$476,500"\n'
'    state deal_count    = 8\n'
'    state avg_deal      = "$59,562"\n'
'    state items         = []\n'
'    state category_data = []\n'
'    state trend_data    = []\n'
'    state report_text   = ""\n'
'    state loading       = false\n'
'\n'
'    on load\n'
'        var res = get_dashboard()\n'
'        if res.success\n'
'            items = res.data\n'
'            category_data = res.categories.items\n'
'            trend_data = res.trends\n'
'        var rep_res = export_executive_report("markdown")\n'
'        if rep_res.success\n'
'            report_text = rep_res.report\n'
'\n'
'    render\n'
'        card\n'
'            card_header "Executive Analytics & Performance BI"\n'
'            div grid_cols=3\n'
'                stat_card label="Total Revenue" value=total_revenue unit=""\n'
'                stat_card label="Total Deals" value=deal_count unit=""\n'
'                stat_card label="Avg Deal Size" value=avg_deal unit=""\n'
'            div grid_cols=2\n'
'                bar_chart data=category_data x_key="category" y_key="amount" height=300\n'
'                line_chart data=trend_data x_key="period" y_key="value" height=300\n'
'            separator\n'
'            card_header "Recent Transactions"\n'
'            table\n'
'                table_header\n'
'                    table_row\n'
'                        table_head "id"\n'
'                        table_head "customer"\n'
'                        table_head "region"\n'
'                        table_head "category"\n'
'                        table_head "amount"\n'
'                        table_head "status"\n'
'                table_body\n'
'\n'
'app BusinessAnalytics\n'
'    title  "Executive Analytics & BI Hub"\n'
'    theme  "professional"\n'
'    layout\n'
'        tabs\n'
'            tab "Executive Overview" AnalyticsDashboard\n'
)


_PROMPT_MARKETPLACE_BACKEND = '''\
use analytics

contract PromptItem
    title: str
    category: str
    ai_tool: str
    prompt_template: str
    description: str
    sample_output: str
    price: float
    author: str
    forks_count: int
    avg_rating: float
    tags: str

contract WorkflowItem
    title: str
    description: str
    ai_tools_used: str
    step_count: int
    author: str
    price: float
    forks_count: int

contract CreatorProfile
    username: str
    specialty: str
    rating: float
    total_sales: float
    badge: str

contract Review
    item_id: int
    reviewer: str
    rating: int
    comment: str

query("CREATE TABLE IF NOT EXISTS prompts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, category TEXT, ai_tool TEXT, prompt_template TEXT, description TEXT, sample_output TEXT, price REAL, author TEXT, forks_count INTEGER DEFAULT 0, avg_rating REAL DEFAULT 5.0, tags TEXT, created_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS workflows (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, ai_tools_used TEXT, step_count INTEGER, author TEXT, price REAL, forks_count INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS creators (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, specialty TEXT, rating REAL, total_sales REAL, badge TEXT, created_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, reviewer TEXT, rating INTEGER, comment TEXT, created_at TEXT DEFAULT (datetime('now')))")
query("CREATE TABLE IF NOT EXISTS prompt_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, prompt_id INTEGER, user TEXT, input_params TEXT, execution_time_ms REAL, created_at TEXT DEFAULT (datetime('now')))")

var count_prompts = query("SELECT COUNT(*) as cnt FROM prompts")[0].cnt
if count_prompts == 0
    query("INSERT INTO creators (username, specialty, rating, total_sales, badge) VALUES ('AlexRivera', 'Midjourney & SDXL Master', 4.95, 14200.0, 'Top Creator')")
    query("INSERT INTO creators (username, specialty, rating, total_sales, badge) VALUES ('ElenaDev', 'Claude & Cursor Code Architect', 4.98, 28900.0, 'Pro Verified')")
    query("INSERT INTO creators (username, specialty, rating, total_sales, badge) VALUES ('MarcusGrowth', 'SEO & Marketing Pipelines', 4.88, 9850.0, 'Rising Star')")

    query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, forks_count, avg_rating, tags) VALUES ('Ultra-Realistic Cinematic Photography', 'Image & Art', 'Midjourney v6', 'Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0', 'Studio-quality portrait and landscape generator with cinematic depth-of-field and lighting.', 'A hyper-detailed 35mm portrait with golden-hour edge lighting and lifelike skin textures.', 4.99, 'AlexRivera', 1420, 4.95, 'photography,cinematic,midjourney,lighting')")

    query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, forks_count, avg_rating, tags) VALUES ('Full-Stack Architecture & TypeScript Refactor', 'Coding & Tech', 'Claude 3.5 Sonnet', 'Act as a Principal Software Architect. Review the following {{language}} component for {{framework}}. Apply clean architecture, strict typing, error boundaries, and return production-ready code with unit tests:\\n\\n{{code_snippet}}', 'Enterprise-grade code reviewer and refactoring engine tailored for full-stack engineering.', 'Provides clean module interfaces, Zod schema validations, and 100% test coverage patterns.', 9.99, 'ElenaDev', 3840, 4.99, 'typescript,react,architecture,clean-code')")

    query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, forks_count, avg_rating, tags) VALUES ('Viral LinkedIn & Twitter Thread Engine', 'Marketing & SEO', 'ChatGPT 4o', 'Write a viral 7-part hook thread about {{topic}} targeting {{audience}}. Use punchy short sentences, contrarian insights, data-backed frameworks, and finish with a high-converting CTA.', 'Transforms complex business lessons and case studies into viral social engagement threads.', 'Hook: 90% of SaaS founders make this pricing mistake... (7-tweet breakdown with actionable takeaways)', 0.0, 'MarcusGrowth', 6120, 4.88, 'social,marketing,growth,threads,free')")

    query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, forks_count, avg_rating, tags) VALUES ('Autonomous Research Agent System Prompt', 'AI Agents', 'Claude 3.5 Sonnet', 'You are an Autonomous Research Analyst Agent. Given the research inquiry: {{inquiry}}, perform a 3-step synthesis: 1. Core thesis, 2. Key counter-arguments, 3. Strategic executive recommendations with citations.', 'Complete system prompt definition for deploying research and market analysis agents.', 'Comprehensive executive brief structured with methodology, findings, and risk matrix.', 14.99, 'ElenaDev', 890, 4.92, 'agent,research,system-prompt,langchain')")

    query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, forks_count, avg_rating, tags) VALUES ('Cyberpunk Isometric Game Asset Generator', 'Image & Art', 'Stable Diffusion XL', 'Isometric 3D render of {{asset_name}}, cyberpunk futuristic aesthetic, neon glow, octane render, game-ready sprite asset on dark clean background', 'Generate ready-to-use game UI, building assets, and props for game developers.', 'Isometric neon-lit cyber-cafe asset with transparent background alpha ready for Unity.', 2.99, 'AlexRivera', 740, 4.85, 'game-dev,isometric,sdxl,3d,cyberpunk')")

    query("INSERT INTO workflows (title, description, ai_tools_used, step_count, author, price, forks_count) VALUES ('End-to-End SEO Content Pipeline', 'Multi-step pipeline that researches search intent, generates SEO outlines, writes 2,000-word authoritative drafts, and optimizes meta tags.', 'Claude 3.5 + Perplexity', 3, 'MarcusGrowth', 19.99, 1280)")
    query("INSERT INTO workflows (title, description, ai_tools_used, step_count, author, price, forks_count) VALUES ('API Contract to Frontend Component Suite', 'Automated pipeline that transforms OpenAPI YAML specs into TypeScript types, Mock Service Worker handlers, and shadcn/ui components.', 'Claude 3.5 + GPT-4o', 4, 'ElenaDev', 24.99, 2150)")

    query("INSERT INTO reviews (item_id, reviewer, rating, comment) VALUES (1, 'Sarah_K', 5, 'The lighting parameters are unbelievable! Saved me hours of prompt tweaking in Midjourney v6.')")
    query("INSERT INTO reviews (item_id, reviewer, rating, comment) VALUES (2, 'DevLead_Tom', 5, 'Best architecture prompt on the market. Catching edge cases in our TypeScript stack effortlessly.')")
    query("INSERT INTO reviews (item_id, reviewer, rating, comment) VALUES (3, 'GrowthHacker99', 5, 'Used this for 3 client threads and impressions went up 400% in 2 weeks.')")

service prompt_marketplace_api
    port 8080

    endpoint list_prompts(category = "All", search = "", limit = 50)
        var items = []
        if category == "All" or category == ""
            if search == ""
                items = query("SELECT * FROM prompts ORDER BY forks_count DESC LIMIT ?", (limit,))
            else
                items = query("SELECT * FROM prompts WHERE title LIKE ? OR tags LIKE ? OR ai_tool LIKE ? ORDER BY forks_count DESC LIMIT ?", ("%" + search + "%", "%" + search + "%", "%" + search + "%", limit))
        else
            if search == ""
                items = query("SELECT * FROM prompts WHERE category = ? ORDER BY forks_count DESC LIMIT ?", (category, limit))
            else
                items = query("SELECT * FROM prompts WHERE category = ? AND (title LIKE ? OR tags LIKE ?) ORDER BY forks_count DESC LIMIT ?", (category, "%" + search + "%", "%" + search + "%", limit))
        return {success: true, data: items, count: len(items)}

    endpoint get_prompt(id)
        var rows = query("SELECT * FROM prompts WHERE id = ?", (id,))
        if not rows
            throw "Prompt with ID " + str(id) + " not found"
        var prompt_data = rows[0]
        var reviews_list = query("SELECT * FROM reviews WHERE item_id = ? ORDER BY id DESC", (id,))
        return {success: true, prompt: prompt_data, reviews: reviews_list}

    endpoint create_prompt(title, category, ai_tool, prompt_template, description, sample_output, price, author, tags)
        var p = float(price) if price else 0.0
        query("INSERT INTO prompts (title, category, ai_tool, prompt_template, description, sample_output, price, author, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (title, category, ai_tool, prompt_template, description, sample_output, p, author, tags))
        var pid = query("SELECT last_insert_rowid() as id")[0].id
        return {success: true, id: pid, message: "Prompt published successfully to Marketplace!"}

    endpoint fork_prompt(id)
        query("UPDATE prompts SET forks_count = forks_count + 1 WHERE id = ?", (id,))
        var updated = query("SELECT forks_count FROM prompts WHERE id = ?", (id,))[0]
        return {success: true, forks_count: updated.forks_count}

    endpoint test_prompt_live(prompt_template, subject = "Cyberpunk Samurai in Rain", language = "TypeScript", audience = "SaaS Founders", inquiry = "Future of Edge AI Computing")
        var executed_prompt = prompt_template
        executed_prompt = executed_prompt.replace("{{subject}}", subject)
        executed_prompt = executed_prompt.replace("{{language}}", language)
        executed_prompt = executed_prompt.replace("{{framework}}", "React + Next.js 15")
        executed_prompt = executed_prompt.replace("{{code_snippet}}", "export function useDataFetch(url) { return fetch(url) }")
        executed_prompt = executed_prompt.replace("{{topic}}", subject)
        executed_prompt = executed_prompt.replace("{{audience}}", audience)
        executed_prompt = executed_prompt.replace("{{inquiry}}", inquiry)
        executed_prompt = executed_prompt.replace("{{asset_name}}", subject)

        var ai_result = ai("You are an advanced AI simulator. Execute the following prompt and generate high-quality output:\\n\\n" + executed_prompt)
        return {
            success: true,
            interpolated_prompt: executed_prompt,
            result: ai_result,
            tokens_used: 284,
            latency_ms: 340
        }

    endpoint list_workflows(limit = 20)
        var wf = query("SELECT * FROM workflows ORDER BY forks_count DESC LIMIT ?", (limit,))
        return {success: true, data: wf}

    endpoint run_multi_stage_workflow(workflow_title, topic = "Autonomous Agents in Healthcare")
        var stage1_out = ai("Stage 1 Analysis: Identify the top 3 high-impact market angles for: " + topic)
        var stage2_out = ai("Stage 2 Architecture: Create a structured outline and strategy based on: " + stage1_out)
        var stage3_out = ai("Stage 3 Final Output: Synthesize an executive report with action items based on: " + stage2_out)

        return {
            success: true,
            workflow: workflow_title,
            topic: topic,
            stages: [
                {stage: 1, title: "Intent & Market Intelligence", output: stage1_out, status: "completed"},
                {stage: 2, title: "Architecture & Framework Construction", output: stage2_out, status: "completed"},
                {stage: 3, title: "Final Delivery & Quality Scoring", output: stage3_out, status: "completed"}
            ]
        }

    endpoint add_prompt_review(item_id, reviewer, rating, comment)
        var r_val = int(rating)
        query("INSERT INTO reviews (item_id, reviewer, rating, comment) VALUES (?, ?, ?, ?)", (item_id, reviewer, r_val, comment))
        var avg_res = query("SELECT AVG(rating) as avg_r FROM reviews WHERE item_id = ?", (item_id,))[0].avg_r
        if avg_res
            query("UPDATE prompts SET avg_rating = ? WHERE id = ?", (round(avg_res, 2), item_id))
        return {success: true, message: "Review published!"}

    endpoint get_marketplace_analytics()
        var kpis = kpi_summary("prompts", metrics=["sum:price", "avg:avg_rating", "count:*"])
        var cat_dist = distribution("prompts", category_field="category", value_field="forks_count", agg="sum")
        var tool_dist = distribution("prompts", category_field="ai_tool", value_field="forks_count", agg="sum")
        var recent_reviews = query("SELECT r.*, p.title as prompt_title FROM reviews r JOIN prompts p ON r.item_id = p.id ORDER BY r.id DESC LIMIT 5")
        var rep = report("prompts", metrics=["sum:forks_count", "avg:avg_rating", "count:*"], group_by=["category"])
        var md_report = export_report(rep, format="markdown")

        return {
            success: true,
            total_prompts: kpis.total_records,
            total_forks: 13490,
            gross_volume: "$68,450.00",
            category_distribution: cat_dist.items,
            tool_distribution: tool_dist.items,
            recent_reviews: recent_reviews,
            report_md: md_report
        }
'''

_PROMPT_MARKETPLACE_UI = '''\
component MarketplaceCatalog
    state items = []
    state category = "All"
    state search = ""
    state active_tool = "All"
    state selected_prompt = null
    state copy_status = ""
    state show_test_modal = false

    on load
        var res = list_prompts(category, search)
        items = res.data

    on submit
        var res = list_prompts(category, search)
        items = res.data

    render
        div
            card
                card_header "Discover & Fork Prompts for Modern AI Tools"
                form on_submit=submit
                    div grid_cols=3
                        input bind=search label="Search prompts, keywords, or tags"
                        select bind=category options=["All", "Image & Art", "Coding & Tech", "Marketing & SEO", "AI Agents"] label="Filter Category"
                        button "Filter Catalog" variant="default"
            card
                card_header "Top Community Prompts & Workflows"
                table data=items
                    table_header
                        table_row
                            table_head "title"
                            table_head "category"
                            table_head "ai_tool"
                            table_head "price"
                            table_head "author"
                            table_head "avg_rating"
                            table_head "forks_count"
                    table_body

component PromptTester
    state template_text = "Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures --ar 16:9"
    state subject = "Cyberpunk Samurai in Neon Rain"
    state language = "TypeScript"
    state audience = "Founders and Engineers"
    state test_output = ""
    state interpolated_prompt = ""
    state loading = false
    state tokens_count = 0
    state latency = 0

    on submit
        loading = true
        var res = test_prompt_live(template_text, subject, language, audience)
        if res.success
            test_output = res.result
            interpolated_prompt = res.interpolated_prompt
            tokens_count = res.tokens_used
            latency = res.latency_ms
        loading = false

    render
        div
            card
                card_header "Live Prompt Playground & Variable Interpolator"
                form on_submit=submit
                    textarea bind=template_text label="Prompt Template (Supports {{variables}})"
                    div grid_cols=3
                        input bind=subject label="Variable: {{subject}} or {{topic}}"
                        input bind=language label="Variable: {{language}} or {{framework}}"
                        input bind=audience label="Variable: {{audience}} or {{target}}"
                    button "Execute Prompt with AI Simulator" variant="default" disabled=loading
            card
                card_header "Execution Result & Interpolated Output"
                div grid_cols=2
                    stat_card label="Simulated Tokens" value=tokens_count unit="tok"
                    stat_card label="Latency" value=latency unit="ms"
                card_content
                    div
                        text test_output

component WorkflowsStudio
    state workflows = []
    state selected_workflow = "End-to-End SEO Content Pipeline"
    state topic = "Autonomous Agents in Financial Services"
    state stage1 = ""
    state stage2 = ""
    state stage3 = ""
    state running = false

    on load
        var res = list_workflows()
        workflows = res.data

    on submit
        running = true
        var res = run_multi_stage_workflow(selected_workflow, topic)
        if res.success
            stage1 = res.stages[0].output
            stage2 = res.stages[1].output
            stage3 = res.stages[2].output
        running = false

    render
        div
            card
                card_header "Multi-Step AI Workflow Orchestrator"
                form on_submit=submit
                    div grid_cols=2
                        input bind=selected_workflow label="Workflow Pipeline"
                        input bind=topic label="Workflow Execution Subject / Topic"
                    button "Run Multi-Stage Workflow" variant="default" disabled=running
            div grid_cols=3
                card
                    card_header "Stage 1: Intent & Market Intelligence"
                    text stage1
                card
                    card_header "Stage 2: Architecture & Content Framework"
                    text stage2
                card
                    card_header "Stage 3: Final Delivery & Executive Score"
                    text stage3

component PublishStudio
    state title = ""
    state category = "Coding & Tech"
    state ai_tool = "Claude 3.5 Sonnet"
    state prompt_template = ""
    state description = ""
    state sample_output = ""
    state price = 0.0
    state author = "CommunityCreator"
    state tags = ""
    state status_msg = ""
    state loading = false

    on submit
        loading = true
        var res = create_prompt(title, category, ai_tool, prompt_template, description, sample_output, price, author, tags)
        if res.success
            status_msg = "Successfully published to Marketplace!"
            title = ""
            prompt_template = ""
            description = ""
            sample_output = ""
            tags = ""
        loading = false

    render
        div
            card
                card_header "Publish Prompt to Global Marketplace"
                form on_submit=submit
                    div grid_cols=2
                        input bind=title label="Prompt Title"
                        select bind=category options=["Image & Art", "Coding & Tech", "Marketing & SEO", "AI Agents"] label="Category"
                    div grid_cols=2
                        select bind=ai_tool options=["Midjourney v6", "Claude 3.5 Sonnet", "ChatGPT 4o", "Stable Diffusion XL", "Cursor", "DALL-E 3"] label="Target AI Model"
                        input bind=price label="Price in USD ($0 for Free/Community)" type="number"
                    textarea bind=prompt_template label="Prompt Template (use {{variable}} for inputs)"
                    textarea bind=description label="What makes this prompt effective? (Description)"
                    textarea bind=sample_output label="Sample Output Generated by AI"
                    div grid_cols=2
                        input bind=author label="Creator Handle"
                        input bind=tags label="Tags (comma separated)"
                    button "Publish to Marketplace" variant="default" disabled=loading
                    div
                        text status_msg

component CreatorAnalytics
    state total_prompts = 5
    state total_forks = 13490
    state gross_volume = "$68,450.00"
    state category_data = []
    state recent_reviews = []
    state report_md = ""

    on load
        var res = get_marketplace_analytics()
        if res.success
            total_prompts = res.total_prompts
            total_forks = res.total_forks
            gross_volume = res.gross_volume
            category_data = res.category_distribution
            recent_reviews = res.recent_reviews
            report_md = res.report_md

    render
        div
            card
                card_header "Marketplace Intelligence & Creator Performance"
                div grid_cols=3
                    stat_card label="Total Prompts" value=total_prompts unit=""
                    stat_card label="Total Community Forks" value=total_forks unit=""
                    stat_card label="Gross Platform Volume" value=gross_volume unit=""
            card
                card_header "Forks by Category Distribution"
                bar_chart data=category_data x_key="category" y_key="value" height=280
            card
                card_header "Community Reviews & Feedback"
                table data=recent_reviews
                    table_header
                        table_row
                            table_head "prompt_title"
                            table_head "reviewer"
                            table_head "rating"
                            table_head "comment"
                    table_body

app PromptMarketplace
    title "PromptVerse — AI Prompt & Workflow Marketplace"
    theme "modern"
    layout
        sidebar
            nav "Marketplace" MarketplaceCatalog
            nav "Prompt Playground" PromptTester
            nav "Workflow Pipelines" WorkflowsStudio
            nav "Publish Prompt" PublishStudio
            nav "Creator Analytics" CreatorAnalytics
'''


@app.route("/api/examples")
def get_examples():
    return jsonify([
        # ═════════════════════════════════════════════════════════════════════
        # 1. REPL & Quick Scripts (category: repl)
        # ═════════════════════════════════════════════════════════════════════
        {
            "id": "db_analytics",
            "name": "Database Reports & Analytics Engine",
            "category": "repl",
            "badge": "Analytics",
            "description": "Native SQLite report generation, KPIs, time-series trends, distribution, and markdown export.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Native Database Reports & Analytics\n'
                'use analytics\n'
                '\n'
                'query("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, rep TEXT, region TEXT, amount REAL, created_at TEXT)")\n'
                'query("INSERT INTO sales (rep, region, amount, created_at) VALUES (\'Alice\', \'North\', 15000, \'2026-01-10\')")\n'
                'query("INSERT INTO sales (rep, region, amount, created_at) VALUES (\'Bob\', \'West\', 22000, \'2026-02-14\')")\n'
                'query("INSERT INTO sales (rep, region, amount, created_at) VALUES (\'Charlie\', \'North\', 35000, \'2026-02-20\')")\n'
                'query("INSERT INTO sales (rep, region, amount, created_at) VALUES (\'Alice\', \'West\', 41000, \'2026-03-05\')")\n'
                'query("INSERT INTO sales (rep, region, amount, created_at) VALUES (\'Diana\', \'East\', 18500, \'2026-03-15\')")\n'
                '\n'
                '// 1. KPI Summary Aggregations\n'
                'var kpi = kpi_summary("sales", metrics=["sum:amount", "avg:amount", "count:*"])\n'
                'log("KPI Summary: " + str(kpi))\n'
                '\n'
                '// 2. Time-series Monthly Trend\n'
                'var trends = trend("sales", date_field="created_at", value_field="amount", interval="monthly", agg="sum")\n'
                'log("Monthly Trend: " + str(trends))\n'
                '\n'
                '// 3. Category & Regional Distribution\n'
                'var regional = distribution("sales", category_field="region", value_field="amount")\n'
                'log("Regional Share: " + str(regional))\n'
                '\n'
                '// 4. Pivot Matrix Table\n'
                'var p = pivot("sales", row_field="rep", col_field="region", value_field="amount")\n'
                'log("Pivot Matrix: " + str(p))\n'
                '\n'
                '// 5. Formatted Markdown Report Export\n'
                'var rep_data = report("sales", metrics=["sum:amount", "count:*"], group_by=["region"])\n'
                'var report_md = export_report(rep_data, format="markdown")\n'
                'log("--- EXECUTIVE EXPORT ---")\n'
                'log(str(report_md))\n'
            )
        },
        {
            "id": "hello",
            "name": "Hello World & Variables",
            "category": "repl",
            "badge": "Basics",
            "description": "Variables, strings, array operations, and condition branches.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Hello World & Variables\n'
                'var title = "MCN Studio"\n'
                'log("⚡ Hello from " + title + "!")\n'
                '\n'
                'var nums = [10, 25, 42, 88, 105]\n'
                'var total = sum(nums)\n'
                'var average = avg(nums)\n'
                'log("Numbers: " + str(nums))\n'
                'log("Total: " + str(total) + " | Average: " + str(average))\n'
                '\n'
                'if total > 100\n'
                '    log("Status: High-volume pipeline active")\n'
                'else\n'
                '    log("Status: Standard volume")\n'
            )
        },
        {
            "id": "functions",
            "name": "Functions & Logic",
            "category": "repl",
            "badge": "Logic",
            "description": "Recursion, default arguments, and pure functions.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Functions, Recursion & Logic\n'
                'function greet(name, prefix = "Welcome")\n'
                '    return prefix + ", " + name + "!"\n'
                '\n'
                'function factorial(n)\n'
                '    if n <= 1\n'
                '        return 1\n'
                '    return n * factorial(n - 1)\n'
                '\n'
                'function clamp(val, min_val, max_val)\n'
                '    if val < min_val\n'
                '        return min_val\n'
                '    if val > max_val\n'
                '        return max_val\n'
                '    return val\n'
                '\n'
                'log(greet("Engineer"))\n'
                'log("5! = " + str(factorial(5)))\n'
                'log("7! = " + str(factorial(7)))\n'
                'log("clamp(150, 0, 100) = " + str(clamp(150, 0, 100)))\n'
            )
        },
        {
            "id": "pipeline",
            "name": "Data Pipeline & ETL",
            "category": "repl",
            "badge": "ETL",
            "description": "Multi-stage data extraction, transform, and load pipeline.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Data Pipeline & ETL\n'
                'pipeline data_processor\n'
                '    stage extract\n'
                '        var raw_records = [\n'
                '            {id: 101, customer: "Acme Corp", amount: 4500, region: "North"},\n'
                '            {id: 102, customer: "Globex", amount: 12000, region: "West"},\n'
                '            {id: 103, customer: "Soylent", amount: 8400, region: "East"}\n'
                '        ]\n'
                '        log("1. Extracted " + str(len(raw_records)) + " records")\n'
                '        return raw_records\n'
                '\n'
                '    stage transform(records)\n'
                '        var enriched = []\n'
                '        var total_revenue = 0\n'
                '        for r in records\n'
                '            var fee = r.amount * 0.05\n'
                '            var net = r.amount - fee\n'
                '            total_revenue = total_revenue + net\n'
                '            enriched = enriched + [{id: r.id, customer: r.customer, net_amount: net}]\n'
                '        log("2. Transformed records — Net Revenue: $" + str(total_revenue))\n'
                '        return {items: enriched, revenue: total_revenue}\n'
                '\n'
                '    stage load(result)\n'
                '        log("3. Pipeline complete: " + str(len(result.items)) + " records ready for export")\n'
                '\n'
                'data_processor.run()\n'
            )
        },
        {
            "id": "tests",
            "name": "Unit Testing & Assertions",
            "category": "repl",
            "badge": "Test",
            "description": "Declarative test suites and assertion blocks.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Unit Testing & Assertions\n'
                'function calc_discount(price, tier)\n'
                '    if tier == "enterprise"\n'
                '        return price * 0.8\n'
                '    if tier == "pro"\n'
                '        return price * 0.9\n'
                '    return price\n'
                '\n'
                'test "enterprise discount gives 20% off"\n'
                '    var p = calc_discount(100, "enterprise")\n'
                '    assert p == 80\n'
                '\n'
                'test "pro discount gives 10% off"\n'
                '    var p = calc_discount(100, "pro")\n'
                '    assert p == 90\n'
                '\n'
                'test "standard tier has no discount"\n'
                '    var p = calc_discount(100, "standard")\n'
                '    assert p == 100\n'
            )
        },
        {
            "id": "algorithms",
            "name": "Algorithms & Analytics",
            "category": "repl",
            "badge": "Math",
            "description": "In-memory sorting, aggregations, and statistics.",
            "file": "backend/main.mcn",
            "code": (
                '// REPL Quick Script: Sorting & Analytics\n'
                'var scores = [45, 12, 89, 34, 99, 23, 76, 55]\n'
                'log("Original scores: " + str(scores))\n'
                'var sorted_scores = sort(scores)\n'
                'log("Sorted scores: " + str(sorted_scores))\n'
                'log("Min score: " + str(min(scores)))\n'
                'log("Max score: " + str(max(scores)))\n'
                'log("Average score: " + str(avg(scores)))\n'
            )
        },

        # ═════════════════════════════════════════════════════════════════════
        # 2. Internal Tools & Web Apps (category: internal_app)
        # ═════════════════════════════════════════════════════════════════════
        {
            "id": "sales_hub",
            "name": "Sales Intelligence Hub",
            "category": "internal_app",
            "badge": "Full-Stack",
            "description": "Executive dashboard, pipeline table, deals breakdown, and lead stats.",
            "project": True,
            "open": "backend/main.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _DEFAULT_BACKEND},
                {"path": "ui/app.mcn",       "content": _DEFAULT_UI}
            ]
        },
        {
            "id": "analytics_hub",
            "name": "Executive Analytics & BI Hub",
            "category": "internal_app",
            "badge": "use analytics",
            "description": "Multi-dimensional SQLite analytics engine, KPIs, trend analysis, Pareto distribution, and executive reports.",
            "project": True,
            "open": "backend/main.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _ANALYTICS_BACKEND},
                {"path": "ui/app.mcn",       "content": _ANALYTICS_UI}
            ]
        },
        {
            "id": "item_manager",
            "name": "Inventory & Item Manager",
            "category": "internal_app",
            "badge": "SQLite CRUD",
            "description": "SQLite relational item storage, CRUD endpoints, and inventory UI.",
            "project": True,
            "open": "backend/main.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _ITEM_MANAGER_BACKEND},
                {"path": "ui/app.mcn",       "content": _ITEM_MANAGER_UI}
            ]
        },
        {
            "id": "crm",
            "name": "Customer CRM & Lead Engine",
            "category": "internal_app",
            "badge": "Enterprise",
            "description": "Multi-stage customer relationship manager, deal velocity, and contacts.",
            "project": True,
            "open": "ui/app.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _CRM_BACKEND},
                {"path": "ui/app.mcn",       "content": _CRM_UI}
            ]
        },
        {
            "id": "construction",
            "name": "Construction Project Manager",
            "category": "internal_app",
            "badge": "Heavy Duty",
            "description": "Job orders, site milestone tracking, compliance, and material inventory.",
            "project": True,
            "open": "ui/app.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _CONSTRUCTION_BACKEND},
                {"path": "ui/app.mcn",       "content": _CONSTRUCTION_UI}
            ]
        },
        {
            "id": "prompt_marketplace",
            "name": "Prompt & Workflow Marketplace",
            "category": "internal_app",
            "badge": "Marketplace",
            "description": "Creator marketplace to publish, test, fork, rate, and orchestrate AI prompts and multi-stage workflows.",
            "project": True,
            "open": "backend/main.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": _PROMPT_MARKETPLACE_BACKEND},
                {"path": "ui/app.mcn",       "content": _PROMPT_MARKETPLACE_UI}
            ]
        },

        # ═════════════════════════════════════════════════════════════════════
        # 3. Mobile Apps (Flutter) (category: flutter_app)
        # ═════════════════════════════════════════════════════════════════════
        {
            "id": "iot_smart_home",
            "name": "Smart Home IoT Controller",
            "category": "flutter_app",
            "badge": "Flutter UI",
            "description": "Cross-platform mobile control for climate, sensors, and lighting.",
            "project": True,
            "open": "ui/app.mcn",
            "files": [
                {"path": "backend/main.mcn", "content": (
                    '// Smart Home Mobile Backend\n'
                    'service iot_api\n'
                    '    port 8080\n'
                    '    endpoint get_home_state()\n'
                    '        return {\n'
                    '            living_room_temp: 22.5,\n'
                    '            humidity: 45,\n'
                    '            hvac_mode: "auto",\n'
                    '            lights_on: 4\n'
                    '        }\n'
                    '\n'
                    'log("⚡ Smart Home IoT Controller Backend Online")\n'
                )},
                {"path": "ui/app.mcn", "content": (
                    '// Smart Home Flutter UI\n'
                    'component HomeOverview\n'
                    '    state temp = 22.5\n'
                    '    render\n'
                    '        card\n'
                    '            card_header "Living Room Climate"\n'
                    '            stat label="Current Temp" value="22.5°C" change=0.8\n'
                    '            button "Toggle HVAC"\n'
                    '\n'
                    'app SmartHome\n'
                    '    title "Smart Home Controller"\n'
                    '    layout\n'
                    '        main\n'
                    '            HomeOverview\n'
                )},
                {"path": "mobile/ui-manifest.json", "content": json.dumps({
                    "name": "SmartHomeApp",
                    "components": {
                        "HomeOverview": {
                            "type": "container",
                            "props": {"className": "column"},
                            "children": [
                                {"type": "text", "props": {"tag": "h1", "content": "Living Room Hub"}},
                                {"type": "chart", "props": {"chartType": "Temperature & Humidity Trend"}},
                                {"type": "button", "props": {"text": "⚡ Toggle HVAC Climate Control"}},
                                {"type": "input", "props": {"placeholder": "Set Target Temperature (°C)..."}}
                            ]
                        }
                    },
                    "pages": {
                        "Smart Home": {
                            "components": ["HomeOverview"]
                        }
                    }
                }, indent=2)}
            ]
        },
        {
            "id": "expense_tracker",
            "name": "Mobile Expense & Budget Tracker",
            "category": "flutter_app",
            "badge": "Flutter UI",
            "description": "Mobile financial ledger, expense categorization, and charts.",
            "project": True,
            "open": "mobile/lib/main.dart",
            "files": [
                {"path": "backend/main.mcn", "content": (
                    '// Expense Tracker Backend\n'
                    'service expense_api\n'
                    '    port 8080\n'
                    '    endpoint get_budget_summary()\n'
                    '        return {\n'
                    '            total_budget: 4500,\n'
                    '            spent: 2130,\n'
                    '            remaining: 2370\n'
                    '        }\n'
                    '\n'
                    'log("⚡ Mobile Expense Tracker Backend Online")\n'
                )},
                {"path": "ui/app.mcn", "content": (
                    '// Expense Tracker Flutter UI\n'
                    'component BudgetOverview\n'
                    '    state remaining = "$2,370"\n'
                    '    render\n'
                    '        card\n'
                    '            card_header "Monthly Budget"\n'
                    '            stat label="Remaining Balance" value=remaining change=12.0\n'
                    '            button "+ Add Expense"\n'
                    '\n'
                    'app ExpenseApp\n'
                    '    title "Expense Tracker"\n'
                    '    layout\n'
                    '        main\n'
                    '            BudgetOverview\n'
                )},
                {"path": "mobile/ui-manifest.json", "content": json.dumps({
                    "name": "ExpenseTrackerApp",
                    "components": {
                        "ExpenseSummary": {
                            "type": "container",
                            "props": {"className": "column"},
                            "children": [
                                {"type": "text", "props": {"tag": "h1", "content": "Monthly Budget: $4,500"}},
                                {"type": "chart", "props": {"chartType": "Spending by Category"}},
                                {"type": "table", "props": {"columns": ["Date", "Merchant", "Category", "Amount"]}},
                                {"type": "button", "props": {"text": "+ Add New Transaction"}}
                            ]
                        }
                    },
                    "pages": {
                        "Budget": {
                            "components": ["ExpenseSummary"]
                        }
                    }
                }, indent=2)}
            ]
        },
        {
            "id": "field_inspector",
            "name": "Field Inspection & Site Audit",
            "category": "flutter_app",
            "badge": "Flutter UI",
            "description": "On-site quality checklist, safety audit forms, and sign-offs.",
            "project": True,
            "open": "mobile/lib/main.dart",
            "files": [
                {"path": "backend/main.mcn", "content": (
                    '// Field Inspection Backend\n'
                    'service audit_api\n'
                    '    port 8080\n'
                    '    endpoint list_checkpoints()\n'
                    '        return [\n'
                    '            {id: "CP1", item: "Fire Extinguisher Pressure", status: "Pass"},\n'
                    '            {id: "CP2", item: "Emergency Exit Lighting", status: "Pass"},\n'
                    '            {id: "CP3", item: "Hard Hat Zone Compliance", status: "Action Required"}\n'
                    '        ]\n'
                    '\n'
                    'log("⚡ Field Inspector Backend Online")\n'
                )},
                {"path": "ui/app.mcn", "content": (
                    '// Field Inspector UI\n'
                    'component InspectionView\n'
                    '    render\n'
                    '        card\n'
                    '            card_header "Site Safety Audit"\n'
                    '            button "Submit Checklist"\n'
                    '\n'
                    'app InspectorApp\n'
                    '    title "Field Inspector"\n'
                    '    layout\n'
                    '        main\n'
                    '            InspectionView\n'
                )},
                {"path": "mobile/ui-manifest.json", "content": json.dumps({
                    "name": "FieldInspectorApp",
                    "components": {
                        "SiteInspection": {
                            "type": "container",
                            "props": {"className": "column"},
                            "children": [
                                {"type": "text", "props": {"tag": "h1", "content": "Site Safety & Audit"}},
                                {"type": "table", "props": {"columns": ["Checkpoint", "Zone", "Status", "Inspector"]}},
                                {"type": "button", "props": {"text": "✓ Sign-off & Submit Report"}}
                            ]
                        }
                    },
                    "pages": {
                        "Inspection": {
                            "components": ["SiteInspection"]
                        }
                    }
                }, indent=2)}
            ]
        },

        # ═════════════════════════════════════════════════════════════════════
        # 4. Backend & Microservices (category: backend)
        # ═════════════════════════════════════════════════════════════════════
        {
            "id": "rest_service",
            "name": "High-Throughput REST Service",
            "category": "backend",
            "badge": "Microservice",
            "description": "Multi-endpoint JSON microservice with port binding and health check.",
            "file": "backend/main.mcn",
            "code": (
                '// Backend Microservice: Multi-endpoint REST Service\n'
                'service cloud_api\n'
                '    port 8080\n'
                '\n'
                '    endpoint get_health()\n'
                '        return {status: "healthy", uptime_seconds: 3600, nodes: 4}\n'
                '\n'
                '    endpoint list_metrics()\n'
                '        return [\n'
                '            {metric: "cpu_usage_pct", value: 14.2},\n'
                '            {metric: "memory_used_mb", value: 512},\n'
                '            {metric: "requests_per_sec", value: 1420}\n'
                '        ]\n'
                '\n'
                '    endpoint get_config()\n'
                '        return {env: "production", rate_limit: 5000, region: "us-east-1"}\n'
                '\n'
                'log("⚡ Microservice cloud_api initialized on port 8080")\n'
                'var health = get_health()\n'
                'log("Health Status: " + health.status + " (Nodes: " + str(health.nodes) + ")")\n'
            )
        },
        {
            "id": "iot_processor",
            "name": "IoT Telemetry Ingestion Hub",
            "category": "backend",
            "badge": "IoT Stream",
            "description": "Live sensor stream processing, threshold alerts, and device control.",
            "file": "backend/main.mcn",
            "code": (
                '// Backend Microservice: IoT Telemetry Processor\n'
                'service telemetry_service\n'
                '    port 9090\n'
                '\n'
                '    endpoint ingest_reading(sensor_id, reading_val)\n'
                '        var is_alert = reading_val > 30.0\n'
                '        if is_alert\n'
                '            log("⚠️ HIGH TEMPERATURE ALERT on sensor " + sensor_id + ": " + str(reading_val) + "°C")\n'
                '        return {sensor_id: sensor_id, alert: is_alert, logged: true}\n'
                '\n'
                'log("⚡ IoT Telemetry Ingestion Hub Online")\n'
                'var r1 = ingest_reading("sensor_office", 23.4)\n'
                'var r2 = ingest_reading("sensor_server_room", 34.8)\n'
                'log("Ingestion results: Office alert=" + str(r1.alert) + ", Server Room alert=" + str(r2.alert))\n'
            )
        },
        {
            "id": "ai_prompt_router",
            "name": "Enterprise AI Prompt Router",
            "category": "backend",
            "badge": "AI & RAG",
            "description": "Multi-agent prompt routing, template interpolation, and structured output.",
            "file": "backend/main.mcn",
            "code": (
                '// Backend Microservice: Enterprise AI Prompt Router\n'
                'service ai_router\n'
                '    port 8080\n'
                '\n'
                '    endpoint summarize_deal(company, value, notes)\n'
                '        var summary = "Deal Analysis for " + company + " ($" + str(value) + "): " + notes\n'
                '        return {\n'
                '            company: company,\n'
                '            pipeline_tier: value > 100000 ? "Enterprise" : "Mid-Market",\n'
                '            action_items: ["Schedule executive briefing", "Prepare custom architecture deck"]\n'
                '        }\n'
                '\n'
                'log("⚡ Enterprise AI Prompt Router Ready")\n'
                'var briefing = summarize_deal("Acme Health", 150000, "Interested in automated MCN cloud deployment.")\n'
                'log("AI Tier Assigned: " + briefing.pipeline_tier)\n'
            )
        }
    ])


@app.route("/api/components")
def get_components():
    return jsonify([
        {
            "name": "Button",
            "category": "primitives",
            "description": "Primary action button with multiple variants and loading states.",
            "mcnSnippet": 'ui("button", {label: "Submit", variant: "primary", action: "submit"})',
            "reactSnippet": '<Button variant="primary" size="md">Submit</Button>',
            "flutterSnippet": 'MCNButton(label: "Submit", variant: MCNButtonVariant.primary, onPressed: () {})',
        },
        {
            "name": "Input",
            "category": "primitives",
            "description": "Text input with optional label, hint, error, and prefix/suffix slots.",
            "mcnSnippet": 'ui("input", {name: "email", label: "Email", placeholder: "user@example.com"})',
            "reactSnippet": '<Input label="Email" placeholder="user@example.com" />',
            "flutterSnippet": 'MCNInput(label: "Email", hint: "user@example.com")',
        },
        {
            "name": "Badge",
            "category": "primitives",
            "description": "Status badge chip with optional dot indicator.",
            "mcnSnippet": 'ui("badge", {label: "Active", variant: "success", dot: true})',
            "reactSnippet": '<Badge variant="success" dot>Active</Badge>',
            "flutterSnippet": 'MCNBadge(label: "Active", variant: MCNBadgeVariant.success, dot: true)',
        },
        {
            "name": "Card",
            "category": "layout",
            "description": "Container card with title, description, and footer.",
            "mcnSnippet": 'ui("card", {title: "Overview", description: "Daily metrics"})',
            "reactSnippet": '<Card title="Overview" description="Daily metrics"><p>Content</p></Card>',
            "flutterSnippet": 'MCNCard(title: "Overview", description: "Daily metrics", child: Text("Content"))',
        },
        {
            "name": "Stat",
            "category": "data",
            "description": "Metric stat block with value, change percentage, and trend indicators.",
            "mcnSnippet": 'ui("stat", {label: "Active Users", value: "1,240", change: 12.5})',
            "reactSnippet": '<Stat label="Active Users" value="1,240" change={12.5} />',
            "flutterSnippet": 'MCNStat(label: "Active Users", value: "1,240", change: 12.5)',
        },
        {
            "name": "AIPrompt",
            "category": "ai",
            "description": "Multi-line AI assistant input with streaming and model controls.",
            "mcnSnippet": 'ui("ai_prompt", {placeholder: "Ask AI to generate..."})',
            "reactSnippet": '<AIPrompt placeholder="Ask AI..." onSubmit={(p) => generate(p)} />',
            "flutterSnippet": 'MCNAIPrompt(placeholder: "Ask AI...", onSubmit: (p) => generate(p))',
        },
        {
            "name": "StreamingText",
            "category": "ai",
            "description": "Animated typewriter text display for live AI response tokens.",
            "mcnSnippet": 'ui("streaming_text", {text: ai_output, streaming: is_loading})',
            "reactSnippet": '<StreamingText text={output} isStreaming={isStreaming} />',
            "flutterSnippet": 'MCNStreamingText(text: output, isStreaming: isStreaming)',
        },
        {
            "name": "OutputLog",
            "category": "ai",
            "description": "Catppuccin Mocha terminal log console with colored levels.",
            "mcnSnippet": 'ui("output_log", {lines: logs})',
            "reactSnippet": '<OutputLog lines={logs} autoScroll />',
            "flutterSnippet": 'MCNOutputLog(entries: logs)',
        }
    ])


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    _seed_workspace()
    import argparse
    parser = argparse.ArgumentParser(description="MCN Web Playground Server")
    parser.add_argument("-p", "--port", type=int, default=int(os.environ.get("MCN_PLAYGROUND_PORT", 5003)), help="Port to run server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind to")
    args, _ = parser.parse_known_args()
    port = args.port
    print(f"MCN Web Playground v2.2 — http://localhost:{port}")
    print(f"Workspace: {WORKSPACE}")
    app.run(debug=False, host=args.host, port=port, threaded=True)
