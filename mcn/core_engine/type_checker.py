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
    "log":            MCNType.NULL,
    "echo":           MCNType.NULL,
    "env":            MCNType.STR,
    "read_file":      MCNType.STR,
    "write_file":     MCNType.NULL,
    "append_file":    MCNType.NULL,
    "now":            MCNType.STR,
    "format_date":    MCNType.STR,
    "hash_data":      MCNType.STR,
    "encode_base64":  MCNType.STR,
    "decode_base64":  MCNType.STR,
    "fetch":          MCNType.DICT,
    "trigger":        MCNType.ANY,
    "query":          MCNType.ANY,
    "workflow":       MCNType.ANY,
    "ai":             MCNType.STR,
    "send_email":     MCNType.NULL,
    "task":           MCNType.STR,
    "await":          MCNType.ANY,
    "use":            MCNType.STR,
}

BUILTIN_ARG_COUNTS: Dict[str, Tuple[int, int]] = {
    # (min_args, max_args); -1 = variadic
    "log":        (1, 1),
    "echo":       (1, 1),
    "env":        (1, 1),
    "read_file":  (1, 1),
    "write_file": (2, 2),
    "now":        (0, 0),
    "hash_data":  (1, 2),
    "fetch":      (1, 1),
    "trigger":    (1, 2),
    "query":      (1, 2),
    "ai":         (1, 3),
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
            scope.define(stmt.name, val_type)
            return val_type

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
                catch_scope.define("error", MCNType.STR)
                self._check_block(stmt.catch_body, catch_scope)
            return MCNType.NULL

        if isinstance(stmt, ast.ThrowStmt):
            self._infer(stmt.message, scope)
            return MCNType.NULL

        if isinstance(stmt, ast.FunctionDecl):
            fn_scope = scope.child()
            for param in stmt.params:
                fn_scope.define(param, MCNType.ANY)
            return_type = self._check_block(stmt.body, fn_scope)
            scope.define(stmt.name, MCNType.CALLABLE)
            return MCNType.NULL

        if isinstance(stmt, ast.ReturnStmt):
            if stmt.value is not None:
                return self._infer(stmt.value, scope)
            return MCNType.NULL

        if isinstance(stmt, ast.ExprStmt):
            return self._infer(stmt.expression, scope)

        if isinstance(stmt, ast.UseStmt):
            return MCNType.STR

        if isinstance(stmt, ast.TaskStmt):
            return MCNType.STR

        if isinstance(stmt, (ast.ThrowStmt,)):
            return MCNType.NULL

        # New language primitive declarations
        for decl_type in ("PipelineDecl", "ServiceDecl", "WorkflowDecl", "ContractDecl"):
            if type(stmt).__name__ == decl_type:
                self._check_primitive_decl(stmt, scope)
                return MCNType.ANY

        return MCNType.ANY

    def _check_primitive_decl(self, stmt: Any, scope: TypeScope):
        """Handle pipeline / service / workflow / contract declarations."""
        # All inner stages/endpoints/steps are function-like — check their bodies
        for attr in ("stages", "endpoints", "steps"):
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

        if isinstance(expr, ast.Index):
            obj_t = self._infer(expr.object, scope)
            if obj_t not in (MCNType.LIST, MCNType.DICT, MCNType.TUPLE, MCNType.ANY):
                self._error(
                    f"Subscript on non-indexable type '{obj_t.value}'",
                    expr.line, expr.col,
                )
            self._infer(expr.index, scope)
            return MCNType.ANY

        if isinstance(expr, ast.Property):
            self._infer(expr.object, scope)
            return MCNType.ANY  # property access always any for now

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
