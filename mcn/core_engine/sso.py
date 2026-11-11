"""
Single sign-on for MCN services with OpenID Connect (Okta, Microsoft Entra ID,
Google Workspace, Auth0, Keycloak, OneLogin, Ping and other OIDC providers).

A service opts in with `auth "sso"`. Then:

    GET  /_auth/login?return_to=<app url>   → redirects to the identity provider
    GET  /_auth/callback                     → the provider sends people back here
    GET  /_auth/me                           → who is signed in
    POST /_auth/logout                       → (the app drops its token)

After sign-in, people return to the app with `#mcn_token=<session token>` in the
URL; the generated web app stores it and sends it as a bearer token. Endpoints
of the service then see the person in current_user(): sub, email, name, roles.

Settings (environment):
    MCN_SSO_ISSUER            the provider's issuer URL (required)
    MCN_SSO_CLIENT_ID         the app's client ID (required)
    MCN_SSO_CLIENT_SECRET     the client secret (omit for public clients; PKCE is always used)
    MCN_SSO_REDIRECT_URL      this server's /_auth/callback URL as registered with the provider
    MCN_SSO_SCOPES            default "openid email profile"
    MCN_SSO_ALLOWED_DOMAINS   comma-separated email domains allowed to sign in
    MCN_SSO_ROLES_CLAIM       the ID token claim holding roles or groups (default: roles, then groups)
    MCN_SSO_SESSION_HOURS     how long a sign-in lasts (default 8)
    MCN_SSO_RETURN_ORIGINS    extra comma-separated origins people may be sent back to

No state is kept between the login and callback requests (the PKCE verifier and
nonce travel in a short-lived signed cookie), so it works on serverless hosts.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

COOKIE = "mcn_sso"
_FLOW_SECONDS = 600
_DISCOVERY_SECONDS = 3600

_cache_lock = threading.Lock()
_discovery: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_jwks_clients: Dict[str, Any] = {}


class SSOError(Exception):
    """A sign-in problem to show to the person, with an HTTP status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# A response the servers turn into their own: (status, headers, json body or None)
Reply = Tuple[int, Dict[str, str], Optional[Dict[str, Any]]]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def configured() -> bool:
    return bool(_env("MCN_SSO_ISSUER") and _env("MCN_SSO_CLIENT_ID"))


def _require_config() -> Tuple[str, str]:
    issuer, client_id = _env("MCN_SSO_ISSUER").rstrip("/"), _env("MCN_SSO_CLIENT_ID")
    if not issuer or not client_id:
        raise SSOError("Single sign-on isn't set up on this server: set MCN_SSO_ISSUER and MCN_SSO_CLIENT_ID.", 503)
    return issuer, client_id


def _jwt():
    try:
        import jwt  # PyJWT
        from jwt import PyJWKClient  # noqa: F401  (needs the cryptography package for RS256/ES256)
        import cryptography  # noqa: F401
    except ImportError:
        raise SSOError("Single sign-on needs an extra package on this server. Run: mcn add sso", 503)
    return jwt


def _secret() -> str:
    from .auth_primitives import _SECRET
    return _SECRET


# ── Provider metadata ─────────────────────────────────────────────────────────

def discovery(issuer: str) -> Dict[str, Any]:
    """The provider's OpenID configuration (cached for an hour)."""
    now = time.time()
    with _cache_lock:
        hit = _discovery.get(issuer)
        if hit and now - hit[0] < _DISCOVERY_SECONDS:
            return hit[1]
    import requests
    url = f"{issuer}/.well-known/openid-configuration"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        meta = res.json()
    except Exception as exc:
        raise SSOError(f"Couldn't read the identity provider's settings from {url}: {exc}", 502)
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not meta.get(key):
            raise SSOError(f"The identity provider's settings have no {key}", 502)
    with _cache_lock:
        _discovery[issuer] = (now, meta)
    return meta


def _jwks_client(uri: str):
    with _cache_lock:
        client = _jwks_clients.get(uri)
        if client is None:
            from jwt import PyJWKClient
            client = _jwks_clients[uri] = PyJWKClient(uri, cache_keys=True, lifespan=_DISCOVERY_SECONDS)
        return client


# ── Where people may be sent back to ──────────────────────────────────────────

def _origin(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme in ("http", "https") and p.netloc else ""


def safe_return_to(return_to: str, base_url: str) -> str:
    """return_to if it points at this server, a CORS-allowed origin or MCN_SSO_RETURN_ORIGINS; else this server.
    Stops the sign-in being used to send tokens to someone else's site."""
    origin = _origin(return_to or "")
    allowed = {_origin(base_url)}
    for name in ("MCN_SSO_RETURN_ORIGINS", "MCN_CORS_ORIGINS"):
        allowed |= {o.strip().rstrip("/") for o in _env(name).split(",") if o.strip() and o.strip() != "*"}
    if origin and origin in allowed:
        return return_to
    if origin and origin.startswith(("http://localhost", "http://127.0.0.1")) and \
            _origin(base_url).startswith(("http://localhost", "http://127.0.0.1")):
        return return_to                 # local development: the app and API on different ports
    return base_url.rstrip("/") + "/"


def _redirect_uri(base_url: str) -> str:
    return _env("MCN_SSO_REDIRECT_URL") or base_url.rstrip("/") + "/_auth/callback"


# ── The flow ──────────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def start(base_url: str, return_to: str = "") -> Reply:
    """Redirect to the provider, with a signed cookie holding this sign-in's secrets."""
    issuer, client_id = _require_config()
    jwt = _jwt()
    meta = discovery(issuer)
    verifier, state, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    flow = jwt.encode({"state": state, "nonce": nonce, "verifier": verifier,
                       "return_to": safe_return_to(return_to, base_url),
                       "exp": int(time.time()) + _FLOW_SECONDS}, _secret(), algorithm="HS256")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _redirect_uri(base_url),
        "scope": _env("MCN_SSO_SCOPES", "openid email profile"),
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    location = meta["authorization_endpoint"] + ("&" if "?" in meta["authorization_endpoint"] else "?") + \
        urllib.parse.urlencode(params)
    secure = "; Secure" if _redirect_uri(base_url).startswith("https://") else ""
    cookie = f"{COOKIE}={flow}; Path=/; Max-Age={_FLOW_SECONDS}; HttpOnly; SameSite=Lax{secure}"
    return 302, {"Location": location, "Set-Cookie": cookie, "Cache-Control": "no-store"}, None


def _roles(claims: Dict[str, Any]) -> list:
    names = [_env("MCN_SSO_ROLES_CLAIM")] if _env("MCN_SSO_ROLES_CLAIM") else ["roles", "groups"]
    for name in names:
        value = claims.get(name)
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str) and value:
            return [v.strip() for v in value.replace(",", " ").split()]
    return []


def _exchange(meta: Dict[str, Any], code: str, verifier: str, base_url: str, client_id: str) -> Dict[str, Any]:
    import requests
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect_uri(base_url),
            "client_id": client_id, "code_verifier": verifier}
    auth = None
    secret = _env("MCN_SSO_CLIENT_SECRET")
    if secret:
        methods = meta.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
        if "client_secret_basic" in methods:
            auth = (client_id, secret)
        else:
            data["client_secret"] = secret
    try:
        res = requests.post(meta["token_endpoint"], data=data, auth=auth, timeout=15,
                            headers={"Accept": "application/json"})
    except Exception as exc:
        raise SSOError(f"Couldn't reach the identity provider: {exc}", 502)
    body = {}
    try:
        body = res.json()
    except ValueError:
        pass
    if res.status_code != 200 or not body.get("id_token"):
        reason = body.get("error_description") or body.get("error") or f"HTTP {res.status_code}"
        raise SSOError(f"The identity provider refused the sign-in: {reason}", 401)
    return body


def verify_id_token(id_token: str, nonce: Optional[str] = None) -> Dict[str, Any]:
    """The ID token's claims, after checking its signature, issuer, audience, expiry and nonce."""
    issuer, client_id = _require_config()
    jwt = _jwt()
    meta = discovery(issuer)
    try:
        key = _jwks_client(meta["jwks_uri"]).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(id_token, key.key, algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"],
                            audience=client_id, issuer=meta.get("issuer", issuer), leeway=60)
    except Exception as exc:
        raise SSOError(f"The sign-in couldn't be verified: {exc}", 401)
    if nonce is not None and claims.get("nonce") != nonce:
        raise SSOError("The sign-in couldn't be verified: the nonce doesn't match", 401)
    return claims


def finish(base_url: str, query: Dict[str, str], cookies: Dict[str, str]) -> Reply:
    """Handle the provider's redirect back: check it, then send the person to the app with a session token."""
    _, client_id = _require_config()
    jwt = _jwt()
    if query.get("error"):
        raise SSOError(f"Sign-in was cancelled or refused: {query.get('error_description') or query['error']}", 401)
    raw = cookies.get(COOKIE, "")
    try:
        flow = jwt.decode(raw, _secret(), algorithms=["HS256"]) if raw else None
    except Exception:
        flow = None
    if not flow or not secrets.compare_digest(str(flow.get("state", "")), str(query.get("state", ""))):
        raise SSOError("This sign-in link has expired or was opened in another browser. Start again.", 400)
    if not query.get("code"):
        raise SSOError("The identity provider didn't send a sign-in code", 400)

    meta = discovery(_require_config()[0])
    tokens = _exchange(meta, query["code"], flow["verifier"], base_url, client_id)
    claims = verify_id_token(tokens["id_token"], flow["nonce"])

    email = str(claims.get("email") or claims.get("preferred_username") or claims.get("upn") or "").lower()
    if claims.get("email_verified") is False:
        raise SSOError("Your email address isn't verified with the identity provider", 403)
    domains = [d.strip().lower() for d in _env("MCN_SSO_ALLOWED_DOMAINS").split(",") if d.strip()]
    if domains and email.rsplit("@", 1)[-1] not in domains:
        raise SSOError("Your account isn't allowed to sign in to this app", 403)

    from .auth_primitives import _make_token
    hours = float(_env("MCN_SSO_SESSION_HOURS", "8") or 8)
    session = _make_token({
        "sub": f"sso|{claims.get('sub')}", "email": email, "name": claims.get("name") or email,
        "roles": _roles(claims), "sso": True, "idp": meta.get("issuer"),
    }, expires_in=int(hours * 3600))
    target = flow.get("return_to") or base_url.rstrip("/") + "/"
    target = target.split("#", 1)[0] + "#" + urllib.parse.urlencode({"mcn_token": session})
    clear = f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
    return 302, {"Location": target, "Set-Cookie": clear, "Cache-Control": "no-store"}, None


def check(authorization: Optional[str]) -> Tuple[bool, Any, str]:
    """(allowed, user, error) for an endpoint of an `auth "sso"` service."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False, None, "Sign in with your organization's account first"
    token = token.strip()
    # Studio's preview runs the backend with its own token (MCN_DEV_TOOLS=1), standing in for a signed-in person
    dev_token = os.environ.get("MCN_API_TOKEN", "")
    if os.environ.get("MCN_DEV_TOOLS") == "1" and dev_token and secrets.compare_digest(token, dev_token):
        return True, {"sub": "studio-preview", "email": "preview@mcn.studio", "name": "Studio preview",
                      "roles": ["admin"], "sso": True}, ""
    from .auth_primitives import _decode_token
    payload = _decode_token(token)
    if not payload or not payload.get("sso"):
        return False, None, "Your sign-in has expired. Sign in again"
    return True, payload, ""


def handle(method: str, path: str, base_url: str, query: Dict[str, str], cookies: Dict[str, str],
           authorization: Optional[str]) -> Optional[Reply]:
    """The /_auth/* routes, for any server. None when the path isn't one of them."""
    if not path.startswith("/_auth/"):
        return None
    action = path[len("/_auth/"):].strip("/")
    try:
        if action == "login" and method == "GET":
            return start(base_url, query.get("return_to", ""))
        if action == "callback" and method == "GET":
            return finish(base_url, query, cookies)
        if action == "me" and method == "GET":
            ok, user, error = check(authorization)
            if not ok:
                return 401, {}, {"error": error, "sso_login": "/_auth/login"}
            return 200, {}, {"success": True, "user": {k: user.get(k) for k in ("sub", "email", "name", "roles")}}
        if action == "logout" and method == "POST":
            # Session tokens are short-lived; signing out is the app forgetting its token
            return 200, {}, {"success": True}
    except SSOError as exc:
        if action in ("login", "callback"):
            return exc.status, {"Content-Type": "text/html; charset=utf-8"}, {"__html__": _error_page(str(exc))}
        return exc.status, {}, {"error": str(exc)}
    return 404, {}, {"error": "Not found"}


def _error_page(message: str) -> str:
    """What a person sees in the browser when sign-in fails."""
    import html
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Sign-in problem</title>"
            "<style>body{font:15px/1.6 system-ui,sans-serif;max-width:520px;margin:15vh auto;padding:0 20px;color:#1f2937}"
            "@media(prefers-color-scheme:dark){body{background:#0b1020;color:#e2e8f0}}</style></head><body>"
            f"<h1>Couldn't sign you in</h1><p>{html.escape(message)}</p>"
            "<p><a href=\"javascript:history.back()\">Go back</a></p></body></html>")
