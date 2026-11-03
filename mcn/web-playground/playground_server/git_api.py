"""Version control for workspaces."""
from flask import Blueprint
from .core import (
    _WORKSPACES_DIR,
    jsonify,
    request,
)

bp = Blueprint("git_api", __name__)

# ── Version Control endpoints ─────────────────────────────────────────────────

@bp.route("/api/git/status", methods=["GET"])
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

@bp.route("/api/git/commit", methods=["POST"])
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

@bp.route("/api/git/push", methods=["POST"])
def git_push():
    import subprocess
    try:
        subprocess.check_call(["git", "push"], cwd=_WORKSPACES_DIR)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
