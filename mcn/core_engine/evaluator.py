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
        self.message = message      # without location prefix
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
      - Blocks (if / for / while / try / catch) share the enclosing scope,
        as in Python
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

    def own(self, name: str) -> Any:
        """Binding in *this* scope only (or _UNDEFINED)."""
        return self._vars.get(name, _UNDEFINED)

    def restore(self, name: str, old: Any):
        """Put back a binding saved with own(); _UNDEFINED removes it."""
        if old is _UNDEFINED:
            self._vars.pop(name, None)
        else:
            self._vars[name] = old

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
        self.current_dir: Optional[str] = None   # dir of the running file (for include)
        self._included:   set           = set()
        # Login & roles (auth block) — app_auth is created with the first service
        self.auth_config:  Optional[ast.AuthDecl] = None
        self.app_auth      = None
        self.audit_log     = None
        self.crud_resources: Dict[str, Any] = {}   # contract name → CrudResource (for ref)
        self.triggers: Dict[tuple, List[Callable]] = {}   # (event, contract) → handlers
        self.jobs: List[Any] = []                  # workflow.Job
        self._trigger_depth = 0
        self._files = None                         # FileStore (lazy)
        self._mailer = None                        # Mailer (lazy)
        import threading as _threading
        self.lock = _threading.RLock()             # serialises requests and jobs
        # Email / PDF / files built-ins (replace the older SMTP-only send_email)
        self.functions["send_email"] = self._send_email
        self.functions["make_pdf"]   = self._make_pdf
        self.functions["file_url"]   = lambda file_id: self.file_store().url(int(file_id))
        self.current_user: Optional[Dict[str, Any]] = None   # set per request by mcn serve

        # Boolean and null literals (JavaScript / JSON style)
        self.globals.define("true",  True)
        self.globals.define("false", False)
        self.globals.define("null",  None)
        self.globals.define("current_user", None)    # signed-in user inside endpoints

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
            is_dict  = isinstance(iterable, dict)
            if is_dict:
                iterable = list(iterable.items())   # dict → [(k,v), ...]
            elif isinstance(iterable, str):
                iterable = list(iterable)
            if not isinstance(iterable, (list, tuple)):
                raise MCNError(
                    f"Cannot iterate over {type(iterable).__name__}",
                    stmt.line, stmt.col,
                )
            # Like Python, the loop body runs in the enclosing scope: variables
            # declared inside the loop (and the loop variable) remain visible
            # after it, exactly as they do for `if` blocks.
            for idx, item in enumerate(iterable):
                if stmt.index_var and is_dict:
                    # for key, value in dict
                    env.define(stmt.index_var, item[0])
                    env.define(stmt.variable, item[1])
                else:
                    env.define(stmt.variable, item)
                    if stmt.index_var:
                        env.define(stmt.index_var, idx)   # for i, item in list
                try:
                    self._exec_block(stmt.body, env)
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
                    # Named catch var:  catch e  →  e.message, e.type, e.raw
                    var = stmt.catch_var or "error"
                    message = exc.message if isinstance(exc, MCNError) else str(exc)
                    err_obj = {
                        "message": message,
                        "type":    type(exc).__name__,
                        "raw":     exc,
                    }
                    # The catch body runs in the enclosing scope (so variables it
                    # declares stay visible, as with `if`), but the error names
                    # are temporary and must not clobber outer variables.
                    bindings = {var: err_obj}
                    if var != "error":
                        bindings["error"] = message          # legacy compat
                    saved = {n: env.own(n) for n in bindings}
                    for n, v in bindings.items():
                        env.define(n, v)
                    try:
                        result = self._exec_block(stmt.catch_body, env)
                    finally:
                        for n, old in saved.items():
                            env.restore(n, old)
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

        if isinstance(stmt, ast.AuthDecl):
            return self._exec_auth_decl(stmt, env)

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
        # Relative paths resolve from the directory of the file being run
        # (falls back to the working directory for code without a file).
        base = self.current_dir or os.getcwd()
        path = os.path.abspath(os.path.join(base, stmt.path))
        if not os.path.exists(path):
            raise MCNError(f"include: file not found: {stmt.path} (looked in {base})",
                           stmt.line, stmt.col)
        if path in self._included:
            return None                     # each file is included once
        self._included.add(path)
        code = open(path, encoding="utf-8").read()
        try:
            program = Parser(Lexer(code).tokenize()).parse()
        except Exception as exc:
            raise MCNError(f"in included file {stmt.path}: {exc}", stmt.line, stmt.col)
        saved, self.current_dir = self.current_dir, os.path.dirname(path)
        try:
            self.execute_program(program)   # merges components, functions, contracts
        finally:
            self.current_dir = saved
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
            raise MCNError(
                f"Undefined variable '{expr.name}'."
                + self._did_you_mean(expr.name, env),
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
            if expr.operator in ("and", "or"):
                # Short-circuit: the right side runs only when it decides the result
                left = self._eval(expr.left, env)
                if self._truthy(left) == (expr.operator == "or"):
                    return left
                return self._eval(expr.right, env)
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
            if isinstance(obj, (list, tuple, str)) and isinstance(index, int) \
                    and not isinstance(index, bool):
                # Python-style: items[-1] is the last item; out of range → null
                return obj[index] if -len(obj) <= index < len(obj) else None
            if isinstance(obj, dict):
                if index in obj:
                    return obj[index]
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

        name = getattr(expr.callee, "name", str(callee))
        raise MCNError(
            f"'{name}' is not a function." + self._did_you_mean(name, env),
            expr.line, expr.col,
        )

    # ── auth & audit ──────────────────────────────────────────────────────────

    def _exec_auth_decl(self, stmt: ast.AuthDecl, env: Environment) -> None:
        """auth / roles … — defines the built-in User contract (no DB work yet)."""
        from .auth import user_contract
        if self.auth_config is not None and self.auth_config.roles != stmt.roles:
            raise MCNError("auth is declared twice with different roles", stmt.line, stmt.col)
        self.auth_config = stmt
        contract = user_contract(stmt.roles)
        env.define("User", contract)
        self.functions["User"] = contract

    def _checked_roles(self, roles: List[str], node) -> List[str]:
        """Validate role names used in allow (typos would lock everyone out)."""
        import difflib
        if self.auth_config is None:
            raise MCNError("'allow' needs an auth block with roles, e.g.\n"
                           "auth\n    roles admin, staff", node.line, node.col)
        known = self.auth_config.roles
        for r in roles:
            if r not in known:
                close = difflib.get_close_matches(r, known, n=1)
                hint = f" Did you mean '{close[0]}'?" if close else ""
                raise MCNError(f"Unknown role '{r}' (roles: {', '.join(known)}).{hint}",
                               node.line, node.col)
        return list(roles)

    def _ensure_app_auth(self, service, env: Environment) -> None:
        """Create users table + login endpoints with the first service."""
        from .auth import AppAuth
        if self.app_auth is None:
            cfg = self.auth_config
            self.app_auth = AppAuth(cfg.roles, cfg.session_hours, self.functions["query"],
                                    actor=lambda: self.current_user,
                                    permissions=self.permissions_for)
            self.audit_log = self.app_auth.audit
            self.app_auth.users.registry = self.crud_resources
            if cfg.sso is not None:
                self.app_auth.sso = self._make_sso(cfg, env)
            self.crud_resources["User"] = self.app_auth.users
        for name, fn in self.app_auth.endpoints().items():
            if name in self.function_params:
                continue                         # already on an earlier service
            service.add_endpoint(name, ["payload"], fn)
            env.define(name, fn)
            self.functions[name] = fn
            self.function_params[name] = ["payload"]

    def _make_sso(self, cfg: ast.AuthDecl, env: Environment):
        from .auth import SSO
        d = cfg.sso
        values = {}
        for key in ("issuer", "client_id", "client_secret"):
            v = self._eval(getattr(d, key), env)
            if not v:
                raise MCNError(f"sso {key} is empty — set it (e.g. the environment variable "
                               f"it reads) before starting the server", d.line, d.col)
            values[key] = str(v)
        sso = SSO(self.app_auth, values["issuer"], values["client_id"], values["client_secret"],
                  [str(self._eval(x, env)) for x in d.allow_domains], d.default_role,
                  str(self._eval(d.label, env)) if d.label is not None else "", d.auto_create)
        sso.request_base = lambda: getattr(self, "request_base", "")
        return sso

    def _ensure_audit(self, service, env: Environment):
        from .crud import AuditLog
        if self.audit_log is None:
            self.audit_log = AuditLog(self.functions["query"])
            if self.auth_config is None:          # with auth, AppAuth adds it (admin-only)
                fn = self.audit_log.list

                def list_audit_log(payload: Any = None):
                    return fn(payload)
                list_audit_log._mcn_body = True
                list_audit_log._mcn_access = "public"
                service.add_endpoint("list_audit_log", ["payload"], list_audit_log)
                env.define("list_audit_log", list_audit_log)
                self.functions["list_audit_log"] = list_audit_log
                self.function_params["list_audit_log"] = ["payload"]
        return self.audit_log

    # ── triggers, jobs, files, email ────────────────────────────────────────

    def _register_trigger(self, trig: ast.TriggerDecl, env: Environment) -> None:
        from .runtime_types import MCNContract
        if not isinstance(env.get(trig.contract), MCNContract):
            raise MCNError(f"on {trig.event} {trig.contract}: no contract named "
                           f"'{trig.contract}'" + self._did_you_mean(trig.contract, env),
                           trig.line, trig.col)
        body = trig.body

        def handler(record, old, _body=body, _env=env):
            scope = Environment(_env)
            scope.define("record", record)
            scope.define("old", old)
            scope.define("changed", lambda field: (old or {}).get(field) != (record or {}).get(field))
            try:
                self._exec_block(_body, scope)
            except ReturnSignal:
                pass
        handler.__name__ = f"on {trig.event} {trig.contract}"
        self.triggers.setdefault((trig.event, trig.contract), []).append(handler)

    def _fire(self, event: str, contract: str, record, old) -> None:
        """Run `on <event> <contract>` handlers after a change has been saved.
        A failing handler is reported but doesn't undo the change."""
        handlers = self.triggers.get((event, contract), [])
        if not handlers:
            return
        if self._trigger_depth >= 5:
            print(f"[mcn] on {event} {contract}: skipped (triggers nested 5 deep — loop?)")
            return
        self._trigger_depth += 1
        try:
            for h in handlers:
                try:
                    h(record, old)
                except Exception as exc:
                    print(f"[mcn] {h.__name__} failed: {exc}")
                    if self.audit_log is not None:
                        self.audit_log.record("trigger_failed", contract, (record or {}).get("id"),
                                              {"note": f"{h.__name__} failed: {exc}"},
                                              self.current_user)
        finally:
            self._trigger_depth -= 1

    def _register_job(self, job: ast.JobDecl, service, env: Environment) -> None:
        from .workflow import Job
        if any(j.name == job.name for j in self.jobs):
            raise MCNError(f"There are two jobs named '{job.name}'", job.line, job.col)
        body = job.body

        def run(_body=body, _env=env):
            try:
                self._exec_block(_body, Environment(_env))
            except ReturnSignal:
                pass
        self.jobs.append(Job(job.name, job.every, job.unit, job.at, run))

    def _add_platform_endpoints(self, service, env: Environment) -> None:
        """upload / list_jobs / run_job / list_outbox (once)."""
        admin = [self.auth_config.roles[0]] if self.auth_config else "public"
        signed_in = "user" if self.auth_config else "public"

        def list_jobs(payload=None):
            return {"items": [j.info() for j in self.jobs]}

        def run_job(payload=None):
            from .crud import BadRequest, NotFound
            name = (payload or {}).get("name") if isinstance(payload, dict) else payload
            job = next((j for j in self.jobs if j.name == name), None)
            if job is None:
                raise NotFound({"error": f"No job named '{name}'"})
            return job.run()

        def upload(payload=None):
            return self.file_store().upload(payload, self.current_user)

        def list_outbox(payload=None):
            return self.mailer().list(payload)

        for name, fn, access in (("list_jobs", list_jobs, admin), ("run_job", run_job, admin),
                                 ("upload", upload, signed_in), ("list_outbox", list_outbox, admin)):
            if name in self.function_params:
                continue
            fn._mcn_body = True
            fn._mcn_access = access
            service.add_endpoint(name, ["payload"], fn)
            env.define(name, fn)
            self.functions[name] = fn
            self.function_params[name] = ["payload"]

    def app_secret(self) -> str:
        """$MCN_SECRET, else one random secret kept in the app database."""
        import os, secrets as _secrets
        if os.environ.get("MCN_SECRET"):
            return os.environ["MCN_SECRET"]
        q = self.functions["query"]
        q('CREATE TABLE IF NOT EXISTS "mcn_meta" ("key" TEXT PRIMARY KEY, "value" TEXT)')
        rows = q('SELECT "value" FROM "mcn_meta" WHERE "key" = ?', ("auth_secret",))
        if rows:
            return rows[0]["value"]
        value = _secrets.token_hex(32)
        q('INSERT INTO "mcn_meta" ("key", "value") VALUES (?, ?)', ("auth_secret", value))
        return value

    def file_store(self):
        from .files import FileStore
        if self._files is None:
            self._files = FileStore(self.functions["query"], self.app_secret())
        return self._files

    def mailer(self):
        from .files import Mailer
        if self._mailer is None:
            self._mailer = Mailer(self.functions["query"], self.file_store())
        return self._mailer

    def _send_email(self, to, subject, body="", attachments=None):
        """send_email(to, subject, body, [attachments])"""
        return self.mailer().send(to, str(subject), str(body), attachments)

    def _make_pdf(self, title, content=None, filename=None):
        """make_pdf(title, content) → file {id, name, url} (attach to emails, link in UI)."""
        from .files import build_pdf
        data = build_pdf(str(title), content if content is not None else "")
        name = filename or (_re.sub(r"[^\w\-]+", "-", str(title)).strip("-").lower() or "document") + ".pdf"
        return self.file_store().save(data, name, "application/pdf", self.current_user)

    def permissions_for(self, user: Optional[Dict[str, Any]]) -> List[str]:
        """Endpoint names this user may call."""
        from .auth import allowed
        return sorted(name for name in self.function_params
                      if allowed(getattr(self.functions.get(name), "_mcn_access", "user"), user))

    def _did_you_mean(self, name: str, env: Environment) -> str:
        """" Did you mean 'total'?" for the closest known names, or ""."""
        import difflib
        candidates = {n for n in env.all_names() if not n.startswith("_")}
        candidates |= {n for n in self.functions if not n.startswith("_")}
        candidates.discard(name)
        matches = difflib.get_close_matches(name, sorted(candidates), n=2, cutoff=0.7)
        if not matches:
            return ""
        return " Did you mean " + " or ".join(f"'{m}'" for m in matches) + "?"

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
            fn._mcn_access = ("public" if ep.public else
                              self._checked_roles(ep.allow, ep) if ep.allow else "user")
            service.add_endpoint(ep.name, params, fn)
            # Also expose each endpoint as a top-level function so tests and
            # scripts can call submit_claim(...) directly without the service prefix.
            env.define(ep.name, fn)
            self.functions[ep.name] = fn
            self.function_params[ep.name] = params

        for crud in stmt.cruds:
            self._exec_crud(crud, service, env)

        if self.auth_config is not None:
            self._ensure_app_auth(service, env)

        for trig in stmt.triggers:
            self._register_trigger(trig, env)
        for job in stmt.jobs:
            self._register_job(job, service, env)
        if any(sp.type == "file" for r in self.crud_resources.values() for sp in r.specs) \
                or stmt.jobs or stmt.triggers:
            self._add_platform_endpoints(service, env)

        # Every `ref X` needs X's table (crud X here or in an earlier service)
        for trig in stmt.triggers:
            if trig.contract not in self.crud_resources:
                raise MCNError(f"on {trig.event} {trig.contract}: add 'crud {trig.contract}' "
                               "to the service (triggers run when records change)",
                               trig.line, trig.col)
            if trig.event in ("approve", "reject") and not self.crud_resources[trig.contract].approval:
                raise MCNError(f"on {trig.event} {trig.contract}: crud {trig.contract} has no "
                               "approval block", trig.line, trig.col)
        for resource in self.crud_resources.values():
            for spec in resource.specs:
                if spec.type == "ref" and spec.ref not in self.crud_resources:
                    raise MCNError(
                        f"{resource.contract.name}.{spec.name} is 'ref {spec.ref}': add "
                        f"'crud {spec.ref}' to the service so {spec.ref} records exist",
                        stmt.line, stmt.col)

        env.define(stmt.name, service)
        self.functions[stmt.name] = service
        return service

    def _exec_crud(self, crud: ast.CrudDecl, service, env: Environment) -> None:
        """crud Lead → table + list/get/create/update/delete endpoints."""
        from .runtime_types import MCNContract
        from .crud import CrudResource
        contract = env.get(crud.contract)
        if not isinstance(contract, MCNContract):
            raise MCNError(
                f"crud {crud.contract}: no contract named '{crud.contract}'"
                + self._did_you_mean(crud.contract, env)
                + " (declare it, or include the file that does)",
                crud.line, crud.col)
        if "query" not in self.functions:
            raise MCNError("crud needs a database (query) function", crud.line, crud.col)
        audit = self._ensure_audit(service, env) if crud.audit else None
        try:
            approval = None
            if crud.approval is not None:
                when_expr = crud.approval.when

                def when(record, _expr=when_expr, _env=env):
                    if _expr is None:
                        return True
                    scope = Environment(_env)
                    scope.define("record", record)
                    return self._truthy(self._eval(_expr, scope))

                approval = {"approvers": self._checked_roles(crud.approval.approvers, crud.approval),
                            "when": when}
            resource = CrudResource(contract, self.functions["query"], search=crud.search,
                                    sort=crud.sort, page_size=crud.page_size,
                                    audit=audit, actor=lambda: self.current_user,
                                    registry=self.crud_resources,
                                    files=self.file_store() if any(sp.type == "file" for sp in contract.specs) else None,
                                    hooks=lambda ev, rec, old, _c=contract.name: self._fire(ev, _c, rec, old),
                                    approval=approval, csv_import=crud.csv_import,
                                    csv_export=crud.csv_export)
        except ValueError as exc:
            raise MCNError(str(exc), crud.line, crud.col)
        for spec in contract.specs:
            if spec.type == "ref" and not isinstance(env.get(spec.ref), MCNContract):
                raise MCNError(f"{contract.name}.{spec.name} is 'ref {spec.ref}', but there is "
                               f"no contract named '{spec.ref}'" + self._did_you_mean(spec.ref, env),
                               crud.line, crud.col)
        self.crud_resources[contract.name] = resource
        resource.ensure_table()
        action_of = {"list": "read", "get": "read", "export": "read", "create": "write",
                     "update": "write", "import": "write", "delete": "delete"}
        for name, fn in resource.endpoints().items():
            action = fn._mcn_action
            if action in ("approve", "reject"):
                fn._mcn_access = approval["approvers"]
            else:
                roles = crud.allow.get(action_of[action])
                fn._mcn_access = self._checked_roles(roles, crud) if roles else "user"
            service.add_endpoint(name, ["payload"], fn)
            env.define(name, fn)
            self.functions[name] = fn
            self.function_params[name] = ["payload"]

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
        from .crud import FieldSpec, FIELD_TYPES
        specs = []
        for f in stmt.fields:
            if f.type_name.lower() not in FIELD_TYPES and f.type_name.lower() not in (
                    "list", "array", "dict", "object"):
                raise MCNError(
                    f"Unknown type '{f.type_name}' for field '{f.name}'. Use str, text, "
                    f"int, float, bool, date, datetime or choice(...)", f.line, f.col)
            default = self._eval(f.default, env) if f.default is not None else None
            specs.append(FieldSpec(f.name, f.type_name.lower(), optional=f.optional,
                                   default=default, has_default=f.default is not None,
                                   unique=f.unique, choices=f.choices, ref=f.ref or None,
                                   read_roles=self._checked_roles(f.read_roles, f) if f.read_roles else None,
                                   write_roles=self._checked_roles(f.write_roles, f) if f.write_roles else None))
        fields = [(f.name, f.type_name) for f in stmt.fields]
        contract = MCNContract(stmt.name, fields, specs)
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

        s = self._INTERP_RE.sub(_replace, s)
        if "{" in s and _re.search(r"[(+\-*/%?<>=!]", s):
            s = self._interp_expressions(s, env)
        return s

    def _interp_expressions(self, s: str, env: Environment) -> str:
        """{format_currency(total)}, {price * qty}, {list_x({a: 1}).total} —
        balanced braces, quotes respected; anything that isn't a valid
        expression is left exactly as written."""
        out, i, n = [], 0, len(s)
        while i < n:
            if s[i] != "{":
                out.append(s[i])
                i += 1
                continue
            depth, j, quote = 0, i, None
            while j < n:
                ch = s[j]
                if quote:
                    if ch == quote:
                        quote = None
                elif ch in "'\"":
                    quote = ch
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= n:                       # unbalanced: keep the rest as is
                out.append(s[i:])
                break
            out.append(self._interp_expr(s[i + 1:j], env, s[i:j + 1]))
            i = j + 1
        return "".join(out)

    def _interp_expr(self, text: str, env: Environment, original: str) -> str:
        """Evaluate an expression placeholder; leave it as written if it isn't one."""
        if not _re.search(r"[A-Za-z_(]", text) or not _re.search(r"[(+\-*/%?<>=!]", text):
            return original
        from .lexer import Lexer
        from .parser import Parser
        try:
            tokens = Lexer(text).tokenize()
            parser = Parser(tokens)
            parser.errors = []
            expr = parser._expression()
            parser._skip_newlines()
            if not parser._at_end():
                return original
            value = self._eval(expr, env)
        except Exception:
            return original
        return "" if value is None else str(value)

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
        if isinstance(value, (str, list, tuple, dict)) and len(value) == 0:
            return False     # "", [], {} are falsy (as in Python)
        return True
