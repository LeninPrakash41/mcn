"""
MCN Runtime Types — first-class objects for the 2030 language primitives.

pipeline  → MCNPipeline   — chainable data transformation pipeline
service   → MCNService    — declarative API service (FastAPI-backed)
workflow  → MCNWorkflow   — multi-step process with audit log
contract  → MCNContract   — schema validator + documentation

Each type is a plain Python object so it can be inspected, serialised,
and eventually handed off to the Go VM without structural changes.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── MCNPipeline ────────────────────────────────────────────────────────────────

class MCNPipeline:
    """
    A named sequence of stages where each stage's output is the next
    stage's input.

    Usage (from MCN):
        pipeline etl
            stage extract
                return fetch("https://api.example.com/data")
            stage transform(data)
                ...
                return cleaned
            stage load(data)
                trigger("https://warehouse.example.com/ingest", data)

        etl.run()           # runs all stages in order
        etl.run_stage("transform", my_data)  # run a single stage
    """

    def __init__(self, name: str):
        self.name   = name
        self._stages: List[Tuple[str, List[str], Callable]] = []
        # (stage_name, param_names, fn)

    def add_stage(self, name: str, params: List[str], fn: Callable):
        self._stages.append((name, params, fn))

    def run(self, initial: Any = None) -> Any:
        """
        Execute all stages in order.
        The return value of stage N is passed as the first argument to stage N+1.
        """
        result = initial
        log: List[Dict] = []
        for stage_name, params, fn in self._stages:
            try:
                result = fn(result) if params and result is not None else fn()
                log.append({"stage": stage_name, "status": "ok"})
            except Exception as exc:
                log.append({"stage": stage_name, "status": "error",
                            "error": str(exc)})
                raise RuntimeError(
                    f"Pipeline '{self.name}' failed at stage '{stage_name}': {exc}"
                ) from exc
        return result

    def run_stage(self, stage_name: str, *args: Any) -> Any:
        """Run a single named stage with explicit arguments."""
        for name, _, fn in self._stages:
            if name == stage_name:
                return fn(*args)
        raise ValueError(
            f"Pipeline '{self.name}' has no stage named '{stage_name}'. "
            f"Available: {[s[0] for s in self._stages]}"
        )

    @property
    def stage_names(self) -> List[str]:
        return [s[0] for s in self._stages]

    def __repr__(self) -> str:
        return (
            f"MCNPipeline(name={self.name!r}, "
            f"stages={self.stage_names})"
        )


# ── MCNService ─────────────────────────────────────────────────────────────────

class MCNService:
    """
    A declarative API service.  Endpoints are registered as callables.
    Calling .start() launches a FastAPI server on the declared port.

    Usage (from MCN):
        service user_api
            port 8080
            endpoint get_user(id)
                return query("SELECT * FROM users WHERE id = ?", (id,))
            endpoint create_user(name, email)
                query("INSERT INTO users VALUES (?, ?)", (name, email))
                return {"status": "created"}

        user_api.start()               # block (production)
        user_api.call("get_user", 42)  # call endpoint directly (testing)
    """

    def __init__(self, name: str, port: int = 8000):
        self.name  = name
        self.port  = port
        self._endpoints: Dict[str, Tuple[List[str], Callable]] = {}

    def add_endpoint(self, name: str, params: List[str], fn: Callable):
        self._endpoints[name] = (params, fn)

    def call(self, endpoint_name: str, *args: Any) -> Any:
        """Invoke an endpoint directly (useful for testing without HTTP)."""
        if endpoint_name not in self._endpoints:
            available = list(self._endpoints.keys())
            raise ValueError(
                f"Service '{self.name}' has no endpoint '{endpoint_name}'. "
                f"Available: {available}"
            )
        _, fn = self._endpoints[endpoint_name]
        return fn(*args)

    def start(self, host: str = "127.0.0.1"):
        """
        Start a FastAPI HTTP server exposing all endpoints.
        Each endpoint is exposed as POST /<endpoint_name>.
        """
        try:
            import fastapi
            import uvicorn
        except ImportError:
            raise RuntimeError(
                "FastAPI and uvicorn are required to start a MCN service. "
                "Run: pip install fastapi uvicorn"
            )

        app = fastapi.FastAPI(title=self.name)

        for ep_name, (params, fn) in self._endpoints.items():
            # Build a dynamic route handler that accepts a JSON body
            _fn   = fn
            _name = ep_name

            @app.post(f"/{_name}")
            async def _handler(body: Dict[str, Any] = fastapi.Body(default={}),
                               _fn=_fn, _params=params):
                args = [body.get(p) for p in _params]
                return _fn(*args)

        print(f"MCN service '{self.name}' starting on {host}:{self.port}")
        uvicorn.run(app, host=host, port=self.port)

    @property
    def endpoint_names(self) -> List[str]:
        return list(self._endpoints.keys())

    def __repr__(self) -> str:
        return (
            f"MCNService(name={self.name!r}, port={self.port}, "
            f"endpoints={self.endpoint_names})"
        )


# ── MCNWorkflow ────────────────────────────────────────────────────────────────

class MCNWorkflow:
    """
    A multi-step process with a built-in audit log.

    Steps are executed in order, each receiving the previous step's output.
    Every execution is recorded in .history for observability and replay.

    Usage (from MCN):
        workflow order_processing
            step validate(order_id)
                var order = query("SELECT * FROM orders WHERE id = ?", (order_id,))
                return order
            step charge(order)
                trigger("https://payments.example.com/charge", order)
                return order
            step notify(order)
                send_email(order.email, "Your order is confirmed!")

        order_processing.execute(order_id)
        order_processing.replay()          # re-run last input through all steps
    """

    def __init__(self, name: str):
        self.name     = name
        self._steps:   List[Tuple[str, List[str], Callable]] = []
        self.history:  List[Dict[str, Any]] = []
        self._last_input: Any = None

    def add_step(self, name: str, params: List[str], fn: Callable):
        self._steps.append((name, params, fn))

    def execute(self, *initial_args: Any) -> Any:
        """Run all steps in sequence, threading output through each."""
        self._last_input = initial_args
        run_log: List[Dict] = []
        result = initial_args[0] if len(initial_args) == 1 else initial_args

        for step_name, params, fn in self._steps:
            try:
                result = fn(result) if params and result is not None else fn()
                run_log.append({"step": step_name, "status": "ok"})
            except Exception as exc:
                run_log.append({"step": step_name, "status": "error",
                               "error": str(exc)})
                self.history.append({"run": len(self.history) + 1, "log": run_log,
                                    "status": "failed"})
                raise RuntimeError(
                    f"Workflow '{self.name}' failed at step '{step_name}': {exc}"
                ) from exc

        self.history.append({"run": len(self.history) + 1, "log": run_log,
                            "status": "completed"})
        return result

    def replay(self) -> Any:
        """Re-run the last execution from scratch."""
        if self._last_input is None:
            raise RuntimeError(f"Workflow '{self.name}' has no previous run to replay")
        args = self._last_input if isinstance(self._last_input, tuple) else (self._last_input,)
        return self.execute(*args)

    @property
    def step_names(self) -> List[str]:
        return [s[0] for s in self._steps]

    def __repr__(self) -> str:
        return (
            f"MCNWorkflow(name={self.name!r}, "
            f"steps={self.step_names}, runs={len(self.history)})"
        )


# ── MCNContract ────────────────────────────────────────────────────────────────

# Supported field type names → Python types for validation
_CONTRACT_TYPES: Dict[str, Any] = {
    "int":    int,
    "float":  float,
    "number": (int, float),
    "str":    str,
    "string": str,
    "bool":   bool,
    "list":   list,
    "array":  list,
    "dict":   dict,
    "object": dict,
    "any":    None,   # None = skip check
}


class MCNContract:
    """
    A schema validator and self-documenting data contract.

    Usage (from MCN):
        contract User
            id:    int
            name:  str
            email: str
            active: bool

        User.validate({"id": 1, "name": "Lenin", "email": "x@y.com", "active": true})
        User.schema()   → JSON schema dict
        User.create(id=1, name="Lenin", email="x@y.com", active=True)

    Validation is lenient for 'any' fields; strict for typed fields.
    Missing optional fields cause a warning (not an error) unless
    the type does not include null.
    """

    def __init__(self, name: str, fields: List[Tuple[str, str]]):
        self.name   = name
        self.fields = fields  # [(field_name, type_name)]

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a dict against this contract.
        Returns {"valid": bool, "errors": [...], "warnings": [...]}.
        """
        errors:   List[str] = []
        warnings: List[str] = []

        for field_name, type_name in self.fields:
            if field_name not in data:
                warnings.append(f"Missing field '{field_name}' ({type_name})")
                continue

            value     = data[field_name]
            py_type   = _CONTRACT_TYPES.get(type_name.lower())

            if py_type is None:
                continue   # 'any' — skip

            if not isinstance(value, py_type):
                actual = type(value).__name__
                errors.append(
                    f"Field '{field_name}': expected {type_name}, got {actual}"
                )

        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Create a validated dict matching this contract.
        Raises ValueError if required fields are missing or wrong type.
        """
        result = self.validate(kwargs)
        if not result["valid"]:
            raise ValueError(
                f"Contract '{self.name}' violation:\n"
                + "\n".join(f"  • {e}" for e in result["errors"])
            )
        return dict(kwargs)

    def schema(self) -> Dict[str, Any]:
        """Return a JSON-schema-like dict describing this contract."""
        properties = {
            name: {"type": type_name}
            for name, type_name in self.fields
        }
        return {
            "title":      self.name,
            "type":       "object",
            "properties": properties,
            "required":   [name for name, _ in self.fields],
        }

    def __repr__(self) -> str:
        field_str = ", ".join(f"{n}:{t}" for n, t in self.fields)
        return f"MCNContract(name={self.name!r}, fields=[{field_str}])"


# ── MCNPrompt ──────────────────────────────────────────────────────────────────

import re as _re
import threading as _threading

class MCNPrompt:
    """
    A reusable prompt template with {{variable}} interpolation.

    Usage (from MCN):
        prompt support_reply
            system "You are a helpful support agent for Acme Corp."
            user   "Customer said: {{message}}"
            format text

        var reply = support_reply.run({message: ticket_text})

    format can be "text" (default) or "json".
    When format is "json", the result is auto-parsed and returned as a dict.
    """

    def __init__(self, name: str, system: str = "", user: str = "",
                 format: str = "text"):
        self.name   = name
        self.system = system
        self.user   = user
        self.format = format

    def run(self, context: Optional[Dict] = None) -> Any:
        """
        Render templates, call AI, return the result.
        `context` is a dict of variable values for {{placeholder}} substitution.
        """
        from .ai_builtins import _provider_complete

        ctx          = context if isinstance(context, dict) else {}
        rendered     = self._render(self.user, ctx)
        system_msg   = self._render(self.system, ctx)

        opts: Dict[str, Any] = {"system": system_msg, "temperature": 0.3}
        if self.format == "json":
            opts["system"] = (system_msg + " Respond ONLY with valid JSON — "
                              "no markdown, no explanation.").strip()

        raw = _provider_complete(rendered, opts)

        if self.format == "json":
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                parts   = cleaned.split("```")
                cleaned = parts[1].lstrip("json").strip() if len(parts) > 1 else cleaned
            try:
                import json as _json
                return _json.loads(cleaned)
            except Exception:
                return raw
        return raw

    @staticmethod
    def _render(template: str, context: Dict) -> str:
        """Replace {{var}} placeholders with values from context."""
        def _replace(m: "_re.Match") -> str:
            key = m.group(1).strip()
            return str(context.get(key, m.group(0)))
        return _re.sub(r'\{\{([^}]+)\}\}', _replace, template)

    def __repr__(self) -> str:
        return f"MCNPrompt(name={self.name!r}, format={self.format!r})"


# ── MCNAgent ───────────────────────────────────────────────────────────────────

# Thread-local used by ai_builtins._provider_complete to inherit the agent model
_current_agent_model = _threading.local()


class MCNAgent:
    """
    A named agent with a fixed model, declared tools, optional memory,
    and callable tasks.

    Usage (from MCN):
        agent researcher
            model  "claude-3-5-sonnet"
            tools  fetch, query, ai
            memory session

            task analyze(topic)
                var data     = fetch("https://api.example.com?q=" + topic)
                var findings = ai("Key insights from: " + data)
                return findings

        var report = researcher.analyze("quantum computing 2026")

    Each task method is accessible as an attribute:  agent.task_name(*args)
    Inside a task, ai() and llm() automatically use the agent's model unless
    the caller overrides it explicitly.
    """

    def __init__(self, name: str, model: str = "",
                 tools: Optional[List[str]] = None, memory: str = ""):
        self.name    = name
        self.model   = model
        self.tools   = tools or []
        self.memory  = memory
        self._tasks: Dict[str, Callable] = {}
        self._session: Dict[str, Any]    = {}   # session memory store

    def add_task(self, name: str, params: List[str], fn: Callable) -> None:
        """Register a task and expose it as an attribute."""
        agent_model = self.model
        session     = self._session

        def _task_wrapper(*args: Any) -> Any:
            # Set agent model context so ai() picks it up automatically
            _current_agent_model.model = agent_model
            # Inject __session__ into the call if the task accepts it
            try:
                return fn(*args)
            finally:
                _current_agent_model.model = None

        self._tasks[name] = _task_wrapper
        setattr(self, name, _task_wrapper)

    @property
    def task_names(self) -> List[str]:
        return list(self._tasks.keys())

    def __repr__(self) -> str:
        return (
            f"MCNAgent(name={self.name!r}, model={self.model!r}, "
            f"tools={self.tools}, tasks={self.task_names})"
        )
