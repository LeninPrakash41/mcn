"""Workspace file listing, reading, saving and reset."""
import os
from pathlib import Path
from . import core
from flask import Blueprint
from .core import (
    _current_user,
    _request_workspace,
    _safe_path,
    _safe_path_for,
    _stop_process,
    jsonify,
    request,
)
from .workspace_seed import (
    _seed_workspace,
)

bp = Blueprint("workspace", __name__)

@bp.route("/api/workspace/info")
def workspace_info():
    """Which folder Studio is editing, and whether it's the user's own project (templates can't replace it)."""
    ws = _request_workspace()
    own = bool(os.environ.get("MCN_WORKSPACE")) and ws == core.WORKSPACE
    home = str(Path.home())
    path = str(ws)
    return jsonify({"own_project": own, "path": "~" + path[len(home):] if path.startswith(home) else path})


@bp.route("/api/workspace/reset", methods=["POST"])
def workspace_reset():
    """Wipe workspace MCN source files and re-seed with defaults (keeps frontend/)."""
    import shutil
    ws   = _request_workspace()
    data = request.get_json(silent=True) or {}
    files_payload = data.get("files")  # [{path, content}, ...] for project templates
    if os.environ.get("MCN_WORKSPACE") and ws == core.WORKSPACE:
        return jsonify({"success": False, "error":
            "Studio is open on your own project folder, so templates can't replace its files. "
            "Run `mcn studio` without a folder to try templates in Studio's scratch workspace."}), 409
    try:
        # Stop any running dev server and backend before wiping the workspace
        _stop_process(core._dev_server);  core._dev_server  = None
        _stop_process(core._mcn_backend); core._mcn_backend = None

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


@bp.route("/api/workspace/files")
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


@bp.route("/api/workspace/file")
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


@bp.route("/api/workspace/file", methods=["POST"])
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


@bp.route("/api/frontend/file")
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
