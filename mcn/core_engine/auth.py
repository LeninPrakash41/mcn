"""
Login and roles for MCN apps.

    auth
        roles         admin, sales, viewer     # first role = administrator
        session_hours 12

With an `auth` block, every `service` gets:

    POST /login          {email, password} → {token, user}
    GET  /me             the signed-in user + the endpoints they may call
    GET  /auth_status    {needs_setup, roles}                       (public)
    POST /setup          create the first administrator (only while no users exist)
    list_users / get_user / create_user / update_user / delete_user   (admin only)

and every endpoint requires a signed-in user unless marked `public`; `allow`
on endpoints and crud actions limits them to roles.  Users are a built-in
`User` contract, so `crud_table User` is a ready-made user-management screen.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Callable, Dict, List, Optional

from .crud import AuditLog, BadRequest, CrudResource, FieldSpec, MCNHttpError

USERS_TABLE = "app_users"


class Unauthorized(MCNHttpError):
    status = 401


class Forbidden(MCNHttpError):
    status = 403


def user_contract(roles: List[str]):
    """The built-in User contract for an app's roles."""
    from .runtime_types import MCNContract
    specs = [
        FieldSpec("name", "str"),
        FieldSpec("email", "str", unique=True),
        FieldSpec("role", "choice", default=roles[-1], has_default=True, choices=roles),
        FieldSpec("active", "bool", default=True, has_default=True),
        FieldSpec("password", "password"),
    ]
    return MCNContract("User", [(s.name, s.type) for s in specs], specs)


class _Users(CrudResource):
    """User CRUD with guards that keep at least one administrator."""

    def __init__(self, auth: "AppAuth", **kw):
        super().__init__(**kw)
        self.auth = auth

    def before_update(self, before, changes):
        me = self.actor()
        if me and me.get("id") == before["id"]:
            if "role" in changes and changes["role"] != before["role"]:
                raise BadRequest({"error": "You can't change your own role",
                                  "errors": {"role": "can't be changed on your own account"}})
            if changes.get("active") is False:
                raise BadRequest({"error": "You can't deactivate your own account",
                                  "errors": {"active": "can't be turned off for yourself"}})

    def before_delete(self, row):
        me = self.actor()
        if me and me.get("id") == row["id"]:
            raise BadRequest({"error": "You can't delete your own account"})


class AppAuth:
    def __init__(self, roles: List[str], session_hours: int, query: Callable,
                 actor: Callable[[], Optional[Dict[str, Any]]],
                 permissions: Callable[[Dict[str, Any]], List[str]]):
        self.roles         = roles
        self.admin_role    = roles[0]
        self.session_hours = max(1, int(session_hours or 12))
        self.query         = query
        self.actor         = actor
        self.permissions   = permissions
        self.audit         = AuditLog(query)
        self.secret        = self._secret()
        self.contract      = user_contract(roles)
        self.users = _Users(self, contract=self.contract, query=query,
                            search=["name", "email"], sort="name", page_size=25,
                            table=USERS_TABLE, audit=self.audit, actor=actor)
        self.users.ensure_table()

    # ── secret ────────────────────────────────────────────────────────────────

    def _secret(self) -> str:
        """$MCN_SECRET, or a random secret generated once and kept in the app DB."""
        env = os.environ.get("MCN_SECRET")
        if env:
            return env
        self.query('CREATE TABLE IF NOT EXISTS "mcn_meta" ("key" TEXT PRIMARY KEY, "value" TEXT)')
        rows = self.query('SELECT "value" FROM "mcn_meta" WHERE "key" = ?', ("auth_secret",))
        if rows:
            return rows[0]["value"]
        value = secrets.token_hex(32)
        self.query('INSERT INTO "mcn_meta" ("key", "value") VALUES (?, ?)', ("auth_secret", value))
        return value

    # ── tokens ────────────────────────────────────────────────────────────────

    def _token(self, user: Dict[str, Any]) -> str:
        from .auth_primitives import _make_token
        return _make_token({"uid": user["id"]}, self.secret, self.session_hours * 3600)

    def authenticate(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Bearer token → the (active) user, re-read from the database."""
        from .auth_primitives import _decode_token
        if not token:
            return None
        data = _decode_token(token, self.secret)
        if not data or "uid" not in data:
            return None
        rows = self.query(f'SELECT * FROM "{USERS_TABLE}" WHERE "id" = ?', (data["uid"],))
        if not rows or not rows[0].get("active"):
            return None
        return self.users._row(rows[0])

    def has_users(self) -> bool:
        return self.query(f'SELECT COUNT(*) AS n FROM "{USERS_TABLE}"')[0]["n"] > 0

    # ── endpoints ─────────────────────────────────────────────────────────────

    def login(self, payload: Any = None) -> Dict[str, Any]:
        from .auth_primitives import _verify_pw
        p = payload if isinstance(payload, dict) else {}
        email = str(p.get("email") or "").strip().lower()
        password = str(p.get("password") or "")
        rows = self.query(f'SELECT * FROM "{USERS_TABLE}" WHERE lower("email") = ?', (email,))
        if not rows or not _verify_pw(password, rows[0].get("password_hash") or ""):
            self.audit.record("login_failed", "User", rows[0]["id"] if rows else None,
                              {"note": f"Failed login for {email or '(blank)'}"},
                              {"email": email})
            raise Unauthorized({"error": "Wrong email or password"})
        user = self.users._row(dict(rows[0]))
        if not user.get("active"):
            raise Forbidden({"error": "This account is disabled. Ask an administrator."})
        self.audit.record("login", "User", user["id"], {"note": "Signed in"}, user)
        return {"token": self._token(user), "user": user,
                "permissions": self.permissions(user)}

    def me(self, payload: Any = None) -> Dict[str, Any]:
        user = self.actor()
        if not user:
            raise Unauthorized({"error": "Please sign in"})
        return {"user": user, "permissions": self.permissions(user)}

    def status(self, payload: Any = None) -> Dict[str, Any]:
        return {"needs_setup": not self.has_users(), "roles": self.roles}

    def setup(self, payload: Any = None) -> Dict[str, Any]:
        """Create the first administrator. Only works while there are no users."""
        if self.has_users():
            raise Forbidden({"error": "Setup is already complete — please sign in"})
        p = dict(payload) if isinstance(payload, dict) else {}
        p["role"], p["active"] = self.admin_role, True
        user = self.users.create(p)
        return {"token": self._token(user), "user": user,
                "permissions": self.permissions(user)}

    def endpoints(self) -> Dict[str, Callable]:
        out: Dict[str, Callable] = {}
        for name, fn, access in (
            ("login", self.login, "public"),
            ("auth_status", self.status, "public"),
            ("setup", self.setup, "public"),
            ("me", self.me, "user"),
            ("list_audit_log", self.audit.list, [self.admin_role]),
        ):
            out[name] = _endpoint(name, fn, access)
        for name, fn in self.users.endpoints().items():
            fn._mcn_access = [self.admin_role]
            out[name] = fn
        return out


def _endpoint(name: str, fn: Callable, access) -> Callable:
    def endpoint(payload: Any = None):
        return fn(payload)
    endpoint.__name__ = name
    endpoint._mcn_body = True
    endpoint._mcn_access = access
    return endpoint


def allowed(access, user: Optional[Dict[str, Any]]) -> bool:
    """access: "public" | "user" | [roles]."""
    if access == "public":
        return True
    if not user:
        return False
    if access in (None, "user"):
        return True
    return user.get("role") in access
