"""Shared state and helpers for the MCN playground server."""

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

_SERVER_DIR = Path(__file__).resolve().parent.parent   # mcn/web-playground
_DEFAULT_WORKSPACE = _SERVER_DIR / "workspace"
_ENV_WORKSPACE = os.environ.get("MCN_WORKSPACE")
# Studio simulates every device, even ones declared with driver: "gpio" or "serial"
os.environ.setdefault("MCN_IOT_SIMULATE", "1")

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
    """Resolve a relative path against the request's workspace; raise ValueError on traversal."""
    return _safe_path_for(rel, _request_workspace())

# ── Package root in sys.path ──────────────────────────────────────────────────

_THIS_DIR    = str(_SERVER_DIR)
_PACKAGE_DIR = os.path.dirname(_THIS_DIR)
_ROOT_DIR    = os.path.dirname(_PACKAGE_DIR)
for _p in (_PACKAGE_DIR, _ROOT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Flask ─────────────────────────────────────────────────────────────────────

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask import current_app, has_app_context, has_request_context
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
        auth_get_user, auth_require, auth_list_users,
        auth_assign_role, auth_revoke_role, _make_token
    )
    _AUTH_AVAILABLE = True
except ImportError:
    try:
        from core_engine.auth_primitives import (  # type: ignore
            auth_create_user, auth_login, auth_verify_token,
            auth_get_user, auth_require, auth_list_users,
            auth_assign_role, auth_revoke_role, _make_token
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
    # Previews (iframes) and downloads can't send a header, so hosted Studio also
    # sets a SameSite=Strict cookie. It's only read for GET, which changes nothing.
    if request.method == "GET":
        return (request.cookies.get("mcn_token") or "").strip()
    return ""


# ── Studio mode ───────────────────────────────────────────────────────────────
# local  (default): Studio installed on someone's own computer. One person, no
#                   accounts here; they can sign in to their MCN account server.
# hosted          : Studio on a shared server (MCN_STUDIO_MODE=hosted). Everyone
#                   signs in, gets their own workspace, and admins manage users.
#                   This server is also the account server desktop installs sign in to.

def studio_mode() -> str:
    return "hosted" if os.environ.get("MCN_STUDIO_MODE", "").strip().lower() == "hosted" else "local"


def is_hosted() -> bool:
    return studio_mode() == "hosted"


def _env_list(name: str) -> list[str]:
    return [v.strip().lower() for v in os.environ.get(name, "").split(",") if v.strip()]


def signup_allowed(email: str) -> bool:
    """MCN_STUDIO_SIGNUP_DOMAINS limits who can create an account (e.g. "college.edu,company.com")."""
    domains = _env_list("MCN_STUDIO_SIGNUP_DOMAINS")
    email = str(email).strip().lower()
    return not domains or email.rsplit("@", 1)[-1] in domains or email in _env_list("MCN_ADMIN_EMAILS")


def ensure_bootstrap_admin(user_id: str, email: str) -> bool:
    """Emails listed in MCN_ADMIN_EMAILS get the admin role when they register or sign in.
    Returns True if the role was just added (the caller should issue a fresh token)."""
    if not _AUTH_AVAILABLE or str(email).strip().lower() not in _env_list("MCN_ADMIN_EMAILS"):
        return False
    user = auth_get_user(user_id) or {}
    if "admin" in (user.get("roles") or []):
        return False
    auth_assign_role(user_id, "admin")
    return True


def _current_user() -> dict | None:
    """Return the signed-in user's token payload, or None.
    Local Studio has no accounts of its own, so it never has a current user."""
    if not _AUTH_AVAILABLE or not is_hosted():
        return None
    tok = _bearer_token()
    if not tok:
        return None
    payload = auth_verify_token(tok)
    if payload and payload.get("sid"):
        # A desktop sign-in: valid only while its session hasn't been revoked
        from . import device_store
        if not device_store.session_active(payload["sid"]):
            return None
    return payload


def _default_workspace() -> Path:
    """The app's shared workspace (app.config["WORKSPACE"]), or the process default."""
    if has_app_context():
        return Path(current_app.config.get("WORKSPACE", WORKSPACE))
    return WORKSPACE


def _request_workspace() -> Path:
    """Return the workspace directory for the current request.
    Authenticated users get their own isolated dir; anonymous share the default."""
    if not has_request_context():
        return _default_workspace()
    user = _current_user()
    if user and user.get("sub"):
        ws = _WORKSPACES_DIR / user["sub"]
        ws.mkdir(parents=True, exist_ok=True)
        return ws
    return _default_workspace()


def _safe_path_for(rel: str, ws: Path) -> Path:
    """Resolve rel against ws; raise on traversal."""
    p = (ws / rel).resolve()
    if not str(p).startswith(str(ws.resolve())):
        raise ValueError(f"Path traversal attempt: {rel!r}")
    return p

_MAX_CODE_BYTES = 128 * 1024   # 128 KB
_EXEC_TIMEOUT_S = 10

# Dev server process (module-level singleton)
_dev_server: subprocess.Popen | None = None
_mcn_backend: subprocess.Popen | None = None
_DEV_PORT     = 5174
# MCN_BACKEND_PORT moves the preview backend when 8080 is taken by something else
_BACKEND_PORT = int(os.environ.get("MCN_BACKEND_PORT") or 8080)

# Demo devices seeded into the shared IoT registry (see simulators._iot)
# Demo devices so the IoT panel has something to show before a script registers its own
_SIMULATED_DEVICES = {
    "office_temp": {"type": "temperature_sensor", "location": "office"},
    "office_occupancy": {"type": "motion_sensor", "location": "office"},
    "hvac_system": {"type": "hvac_controller", "location": "office"},
}


def seed_demo_devices(registry) -> None:
    for device_id, config in _SIMULATED_DEVICES.items():
        if device_id not in registry.devices:
            registry.register(device_id, config)
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


# ── Dev server ────────────────────────────────────────────────────────────────

def _stop_process(proc):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
