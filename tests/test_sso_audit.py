"""
Single sign-on (`auth "sso"`, OpenID Connect) and automatic audit logs (`audit`)
for MCN services, against a fake identity provider with real RS256 signatures.
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import security, sso  # noqa: E402

ISSUER = "https://idp.example.com"
CLIENT = "mcn-test-app"
SERVICE = '''
service hr_api
    auth "sso"
    audit
    public health

    endpoint health()
        return {ok: true}

    endpoint whoami()
        return {email: current_user().email, roles: current_user().roles}

    endpoint set_salary(employee, amount, password)
        return {saved: true}

    endpoint fail()
        throw "database is down"
'''


@pytest.fixture
def idp(monkeypatch, tmp_path):
    """A fake OIDC provider. Returns a function that signs ID tokens."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    meta = {"issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token", "jwks_uri": f"{ISSUER}/jwks",
            "token_endpoint_auth_methods_supported": ["client_secret_basic"]}
    state = {"claims": {}, "token_calls": []}

    def sign(**claims):
        base = {"iss": ISSUER, "aud": CLIENT, "sub": "u-123", "email": "ana@acme.com", "name": "Ana",
                "groups": ["hr", "admin"], "iat": int(time.time()), "exp": int(time.time()) + 300}
        base.update(claims)
        return jwt.encode(base, key, algorithm="RS256", headers={"kid": "k1"})

    def fake_get(url, timeout=None):
        assert url == f"{ISSUER}/.well-known/openid-configuration"
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: meta, status_code=200)

    def fake_post(url, data=None, auth=None, timeout=None, headers=None):
        state["token_calls"].append({"url": url, "data": data, "auth": auth})
        body = {"id_token": sign(**state["claims"]), "access_token": "at"}
        return SimpleNamespace(status_code=200, json=lambda: body)

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(sso, "_jwks_client", lambda uri: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    sso._discovery.clear()
    for name, value in {"MCN_SSO_ISSUER": ISSUER, "MCN_SSO_CLIENT_ID": CLIENT, "MCN_SSO_CLIENT_SECRET": "s3cret",
                        "MCN_APP_AUDIT_LOG": str(tmp_path / "audit.jsonl"),
                        "MCN_CORS_ORIGINS": "http://app.acme.com"}.items():
        monkeypatch.setenv(name, value)
    for name in ("MCN_SSO_ALLOWED_DOMAINS", "MCN_SSO_REDIRECT_URL", "MCN_DEV_TOOLS", "MCN_AUDIT_WEBHOOK"):
        monkeypatch.delenv(name, raising=False)
    security._tail_cache.clear()
    return SimpleNamespace(sign=sign, state=state, log=tmp_path / "audit.jsonl")


@pytest.fixture
def api(tmp_path, idp):
    from fastapi.testclient import TestClient
    from mcn.core_engine.mcn_server import MCNServer
    script = tmp_path / "main.mcn"
    script.write_text(SERVICE)
    server = MCNServer()
    server.load_script(str(script))
    client = TestClient(server.app, base_url="http://api.acme.com")
    client.idp = idp
    return client


def sign_in(api, return_to="http://app.acme.com/dashboard"):
    """Run the whole browser round trip; returns (callback response, token)."""
    start = api.get("/_auth/login", params={"return_to": return_to}, follow_redirects=False)
    assert start.status_code == 302, start.text
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(start.headers["location"]).query))
    # A real provider puts the nonce it was sent into the ID token
    api.idp.state["claims"].setdefault("nonce", query["nonce"])
    back = api.get("/_auth/callback", params={"code": "c0de", "state": query["state"]}, follow_redirects=False)
    token = None
    if back.status_code == 302:
        token = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(back.headers["location"]).fragment)).get("mcn_token")
    return start, query, back, token


def test_login_redirects_to_the_provider_with_pkce(api):
    start, query, _, _ = sign_in(api)
    assert start.headers["location"].startswith(f"{ISSUER}/authorize?")
    assert query["client_id"] == CLIENT and query["response_type"] == "code"
    assert query["code_challenge_method"] == "S256" and query["scope"] == "openid email profile"
    assert query["redirect_uri"] == "http://api.acme.com/_auth/callback"
    assert "HttpOnly" in start.headers["set-cookie"] and "SameSite=Lax" in start.headers["set-cookie"]


def test_full_sign_in_then_calling_endpoints(api, idp):
    _, _, back, token = sign_in(api)
    assert back.status_code == 302
    assert back.headers["location"].startswith("http://app.acme.com/dashboard#mcn_token=")
    call = idp.state["token_calls"][0]
    assert call["auth"] == (CLIENT, "s3cret") and call["data"]["code"] == "c0de" and call["data"]["code_verifier"]

    me = api.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json() == {"email": "ana@acme.com", "roles": ["hr", "admin"]}
    assert api.get("/_auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["name"] == "Ana"
    assert api.get("/health").status_code == 200                       # public endpoint


def test_signed_out_requests_point_to_sign_in(api):
    res = api.get("/whoami")
    assert res.status_code == 401 and res.json()["sso_login"] == "/_auth/login"
    # A plain MCN jwt (not from SSO) isn't accepted by an sso service
    from mcn.core_engine.auth_primitives import _make_token
    plain = _make_token({"sub": "x", "email": "x@acme.com"})
    assert api.get("/whoami", headers={"Authorization": f"Bearer {plain}"}).status_code == 401


def test_rejects_tampered_or_mismatched_sign_ins(api, idp):
    idp.state["claims"] = {"nonce": "not-the-one-we-sent"}
    _, _, back, token = sign_in(api)
    assert back.status_code == 401 and token is None and "nonce" in back.text

    idp.state["claims"] = {"aud": "some-other-app"}
    api.cookies.clear()
    _, _, back, _ = sign_in(api)
    assert back.status_code == 401 and "Couldn" in back.text

    # The callback without the browser's cookie (opened elsewhere, or forged)
    start = api.get("/_auth/login", follow_redirects=False)
    state = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(start.headers["location"]).query))["state"]
    api.cookies.clear()
    res = api.get("/_auth/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert res.status_code == 400 and "text/html" in res.headers["content-type"]


def test_allowed_domains_and_return_targets(api, idp, monkeypatch):
    monkeypatch.setattr(sso, "verify_id_token", lambda token, nonce=None: jwt.decode(
        idp.sign(email="mallory@gmail.com"), options={"verify_signature": False}))
    monkeypatch.setenv("MCN_SSO_ALLOWED_DOMAINS", "acme.com")
    _, _, back, token = sign_in(api)
    assert back.status_code == 403 and token is None

    assert sso.safe_return_to("https://evil.example/steal", "http://api.acme.com/") == "http://api.acme.com/"
    assert sso.safe_return_to("http://app.acme.com/x", "http://api.acme.com/") == "http://app.acme.com/x"
    assert sso.safe_return_to("http://localhost:5173/", "http://localhost:8080/") == "http://localhost:5173/"


def test_studio_preview_token_counts_only_in_dev_mode(monkeypatch):
    monkeypatch.setenv("MCN_API_TOKEN", "studio-dev")
    monkeypatch.delenv("MCN_DEV_TOOLS", raising=False)
    assert sso.check("Bearer studio-dev")[0] is False
    monkeypatch.setenv("MCN_DEV_TOOLS", "1")
    ok, user, _ = sso.check("Bearer studio-dev")
    assert ok and user["sub"] == "studio-preview"


def test_not_configured_or_missing_package(monkeypatch, tmp_path):
    monkeypatch.delenv("MCN_SSO_ISSUER", raising=False)
    status, headers, body = sso.handle("GET", "/_auth/login", "http://x/", {}, {}, None)
    assert status == 503 and "MCN_SSO_ISSUER" in body["__html__"]


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_every_call_is_audited_with_secrets_masked(api, idp):
    _, _, _, token = sign_in(api)
    auth = {"Authorization": f"Bearer {token}"}
    api.post("/set_salary", json={"employee": "bo", "amount": 90000, "password": "hunter2"}, headers=auth)
    api.post("/fail", json={}, headers=auth)
    api.get("/whoami")                                                  # refused: not signed in
    entries = [json.loads(line) for line in idp.log.read_text().splitlines()]
    by_action = {(e["action"], e["details"]["endpoint"]): e for e in entries}

    saved = by_action[("api.call", "set_salary")]
    assert saved["actor"] == "ana@acme.com" and saved["details"]["status"] == 200
    assert saved["details"]["args"] == {"employee": "bo", "amount": 90000, "password": "***"}
    assert "hunter2" not in idp.log.read_text()
    assert by_action[("api.error", "fail")]["details"]["error"].endswith("database is down")
    denied = by_action[("api.denied", "whoami")]
    assert denied["details"]["status"] == 401 and denied["actor"] is None
    assert security.verify_audit_log()["valid"] is True


def test_tampering_is_detected_and_ocsf_export(api, idp):
    _, _, _, token = sign_in(api)
    for _ in range(3):
        api.get("/health")
        api.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    event = security.to_ocsf(json.loads(idp.log.read_text().splitlines()[-1]))
    assert event["class_uid"] == 6003 and event["status"] == "Success"
    assert event["actor"]["user"]["name"] == "ana@acme.com" and event["api"]["operation"] == "whoami"

    lines = idp.log.read_text().splitlines()
    lines[1] = lines[1].replace('"status": 200', '"status": 201')
    idp.log.write_text("\n".join(lines) + "\n")
    assert security.verify_audit_log() == {"valid": False, "entries": len(lines), "broken_at": 2}


def test_audit_log_cli(api, idp, tmp_path, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    api.get("/health")
    out = tmp_path / "events.jsonl"
    monkeypatch.setattr(sys, "argv", ["mcn", "audit-log", "export", "--format", "ocsf", "--out", str(out)])
    assert main() == 0
    assert json.loads(out.read_text().splitlines()[0])["class_uid"] == 6003
    monkeypatch.setattr(sys, "argv", ["mcn", "audit-log", "verify"])
    assert main() == 0
    assert "intact" in capsys.readouterr().out


def test_services_without_audit_log_nothing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mcn.core_engine.mcn_server import MCNServer
    monkeypatch.setenv("MCN_APP_AUDIT_LOG", str(tmp_path / "none.jsonl"))
    script = tmp_path / "open.mcn"
    script.write_text("service open_api\n    endpoint ping()\n        return {ok: true}\n")
    server = MCNServer()
    server.load_script(str(script))
    assert TestClient(server.app).get("/ping").status_code == 200
    assert not (tmp_path / "none.jsonl").exists()
