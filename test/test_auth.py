"""
Login, roles and the audit log: `auth`, `allow`, `public`, `audit`.
"""

import json
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from mcn.core_engine.lexer import Lexer
from mcn.core_engine.parser import Parser, ParseError
from mcn.core_engine.mcn_interpreter import MCNInterpreter

APP = '''
auth
    roles admin, sales, viewer

contract Lead
    name:  str
    email: str unique

service crm
    crud Lead
        allow read:   admin, sales, viewer
        allow write:  admin, sales
        allow delete: admin
        audit

    endpoint whoami() allow admin, sales
        return {name: current_user.name, role: current_user.role}

    endpoint health() public
        return {ok: true}

    endpoint anyone()
        return {ok: true}
'''


def load(src=APP):
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    return interp


@pytest.fixture
def server(tmp_path, monkeypatch):
    from mcn.core_engine.mcn_server import _make_handler
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCN_SECRET", raising=False)
    interp = load()
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(interp._evaluator))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", interp
    httpd.shutdown()


def call(url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urlopen(Request(url, data=data, headers=headers)) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def setup_users(base):
    status, out = call(base + "/setup", {"name": "Ada", "email": "admin@x.in",
                                         "password": "adminpass1"})
    assert status == 200 and out["user"]["role"] == "admin"
    admin = out["token"]
    for name, role in (("Sam", "sales"), ("Vee", "viewer")):
        s, _ = call(base + "/create_user", {"name": name, "email": f"{role}@x.in",
                                            "role": role, "password": f"{role}pass1"}, admin)
        assert s == 200
    login = lambda email, pw: call(base + "/login", {"email": email, "password": pw})[1]["token"]
    return admin, login("sales@x.in", "salespass1"), login("viewer@x.in", "viewerpass1")


# ── syntax & validation ───────────────────────────────────────────────────────

def test_parse_auth_allow_public_audit():
    body = Parser(Lexer(APP + "\napp A\n    layout\n        sidebar\n"
                        '            nav "Users" icon="shield" component=Users allow admin\n'
                        ).tokenize()).parse().body
    assert body[0].roles == ["admin", "sales", "viewer"]
    crud = body[2].cruds[0]
    assert crud.allow == {"read": ["admin", "sales", "viewer"], "write": ["admin", "sales"],
                          "delete": ["admin"]} and crud.audit
    eps = {e.name: e for e in body[2].endpoints}
    assert eps["whoami"].allow == ["admin", "sales"] and eps["health"].public
    assert body[3].layout.sidebar[0].allow == ["admin"]


def test_unknown_role_is_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception, match="Unknown role 'salse'.*Did you mean 'sales'"):
        load(APP.replace("allow write:  admin, sales", "allow write:  admin, salse"))


def test_allow_without_auth_is_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception, match="'allow' needs an auth block"):
        load("service s\n    endpoint x() allow admin\n        return 1\n")


def test_auth_needs_roles():
    with pytest.raises(ParseError, match="auth needs a roles line"):
        Parser(Lexer("auth\n    session_hours 4\n").tokenize()).parse()


# ── HTTP: sign-in and roles ───────────────────────────────────────────────────

def test_signed_out_and_first_run(server):
    base, _ = server
    assert call(base + "/auth_status") == (200, {"needs_setup": True,
                                                 "roles": ["admin", "sales", "viewer"]})
    assert call(base + "/list_leads")[0] == 401
    assert call(base + "/anyone")[0] == 401                       # default: signed in
    assert call(base + "/health") == (200, {"ok": True})          # public
    setup_users(base)
    assert call(base + "/setup", {"name": "X", "email": "x@x.in",
                                  "password": "xxxxxxxx1"})[0] == 403   # only once
    assert call(base + "/login", {"email": "admin@x.in", "password": "nope"})[0] == 401


def test_role_rules(server):
    base, _ = server
    admin, sales, viewer = setup_users(base)
    assert call(base + "/create_lead", {"name": "A", "email": "a@x.in"}, sales)[0] == 200
    assert call(base + "/update_lead", {"id": 1, "name": "B"}, sales)[0] == 200
    assert call(base + "/delete_lead", {"id": 1}, sales)[0] == 403
    assert call(base + "/create_lead", {"name": "V", "email": "v@x.in"}, viewer)[0] == 403
    assert call(base + "/list_leads", None, viewer)[1]["total"] == 1
    assert call(base + "/whoami", None, sales) == (200, {"name": "Sam", "role": "sales"})
    assert call(base + "/whoami", None, viewer)[0] == 403
    assert call(base + "/list_users", None, sales)[0] == 403       # admin only
    assert call(base + "/delete_lead", {"id": 1}, admin)[0] == 200
    status, me = call(base + "/me", None, viewer)
    assert status == 200 and me["user"]["role"] == "viewer"
    assert "list_leads" in me["permissions"] and "create_lead" not in me["permissions"]


def test_passwords_and_admin_guards(server):
    base, _ = server
    admin, sales, viewer = setup_users(base)
    users = call(base + "/list_users", None, admin)[1]["items"]
    assert all("password" not in u and "password_hash" not in u for u in users)
    s, err = call(base + "/create_user", {"name": "W", "email": "w@x.in", "password": "short"}, admin)
    assert s == 400 and err["errors"]["password"] == "must be at least 8 characters"
    assert call(base + "/update_user", {"id": 1, "role": "viewer"}, admin)[0] == 400
    assert call(base + "/update_user", {"id": 1, "active": False}, admin)[0] == 400
    assert call(base + "/delete_user", {"id": 1}, admin)[0] == 400
    # blank password on update keeps it; disabling a user ends their session
    assert call(base + "/update_user", {"id": 3, "name": "Vee 2", "password": ""}, admin)[0] == 200
    assert call(base + "/login", {"email": "viewer@x.in", "password": "viewerpass1"})[0] == 200
    assert call(base + "/update_user", {"id": 3, "active": False}, admin)[0] == 200
    assert call(base + "/list_leads", None, viewer)[0] == 401
    assert call(base + "/login", {"email": "viewer@x.in", "password": "viewerpass1"})[0] == 403


def test_tokens_survive_restart(server, tmp_path):
    base, _ = server
    admin, _, _ = setup_users(base)
    from mcn.core_engine.mcn_server import _make_handler
    again = load()                                      # same DB → same secret
    assert again._evaluator.app_auth.authenticate(admin)["email"] == "admin@x.in"
    assert again._evaluator.app_auth.authenticate(admin + "x") is None


def test_audit_log(server):
    base, _ = server
    admin, sales, _ = setup_users(base)
    call(base + "/create_lead", {"name": "Asha", "email": "a@x.in"}, sales)
    call(base + "/update_lead", {"id": 1, "name": "Asha Rao"}, sales)
    call(base + "/delete_lead", {"id": 1}, admin)
    call(base + "/login", {"email": "sales@x.in", "password": "bad"})
    assert call(base + "/list_audit_log", None, sales)[0] == 403
    log = call(base + "/list_audit_log?entity=Lead", None, admin)[1]
    actions = [(e["action"], e["user_email"]) for e in log["items"]]
    assert actions == [("delete", "admin@x.in"), ("update", "sales@x.in"), ("create", "sales@x.in")]
    assert log["items"][1]["changes"] == {"name": ["Asha", "Asha Rao"]}
    assert log["items"][2]["summary"] == "Created lead “Asha”"
    all_actions = {e["action"] for e in call(base + "/list_audit_log?page_size=100", None, admin)[1]["items"]}
    assert {"login", "login_failed", "create"} <= all_actions


def test_audit_without_auth_is_public(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interp = load("contract Note\n    title: str\nservice s\n    crud Note\n        audit\n")
    fns = interp._evaluator.functions
    fns["create_note"]({"title": "hello"})
    entry = fns["list_audit_log"]({})["items"][0]
    assert entry["summary"] == "Created note “hello”" and entry["user_email"] is None


# ── UI ────────────────────────────────────────────────────────────────────────

UI = '''
auth
    roles admin, staff

contract Lead
    name: str

component Leads
    render
        crud_table Lead

component Users
    render
        crud_table User

component Activity
    render
        audit_log

app Desk
    title "Desk"
    layout
        sidebar
            nav "Leads"    icon="users"   component=Leads
            nav "Users"    icon="shield"  component=Users     allow admin
            nav "Activity" icon="history" component=Activity  allow admin
'''


def build(tmp_path, src):
    from mcn.core_engine.ui_compiler import UICompiler
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    UICompiler(output_dir=tmp_path).compile(interp._evaluator)
    return tmp_path / "src"


def test_ui_with_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = build(tmp_path / "fe", UI)
    app = (src / "App.tsx").read_text()
    assert "<AuthProvider>" in app and '<AuthGate title="Desk">' in app
    assert '{hasRole("admin") && (' in app                       # nav item guarded
    assert 'active === "Users" && hasRole("admin") && <Users />' in app
    assert "UsersIcon" in app and "import { Users }" in app      # no icon/component clash
    assert 'useState("Leads")' in app
    assert (src / "auth.tsx").exists() and (src / "components" / "AuditLog.tsx").exists()
    assert '"type": "password"' in (src / "models.ts").read_text()
    crud = (src / "components" / "CrudTable.tsx").read_text()
    assert "const canCreate = can(resource.endpoints.create)" in crud
    assert "Authorization" in (src / "services" / "api.ts").read_text()


def test_ui_without_auth_has_no_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = build(tmp_path / "fe", UI.replace("auth\n    roles admin, staff\n", "")
                .replace("component Users\n    render\n        crud_table User\n", "")
                .replace("     allow admin", "").replace('            nav "Users"    icon="shield"  component=Users\n', ""))
    app = (src / "App.tsx").read_text()
    assert "AuthProvider" not in app and "hasRole" not in app
