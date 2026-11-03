"""Accounts, login and auth-guard validation."""
from flask import Blueprint
from .core import (
    _AUTH_AVAILABLE,
    _WORKSPACES_DIR,
    _current_user,
    auth_create_user,
    auth_get_user,
    auth_login,
    auth_verify_token,
    jsonify,
    request,
)
from .workspace_seed import (
    _seed_workspace,
)

bp = Blueprint("auth", __name__)

# ── Auth endpoints ────────────────────────────────────────────────────────────

@bp.route("/api/auth/register", methods=["POST"])
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


@bp.route("/api/auth/login", methods=["POST"])
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


@bp.route("/api/auth/me")
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


# ── Declarative Auth & RBAC Guard Validator ───────────────────────────────────

@bp.route("/api/auth/validate_guard", methods=["POST"])
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
