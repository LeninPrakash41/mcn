"""Device sign-in on hosted Studio, the MCN account server.

1. The desktop (installed Studio or `mcn login`) calls POST /api/device/code.
2. The person opens /device in their browser, signs in, and approves the code.
3. The desktop polls POST /api/device/token and receives a 30-day token tied
   to a session that admins (and the person) can revoke.
"""
import os

from flask import Blueprint

from . import device_store
from .core import (
    _THIS_DIR,
    _current_user,
    _make_token,
    auth_get_user,
    is_hosted,
    jsonify,
    request,
    send_from_directory,
)

bp = Blueprint("device", __name__)


def _hosted_only():
    if not is_hosted():
        return jsonify({"error": "Device sign-in is served by hosted Studio (MCN_STUDIO_MODE=hosted)."}), 404
    return None


@bp.route("/device")
def device_page():
    if not is_hosted():
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(_THIS_DIR, "device.html", max_age=0)


@bp.route("/api/device/code", methods=["POST"])
def device_code():
    err = _hosted_only()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    code = device_store.create_code(data.get("client_name", ""))
    # Behind a proxy, MCN_PUBLIC_URL gives the address people actually open
    base = (os.environ.get("MCN_PUBLIC_URL") or request.host_url).rstrip("/")
    code["verification_uri"] = f"{base}/device"
    code["verification_uri_complete"] = f"{base}/device?code={code['user_code']}"
    return jsonify(code)


@bp.route("/api/device/lookup", methods=["POST"])
def device_lookup():
    """What the approval page shows before the person decides."""
    err = _hosted_only()
    if err:
        return err
    if not _current_user():
        return jsonify({"error": "Sign in first", "needs_login": True}), 401
    info = device_store.lookup_user_code((request.get_json(silent=True) or {}).get("user_code", ""))
    if not info:
        return jsonify({"error": "That code is wrong or has expired. Start sign-in again on your computer."}), 404
    return jsonify({"success": True, **info})


@bp.route("/api/device/approve", methods=["POST"])
def device_approve():
    err = _hosted_only()
    if err:
        return err
    user = _current_user()
    if not user or not user.get("sub"):
        return jsonify({"error": "Sign in first", "needs_login": True}), 401
    data = request.get_json(silent=True) or {}
    result = device_store.decide(data.get("user_code", ""), user["sub"], approve=data.get("approve", True) is not False)
    if not result:
        return jsonify({"error": "That code is wrong or has expired. Start sign-in again on your computer."}), 404
    return jsonify({"success": True, "status": result["status"], "client_name": result["client_name"]})


@bp.route("/api/device/token", methods=["POST"])
def device_token():
    err = _hosted_only()
    if err:
        return err
    result = device_store.claim((request.get_json(silent=True) or {}).get("device_code", ""))
    status = result["status"]
    if status == "pending":
        return jsonify({"status": "pending"}), 428
    if status == "denied":
        return jsonify({"status": "denied", "error": "Sign-in was declined in the browser."}), 403
    if status == "expired":
        return jsonify({"status": "expired", "error": "The sign-in code expired. Start again."}), 410
    user = auth_get_user(result["user_id"]) or {}
    if not user:
        device_store.revoke(result["sid"])
        return jsonify({"status": "denied", "error": "That account no longer exists."}), 403
    token = _make_token({"sub": user["id"], "email": user.get("email", ""), "roles": user.get("roles", []),
                         "sid": result["sid"]}, expires_in=device_store.SESSION_TTL_S)
    return jsonify({"status": "approved", "token": token,
                    "user": {"id": user["id"], "email": user.get("email", ""), "roles": user.get("roles", [])}})


@bp.route("/api/device/sessions", methods=["GET"])
def my_sessions():
    """The computers signed in to this account."""
    err = _hosted_only()
    if err:
        return err
    user = _current_user()
    if not user:
        return jsonify({"error": "Sign in first", "needs_login": True}), 401
    return jsonify({"success": True, "sessions": device_store.sessions_for(user["sub"]),
                    "current": user.get("sid")})


@bp.route("/api/device/revoke", methods=["POST"])
def revoke_session():
    """Sign out a computer. With no sid, the computer making the call signs itself out."""
    err = _hosted_only()
    if err:
        return err
    user = _current_user()
    if not user:
        return jsonify({"error": "Sign in first", "needs_login": True}), 401
    sid = (request.get_json(silent=True) or {}).get("sid") or user.get("sid")
    if not sid:
        return jsonify({"error": "sid required"}), 400
    return jsonify({"success": device_store.revoke(sid, user_id=user["sub"])})
