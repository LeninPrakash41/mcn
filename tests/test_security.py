"""
Security: built-in check functions, service auth, what the server lets through,
and `mcn audit`.
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import mcn_server, security  # noqa: E402
from mcn.core_engine.mcn_interpreter import MCNInterpreter  # noqa: E402
from mcn.core_engine.security_audit import audit_source  # noqa: E402


def run(code):
    interp = MCNInterpreter()
    interp.execute(code, quiet=True)
    return interp


def value(expr):
    return run(f"var out = {expr}").variables["out"]


# ── Built-in check functions ────────────────────────────────────────────────

def test_escape_and_sanitize_html():
    assert value('escape_html("<b>hi</b> & \'x\'")') == "&lt;b&gt;hi&lt;/b&gt; &amp; &#x27;x&#x27;"
    clean = value('sanitize_html("<p onclick=\\"x()\\">ok <script>bad()</script><a href=\\"javascript:alert(1)\\">l</a></p>")')
    assert "script" not in clean and "onclick" not in clean and "javascript:" not in clean
    assert clean.startswith("<p>ok")


def test_validate_reports_each_problem():
    res = value('validate({email: "nope", age: 7, plan: "gold"}, '
                '{email: "required|email", age: "number|min:18", plan: "in:free,pro", name: "required"})')
    assert res["valid"] is False
    assert set(res["errors"]) == {"email", "age", "plan", "name"}
    assert value('validate({email: "a@b.co", age: 30}, {email: "required|email", age: "integer|min:18"})')["valid"] is True


def test_email_url_password_mask_token():
    assert value('is_email("dev@mcn.dev")') is True and value('is_email("dev@")') is False
    assert value('is_url("https://mcn.dev/x")') is True and value('is_url("javascript:alert(1)")') is False
    assert value('password_strength("password")')["ok"] is False
    assert value('password_strength("c0rrect-Horse-battery")')["ok"] is True
    assert value('mask("sk-ant-1234567890")').endswith("7890") and "1234" not in value('mask("sk-ant-1234567890")')
    assert len(value("secure_token()")) >= 32
    assert value('safe_equals("abc", "abc")') is True and value('safe_equals("abc", "abd")') is False


def test_rate_limit_allows_then_blocks():
    interp = run('var a = rate_limit("t-key", 2, 60)\nvar b = rate_limit("t-key", 2, 60)\nvar c = rate_limit("t-key", 2, 60)')
    assert [interp.variables[k] for k in "abc"] == [True, True, False]


def test_require_raises_clean_error():
    with pytest.raises(Exception) as err:
        run('require(false, "Only admins can do that")')
    assert "Only admins can do that" in str(err.value)
    assert "failed" not in str(err.value).lower()


def test_audit_log_chain_detects_tampering(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCN_APP_AUDIT_LOG", str(log))
    run('audit_log("refund", {order: 7, amount: 20}, "ana")\naudit_log("login", {}, "ben")')
    assert value("verify_audit_log()")["valid"] is True
    lines = log.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["details"]["amount"] = 2000
    log.write_text(json.dumps(entry) + "\n" + lines[1] + "\n")
    assert value("verify_audit_log()")["valid"] is False


def test_no_hardcoded_default_secret():
    from mcn.core_engine import auth_primitives
    assert "change-in-production" not in str(auth_primitives._SECRET)
    assert len(auth_primitives._SECRET) >= 32


# ── Service auth and the server ─────────────────────────────────────────────

SERVICE = '''
service api
    auth "token"
    public health

    endpoint health()
        return {ok: true}

    endpoint secret()
        return {secret: 42}
'''


def test_auth_parses_into_endpoint_modes():
    interp = run(SERVICE)
    assert interp._evaluator.endpoint_auth == {"health": "", "secret": "token"}


def test_unknown_auth_mode_is_a_syntax_error():
    with pytest.raises(Exception) as err:
        run('service s\n    auth "magic"\n\n    endpoint a()\n        return 1')
    assert "auth" in str(err.value)


def test_check_auth_fails_closed_without_server_token(monkeypatch):
    monkeypatch.delenv("MCN_API_TOKEN", raising=False)
    ok, _, error = security.check_auth("token", "Bearer anything")
    assert not ok and "MCN_API_TOKEN" in error


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("MCN_API_TOKEN", "test-token")
    monkeypatch.setenv("MCN_RATE_LIMIT", "1000")
    monkeypatch.setenv("MCN_MAX_BODY_BYTES", "200")
    security.SERVER_LIMITER.reset() if hasattr(security.SERVER_LIMITER, "reset") else None
    script = tmp_path / "api.mcn"
    script.write_text(SERVICE)
    ev = mcn_server._load_evaluator(str(script))
    srv = HTTPServer(("127.0.0.1", 0), mcn_server._make_handler(ev))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def call(url, token=None, data=None):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read()), res.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


def test_server_enforces_token(server):
    assert call(f"{server}/health")[0] == 200
    assert call(f"{server}/secret")[0] == 401
    assert call(f"{server}/secret", "wrong")[0] == 401
    status, body, headers = call(f"{server}/secret", "test-token")
    assert (status, body) == (200, {"secret": 42})
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_server_never_exposes_builtins(server):
    for name in ("query", "write_file", "read_file", "env"):
        assert call(f"{server}/{name}", "test-token")[0] == 404


def test_server_rejects_large_bodies(server):
    assert call(f"{server}/health", data=b"{" + b" " * 500 + b"}")[0] == 413


def test_server_rate_limits(server, monkeypatch):
    monkeypatch.setenv("MCN_RATE_LIMIT", "3")
    security.SERVER_LIMITER.__init__()
    codes = [call(f"{server}/health")[0] for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429


# ── mcn audit ───────────────────────────────────────────────────────────────

def rules(code):
    return {f.rule for f in audit_source(code)}


def test_audit_finds_sql_injection():
    assert "sql-injection" in rules('service s\n    endpoint f(id)\n        return query("SELECT * FROM t WHERE id = " + id)')
    assert "sql-injection" in rules('service s\n    endpoint f(n)\n        return query("SELECT * FROM t WHERE n = \'{n}\'")')
    assert "sql-injection" not in rules('service s\n    endpoint f(id)\n        return query("SELECT * FROM t WHERE id = ?", (id,))')
    assert "sql-injection" not in rules('query("INSERT INTO p VALUES (\'shot of {{subject}}\')")')


def test_audit_finds_secrets_and_weak_hashes():
    assert "hardcoded-secret" in rules('var api_key = "sk-ant-api03-abcdefghijklmnopqrstu"')
    assert "hardcoded-secret" in rules('var db_password = "hunter2hunter2"')
    assert "hardcoded-secret" not in rules('var api_key = env("API_KEY")')
    assert "weak-password-hash" in rules('function save(password)\n    return sha256(password)')


def test_audit_finds_request_controlled_paths_and_urls():
    found = rules('service s\n    endpoint get_file(name)\n        var p = "files/" + name\n        return read_file(p)\n\n'
                  '    endpoint proxy(url)\n        return fetch(url)')
    assert {"path-traversal", "request-forgery"} <= found


def test_audit_open_service_and_auth():
    assert "open-service" in rules('service s\n    endpoint delete_user(id)\n        return 1')
    assert "open-service" not in rules('service s\n    auth "token"\n\n    endpoint delete_user(id)\n        return 1')


def test_audit_cli_exit_codes(tmp_path):
    from mcn.core_engine.security_audit import audit_path
    bad = tmp_path / "bad.mcn"
    bad.write_text('var token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"')
    good = tmp_path / "good" / "ok.mcn"
    good.parent.mkdir()
    good.write_text('var x = 1')
    assert audit_path(str(bad)) == 1
    assert audit_path(str(good.parent)) == 0
