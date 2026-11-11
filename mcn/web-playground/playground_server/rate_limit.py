"""Limits on sign-in attempts for hosted Studio, so passwords and codes can't be guessed.

Counts are kept in memory per server process. Run hosted Studio as one process (or
put a limiter in the reverse proxy too) for the limits to hold across workers.
"""
from __future__ import annotations

import math
import os
import threading
import time
from collections import deque

from flask import jsonify, request

# (attempts allowed, window in seconds). Generous enough for a class signing in
# from one school network, tight enough to stop guessing.
LIMITS = {
    "login_email": (10, 15 * 60),      # failed sign-ins for one account
    "login_ip": (100, 15 * 60),        # failed sign-ins from one address
    "register_ip": (50, 60 * 60),      # new accounts from one address
    "device_code_ip": (60, 10 * 60),   # sign-in codes requested from one address
    "device_guess": (10, 10 * 60),     # wrong sign-in codes entered by one user
}

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = {}


def client_ip() -> str:
    """The caller's address. Behind a reverse proxy, set MCN_TRUST_PROXY=1 to use X-Forwarded-For."""
    if os.environ.get("MCN_TRUST_PROXY") == "1":
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _window(bucket: str, key: str) -> deque:
    _, seconds = LIMITS[bucket]
    q = _hits.setdefault((bucket, key), deque())
    cutoff = time.monotonic() - seconds
    while q and q[0] < cutoff:
        q.popleft()
    return q


def retry_after(bucket: str, key: str) -> int:
    """Seconds until another attempt is allowed; 0 when it's allowed now."""
    limit, seconds = LIMITS[bucket]
    with _lock:
        q = _window(bucket, str(key).lower())
        if len(q) < limit:
            return 0
        return max(1, math.ceil(q[0] + seconds - time.monotonic()))


def record(bucket: str, key: str) -> None:
    with _lock:
        _window(bucket, str(key).lower()).append(time.monotonic())


def clear(bucket: str, key: str) -> None:
    with _lock:
        _hits.pop((bucket, str(key).lower()), None)


def reset_all() -> None:
    """Forget every count (tests)."""
    with _lock:
        _hits.clear()


def too_many(seconds: int, what: str = "attempts"):
    """The 429 response, telling people when they can try again."""
    minutes = max(1, math.ceil(seconds / 60))
    res = jsonify({"error": f"Too many {what}. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
                   "retry_after": seconds})
    res.status_code = 429
    res.headers["Retry-After"] = str(seconds)
    return res


def check(*buckets: tuple[str, str], what: str = "attempts"):
    """A 429 response if any (bucket, key) is over its limit, else None."""
    wait = max((retry_after(b, k) for b, k in buckets), default=0)
    return too_many(wait, what) if wait else None
