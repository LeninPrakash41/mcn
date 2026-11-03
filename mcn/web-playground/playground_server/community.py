"""Community registration, telemetry and feedback."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Blueprint
from .core import (
    jsonify,
    request,
)

bp = Blueprint("community", __name__)

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

_OUTBOX_FILE = Path.home() / ".mcn" / "telemetry_outbox.jsonl"


def _queue(kind: str, payload: dict) -> None:
    """Keep every submission locally until it has been delivered."""
    _OUTBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUTBOX_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, "payload": payload}) + "\n")


def _endpoint(kind: str) -> str:
    return os.environ.get("MCN_TELEMETRY_ENDPOINT" if kind == "register" else "MCN_FEEDBACK_ENDPOINT", "")


def _post(url: str, payload: dict) -> bool:
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "MCN-Studio/3.0.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _flush_outbox() -> dict:
    """Send queued submissions to their configured endpoints; keep what fails.
    Returns counts so callers can tell the user what actually happened."""
    if not _OUTBOX_FILE.exists():
        return {"sent": 0, "pending": 0}
    sent, remaining = 0, []
    for line in _OUTBOX_FILE.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = _endpoint(item["kind"])
        if url and _post(url, item["payload"]):
            sent += 1
        else:
            remaining.append(line)
    _OUTBOX_FILE.write_text("".join(l + "\n" for l in remaining), encoding="utf-8")
    return {"sent": sent, "pending": len(remaining)}


def _submit(kind: str, payload: dict) -> dict:
    _queue(kind, payload)
    result = _flush_outbox()
    delivered = bool(_endpoint(kind)) and result["pending"] == 0
    return {"delivered": delivered, "pending": result["pending"], "endpoint_configured": bool(_endpoint(kind))}

@bp.route("/api/telemetry/status")
def telemetry_status():
    reg = _get_local_registration()
    pending = len(_OUTBOX_FILE.read_text(encoding="utf-8").splitlines()) if _OUTBOX_FILE.exists() else 0
    return jsonify({
        "registered": bool(reg.get("email")),
        "user": reg,
        "pending_submissions": pending,
    })

@bp.route("/api/telemetry/register", methods=["POST"])
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
        "newsletter_opt_in": bool(data.get("newsletter_opt_in", False)),   # consent is opt-in
        "registered_at": datetime.now().isoformat()
    }
    _save_local_registration(profile)
    status = _submit("register", profile)
    return jsonify({
        "success": True,
        "message": ("Registration successful! Welcome to the MCN Developer Community."
                    if status["delivered"] else "Registration saved on this computer."),
        "profile": profile,
        **status,
    })

@bp.route("/api/telemetry/feedback", methods=["POST"])
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

    status = _submit("feedback", payload)
    return jsonify({
        "success": True,
        "message": ("Thank you! Your feedback was sent to the MCN team." if status["delivered"] else
                    "Thank you! Your feedback is saved and will be sent when a feedback endpoint is reachable."),
        **status,
    })
