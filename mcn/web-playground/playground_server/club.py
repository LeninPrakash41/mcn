"""
The MCN Developer Club API: join with a profile, launch the workspace's app for
review, the public marketplace and certificate verification, and review tools.

The club lives on the MCN account server (hosted Studio). Installed Studio forwards
every call there with the signed-in account (`mcn login` / Sign in), attaching the
local workspace's files when you launch a project.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

import time

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


def _is_admin(user) -> bool:
    return "admin" in _roles(user)


def _public(p):
    """A project as anyone may see it: rubric scores are for reviewers and the developer only."""
    if isinstance(p, list):
        return [_public(x) for x in p]
    if isinstance(p, dict):
        return {k: v for k, v in p.items() if k not in ("scores",)}
    return p


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
@bp.route("/club/u/<user_id>")
@bp.route("/club/leaderboard")
@bp.route("/club/awards")
@bp.route("/club/verify")
@bp.route("/club/seasons")
@bp.route("/club/season/<season_id>")
def club_page(project_id: str = "", code: str = "", user_id: str = "", season_id: str = ""):
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
                    "order": {"awards": list(store.AWARDS), "spotlights": list(store.SPOTLIGHTS), "kinds": list(store.KINDS),
                              "rubric": list(store.RUBRIC)},
                    "rubric_short": store.RUBRIC_SHORT,
                    "sorts": {"newest": "Newest", "most_used": "Most used", "most_liked": "Most liked", "trending": "Trending"},
                    "signatory": _signatory(), "user_id": user["sub"] if user else None,
                    "counts": store.public_counts(),
                    "rubric": store.RUBRIC, "rubric_help": store.RUBRIC_HELP, "open_seasons": store.open_seasons(),
                    "is_admin": _is_admin(user),
                    "signed_in": bool(user), "member": store.member(user["sub"]) if user else None,
                    "is_reviewer": _is_reviewer(user), "club_url": request.host_url.rstrip("/") + "/club"})


def _signatory():
    """Who signs certificates, from MCN_CLUB_SIGNATORY="Name|Title" (nobody when unset)."""
    raw = os.getenv("MCN_CLUB_SIGNATORY", "").strip()
    if not raw:
        return None
    name, _, title = raw.partition("|")
    return {"name": name.strip()[:80], "title": title.strip()[:80] or "MCN Developer Club"}


def _visitor() -> str:
    """A visitor key for counting page views once a day, without keeping anyone's address."""
    user = _current_user()
    if user and user.get("sub"):
        return "u:" + user["sub"]
    raw = f"{request.remote_addr}|{request.headers.get('User-Agent', '')}|{time.strftime('%Y-%m-%d')}"
    return "a:" + hashlib.sha256(raw.encode()).hexdigest()[:24]


@bp.route("/api/club/leaderboard")
def club_leaderboard():
    if not is_hosted():
        return _forward("GET", "/api/club/leaderboard")
    board = store.leaderboard()
    for key in ("most_used", "most_liked", "trending"):
        board[key] = _public(board[key])
    board["winners"] = {k: _public(v) for k, v in board["winners"].items()}
    return jsonify(board)


@bp.route("/api/club/members/<user_id>")
def club_member(user_id):
    if not is_hosted():
        return _forward("GET", f"/api/club/members/{user_id}")
    found = store.profile(user_id)
    if not found:
        return jsonify({"error": "No such member"}), 404
    found["apps"] = _public(found["apps"])
    return jsonify({"member": found})


@bp.route("/api/club/marketplace")
def club_marketplace():
    if not is_hosted():
        return _forward("GET", "/api/club/marketplace")
    a = request.args
    return jsonify({"projects": _public(store.marketplace(a.get("award", ""), a.get("spotlight", ""), a.get("kind", ""),
                                                          a.get("q", "")[:80], a.get("sort", "newest"),
                                                          season=a.get("season", "")))})


@bp.route("/api/club/projects/<project_id>")
def club_project(project_id):
    if not is_hosted():
        return _forward("GET", f"/api/club/projects/{project_id}")
    user = _current_user()
    found = store.project(project_id, include_source=True)
    mine = bool(user and found and found["user_id"] == user.get("sub"))
    if not found or (found["status"] != "approved" and not mine and not _is_reviewer(user)):
        return jsonify({"error": "No such project in the marketplace"}), 404
    if request.args.get("view") == "1" and found["status"] == "approved":
        store.record_view(project_id, _visitor())
        found["usage"] = store.project(project_id)["usage"]
    found["liked"] = bool(user and store.liked_by(project_id, user["sub"]))
    found["mine"] = mine
    return jsonify({"project": found if (mine or _is_reviewer(user)) else _public(found)})


@bp.route("/api/club/projects/<project_id>/like", methods=["POST"])
def club_like(project_id):
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", f"/api/club/projects/{project_id}/like", data)
    user, err = _signed_in()
    if err:
        return err
    try:
        return jsonify(store.set_like(project_id, user["sub"], bool(data.get("liked", True))))
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/projects/<project_id>/use", methods=["POST"])
def club_use(project_id):
    """Installed Studio reporting that its signed-in user opened this app."""
    if not is_hosted():
        return _forward("POST", f"/api/club/projects/{project_id}/use", {})
    user, err = _signed_in()
    if err:
        return err
    try:
        return jsonify({"counted": store.record_use(project_id, user["sub"])})
    except store.ClubError as exc:
        return _bad(exc, 404)


@bp.route("/api/club/precheck", methods=["POST"])
def club_precheck():
    """The checks a launch would run, on this workspace's app, before sending it (runs locally)."""
    files = _workspace_files()
    if not (files["backend"].strip() or files["ui"].strip()):
        return jsonify({"ready": False, "checks": None,
                        "error": "There's no app here yet: backend/main.mcn and ui/app.mcn are empty"})
    checks = _check(files)
    return jsonify({"ready": not checks["parse_errors"], "checks": checks})


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
    if is_hosted():
        user = _current_user()
        if user and found["status"] == "approved":
            store.record_use(project_id, user["sub"])
    else:
        _forward("POST", f"/api/club/projects/{project_id}/use", {})          # counted on the account server
    ws = _request_workspace()
    for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
        if found.get(key):
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(found[key], encoding="utf-8")
    return jsonify({"success": True, "files": ["backend/main.mcn", "ui/app.mcn"], "title": found["title"]})


# ── Seasons ──────────────────────────────────────────────────────────────────

@bp.route("/api/club/seasons", methods=["GET", "POST"])
def club_seasons():
    if not is_hosted():
        return _forward(request.method, "/api/club/seasons", request.get_json(silent=True))
    if request.method == "GET":
        return jsonify({"seasons": store.seasons()})
    user, err = _signed_in()
    if err:
        return err
    if not _is_admin(user):
        return jsonify({"error": "Only admins can create seasons"}), 403
    try:
        return jsonify({"season": store.create_season(request.get_json(silent=True) or {}, user.get("email", ""))})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/seasons/<season_id>", methods=["GET", "POST"])
def club_season(season_id):
    if not is_hosted():
        return _forward(request.method, f"/api/club/seasons/{season_id}", request.get_json(silent=True))
    if request.method == "GET":
        found = store.season(season_id)
        if not found:
            return jsonify({"error": "No such season"}), 404
        found["entries"] = _public(found["entries"])
        found["winners"] = {k: _public(v) for k, v in found["winners"].items()} if found["status"] == "closed" else {}
        return jsonify({"season": found})
    user, err = _signed_in()
    if err:
        return err
    if not _is_admin(user):
        return jsonify({"error": "Only admins can change seasons"}), 403
    try:
        return jsonify({"season": store.update_season(season_id, request.get_json(silent=True) or {}, user.get("email", ""))})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/seasons/<season_id>/standings")
def club_standings(season_id):
    if not is_hosted():
        return _forward("GET", f"/api/club/seasons/{season_id}/standings")
    user, err = _reviewer()
    if err:
        return err
    try:
        return jsonify(store.standings(season_id))
    except store.ClubError as exc:
        return _bad(exc, 404)


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
        return jsonify({"project": found, "mine": store.scores_by(project_id, user.get("email", "")),
                        "checks": _check({"backend": found.get("backend") or "", "ui": found.get("ui") or ""})})
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"project": store.decide(project_id, user.get("email", ""), data.get("decision", ""),
                                                data.get("notes", ""))})
    except store.ClubError as exc:
        return _bad(exc)


@bp.route("/api/club/review/<project_id>/score", methods=["POST"])
def club_score(project_id):
    data = request.get_json(silent=True) or {}
    if not is_hosted():
        return _forward("POST", f"/api/club/review/{project_id}/score", data)
    user, err = _reviewer()
    if err:
        return err
    try:
        found = store.score(project_id, user.get("email", ""), data.get("scores") or {}, data.get("note", ""))
        return jsonify({"project": found, "mine": store.scores_by(project_id, user.get("email", ""))})
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
