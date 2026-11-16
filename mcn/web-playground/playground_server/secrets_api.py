"""Workspace secrets (stored locally, exported to the environment)."""
import json
import os
from flask import Blueprint
from .core import (
    _WORKSPACES_DIR,
    is_hosted,
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


# ── Connectors: Google Sheets, HubSpot, SQL, Slack, ... (see connectors.py) ────

@bp.route("/api/connectors", methods=["GET"])
def connectors_list():
    from mcn.core_engine import connectors
    return jsonify({"success": True, "connectors": connectors.status(), "hosted": is_hosted()})


@bp.route("/api/connectors/<name>/settings", methods=["POST"])
def connectors_settings(name):
    """Save a connector's settings as workspace secrets (they reach your code through env)."""
    from mcn.core_engine import connectors
    entry = connectors.CATALOG.get(name)
    if not entry:
        return jsonify({"success": False, "error": "No such connector"}), 404
    if is_hosted():
        return jsonify({"success": False, "error": "On hosted Studio, add connector settings to your deployment's "
                                                   "environment instead (they'd be shared with other people here)."}), 403
    allowed = {k for k, _, _ in entry["settings"]}
    data = request.get_json(silent=True) or {}
    secrets = _load_secrets()
    for key, value in data.items():
        if key not in allowed:
            continue
        value = str(value or "").strip()
        if value:
            secrets[key] = value
            os.environ[key] = value
        else:
            secrets.pop(key, None)
            os.environ.pop(key, None)
    _save_secrets(secrets)
    return jsonify({"success": True, "connector": next(c for c in connectors.status() if c["name"] == name)})


@bp.route("/api/connectors/<name>/test", methods=["POST"])
def connectors_test(name):
    from mcn.core_engine import connectors
    try:
        return jsonify(connectors.test(name))
    except connectors.ConnectorError as exc:
        return jsonify({"success": False, "message": str(exc)})
    except Exception as exc:
        return jsonify({"success": False, "message": f"It didn't work: {exc}"})
