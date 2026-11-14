"""
The MCN Developer Club: members, projects launched for review, the marketplace,
awards and certificates. Stored in ~/.mcn/club.db on the MCN account server
(hosted Studio).

    member        a student (with their college) or professional (with their company)
    project       an app a member launched for review: in_review → approved | changes_requested | rejected
    award         a reviewer's recognition of an approved project (AWARDS below)
    spotlight     an approved project picked out for funding, recognition or showcasing
    certificate   given to every member who launches a project, for each approved project,
                  and for each award; anyone can verify one by its code
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

AWARDS = {
    "best_overall": "Best Overall Application",
    "best_innovation": "Best Innovation",
    "best_technical": "Best Technical Implementation",
    "best_use_of_mcn": "Best Use of MCN",
    "best_ai": "Best AI-Powered Application",
}
SPOTLIGHTS = {"funding": "Funding candidate", "recognition": "Recognition", "showcase": "Showcase"}
KINDS = {"student": "Student", "professional": "Professional"}
STATUSES = ("in_review", "approved", "changes_requested", "rejected", "withdrawn")
CERTIFICATES = {
    "participant": "Certificate of Participation",
    "certified": "Certified MCN Developer",
    "award": "Award",
}

_DB_PATH = Path.home() / ".mcn" / "club.db"
_lock = threading.Lock()
_CODE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class ClubError(ValueError):
    """A request the club can't accept as it is."""


def set_db_path(path: Path) -> None:
    global _DB_PATH
    _DB_PATH = Path(path)


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS club_members (
            user_id TEXT PRIMARY KEY, email TEXT, name TEXT NOT NULL, kind TEXT NOT NULL,
            organization TEXT NOT NULL, title TEXT, country TEXT, bio TEXT, joined_at REAL);
        CREATE TABLE IF NOT EXISTS club_projects (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, tagline TEXT, description TEXT,
            category TEXT, backend TEXT, ui TEXT, stats TEXT, status TEXT NOT NULL, version INTEGER DEFAULT 1,
            submitted_at REAL, reviewed_at REAL, reviewer TEXT, review_notes TEXT, spotlight TEXT,
            listed_at REAL);
        CREATE TABLE IF NOT EXISTS club_awards (
            project_id TEXT NOT NULL, category TEXT NOT NULL, note TEXT, awarded_by TEXT, awarded_at REAL,
            PRIMARY KEY (project_id, category));
        CREATE TABLE IF NOT EXISTS club_certificates (
            code TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, project_id TEXT, award TEXT,
            holder TEXT, organization TEXT, title TEXT, issued_at REAL);
        CREATE TABLE IF NOT EXISTS club_events (
            project_id TEXT, at REAL, actor TEXT, action TEXT, note TEXT);
    """)
    return c


def _row(r: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(r) if r else None


def _clean(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


# ── Members ──────────────────────────────────────────────────────────────────

def join(user_id: str, email: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a member's profile."""
    name = _clean(profile.get("name"), 80)
    kind = _clean(profile.get("kind"), 20).lower()
    org = _clean(profile.get("organization"), 120)
    if not name:
        raise ClubError("Add your name")
    if kind not in KINDS:
        raise ClubError("Choose student or professional")
    if not org:
        raise ClubError("Add your " + ("college or university" if kind == "student" else "company"))
    with _lock, _conn() as c:
        existing = c.execute("SELECT joined_at FROM club_members WHERE user_id = ?", (user_id,)).fetchone()
        c.execute("INSERT OR REPLACE INTO club_members (user_id, email, name, kind, organization, title, country, bio, joined_at) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, email, name, kind, org, _clean(profile.get("title"), 80), _clean(profile.get("country"), 60),
                   _clean(profile.get("bio"), 500), existing["joined_at"] if existing else time.time()))
    return member(user_id)


def member(user_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        return _row(c.execute("SELECT * FROM club_members WHERE user_id = ?", (user_id,)).fetchone())


# ── Projects ─────────────────────────────────────────────────────────────────

def _event(c, project_id: str, actor: str, action: str, note: str = "") -> None:
    c.execute("INSERT INTO club_events (project_id, at, actor, action, note) VALUES (?, ?, ?, ?, ?)",
              (project_id, time.time(), actor, action, note))


def submit(user_id: str, data: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    """Launch a project for review (or send an updated version of one that needs changes)."""
    who = member(user_id)
    if not who:
        raise ClubError("Join the MCN Developer Club first")
    title = _clean(data.get("title"), 80)
    if not title:
        raise ClubError("Give your project a title")
    backend, ui = str(data.get("backend") or ""), str(data.get("ui") or "")
    if not (backend.strip() or ui.strip()):
        raise ClubError("There's no app to submit: backend/main.mcn and ui/app.mcn are empty")
    if len(backend) + len(ui) > 400_000:
        raise ClubError("The app is too large to submit (over 400 KB of MCN)")
    fields = (title, _clean(data.get("tagline"), 140), _clean(data.get("description"), 4000),
              _clean(data.get("category"), 40), backend, ui, json.dumps(stats))
    with _lock, _conn() as c:
        pid = data.get("project_id")
        if pid:
            row = c.execute("SELECT * FROM club_projects WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not row:
                raise ClubError("That project isn't yours")
            if row["status"] not in ("changes_requested", "rejected", "withdrawn", "approved"):
                raise ClubError("This project is already waiting for review")
            c.execute("UPDATE club_projects SET title=?, tagline=?, description=?, category=?, backend=?, ui=?, stats=?, "
                      "status='in_review', version=version+1, submitted_at=? WHERE id=?", fields + (time.time(), pid))
            _event(c, pid, who["email"], "resubmitted")
        else:
            pid = secrets.token_hex(4)
            c.execute("INSERT INTO club_projects (id, user_id, title, tagline, description, category, backend, ui, stats, "
                      "status, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_review', ?)",
                      (pid, user_id) + fields + (time.time(),))
            _event(c, pid, who["email"], "submitted")
        _issue(c, user_id, "participant", None, None, CERTIFICATES["participant"], once=True)
    return project(pid, include_source=True)


def withdraw(user_id: str, project_id: str) -> Dict[str, Any]:
    with _lock, _conn() as c:
        n = c.execute("UPDATE club_projects SET status='withdrawn', listed_at=NULL WHERE id=? AND user_id=? "
                      "AND status IN ('in_review', 'changes_requested', 'approved')", (project_id, user_id)).rowcount
        if not n:
            raise ClubError("That project can't be withdrawn")
        _event(c, project_id, user_id, "withdrawn")
    return project(project_id)


def _awards_for(c, project_id: str) -> List[Dict[str, Any]]:
    return [{"category": r["category"], "label": AWARDS.get(r["category"], r["category"]), "note": r["note"]}
            for r in c.execute("SELECT * FROM club_awards WHERE project_id = ? ORDER BY awarded_at", (project_id,))]


def project(project_id: str, include_source: bool = False) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        r = c.execute("SELECT p.*, m.name AS author, m.kind AS author_kind, m.organization AS author_org "
                      "FROM club_projects p LEFT JOIN club_members m ON m.user_id = p.user_id WHERE p.id = ?",
                      (project_id,)).fetchone()
        if not r:
            return None
        out = dict(r)
        out["stats"] = json.loads(out.get("stats") or "{}")
        out["awards"] = _awards_for(c, project_id)
        out["spotlight_label"] = SPOTLIGHTS.get(out.get("spotlight") or "", "")
        out["history"] = [dict(e) for e in c.execute("SELECT at, actor, action, note FROM club_events "
                                                     "WHERE project_id = ? ORDER BY at", (project_id,))]
        if not include_source:
            out.pop("backend", None)
            out.pop("ui", None)
        return out


def projects_of(user_id: str) -> List[Dict[str, Any]]:
    with _conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM club_projects WHERE user_id = ? ORDER BY submitted_at DESC",
                                          (user_id,))]
    return [project(i) for i in ids]


def marketplace(award: str = "", spotlight: str = "", kind: str = "", query: str = "") -> List[Dict[str, Any]]:
    """Approved projects, newest first, optionally only those with an award, spotlight, author kind or text."""
    sql = ("SELECT p.id FROM club_projects p JOIN club_members m ON m.user_id = p.user_id "
           "WHERE p.status = 'approved'")
    args: List[Any] = []
    if award:
        sql += " AND EXISTS (SELECT 1 FROM club_awards a WHERE a.project_id = p.id AND a.category = ?)"
        args.append(award)
    if spotlight:
        sql += " AND p.spotlight = ?"
        args.append(spotlight)
    if kind:
        sql += " AND m.kind = ?"
        args.append(kind)
    if query:
        sql += " AND (p.title LIKE ? OR p.tagline LIKE ? OR p.description LIKE ? OR m.organization LIKE ? OR m.name LIKE ?)"
        args += [f"%{query}%"] * 5
    sql += " ORDER BY p.listed_at DESC"
    with _conn() as c:
        ids = [r["id"] for r in c.execute(sql, args)]
    return [project(i) for i in ids]


# ── Review ───────────────────────────────────────────────────────────────────

def queue() -> List[Dict[str, Any]]:
    with _conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM club_projects WHERE status = 'in_review' ORDER BY submitted_at")]
    return [project(i) for i in ids]


def decide(project_id: str, reviewer: str, decision: str, notes: str = "") -> Dict[str, Any]:
    status = {"approve": "approved", "changes": "changes_requested", "reject": "rejected"}.get(decision)
    if not status:
        raise ClubError("Decide approve, changes or reject")
    if status != "approved" and not _clean(notes, 10):
        raise ClubError("Tell the developer what to change, or why it was rejected")
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM club_projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise ClubError("No such project")
        if row["status"] != "in_review":
            raise ClubError(f"This project isn't waiting for review (it's {row['status'].replace('_', ' ')})")
        now = time.time()
        c.execute("UPDATE club_projects SET status=?, reviewed_at=?, reviewer=?, review_notes=?, listed_at=? WHERE id=?",
                  (status, now, reviewer, _clean(notes, 4000), now if status == "approved" else None, project_id))
        _event(c, project_id, reviewer, status, _clean(notes, 4000))
        if status == "approved":
            _issue(c, row["user_id"], "certified", project_id, None, f"{CERTIFICATES['certified']}: {row['title']}")
    return project(project_id)


def give_award(project_id: str, category: str, reviewer: str, note: str = "") -> Dict[str, Any]:
    if category not in AWARDS:
        raise ClubError("Unknown award")
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM club_projects WHERE id = ?", (project_id,)).fetchone()
        if not row or row["status"] != "approved":
            raise ClubError("Only approved projects can win awards")
        if c.execute("SELECT 1 FROM club_awards WHERE project_id=? AND category=?", (project_id, category)).fetchone():
            raise ClubError("This project already has that award")
        c.execute("INSERT INTO club_awards (project_id, category, note, awarded_by, awarded_at) VALUES (?, ?, ?, ?, ?)",
                  (project_id, category, _clean(note, 500), reviewer, time.time()))
        _event(c, project_id, reviewer, "award", AWARDS[category])
        _issue(c, row["user_id"], "award", project_id, category, f"{AWARDS[category]}: {row['title']}")
    return project(project_id)


def remove_award(project_id: str, category: str, reviewer: str) -> Dict[str, Any]:
    with _lock, _conn() as c:
        c.execute("DELETE FROM club_awards WHERE project_id=? AND category=?", (project_id, category))
        c.execute("DELETE FROM club_certificates WHERE project_id=? AND award=?", (project_id, category))
        _event(c, project_id, reviewer, "award removed", AWARDS.get(category, category))
    return project(project_id)


def set_spotlight(project_id: str, spotlight: str, reviewer: str) -> Dict[str, Any]:
    if spotlight and spotlight not in SPOTLIGHTS:
        raise ClubError("Spotlight must be funding, recognition or showcase")
    with _lock, _conn() as c:
        n = c.execute("UPDATE club_projects SET spotlight=? WHERE id=? AND status='approved'",
                      (spotlight or None, project_id)).rowcount
        if not n:
            raise ClubError("Only approved projects can be spotlighted")
        _event(c, project_id, reviewer, "spotlight", SPOTLIGHTS.get(spotlight, "removed"))
    return project(project_id)


def stats() -> Dict[str, Any]:
    """What the club has produced: projects by status, awards, student/professional split, top organisations."""
    with _conn() as c:
        by_status = {s: 0 for s in STATUSES}
        for r in c.execute("SELECT status, COUNT(*) AS n FROM club_projects GROUP BY status"):
            by_status[r["status"]] = r["n"]
        members_by_kind = {k: 0 for k in KINDS}
        for r in c.execute("SELECT kind, COUNT(*) AS n FROM club_members GROUP BY kind"):
            members_by_kind[r["kind"]] = r["n"]
        awards = {k: 0 for k in AWARDS}
        for r in c.execute("SELECT category, COUNT(*) AS n FROM club_awards GROUP BY category"):
            awards[r["category"]] = r["n"]
        spotlights = {k: 0 for k in SPOTLIGHTS}
        for r in c.execute("SELECT spotlight, COUNT(*) AS n FROM club_projects WHERE spotlight IS NOT NULL "
                           "GROUP BY spotlight"):
            spotlights[r["spotlight"]] = r["n"]
        top_orgs = [dict(r) for r in c.execute(
            "SELECT m.organization, m.kind, COUNT(p.id) AS approved FROM club_members m "
            "JOIN club_projects p ON p.user_id = m.user_id AND p.status = 'approved' "
            "GROUP BY m.organization, m.kind ORDER BY approved DESC, m.organization LIMIT 10")]
        certificates = c.execute("SELECT COUNT(*) FROM club_certificates").fetchone()[0]
        members = c.execute("SELECT COUNT(*) FROM club_members").fetchone()[0]
        uses_ai = c.execute("SELECT COUNT(*) FROM club_projects WHERE status='approved' AND stats LIKE '%\"uses_ai\": true%'"
                            ).fetchone()[0]
    return {"members": members, "members_by_kind": members_by_kind, "projects_by_status": by_status,
            "awards": awards, "spotlights": spotlights, "top_organizations": top_orgs,
            "certificates": certificates, "approved_using_ai": uses_ai}


# ── Certificates ─────────────────────────────────────────────────────────────

def _issue(c, user_id: str, kind: str, project_id: Optional[str], award: Optional[str], title: str,
           once: bool = False) -> Optional[str]:
    if once and c.execute("SELECT 1 FROM club_certificates WHERE user_id=? AND kind=?", (user_id, kind)).fetchone():
        return None
    if project_id and c.execute("SELECT 1 FROM club_certificates WHERE user_id=? AND kind=? AND project_id=? "
                                "AND COALESCE(award,'')=?", (user_id, kind, project_id, award or "")).fetchone():
        return None
    who = c.execute("SELECT name, organization FROM club_members WHERE user_id = ?", (user_id,)).fetchone()
    code = "MCN-" + "".join(secrets.choice(_CODE) for _ in range(10))
    c.execute("INSERT INTO club_certificates (code, user_id, kind, project_id, award, holder, organization, title, issued_at) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (code, user_id, kind, project_id, award, who["name"] if who else "", who["organization"] if who else "",
               title, time.time()))
    return code


def certificates_of(user_id: str) -> List[Dict[str, Any]]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT code, kind, project_id, award, title, holder, organization, issued_at "
                                           "FROM club_certificates WHERE user_id = ? ORDER BY issued_at", (user_id,))]


def certificate(code: str) -> Optional[Dict[str, Any]]:
    """A certificate by its code (public, for verification); None when there's no such certificate."""
    with _conn() as c:
        r = c.execute("SELECT c.code, c.kind, c.project_id, c.award, c.title, c.holder, c.organization, c.issued_at, "
                      "m.kind AS holder_kind, p.title AS project_title FROM club_certificates c "
                      "LEFT JOIN club_members m ON m.user_id = c.user_id "
                      "LEFT JOIN club_projects p ON p.id = c.project_id WHERE c.code = ?", (code,)).fetchone()
    if not r:
        return None
    out = dict(r)
    out["kind_label"] = CERTIFICATES.get(out["kind"], out["kind"])
    out["award_label"] = AWARDS.get(out.get("award") or "", "")
    return out
