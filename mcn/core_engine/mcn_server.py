"""
MCN Server Runtime — serves a parsed MCN service file over HTTP.

Each service endpoint becomes a POST route:
  endpoint submit_claim(claimant, amount, ...)  →  POST /submit_claim
  endpoint list_claims(limit = 50)              →  POST /list_claims

Reads the JSON body and maps keys → positional args using the evaluator's
``function_params`` dict (populated during evaluation).

Usage:
  mcn serve --file backend/main.mcn --port 8080

Or from Python:
  from mcn.core_engine.mcn_server import serve_script
  serve_script("backend/main.mcn", port=8080)
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List

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

        def do_GET(self):
            path = self.path.lstrip("/") or ""
            if path == "":
                # Health check / route list
                routes = list(evaluator.function_params.keys())
                self._send_json(200, {"status": "ok", "endpoints": routes})
            else:
                fn_name = path.split("?")[0]
                if fn_name not in evaluator.functions:
                    self._send_json(404, {"error": f"Unknown endpoint: {fn_name}"})
                    return
                try:
                    result = evaluator.functions[fn_name]()
                    self._send_json(200, result if result is not None else {})
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})

        def do_POST(self):
            fn_name = self.path.lstrip("/").split("?")[0]
            if fn_name not in evaluator.functions:
                self._send_json(404, {"error": f"Unknown endpoint: {fn_name}"})
                return

            # Read JSON body
            length = int(self.headers.get("Content-Length", 0))
            body: Dict[str, Any] = {}
            if length:
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON body"})
                    return

            # Map body dict → ordered positional args using stored param names.
            # Stop at the first param NOT in the body so MCN defaults apply.
            params: List[str] = evaluator.function_params.get(fn_name, [])
            args = []
            for p in params:
                if p not in body:
                    break   # remaining params use their MCN default values
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
