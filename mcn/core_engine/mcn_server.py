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
from typing import Any, Dict, List, Optional, Tuple
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


def _guard(evaluator: Evaluator, fn_name: str, authorization: Optional[str], client: str,
           body_length: int = 0) -> Optional[Tuple[int, str]]:
    """Checks before an endpoint runs. Returns (status, error) to refuse, or None to allow.

    Only declared endpoints are reachable — never built-ins like query() or
    write_file(). Endpoints of an `auth` service need a valid bearer token.
    """
    from . import security
    if fn_name not in evaluator.function_params:
        return 404, f"Unknown endpoint: '{fn_name}'"
    limit = security.server_rate_limit()
    if limit and not security.SERVER_LIMITER.allow(client, limit, 60):
        return 429, "Too many requests. Try again in a minute."
    if body_length > security.max_body_bytes():
        return 413, "Request body is too large"
    ok, user, error = security.check_auth(evaluator.endpoint_auth.get(fn_name, ""), authorization)
    if not ok:
        return 401, error
    security.set_current_user(user)
    return None


def _dev_iot(method: str, path: str, body: Dict[str, Any], authorization: Optional[str]) -> Optional[Tuple[int, Any]]:
    """Studio's IoT panel driving the devices of a backend it started.

    Only exists when Studio sets MCN_DEV_TOOLS=1, and needs Studio's token.
    Returns None for paths that aren't these routes.
    """
    if not path.startswith("/_mcn/iot/"):
        return None
    from . import security
    from .iot import shared_registry
    if os.getenv("MCN_DEV_TOOLS") != "1":
        return 404, {"error": "Not found"}
    ok, _, error = security.check_auth("token", authorization)
    if not ok:
        return 401, {"error": error}
    reg, action = shared_registry(), path[len("/_mcn/iot/"):]
    try:
        if action == "devices" and method == "GET":
            return 200, {"success": True, "devices": reg.snapshot()}
        if action == "commands" and method == "GET":
            return 200, {"success": True, "commands": list(reg.command_log)}
        if action == "value" and method == "POST":
            return 200, {"success": True, "value": reg.write(str(body.get("device_id")), body.get("value"), source="simulator")}
        if action == "pin" and method == "POST":
            return 200, {"success": True, "value": reg.pin(str(body.get("device_id")), body.get("value"))}
    except Exception as exc:
        return 400, {"success": False, "error": str(exc)}
    return 404, {"error": "Not found"}


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

            # CORS: origins from MCN_CORS_ORIGINS (default any). Auth uses bearer
            # tokens, not cookies, so credentials stay off.
            from fastapi.middleware.cors import CORSMiddleware
            from . import security
            origins = [o.strip() for o in os.getenv("MCN_CORS_ORIGINS", "*").split(",") if o.strip()]
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=False,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
            )

            @self.app.middleware("http")
            async def security_headers(request: Request, call_next):
                response = await call_next(request)
                for key, value in security.SECURITY_HEADERS.items():
                    # The interactive docs page loads its own scripts and styles
                    if key == "Content-Security-Policy" and request.url.path in ("/docs", "/redoc", "/openapi.json"):
                        continue
                    response.headers.setdefault(key, value)
                return response

            @self.app.api_route("/_mcn/iot/{action}", methods=["GET", "POST"], include_in_schema=False)
            async def dev_iot(action: str, request: Request):
                body = {}
                if request.method == "POST":
                    try:
                        body = await request.json()
                    except Exception:
                        body = {}
                status, payload = _dev_iot(request.method, f"/_mcn/iot/{action}", body or {},
                                           request.headers.get("authorization"))
                return JSONResponse(payload, status_code=status)

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
                        print(f"Warning: can't schedule '{name}': scheduling isn't installed. Run: mcn add scheduler")
            
            if ev.function_params:
                return f"/{os.path.basename(script_path)}"

        # A file without a service has nothing to expose. (Running a whole script
        # per request and returning its variables would leak secrets.)
        print(f"Warning: {os.path.basename(script_path)} declares no service endpoints; nothing to serve.")
        return None

    def _register_fastapi_endpoint(self, fn_name: str, params: List[str], evaluator: Evaluator):
        def run(args):
            try:
                result = evaluator.functions[fn_name](*args)
                return JSONResponse(result if result is not None else {})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        def refused(request: Request, length: int = 0):
            client = request.client.host if request.client else "?"
            problem = _guard(evaluator, fn_name, request.headers.get("authorization"), client, length)
            return JSONResponse({"error": problem[1]}, status_code=problem[0]) if problem else None

        async def post_endpoint(request: Request):
            blocked = refused(request, int(request.headers.get("content-length") or 0))
            if blocked:
                return blocked
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
            blocked = refused(request)
            if blocked:
                return blocked
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

        def _cors(self):
            from . import security
            self.send_header("Access-Control-Allow-Origin", security.cors_origin(self.headers.get("Origin")))
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def _send_json(self, status: int, obj: Any):
            from . import security
            body = json.dumps(obj, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type",  "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            for key, value in security.SECURITY_HEADERS.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def _refused(self, fn_name: str, length: int = 0) -> bool:
            problem = _guard(evaluator, fn_name, self.headers.get("Authorization"), self.client_address[0], length)
            if problem:
                self._send_json(problem[0], {"error": problem[1]})
            return bool(problem)

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

        def _dev(self, method: str, body: Dict[str, Any]) -> bool:
            handled = _dev_iot(method, urllib.parse.urlparse(self.path).path, body, self.headers.get("Authorization"))
            if handled:
                self._send_json(*handled)
            return bool(handled)

        def do_GET(self):
            if self._dev("GET", {}):
                return
            fn_name, path_arg, query_params = self._resolve_endpoint(self.path)

            if not fn_name:
                # Health / route list
                routes = [
                    {"name": k, "params": v, "methods": ["GET", "POST"], "auth": evaluator.endpoint_auth.get(k) or None}
                    for k, v in evaluator.function_params.items()
                ]
                self._send_json(200, {"status": "ok", "version": "MCN/2.0", "endpoints": routes})
                return

            if self._refused(fn_name):
                return

            args = _get_args(evaluator.function_params.get(fn_name, []), path_arg, query_params)

            try:
                result = evaluator.functions[fn_name](*args)
                self._send_json(200, result if result is not None else {})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})

        def do_POST(self):
            fn_name, path_arg, _ = self._resolve_endpoint(self.path)
            length = int(self.headers.get("Content-Length", 0) or 0)
            if self.path.startswith("/_mcn/iot/"):
                try:
                    data = json.loads(self.rfile.read(min(length, 65536)) or b"{}") if length else {}
                except json.JSONDecodeError:
                    data = {}
                self._dev("POST", data if isinstance(data, dict) else {})
                return
            if self._refused(fn_name, length):
                return

            # Read JSON body (optional)
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
        print("Warning: no service endpoints found; add a `service` block to expose functions.")

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
    all_auth:    Dict[str, str]        = {}

    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".mcn"):
            continue
        path = os.path.join(directory, fname)
        try:
            ev = _load_evaluator(path)
            all_fns.update(ev.functions)
            all_params.update(ev.function_params)
            all_auth.update(ev.endpoint_auth)
            print(f"  loaded  {fname}  ({len(ev.function_params)} endpoints)")
        except Exception as exc:
            print(f"  error   {fname}: {exc}")

    # Build a stub evaluator shell to pass to handler
    class _Stub:
        functions      = all_fns
        function_params = all_params
        endpoint_auth   = all_auth

    handler = _make_handler(_Stub())  # type: ignore[arg-type]
    server  = HTTPServer((host, port), handler)

    print(f"\nMCN server running on http://{host}:{port}")
    print(f"Endpoints: {', '.join(all_params) or 'none'}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
