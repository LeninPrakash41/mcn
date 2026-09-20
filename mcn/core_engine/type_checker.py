"""
MCN Static Type Checker — walks the AST and infers / checks types.

Design principles
─────────────────
1. Non-blocking  — collects ALL issues in one pass; never raises.
2. Gradual typing — variables without an obvious type become 'any'.
   'any' is compatible with everything, so unknown code never causes a
   false positive.
3. Inference     — `var x = 42` → x:int without any annotation.
4. Issue severity — WARNING (uncertain / style) vs ERROR (definite
   violation, e.g. calling a non-callable variable).

Type lattice (simplified):
    any  ← every type is a subtype of any
    int  ← subtype of number
    float← subtype of number
    number = int | float
    str, bool, list, dict, tuple, null, callable
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from . import ast_nodes as ast


# ── Types ──────────────────────────────────────────────────────────────────────

class MCNType(str, Enum):
    ANY      = "any"
    INT      = "int"
    FLOAT    = "float"
    NUMBER   = "number"
    STR      = "str"
    BOOL     = "bool"
    LIST     = "list"
    DICT     = "dict"
    TUPLE    = "tuple"
    NULL     = "null"
    CALLABLE = "callable"

    def is_compatible(self, other: "MCNType") -> bool:
        """Return True if `self` can be used where `other` is expected."""
        if self == MCNType.ANY or other == MCNType.ANY:
            return True
        if self == other:
            return True
        # int and float are both number-compatible
        number_types = {MCNType.INT, MCNType.FLOAT, MCNType.NUMBER}
        if self in number_types and other in number_types:
            return True
        return False


_TYPE_MAP: Dict[str, MCNType] = {
    "any":      MCNType.ANY,
    "int":      MCNType.INT,
    "integer":  MCNType.INT,
    "float":    MCNType.FLOAT,
    "number":   MCNType.NUMBER,
    "num":      MCNType.NUMBER,
    "str":      MCNType.STR,
    "string":   MCNType.STR,
    "bool":     MCNType.BOOL,
    "boolean":  MCNType.BOOL,
    "list":     MCNType.LIST,
    "array":    MCNType.LIST,
    "dict":     MCNType.DICT,
    "map":      MCNType.DICT,
    "object":   MCNType.DICT,
    "tuple":    MCNType.TUPLE,
    "null":     MCNType.NULL,
    "void":     MCNType.NULL,
    "none":     MCNType.NULL,
    "callable": MCNType.CALLABLE,
    "func":     MCNType.CALLABLE,
    "function": MCNType.CALLABLE,
    "fn":       MCNType.CALLABLE,
}


def _resolve_type_name(name: Optional[str]) -> MCNType:
    """Map a type annotation string (e.g. 'str', 'int', 'list') to MCNType."""
    if not name:
        return MCNType.ANY
    cleaned = str(name).strip().lower()
    return _TYPE_MAP.get(cleaned, MCNType.ANY)


# ── Issues ─────────────────────────────────────────────────────────────────────

class Severity(Enum):
    WARNING = auto()
    ERROR   = auto()


@dataclass
class TypeIssue:
    severity: Severity
    message:  str
    line:     int
    col:      int

    def __str__(self) -> str:
        tag = "error  " if self.severity == Severity.ERROR else "warning"
        return f"[{self.line}:{self.col}] {tag}  {self.message}"


# ── Type scope (mirrors evaluator.Environment) ────────────────────────────────

class TypeScope:
    def __init__(self, parent: Optional["TypeScope"] = None):
        self._types:  Dict[str, MCNType]    = {}
        self._parent: Optional[TypeScope]   = parent

    def get(self, name: str) -> MCNType:
        if name in self._types:
            return self._types[name]
        if self._parent:
            return self._parent.get(name)
        return MCNType.ANY          # unknown → any (no false positives)

    def define(self, name: str, t: MCNType):
        self._types[name] = t

    def child(self) -> "TypeScope":
        return TypeScope(parent=self)


# ── Known built-in return types ───────────────────────────────────────────────

BUILTIN_RETURN_TYPES: Dict[str, MCNType] = {
    # Core runtime
    "log":               MCNType.NULL,
    "echo":              MCNType.NULL,
    "env":               MCNType.STR,
    "read_file":         MCNType.STR,
    "write_file":        MCNType.NULL,
    "append_file":       MCNType.NULL,
    "now":               MCNType.STR,
    "format_date":       MCNType.STR,
    "hash_data":         MCNType.STR,
    "encode_base64":     MCNType.STR,
    "decode_base64":     MCNType.STR,
    "fetch":             MCNType.DICT,
    "trigger":           MCNType.ANY,
    "query":             MCNType.ANY,
    "workflow":          MCNType.ANY,
    "ai":                MCNType.STR,
    "llm":               MCNType.STR,
    "embed":             MCNType.LIST,
    "extract":           MCNType.DICT,
    "classify":          MCNType.STR,
    "checkpoint":        MCNType.ANY,
    "send_email":        MCNType.NULL,
    "task":              MCNType.STR,
    "await":             MCNType.ANY,
    "use":               MCNType.STR,
    # Session
    "session_set":       MCNType.NULL,
    "session_get":       MCNType.ANY,
    "session_delete":    MCNType.NULL,
    "session_clear":     MCNType.NULL,
    "session_all":       MCNType.DICT,
    # Cache
    "cache_set":         MCNType.NULL,
    "cache_get":         MCNType.ANY,
    "cache_delete":      MCNType.NULL,
    "cache_clear":       MCNType.NULL,
    # Memory
    "memory_store":      MCNType.STR,
    "memory_get":        MCNType.DICT,
    "memory_search":     MCNType.LIST,
    "memory_all":        MCNType.LIST,
    "memory_clear":      MCNType.NULL,
    # Vector Store
    "vector_upsert":     MCNType.STR,
    "vector_search":     MCNType.LIST,
    "vector_delete":     MCNType.NULL,
    "vector_clear":      MCNType.NULL,
    # RAG
    "rag":               MCNType.STR,
    # Analytics & Reporting
    "report":                MCNType.DICT,
    "generate_report":       MCNType.DICT,
    "kpi":                   MCNType.DICT,
    "kpi_summary":           MCNType.DICT,
    "trend":                 MCNType.DICT,
    "trend_analysis":        MCNType.DICT,
    "distribution":          MCNType.DICT,
    "distribution_analysis": MCNType.DICT,
    "pivot":                 MCNType.DICT,
    "pivot_table":           MCNType.DICT,
    "chart_data":            MCNType.DICT,
    "export_report":         MCNType.STR,
    # Auth
    "auth_hash":         MCNType.STR,
    "auth_verify_hash":  MCNType.BOOL,
    "auth_create_token": MCNType.STR,
    "auth_verify_token": MCNType.ANY,
    # Data
    "parse_csv":         MCNType.LIST,
    "parse_json":        MCNType.ANY,
    "to_json":           MCNType.STR,
    # Strings
    "split":             MCNType.LIST,
    "join":              MCNType.STR,
    "upper":             MCNType.STR,
    "lower":             MCNType.STR,
    "trim":              MCNType.STR,
    "replace":           MCNType.STR,
    "contains":          MCNType.BOOL,
    "starts_with":       MCNType.BOOL,
    "ends_with":         MCNType.BOOL,
    "str_len":           MCNType.INT,
    "pad_left":          MCNType.STR,
    "pad_right":         MCNType.STR,
    "substring":         MCNType.STR,
    "regex_match":       MCNType.BOOL,
    "regex_extract":     MCNType.LIST,
    # Arrays
    "first":             MCNType.ANY,
    "last":              MCNType.ANY,
    "flatten":           MCNType.LIST,
    "unique":            MCNType.LIST,
    "sort_list":         MCNType.LIST,
    "reverse_list":      MCNType.LIST,
    "slice_list":        MCNType.LIST,
    "push":              MCNType.LIST,
    "pop":               MCNType.ANY,
    "array_contains":    MCNType.BOOL,
    "zip_lists":         MCNType.LIST,
    "group_by":          MCNType.DICT,
    "count":             MCNType.INT,
    # Math
    "abs_val":           MCNType.NUMBER,
    "round_val":         MCNType.NUMBER,
    "floor_val":         MCNType.INT,
    "ceil_val":          MCNType.INT,
    "min_val":           MCNType.NUMBER,
    "max_val":           MCNType.NUMBER,
    "sum_list":          MCNType.NUMBER,
    "average":           MCNType.NUMBER,
    "random_float":      MCNType.NUMBER,
    "random_int":        MCNType.INT,
    "clamp":             MCNType.NUMBER,
    # Queue
    "queue_push":        MCNType.NULL,
    "queue_pop":         MCNType.ANY,
    "queue_size":        MCNType.INT,
    "queue_clear":       MCNType.NULL,
    # Crypto / UUID
    "uuid":              MCNType.STR,
    "sha256":            MCNType.STR,
    "md5":               MCNType.STR,
}

BUILTIN_ARG_COUNTS: Dict[str, Tuple[int, int]] = {
    # (min_args, max_args); -1 = variadic
    "log":               (1, 1),
    "echo":              (1, 1),
    "env":               (1, 1),
    "read_file":         (1, 1),
    "write_file":        (2, 2),
    "now":               (0, 0),
    "hash_data":         (1, 2),
    "fetch":             (1, 1),
    "trigger":           (1, 2),
    "query":             (1, 2),
    "ai":                (1, 3),
    "llm":               (2, 3),
    "embed":             (1, 1),
    "extract":           (2, 2),
    "classify":          (2, 2),
    "checkpoint":        (2, 2),
    # Session
    "session_set":       (2, 2),
    "session_get":       (1, 2),
    "session_delete":    (1, 1),
    "session_clear":     (0, 0),
    "session_all":       (0, 0),
    # Cache
    "cache_set":         (2, 3),
    "cache_get":         (1, 2),
    "cache_delete":      (1, 1),
    "cache_clear":       (0, 0),
    # Memory
    "memory_store":      (1, 2),
    "memory_get":        (1, 1),
    "memory_search":     (1, 2),
    "memory_all":        (0, 0),
    "memory_clear":      (0, 0),
    # Vector
    "vector_upsert":     (2, 3),
    "vector_search":     (1, 2),
    "vector_delete":     (1, 1),
    "vector_clear":      (0, 0),
    # RAG
    "rag":               (1, 3),
    # Auth
    "auth_hash":         (1, 1),
    "auth_verify_hash":  (2, 2),
    "auth_create_token": (1, 3),
    "auth_verify_token": (1, 2),
    # Data
    "parse_csv":         (1, 2),
    "parse_json":        (1, 1),
    "to_json":           (1, 2),
    # Strings
    "split":             (1, 2),
    "join":              (1, 2),
    "upper":             (1, 1),
    "lower":             (1, 1),
    "trim":              (1, 1),
    "replace":           (3, 3),
    "contains":          (2, 2),
    "starts_with":       (2, 2),
    "ends_with":         (2, 2),
    "str_len":           (1, 1),
    "pad_left":          (2, 3),
    "pad_right":         (2, 3),
    "substring":         (2, 3),
    "regex_match":       (2, 2),
    "regex_extract":     (2, 2),
    # Arrays
    "first":             (1, 1),
    "last":              (1, 1),
    "flatten":           (1, 1),
    "unique":            (1, 1),
    "sort_list":         (1, 3),
    "reverse_list":      (1, 1),
    "slice_list":        (2, 3),
    "push":              (2, 2),
    "pop":               (1, 1),
    "array_contains":    (2, 2),
    "zip_lists":         (2, 2),
    "group_by":          (2, 2),
    "count":             (1, 1),
    # Math
    "abs_val":           (1, 1),
    "round_val":         (1, 2),
    "floor_val":         (1, 1),
    "ceil_val":          (1, 1),
    "min_val":           (1, -1),
    "max_val":           (1, -1),
    "sum_list":          (1, 1),
    "average":           (1, 1),
    "random_float":      (0, 0),
    "random_int":        (2, 2),
    "clamp":             (3, 3),
    # Queue
    "queue_push":        (2, 2),
    "queue_pop":         (1, 1),
    "queue_size":        (1, 1),
    "queue_clear":       (1, 1),
    # Crypto / UUID
    "uuid":              (0, 0),
    "sha256":            (1, 1),
    "md5":               (1, 1),
}


# ── Type Checker ──────────────────────────────────────────────────────────────

class TypeChecker:
    """
    Walk an AST, infer expression types, and collect TypeIssues.

    Usage:
        checker = TypeChecker()
        issues  = checker.check(program)
        errors  = [i for i in issues if i.severity == Severity.ERROR]
    """

    def __init__(self):
        self._issues: List[TypeIssue] = []

    # ── Entry point ────────────────────────────────────────────────────────────

    def check(self, program: ast.Program) -> List[TypeIssue]:
        self._issues = []
        scope = TypeScope()
        # Seed built-ins so they are always CALLABLE
        for name in BUILTIN_RETURN_TYPES:
            scope.define(name, MCNType.CALLABLE)
        self._check_block(program.body, scope)
        return list(self._issues)

    # ── Statement checking ─────────────────────────────────────────────────────

    def _check_block(self, stmts: List[ast.Stmt], scope: TypeScope) -> MCNType:
        last = MCNType.NULL
        for stmt in stmts:
            last = self._check_stmt(stmt, scope)
        return last

    def _check_stmt(self, stmt: ast.Stmt, scope: TypeScope) -> MCNType:  # noqa: C901
        if isinstance(stmt, ast.VarDecl):
            val_type = self._infer(stmt.value, scope)
            if stmt.type_hint:
                expected_type = _resolve_type_name(stmt.type_hint)
                if expected_type != MCNType.ANY and val_type != MCNType.ANY:
                    if not val_type.is_compatible(expected_type):
                        self._error(
                            f"Cannot assign expression of type '{val_type.value}' to variable '{stmt.name}' with declared type '{stmt.type_hint}'",
                            stmt.line, stmt.col,
                        )
                scope.define(stmt.name, expected_type if expected_type != MCNType.ANY else val_type)
            else:
                scope.define(stmt.name, val_type)
            return val_type

        if isinstance(stmt, ast.AssignStmt):
            val_type = self._infer(stmt.value, scope)
            existing_type = scope.get(stmt.name)
            if existing_type != MCNType.ANY and val_type != MCNType.ANY:
                if not val_type.is_compatible(existing_type):
                    self._error(
                        f"Cannot assign expression of type '{val_type.value}' to variable '{stmt.name}' of type '{existing_type.value}'",
                        stmt.line, stmt.col,
                    )
            return val_type

        if isinstance(stmt, ast.CompoundAssignStmt):
            val_type = self._infer(stmt.value, scope)
            existing_type = scope.get(stmt.name)
            if existing_type != MCNType.ANY and val_type != MCNType.ANY:
                if stmt.op in ("+=", "-=", "*=", "/=", "%="):
                    if existing_type not in (MCNType.INT, MCNType.FLOAT, MCNType.NUMBER) and not (stmt.op == "+=" and existing_type == MCNType.STR):
                        self._error(
                            f"Compound assignment '{stmt.op}' not supported on type '{existing_type.value}'",
                            stmt.line, stmt.col,
                        )
            return existing_type

        if isinstance(stmt, ast.IfStmt):
            cond_type = self._infer(stmt.condition, scope)
            if cond_type not in (MCNType.BOOL, MCNType.ANY):
                self._warn(
                    f"Condition has type '{cond_type.value}', expected bool",
                    stmt.line, stmt.col,
                )
            then_t = self._check_block(stmt.then_body, scope.child())
            else_t = self._check_block(stmt.else_body, scope.child()) if stmt.else_body else MCNType.NULL
            return then_t if then_t == else_t else MCNType.ANY

        if isinstance(stmt, ast.ForStmt):
            iter_type = self._infer(stmt.iterable, scope)
            if iter_type not in (MCNType.LIST, MCNType.TUPLE, MCNType.ANY):
                self._error(
                    f"'for' requires an iterable (list/tuple), got '{iter_type.value}'",
                    stmt.line, stmt.col,
                )
            loop_scope = scope.child()
            loop_scope.define(stmt.variable, MCNType.ANY)
            if getattr(stmt, "index_var", None):
                loop_scope.define(stmt.index_var, MCNType.INT)
            self._check_block(stmt.body, loop_scope)
            return MCNType.NULL

        if isinstance(stmt, ast.WhileStmt):
            self._infer(stmt.condition, scope)
            self._check_block(stmt.body, scope.child())
            return MCNType.NULL

        if isinstance(stmt, ast.TryStmt):
            self._check_block(stmt.try_body, scope.child())
            if stmt.catch_body:
                catch_scope = scope.child()
                err_var = getattr(stmt, "catch_var", None) or "error"
                catch_scope.define(err_var, MCNType.STR)
                self._check_block(stmt.catch_body, catch_scope)
            if getattr(stmt, "finally_body", None):
                self._check_block(stmt.finally_body, scope.child())
            return MCNType.NULL

        if isinstance(stmt, ast.ThrowStmt):
            self._infer(stmt.message, scope)
            return MCNType.NULL

        if isinstance(stmt, ast.FunctionDecl):
            fn_scope = scope.child()
            expected_ret = _resolve_type_name(stmt.return_type) if stmt.return_type else MCNType.ANY
            for param in stmt.params:
                p_hint = stmt.param_types.get(param) if stmt.param_types else None
                p_type = _resolve_type_name(p_hint)
                fn_scope.define(param, p_type)
                if stmt.defaults and param in stmt.defaults:
                    def_val_t = self._infer(stmt.defaults[param], scope)
                    if p_type != MCNType.ANY and def_val_t != MCNType.ANY and not def_val_t.is_compatible(p_type):
                        self._error(
                            f"Default value of type '{def_val_t.value}' is incompatible with parameter '{param}' of type '{p_type.value}'",
                            stmt.line, stmt.col,
                        )
            self._check_function_body(stmt.body, fn_scope, expected_ret)
            scope.define(stmt.name, MCNType.CALLABLE)
            return MCNType.NULL

        if isinstance(stmt, ast.ReturnStmt):
            if stmt.value is not None:
                return self._infer(stmt.value, scope)
            return MCNType.NULL

        if isinstance(stmt, ast.AssertStmt):
            self._infer(stmt.condition, scope)
            if stmt.message:
                self._infer(stmt.message, scope)
            return MCNType.NULL

        if isinstance(stmt, ast.TestDecl):
            test_scope = scope.child()
            self._check_block(stmt.body, test_scope)
            return MCNType.NULL

        if isinstance(stmt, ast.ExprStmt):
            return self._infer(stmt.expression, scope)

        if isinstance(stmt, ast.UseStmt):
            return MCNType.STR

        if isinstance(stmt, ast.TaskStmt):
            return MCNType.STR

        # New language primitive declarations
        for decl_type in ("PipelineDecl", "ServiceDecl", "WorkflowDecl", "ContractDecl", "AgentDecl", "PromptDecl", "MCPDecl"):
            if type(stmt).__name__ == decl_type:
                self._check_primitive_decl(stmt, scope)
                return MCNType.ANY

        return MCNType.ANY

    def _check_function_body(self, stmts: List[ast.Stmt], scope: TypeScope, expected_ret: MCNType):
        for s in stmts:
            if isinstance(s, ast.ReturnStmt):
                actual_ret = self._infer(s.value, scope) if s.value is not None else MCNType.NULL
                if expected_ret != MCNType.ANY and actual_ret != MCNType.ANY and not actual_ret.is_compatible(expected_ret):
                    self._error(
                        f"Return value of type '{actual_ret.value}' is incompatible with declared return type '{expected_ret.value}'",
                        s.line, s.col,
                    )
            elif isinstance(s, ast.IfStmt):
                self._infer(s.condition, scope)
                self._check_function_body(s.then_body, scope.child(), expected_ret)
                if s.else_body:
                    self._check_function_body(s.else_body, scope.child(), expected_ret)
            elif isinstance(s, ast.TryStmt):
                self._check_function_body(s.try_body, scope.child(), expected_ret)
                if s.catch_body:
                    catch_scope = scope.child()
                    err_var = getattr(s, "catch_var", None) or "error"
                    catch_scope.define(err_var, MCNType.STR)
                    self._check_function_body(s.catch_body, catch_scope, expected_ret)
            else:
                self._check_stmt(s, scope)

    def _check_primitive_decl(self, stmt: Any, scope: TypeScope):
        """Handle pipeline / service / workflow / contract / agent declarations."""
        # All inner stages/endpoints/steps/tools are function-like — check their bodies
        for attr in ("stages", "endpoints", "steps", "tools"):
            for sub in getattr(stmt, attr, []):
                sub_scope = scope.child()
                for param in getattr(sub, "params", []):
                    sub_scope.define(param, MCNType.ANY)
                self._check_block(getattr(sub, "body", []), sub_scope)
        scope.define(stmt.name, MCNType.ANY)

    # ── Expression inference ───────────────────────────────────────────────────

    def _infer(self, expr: ast.Expr, scope: TypeScope) -> MCNType:  # noqa: C901
        if isinstance(expr, ast.Literal):
            v = expr.value
            if isinstance(v, bool):   return MCNType.BOOL
            if isinstance(v, int):    return MCNType.INT
            if isinstance(v, float):  return MCNType.FLOAT
            if isinstance(v, str):    return MCNType.STR
            if v is None:             return MCNType.NULL
            return MCNType.ANY

        if isinstance(expr, ast.Variable):
            t = scope.get(expr.name)
            return t

        if isinstance(expr, ast.Binary):
            return self._infer_binary(expr, scope)

        if isinstance(expr, ast.Unary):
            operand_t = self._infer(expr.operand, scope)
            if expr.operator == "not":
                return MCNType.BOOL
            if expr.operator == "-":
                if operand_t in (MCNType.INT, MCNType.FLOAT, MCNType.NUMBER, MCNType.ANY):
                    return operand_t
                self._error(
                    f"Unary '-' applied to '{operand_t.value}'",
                    expr.line, expr.col,
                )
            return MCNType.ANY

        if isinstance(expr, ast.Array):
            for elem in expr.elements:
                self._infer(elem, scope)
            return MCNType.LIST

        if isinstance(expr, ast.MCNTuple):
            for elem in expr.elements:
                self._infer(elem, scope)
            return MCNType.TUPLE

        if isinstance(expr, ast.MCNObject):
            for key_expr, val_expr in expr.properties:
                self._infer(key_expr, scope)
                self._infer(val_expr, scope)
            return MCNType.DICT

        if isinstance(expr, ast.TernaryExpr):
            self._infer(expr.condition, scope)
            t1 = self._infer(expr.then_expr, scope)
            t2 = self._infer(expr.else_expr, scope)
            if t1 == t2:
                return t1
            if t1 in (MCNType.INT, MCNType.FLOAT) and t2 in (MCNType.INT, MCNType.FLOAT):
                return MCNType.NUMBER
            return MCNType.ANY

        if isinstance(expr, ast.ArrowFunc):
            af_scope = scope.child()
            for p in expr.params:
                af_scope.define(p, MCNType.ANY)
            self._infer(expr.body, af_scope)
            return MCNType.CALLABLE

        if isinstance(expr, ast.Index):
            obj_t = self._infer(expr.object, scope)
            if obj_t not in (MCNType.LIST, MCNType.DICT, MCNType.TUPLE, MCNType.STR, MCNType.ANY):
                self._error(
                    f"Subscript on non-indexable type '{obj_t.value}'",
                    expr.line, expr.col,
                )
            self._infer(expr.index, scope)
            return MCNType.ANY

        if isinstance(expr, ast.Property):
            self._infer(expr.object, scope)
            return MCNType.ANY  # property access always any for now

        if isinstance(expr, ast.NamedArg):
            return self._infer(expr.value, scope)

        if isinstance(expr, ast.Call):
            return self._infer_call(expr, scope)

        return MCNType.ANY

    def _infer_binary(self, expr: ast.Binary, scope: TypeScope) -> MCNType:
        left_t  = self._infer(expr.left,  scope)
        right_t = self._infer(expr.right, scope)
        op = expr.operator

        # Comparison operators always return bool
        if op in ("==", "!=", ">", "<", ">=", "<="):
            return MCNType.BOOL

        # Logical operators return bool
        if op in ("and", "or"):
            return MCNType.BOOL

        # String concatenation coercion
        if op == "+":
            if left_t == MCNType.STR or right_t == MCNType.STR:
                return MCNType.STR
            if left_t == MCNType.INT and right_t == MCNType.INT:
                return MCNType.INT
            if left_t in (MCNType.INT, MCNType.FLOAT, MCNType.NUMBER) and \
               right_t in (MCNType.INT, MCNType.FLOAT, MCNType.NUMBER):
                return MCNType.FLOAT
            if left_t == MCNType.ANY or right_t == MCNType.ANY:
                return MCNType.ANY
            self._warn(
                f"Operator '+' on '{left_t.value}' and '{right_t.value}'",
                expr.line, expr.col,
            )
            return MCNType.ANY

        # Arithmetic
        if op in ("-", "*"):
            number = {MCNType.INT, MCNType.FLOAT, MCNType.NUMBER, MCNType.ANY}
            if left_t not in number or right_t not in number:
                self._error(
                    f"Operator '{op}' requires numbers, got "
                    f"'{left_t.value}' and '{right_t.value}'",
                    expr.line, expr.col,
                )
                return MCNType.ANY
            if left_t == MCNType.INT and right_t == MCNType.INT:
                return MCNType.INT
            return MCNType.FLOAT

        if op == "/":
            return MCNType.FLOAT      # always float

        return MCNType.ANY

    def _infer_call(self, expr: ast.Call, scope: TypeScope) -> MCNType:
        callee_t = self._infer(expr.callee, scope)

        # Get function name if it's a simple variable call
        func_name: Optional[str] = None
        if isinstance(expr.callee, ast.Variable):
            func_name = expr.callee.name

        # Check callability
        if callee_t not in (MCNType.CALLABLE, MCNType.ANY):
            self._error(
                f"'{func_name or '?'}' is not callable (type: '{callee_t.value}')",
                expr.line, expr.col,
            )
            return MCNType.ANY

        # Check argument count for known builtins
        if func_name and func_name in BUILTIN_ARG_COUNTS:
            mn, mx = BUILTIN_ARG_COUNTS[func_name]
            n = len(expr.arguments)
            if n < mn or (mx != -1 and n > mx):
                expected = f"{mn}" if mn == mx else f"{mn}–{mx}"
                self._error(
                    f"'{func_name}' expects {expected} argument(s), got {n}",
                    expr.line, expr.col,
                )

        # Infer all argument types (for side-effect checking of nested calls)
        for arg in expr.arguments:
            self._infer(arg, scope)

        # Return type from known builtins
        if func_name and func_name in BUILTIN_RETURN_TYPES:
            return BUILTIN_RETURN_TYPES[func_name]

        return MCNType.ANY

    # ── Issue helpers ──────────────────────────────────────────────────────────

    def _error(self, message: str, line: int, col: int):
        self._issues.append(TypeIssue(Severity.ERROR, message, line, col))

    def _warn(self, message: str, line: int, col: int):
        self._issues.append(TypeIssue(Severity.WARNING, message, line, col))


# ── Convenience function ───────────────────────────────────────────────────────

def check_source(code: str) -> List[TypeIssue]:
    """
    Lex, parse, and type-check a MCN source string.
    Returns a list of TypeIssue (may be empty — means clean).
    Lex / parse errors are returned as ERROR-severity issues.
    """
    from .lexer  import Lexer
    from .parser import Parser

    try:
        tokens  = Lexer(code).tokenize()
        program = Parser(tokens).parse()
    except Exception as exc:
        line, col = 1, 1
        # Extract location if the error message contains [line:col]
        import re
        m = re.search(r"\[(\d+):(\d+)\]", str(exc))
        if m:
            line, col = int(m.group(1)), int(m.group(2))
        return [TypeIssue(Severity.ERROR, str(exc), line, col)]

    return TypeChecker().check(program)
