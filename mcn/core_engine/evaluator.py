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

import inspect
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
        self.message = message
        self.line = line
        self.col  = col


class ArgumentCountError(MCNError):
    """Wrong number of arguments to a user function; re-raised at the call site."""


def _did_you_mean(name: str, candidates) -> str:
    """' Did you mean 'x'?' for the closest known names, or ''."""
    import difflib
    names = sorted({c for c in candidates if isinstance(c, str) and not c.startswith("_")})
    close = difflib.get_close_matches(name, names, n=2, cutoff=0.75)
    if not close:
        return ""
    return " Did you mean " + " or ".join(f"'{c}'" for c in close) + "?"


def _describe(value) -> str:
    """'a number (3)', 'null', 'an object' — for operator type errors."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"a boolean ({str(value).lower()})"
    if isinstance(value, (int, float)):
        return f"a number ({value})"
    if isinstance(value, str):
        return f"text ({value[:20]!r})"
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, (list, tuple)):
        return "a list"
    return f"a {type(value).__name__}"


def _friendly_call_error(name: str, exc: Exception, bound: bool = False) -> str:
    """Rewrite Python's argument errors in terms of the MCN call.

    `bound` — the built-in is a Python method, whose counts include `self`."""
    import re
    msg = str(exc)
    m = re.search(r"missing (\d+) required positional arguments?: (.+)$", msg)
    if m:
        missing = m.group(2).replace("'", "").replace(" and ", ", ")
        return f"{name}() is missing {'an argument' if m.group(1) == '1' else 'arguments'}: {missing}"
    m = re.search(r"takes (?:from )?(\d+)(?: to (\d+))? positional arguments? but (\d+) (?:was|were) given", msg)
    if m:
        lo, hi, got = (str(int(g) - bound) if g else g for g in m.groups())
        takes = f"{lo} to {hi}" if hi else lo
        return f"{name}() takes {takes} argument{'s' if (hi or lo) != '1' else ''} but {got} {'was' if got == '1' else 'were'} given"
    m = re.search(r"got an unexpected keyword argument '(\w+)'", msg)
    if m:
        return f"{name}() has no parameter named '{m.group(1)}'"
    return f"Function '{name}' failed: {msg}"


# ── Lexical environment ────────────────────────────────────────────────────────

_UNDEFINED = object()          # sentinel — distinct from None

import threading as _threading
# The evaluator making the current call, so built-ins like agent_run can find
# the program's own functions (the test runner uses a separate evaluator)
CURRENT = _threading.local()


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

    def __init__(self, functions: Dict[str, Callable], max_steps: Optional[int] = None):
        # Step counting is per thread and per run: each script run, request,
        # watch handler or test gets its own budget (see user_func below)
        self._tl = _threading.local()
        self.functions       = functions         # shared with MCNInterpreter
        self.function_params: Dict[str, List[str]] = {}
        self.endpoint_auth: Dict[str, str] = {}      # endpoint → "" | "token" | "jwt"   # param names per endpoint
        self.globals    = Environment()
        self.components: Dict[str, ast.ComponentDecl] = {}   # UI components registry
        self.app_decl:   Optional[ast.AppDecl]        = None  # app declaration
        self.step_count = 0
        self.max_steps = max_steps or int(__import__("os").environ.get("MCN_MAX_STEPS") or 5_000_000)

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
        # Top-level functions are hoisted: a script can call a function defined
        # further down (each declaration runs again in order, so later ones win).
        for stmt in program.body:
            if isinstance(stmt, ast.FunctionDecl):
                self._exec_function_decl(stmt, self.globals)
        try:
            return self._exec_block(program.body, self.globals)
        except ReturnSignal as ret:
            return ret.value

    # ── Statement execution ────────────────────────────────────────────────────

    @property
    def step_count(self) -> int:
        return getattr(self._tl, "steps", 0)

    @step_count.setter
    def step_count(self, value: int) -> None:
        self._tl.steps = value

    @property
    def run_depth(self) -> int:
        """How many runs or MCN calls are active on this thread (0 = called from outside MCN)."""
        return getattr(self._tl, "depth", 0)

    @run_depth.setter
    def run_depth(self, value: int) -> None:
        self._tl.depth = value

    def _call_body(self, body: List[ast.Stmt], env: Environment) -> Any:
        """Run a function, endpoint, stage or step body. A call from outside MCN
        (a request, a watch handler, a schedule) starts with a fresh step budget;
        calls made while a script runs share that run's budget."""
        depth = self.run_depth
        if depth == 0:
            self.step_count = 0
        self.run_depth = depth + 1
        try:
            return self._exec_block(body, env)
        finally:
            self.run_depth = depth

    def _exec_block(self, stmts: List[ast.Stmt], env: Environment) -> Any:
        result = None
        for stmt in stmts:
            result = self._exec_stmt(stmt, env)
        return result

    def _exec_stmt(self, stmt: ast.Stmt, env: Environment) -> Any:  # noqa: C901
        # Increment and check statement execution limit
        self.step_count += 1
        if self.step_count > self.max_steps:
            raise MCNError(
                f"Maximum statement execution limit of {self.max_steps} exceeded. Script execution terminated.",
                stmt.line, stmt.col
            )

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
                    # `throw "boom"` → e.message == "boom" (no location prefix)
                    message = exc.message if isinstance(exc, MCNError) else str(exc)
                    err_obj = {
                        "message": message,
                        "type":    type(exc).__name__,
                        "line":    getattr(exc, "line", 0),
                        "raw":     exc,
                    }
                    catch_env.define(var, err_obj)
                    catch_env.define("error", message)  # legacy compat
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
            name = str(self._eval(stmt.name, env))
            func = self._eval(stmt.function, env)   # a function, or its name as a string
            args = [self._eval(a, env) for a in stmt.arguments]
            if "task" in self.functions:
                return self.functions["task"](name, func, *args)
            raise MCNError("Task system not initialised", stmt.line, stmt.col)

        # ── use (package import) ───────────────────────────────────────────────
        if isinstance(stmt, ast.UseStmt):
            if isinstance(stmt.package, ast.Variable):
                package_name = stmt.package.name
            elif isinstance(stmt.package, ast.Literal):
                package_name = str(stmt.package.value)
            elif hasattr(stmt.package, "name"):
                package_name = getattr(stmt.package, "name")
            else:
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

        if isinstance(stmt, ast.ScheduleDecl):
            return self._exec_schedule_decl(stmt, env)

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

        if isinstance(stmt, ast.MCPServerDecl):
            return self._exec_mcp_decl(stmt, env)

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

        def user_func(*args: Any, **kwargs: Any) -> Any:
            call_env = Environment(captured_env)
            if len(args) > len(params):
                raise ArgumentCountError(f"{name}() takes {len(params)} argument{'s' if len(params) != 1 else ''} "
                                         f"({', '.join(params) or 'none'}) but {len(args)} were given")
            missing = [p for i, p in enumerate(params)
                       if i >= len(args) and p not in kwargs and p not in defaults]
            if missing:
                raise ArgumentCountError(f"{name}() is missing {'an argument' if len(missing) == 1 else 'arguments'}: "
                                         f"{', '.join(missing)} (it takes {', '.join(params)})")
            for i, param in enumerate(params):
                if i < len(args):
                    call_env.define(param, args[i])
                elif param in kwargs:
                    call_env.define(param, kwargs[param])
                elif param in defaults:
                    # Evaluate the default in the defining scope (lexical)
                    call_env.define(param, self._eval(defaults[param], captured_env))
                else:
                    call_env.define(param, None)
            try:
                return self._call_body(body, call_env)
            except ReturnSignal as ret:
                return ret.value

        # Register in both the environment and the shared functions dict
        # so the function is callable by name from anywhere.
        # Parameter names, for tools that describe MCN functions (agent_run)
        user_func.mcn_params = list(params)
        user_func.mcn_required = [p for p in params if p not in defaults]
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
            hint = _did_you_mean(expr.name, list(env.all_names()) + list(self.functions))
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
            try:
                return self._apply_binary(expr.operator, left, right,
                                          expr.line, expr.col)
            except TypeError:
                raise MCNError(
                    f"Can't use '{expr.operator}' with {_describe(left)} and {_describe(right)}",
                    expr.line, expr.col,
                ) from None

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
            if isinstance(obj, (list, tuple, str)):
                if expr.name == "length":
                    return len(obj)
                if expr.name == "includes":
                    return lambda x: x in obj
            # Allow attribute access on runtime objects (MCNPipeline, MCNService,
            # MCNWorkflow, MCNContract, MCNPrompt, MCNAgent) and any Python object
            if hasattr(obj, expr.name):
                return getattr(obj, expr.name)
            return None

        if isinstance(expr, ast.NamedArg):
            return (expr.name, self._eval(expr.value, env))

        if isinstance(expr, ast.Call):
            return self._eval_call(expr, env)

        raise MCNError(f"Unknown expression type: {type(expr).__name__}")

    def _method(self, prop: ast.Property, env: Environment, value: Any) -> Any:
        """`x.name(args)` where x has no such method: call the built-in or user
        function `name(x, args)` instead, so text.contains("a") == contains(text, "a")."""
        obj = self._eval(prop.object, env)
        if obj is None:
            if prop.safe:
                return lambda *a, **k: None
            raise MCNError(f"Can't call '.{prop.name}()' on null", prop.line, prop.col)
        fn = env.get(prop.name)
        if fn is _UNDEFINED:
            fn = self.functions.get(prop.name)
        if callable(fn):
            return lambda *a, **k: fn(obj, *a, **k)
        if isinstance(obj, dict) and prop.name in obj:
            return value        # a dict key holding a non-function — let the call fail normally
        kind = {dict: "object", list: "list", str: "text", int: "number", float: "number", bool: "boolean"}.get(type(obj), type(obj).__name__)
        known = [n for n in dir(obj) if not n.startswith("_")] + list(self.functions)
        raise MCNError(f"A {kind} value has no method '{prop.name}'.{_did_you_mean(prop.name, known)}",
                       prop.line, prop.col)

    def _eval_call(self, expr: ast.Call, env: Environment) -> Any:
        CURRENT.evaluator = self
        if isinstance(expr.callee, ast.Variable) and env.get(expr.callee.name) is _UNDEFINED \
                and expr.callee.name not in self.functions:
            name = expr.callee.name
            raise MCNError(
                f"Undefined function: '{name}'.{_did_you_mean(name, list(self.functions) + list(env.all_names()))}",
                expr.line, expr.col,
            )
        callee = self._eval(expr.callee, env)
        if isinstance(expr.callee, ast.Property) and not callable(callee):
            callee = self._method(expr.callee, env, callee)
        pos_args = []
        kw_args = {}
        for a in expr.arguments:
            if isinstance(a, ast.NamedArg):
                kw_args[a.name] = self._eval(a.value, env)
            else:
                pos_args.append(self._eval(a, env))

        if callable(callee):
            try:
                if kw_args:
                    return callee(*pos_args, **kw_args)
                return callee(*pos_args)
            except ArgumentCountError as exc:
                if not exc.line:
                    raise MCNError(exc.message, expr.line, expr.col) from exc
                raise
            except (ReturnSignal, MCNError):
                raise
            except PermissionError as exc:          # require(): the message is the whole story
                raise MCNError(str(exc), expr.line, expr.col) from exc
            except Exception as exc:
                if type(exc).__name__ == "HardwareError":   # device(): says what to check
                    raise MCNError(f"Device error: {exc}", expr.line, expr.col) from exc
                name = getattr(expr.callee, "name", "?")
                raise MCNError(_friendly_call_error(name, exc, bound=inspect.ismethod(callee)),
                               expr.line, expr.col) from exc

        # Callee resolved to a string (legacy edge-case)
        if isinstance(callee, str) and callee in self.functions:
            fn = self.functions[callee]
            if kw_args:
                return fn(*pos_args, **kw_args)
            return fn(*pos_args)

        name    = getattr(expr.callee, "name", str(callee))
        if isinstance(expr.callee, ast.Property):
            raise MCNError(f"'{name}' holds a {type(callee).__name__} value, not a function, so it can't be called",
                           expr.line, expr.col)
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
                        return self._call_body(b, call_env)
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
                        return self._call_body(b, call_env)
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
            # How the HTTP server protects this endpoint: "", "token" or "jwt"
            self.endpoint_auth[ep.name] = "" if ep.name in stmt.public else stmt.auth

        env.define(stmt.name, service)
        env.define(stmt.name, service)
        return service

    def _exec_schedule_decl(self, stmt: ast.ScheduleDecl,
                            env: Environment) -> Any:
        """
        Build an MCNSchedule and bind it in the environment.
        """
        from .runtime_types import MCNSchedule
        captured_env = env
        body = stmt.body

        def schedule_fn() -> Any:
            call_env = Environment(captured_env)
            try:
                return self._call_body(body, call_env)
            except ReturnSignal as ret:
                return ret.value

        schedule = MCNSchedule(stmt.name, stmt.cron_expr, schedule_fn)
        env.define(stmt.name, schedule)
        self.functions[stmt.name] = schedule
        return schedule

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
                        return self._call_body(b, call_env)
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
            if val is None:
                return ""
            from .display import to_text
            return to_text(val)

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
                        return self._call_body(b, call_env)
                    except ReturnSignal as ret:
                        return ret.value
                return task_fn

            agent.add_task(task.name, params,
                           make_task_fn(params, defaults, body, captured_env))

        env.define(stmt.name, agent)
        self.functions[stmt.name] = agent
        return agent

    def _exec_mcp_decl(self, stmt: ast.MCPServerDecl,
                        env: Environment) -> Any:
        """
        Build an MCNMCPServer and bind it in the environment by name.
        Each declared tool is also exposed as a top-level callable:
            filesystem_server.call("read_file", path)
            read_file(path)   ← shorthand
        """
        from .runtime_types import MCNMCPServer
        server = MCNMCPServer(
            name      = stmt.name,
            transport = stmt.transport,
            command   = stmt.command,
            args      = stmt.args,
            url       = stmt.url,
            tools     = [t.name for t in stmt.tools],
        )

        # Expose each declared tool as a top-level function shorthand
        for tool in stmt.tools:
            _server    = server
            _tool_name = tool.name

            def make_tool_fn(s, n):
                def tool_fn(*args: Any) -> Any:
                    return s.call(n, *args)
                tool_fn.__name__ = n
                return tool_fn

            fn = make_tool_fn(_server, _tool_name)
            env.define(_tool_name, fn)
            self.functions[_tool_name] = fn

        env.define(stmt.name, server)
        self.functions[stmt.name] = server
        return server

    # ── Operators ──────────────────────────────────────────────────────────────────────────────

    def _apply_binary(self, op: str, left: Any, right: Any,
                      line: int, col: int) -> Any:
        if op == "+":
            # Automatic string coercion when either side is a string
            if isinstance(left, str) or isinstance(right, str):
                from .display import to_text
                return to_text(left) + to_text(right)
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
