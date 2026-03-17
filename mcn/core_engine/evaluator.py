"""
MCN Evaluator — tree-walking interpreter over the typed AST.

Key improvements over v1:
  - Proper lexical scoping via Environment chain (closures work correctly)
  - ReturnSignal is an internal detail, not visible outside a function call
  - MCNError carries line + col for precise runtime error messages
  - Division-by-zero is caught explicitly
  - for-loop variable is scoped to the loop (doesn't pollute outer scope)
  - Functions are first-class values stored in the environment

Separation of concerns:
  This module knows nothing about tokenisation or parsing.
  It only walks ast_nodes.Node subclasses.
  Future backends (bytecode VM, Go runtime) replace this file alone.
"""
from __future__ import annotations

import re as _re
from typing import Any, Callable, Dict, List, Optional

from . import ast_nodes as ast


# ── Signals ────────────────────────────────────────────────────────────────────

class ReturnSignal(Exception):
    """Internal control-flow signal for 'return' statements.
    Never escapes a function call frame."""
    def __init__(self, value: Any):
        self.value = value

class BreakSignal(Exception):
    """Internal control-flow signal for 'break' in loops."""

class ContinueSignal(Exception):
    """Internal control-flow signal for 'continue' in loops."""


# ── Errors ─────────────────────────────────────────────────────────────────────

class MCNError(Exception):
    """Runtime error with optional source location."""
    def __init__(self, message: str, line: int = 0, col: int = 0):
        loc = f"[{line}:{col}] " if line else ""
        super().__init__(f"{loc}RuntimeError: {message}")
        self.line = line
        self.col  = col


# ── Lexical environment ────────────────────────────────────────────────────────

_UNDEFINED = object()          # sentinel — distinct from None


class Environment:
    """
    A single scope in the environment chain.

    Variables are looked up by walking the parent chain, just like
    Python's LEGB rule. This gives MCN:
      - Function-local variables that don't leak to the caller
      - True closure capture (the lambda in _exec_function_decl captures `env`)
      - Loop variables scoped to the loop body
    """

    def __init__(self, parent: Optional["Environment"] = None):
        self._vars:   Dict[str, Any]    = {}
        self._parent: Optional[Environment] = parent

    # ── Read ───────────────────────────────────────────────────────────────────

    def get(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self._parent is not None:
            return self._parent.get(name)
        return _UNDEFINED

    # ── Write (always to the innermost scope) ──────────────────────────────────

    def define(self, name: str, value: Any):
        """Create or overwrite a binding in *this* scope."""
        self._vars[name] = value

    def assign(self, name: str, value: Any):
        """
        Update an *existing* binding, walking up the chain.
        Falls back to defining in the current scope if not found.
        """
        if name in self._vars:
            self._vars[name] = value
            return
        if self._parent is not None:
            self._parent.assign(name, value)
        else:
            self._vars[name] = value    # global fallback

    # ── Introspection (for error messages) ─────────────────────────────────────

    def all_names(self) -> List[str]:
        names = list(self._vars.keys())
        if self._parent is not None:
            names += self._parent.all_names()
        return names

    # ── Backward-compat dict-like access (used by MCNInterpreter.variables) ────

    @property
    def as_dict(self) -> Dict[str, Any]:
        return self._vars


# ── Evaluator ──────────────────────────────────────────────────────────────────

class Evaluator:
    """
    Tree-walking evaluator.

    Usage:
        ev = Evaluator(builtin_functions)
        ev.execute_program(parsed_ast)

    `builtin_functions` is a dict mapping name → Python callable.
    User-defined functions are added to this dict as they are declared,
    so they are also available for recursion and cross-function calls.
    """

    def __init__(self, functions: Dict[str, Callable]):
        self.functions       = functions         # shared with MCNInterpreter
        self.function_params: Dict[str, List[str]] = {}   # param names per endpoint
        self.globals    = Environment()
        self.components: Dict[str, ast.ComponentDecl] = {}   # UI components registry
        self.app_decl:   Optional[ast.AppDecl]        = None  # app declaration

        # Boolean and null literals (JavaScript / JSON style)
        self.globals.define("true",  True)
        self.globals.define("false", False)
        self.globals.define("null",  None)

        # Seed the global environment with request context
        self.globals.define("request_data", {
            "method": "GET", "params": {}, "headers": {}, "body": None,
        })

    # ── Compat shim used by legacy code ────────────────────────────────────────

    @property
    def variables(self) -> Dict[str, Any]:
        """Backward-compatible flat view of the global scope."""
        return self.globals.as_dict

    # ── Program entry point ────────────────────────────────────────────────────

    def execute_program(self, program: ast.Program) -> Any:
        return self._exec_block(program.body, self.globals)

    # ── Statement execution ────────────────────────────────────────────────────

    def _exec_block(self, stmts: List[ast.Stmt], env: Environment) -> Any:
        result = None
        for stmt in stmts:
            result = self._exec_stmt(stmt, env)
        return result

    def _exec_stmt(self, stmt: ast.Stmt, env: Environment) -> Any:  # noqa: C901
        # ── var declaration ────────────────────────────────────────────────────
        if isinstance(stmt, ast.VarDecl):
            value = self._eval(stmt.value, env)
            env.define(stmt.name, value)
            return value

        # ── bare assignment (name = expr) ─────────────────────────────────────
        if isinstance(stmt, ast.AssignStmt):
            value = self._eval(stmt.value, env)
            env.assign(stmt.name, value)
            return value

        # ── compound assignment (name OP= expr) ────────────────────────────────
        if isinstance(stmt, ast.CompoundAssignStmt):
            current = env.get(stmt.name)
            delta   = self._eval(stmt.value, env)
            value   = self._apply_binary(stmt.op, current, delta, stmt.line, stmt.col)
            env.assign(stmt.name, value)
            return value

        # ── property assignment (obj.key = expr) ──────────────────────────────
        if isinstance(stmt, ast.PropertyAssignStmt):
            obj = self._eval(stmt.object, env)
            val = self._eval(stmt.value, env)
            if isinstance(obj, dict):
                obj[stmt.prop] = val
            elif hasattr(obj, stmt.prop):
                setattr(obj, stmt.prop, val)
            else:
                raise MCNError(
                    f"Cannot set property '{stmt.prop}' on {type(obj).__name__}",
                    stmt.line, stmt.col)
            return val

        # ── index assignment (arr[i] = expr  or  dict[key] = expr) ────────────
        if isinstance(stmt, ast.IndexAssignStmt):
            obj = self._eval(stmt.object, env)
            idx = self._eval(stmt.index, env)
            val = self._eval(stmt.value, env)
            if isinstance(obj, (list, dict)):
                obj[idx] = val
            else:
                raise MCNError(
                    f"Cannot index-assign on {type(obj).__name__}",
                    stmt.line, stmt.col)
            return val

        # ── if / else ─────────────────────────────────────────────────────────
        if isinstance(stmt, ast.IfStmt):
            cond = self._eval(stmt.condition, env)
            if self._truthy(cond):
                return self._exec_block(stmt.then_body, env)
            if stmt.else_body:
                return self._exec_block(stmt.else_body, env)
            return None

        # ── for loop ──────────────────────────────────────────────────────────
        if isinstance(stmt, ast.ForStmt):
            iterable = self._eval(stmt.iterable, env)
            if isinstance(iterable, dict):
                iterable = list(iterable.items())   # dict → [(k,v), ...]
            if not isinstance(iterable, (list, tuple)):
                raise MCNError(
                    f"Cannot iterate over {type(iterable).__name__}",
                    stmt.line, stmt.col,
                )
            for idx, item in enumerate(iterable):
                loop_env = Environment(env)
                loop_env.define(stmt.variable, item)
                if stmt.index_var:
                    loop_env.define(stmt.index_var, idx)
                try:
                    self._exec_block(stmt.body, loop_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return None

        # ── while loop ────────────────────────────────────────────────────────
        if isinstance(stmt, ast.WhileStmt):
            max_iters = 100_000
            count = 0
            while self._truthy(self._eval(stmt.condition, env)):
                count += 1
                if count > max_iters:
                    raise MCNError(
                        f"Maximum loop iterations ({max_iters}) exceeded",
                        stmt.line, stmt.col,
                    )
                try:
                    self._exec_block(stmt.body, env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return None

        # ── try / catch ───────────────────────────────────────────────────────
        if isinstance(stmt, ast.TryStmt):
            result = None
            try:
                result = self._exec_block(stmt.try_body, env)
            except ReturnSignal:
                raise                         # never swallow return signals
            except (BreakSignal, ContinueSignal):
                raise                         # never swallow loop signals
            except Exception as exc:
                if stmt.catch_body:
                    catch_env = Environment(env)
                    # Named catch var:  catch e  →  e.message, e.type, e.raw
                    var = stmt.catch_var or "error"
                    err_obj = {
                        "message": str(exc),
                        "type":    type(exc).__name__,
                        "raw":     exc,
                    }
                    catch_env.define(var, err_obj)
                    catch_env.define("error", str(exc))  # legacy compat
                    result = self._exec_block(stmt.catch_body, catch_env)
                else:
                    raise
            finally:
                if stmt.finally_body:
                    self._exec_block(stmt.finally_body, env)
            return result

        # ── throw ─────────────────────────────────────────────────────────────
        if isinstance(stmt, ast.ThrowStmt):
            message = self._eval(stmt.message, env)
            raise MCNError(str(message), stmt.line, stmt.col)

        # ── task ──────────────────────────────────────────────────────────────
        if isinstance(stmt, ast.TaskStmt):
            name      = str(self._eval(stmt.name, env))
            func_name = str(self._eval(stmt.function, env))
            args      = [self._eval(a, env) for a in stmt.arguments]
            if "task" in self.functions:
                return self.functions["task"](name, func_name, *args)
            raise MCNError("Task system not initialised", stmt.line, stmt.col)

        # ── use (package import) ───────────────────────────────────────────────
        if isinstance(stmt, ast.UseStmt):
            package_name = str(self._eval(stmt.package, env))
            if "use" in self.functions:
                return self.functions["use"](package_name)
            raise MCNError("Package system not initialised", stmt.line, stmt.col)

        # ── function declaration ───────────────────────────────────────────────
        if isinstance(stmt, ast.FunctionDecl):
            self._exec_function_decl(stmt, env)
            return None

        # ── return ────────────────────────────────────────────────────────────
        if isinstance(stmt, ast.ReturnStmt):
            value = self._eval(stmt.value, env) if stmt.value is not None else None
            raise ReturnSignal(value)

        # ── expression statement ───────────────────────────────────────────────
        if isinstance(stmt, ast.ExprStmt):
            return self._eval(stmt.expression, env)

        # ── 2030 language primitives ───────────────────────────────────────────
        if isinstance(stmt, ast.PipelineDecl):
            return self._exec_pipeline_decl(stmt, env)

        if isinstance(stmt, ast.ServiceDecl):
            return self._exec_service_decl(stmt, env)

        if isinstance(stmt, ast.WorkflowDecl):
            return self._exec_workflow_decl(stmt, env)

        if isinstance(stmt, ast.ContractDecl):
            return self._exec_contract_decl(stmt, env)

        # ── break / continue ──────────────────────────────────────────────────
        if isinstance(stmt, ast.BreakStmt):
            raise BreakSignal()

        if isinstance(stmt, ast.ContinueStmt):
            raise ContinueSignal()

        # ── assert ────────────────────────────────────────────────────────────
        if isinstance(stmt, ast.AssertStmt):
            result = self._eval(stmt.condition, env)
            if not self._truthy(result):
                msg = (self._eval(stmt.message, env)
                       if stmt.message is not None else "assertion failed")
                raise MCNError(str(msg), stmt.line, stmt.col)
            return True

        # ── test (no-op during normal execution; executed by mcn test runner) ─
        if isinstance(stmt, ast.TestDecl):
            return None

        # AI / intelligent primitives
        if isinstance(stmt, ast.PromptDecl):
            return self._exec_prompt_decl(stmt, env)

        if isinstance(stmt, ast.AgentDecl):
            return self._exec_agent_decl(stmt, env)

        # ── UI / Frontend primitives (registered for mcn build; no-op at runtime) ─
        if isinstance(stmt, ast.ComponentDecl):
            self.components[stmt.name] = stmt
            return None

        if isinstance(stmt, ast.AppDecl):
            self.app_decl = stmt
            return None

        if isinstance(stmt, ast.IncludeStmt):
            return self._exec_include(stmt)

        raise MCNError(f"Unknown statement type: {type(stmt).__name__}")

    def _exec_include(self, stmt: ast.IncludeStmt):
        """Load and execute an included MCN file, merging its components/functions."""
        import os
        from .lexer  import Lexer
        from .parser import Parser
        # Resolve path relative to cwd (caller sets cwd before evaluation)
        path = os.path.abspath(stmt.path)
        if not os.path.exists(path):
            raise MCNError(f"include: file not found: {path}")
        code    = open(path, encoding="utf-8").read()
        tokens  = Lexer(code).tokenize()
        program = Parser(tokens).parse()
        self.execute_program(program)   # merges into self.components, self.functions, etc.
        return None

    def _exec_function_decl(self, stmt: ast.FunctionDecl, env: Environment):
        """
        Bind the function name to a Python callable that:
          1. Creates a new scope whose parent is the *defining* environment
             (lexical / closure semantics).
          2. Binds parameters.
          3. Executes the body, catching ReturnSignal.
        """
        captured_env = env
        params       = stmt.params
        defaults     = stmt.defaults     # dict of param_name → default Expr
        body         = stmt.body
        name         = stmt.name

        def user_func(*args: Any) -> Any:
            call_env = Environment(captured_env)
            for i, param in enumerate(params):
                if i < len(args):
                    call_env.define(param, args[i])
                elif param in defaults:
                    # Evaluate the default in the defining scope (lexical)
                    call_env.define(param, self._eval(defaults[param], captured_env))
                else:
                    call_env.define(param, None)
            try:
                return self._exec_block(body, call_env)
            except ReturnSignal as ret:
                return ret.value

        # Register in both the environment and the shared functions dict
        # so the function is callable by name from anywhere.
        env.define(name, user_func)
        self.functions[name] = user_func

    # ── Expression evaluation ──────────────────────────────────────────────────

    def _eval(self, expr: ast.Expr, env: Environment) -> Any:  # noqa: C901
        if isinstance(expr, ast.Literal):
            # String interpolation: "Hello {name}, score is {score}"
            # Supports identifiers only: {var_name} — use + concat for expressions
            if isinstance(expr.value, str) and "{" in expr.value:
                return self._interpolate(expr.value, env)
            return expr.value

        if isinstance(expr, ast.Variable):
            # Check environment first, then the shared functions dict
            val = env.get(expr.name)
            if val is not _UNDEFINED:
                return val
            if expr.name in self.functions:
                return self.functions[expr.name]
            # Helpful "did you mean?" hint
            similar = [
                k for k in env.all_names()
                if k.lower().startswith(expr.name[:2].lower())
            ]
            hint = f" Did you mean: {', '.join(similar[:3])}?" if similar else ""
            raise MCNError(
                f"Undefined variable: '{expr.name}'.{hint}",
                expr.line, expr.col,
            )

        if isinstance(expr, ast.TernaryExpr):
            cond = self._eval(expr.condition, env)
            return self._eval(expr.then_expr if self._truthy(cond) else expr.else_expr, env)

        if isinstance(expr, ast.ArrowFunc):
            # Capture the current environment (closure)
            captured_env  = env
            params        = expr.params
            body_expr     = expr.body
            evaluator_ref = self

            def arrow_fn(*args: Any) -> Any:
                fn_env = Environment(captured_env)
                for i, p in enumerate(params):
                    fn_env.define(p, args[i] if i < len(args) else None)
                return evaluator_ref._eval(body_expr, fn_env)

            arrow_fn.__name__ = f"<arrow({', '.join(params)})>"
            return arrow_fn

        if isinstance(expr, ast.Binary):
            left  = self._eval(expr.left,  env)
            right = self._eval(expr.right, env)
            return self._apply_binary(expr.operator, left, right,
                                      expr.line, expr.col)

        if isinstance(expr, ast.Unary):
            operand = self._eval(expr.operand, env)
            if expr.operator == "-":
                return -operand
            if expr.operator == "not":
                return not self._truthy(operand)

        if isinstance(expr, ast.Array):
            return [self._eval(e, env) for e in expr.elements]

        if isinstance(expr, ast.MCNTuple):
            return tuple(self._eval(e, env) for e in expr.elements)

        if isinstance(expr, ast.MCNObject):
            obj: Dict[str, Any] = {}
            for key_expr, val_expr in expr.properties:
                # Object literal keys: bare identifiers are string keys (JSON style),
                # not variable lookups.  {name: value}  →  {"name": value}
                if isinstance(key_expr, ast.Variable):
                    k = key_expr.name
                else:
                    k = str(self._eval(key_expr, env))
                v = self._eval(val_expr, env)
                obj[k] = v
            return obj

        if isinstance(expr, ast.Index):
            obj   = self._eval(expr.object, env)
            index = self._eval(expr.index, env)
            if isinstance(obj, (list, tuple)) and isinstance(index, int):
                return obj[index] if 0 <= index < len(obj) else None
            if isinstance(obj, dict):
                return obj.get(str(index))
            return None

        if isinstance(expr, ast.Property):
            obj = self._eval(expr.object, env)
            # obj?.name — return None if object is None (null-safe)
            if obj is None:
                return None     # both safe and unsafe return None for None objects
            if isinstance(obj, dict):
                return obj.get(expr.name)
            if isinstance(obj, (list, tuple, str)) and expr.name == "length":
                return len(obj)
            # Allow attribute access on runtime objects (MCNPipeline, MCNService,
            # MCNWorkflow, MCNContract, MCNPrompt, MCNAgent) and any Python object
            if hasattr(obj, expr.name):
                return getattr(obj, expr.name)
            return None

        if isinstance(expr, ast.Call):
            return self._eval_call(expr, env)

        raise MCNError(f"Unknown expression type: {type(expr).__name__}")

    def _eval_call(self, expr: ast.Call, env: Environment) -> Any:
        callee = self._eval(expr.callee, env)
        args   = [self._eval(a, env) for a in expr.arguments]

        if callable(callee):
            try:
                return callee(*args)
            except (ReturnSignal, MCNError):
                raise
            except Exception as exc:
                name = getattr(expr.callee, "name", "?")
                raise MCNError(
                    f"Function '{name}' failed: {exc}",
                    expr.line, expr.col,
                ) from exc

        # Callee resolved to a string (legacy edge-case)
        if isinstance(callee, str) and callee in self.functions:
            return self.functions[callee](*args)

        name    = getattr(expr.callee, "name", str(callee))
        similar = [
            k for k in self.functions
            if k.lower().startswith(name[:2].lower())
        ]
        hint = f" Did you mean: {', '.join(similar[:3])}?" if similar else ""
        raise MCNError(
            f"Undefined function: '{name}'.{hint}",
            expr.line, expr.col,
        )

    # ── 2030 Language Primitive Handlers ──────────────────────────────────────

    def _exec_pipeline_decl(self, stmt: ast.PipelineDecl,
                            env: Environment) -> Any:
        """
        Build an MCNPipeline and bind it in the environment by name.
        Each stage becomes a closure that captures the current env.
        """
        from .runtime_types import MCNPipeline
        pipeline = MCNPipeline(stmt.name)

        for stage in stmt.stages:
            captured_env = env
            params   = stage.params
            defaults = {k: self._eval(v, env) for k, v in stage.defaults.items()}
            body     = stage.body

            def make_stage_fn(p, d, b, e):
                def stage_fn(*args: Any) -> Any:
                    call_env = Environment(e)
                    for i, param in enumerate(p):
                        call_env.define(param, args[i] if i < len(args) else d.get(param))
                    try:
                        return self._exec_block(b, call_env)
                    except ReturnSignal as ret:
                        return ret.value
                return stage_fn

            pipeline.add_stage(stage.name, params,
                               make_stage_fn(params, defaults, body, captured_env))

        env.define(stmt.name, pipeline)
        self.functions[stmt.name] = pipeline
        return pipeline

    def _exec_service_decl(self, stmt: ast.ServiceDecl,
                           env: Environment) -> Any:
        """
        Build an MCNService and bind it in the environment by name.
        Each endpoint becomes a closure.
        """
        from .runtime_types import MCNService
        service = MCNService(stmt.name, port=stmt.port or 8000)

        for ep in stmt.endpoints:
            captured_env = env
            params   = ep.params
            defaults = {k: self._eval(v, env) for k, v in ep.defaults.items()}
            body     = ep.body

            def make_endpoint_fn(p, d, b, e):
                def endpoint_fn(*args: Any) -> Any:
                    call_env = Environment(e)
                    for i, param in enumerate(p):
                        call_env.define(param, args[i] if i < len(args) else d.get(param))
                    try:
                        return self._exec_block(b, call_env)
                    except ReturnSignal as ret:
                        return ret.value
                return endpoint_fn

            fn = make_endpoint_fn(params, defaults, body, captured_env)
            service.add_endpoint(ep.name, params, fn)
            # Also expose each endpoint as a top-level function so tests and
            # scripts can call submit_claim(...) directly without the service prefix.
            env.define(ep.name, fn)
            self.functions[ep.name] = fn
            self.function_params[ep.name] = params

        env.define(stmt.name, service)
        self.functions[stmt.name] = service
        return service

    def _exec_workflow_decl(self, stmt: ast.WorkflowDecl,
                            env: Environment) -> Any:
        """
        Build an MCNWorkflow and bind it in the environment by name.
        Each step becomes a closure.
        """
        from .runtime_types import MCNWorkflow
        workflow = MCNWorkflow(stmt.name)

        for step in stmt.steps:
            captured_env = env
            params   = step.params
            defaults = {k: self._eval(v, env) for k, v in step.defaults.items()}
            body     = step.body

            def make_step_fn(p, d, b, e):
                def step_fn(*args: Any) -> Any:
                    call_env = Environment(e)
                    for i, param in enumerate(p):
                        call_env.define(param, args[i] if i < len(args) else d.get(param))
                    try:
                        return self._exec_block(b, call_env)
                    except ReturnSignal as ret:
                        return ret.value
                return step_fn

            workflow.add_step(step.name, params,
                              make_step_fn(params, defaults, body, captured_env))

        env.define(stmt.name, workflow)
        self.functions[stmt.name] = workflow
        return workflow

    def _exec_contract_decl(self, stmt: ast.ContractDecl,
                            env: Environment) -> Any:
        """
        Build an MCNContract and bind it in the environment by name.
        """
        from .runtime_types import MCNContract
        fields = [(f.name, f.type_name) for f in stmt.fields]
        contract = MCNContract(stmt.name, fields)
        env.define(stmt.name, contract)
        self.functions[stmt.name] = contract
        return contract

    # ── String interpolation ───────────────────────────────────────────────────

    # Matches {identifier}, {obj.prop}, {arr[0]}, {obj["key"]}, {arr[0].prop}, etc.
    _INTERP_RE = _re.compile(
        r'\{([a-zA-Z_][a-zA-Z0-9_]*'
        r'(?:'
        r'  \.[a-zA-Z_][a-zA-Z0-9_]*'    # .prop
        r'| \[\d+\]'                       # [0]
        r'| \["[^"]*"\]'                   # ["key"]'
        r"| \['[^']*'\]"                   # ['key']
        r')*'
        r')\}',
        _re.VERBOSE,
    )

    def _interpolate(self, s: str, env: Environment) -> str:
        """
        Replace {identifier} or {obj.prop.sub} or {arr[0]} or {obj["key"]}
        placeholders in a string with their values.

        "Hello {name}, you have {items[0]} and {items[1]}"
        "Path: {result.data[0].name}"

        Unknown identifiers are left as-is so JSON-like strings don't break.
        """
        # Tokenise an accessor expression like: name, arr[0], obj.prop["key"].x
        _STEP_RE = _re.compile(
            r'\.([a-zA-Z_][a-zA-Z0-9_]*)'   # .prop
            r'|\[(\d+)\]'                     # [int_index]
            r'|\["([^"]*)"\]'                 # ["str_key"]
            r"|\'([^']*)\']"                  # ['str_key']  (legacy compat)
        )

        def _resolve(expr: str) -> Any:
            # Split off the root identifier (everything before first . or [)
            m0 = _re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', expr)
            if not m0:
                return _UNDEFINED
            root = m0.group(1)
            val = env.get(root)
            if val is _UNDEFINED:
                if root in self.functions:
                    val = self.functions[root]
                else:
                    return _UNDEFINED

            rest = expr[m0.end():]
            for step in _STEP_RE.finditer(rest):
                if val is None or val is _UNDEFINED:
                    return _UNDEFINED
                prop, idx, skey1, skey2 = step.groups()
                if prop is not None:
                    # .prop  — handle .length specially
                    if prop == "length" and isinstance(val, (list, str)):
                        val = len(val)
                    elif isinstance(val, dict):
                        val = val.get(prop, _UNDEFINED)
                    elif hasattr(val, prop):
                        val = getattr(val, prop)
                    else:
                        return _UNDEFINED
                elif idx is not None:
                    # [integer_index]
                    i = int(idx)
                    if isinstance(val, (list, str)):
                        try:
                            val = val[i]
                        except IndexError:
                            return _UNDEFINED
                    elif isinstance(val, dict):
                        val = val.get(i, val.get(str(i), _UNDEFINED))
                    else:
                        return _UNDEFINED
                else:
                    # ["str_key"] or ['str_key']
                    key = skey1 if skey1 is not None else skey2
                    if isinstance(val, dict):
                        val = val.get(key, _UNDEFINED)
                    else:
                        return _UNDEFINED
            return val

        def _replace(m: "_re.Match") -> str:
            val = _resolve(m.group(1))
            if val is _UNDEFINED:
                return m.group(0)   # leave {expr} untouched
            return "" if val is None else str(val)

        return self._INTERP_RE.sub(_replace, s)

    def _exec_prompt_decl(self, stmt: ast.PromptDecl,
                          env: Environment) -> Any:
        """
        Build an MCNPrompt and bind it in the environment by name.

        prompt support_reply
            system "You are a helpful support agent."
            user   "Customer: {{message}}"
            format text

        Calling support_reply.run({message: "..."}) renders the template
        and calls the AI provider.
        """
        from .runtime_types import MCNPrompt
        prompt_obj = MCNPrompt(
            name   = stmt.name,
            system = stmt.system,
            user   = stmt.user,
            format = stmt.format,
        )
        env.define(stmt.name, prompt_obj)
        self.functions[stmt.name] = prompt_obj
        return prompt_obj

    def _exec_agent_decl(self, stmt: ast.AgentDecl,
                         env: Environment) -> Any:
        """
        Build an MCNAgent and bind it in the environment by name.
        Each task becomes a closure that:
          1. Captures the current lexical scope (closures work)
          2. Automatically sets the agent's model for ai() calls inside the task
        """
        from .runtime_types import MCNAgent
        agent = MCNAgent(
            name   = stmt.name,
            model  = stmt.model,
            tools  = stmt.tools,
            memory = stmt.memory,
        )

        for task in stmt.tasks:
            captured_env = env
            params   = task.params
            defaults = {k: self._eval(v, env) for k, v in task.defaults.items()}
            body     = task.body

            def make_task_fn(p, d, b, e):
                def task_fn(*args: Any) -> Any:
                    call_env = Environment(e)
                    for i, param in enumerate(p):
                        call_env.define(param, args[i] if i < len(args) else d.get(param))
                    try:
                        return self._exec_block(b, call_env)
                    except ReturnSignal as ret:
                        return ret.value
                return task_fn

            agent.add_task(task.name, params,
                           make_task_fn(params, defaults, body, captured_env))

        env.define(stmt.name, agent)
        self.functions[stmt.name] = agent
        return agent

    # ── Operators ──────────────────────────────────────────────────────────────

    def _apply_binary(self, op: str, left: Any, right: Any,
                      line: int, col: int) -> Any:
        if op == "+":
            # Automatic string coercion when either side is a string
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if op == "-":  return left - right
        if op == "*":  return left * right
        if op == "/":
            if right == 0:
                raise MCNError("Division by zero", line, col)
            return left / right
        if op == "%":
            if right == 0:
                raise MCNError("Modulo by zero", line, col)
            return left % right
        if op == "==": return left == right
        if op == "!=": return left != right
        if op == ">":  return left > right
        if op == "<":  return left < right
        if op == ">=": return left >= right
        if op == "<=": return left <= right
        # Return the actual value, not a bool — matches Python and JS semantics:
        #   "admin" or "guest"  →  "admin"  (first truthy)
        #   null or "default"   →  "default"
        #   user and user.name  →  user.name (second value if first is truthy)
        if op == "and": return right if self._truthy(left) else left
        if op == "or":  return left  if self._truthy(left) else right
        raise MCNError(f"Unknown operator: '{op}'", line, col)

    # ── Truthiness ────────────────────────────────────────────────────────────

    @staticmethod
    def _truthy(value: Any) -> bool:
        if value is None or value is False:
            return False
        if isinstance(value, (int, float)) and value == 0:
            return False
        if isinstance(value, str) and value == "":
            return False
        return True
