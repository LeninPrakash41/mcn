#!/usr/bin/env python3
"""The Mummy - game server.

Serves the browser game (static/) and a small JSON leaderboard API backed by
SQLite. Uses only the Python standard library.

    python server.py            # http://localhost:8000
    python server.py --port 9000
"""

import argparse
import json
import re
import sqlite3
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "scores.db"
NAME_RE = re.compile(r"^[\w .\-]{1,20}$", re.UNICODE)
MAX_SCORE = 10_000_000
MAX_BODY = 1024

_db_lock = threading.Lock()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scores (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   score INTEGER NOT NULL,
                   level INTEGER NOT NULL,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )


def top_scores(limit=10):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT name, score, level FROM scores ORDER BY score DESC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"name": n, "score": s, "level": lv} for n, s, lv in rows]


def add_score(name, score, level):
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scores (name, score, level) VALUES (?, ?, ?)",
            (name, score, level),
        )


def validate(payload):
    if not isinstance(payload, dict):
        return None, "body must be a JSON object"
    name = str(payload.get("name", "")).strip()
    score = payload.get("score")
    level = payload.get("level")
    if not NAME_RE.match(name):
        return None, "name must be 1-20 letters, digits, spaces, '.', '-' or '_'"
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= MAX_SCORE:
        return None, "score must be an integer between 0 and %d" % MAX_SCORE
    if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 1000:
        return None, "level must be an integer between 1 and 1000"
    return (name, score, level), None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/scores":
            self._json(200, top_scores())
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/scores":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(400, {"error": "invalid body size"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "invalid JSON"})
            return
        values, err = validate(payload)
        if err:
            self._json(400, {"error": err})
            return
        add_score(*values)
        self._json(201, {"ok": True, "top": top_scores()})


def main():
    parser = argparse.ArgumentParser(description="The Mummy game server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    init_db()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"The Mummy is awake at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
