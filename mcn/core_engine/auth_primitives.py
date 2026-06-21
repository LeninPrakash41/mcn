"""
MCN Auth Primitives — SQLite-backed user management as a language-level feature.

Available as the "auth" package:

    use "auth"

    var user  = auth.create_user("alice@example.com", "s3cur3!")
    var token = auth.login("alice@example.com", "s3cur3!")
    var me    = auth.require(token)
    auth.assign_role(user["id"], "admin")
    auth.require_role(token, "admin")

Also exports flat JWT primitives usable without the package:

    var token   = jwt_sign({user_id: 1, role: "admin"}, "secret", 3600)
    var payload = jwt_verify(token, "secret")

All user data is stored in ~/.mcn/auth.db (SQLite, persistent).
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Config ────────────────────────────────────────────────────────────────────

_DB_PATH = Path.home() / ".mcn" / "auth.db"
_SECRET  = os.getenv("MCN_AUTH_SECRET", "mcn-auth-default-secret-change-in-production")

# ── DB setup ──────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS mcn_users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    REAL NOT NULL,
            updated_at    REAL NOT NULL,
            metadata      TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS mcn_roles (
            user_id TEXT NOT NULL,
            role    TEXT NOT NULL,
            PRIMARY KEY (user_id, role),
            FOREIGN KEY (user_id) REFERENCES mcn_users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_mcn_users_email ON mcn_users(email);
    """)
    c.commit()
    return c

# ── Internal helpers ──────────────────────────────────────────────────────────

def _hash_pw(password: str) -> str:
    salt   = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), 260_000)
    return f"pbkdf2${salt}${digest.hex()}"

def _verify_pw(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        new = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), 260_000)
        return _hmac.compare_digest(new.hex(), digest)
    except Exception:
        return False

def _make_token(payload: dict, secret: str = "", expires_in: int = 86_400) -> str:
    import base64
    data = dict(payload)
    data["_exp"] = int(time.time()) + int(expires_in)
    data["_iat"] = int(time.time())
    key    = str(secret).encode() if secret else _SECRET.encode()
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    body   = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    msg    = f"{header}.{body}"
    sig    = _hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"

def _decode_token(token: str, secret: str = "") -> Optional[Dict]:
    import base64
    try:
        parts = str(token).strip().removeprefix("Bearer ").strip().split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        key      = str(secret).encode() if secret else _SECRET.encode()
        expected = _hmac.new(key, f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(expected, sig):
            return None
        pad  = "=" * (-len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(body + pad))
        if data.get("_exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

def _user_dict(row: sqlite3.Row, roles: List[str]) -> Dict:
    d = dict(row)
    d.pop("password_hash", None)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except Exception:
        d["metadata"] = {}
    d["roles"] = roles
    return d

def _get_roles(c: sqlite3.Connection, user_id: str) -> List[str]:
    return [r["role"] for r in c.execute(
        "SELECT role FROM mcn_roles WHERE user_id = ?", (user_id,)
    ).fetchall()]

# ── User management ───────────────────────────────────────────────────────────

def auth_create_user(email: str, password: str, metadata: Any = None) -> Dict:
    """
    Create a new user. Returns the user dict (password excluded).
    Raises ValueError if email already exists.
    """
    c = _conn()
    uid = str(uuid.uuid4())
    now = time.time()
    try:
        c.execute(
            "INSERT INTO mcn_users (id, email, password_hash, created_at, updated_at, metadata) "
            "VALUES (?,?,?,?,?,?)",
            (uid, str(email).lower().strip(), _hash_pw(str(password)),
             now, now, json.dumps(metadata if isinstance(metadata, dict) else {}))
        )
        c.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A user with email '{email}' already exists")
    finally:
        c.close()
    return {"id": uid, "email": email.lower().strip(),
            "created_at": now, "roles": [], "metadata": metadata or {}}


def auth_login(email: str, password: str, expires_in: int = 86_400) -> str:
    """
    Verify credentials and return a signed token.
    Raises ValueError on bad credentials.
    """
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM mcn_users WHERE email = ?",
            (str(email).lower().strip(),)
        ).fetchone()
        if not row or not _verify_pw(str(password), row["password_hash"]):
            raise ValueError("Invalid email or password")
        roles = _get_roles(c, row["id"])
    finally:
        c.close()
    return _make_token({"sub": row["id"], "email": row["email"], "roles": roles},
                       expires_in=expires_in)


def auth_verify_token(token: str) -> Optional[Dict]:
    """Decode and verify a token. Returns payload dict or null if invalid/expired."""
    return _decode_token(token)


def auth_require(token: str) -> Dict:
    """Like verify_token but throws if the token is invalid or expired."""
    payload = _decode_token(token)
    if not payload:
        raise ValueError("Unauthorized: invalid or expired token")
    return payload


def auth_require_role(token: str, role: str) -> Dict:
    """Verify token AND check that the user holds `role`. Throws if not."""
    payload = auth_require(token)
    if str(role) not in (payload.get("roles") or []):
        raise ValueError(f"Forbidden: role '{role}' required")
    return payload


def auth_has_role(user_id: str, role: str) -> bool:
    """Check whether a user has a specific role."""
    c = _conn()
    try:
        return c.execute(
            "SELECT 1 FROM mcn_roles WHERE user_id = ? AND role = ?",
            (str(user_id), str(role))
        ).fetchone() is not None
    finally:
        c.close()


def auth_assign_role(user_id: str, role: str) -> bool:
    """Assign a role to a user. Idempotent — no error if already assigned."""
    c = _conn()
    try:
        c.execute("INSERT OR IGNORE INTO mcn_roles (user_id, role) VALUES (?,?)",
                  (str(user_id), str(role)))
        c.commit()
    finally:
        c.close()
    return True


def auth_revoke_role(user_id: str, role: str) -> bool:
    """Remove a role from a user."""
    c = _conn()
    try:
        c.execute("DELETE FROM mcn_roles WHERE user_id = ? AND role = ?",
                  (str(user_id), str(role)))
        c.commit()
    finally:
        c.close()
    return True


def auth_get_user(user_id: str) -> Optional[Dict]:
    """Get a user by ID. Returns user dict or null."""
    c = _conn()
    try:
        row = c.execute("SELECT * FROM mcn_users WHERE id = ?", (str(user_id),)).fetchone()
        if not row:
            return None
        return _user_dict(row, _get_roles(c, row["id"]))
    finally:
        c.close()


def auth_get_user_by_email(email: str) -> Optional[Dict]:
    """Get a user by email. Returns user dict or null."""
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM mcn_users WHERE email = ?",
            (str(email).lower().strip(),)
        ).fetchone()
        if not row:
            return None
        return _user_dict(row, _get_roles(c, row["id"]))
    finally:
        c.close()


def auth_delete_user(user_id: str) -> bool:
    """Delete a user by ID."""
    c = _conn()
    try:
        c.execute("DELETE FROM mcn_users WHERE id = ?", (str(user_id),))
        c.commit()
    finally:
        c.close()
    return True


def auth_list_users() -> List[Dict]:
    """Return all users (for admin dashboards)."""
    c = _conn()
    try:
        rows = c.execute("SELECT * FROM mcn_users ORDER BY created_at DESC").fetchall()
        return [_user_dict(r, _get_roles(c, r["id"])) for r in rows]
    finally:
        c.close()


def auth_update_metadata(user_id: str, metadata: Dict) -> bool:
    """Merge metadata dict into user record."""
    c = _conn()
    try:
        row = c.execute("SELECT metadata FROM mcn_users WHERE id = ?",
                        (str(user_id),)).fetchone()
        if not row:
            return False
        try:
            existing = json.loads(row["metadata"] or "{}")
        except Exception:
            existing = {}
        existing.update(metadata if isinstance(metadata, dict) else {})
        c.execute("UPDATE mcn_users SET metadata = ?, updated_at = ? WHERE id = ?",
                  (json.dumps(existing), time.time(), str(user_id)))
        c.commit()
    finally:
        c.close()
    return True

# ── JWT primitives (also exposed as flat built-ins) ───────────────────────────

def jwt_sign(payload: Any, secret: str = "", expires_in: int = 3600) -> str:
    """
    Sign any dict as a JWT-style token.
    jwt_sign({user_id: 42, role: "admin"}, "my-secret", 3600)
    """
    data = dict(payload) if isinstance(payload, dict) else {"value": payload}
    return _make_token(data, secret=str(secret), expires_in=int(expires_in))


def jwt_verify(token: str, secret: str = "") -> Optional[Dict]:
    """
    Verify and decode a token. Returns payload dict or null if invalid/expired.
    jwt_verify(token, "my-secret")
    """
    return _decode_token(str(token), secret=str(secret))

# ── Package export ────────────────────────────────────────────────────────────

def get_auth_package() -> Dict:
    """Return the dict of functions exposed via `use "auth"`."""
    return {
        # User lifecycle
        "create_user":       auth_create_user,
        "login":             auth_login,
        "delete_user":       auth_delete_user,
        "list_users":        auth_list_users,
        "update_metadata":   auth_update_metadata,
        # Lookup
        "get_user":          auth_get_user,
        "get_user_by_email": auth_get_user_by_email,
        # Token
        "verify_token":      auth_verify_token,
        "require":           auth_require,
        # Role-based access control
        "assign_role":       auth_assign_role,
        "revoke_role":       auth_revoke_role,
        "has_role":          auth_has_role,
        "require_role":      auth_require_role,
        # JWT primitives (also accessible flat via stdlib)
        "jwt_sign":          jwt_sign,
        "jwt_verify":        jwt_verify,
    }
