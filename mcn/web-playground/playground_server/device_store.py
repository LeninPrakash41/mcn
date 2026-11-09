"""Device sign-in records for hosted Studio (the MCN account server).

A desktop Studio or `mcn login` asks for a code, the user approves it in the
browser, and the desktop receives a token tied to a session row here. Admins
see those sessions per user and can revoke them; a revoked session's token
stops working on the next request.
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from pathlib import Path

CODE_TTL_S = 10 * 60            # how long a sign-in code can be approved
POLL_INTERVAL_S = 3             # how often the desktop should ask
SESSION_TTL_S = 30 * 86_400     # a desktop stays signed in for 30 days
_TOUCH_EVERY_S = 300            # last_seen is written at most every 5 minutes

# No 0/O, 1/I/L: easy to read aloud and type from a phone
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_DB_PATH = Path.home() / ".mcn" / "device_sessions.db"
_lock = threading.Lock()
_touched: dict[str, float] = {}


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS device_codes (
            device_code TEXT PRIMARY KEY,
            user_code   TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            created_at  REAL NOT NULL,
            expires_at  REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            user_id     TEXT,
            sid         TEXT
        );
        CREATE TABLE IF NOT EXISTS device_sessions (
            sid         TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            client_name TEXT NOT NULL,
            created_at  REAL NOT NULL,
            last_seen   REAL NOT NULL,
            expires_at  REAL NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_device_sessions_user ON device_sessions(user_id);
    """)
    return c


def normalize_user_code(code: str) -> str:
    raw = "".join(ch for ch in str(code).upper() if ch.isalnum())
    return f"{raw[:4]}-{raw[4:8]}" if len(raw) == 8 else raw


def create_code(client_name: str) -> dict:
    """A new pending sign-in: a secret device_code for the desktop, a short user_code for the person."""
    client_name = (str(client_name or "").strip() or "MCN Studio")[:80]
    now = time.time()
    with _lock, _conn() as c:
        c.execute("DELETE FROM device_codes WHERE expires_at < ?", (now - CODE_TTL_S,))
        while True:
            user_code = normalize_user_code("".join(secrets.choice(_CODE_ALPHABET) for _ in range(8)))
            if not c.execute("SELECT 1 FROM device_codes WHERE user_code = ?", (user_code,)).fetchone():
                break
        device_code = secrets.token_urlsafe(32)
        c.execute("INSERT INTO device_codes (device_code, user_code, client_name, created_at, expires_at) "
                  "VALUES (?,?,?,?,?)", (device_code, user_code, client_name, now, now + CODE_TTL_S))
    return {"device_code": device_code, "user_code": user_code, "client_name": client_name,
            "expires_in": CODE_TTL_S, "interval": POLL_INTERVAL_S}


def lookup_user_code(user_code: str) -> dict | None:
    """The pending request behind a user code, or None if unknown or expired."""
    with _conn() as c:
        row = c.execute("SELECT * FROM device_codes WHERE user_code = ?",
                        (normalize_user_code(user_code),)).fetchone()
    if not row or row["expires_at"] < time.time() or row["status"] != "pending":
        return None
    return {"user_code": row["user_code"], "client_name": row["client_name"],
            "expires_at": row["expires_at"]}


def decide(user_code: str, user_id: str, approve: bool) -> dict | None:
    """Approve (creating a session) or deny a pending code. None if it's no longer pending."""
    now = time.time()
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM device_codes WHERE user_code = ?",
                        (normalize_user_code(user_code),)).fetchone()
        if not row or row["expires_at"] < now or row["status"] != "pending":
            return None
        if not approve:
            c.execute("UPDATE device_codes SET status = 'denied', user_id = ? WHERE device_code = ?",
                      (user_id, row["device_code"]))
            return {"status": "denied", "client_name": row["client_name"]}
        sid = secrets.token_urlsafe(16)
        c.execute("INSERT INTO device_sessions (sid, user_id, client_name, created_at, last_seen, expires_at) "
                  "VALUES (?,?,?,?,?,?)", (sid, user_id, row["client_name"], now, now, now + SESSION_TTL_S))
        c.execute("UPDATE device_codes SET status = 'approved', user_id = ?, sid = ? WHERE device_code = ?",
                  (user_id, sid, row["device_code"]))
    return {"status": "approved", "client_name": row["client_name"], "sid": sid}


def claim(device_code: str) -> dict:
    """What the desktop gets when it polls: pending, denied, expired, or (once) approved with its session."""
    now = time.time()
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM device_codes WHERE device_code = ?", (str(device_code),)).fetchone()
        if not row:
            return {"status": "expired"}
        if row["status"] == "approved":
            # Hand the session over exactly once
            c.execute("DELETE FROM device_codes WHERE device_code = ?", (row["device_code"],))
            return {"status": "approved", "user_id": row["user_id"], "sid": row["sid"]}
        if row["status"] == "denied":
            c.execute("DELETE FROM device_codes WHERE device_code = ?", (row["device_code"],))
            return {"status": "denied"}
        if row["expires_at"] < now:
            return {"status": "expired"}
        return {"status": "pending"}


def session_active(sid: str) -> bool:
    """True while the session exists, isn't revoked and hasn't expired. Also records when it was last used."""
    now = time.time()
    try:
        with _conn() as c:
            row = c.execute("SELECT revoked, expires_at FROM device_sessions WHERE sid = ?", (str(sid),)).fetchone()
            if not row or row["revoked"] or row["expires_at"] < now:
                return False
            if now - _touched.get(sid, 0) > _TOUCH_EVERY_S:
                _touched[sid] = now
                c.execute("UPDATE device_sessions SET last_seen = ? WHERE sid = ?", (now, sid))
        return True
    except sqlite3.Error:
        return False


def sessions_for(user_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT sid, client_name, created_at, last_seen, expires_at FROM device_sessions "
                         "WHERE user_id = ? AND revoked = 0 AND expires_at > ? ORDER BY last_seen DESC",
                         (str(user_id), time.time())).fetchall()
    return [dict(r) for r in rows]


def revoke(sid: str, user_id: str | None = None) -> bool:
    """Sign a desktop out. With user_id, only that user's own session can be revoked."""
    with _lock, _conn() as c:
        if user_id is None:
            cur = c.execute("UPDATE device_sessions SET revoked = 1 WHERE sid = ?", (str(sid),))
        else:
            cur = c.execute("UPDATE device_sessions SET revoked = 1 WHERE sid = ? AND user_id = ?",
                            (str(sid), str(user_id)))
    _touched.pop(sid, None)
    return cur.rowcount > 0
