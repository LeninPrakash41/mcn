"""
The MCN Developer Club on hosted Studio: joining with a college or company,
launching an app for review, reviewers deciding, the marketplace with awards and
spotlights, certificates anyone can verify, and installed Studio forwarding to the
account server.
"""
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playground_app import load  # noqa: E402

PWD = "SecurePassword123!"
BACKEND = '''query("CREATE TABLE IF NOT EXISTS club_t (id INTEGER PRIMARY KEY, q TEXT)")

service helper
    endpoint answer(q: str)
        return {reply: ai("Answer briefly: " + q)}
'''
UI = '''component Ask
    state q = ""

    render
        card
            input bind=q label="Question"

app Helper
    title "Helper"
    layout
        tabs
            tab "Ask" Ask
'''


@pytest.fixture
def client(tmp_path, monkeypatch):
    _, c = load()
    from mcn.core_engine import auth_primitives
    from playground_server import club_store, device_store, rate_limit
    rate_limit.reset_all()
    monkeypatch.setattr(auth_primitives, "_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(device_store, "_DB_PATH", tmp_path / "device_sessions.db")
    monkeypatch.setattr(club_store, "_DB_PATH", tmp_path / "club.db")
    monkeypatch.setenv("MCN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "judge@example.com")
    monkeypatch.delenv("MCN_STUDIO_SIGNUP_DOMAINS", raising=False)
    monkeypatch.delenv("MCN_STUDIO_MODE", raising=False)
    return c


@contextmanager
def hosted():
    with patch.dict(os.environ, {"MCN_STUDIO_MODE": "hosted"}):
        yield


def register(c, email):
    with hosted():
        res = c.post("/api/auth/register", json={"email": email, "password": PWD})
    assert res.status_code == 200, res.get_json()
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def put_app(c, who, backend=BACKEND, ui=UI):
    for path, content in (("backend/main.mcn", backend), ("ui/app.mcn", ui)):
        assert c.post("/api/workspace/file", headers=who, json={"path": path, "content": content}).status_code == 200


def test_the_whole_journey(client):
    dev = register(client, "asha@college.example")
    judge = register(client, "judge@example.com")
    with hosted():
        put_app(client, dev)
        refused = client.post("/api/club/submit", headers=dev, json={"title": "Helper"})
        assert refused.status_code == 400 and "Join" in refused.get_json()["error"]
        bad = client.post("/api/club/join", headers=dev, json={"name": "Asha", "kind": "student"})
        assert bad.status_code == 400 and "college" in bad.get_json()["error"]
        member = client.post("/api/club/join", headers=dev, json={
            "name": "Asha Rao", "kind": "student", "organization": "City College of Engineering", "title": "B.Tech, 3rd year"})
        assert member.get_json()["member"]["organization"] == "City College of Engineering"

        launched = client.post("/api/club/submit", headers=dev, json={
            "title": "Helper", "tagline": "Answers questions", "description": "An AI helper.", "category": "AI"}).get_json()
        pid = launched["project"]["id"]
        assert launched["project"]["status"] == "in_review"
        assert launched["checks"]["uses_ai"] is True and launched["checks"]["endpoints"] == 1
        me = client.get("/api/club/me", headers=dev).get_json()
        assert [c["kind"] for c in me["certificates"]] == ["participant"]       # every developer gets one
        assert client.get("/api/club/marketplace").get_json()["projects"] == []   # not listed until approved
        assert client.get(f"/api/club/projects/{pid}").status_code == 404        # not public yet

        assert client.get("/api/club/review", headers=dev).status_code == 403
        detail = client.get(f"/api/club/review/{pid}", headers=judge).get_json()
        assert "ai(" in detail["project"]["backend"] and detail["checks"]["parse_errors"] == []
        no_notes = client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "changes"})
        assert no_notes.status_code == 400
        client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "changes", "notes": "Add a test block"})
        assert client.get("/api/club/me", headers=dev).get_json()["projects"][0]["review_notes"] == "Add a test block"

        put_app(client, dev, BACKEND + '\ntest "answers"\n    assert answer("hi").reply != ""\n')
        again = client.post("/api/club/submit", headers=dev, json={"title": "Helper", "project_id": pid}).get_json()
        assert again["project"]["version"] == 2 and again["checks"]["tests"] == 1
        assert client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "approve"}).status_code == 200

        listed = client.get("/api/club/marketplace").get_json()["projects"]
        assert [p["id"] for p in listed] == [pid] and listed[0]["author_org"] == "City College of Engineering"
        assert "backend" not in listed[0]
        public = client.get(f"/api/club/projects/{pid}").get_json()["project"]
        assert public["backend"].startswith("query(") and public["author_kind"] == "student"

        client.post(f"/api/club/review/{pid}/award", headers=judge, json={"category": "best_ai", "note": "Clever prompts"})
        dup = client.post(f"/api/club/review/{pid}/award", headers=judge, json={"category": "best_ai"})
        assert dup.status_code == 400
        client.post(f"/api/club/review/{pid}/spotlight", headers=judge, json={"spotlight": "funding"})
        assert [p["id"] for p in client.get("/api/club/marketplace?award=best_ai").get_json()["projects"]] == [pid]
        assert client.get("/api/club/marketplace?award=best_innovation").get_json()["projects"] == []
        assert len(client.get("/api/club/marketplace?spotlight=funding&kind=student&q=City").get_json()["projects"]) == 1
        assert client.get("/api/club/marketplace?kind=professional").get_json()["projects"] == []

        certs = client.get("/api/club/me", headers=dev).get_json()["certificates"]
        assert [c["kind"] for c in certs] == ["participant", "certified", "award"]
        award_cert = certs[2]
        verified = client.get(f"/api/club/certificates/{award_cert['code']}").get_json()      # no sign-in needed
        assert verified["valid"] and verified["certificate"]["award_label"] == "Best AI-Powered Application"
        assert verified["certificate"]["holder"] == "Asha Rao" and verified["certificate"]["project_title"] == "Helper"
        assert client.get("/api/club/certificates/MCN-NOTREAL123").status_code == 404

        stats = client.get("/api/club/review", headers=judge).get_json()["stats"]
        assert stats["projects_by_status"]["approved"] == 1 and stats["awards"]["best_ai"] == 1
        assert stats["spotlights"]["funding"] == 1 and stats["members_by_kind"]["student"] == 1
        assert stats["top_organizations"][0] == {"organization": "City College of Engineering", "kind": "student",
                                                 "approved": 1}
        assert stats["approved_using_ai"] == 1

        client.post(f"/api/club/projects/{pid}/withdraw", headers=dev)
        assert client.get("/api/club/marketplace").get_json()["projects"] == []


def test_broken_apps_are_not_launched_and_nobody_reviews_their_own(client):
    dev = register(client, "pro@company.example")
    with hosted():
        client.post("/api/club/join", headers=dev, json={"name": "Ravi", "kind": "professional", "organization": "Acme"})
        put_app(client, dev, backend="service s\n    endpoint broken(\n")
        res = client.post("/api/club/submit", headers=dev, json={"title": "Broken"})
        assert res.status_code == 400 and "Fix these errors" in res.get_json()["error"]
        put_app(client, dev, backend="", ui="")
        assert "empty" in client.post("/api/club/submit", headers=dev, json={"title": "Empty"}).get_json()["error"]
        assert client.post("/api/club/submit", json={"title": "x"}).status_code == 401
        assert client.post("/api/club/review/abc", headers=dev, json={"decision": "approve"}).status_code == 403


def test_open_an_approved_project_in_my_workspace(client):
    dev = register(client, "maker@college.example")
    judge = register(client, "judge@example.com")
    other = register(client, "other@company.example")
    with hosted():
        client.post("/api/club/join", headers=dev, json={"name": "M", "kind": "student", "organization": "X University"})
        put_app(client, dev)
        pid = client.post("/api/club/submit", headers=dev, json={"title": "Helper"}).get_json()["project"]["id"]
        assert client.post(f"/api/club/projects/{pid}/open", headers=other).status_code == 404      # not approved yet
        client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "approve"})
        assert client.post(f"/api/club/projects/{pid}/open", headers=other).get_json()["success"]
        mine = client.get("/api/workspace/file?path=backend/main.mcn", headers=other).get_json()
        assert "service helper" in mine["content"]


def test_pages_are_served(client):
    with hosted():
        for path in ("/club", "/club/project/abc", "/club/certificate/MCN-ABC", "/club/leaderboard", "/club/awards", "/club/verify", "/club/u/x", "/club/seasons", "/club/season/abc"):
            res = client.get(path)
            assert res.status_code == 200 and b"MCN Developer Club" in res.data


def test_installed_studio_forwards_with_the_local_files(client, monkeypatch, tmp_path):
    from mcn.core_engine import account
    sent = {}

    def fake_request(method, url, payload=None, token="", timeout=10):
        sent.update(method=method, url=url, payload=payload, token=token)
        return 200, {"project": {"id": "p1", "status": "in_review"}}
    monkeypatch.setattr(account, "account_url", lambda: "https://club.example")
    monkeypatch.setattr(account, "token", lambda: "tok-123")
    monkeypatch.setattr(account, "_request", fake_request)
    put_app(client, {})
    res = client.post("/api/club/submit", json={"title": "Helper"})
    assert res.status_code == 200 and res.get_json()["club_url"] == "https://club.example/club"
    assert sent["url"] == "https://club.example/api/club/submit" and sent["token"] == "tok-123"
    assert sent["payload"]["title"] == "Helper" and "service helper" in sent["payload"]["backend"]
    monkeypatch.setattr(account, "account_url", lambda: "")
    assert client.get("/api/club/me").status_code == 409


def approved_app(client, email="builder@college.example", title="Helper", org="X University", judge=None):
    dev = register(client, email)
    judge = judge or register(client, "judge@example.com")
    with hosted():
        client.post("/api/club/join", headers=dev, json={"name": email.split("@")[0].title(), "kind": "student",
                                                          "organization": org})
        put_app(client, dev)
        pid = client.post("/api/club/submit", headers=dev, json={"title": title}).get_json()["project"]["id"]
        client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "approve"})
    return dev, judge, pid


def test_usage_counts_other_members_once(client):
    dev, judge, pid = approved_app(client)
    users = [register(client, f"user{i}@company.example") for i in range(3)]
    with hosted():
        client.post(f"/api/club/projects/{pid}/open", headers=dev)                     # the author: not counted
        for u in users:
            client.post(f"/api/club/projects/{pid}/open", headers=u)
        client.post(f"/api/club/projects/{pid}/open", headers=users[0])               # again: still one person
        assert client.post(f"/api/club/projects/{pid}/like", headers=dev, json={"liked": True}).status_code == 400
        client.post(f"/api/club/projects/{pid}/like", headers=users[1], json={"liked": True})
        client.post(f"/api/club/projects/{pid}/like", headers=users[2], json={"liked": True})
        client.post(f"/api/club/projects/{pid}/like", headers=users[2], json={"liked": False})
        client.get(f"/api/club/projects/{pid}?view=1")
        client.get(f"/api/club/projects/{pid}?view=1")                                 # same visitor, same day
        client.get(f"/api/club/projects/{pid}?view=1", headers=users[0])
        page = client.get(f"/api/club/projects/{pid}", headers=users[1]).get_json()["project"]
        assert page["usage"] == {"uses": 3, "recent_uses": 3, "likes": 1, "views": 2} and page["liked"] is True
        assert client.post(f"/api/club/projects/{pid}/like", json={"liked": True}).status_code == 401


def test_best_apps_by_usage(client):
    _, judge, popular = approved_app(client, "a@college.example", "Popular", "A College")
    _, _, quiet = approved_app(client, "b@company.example", "Quiet", "B Corp", judge=judge)
    fans = [register(client, f"fan{i}@company.example") for i in range(2)]
    with hosted():
        for f in fans:
            client.post(f"/api/club/projects/{popular}/open", headers=f)
        client.post(f"/api/club/projects/{quiet}/like", headers=fans[0], json={"liked": True})
        titles = lambda sort: [p["title"] for p in client.get(f"/api/club/marketplace?sort={sort}").get_json()["projects"]]
        assert titles("most_used") == ["Popular", "Quiet"] and titles("most_liked") == ["Quiet", "Popular"]
        assert titles("trending")[0] == "Popular" and titles("newest") == ["Quiet", "Popular"]
        board = client.get("/api/club/leaderboard").get_json()                         # public
        assert board["most_used"][0]["title"] == "Popular" and board["builders"][0]["organization"] == "A College"
        assert board["builders"][0]["uses"] == 2
        stats = client.get("/api/club/review", headers=judge).get_json()["stats"]
        assert stats["top_used"][0]["title"] == "Popular" and stats["top_used"][0]["uses"] == 2
        author = board["most_used"][0]["user_id"]
        profile = client.get(f"/api/club/members/{author}").get_json()["member"]      # public profile
        assert profile["organization"] == "A College" and profile["uses"] == 2 and len(profile["certificates"]) == 2
        assert client.get("/api/club/members/nobody").status_code == 404
        info = client.get("/api/club/info").get_json()
        assert info["counts"]["apps"] == 2 and info["counts"]["organizations"] == 2 and "most_used" in info["sorts"]


def test_precheck_runs_on_the_workspace(client):
    dev = register(client, "pre@college.example")
    with hosted():
        put_app(client, dev)
        res = client.post("/api/club/precheck", headers=dev, json={}).get_json()
        assert res["ready"] is True and res["checks"]["uses_ai"] is True and res["checks"]["tests"] == 0
        put_app(client, dev, backend="service s\n    endpoint broken(\n")
        assert client.post("/api/club/precheck", headers=dev, json={}).get_json()["ready"] is False


def test_signatory_comes_from_config(client, monkeypatch):
    monkeypatch.setenv("MCN_CLUB_SIGNATORY", "Dr. A. Kumar|Programme Director")
    with hosted():
        assert client.get("/api/club/info").get_json()["signatory"] == {"name": "Dr. A. Kumar", "title": "Programme Director"}


def test_seasons_and_scoring(client, monkeypatch):
    import time as _time
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "judge@example.com,second@example.com")
    judge = register(client, "judge@example.com")
    second = register(client, "second@example.com")
    dev = register(client, "maya@college.example")
    fan = register(client, "fan@company.example")
    now = _time.time()
    with hosted():
        assert client.post("/api/club/seasons", headers=dev, json={"name": "X"}).status_code == 403
        bad = client.post("/api/club/seasons", headers=judge, json={"name": "Bad", "starts_at": now, "ends_at": now - 5})
        assert bad.status_code == 400 and "after the start" in bad.get_json()["error"]
        spring = client.post("/api/club/seasons", headers=judge, json={
            "name": "Spring 2027", "theme": "AI for healthcare", "starts_at": now - 86400, "ends_at": now + 7 * 86400}).get_json()["season"]
        later = client.post("/api/club/seasons", headers=judge, json={
            "name": "Autumn 2027", "starts_at": now + 30 * 86400, "ends_at": now + 60 * 86400}).get_json()["season"]
        assert spring["status"] == "open" and later["status"] == "upcoming"
        assert [s["name"] for s in client.get("/api/club/info").get_json()["open_seasons"]] == ["Spring 2027"]

        client.post("/api/club/join", headers=dev, json={"name": "Maya", "kind": "student", "organization": "Y College"})
        put_app(client, dev)
        refused = client.post("/api/club/submit", headers=dev, json={"title": "Early", "season_id": later["id"]})
        assert refused.status_code == 400 and "isn't taking entries" in refused.get_json()["error"]
        entry = client.post("/api/club/submit", headers=dev, json={"title": "Triage Bot", "season_id": spring["id"]}).get_json()["project"]
        pid = entry["id"]
        assert entry["season"]["name"] == "Spring 2027"

        assert client.post(f"/api/club/review/{pid}/score", headers=dev, json={"scores": {}}).status_code == 403
        missing = client.post(f"/api/club/review/{pid}/score", headers=judge, json={"scores": {"overall": 4}})
        assert missing.status_code == 400 and "Innovation" in missing.get_json()["error"]
        out_of_range = client.post(f"/api/club/review/{pid}/score", headers=judge, json={"scores": {
            "overall": 9, "innovation": 4, "technical": 4, "use_of_mcn": 4, "ai": "na"}})
        assert out_of_range.status_code == 400
        client.post(f"/api/club/review/{pid}/score", headers=judge, json={"scores": {
            "overall": 4, "innovation": 5, "technical": 3, "use_of_mcn": 4, "ai": 5}, "note": "Strong idea"})
        scored = client.post(f"/api/club/review/{pid}/score", headers=second, json={"scores": {
            "overall": 5, "innovation": 4, "technical": 4, "use_of_mcn": 4, "ai": "na"}}).get_json()
        sc = scored["project"]["scores"]
        assert sc["reviewers"] == 2 and sc["averages"]["overall"] == 4.5 and sc["averages"]["ai"] == 5
        assert sc["total"] == round((4.5 + 4.5 + 3.5 + 4 + 5) / 5, 2)
        mine = client.get(f"/api/club/review/{pid}", headers=judge).get_json()["mine"]
        assert mine == {"scores": {"overall": 4, "innovation": 5, "technical": 3, "use_of_mcn": 4, "ai": 5}, "note": "Strong idea"}

        client.post(f"/api/club/review/{pid}", headers=judge, json={"decision": "approve"})
        client.post(f"/api/club/projects/{pid}/open", headers=fan)
        public = client.get(f"/api/club/projects/{pid}").get_json()["project"]
        assert "scores" not in public and public["season"]["id"] == spring["id"]
        assert all("scores" not in p for p in client.get("/api/club/marketplace").get_json()["projects"])
        assert client.get("/api/club/me", headers=dev).get_json()["projects"][0]["scores"]["reviewers"] == 2   # feedback
        assert [p["id"] for p in client.get(f"/api/club/marketplace?season={spring['id']}").get_json()["projects"]] == [pid]
        assert client.get(f"/api/club/marketplace?season={later['id']}").get_json()["projects"] == []

        assert client.get(f"/api/club/seasons/{spring['id']}/standings", headers=dev).status_code == 403
        table = client.get(f"/api/club/seasons/{spring['id']}/standings", headers=judge).get_json()
        assert table["ranked"][0]["id"] == pid and table["suggestions"]["best_ai"]["project_id"] == pid
        assert table["suggestions"]["best_innovation"]["score"] == 4.5 and table["peoples_choice"]["uses"] == 1

        client.post(f"/api/club/review/{pid}/award", headers=judge, json={"category": "best_innovation"})
        cert = [c for c in client.get("/api/club/me", headers=dev).get_json()["certificates"] if c["kind"] == "award"][0]
        assert cert["title"] == "Best Innovation: Triage Bot · Spring 2027"
        assert client.get(f"/api/club/certificates/{cert['code']}").get_json()["certificate"]["season"] == "Spring 2027"

        page = client.get(f"/api/club/seasons/{spring['id']}").get_json()["season"]
        assert page["winners"] == {} and len(page["entries"]) == 1 and "scores" not in page["entries"][0]
        assert client.post(f"/api/club/seasons/{spring['id']}", headers=dev, json={"results_published": True}).status_code == 403
        client.post(f"/api/club/seasons/{spring['id']}", headers=judge, json={"results_published": True})
        page = client.get(f"/api/club/seasons/{spring['id']}").get_json()["season"]
        assert page["status"] == "closed" and [p["id"] for p in page["winners"]["best_innovation"]] == [pid]
        listed = {s["name"]: s for s in client.get("/api/club/seasons").get_json()["seasons"]}
        assert listed["Spring 2027"]["approved"] == 1 and listed["Autumn 2027"]["status"] == "upcoming"


def test_old_club_databases_gain_season_columns(tmp_path):
    import sqlite3
    from playground_server import club_store
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE club_projects (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, tagline TEXT, "
                "description TEXT, category TEXT, backend TEXT, ui TEXT, stats TEXT, status TEXT NOT NULL, version INTEGER DEFAULT 1, "
                "submitted_at REAL, reviewed_at REAL, reviewer TEXT, review_notes TEXT, spotlight TEXT, listed_at REAL)")
    old.execute("CREATE TABLE club_awards (project_id TEXT NOT NULL, category TEXT NOT NULL, note TEXT, awarded_by TEXT, "
                "awarded_at REAL, PRIMARY KEY (project_id, category))")
    old.commit()
    old.close()
    before = club_store._DB_PATH
    try:
        club_store.set_db_path(db)
        assert club_store.seasons() == []
        cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(club_projects)")}
        assert "season_id" in cols
    finally:
        club_store.set_db_path(before)
