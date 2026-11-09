"""Sign in from installed (local) Studio to the person's MCN account server.

The device code flow runs here, server side, so the token is stored in
~/.mcn/credentials.json (shared with `mcn login`) and never reaches the page.
"""
from flask import Blueprint

from .core import is_hosted, jsonify, request

try:
    from mcn.core_engine import account
except ImportError:  # pragma: no cover
    from core_engine import account  # type: ignore

bp = Blueprint("account_api", __name__)


def _local_only():
    if is_hosted():
        return jsonify({"error": "Hosted Studio signs people in directly; see /api/auth/login."}), 404
    return None


def _public(info: dict) -> dict:
    """Account status without anything secret."""
    user = info.get("user") or {}
    return {
        "signed_in": bool(info.get("signed_in")),
        "account_url": info.get("account_url", ""),
        "configured": bool(info.get("account_url")),
        "user": {"id": user.get("id"), "email": user.get("email", ""), "roles": user.get("roles", [])}
        if info.get("signed_in") else None,
        "offline": bool(info.get("offline")),
        "signed_out_remotely": bool(info.get("signed_out_remotely")),
    }


@bp.route("/api/account", methods=["GET"])
def account_status():
    err = _local_only()
    if err:
        return err
    return jsonify(_public(account.status(refresh=request.args.get("refresh") == "1")))


@bp.route("/api/account/login", methods=["POST"])
def account_login():
    err = _local_only()
    if err:
        return err
    try:
        started = account.start_login()
    except account.AccountError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({k: started.get(k) for k in (
        "device_code", "user_code", "verification_uri", "verification_uri_complete",
        "expires_in", "interval", "account_url")})


@bp.route("/api/account/poll", methods=["POST"])
def account_poll():
    err = _local_only()
    if err:
        return err
    device_code = (request.get_json(silent=True) or {}).get("device_code", "")
    if not device_code:
        return jsonify({"error": "device_code required"}), 400
    try:
        result = account.poll_login(device_code)
    except account.AccountError as e:
        return jsonify({"status": "error", "error": str(e)}), 502
    if result["status"] == "approved":
        return jsonify({"status": "approved", **_public(account.status())})
    return jsonify(result)


@bp.route("/api/account/logout", methods=["POST"])
def account_logout():
    err = _local_only()
    if err:
        return err
    return jsonify({"success": True, **account.logout()})
