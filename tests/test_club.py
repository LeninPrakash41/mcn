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
        for path in ("/club", "/club/project/abc", "/club/certificate/MCN-ABC"):
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
