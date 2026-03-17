"""
MCN Server Runtime — serves a parsed MCN service file over HTTP.

Endpoints map to HTTP methods based on naming convention OR explicit attribute:

  endpoint get_users(limit = 50)       →  GET  /get_users?limit=50
  endpoint create_user(name, email)    →  POST /create_user  { "name":..., "email":... }
  endpoint delete_user(id)             →  POST /delete_user  (or DELETE via OPTIONS)

Path parameters  (/users/42) are also supported — the server matches
  /endpoint_name/<value>  and passes <value> as the first positional arg.

GET naming heuristic: endpoint names starting with get_, list_, fetch_, search_,
  count_, find_ are served on GET as well as POST, with query-string → args mapping.

Usage:
  mcn serve --file backend/main.mcn --port 8080
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

_GET_PREFIXES = ("get_", "list_", "fetch_", "search_", "count_", "find_", "read_")

from .mcn_interpreter import MCNInterpreter
from .lexer import Lexer
from .parser import Parser
from .evaluator import Evaluator


def _load_evaluator(script_path: str) -> Evaluator:
    """Parse and evaluate an MCN file; return the populated evaluator."""
    code = open(script_path, encoding="utf-8").read()
    tokens  = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    interp  = MCNInterpreter()
    ev      = interp._evaluator
    ev.execute_program(program)
    return ev


def _make_handler(evaluator: Evaluator, cors_origin: str = "*"):
    """Return an HTTPServer handler class bound to the given evaluator."""

    class MCNHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # suppress default access log
            pass

        def _send_json(self, status: int, obj: Any):
            body = json.dumps(obj, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type",  "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin",  cors_origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin",  cors_origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _resolve_endpoint(self, raw_path: str):
            """
            Return (fn_name, path_arg, query_params) from a raw URL path.

            Supports:
              /get_users              → ("get_users", None, {})
              /get_users?limit=10     → ("get_users", None, {"limit": "10"})
              /get_user/42            → ("get_user", "42", {})
              /get_user/42?expand=true → ("get_user", "42", {"expand": "true"})
            """
            parsed = urllib.parse.urlparse(raw_path)
            parts  = parsed.path.strip("/").split("/", 1)
            fn_name   = parts[0]
            path_arg  = parts[1] if len(parts) > 1 else None
            qs        = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            # Flatten single-item lists from parse_qs
            query_params = {k: v[0] if len(v) == 1 else v for k, v in qs.items()}
            return fn_name, path_arg, query_params

        def do_GET(self):
            fn_name, path_arg, query_params = self._resolve_endpoint(self.path)

            if not fn_name:
                # Health / route list
                routes = [
                    {"name": k, "params": v, "methods": ["POST"] + (["GET"] if any(k.startswith(p) for p in _GET_PREFIXES) else [])}
                    for k, v in evaluator.function_params.items()
                ]
                self._send_json(200, {"status": "ok", "version": "MCN/2.0", "endpoints": routes})
                return

            if fn_name not in evaluator.functions:
                self._send_json(404, {"error": f"Unknown endpoint: '{fn_name}'"})
                return

            # Build args: path_arg first (if any), then query string params
            params: List[str] = evaluator.function_params.get(fn_name, [])
            args = []
            if path_arg is not None and params:
                args.append(path_arg)
                params = params[1:]  # skip first param (consumed by path)
            for p in params:
                if p in query_params:
                    # Try numeric coercion for convenience
                    raw = query_params[p]
                    try:
                        args.append(int(raw))
                    except (ValueError, TypeError):
                        try:
                            args.append(float(raw))
                        except (ValueError, TypeError):
                            args.append(raw)
                else:
                    break  # remaining use MCN defaults

            try:
                result = evaluator.functions[fn_name](*args)
                self._send_json(200, result if result is not None else {})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})

        def do_POST(self):
            fn_name, path_arg, _ = self._resolve_endpoint(self.path)
            if fn_name not in evaluator.functions:
                self._send_json(404, {"error": f"Unknown endpoint: '{fn_name}'"})
                return

            # Read JSON body (optional)
            length = int(self.headers.get("Content-Length", 0))
            body: Dict[str, Any] = {}
            if length:
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON body"})
                    return

            # Build args: path_arg first (if any), then body dict keys in param order
            params: List[str] = list(evaluator.function_params.get(fn_name, []))
            args = []
            if path_arg is not None and params:
                args.append(path_arg)
                params = params[1:]
            for p in params:
                if p not in body:
                    break   # remaining use MCN defaults
                args.append(body[p])

            try:
                result = evaluator.functions[fn_name](*args)
                self._send_json(200, result if result is not None else {})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})

    return MCNHandler


def serve_script(script_path: str, host: str = "0.0.0.0", port: int = 8080):
    """Evaluate an MCN service file and serve each endpoint as a POST route."""
    if not os.path.exists(script_path):
        print(f"Error: file not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading: {script_path}")
    ev = _load_evaluator(script_path)

    if not ev.function_params:
        print("Warning: no service endpoints found — serving raw functions only")

    handler = _make_handler(ev)
    server  = HTTPServer((host, port), handler)

    print(f"\nMCN server running on http://localhost:{port}")
    print("Endpoints:")
    for name, params in ev.function_params.items():
        sig = ", ".join(params) if params else "(no params)"
        print(f"  POST /{name}  ← {sig}")
    print("\nPress Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


def serve_directory(directory: str, host: str = "0.0.0.0", port: int = 8080):
    """Serve all .mcn files in a directory (loads each, merges endpoints)."""
    import importlib

    # Merge all evaluators by loading each file
    all_fns:     Dict[str, Any]        = {}
    all_params:  Dict[str, List[str]]  = {}

    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".mcn"):
            continue
        path = os.path.join(directory, fname)
        try:
            ev = _load_evaluator(path)
            all_fns.update(ev.functions)
            all_params.update(ev.function_params)
            print(f"  loaded  {fname}  ({len(ev.function_params)} endpoints)")
        except Exception as exc:
            print(f"  error   {fname}: {exc}")

    # Build a stub evaluator shell to pass to handler
    class _Stub:
        functions      = all_fns
        function_params = all_params

    handler = _make_handler(_Stub())  # type: ignore[arg-type]
    server  = HTTPServer((host, port), handler)

    print(f"\nMCN server running on http://localhost:{port}")
    print(f"Endpoints: {', '.join(all_params) or 'none'}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
