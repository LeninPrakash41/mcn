"""
The MCN Developer Club API: join with a profile, launch the workspace's app for
review, the public marketplace and certificate verification, and review tools.

The club lives on the MCN account server (hosted Studio). Installed Studio forwards
every call there with the signed-in account (`mcn login` / Sign in), attaching the
local workspace's files when you launch a project.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from flask import Blueprint, redirect, send_from_directory

from . import club_store as store
from .core import _current_user, _request_workspace, is_hosted, jsonify, request

bp = Blueprint("club", __name__)
_THIS_DIR = Path(__file__).resolve().parent.parent
_AI_CALL = re.compile(r"\b(ai|llm|agent_run|classify|extract|rag|embed|vector_search|fine_tune)\s*\(")


# ── Who's asking ─────────────────────────────────────────────────────────────

def _roles(user) -> list:
    roles = (user or {}).get("roles") or []
    return [roles] if isinstance(roles, str) else list(roles)


def _is_reviewer(user) -> bool:
    return bool({"admin", "reviewer"} & set(_roles(user)))


def _signed_in():
    user = _current_user()
    if not user or not user.get("sub"):
        return None, (jsonify({"error": "Sign in to use the MCN Developer Club"}), 401)
    return user, None


def _reviewer():
    user, err = _signed_in()
    if err:
        return None, err
    if not _is_reviewer(user):
        return None, (jsonify({"error": "Only club reviewers can do this"}), 403)
    return user, None


def _bad(exc: Exception, status: int = 400):
    return jsonify({"error": str(exc)}), status


# ── Installed Studio: forward to the account server ──────────────────────────

def _account():
    try:
        from mcn.core_engine import account
    except ImportError:  # pragma: no cover
        from core_engine import account  # type: ignore
    return account


def _forward(method: str, path: str, payload: dict | None = None):
    account = _account()
    url = account.account_url().rstrip("/")
    if not url:
        return jsonify({"error": "The MCN Developer Club is on your MCN account server. Set it with "
                                 "`mcn config set account_url https://...`, then Sign in.", "local": True}), 409
    token = account.token()
    query = request.query_string.decode()
    try:
        status, body = account._request(method, f"{url}{path}" + (f"?{query}" if query else ""), payload, token)
    except account.AccountError as exc:
        return jsonify({"error": str(exc)}), 502
    if status == 401 and not token:
        body = {"error": "Sign in to your MCN account (the Sign In button) to use the club"}
    body.setdefault("club_url", f"{url}/club")
    return jsonify(body), status


# ── Workspace files and their checks ─────────────────────────────────────────

def _workspace_files() -> dict:
    ws = _request_workspace()
    read = lambda rel: (ws / rel).read_text(encoding="utf-8") if (ws / rel).exists() else ""
    return {"backend": read("backend/main.mcn"), "ui": read("ui/app.mcn")}


def _check(files: dict) -> dict:
    """Static checks only: submitted code is never run on the server."""
    from mcn.core_engine.app_map import build_map
    from mcn.core_engine.type_checker import Severity, check_source
    with tempfile.TemporaryDirectory(prefix="mcn_club_") as tmp:
        root = Path(tmp)
        for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
            if files.get(key, "").strip():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(files[key], encoding="utf-8")
        app = build_map(root)
    type_errors = []
    for key in ("backend", "ui"):
        if files.get(key, "").strip():
            type_errors += [f"{key}: line {i.line}: {i.message}" for i in check_source(files[key])
                            if i.severity == Severity.ERROR]
    summary = app["summary"]
    return {"screens": summary.get("screens", 0), "endpoints": summary.get("endpoints", 0),
            "tables": summary.get("tables", 0), "tests": summary.get("tests", 0), "modules": summary.get("modules", 0),
            "uses_ai": bool(_AI_CALL.search(files.get("backend", "") + files.get("ui", ""))),
            "parse_errors": app["errors"], "type_errors": type_errors[:20],
            "issues": [i["message"] for i in app["issues"] if i.get("severity") != "note"][:20]}


# ── Pages ────────────────────────────────────────────────────────────────────

@bp.route("/club")
@bp.route("/club/")
@bp.route("/club/project/<project_id>")
@bp.route("/club/certificate/<code>")
def club_page(project_id: str = "", code: str = ""):
    if not is_hosted():
        url = _account().account_url().rstrip("/")
        if url:
            return redirect(url + request.path)
    return send_from_directory(_THIS_DIR, "club.html", max_age=0)


# ── Everyone ─────────────────────────────────────────────────────────────────

@bp.route("/api/club/info")
def club_info():
    if not is_hosted():
        return _forward("GET", "/api/club/info")
    user = _current_user()
    return jsonify({"awards": store.AWARDS, "spotlights": store.SPOTLIGHTS, "kinds": store.KINDS,
                    "order": {"awards": list(store.AWARDS), "spotlights": list(store.SPOTLIGHTS), "kinds": list(store.KINDS)},
                    "signed_in": bool(user), "member": store.member(user["sub"]) if user else None,
                    "is_reviewer": _is_reviewer(user), "club_url": request.host_url.rstrip("/") + "/club"})


@bp.route("/api/club/marketplace")
def club_marketplace():
    if not is_hosted():
        return _forward("GET", "/api/club/marketplace")
    a = request.args
    return jsonify({"projects": store.marketplace(a.get("award", ""), a.get("spotlight", ""), a.get("kind", ""),
                                                  a.get("q", "")[:80])})


@bp.route("/api/club/projects/<project_id>")
def club_project(project_id):
    if not is_hosted():
        return _forward("GET", f"/api/club/projects/{project_id}")
    user = _current_user()
    found = store.project(project_id, include_source=True)
    mine = bool(user and found and found["user_id"] == user.get("sub"))
    if not found or (found["status"] != "approved" and not mine and not _is_reviewer(user)):
        return jsonify({"error": "No such project in the marketplace"}), 404
    return jsonify({"project": found})


@bp.route("/api/club/certificates/<code>")
def club_certificate(code):
    if not is_hosted():
        return _forward("GET", f"/api/club/certificates/{code}")
    cert = store.certificate(code.strip().upper())
    if not cert:
        return jsonify({"error": "No certificate has this code", "valid": False}), 404
    return jsonify({"valid": True, "certificate": cert})


# ── Members ──────────────────────────────────────────────────────────────────

@bp.route("/api/club/join", methods=["POST"])
def club_join():
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", "/api/club/join", data)
    user, err = _signed_in()
    if err:
        return err
    try:
        return jsonify({"member": store.join(user["sub"], user.get("email", ""), data)})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/me")
def club_me():
    if not is_hosted():
        return _forward("GET", "/api/club/me")
    user, err = _signed_in()
    if err:
        return err
    return jsonify({"member": store.member(user["sub"]), "projects": store.projects_of(user["sub"]),
                    "certificates": store.certificates_of(user["sub"]), "is_reviewer": _is_reviewer(user)})


@bp.route("/api/club/submit", methods=["POST"])
def club_submit():
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", "/api/club/submit", {**data, **_workspace_files()})
    user, err = _signed_in()
    if err:
        return err
    files = {"backend": data.get("backend"), "ui": data.get("ui")} if ("backend" in data or "ui" in data) \
        else _workspace_files()
    checks = _check({k: v or "" for k, v in files.items()})
    if checks["parse_errors"]:
        return jsonify({"error": "Fix these errors before launching: " + "; ".join(checks["parse_errors"][:3]),
                        "checks": checks}), 400
    try:
        submitted = store.submit(user["sub"], {**data, **files}, checks)
    except store.ClubError as exc:
        return _bad(exc)
    submitted.pop("backend", None)
    submitted.pop("ui", None)
    return jsonify({"project": submitted, "checks": checks})


@bp.route("/api/club/projects/<project_id>/withdraw", methods=["POST"])
def club_withdraw(project_id):
    if not is_hosted():
        return _forward("POST", f"/api/club/projects/{project_id}/withdraw", {})
    user, err = _signed_in()
    if err:
        return err
    try:
        return jsonify({"project": store.withdraw(user["sub"], project_id)})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/projects/<project_id>/open", methods=["POST"])
def club_open(project_id):
    """Copy an approved project's app into this Studio's workspace, to try it or build on it."""
    if is_hosted():
        found = store.project(project_id, include_source=True)
        user = _current_user()
        mine = bool(user and found and found["user_id"] == user.get("sub"))
        if not found or (found["status"] != "approved" and not mine):
            return jsonify({"error": "No such project in the marketplace"}), 404
    else:
        resp, status = _forward("GET", f"/api/club/projects/{project_id}")
        if status != 200:
            return resp, status
        found = resp.get_json()["project"]
    ws = _request_workspace()
    for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
        if found.get(key):
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(found[key], encoding="utf-8")
    return jsonify({"success": True, "files": ["backend/main.mcn", "ui/app.mcn"], "title": found["title"]})


# ── Reviewers ────────────────────────────────────────────────────────────────

@bp.route("/api/club/review")
def club_review_queue():
    if not is_hosted():
        return _forward("GET", "/api/club/review")
    user, err = _reviewer()
    if err:
        return err
    return jsonify({"queue": store.queue(), "stats": store.stats()})


@bp.route("/api/club/review/<project_id>", methods=["GET", "POST"])
def club_review(project_id):
    if not is_hosted():
        return _forward(request.method, f"/api/club/review/{project_id}", request.get_json(silent=True))
    user, err = _reviewer()
    if err:
        return err
    if request.method == "GET":
        found = store.project(project_id, include_source=True)
        if not found:
            return jsonify({"error": "No such project"}), 404
        return jsonify({"project": found, "checks": _check({"backend": found.get("backend") or "",
                                                             "ui": found.get("ui") or ""})})
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"project": store.decide(project_id, user.get("email", ""), data.get("decision", ""),
                                                data.get("notes", ""))})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/review/<project_id>/award", methods=["POST"])
def club_award(project_id):
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", f"/api/club/review/{project_id}/award", data)
    user, err = _reviewer()
    if err:
        return err
    try:
        if data.get("remove"):
            return jsonify({"project": store.remove_award(project_id, data.get("category", ""), user.get("email", ""))})
        return jsonify({"project": store.give_award(project_id, data.get("category", ""), user.get("email", ""),
                                                    data.get("note", ""))})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/review/<project_id>/spotlight", methods=["POST"])
def club_spotlight(project_id):
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", f"/api/club/review/{project_id}/spotlight", data)
    user, err = _reviewer()
    if err:
        return err
    try:
        return jsonify({"project": store.set_spotlight(project_id, data.get("spotlight", ""), user.get("email", ""))})
    except store.ClubError as exc:
        return _bad(exc)
