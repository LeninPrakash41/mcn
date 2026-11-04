"""
Security for MCN programs and the HTTP server.

Built-ins (registered in stdlib_builtins):
    escape_html, sanitize_html, is_email, is_url, validate, password_strength,
    rate_limit, mask, require, secure_token, safe_equals, audit_log,
    verify_audit_log, current_user

Server helpers (used by mcn_server): check_auth, RateLimiter, SECURITY_HEADERS.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

# ── Request authentication (service `auth "token"` / `auth "jwt"`) ──────────────

_request = threading.local()


def current_user() -> Any:
    """Inside an endpoint of an `auth "jwt"` service: the verified token payload, else null."""
    return getattr(_request, "user", None)


def set_current_user(user: Any) -> None:
    _request.user = user


def check_auth(mode: str, authorization: Optional[str]) -> Tuple[bool, Any, str]:
    """(allowed, user, error) for an Authorization header under the endpoint's auth mode."""
    if not mode:
        return True, None, ""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False, None, "This endpoint needs an Authorization: Bearer <token> header"
    token = token.strip()
    if mode == "token":
        expected = os.getenv("MCN_API_TOKEN", "")
        if not expected:
            return False, None, "The server has no MCN_API_TOKEN set, so token-protected endpoints are closed"
        if hmac.compare_digest(token.encode(), expected.encode()):
            return True, {"token": True}, ""
        return False, None, "Invalid token"
    if mode == "jwt":
        from .auth_primitives import jwt_verify
        payload = jwt_verify(token)
        if payload:
            return True, payload, ""
        return False, None, "Invalid or expired token"
    return False, None, f"Unknown auth mode '{mode}'"


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-site",
}


def max_body_bytes() -> int:
    return int(os.getenv("MCN_MAX_BODY_BYTES", str(1024 * 1024)))


def cors_origin(request_origin: Optional[str]) -> str:
    """The Access-Control-Allow-Origin value: MCN_CORS_ORIGINS (comma-separated), default *."""
    allowed = [o.strip() for o in os.getenv("MCN_CORS_ORIGINS", "*").split(",") if o.strip()]
    if "*" in allowed:
        return "*"
    return request_origin if request_origin in allowed else allowed[0] if allowed else ""


class RateLimiter:
    """Sliding-window limit per key (client IP for the server, any string for rate_limit())."""

    def __init__(self):
        self._hits: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


_limiter = RateLimiter()
SERVER_LIMITER = RateLimiter()


def server_rate_limit() -> int:
    """Requests per minute per client IP for `mcn serve` (MCN_RATE_LIMIT; 0 turns it off)."""
    return int(os.getenv("MCN_RATE_LIMIT", "600"))


# ── Built-ins ─────────────────────────────────────────────────────────────────

def escape_html(text: Any) -> str:
    """Make text safe to put inside HTML: <b> becomes &lt;b&gt;."""
    return html.escape("" if text is None else str(text), quote=True)


_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "p", "br", "ul", "ol", "li", "code", "pre", "blockquote", "a"}


def sanitize_html(text: Any) -> str:
    """Keep simple formatting tags and safe links; drop scripts, styles, event handlers and other tags."""
    s = "" if text is None else str(text)
    s = re.sub(r"(?is)<(script|style|iframe|object|embed)\b.*?</\1\s*>", "", s)

    def tag(m: re.Match) -> str:
        closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if name not in _ALLOWED_TAGS:
            return ""
        if closing:
            return f"</{name}>"
        if name == "a":
            href = re.search(r'''href\s*=\s*["']([^"']*)["']''', attrs, re.I)
            url = href.group(1).strip() if href else ""
            if re.match(r"^(https?:|mailto:|/|#)", url, re.I):
                return f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer">'
            return "<a>"
        return f"<{name}>"

    return re.sub(r"<\s*(/)?\s*([a-zA-Z0-9]+)([^>]*)>", tag, s)


_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_email(value: Any) -> bool:
    return bool(value) and len(str(value)) <= 254 and bool(_EMAIL.match(str(value)))


def is_url(value: Any, https_only: bool = False) -> bool:
    pattern = r"^https://" if https_only else r"^https?://"
    return bool(value) and bool(re.match(pattern + r"[A-Za-z0-9.-]+(:\d+)?(/\S*)?$", str(value)))


def validate(data: Any, rules: Any) -> Dict[str, Any]:
    """
    Check a record against rules; returns {valid, errors: {field: message}, data}.

        validate(input, {name: "required|min:2|max:80", email: "required|email",
                         age: "number|min:0|max:150", role: "in:admin,member"})

    Rules: required, text, number, integer, boolean, email, url, min:N, max:N
    (length for text and lists, value for numbers), in:a,b,c, pattern:REGEX.
    """
    data = data if isinstance(data, dict) else {}
    errors: Dict[str, str] = {}
    for field, spec in (rules or {}).items():
        value = data.get(field)
        checks = [c.strip() for c in str(spec).split("|") if c.strip()]
        label = field.replace("_", " ").capitalize()
        empty = value is None or value == "" or value == []
        if empty:
            if "required" in checks:
                errors[field] = f"{label} is required"
            continue
        for check in checks:
            name, _, arg = check.partition(":")
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if name == "number" and not numeric:
                if isinstance(value, str) and re.match(r"^-?\d+(\.\d+)?$", value.strip()):
                    value = float(value) if "." in value else int(value)
                    numeric = True
                else:
                    errors[field] = f"{label} must be a number"; break
            elif name == "integer" and not (isinstance(value, int) and not isinstance(value, bool)):
                errors[field] = f"{label} must be a whole number"; break
            elif name == "boolean" and not isinstance(value, bool):
                errors[field] = f"{label} must be true or false"; break
            elif name == "text" and not isinstance(value, str):
                errors[field] = f"{label} must be text"; break
            elif name == "email" and not is_email(value):
                errors[field] = f"{label} must be a valid email address"; break
            elif name == "url" and not is_url(value):
                errors[field] = f"{label} must be a valid http(s) URL"; break
            elif name in ("min", "max") and arg:
                limit = float(arg)
                size = value if numeric else len(value) if hasattr(value, "__len__") else None
                if size is None:
                    continue
                if name == "min" and size < limit:
                    errors[field] = f"{label} must be at least {arg}" + ("" if numeric else " characters" if isinstance(value, str) else " items"); break
                if name == "max" and size > limit:
                    errors[field] = f"{label} must be at most {arg}" + ("" if numeric else " characters" if isinstance(value, str) else " items"); break
            elif name == "in" and str(value) not in [o.strip() for o in arg.split(",")]:
                errors[field] = f"{label} must be one of: {arg.replace(',', ', ')}"; break
            elif name == "pattern" and not re.fullmatch(arg, str(value)):
                errors[field] = f"{label} has the wrong format"; break
    return {"valid": not errors, "errors": errors, "data": data}


_COMMON = {"password", "123456", "12345678", "qwerty", "letmein", "welcome", "admin", "iloveyou", "monkey", "abc123"}


def password_strength(password: Any) -> Dict[str, Any]:
    """{score: 0–4, ok: score >= 3, issues: [...]} — guidance for sign-up forms."""
    pw = "" if password is None else str(password)
    issues: List[str] = []
    if len(pw) < 12:
        issues.append("Use at least 12 characters")
    classes = sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if classes < 3:
        issues.append("Mix upper and lower case letters, numbers and symbols")
    if pw.lower() in _COMMON or re.fullmatch(r"(.)\1+", pw or "x"):
        issues.append("This password is too common")
    score = max(0, min(4, (len(pw) >= 12) + (len(pw) >= 16) + (classes >= 3) + (classes == 4) - (2 if pw.lower() in _COMMON else 0)))
    return {"score": score, "ok": score >= 3 and not issues, "issues": issues}


def rate_limit(key: Any, limit: Any = 10, window_seconds: Any = 60) -> bool:
    """True if this call is within `limit` calls per `window_seconds` for `key` (e.g. an email or IP)."""
    return _limiter.allow(str(key), int(limit), float(window_seconds))


def mask(value: Any, visible: Any = 4) -> str:
    """"4111111111111111" → "••••••••••••1111" — show only the last characters."""
    s = "" if value is None else str(value)
    n = max(0, int(visible))
    return "•" * max(0, len(s) - n) + (s[-n:] if n else "")


def require(condition: Any, message: Any = "Not allowed") -> bool:
    """Stop with an error unless the condition holds: require(user.role == "admin", "Admins only")."""
    if not condition:
        raise PermissionError(str(message))
    return True


def secure_token(length: Any = 32) -> str:
    """A random URL-safe token for invites, password resets and API keys."""
    return secrets.token_urlsafe(max(16, int(length)))


def safe_equals(a: Any, b: Any) -> bool:
    """Compare secrets in constant time, so the comparison doesn't leak where they differ."""
    return hmac.compare_digest(str(a).encode(), str(b).encode())


# ── Tamper-evident audit log ─────────────────────────────────────────────────

_audit_lock = threading.Lock()


def _audit_path():
    from .paths import mcn_home
    custom = os.getenv("MCN_APP_AUDIT_LOG")
    if custom:
        from pathlib import Path
        return Path(custom)
    return mcn_home("audit") / "app_audit.jsonl"


def _entry_hash(entry: Dict[str, Any]) -> str:
    body = json.dumps({k: entry[k] for k in ("time", "action", "actor", "details", "prev")}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def audit_log(action: Any, details: Any = None, actor: Any = None) -> Dict[str, Any]:
    """
    Record who did what. Each entry stores the hash of the previous one, so
    editing or deleting an earlier entry is detected by verify_audit_log().
    """
    user = current_user()
    who = actor if actor is not None else (user.get("user") or user.get("email") or user.get("sub")) if isinstance(user, dict) else actor
    path = _audit_path()
    with _audit_lock:
        prev = "0" * 64
        if path.exists():
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                prev = json.loads(lines[-1]).get("hash", prev)
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "action": str(action),
                 "actor": who, "details": details, "prev": prev}
        entry["hash"] = _entry_hash(entry)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    return {"logged": True, "hash": entry["hash"], "file": str(path)}


def verify_audit_log() -> Dict[str, Any]:
    """{valid, entries, broken_at} — false if any entry was changed, removed or reordered."""
    path = _audit_path()
    if not path.exists():
        return {"valid": True, "entries": 0, "broken_at": None}
    prev = "0" * 64
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    for i, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return {"valid": False, "entries": len(lines), "broken_at": i}
        if entry.get("prev") != prev or entry.get("hash") != _entry_hash(entry):
            return {"valid": False, "entries": len(lines), "broken_at": i}
        prev = entry["hash"]
    return {"valid": True, "entries": len(lines), "broken_at": None}


BUILTINS = {
    "escape_html": escape_html, "sanitize_html": sanitize_html, "is_email": is_email, "is_url": is_url,
    "validate": validate, "password_strength": password_strength, "rate_limit": rate_limit, "mask": mask,
    "require": require, "secure_token": secure_token, "safe_equals": safe_equals,
    "audit_log": audit_log, "verify_audit_log": verify_audit_log, "current_user": current_user,
}
