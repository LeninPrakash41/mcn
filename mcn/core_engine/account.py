"""Your MCN account on this computer: `mcn login`, `mcn logout`, `mcn whoami`,
and Studio's Sign in button.

Studio installed on a laptop has no accounts of its own. Signing in connects it
to an MCN account server (a hosted Studio) with a device code: the person
approves the code in their browser, and this computer keeps a token in
~/.mcn/credentials.json, readable only by them. Admins on the account server
see every signed-in computer and can sign it out.

The account server comes from, in order: MCN_ACCOUNT_URL, `mcn config set
account_url <url>`, then DEFAULT_ACCOUNT_URL.
"""
from __future__ import annotations

import json
import os
import platform
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .paths import mcn_home
except ImportError:  # pragma: no cover - loaded outside the package
    from paths import mcn_home

# The official MCN account server. Set this when it's online; until then
# people set MCN_ACCOUNT_URL or `mcn config set account_url`.
DEFAULT_ACCOUNT_URL = ""

_RECHECK_S = 10 * 60      # how often status() confirms the token with the server


class AccountError(Exception):
    pass


# ── Settings and stored credentials ───────────────────────────────────────────

def _config() -> dict:
    path = Path(os.environ.get("MCN_HOME") or Path.home() / ".mcn") / "config.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def account_url() -> str:
    url = os.environ.get("MCN_ACCOUNT_URL") or _config().get("account_url") or DEFAULT_ACCOUNT_URL
    return str(url).strip().rstrip("/")


def client_name() -> str:
    return f"MCN on {platform.node() or 'this computer'} ({platform.system() or 'unknown'})"


def _cred_path() -> Path:
    return mcn_home() / "credentials.json"


def load_credentials() -> dict | None:
    try:
        data = json.loads(_cred_path().read_text())
        return data if isinstance(data, dict) and data.get("token") else None
    except (OSError, ValueError):
        return None


def save_credentials(data: dict) -> None:
    path = _cred_path()
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_credentials() -> None:
    try:
        _cred_path().unlink()
    except FileNotFoundError:
        pass


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _request(method: str, url: str, payload: dict | None = None, token: str = "",
             timeout: float = 10) -> tuple[int, dict]:
    """(status, json body). Raises AccountError when the server can't be reached."""
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "mcn-account-client"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        raise AccountError(f"Can't reach the MCN account server at {url.split('/api/')[0]}: "
                           f"{getattr(e, 'reason', e)}") from None
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {}
    return status, data if isinstance(data, dict) else {}


def _require_url(url: str | None = None) -> str:
    url = (url or account_url()).rstrip("/")
    if not url:
        raise AccountError("No MCN account server is set. Run `mcn config set account_url https://...` "
                           "or set MCN_ACCOUNT_URL.")
    if not url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise AccountError("The account server must use https:// (http is only allowed for localhost).")
    return url


# ── Sign-in flow ──────────────────────────────────────────────────────────────

def start_login(url: str | None = None, name: str | None = None) -> dict:
    """Ask the account server for a sign-in code. Show user_code and open verification_uri_complete."""
    url = _require_url(url)
    status, data = _request("POST", f"{url}/api/device/code", {"client_name": name or client_name()})
    if status != 200 or not data.get("device_code"):
        raise AccountError(data.get("error") or f"The account server refused sign-in (HTTP {status}).")
    data["account_url"] = url
    return data


def poll_login(device_code: str, url: str | None = None) -> dict:
    """Check once whether the code was approved. Saves the credentials when it was.
    Returns {"status": "pending" | "approved" | "denied" | "expired", ...}."""
    url = _require_url(url)
    status, data = _request("POST", f"{url}/api/device/token", {"device_code": device_code})
    if status == 428:
        return {"status": "pending"}
    if status == 200 and data.get("token"):
        user = data.get("user") or {}
        save_credentials({"account_url": url, "token": data["token"], "user": user,
                          "signed_in_at": time.time(), "checked_at": time.time()})
        return {"status": "approved", "user": user, "account_url": url}
    return {"status": data.get("status") or "error",
            "error": data.get("error") or f"Sign-in failed (HTTP {status})."}


def status(refresh: bool = False) -> dict:
    """Who is signed in on this computer. Confirms with the server every few minutes;
    when the server can't be reached, the last known account is reported as offline."""
    creds = load_credentials()
    if not creds:
        return {"signed_in": False, "account_url": account_url()}
    url = creds.get("account_url") or account_url()
    result = {"signed_in": True, "user": creds.get("user") or {}, "account_url": url}
    if not refresh and time.time() - float(creds.get("checked_at") or 0) < _RECHECK_S:
        return result
    try:
        code, data = _request("GET", f"{url}/api/auth/me", token=creds["token"], timeout=5)
    except AccountError:
        return {**result, "offline": True}
    if code == 401:
        # Signed out from the server (revoked by an admin or from another device) or expired
        clear_credentials()
        return {"signed_in": False, "account_url": url, "signed_out_remotely": True}
    if code == 200 and isinstance(data.get("user"), dict):
        u = data["user"]
        creds["user"] = {"id": u.get("id"), "email": u.get("email", ""), "roles": u.get("roles", [])}
        creds["checked_at"] = time.time()
        save_credentials(creds)
        result["user"] = creds["user"]
    return result


def token() -> str:
    """The stored token, for calling account-server features (empty when signed out)."""
    creds = load_credentials()
    return creds["token"] if creds else ""


def logout() -> dict:
    """Sign this computer out, on the server too when it can be reached."""
    creds = load_credentials()
    if not creds:
        return {"signed_in": False}
    revoked = False
    try:
        code, _ = _request("POST", f"{creds.get('account_url') or account_url()}/api/device/revoke", {},
                           token=creds["token"], timeout=5)
        revoked = code == 200
    except AccountError:
        pass
    clear_credentials()
    return {"signed_in": False, "revoked_on_server": revoked}


def login_interactive(url: str | None = None, log=print, open_browser: bool = True) -> dict:
    """`mcn login`: show the code, open the browser, wait for approval."""
    started = start_login(url)
    link = started.get("verification_uri_complete") or started.get("verification_uri")
    log(f"Your sign-in code: {started['user_code']}")
    log(f"Approve it at {link}")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(link)
        except Exception:
            pass
    log("Waiting for approval… (Ctrl+C to cancel)")
    deadline = time.time() + float(started.get("expires_in") or 600)
    interval = max(1.0, float(started.get("interval") or 3))
    while time.time() < deadline:
        time.sleep(interval)
        result = poll_login(started["device_code"], started["account_url"])
        if result["status"] == "pending":
            continue
        if result["status"] == "approved":
            return result
        raise AccountError(result.get("error") or "Sign-in failed.")
    raise AccountError("The sign-in code expired. Run `mcn login` again.")
