"""
Accounts across installs: local Studio (no accounts, signs in to an account
server), hosted Studio (everyone signs in, admins manage users), and device
sign-in between them.
"""
import json
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playground_app import load  # noqa: E402

PWD = "SecurePassword123!"


@pytest.fixture
def client(tmp_path, monkeypatch):
    _, c = load()
    from mcn.core_engine import auth_primitives
    from playground_server import device_store, rate_limit
    rate_limit.reset_all()
    monkeypatch.setattr(auth_primitives, "_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(device_store, "_DB_PATH", tmp_path / "device_sessions.db")
    monkeypatch.setenv("MCN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MCN_ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("MCN_STUDIO_SIGNUP_DOMAINS", raising=False)
    monkeypatch.delenv("MCN_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("MCN_STUDIO_MODE", raising=False)
    return c


@contextmanager
def hosted():
    with patch.dict(os.environ, {"MCN_STUDIO_MODE": "hosted"}):
        yield


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def register(c, email):
    with hosted():
        res = c.post("/api/auth/register", json={"email": email, "password": PWD})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["token"]


# ── Local Studio ──────────────────────────────────────────────────────────────

def test_local_studio_has_no_accounts(client):
    assert client.get("/api/studio/mode").get_json()["mode"] == "local"
    res = client.post("/api/auth/register", json={"email": "a@example.com", "password": PWD})
    assert res.status_code == 404 and res.get_json()["mode"] == "local"
    assert client.post("/api/admin/login", json={"email": "a@example.com", "password": PWD}).status_code == 404
    assert client.get("/api/admin/overview").status_code == 404
    page = client.get("/admin")
    assert page.status_code == 200 and b"account server" in page.data
    assert client.get("/device").status_code == 404
    assert client.post("/api/device/code", json={}).status_code == 404


def test_local_studio_ignores_tokens_for_workspaces(client):
    token = register(client, "someone@example.com")
    client.post("/api/workspace/file", headers=bearer(token), json={"path": "mine.mcn", "content": "var a = 1\n"})
    files = client.get("/api/workspace/files").get_json()["files"]
    assert any(f["path"] == "mine.mcn" for f in files)        # one shared workspace, token or not


# ── Hosted Studio ─────────────────────────────────────────────────────────────

def test_hosted_studio_requires_sign_in(client):
    with hosted():
        res = client.get("/api/workspace/files")
        assert res.status_code == 401 and res.get_json()["needs_login"] is True
        assert client.post("/api/execute", json={"code": "log(1)"}).status_code == 401
        assert client.get("/api/health").get_json()["mode"] == "hosted"
        assert client.get("/api/studio/mode").get_json() == {"mode": "hosted"}
        assert client.get("/preview-mobile/").status_code == 401
    token = register(client, "dev@example.com")
    with hosted():
        assert client.get("/api/workspace/files", headers=bearer(token)).status_code == 200


def test_cookie_counts_for_get_only(client):
    token = register(client, "cookie@example.com")
    with hosted():
        client.set_cookie("mcn_token", token)
        assert client.get("/api/workspace/files").status_code == 200
        assert client.post("/api/workspace/file", json={"path": "x.mcn", "content": ""}).status_code == 401
        client.delete_cookie("mcn_token")


def test_sign_up_checks(client, monkeypatch):
    with hosted():
        bad = client.post("/api/auth/register", json={"email": "<img src=x onerror=alert(1)>@a.com", "password": PWD})
        assert bad.status_code == 400
        monkeypatch.setenv("MCN_STUDIO_SIGNUP_DOMAINS", "college.edu")
        assert client.post("/api/auth/register", json={"email": "x@gmail.com", "password": PWD}).status_code == 403
        assert client.post("/api/auth/register", json={"email": "x@college.edu", "password": PWD}).status_code == 200


def test_admin_emails_become_admins(client, monkeypatch):
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "Owner@Example.com")
    token = register(client, "owner@example.com")
    with hosted():
        me = client.get("/api/auth/me", headers=bearer(token)).get_json()["user"]
        assert "admin" in me["roles"]
        assert client.get("/api/admin/users", headers=bearer(token)).status_code == 200
    plain = register(client, "student@example.com")
    with hosted():
        assert client.get("/api/admin/users", headers=bearer(plain)).status_code == 403


# ── Device sign-in ────────────────────────────────────────────────────────────

def test_device_sign_in_approve_use_and_revoke(client, monkeypatch):
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "admin@example.com")
    admin = register(client, "admin@example.com")
    user = register(client, "ana@example.com")
    with hosted():
        started = client.post("/api/device/code", json={"client_name": "MCN on ana-mac (Darwin)"}).get_json()
        assert started["verification_uri_complete"].endswith(f"/device?code={started['user_code']}")
        assert len(started["user_code"]) == 9 and started["user_code"][4] == "-"
        assert client.get("/device").status_code == 200

        poll = lambda: client.post("/api/device/token", json={"device_code": started["device_code"]})
        assert poll().status_code == 428                                   # not approved yet

        assert client.post("/api/device/lookup", json={"user_code": started["user_code"]}).status_code == 401
        info = client.post("/api/device/lookup", headers=bearer(user),
                           json={"user_code": started["user_code"].lower().replace("-", "")}).get_json()
        assert info["client_name"] == "MCN on ana-mac (Darwin)"
        ok = client.post("/api/device/approve", headers=bearer(user), json={"user_code": started["user_code"]})
        assert ok.get_json()["status"] == "approved"

        got = poll()
        assert got.status_code == 200
        device_token = got.get_json()["token"]
        assert got.get_json()["user"]["email"] == "ana@example.com"
        assert poll().status_code == 410                                   # handed over only once

        me = client.get("/api/auth/me", headers=bearer(device_token))
        assert me.status_code == 200 and me.get_json()["user"]["email"] == "ana@example.com"

        users = client.get("/api/admin/users", headers=bearer(admin)).get_json()["users"]
        ana = next(u for u in users if u["email"] == "ana@example.com")
        assert [d["client_name"] for d in ana["devices"]] == ["MCN on ana-mac (Darwin)"]

        sid = ana["devices"][0]["sid"]
        assert client.post("/api/admin/devices/revoke", headers=bearer(user), json={"sid": sid}).status_code == 403
        assert client.post("/api/admin/devices/revoke", headers=bearer(admin), json={"sid": sid}).status_code == 200
        assert client.get("/api/auth/me", headers=bearer(device_token)).status_code == 401
        assert client.get("/api/auth/me", headers=bearer(user)).status_code == 200   # the browser sign-in is separate


def test_device_sign_in_denied(client):
    user = register(client, "bo@example.com")
    with hosted():
        started = client.post("/api/device/code", json={}).get_json()
        client.post("/api/device/approve", headers=bearer(user), json={"user_code": started["user_code"], "approve": False})
        res = client.post("/api/device/token", json={"device_code": started["device_code"]})
        assert res.status_code == 403 and res.get_json()["status"] == "denied"
        again = client.post("/api/device/approve", headers=bearer(user), json={"user_code": started["user_code"]})
        assert again.status_code == 404


# ── The client used by local Studio and `mcn login` ───────────────────────────

@pytest.fixture
def account_server(client, monkeypatch):
    """Route the account client's HTTP calls to the test app in hosted mode."""
    from mcn.core_engine import account

    def fake_request(method, url, payload=None, token="", timeout=10):
        path = url.split("https://accounts.test", 1)[1]
        with hosted():
            res = client.open(path, method=method, json=payload, headers=bearer(token) if token else {})
        return res.status_code, res.get_json() or {}

    monkeypatch.setattr(account, "_request", fake_request)
    monkeypatch.setenv("MCN_ACCOUNT_URL", "https://accounts.test")
    return account


def _approve(client, user_token, user_code):
    with hosted():
        res = client.post("/api/device/approve", headers=bearer(user_token), json={"user_code": user_code})
    assert res.status_code == 200


def test_client_signs_in_stores_and_signs_out(client, account_server):
    account = account_server
    user = register(client, "cli@example.com")
    started = account.start_login()
    assert account.poll_login(started["device_code"])["status"] == "pending"
    _approve(client, user, started["user_code"])
    assert account.poll_login(started["device_code"])["status"] == "approved"

    cred_file = Path(os.environ["MCN_HOME"]) / "credentials.json"
    assert stat.S_IMODE(cred_file.stat().st_mode) == 0o600
    assert json.loads(cred_file.read_text())["account_url"] == "https://accounts.test"
    info = account.status(refresh=True)
    assert info["signed_in"] and info["user"]["email"] == "cli@example.com"

    result = account.logout()
    assert result["revoked_on_server"] is True and not cred_file.exists()
    assert account.status()["signed_in"] is False


def test_client_notices_remote_sign_out(client, account_server, monkeypatch):
    account = account_server
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "boss@example.com")
    admin = register(client, "boss@example.com")
    user = register(client, "kai@example.com")
    started = account.start_login()
    _approve(client, user, started["user_code"])
    account.poll_login(started["device_code"])
    with hosted():
        users = client.get("/api/admin/users", headers=bearer(admin)).get_json()["users"]
        sid = next(u for u in users if u["email"] == "kai@example.com")["devices"][0]["sid"]
        client.post("/api/admin/devices/revoke", headers=bearer(admin), json={"sid": sid})
    info = account.status(refresh=True)
    assert info["signed_in"] is False and info["signed_out_remotely"] is True


def test_client_needs_an_https_server(monkeypatch, tmp_path):
    from mcn.core_engine import account
    monkeypatch.setenv("MCN_HOME", str(tmp_path))
    monkeypatch.setenv("MCN_ACCOUNT_URL", "")
    monkeypatch.setattr(account, "DEFAULT_ACCOUNT_URL", "")
    with pytest.raises(account.AccountError, match="No MCN account server"):
        account.start_login()
    with pytest.raises(account.AccountError, match="https"):
        account.start_login("http://example.com")


def test_local_studio_sign_in_endpoints(client, account_server):
    user = register(client, "studio@example.com")
    status = client.get("/api/account").get_json()
    assert status["signed_in"] is False and status["account_url"] == "https://accounts.test"
    started = client.post("/api/account/login").get_json()
    assert set(started) >= {"device_code", "user_code", "verification_uri_complete"}
    assert client.post("/api/account/poll", json={"device_code": started["device_code"]}).get_json()["status"] == "pending"
    _approve(client, user, started["user_code"])
    done = client.post("/api/account/poll", json={"device_code": started["device_code"]}).get_json()
    assert done["status"] == "approved" and done["user"]["email"] == "studio@example.com"
    assert "token" not in json.dumps(client.get("/api/account").get_json())   # the page never sees the token
    assert client.post("/api/account/logout").get_json()["signed_in"] is False
    with hosted():
        assert client.get("/api/account").status_code == 401                 # hosted Studio doesn't use these


# ── Attempt limits ────────────────────────────────────────────────────────────

def test_failed_sign_ins_are_limited_per_account(client):
    register(client, "guess@example.com")
    with hosted():
        for _ in range(10):
            res = client.post("/api/auth/login", json={"email": "guess@example.com", "password": "wrong-pass"})
            assert res.status_code == 401
        res = client.post("/api/auth/login", json={"email": "guess@example.com", "password": PWD})
        assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0
        assert "Too many failed sign-in attempts" in res.get_json()["error"]
        # The admin sign-in shares the same limit
        assert client.post("/api/admin/login", json={"email": "guess@example.com", "password": PWD}).status_code == 429
        # Another account isn't affected
        assert client.post("/api/auth/login", json={"email": "other@example.com", "password": "x" * 8}).status_code == 401


def test_successful_sign_in_resets_the_count(client):
    register(client, "typo@example.com")
    with hosted():
        for _ in range(9):
            client.post("/api/auth/login", json={"email": "typo@example.com", "password": "wrong-pass"})
        assert client.post("/api/auth/login", json={"email": "typo@example.com", "password": PWD}).status_code == 200
        for _ in range(9):
            assert client.post("/api/auth/login", json={"email": "typo@example.com", "password": "wrong-pass"}).status_code == 401


def test_wrong_device_codes_are_limited(client):
    user = register(client, "codes@example.com")
    with hosted():
        for _ in range(10):
            assert client.post("/api/device/lookup", headers=bearer(user), json={"user_code": "AAAA-AAAA"}).status_code == 404
        started = client.post("/api/device/code", json={}).get_json()
        res = client.post("/api/device/approve", headers=bearer(user), json={"user_code": started["user_code"]})
        assert res.status_code == 429


def test_admin_shows_the_real_version(client, monkeypatch):
    from mcn.version import __version__
    monkeypatch.setenv("MCN_ADMIN_EMAILS", "ver@example.com")
    token = register(client, "ver@example.com")
    with hosted():
        overview = client.get("/api/admin/overview", headers=bearer(token)).get_json()
    assert overview["system"]["app_version"] == __version__
