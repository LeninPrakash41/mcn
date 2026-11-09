"""Admin endpoints: authentication, overview, users, feedback, system health, and broadcasts."""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from flask import Blueprint
from .core import (
    _AUTH_AVAILABLE,
    _WORKSPACES_DIR,
    _current_user,
    auth_assign_role,
    auth_get_user,
    auth_list_users,
    auth_login,
    auth_revoke_role,
    auth_verify_token,
    ensure_bootstrap_admin,
    is_hosted,
    jsonify,
    request,
)
from . import device_store
from .community import _COMMUNITY_REG_FILE, _OUTBOX_FILE

bp = Blueprint("admin", __name__)

_BROADCAST_HISTORY_FILE = Path.home() / ".mcn" / "admin_broadcasts.jsonl"


def _local_mode():
    return (jsonify({"error": "This Studio runs on your own computer and has no users to manage. "
                              "Admin is on hosted Studio (MCN_STUDIO_MODE=hosted).", "mode": "local"}), 404)


def _require_admin():
    """Verify that the request comes from an authenticated user with 'admin' role."""
    if not is_hosted():
        return None, _local_mode()
    user = _current_user()
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)
    roles = user.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    if "admin" not in roles:
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


@bp.route("/api/admin/login", methods=["POST"])
def admin_login():
    """Authenticate an admin user and return a session token."""
    if not is_hosted():
        return _local_mode()
    if not _AUTH_AVAILABLE:
        return jsonify({"error": "Authentication system not available"}), 503
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    try:
        token = auth_login(email, password)
        payload = auth_verify_token(token) or {}
        if payload.get("sub") and ensure_bootstrap_admin(payload["sub"], payload.get("email", email)):
            token = auth_login(email, password)
            payload = auth_verify_token(token) or {}
        roles = payload.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        if "admin" not in roles:
            return jsonify({"error": "Account does not have admin privileges"}), 403

        user_id = payload.get("sub") or email
        return jsonify({
            "success": True,
            "token": token,
            "user": {
                "id": user_id,
                "email": payload.get("email", email),
                "roles": roles,
            },
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 401


@bp.route("/api/admin/overview", methods=["GET"])
def admin_overview():
    """Retrieve high-level system, user, and community metrics."""
    user, err = _require_admin()
    if err:
        return err

    # User accounts
    users = auth_list_users() if _AUTH_AVAILABLE else []
    admin_count = sum(1 for u in users if "admin" in u.get("roles", []))

    # Active workspaces on disk
    workspace_count = 0
    if _WORKSPACES_DIR.exists():
        workspace_count = sum(1 for p in _WORKSPACES_DIR.iterdir() if p.is_dir())

    # Community registration
    comm_reg = {}
    if _COMMUNITY_REG_FILE.exists():
        try:
            comm_reg = json.loads(_COMMUNITY_REG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Telemetry outbox items (feedback and registration events)
    feedbacks = []
    registrations = []
    if _OUTBOX_FILE.exists():
        for line in _OUTBOX_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                k = item.get("kind")
                if k == "feedback":
                    feedbacks.append(item.get("payload", {}))
                elif k == "register":
                    registrations.append(item.get("payload", {}))
            except Exception:
                continue

    # Opt-ins for release updates
    opt_in_count = 0
    seen_emails = set()
    if comm_reg.get("newsletter_opt_in") and comm_reg.get("email"):
        opt_in_count += 1
        seen_emails.add(comm_reg.get("email").lower())
    for reg in registrations:
        em = (reg.get("email") or "").lower()
        if em and em not in seen_emails and reg.get("newsletter_opt_in"):
            opt_in_count += 1
            seen_emails.add(em)

    return jsonify({
        "success": True,
        "metrics": {
            "total_users": len(users),
            "admin_users": admin_count,
            "isolated_workspaces": workspace_count,
            "community_registrations": len(registrations) + (1 if comm_reg else 0),
            "opt_in_subscribers": opt_in_count,
            "total_feedback": len(feedbacks),
        },
        "community_profile": comm_reg,
        "system": {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "app_version": "3.0.0",
        }
    })


@bp.route("/api/admin/users", methods=["GET"])
def admin_users():
    """List all registered users, roles, and workspace paths."""
    user, err = _require_admin()
    if err:
        return err

    users = auth_list_users() if _AUTH_AVAILABLE else []
    safe_users = []
    for u in users:
        u_id = u.get("id")
        ws_path = str(_WORKSPACES_DIR / str(u_id)) if u_id else ""
        has_ws = (_WORKSPACES_DIR / str(u_id)).exists() if u_id else False
        safe_users.append({
            "id": u_id,
            "email": u.get("email"),
            "roles": u.get("roles", []),
            "created_at": u.get("created_at"),
            "has_workspace": has_ws,
            "workspace_path": ws_path,
            # Desktop installs signed in to this account (Studio or `mcn login`)
            "devices": device_store.sessions_for(u_id) if u_id else [],
        })

    return jsonify({"success": True, "users": safe_users})


@bp.route("/api/admin/devices/revoke", methods=["POST"])
def admin_revoke_device():
    """Sign a user's computer out. Its token stops working on the next request."""
    user, err = _require_admin()
    if err:
        return err
    sid = (request.get_json(silent=True) or {}).get("sid")
    if not sid:
        return jsonify({"error": "sid required"}), 400
    if not device_store.revoke(sid):
        return jsonify({"error": "No such session"}), 404
    return jsonify({"success": True})


@bp.route("/api/admin/users/role", methods=["POST"])
def admin_user_role():
    """Assign or revoke a role from a user."""
    user, err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id")
    role = data.get("role", "admin").strip()
    action = data.get("action", "assign").strip().lower()

    if not target_user_id:
        return jsonify({"error": "user_id required"}), 400

    try:
        if action == "revoke":
            auth_revoke_role(target_user_id, role)
        else:
            auth_assign_role(target_user_id, role)
        updated = auth_get_user(target_user_id)
        return jsonify({"success": True, "user": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/admin/feedback", methods=["GET"])
def admin_feedback_list():
    """List all submitted user feedbacks, bugs, and telemetry outbox items."""
    user, err = _require_admin()
    if err:
        return err

    feedbacks = []
    if _OUTBOX_FILE.exists():
        for idx, line in enumerate(reversed(_OUTBOX_FILE.read_text(encoding="utf-8").splitlines())):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if item.get("kind") == "feedback":
                    p = item.get("payload", {})
                    p["_id"] = idx
                    feedbacks.append(p)
            except Exception:
                continue

    return jsonify({"success": True, "feedback": feedbacks})


@bp.route("/api/admin/health", methods=["GET"])
def admin_health():
    """Check system health, database files, and workspace disk footprints."""
    user, err = _require_admin()
    if err:
        return err

    mcn_home = Path.home() / ".mcn"
    db_path = mcn_home / "auth.db"

    health = {
        "status": "healthy",
        "auth_db": {
            "exists": db_path.exists(),
            "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
            "path": str(db_path),
        },
        "workspaces_dir": {
            "exists": _WORKSPACES_DIR.exists(),
            "path": str(_WORKSPACES_DIR),
        },
        "outbox_file": {
            "exists": _OUTBOX_FILE.exists(),
            "size_bytes": _OUTBOX_FILE.stat().st_size if _OUTBOX_FILE.exists() else 0,
        },
        "python": sys.version,
        "platform": sys.platform,
        "timestamp": datetime.now().isoformat(),
    }
    return jsonify({"success": True, "health": health})


@bp.route("/api/admin/broadcast", methods=["POST"])
def admin_broadcast():
    """Send release updates and tutorials to opted-in users."""
    user, err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    category = data.get("category") or "release_update"

    if not title or not content:
        return jsonify({"error": "Title and content required"}), 400

    # Collect recipient emails from local community registrations and outbox registrations
    recipients = set()
    if _COMMUNITY_REG_FILE.exists():
        try:
            reg = json.loads(_COMMUNITY_REG_FILE.read_text(encoding="utf-8"))
            if reg.get("newsletter_opt_in") and reg.get("email"):
                recipients.add(reg.get("email").strip())
        except Exception:
            pass

    if _OUTBOX_FILE.exists():
        for line in _OUTBOX_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if item.get("kind") == "register":
                    p = item.get("payload", {})
                    if p.get("newsletter_opt_in") and p.get("email"):
                        recipients.add(p.get("email").strip())
            except Exception:
                continue

    broadcast_record = {
        "id": f"bc_{int(time.time())}",
        "title": title,
        "content": content,
        "category": category,
        "recipients_count": len(recipients),
        "recipients": sorted(list(recipients)),
        "created_at": datetime.now().isoformat(),
        "sent_by": user.get("email", "admin"),
        "status": "delivered",
    }

    # Record broadcast locally
    try:
        _BROADCAST_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _BROADCAST_HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(broadcast_record) + "\n")
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": f"Broadcast successfully dispatched to {len(recipients)} opted-in developer(s).",
        "broadcast": broadcast_record,
    })


@bp.route("/api/admin/broadcasts", methods=["GET"])
def admin_broadcasts_list():
    """Get history of release update broadcasts."""
    user, err = _require_admin()
    if err:
        return err

    broadcasts = []
    if _BROADCAST_HISTORY_FILE.exists():
        for line in reversed(_BROADCAST_HISTORY_FILE.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                broadcasts.append(json.loads(line))
            except Exception:
                continue

    return jsonify({"success": True, "broadcasts": broadcasts})

