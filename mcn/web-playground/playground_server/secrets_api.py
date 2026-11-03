"""Workspace secrets (stored locally, exported to the environment)."""
import json
import os
from flask import Blueprint
from .core import (
    _WORKSPACES_DIR,
    jsonify,
    request,
)

bp = Blueprint("secrets_api", __name__)

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

@bp.route("/api/secrets", methods=["GET"])
def get_secrets():
    secrets = _load_secrets()
    # Mask values for security
    masked = {k: ("*" * len(str(v)) if len(str(v)) <= 4 else str(v)[:2] + "*" * 6 + str(v)[-2:]) for k, v in secrets.items()}
    return jsonify({"success": True, "secrets": masked})

@bp.route("/api/secrets", methods=["POST"])
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

@bp.route("/api/secrets/<key>", methods=["DELETE"])
def delete_secret(key):
    secrets = _load_secrets()
    if key in secrets:
        del secrets[key]
        _save_secrets(secrets)
        os.environ.pop(key, None)
    return jsonify({"success": True})
