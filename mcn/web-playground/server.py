#!/usr/bin/env python3
"""
MCN Studio server (the browser IDE)

Endpoints:
  GET  /                          — serve the playground UI
  GET  /api/health                — liveness check
  GET  /api/examples              — bundled example snippets

  # Workspace (project files)
  GET  /api/workspace/files       — list project files
  GET  /api/workspace/file        — get file content  (?path=...)
  POST /api/workspace/file        — save file content {path, content}

  # MCN operations
  POST /api/execute               — run MCN code
  POST /api/format                — format MCN code
  POST /api/check                 — type-check MCN code
  POST /api/test                  — run test blocks

  # AI Agent
  POST /api/generate              — stream MCN generation via SSE

  # Compiler + preview
  POST /api/build                 — compile ui/app.mcn → React project
  GET  /api/frontend/file         — read generated file (?path=...)
  POST /api/devserver/start       — start Vite dev server
  POST /api/devserver/stop        — stop Vite dev server
  GET  /api/devserver/status      — poll dev server health
"""

import importlib
import os
import re
import sys

# The feature modules live in ./playground_server; make them importable however
# this file is launched (python server.py, the desktop app, or the test suite).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playground_server import BLUEPRINT_MODULES, core  # noqa: E402
from playground_server.core import CORS, Flask, jsonify, request  # noqa: E402
from playground_server.workspace_seed import _seed_workspace  # noqa: E402



# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
            static_url_path="/static")
# Shared (anonymous) workspace; logged-in users get their own under ~/.mcn/workspaces
app.config["WORKSPACE"] = core.WORKSPACE

# The playground executes arbitrary MCN code (file, env, network and shell
# builtins), so only loopback pages may call it. Extra origins can be allowed
# via MCN_PLAYGROUND_ALLOWED_ORIGINS (comma-separated, exact match).
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
_LOOPBACK_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
_EXTRA_ORIGINS = {
    o.strip().rstrip("/") for o in os.environ.get("MCN_PLAYGROUND_ALLOWED_ORIGINS", "").split(",") if o.strip()
}
# Set to False in __main__ when the server is deliberately bound to a public interface.
_LOCAL_ONLY = True


def _origin_allowed(origin: str) -> bool:
    origin = origin.rstrip("/")
    return bool(_LOOPBACK_ORIGIN_RE.match(origin)) or origin in _EXTRA_ORIGINS


CORS(app, origins=[_LOOPBACK_ORIGIN_RE, *_EXTRA_ORIGINS])


@app.before_request
def _guard_request_source():
    # CORS only hides responses; a cross-site "simple" POST still reaches the
    # handler, so refuse foreign origins before any code runs.
    origin = request.headers.get("Origin")
    if origin and not _origin_allowed(origin):  # also rejects sandboxed "null" origins
        return jsonify({"error": "Origin not allowed"}), 403
    # Block DNS-rebinding: a loopback-bound server must be addressed as loopback.
    if _LOCAL_ONLY:
        host = request.host.rsplit(":", 1)[0] if not request.host.startswith("[") else request.host.split("]")[0] + "]"
        if host not in _LOOPBACK_HOSTS:
            return jsonify({"error": "Host not allowed"}), 403

@app.after_request
def _add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── Feature blueprints ────────────────────────────────────────────────────────

for _name in BLUEPRINT_MODULES:
    app.register_blueprint(importlib.import_module(f"playground_server.{_name}").bp)


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    _seed_workspace()
    import argparse
    parser = argparse.ArgumentParser(description="MCN Web Playground Server")
    parser.add_argument("-p", "--port", type=int, default=int(os.environ.get("MCN_PLAYGROUND_PORT", 5003)), help="Port to run server on")
    parser.add_argument("--host", type=str, default=os.environ.get("MCN_PLAYGROUND_HOST", "127.0.0.1"),
                        help="Host address to bind to (default: loopback only)")
    args, _ = parser.parse_known_args()
    port = args.port
    if args.host not in _LOOPBACK_HOSTS:
        _LOCAL_ONLY = False
        print(f"WARNING: binding to {args.host} exposes unauthenticated code execution to the network. "
              "Only do this inside an isolated container or sandbox.")
    print(f"MCN Studio — http://localhost:{port}")
    print(f"Workspace: {app.config['WORKSPACE']}")
    app.run(debug=False, host=args.host, port=port, threaded=True)
