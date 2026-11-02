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

    sso: Optional["SSO"] = None

    def status(self, payload: Any = None) -> Dict[str, Any]:
        out = {"needs_setup": not self.has_users(), "roles": self.roles}
        if self.sso is not None:
            out["sso"] = {"label": self.sso.label}
        return out

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
        if self.sso is not None:
            out.update(self.sso.endpoints())
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


# ── Single sign-on (OpenID Connect, authorization-code flow) ─────────────────

class SSO:
    """
    auth
        roles admin, staff
        sso
            issuer        "https://accounts.google.com"     # or Microsoft / Okta / Keycloak / Zoho
            client_id     env("SSO_CLIENT_ID")
            client_secret env("SSO_CLIENT_SECRET")
            allow_domains "acme.in"
            default_role  staff

    Register  <backend>/sso_callback  as the redirect URL at your provider.
    The browser is sent back to the app with the session token only if the
    app's address is in $MCN_APP_URL (comma-separated) — or is localhost.
    """

    def __init__(self, auth: AppAuth, issuer: str, client_id: str, client_secret: str,
                 allow_domains: List[str], default_role: str, label: str = "",
                 auto_create: bool = True):
        self.auth = auth
        self.issuer = issuer.rstrip("/")
        self.client_id, self.client_secret = client_id, client_secret
        self.allow_domains = [d.lower().lstrip("@") for d in allow_domains if d]
        self.default_role = default_role or auth.roles[-1]
        self.label = label or _provider_label(self.issuer)
        self.auto_create = auto_create
        self._config: Optional[Dict[str, Any]] = None
        self.request_base: Callable[[], str] = lambda: os.environ.get("MCN_PUBLIC_URL", "")

    # ── provider ──────────────────────────────────────────────────────────────

    def config(self) -> Dict[str, Any]:
        if self._config is None:
            self._config = _http_json(f"{self.issuer}/.well-known/openid-configuration")
        return self._config

    def redirect_uri(self) -> str:
        base = (os.environ.get("MCN_PUBLIC_URL") or self.request_base()).rstrip("/")
        return f"{base}/sso_callback"

    # ── endpoints ─────────────────────────────────────────────────────────────

    def start(self, payload: Any = None) -> Dict[str, Any]:
        """GET /sso_start?return_to=<app url> → {url} to send the browser to."""
        from urllib.parse import urlencode
        from .auth_primitives import _make_token
        p = payload if isinstance(payload, dict) else {}
        return_to = str(p.get("return_to") or "")
        if not _allowed_return(return_to):
            raise BadRequest({"error": "This app address isn't allowed for sign-in. "
                                       "Add it to MCN_APP_URL on the server."})
        state = _make_token({"rt": return_to, "n": secrets.token_hex(8)}, self.auth.secret, 600)
        params = {"response_type": "code", "client_id": self.client_id,
                  "redirect_uri": self.redirect_uri(), "scope": "openid email profile",
                  "state": state}
        return {"url": f"{self.config()['authorization_endpoint']}?{urlencode(params)}"}

    def callback(self, payload: Any = None) -> Dict[str, Any]:
        """GET /sso_callback?code&state → redirect to the app with #mcn_token=…"""
        from urllib.parse import quote
        from .auth_primitives import _decode_token
        p = payload if isinstance(payload, dict) else {}
        state = _decode_token(str(p.get("state") or ""), self.auth.secret)
        if not state or not _allowed_return(state.get("rt", "")):
            raise BadRequest({"error": "Sign-in expired or was tampered with. Please try again."})
        return_to = state["rt"]
        try:
            if p.get("error"):
                raise PermissionError(str(p.get("error_description") or p["error"]))
            user = self._user_for(self._userinfo(str(p.get("code") or "")))
            token = self.auth._token(user)
            self.auth.audit.record("login", "User", user["id"],
                                   {"note": f"Signed in with {self.label}"}, user)
            return {"_redirect": f"{return_to}#mcn_token={quote(token)}"}
        except Exception as exc:
            return {"_redirect": f"{return_to}#mcn_error={quote(str(exc))}"}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _userinfo(self, code: str) -> Dict[str, Any]:
        if not code:
            raise PermissionError("The sign-in provider didn't return a code")
        cfg = self.config()
        tokens = _http_json(cfg["token_endpoint"], form={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": self.redirect_uri(), "client_id": self.client_id,
            "client_secret": self.client_secret})
        if "access_token" not in tokens:
            raise PermissionError(tokens.get("error_description") or "Sign-in was refused")
        # Read the profile from the provider over TLS (OIDC Core §3.1.3.7 lets a
        # confidential client rely on the TLS channel instead of the ID-token signature)
        return _http_json(cfg["userinfo_endpoint"], bearer=tokens["access_token"])

    def _user_for(self, info: Dict[str, Any]) -> Dict[str, Any]:
        email = str(info.get("email") or "").strip().lower()
        if not email:
            raise PermissionError("Your account has no email address")
        if info.get("email_verified") is False:
            raise PermissionError("Your email address isn't verified with the provider")
        domain = email.rsplit("@", 1)[-1]
        if self.allow_domains and domain not in self.allow_domains:
            raise PermissionError(f"Accounts from {domain} can't sign in to this app")
        rows = self.auth.query(f'SELECT * FROM "{USERS_TABLE}" WHERE lower("email") = ?', (email,))
        if rows:
            user = self.auth.users._row(dict(rows[0]))
            if not user.get("active"):
                raise PermissionError("This account is disabled. Ask an administrator.")
            return user
        if not self.auto_create and self.auth.has_users():
            raise PermissionError("No account for this email. Ask an administrator to add you.")
        role = self.auth.admin_role if not self.auth.has_users() else self.default_role
        name = str(info.get("name") or email.split("@")[0])
        return self.auth.users.create({"name": name, "email": email, "role": role,
                                       "password": secrets.token_urlsafe(24)})

    def endpoints(self) -> Dict[str, Callable]:
        return {"sso_start": _endpoint("sso_start", self.start, "public"),
                "sso_callback": _endpoint("sso_callback", self.callback, "public")}


def _provider_label(issuer: str) -> str:
    for key, name in (("google", "Google"), ("microsoft", "Microsoft"), ("okta", "Okta"),
                      ("zoho", "Zoho"), ("keycloak", "Keycloak"), ("auth0", "Auth0")):
        if key in issuer:
            return name
    return "SSO"


def _allowed_return(url: str) -> bool:
    from urllib.parse import urlparse
    u = urlparse(str(url))
    if u.scheme not in ("http", "https") or not u.netloc:
        return False
    origin = f"{u.scheme}://{u.netloc}".lower()
    allowed = [a.strip().rstrip("/").lower() for a in os.environ.get("MCN_APP_URL", "").split(",")
               if a.strip()]
    if allowed:
        return any(origin == urlparse(a).scheme + "://" + urlparse(a).netloc for a in allowed)
    return u.hostname in ("localhost", "127.0.0.1")       # development default


def _http_json(url: str, form: Optional[Dict[str, str]] = None,
               bearer: Optional[str] = None) -> Dict[str, Any]:
    import json as _json
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=15) as resp:
            return _json.loads(resp.read() or b"{}")
    except HTTPError as exc:
        try:
            return _json.loads(exc.read() or b"{}")
        except ValueError:
            raise PermissionError(f"Sign-in provider error ({exc.code})")
