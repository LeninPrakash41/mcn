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
from .mcn_interpreter import MCNInterpreter
from .lexer import Lexer
from .parser import Parser
from .evaluator import Evaluator

_GET_PREFIXES = ("get_", "list_", "fetch_", "search_", "count_", "find_", "read_")


# ── FastAPI implementation from develop ──────────────────────────────────────────

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def _coerce(raw):
    """Query-string values arrive as text; '10' → 10, '2.5' → 2.5."""
    for convert in (int, float):
        try:
            return convert(raw)
        except (ValueError, TypeError):
            pass
    return raw


def _get_args(params: List[str], path_arg, query_params: Dict[str, Any]) -> list:
    """GET /get_user/42?expand=true → [42, "true"]: the path segment fills the
    first parameter, query values fill the rest by name, until one is missing."""
    args = []
    if path_arg is not None and params:
        args.append(_coerce(path_arg))
        params = params[1:]
    for p in params:
        if p not in query_params:
            break  # remaining use MCN defaults
        args.append(_coerce(query_params[p]))
    return args


class MCNServer:
    """FastAPI-based server runtime from develop branch."""

    def __init__(self):
        if HAS_FASTAPI:
            self.app = FastAPI(title="MCN API", version=__import__("mcn.version", fromlist=["x"]).__version__)

            # Add CORS middleware
            from fastapi.middleware.cors import CORSMiddleware
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            try:
                from apscheduler.schedulers.background import BackgroundScheduler
                self.scheduler = BackgroundScheduler()
            except ImportError:
                self.scheduler = None
        else:
            self.app = None
        self.interpreters = {}
        self.routes = {}
        self.evaluators: List[Evaluator] = []

    def load_script(self, script_path: str, endpoint: str = None):
        """Load MCN script as API endpoint"""
        if not HAS_FASTAPI:
            print("Warning: FastAPI/Uvicorn not found. Running in fallback mode.")
            return None

        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Check if the script defines service endpoints
        ev = _load_evaluator(script_path)

        if ev:
            # Register endpoints
            if ev.function_params:
                for fn_name, params in ev.function_params.items():
                    self._register_fastapi_endpoint(fn_name, params, ev)
                self.evaluators.append(ev)
                self.routes[f"/{os.path.basename(script_path)}"] = f"service endpoints ({len(ev.function_params)})"
            
            # Register schedules
            from .runtime_types import MCNSchedule
            for name, obj in ev.functions.items():
                if isinstance(obj, MCNSchedule):
                    if self.scheduler:
                        from apscheduler.triggers.cron import CronTrigger
                        self.scheduler.add_job(obj.fn, CronTrigger.from_crontab(obj.cron_expr), id=name)
                    else:
                        print(f"Warning: apscheduler not installed. Cannot schedule '{name}'.")
            
            if ev.function_params:
                return f"/{os.path.basename(script_path)}"

        script_name = os.path.basename(script_path).replace(".mcn", "")
        endpoint = endpoint or f"/{script_name}"

        # Create interpreter for this script
        interpreter = MCNInterpreter()

        # Read and parse script
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()

        self.interpreters[endpoint] = {
            "interpreter": interpreter,
            "script": script_content,
            "path": script_path,
        }

        # Create FastAPI route
        @self.app.post(endpoint)
        async def execute_script(data: Dict[str, Any] = None):
            try:
                # Set request data as variables
                if data:
                    for key, value in data.items():
                        interpreter.variables[key] = value

                # Execute script
                result = interpreter.execute(script_content)

                return JSONResponse(
                    {
                        "success": True,
                        "result": result,
                        "variables": interpreter.variables,
                    }
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        self.routes[endpoint] = script_path
        return endpoint

    def _register_fastapi_endpoint(self, fn_name: str, params: List[str], evaluator: Evaluator):
        def run(args):
            try:
                result = evaluator.functions[fn_name](*args)
                return JSONResponse(result if result is not None else {})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        async def post_endpoint(request: Request):
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                body = dict(await request.form())
            else:
                try: body = await request.json()
                except Exception: body = {}
            args = []
            for p in params:
                if p not in body:
                    break
                args.append(body[p])
            return run(args)

        async def get_endpoint(request: Request, path_arg: str = None):
            return run(_get_args(params, path_arg, dict(request.query_params)))

        self.app.add_api_route(f"/{fn_name}", post_endpoint, methods=["POST"])
        self.app.add_api_route(f"/{fn_name}", get_endpoint, methods=["GET"])
        self.app.add_api_route(f"/{fn_name}/{{path_arg}}", get_endpoint, methods=["GET"])

    def serve(self, host: str = "127.0.0.1", port: int = 8080, auto_postman: bool = False):
        """Start the MCN server"""
        if not HAS_FASTAPI:
            print("Error: FastAPI/Uvicorn are required to use MCNServer. Please install them or use the standard HTTP server.")
            return

        @self.app.get("/")
        async def route_list():
            return {"status": "ok", "endpoints": [
                {"name": n, "params": p, "methods": ["GET", "POST"]}
                for ev in self.evaluators for n, p in ev.function_params.items()]}

        for ev in self.evaluators:
            _print_routes(ev, host, port, docs=True)
        
        # Auto-generate Postman collection
        if auto_postman:
            try:
                from .mcn_postman_generator import auto_generate_on_server_start
                auto_generate_on_server_start(self)
            except Exception as e:
                print(f"⚠️  Postman generation failed: {e}")

        if self.scheduler and self.scheduler.get_jobs():
            self.scheduler.start()
            print(f"Started {len(self.scheduler.get_jobs())} scheduled background jobs.")

        uvicorn.run(self.app, host=host, port=port)


# ── Standard BaseHTTPRequestHandler server from main ───────────────────────────

def _load_evaluator(script_path: str) -> Evaluator:
    """Run an MCN file (refusing any syntax error) and return the populated evaluator."""
    code = open(script_path, encoding="utf-8").read()
    interp = MCNInterpreter()
    interp.execute(code, script_path, quiet=True)
    return interp._evaluator


def declared_port(script_path: str) -> Optional[int]:
    """The `port` from the file's `service` block, if it has one."""
    try:
        program = Parser(Lexer(open(script_path, encoding="utf-8").read()).tokenize()).parse()
    except Exception:
        return None
    for stmt in program.body:
        if type(stmt).__name__ == "ServiceDecl" and stmt.port:
            return int(stmt.port)
    return None


def _print_routes(evaluator: Evaluator, host: str, port: int, docs: bool):
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0", "::") else host
    print(f"\nMCN API running on http://{shown}:{port}")
    for name, params in evaluator.function_params.items():
        print(f"  GET/POST /{name}  ({', '.join(params) or 'no parameters'})")
    if docs:
        print(f"Interactive docs: http://{shown}:{port}/docs")
    print("Press Ctrl+C to stop.\n")


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

            args = _get_args(evaluator.function_params.get(fn_name, []), path_arg, query_params)

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


def serve_script(script_path: str, host: str = "127.0.0.1", port: Optional[int] = None,
                 postman: bool = False):
    """Serve each endpoint of an MCN service file over HTTP (GET and POST).

    The port defaults to the service's own `port` line, then 8080.
    """
    if not os.path.exists(script_path):
        print(f"Error: file not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    port = port or declared_port(script_path) or 8080
    try:
        if HAS_FASTAPI:
            server = MCNServer()
            server.load_script(script_path)
            server.serve(host, port, auto_postman=postman)
            return
        ev = _load_evaluator(script_path)
    except Exception as exc:   # the interpreter's message already shows line, caret and hint
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if not ev.function_params:
        print("Warning: no service endpoints found — serving raw functions only")

    handler = _make_handler(ev)
    server  = HTTPServer((host, port), handler)
    _print_routes(ev, host, port, docs=False)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


def serve_directory(directory: str, host: str = "127.0.0.1", port: int = 8080, postman: bool = False):
    """Serve all .mcn files in a directory (loads each, merges endpoints)."""
    if HAS_FASTAPI:
        server = MCNServer()
        for filename in os.listdir(directory):
            if filename.endswith(".mcn"):
                script_path = os.path.join(directory, filename)
                server.load_script(script_path)
        server.serve(host, port, auto_postman=postman)
        return

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

    print(f"\nMCN server running on http://{host}:{port}")
    print(f"Endpoints: {', '.join(all_params) or 'none'}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
