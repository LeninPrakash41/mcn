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
RUBRIC = {
    "overall": "Overall quality",
    "innovation": "Innovation",
    "technical": "Technical implementation",
    "use_of_mcn": "Use of MCN",
    "ai": "Use of AI",
}
RUBRIC_HELP = {
    "overall": "Useful, complete and polished: would people use it?",
    "innovation": "A new idea, or a fresh take on a real problem",
    "technical": "Clean structure, typed endpoints, tests, sensible data model",
    "use_of_mcn": "Uses MCN well: services, screens, modules, the app map, agents",
    "ai": "AI that genuinely helps (not applicable if the app has no AI)",
}
RUBRIC_SHORT = {"overall": "Overall", "innovation": "Innovation", "technical": "Technical", "use_of_mcn": "MCN", "ai": "AI"}
CRITERION_AWARD = {"overall": "best_overall", "innovation": "best_innovation", "technical": "best_technical",
                   "use_of_mcn": "best_use_of_mcn", "ai": "best_ai"}
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
        CREATE TABLE IF NOT EXISTS club_uses (
            project_id TEXT NOT NULL, user_id TEXT NOT NULL, first_at REAL, last_at REAL, times INTEGER DEFAULT 1,
            PRIMARY KEY (project_id, user_id));
        CREATE TABLE IF NOT EXISTS club_likes (
            project_id TEXT NOT NULL, user_id TEXT NOT NULL, at REAL, PRIMARY KEY (project_id, user_id));
        CREATE TABLE IF NOT EXISTS club_views (
            project_id TEXT NOT NULL, visitor TEXT NOT NULL, day TEXT NOT NULL, PRIMARY KEY (project_id, visitor, day));
        CREATE TABLE IF NOT EXISTS club_seasons (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, theme TEXT, description TEXT, starts_at REAL NOT NULL,
            ends_at REAL NOT NULL, results_published INTEGER DEFAULT 0, created_by TEXT, created_at REAL);
        CREATE TABLE IF NOT EXISTS club_scores (
            project_id TEXT NOT NULL, reviewer TEXT NOT NULL, criterion TEXT NOT NULL, score INTEGER, at REAL,
            PRIMARY KEY (project_id, reviewer, criterion));
        CREATE TABLE IF NOT EXISTS club_score_notes (
            project_id TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT, at REAL, PRIMARY KEY (project_id, reviewer));
    """)
    # Older club databases: add the season columns
    for table in ("club_projects", "club_awards"):
        if "season_id" not in {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
            c.execute(f"ALTER TABLE {table} ADD COLUMN season_id TEXT")
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
    season_id = _clean(data.get("season_id"), 20) or None
    with _lock, _conn() as c:
        if season_id:
            season = _season_brief(c, season_id)
            if not season:
                raise ClubError("No such season")
            if season["status"] != "open" and not data.get("project_id"):
                raise ClubError(f"{season['name']} isn't taking entries ({season['status_label'].lower()})")
        pid = data.get("project_id")
        if pid:
            row = c.execute("SELECT * FROM club_projects WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not row:
                raise ClubError("That project isn't yours")
            if row["status"] not in ("changes_requested", "rejected", "withdrawn", "approved"):
                raise ClubError("This project is already waiting for review")
            c.execute("UPDATE club_projects SET title=?, tagline=?, description=?, category=?, backend=?, ui=?, stats=?, "
                      "status='in_review', version=version+1, submitted_at=?, season_id=COALESCE(season_id, ?) WHERE id=?",
                      fields + (time.time(), season_id, pid))
            _event(c, pid, who["email"], "resubmitted")
        else:
            pid = secrets.token_hex(4)
            c.execute("INSERT INTO club_projects (id, user_id, title, tagline, description, category, backend, ui, stats, "
                      "status, submitted_at, season_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_review', ?, ?)",
                      (pid, user_id) + fields + (time.time(), season_id))
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
    out = []
    for r in c.execute("SELECT * FROM club_awards WHERE project_id = ? ORDER BY awarded_at", (project_id,)):
        season = _season_brief(c, r["season_id"])
        out.append({"category": r["category"], "label": AWARDS.get(r["category"], r["category"]), "note": r["note"],
                    "season": season["name"] if season else None})
    return out


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
        out["usage"] = _usage(c, project_id)
        out["season"] = _season_brief(c, out.get("season_id"))
        out["scores"] = _score_summary(c, project_id)
        out["spotlight_label"] = SPOTLIGHTS.get(out.get("spotlight") or "", "")
        out["history"] = [dict(e) for e in c.execute("SELECT at, actor, action, note FROM club_events "
                                                     "WHERE project_id = ? ORDER BY at", (project_id,))]
        if not include_source:
            out.pop("backend", None)
            out.pop("ui", None)
        return out


def _usage(c, project_id: str) -> Dict[str, int]:
    """uses: distinct registered users (not the author) who opened the app in Studio;
    recent_uses: those in the last 30 days; likes; views: visitors per day."""
    month = time.time() - 30 * 86400
    one = lambda sql, *a: c.execute(sql, (project_id,) + a).fetchone()[0]
    return {"uses": one("SELECT COUNT(*) FROM club_uses WHERE project_id = ?"),
            "recent_uses": one("SELECT COUNT(*) FROM club_uses WHERE project_id = ? AND last_at >= ?", month),
            "likes": one("SELECT COUNT(*) FROM club_likes WHERE project_id = ?"),
            "views": one("SELECT COUNT(*) FROM club_views WHERE project_id = ?")}


def _approved_or_raise(c, project_id: str) -> sqlite3.Row:
    row = c.execute("SELECT * FROM club_projects WHERE id = ?", (project_id,)).fetchone()
    if not row or row["status"] != "approved":
        raise ClubError("No such project in the marketplace")
    return row


def record_use(project_id: str, user_id: str) -> bool:
    """A registered user opened the app in Studio. Counts once per person; the author's own opens don't count."""
    with _lock, _conn() as c:
        row = _approved_or_raise(c, project_id)
        if row["user_id"] == user_id:
            return False
        now = time.time()
        updated = c.execute("UPDATE club_uses SET last_at = ?, times = times + 1 WHERE project_id = ? AND user_id = ?",
                            (now, project_id, user_id)).rowcount
        if not updated:
            c.execute("INSERT INTO club_uses (project_id, user_id, first_at, last_at) VALUES (?, ?, ?, ?)",
                      (project_id, user_id, now, now))
        return not updated


def set_like(project_id: str, user_id: str, liked: bool) -> Dict[str, Any]:
    with _lock, _conn() as c:
        row = _approved_or_raise(c, project_id)
        if row["user_id"] == user_id:
            raise ClubError("You can't like your own app")
        if liked:
            c.execute("INSERT OR IGNORE INTO club_likes (project_id, user_id, at) VALUES (?, ?, ?)",
                      (project_id, user_id, time.time()))
        else:
            c.execute("DELETE FROM club_likes WHERE project_id = ? AND user_id = ?", (project_id, user_id))
        return {"liked": liked, **_usage(c, project_id)}


def liked_by(project_id: str, user_id: str) -> bool:
    with _conn() as c:
        return bool(c.execute("SELECT 1 FROM club_likes WHERE project_id = ? AND user_id = ?",
                              (project_id, user_id)).fetchone())


def record_view(project_id: str, visitor: str) -> None:
    """A visit to the app's page, counted once per visitor per day."""
    with _lock, _conn() as c:
        if c.execute("SELECT status FROM club_projects WHERE id = ?", (project_id,)).fetchone():
            c.execute("INSERT OR IGNORE INTO club_views (project_id, visitor, day) VALUES (?, ?, ?)",
                      (project_id, visitor[:64], time.strftime("%Y-%m-%d")))


def projects_of(user_id: str) -> List[Dict[str, Any]]:
    with _conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM club_projects WHERE user_id = ? ORDER BY submitted_at DESC",
                                          (user_id,))]
    return [project(i) for i in ids]


SORTS = {
    "newest": "p.listed_at DESC",
    "most_used": "(SELECT COUNT(*) FROM club_uses u WHERE u.project_id = p.id) DESC, p.listed_at DESC",
    "most_liked": "(SELECT COUNT(*) FROM club_likes l WHERE l.project_id = p.id) DESC, p.listed_at DESC",
    "trending": "(SELECT COUNT(*) FROM club_uses u WHERE u.project_id = p.id AND u.last_at >= {month}) DESC, "
                "(SELECT COUNT(*) FROM club_likes l WHERE l.project_id = p.id AND l.at >= {month}) DESC, p.listed_at DESC",
}


def marketplace(award: str = "", spotlight: str = "", kind: str = "", query: str = "", sort: str = "newest",
                author: str = "", limit: int = 0, season: str = "") -> List[Dict[str, Any]]:
    """Approved projects, optionally only those with an award, spotlight, author kind, author or text, sorted
    by newest, most used (by other registered users), most liked, or trending (the last 30 days)."""
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
    if author:
        sql += " AND p.user_id = ?"
        args.append(author)
    if season:
        sql += " AND p.season_id = ?"
        args.append(season)
    sql += " ORDER BY " + SORTS.get(sort, SORTS["newest"]).format(month=time.time() - 30 * 86400)
    if limit:
        sql += f" LIMIT {int(limit)}"
    with _conn() as c:
        ids = [r["id"] for r in c.execute(sql, args)]
    return [project(i) for i in ids]


def public_counts() -> Dict[str, int]:
    with _conn() as c:
        one = lambda sql: c.execute(sql).fetchone()[0]
        return {"apps": one("SELECT COUNT(*) FROM club_projects WHERE status = 'approved'"),
                "members": one("SELECT COUNT(*) FROM club_members"),
                "organizations": one("SELECT COUNT(DISTINCT lower(organization)) FROM club_members"),
                "certificates": one("SELECT COUNT(*) FROM club_certificates")}


def leaderboard(limit: int = 10) -> Dict[str, Any]:
    """The apps other members use and like most, the builders with the most approved and used apps,
    and the award winners by category."""
    with _conn() as c:
        builders = [dict(r) for r in c.execute(
            "SELECT m.user_id, m.name, m.kind, m.organization, COUNT(DISTINCT p.id) AS apps, "
            "(SELECT COUNT(*) FROM club_uses u JOIN club_projects q ON q.id = u.project_id "
            " WHERE q.user_id = m.user_id AND q.status = 'approved') AS uses, "
            "(SELECT COUNT(*) FROM club_awards a JOIN club_projects q ON q.id = a.project_id "
            " WHERE q.user_id = m.user_id AND q.status = 'approved') AS awards "
            "FROM club_members m JOIN club_projects p ON p.user_id = m.user_id AND p.status = 'approved' "
            "GROUP BY m.user_id ORDER BY uses DESC, awards DESC, apps DESC LIMIT ?", (limit,))]
        winners = {}
        for cat in AWARDS:
            ids = [r["project_id"] for r in c.execute(
                "SELECT a.project_id FROM club_awards a JOIN club_projects p ON p.id = a.project_id "
                "WHERE a.category = ? AND p.status = 'approved' ORDER BY a.awarded_at DESC", (cat,))]
            winners[cat] = ids
    flat = {i for ids in winners.values() for i in ids}
    projects = {i: project(i) for i in flat}
    return {"most_used": marketplace(sort="most_used", limit=limit),
            "most_liked": marketplace(sort="most_liked", limit=limit),
            "trending": marketplace(sort="trending", limit=limit),
            "builders": builders,
            "winners": {cat: [projects[i] for i in ids] for cat, ids in winners.items()}}


def profile(user_id: str) -> Optional[Dict[str, Any]]:
    """A member's public page: who they are, their approved apps and the certificates they've earned."""
    who = member(user_id)
    if not who:
        return None
    apps = marketplace(author=user_id)
    certs = [c for c in certificates_of(user_id)]
    return {"name": who["name"], "kind": who["kind"], "organization": who["organization"], "title": who.get("title"),
            "country": who.get("country"), "bio": who.get("bio"), "joined_at": who["joined_at"], "apps": apps,
            "certificates": certs, "uses": sum(a["usage"]["uses"] for a in apps),
            "awards": sum(len(a["awards"]) for a in apps)}


# ── Seasons ──────────────────────────────────────────────────────────────────

_SEASON_LABELS = {"upcoming": "Starting soon", "open": "Open for entries", "judging": "Judging", "closed": "Results out"}


def _season_status(row) -> str:
    now = time.time()
    if row["results_published"]:
        return "closed"
    if now < row["starts_at"]:
        return "upcoming"
    if now <= row["ends_at"]:
        return "open"
    return "judging"


def _season_brief(c, season_id) -> Optional[Dict[str, Any]]:
    if not season_id:
        return None
    r = c.execute("SELECT * FROM club_seasons WHERE id = ?", (season_id,)).fetchone()
    if not r:
        return None
    status = _season_status(r)
    return {"id": r["id"], "name": r["name"], "theme": r["theme"], "description": r["description"],
            "starts_at": r["starts_at"], "ends_at": r["ends_at"], "status": status, "status_label": _SEASON_LABELS[status]}


def _season_fields(data: Dict[str, Any]):
    name = _clean(data.get("name"), 60)
    if not name:
        raise ClubError("Give the season a name, e.g. Spring 2027")
    try:
        starts, ends = float(data.get("starts_at")), float(data.get("ends_at"))
    except (TypeError, ValueError):
        raise ClubError("Give the season a start and a deadline") from None
    if ends <= starts:
        raise ClubError("The deadline must be after the start")
    return name, _clean(data.get("theme"), 120), _clean(data.get("description"), 2000), starts, ends


def create_season(data: Dict[str, Any], actor: str) -> Dict[str, Any]:
    name, theme, description, starts, ends = _season_fields(data)
    sid = secrets.token_hex(3)
    with _lock, _conn() as c:
        c.execute("INSERT INTO club_seasons (id, name, theme, description, starts_at, ends_at, created_by, created_at) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (sid, name, theme, description, starts, ends, actor, time.time()))
    return season(sid)


def update_season(season_id: str, data: Dict[str, Any], actor: str) -> Dict[str, Any]:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM club_seasons WHERE id = ?", (season_id,)).fetchone()
        if not row:
            raise ClubError("No such season")
        if "results_published" in data:
            c.execute("UPDATE club_seasons SET results_published = ? WHERE id = ?",
                      (1 if data["results_published"] else 0, season_id))
        if any(k in data for k in ("name", "starts_at", "ends_at")):
            merged = {**dict(row), **data}
            name, theme, description, starts, ends = _season_fields(merged)
            c.execute("UPDATE club_seasons SET name=?, theme=?, description=?, starts_at=?, ends_at=? WHERE id=?",
                      (name, theme, description, starts, ends, season_id))
    return season(season_id)


def seasons() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT id FROM club_seasons ORDER BY starts_at DESC").fetchall()
        out = []
        for r in rows:
            brief = _season_brief(c, r["id"])
            brief["entries"] = c.execute("SELECT COUNT(*) FROM club_projects WHERE season_id = ? AND status != 'withdrawn'",
                                         (r["id"],)).fetchone()[0]
            brief["approved"] = c.execute("SELECT COUNT(*) FROM club_projects WHERE season_id = ? AND status = 'approved'",
                                          (r["id"],)).fetchone()[0]
            out.append(brief)
    return out


def open_seasons() -> List[Dict[str, Any]]:
    return [s for s in seasons() if s["status"] == "open"]


def season(season_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        brief = _season_brief(c, season_id)
    if not brief:
        return None
    entries = marketplace(season=season_id, sort="most_used")
    winners = {cat: [p for p in entries if any(a["category"] == cat for a in p["awards"])] for cat in AWARDS}
    return {**brief, "entries": entries, "winners": winners}


# ── Scoring ──────────────────────────────────────────────────────────────────

def _score_summary(c, project_id: str) -> Dict[str, Any]:
    """Average score per criterion over the reviewers who scored it, and an overall average."""
    averages = {}
    for crit in RUBRIC:
        r = c.execute("SELECT AVG(score) AS a, COUNT(score) AS n FROM club_scores WHERE project_id = ? AND criterion = ? "
                      "AND score IS NOT NULL", (project_id, crit)).fetchone()
        averages[crit] = round(r["a"], 2) if r["n"] else None
    reviewers = c.execute("SELECT COUNT(DISTINCT reviewer) FROM club_scores WHERE project_id = ?", (project_id,)).fetchone()[0]
    present = [v for v in averages.values() if v is not None]
    return {"averages": averages, "total": round(sum(present) / len(present), 2) if present else None,
            "reviewers": reviewers}


def score(project_id: str, reviewer: str, scores: Dict[str, Any], note: str = "") -> Dict[str, Any]:
    """A reviewer's 1–5 scores on the rubric (AI may be left out when the app has no AI)."""
    clean: Dict[str, Optional[int]] = {}
    for crit in RUBRIC:
        value = scores.get(crit)
        if value in (None, "", "na"):
            if crit != "ai":
                raise ClubError(f"Score {RUBRIC[crit]} from 1 to 5")
            clean[crit] = None
            continue
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise ClubError(f"{RUBRIC[crit]} must be 1 to 5") from None
        if not 1 <= n <= 5:
            raise ClubError(f"{RUBRIC[crit]} must be 1 to 5")
        clean[crit] = n
    with _lock, _conn() as c:
        row = c.execute("SELECT status FROM club_projects WHERE id = ?", (project_id,)).fetchone()
        if not row or row["status"] not in ("in_review", "approved"):
            raise ClubError("Only projects in review or approved can be scored")
        now = time.time()
        for crit, n in clean.items():
            c.execute("INSERT OR REPLACE INTO club_scores (project_id, reviewer, criterion, score, at) VALUES (?, ?, ?, ?, ?)",
                      (project_id, reviewer, crit, n, now))
        c.execute("INSERT OR REPLACE INTO club_score_notes (project_id, reviewer, note, at) VALUES (?, ?, ?, ?)",
                  (project_id, reviewer, _clean(note, 1000), now))
        _event(c, project_id, reviewer, "scored")
    return project(project_id)


def scores_by(project_id: str, reviewer: str) -> Dict[str, Any]:
    with _conn() as c:
        mine = {r["criterion"]: r["score"] for r in c.execute(
            "SELECT criterion, score FROM club_scores WHERE project_id = ? AND reviewer = ?", (project_id, reviewer))}
        note = c.execute("SELECT note FROM club_score_notes WHERE project_id = ? AND reviewer = ?",
                         (project_id, reviewer)).fetchone()
    return {"scores": mine, "note": note["note"] if note else ""}


def standings(season_id: str) -> Dict[str, Any]:
    """A season's approved entries ranked by their rubric score, with a suggested winner for each award (the best
    average on its criterion) and People's Choice (the most used by other members)."""
    found = season(season_id)
    if not found:
        raise ClubError("No such season")
    entries = found["entries"]
    ranked = sorted(entries, key=lambda p: (p["scores"]["total"] is None, -(p["scores"]["total"] or 0)))
    suggestions = {}
    for crit, award in CRITERION_AWARD.items():
        scored = [p for p in entries if p["scores"]["averages"][crit] is not None]
        if scored:
            best = max(scored, key=lambda p: (p["scores"]["averages"][crit], p["usage"]["uses"]))
            suggestions[award] = {"project_id": best["id"], "title": best["title"],
                                  "score": best["scores"]["averages"][crit]}
    used = [p for p in entries if p["usage"]["uses"]]
    peoples = max(used, key=lambda p: (p["usage"]["uses"], p["usage"]["likes"])) if used else None
    return {"season": {k: v for k, v in found.items() if k not in ("entries", "winners")},
            "ranked": [{"id": p["id"], "title": p["title"], "author": p["author"], "author_org": p["author_org"],
                        "scores": p["scores"], "usage": p["usage"], "awards": p["awards"]} for p in ranked],
            "suggestions": suggestions,
            "peoples_choice": {"project_id": peoples["id"], "title": peoples["title"], "uses": peoples["usage"]["uses"]}
            if peoples else None}


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
        season = _season_brief(c, row["season_id"])
        c.execute("INSERT INTO club_awards (project_id, category, note, awarded_by, awarded_at, season_id) VALUES (?, ?, ?, ?, ?, ?)",
                  (project_id, category, _clean(note, 500), reviewer, time.time(), row["season_id"]))
        _event(c, project_id, reviewer, "award", AWARDS[category])
        _issue(c, row["user_id"], "award", project_id, category,
               f"{AWARDS[category]}: {row['title']}" + (f" · {season['name']}" if season else ""))
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
    top_used = [{"id": p["id"], "title": p["title"], "author_org": p["author_org"], **p["usage"]}
                for p in marketplace(sort="most_used", limit=5)]
    return {"members": members, "members_by_kind": members_by_kind, "projects_by_status": by_status,
            "top_used": top_used,
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
                      "m.kind AS holder_kind, p.title AS project_title, p.season_id FROM club_certificates c "
                      "LEFT JOIN club_members m ON m.user_id = c.user_id "
                      "LEFT JOIN club_projects p ON p.id = c.project_id WHERE c.code = ?", (code,)).fetchone()
        season = _season_brief(c, r["season_id"]) if r else None
    if not r:
        return None
    out = dict(r)
    out["season"] = season["name"] if season and out["kind"] == "award" else None
    out["kind_label"] = CERTIFICATES.get(out["kind"], out["kind"])
    out["award_label"] = AWARDS.get(out.get("award") or "", "")
    return out
