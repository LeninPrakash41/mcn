"""
Print an MCN syntax tree back as MCN source.

    to_source(program)        canonical MCN for a whole Program
    print_stmt(stmt)          one statement or declaration, as lines
    same_tree(a, b)           two trees are the same program (positions ignored)

Parsing what `to_source` prints gives back the same tree. Comments and the original
layout aren't part of the tree, so they aren't printed; `msg.write_back` keeps the
original text of everything that didn't change.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any, List, Optional

from . import ast_nodes as ast

IND = "    "
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# Binary operators by precedence (higher binds tighter), as in the parser
_PREC = {"or": 1, "and": 2, "==": 3, "!=": 3, ">": 4, ">=": 4, "<": 4, "<=": 4,
         "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}
_UNARY, _POSTFIX, _ATOM, _LOWEST = 7, 8, 9, 0


class UnparseError(ValueError):
    pass


# ── Expressions ──────────────────────────────────────────────────────────────

def _string(value: str) -> str:
    out = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return f'"{out}"'


def _number(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = repr(float(value))
    if "e" in text or "inf" in text or "nan" in text:
        text = format(float(value), "f")
        if "." not in text:
            text += ".0"
    return text


def _literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (bool, int, float)):
        return _number(value)
    raise UnparseError(f"Can't print a literal {value!r}")


def _prec(e: Any) -> int:
    if isinstance(e, ast.Binary):
        return _PREC.get(e.operator, 1)
    if isinstance(e, (ast.TernaryExpr, ast.ArrowFunc)):
        return _LOWEST
    if isinstance(e, ast.Unary):
        return _UNARY
    if isinstance(e, ast.Literal) and isinstance(e.value, (int, float)) and not isinstance(e.value, bool) and e.value < 0:
        return _UNARY
    return _ATOM


def _wrap(e: Any, min_prec: int) -> str:
    text = expr(e)
    return f"({text})" if _prec(e) < min_prec else text


def expr(e: Any) -> str:
    if e is None:
        return "null"
    if isinstance(e, ast.Literal):
        return _literal(e.value)
    if isinstance(e, ast.Variable):
        return e.name
    if isinstance(e, ast.Binary):
        p = _PREC.get(e.operator)
        if p is None:
            raise UnparseError(f"Unknown operator '{e.operator}'")
        return f"{_wrap(e.left, p)} {e.operator} {_wrap(e.right, p + 1)}"
    if isinstance(e, ast.Unary):
        op = "not " if e.operator == "not" else e.operator
        return f"{op}{_wrap(e.operand, _UNARY)}"
    if isinstance(e, ast.Call):
        return f"{_wrap(e.callee, _POSTFIX)}({', '.join(expr(a) for a in e.arguments)})"
    if isinstance(e, ast.NamedArg):
        return f"{e.name} = {expr(e.value)}"
    if isinstance(e, ast.Index):
        return f"{_wrap(e.object, _POSTFIX)}[{expr(e.index)}]"
    if isinstance(e, ast.Property):
        return f"{_wrap(e.object, _POSTFIX)}{'?.' if e.safe else '.'}{e.name}"
    if isinstance(e, ast.Array):
        return "[" + ", ".join(expr(x) for x in e.elements) + "]"
    if isinstance(e, ast.MCNObject):
        parts = []
        for key, value in e.properties:
            k = key.name if isinstance(key, ast.Variable) else _string(str(key.value))
            parts.append(f"{k}: {expr(value)}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(e, ast.MCNTuple):
        items = [expr(x) for x in e.elements]
        return f"({items[0]},)" if len(items) == 1 else "(" + ", ".join(items) + ")"
    if isinstance(e, ast.TernaryExpr):
        # value if condition else other; the parser reads both sides of `if` at the `or` level
        return f"{_wrap(e.then_expr, 1)} if {_wrap(e.condition, 1)} else {expr(e.else_expr)}"
    if isinstance(e, ast.ArrowFunc):
        params = e.params[0] if len(e.params) == 1 else "(" + ", ".join(e.params) + ")"
        return f"{params} => {expr(e.body)}"
    raise UnparseError(f"Can't print a {type(e).__name__} as an expression")


# ── Statements ───────────────────────────────────────────────────────────────

def _block(stmts: List[Any], indent: str) -> List[str]:
    lines: List[str] = []
    for s in stmts:
        lines += print_stmt(s, indent)
    return lines


def _header_with_block(header: str, body: List[Any], indent: str) -> List[str]:
    if not body:
        return [f"{indent}{header} {{}}"]
    return [f"{indent}{header}"] + _block(body, indent + IND)


def _params(params: List[str], defaults: dict, types: Optional[dict] = None) -> str:
    out = []
    for p in params:
        text = p
        if types and p in types:
            text += f": {types[p]}"
        if p in (defaults or {}):
            text += f" = {expr(defaults[p])}"
        out.append(text)
    return ", ".join(out)


def print_stmt(s: Any, indent: str = "") -> List[str]:
    t = type(s)
    if t is ast.VarDecl:
        hint = f": {s.type_hint}" if s.type_hint else ""
        return [f"{indent}var {s.name}{hint} = {expr(s.value)}"]
    if t is ast.AssignStmt:
        return [f"{indent}{s.name} = {expr(s.value)}"]
    if t is ast.CompoundAssignStmt:
        return [f"{indent}{s.name} {s.op}= {expr(s.value)}"]
    if t is ast.PropertyAssignStmt:
        return [f"{indent}{_wrap(s.object, _POSTFIX)}.{s.prop} = {expr(s.value)}"]
    if t is ast.IndexAssignStmt:
        return [f"{indent}{_wrap(s.object, _POSTFIX)}[{expr(s.index)}] = {expr(s.value)}"]
    if t is ast.ExprStmt:
        e = s.expression
        if isinstance(e, ast.Call) and isinstance(e.callee, ast.Variable) and e.callee.name == "on":
            return [f"{indent}on " + " ".join(_wrap(a, _POSTFIX) for a in e.arguments)]
        return [f"{indent}{expr(e)}"]
    if t is ast.IfStmt:
        lines = _header_with_block(f"if {expr(s.condition)}", s.then_body, indent)
        else_body = s.else_body
        while len(else_body) == 1 and type(else_body[0]) is ast.IfStmt:
            inner = else_body[0]
            lines += _header_with_block(f"else if {expr(inner.condition)}", inner.then_body, indent)
            else_body = inner.else_body
        if else_body:
            lines += _header_with_block("else", else_body, indent)
        return lines
    if t is ast.ForStmt:
        names = f"{s.index_var}, {s.variable}" if s.index_var else s.variable
        return _header_with_block(f"for {names} in {expr(s.iterable)}", s.body, indent)
    if t is ast.WhileStmt:
        return _header_with_block(f"while {expr(s.condition)}", s.body, indent)
    if t is ast.TryStmt:
        lines = _header_with_block("try", s.try_body, indent)
        if s.catch_var is not None or s.catch_body:
            lines += _header_with_block("catch" + (f" {s.catch_var}" if s.catch_var else ""), s.catch_body, indent)
        if s.finally_body:
            lines += _header_with_block("finally", s.finally_body, indent)
        return lines
    if t is ast.ThrowStmt:
        return [f"{indent}throw {expr(s.message)}"]
    if t is ast.ReturnStmt:
        return [f"{indent}return" + (f" {expr(s.value)}" if s.value is not None else "")]
    if t is ast.BreakStmt:
        return [f"{indent}break"]
    if t is ast.ContinueStmt:
        return [f"{indent}continue"]
    if t is ast.AssertStmt:
        return [f"{indent}assert {expr(s.condition)}" + (f", {expr(s.message)}" if s.message is not None else "")]
    if t is ast.TaskStmt:
        parts = [s.name, s.function] + list(s.arguments)
        # Space-separated: a part in parentheses would read as a call on the part before it
        return [f"{indent}task " + " ".join(expr(p) for p in parts)]
    if t is ast.UseStmt:
        return [f"{indent}use {expr(s.package)}"]
    if t is ast.IncludeStmt:
        return [f"{indent}include {_string(s.path)}"]
    if t is ast.FunctionDecl:
        ret = f": {s.return_type}" if s.return_type else ""
        return _header_with_block(f"function {s.name}({_params(s.params, s.defaults, s.param_types)}){ret}",
                                  s.body, indent)
    if t is ast.TestDecl:
        return _header_with_block(f"test {_string(s.description)}", s.body, indent)
    if t is ast.ContractDecl:
        return [f"{indent}contract {s.name}"] + [f"{indent}{IND}{f.name}: {f.type_name}" for f in s.fields]
    if t is ast.ServiceDecl:
        inner = indent + IND
        lines = [f"{indent}service {s.name}"]
        if s.port is not None:
            lines.append(f"{inner}port {s.port}")
        if s.auth:
            lines.append(f"{inner}auth {_string(s.auth)}")
        if s.public:
            lines.append(f"{inner}public {', '.join(s.public)}")
        if s.audit:
            lines.append(f"{inner}audit")
        for ep in s.endpoints:
            lines.append("")
            lines += _header_with_block(f"endpoint {ep.name}({_params(ep.params, ep.defaults, ep.param_types)})",
                                        ep.body, inner)
        return lines
    if t in (ast.PipelineDecl, ast.WorkflowDecl):
        word, items, item_word = ("pipeline", s.stages, "stage") if t is ast.PipelineDecl else ("workflow", s.steps, "step")
        lines = [f"{indent}{word} {s.name}"]
        for item in items:
            params = f"({_params(item.params, item.defaults)})" if item.params else ""
            lines += _header_with_block(f"{item_word} {item.name}{params}", item.body, indent + IND)
        return lines
    if t is ast.ScheduleDecl:
        return _header_with_block(f"schedule {s.name} at {_string(s.cron_expr)}", s.body, indent)
    if t is ast.PromptDecl:
        inner = indent + IND
        lines = [f"{indent}prompt {s.name}"]
        if s.system:
            lines.append(f"{inner}system {_string(s.system)}")
        if s.user:
            lines.append(f"{inner}user {_string(s.user)}")
        lines.append(f"{inner}format {s.format if _IDENT.match(s.format or '') else _string(s.format)}")
        return lines
    if t is ast.AgentDecl:
        inner = indent + IND
        lines = [f"{indent}agent {s.name}"]
        if s.model:
            lines.append(f"{inner}model {_string(s.model)}")
        if s.tools:
            lines.append(f"{inner}tools {', '.join(s.tools)}")
        if s.memory:
            lines.append(f"{inner}memory {s.memory if _IDENT.match(s.memory) else _string(s.memory)}")
        for task in s.tasks:
            params = f"({_params(task.params, task.defaults)})" if task.params else ""
            lines += _header_with_block(f"task {task.name}{params}", task.body, inner)
        if len(lines) == 1:
            lines.append(f"{inner}memory \"\"")
        return lines
    if t is ast.MCPServerDecl:
        inner = indent + IND
        lines = [f"{indent}mcp {s.name}", f"{inner}transport {_string(s.transport)}"]
        if s.command:
            lines.append(f"{inner}command {_string(s.command)}")
        if s.args:
            lines.append(f"{inner}args [" + ", ".join(_string(a) for a in s.args) + "]")
        if s.url:
            lines.append(f"{inner}url {_string(s.url)}")
        for tool in s.tools:
            lines.append(f"{inner}tool {tool.name}" + (f"({', '.join(tool.params)})" if tool.params else ""))
        return lines
    if t is ast.ComponentDecl:
        return _component(s, indent)
    if t is ast.AppDecl:
        return _app(s, indent)
    if t is ast.ModuleDecl:
        raise UnparseError("A module is printed with its members; use to_source")
    raise UnparseError(f"Can't print a {t.__name__} as a statement")


# ── UI ───────────────────────────────────────────────────────────────────────

def _attr_value(v: Any) -> str:
    if isinstance(v, (ast.Literal, ast.Variable, ast.Array, ast.MCNObject)):
        return expr(v)
    return "{" + expr(v) + "}"


def _ui(el: ast.UIElement, indent: str) -> List[str]:
    if el.tag == "for":
        lines = [f"{indent}for {el.for_var} in {expr(el.for_iterable)}"]
    else:
        parts = [el.tag]
        for a in el.attrs:
            parts.append(a.key if a.value is None else f"{a.key}={_attr_value(a.value)}")
        if el.text is not None:
            parts.append(_string(el.text.value) if isinstance(el.text, ast.Literal) and isinstance(el.text.value, str)
                         else "{" + expr(el.text) + "}")
        lines = [indent + " ".join(parts)]
    for child in el.children:
        lines += _ui(child, indent + IND)
    return lines


def _component(s: ast.ComponentDecl, indent: str) -> List[str]:
    inner = indent + IND
    lines = [f"{indent}component {s.name}"]
    for st in s.states:
        lines.append(f"{inner}state {st.name} = {expr(st.value)}")
    for h in s.handlers:
        lines.append("")
        lines += _header_with_block(f"on {h.event}", h.body, inner)
    if s.render is not None:
        lines.append("")
        lines.append(f"{inner}render")
        for el in s.render.elements:
            lines += _ui(el, inner + IND)
    if len(lines) == 1:
        lines.append(f"{inner}render")
    return lines


def _app(s: ast.AppDecl, indent: str) -> List[str]:
    inner = indent + IND
    lines = [f"{indent}app {s.name}"]
    if s.title:
        lines.append(f"{inner}title {_string(s.title)}")
    if s.theme and s.theme != "default":
        lines.append(f"{inner}theme {_string(s.theme)}")
    if s.logo:
        lines.append(f"{inner}logo {_string(s.logo)}")
    if s.footer:
        lines.append(f"{inner}footer {_string(s.footer)}")
    lay = s.layout
    if lay is not None:
        l1, l2, l3 = inner + IND, inner + IND * 2, inner + IND * 3
        lines.append(f"{l1[:-len(IND)]}layout")
        if lay.sidebar:
            lines.append(f"{l1}sidebar")
            for n in lay.sidebar:
                parts = [f"nav {_string(n.label)}"]
                if n.component:
                    parts.append(n.component)
                if n.icon:
                    parts.append(f"icon={_string(n.icon)}")
                if n.group:
                    parts.append(f"group={_string(n.group)}")
                lines.append(l2 + " ".join(parts))
        if lay.tabs:
            lines.append(f"{l1}tabs")
            for tab in lay.tabs:
                lines.append(f"{l2}tab {_string(tab.label)}" + (f" {tab.component}" if tab.component else ""))
        if lay.main:
            lines.append(f"{l1}main")
            lines += [f"{l2}{m}" for m in lay.main]
        if lay.routes:
            lines.append(f"{l1}routes")
            lines += [f"{l2}route {_string(r.path)}" + (f" {r.component}" if r.component else "") for r in lay.routes]
        del l3
    if len(lines) == 1:
        lines.append(f"{inner}title {_string(s.name)}")
    return lines


# ── Programs and modules ─────────────────────────────────────────────────────

def units(body: List[Any]) -> List[List[Any]]:
    """Top-level statements grouped into units: a module with its members, or one statement.
    A module's members are the statements after it up to its last line; new statements
    (line 0) right after a member join the module too."""
    out: List[List[Any]] = []
    i = 0
    while i < len(body):
        stmt = body[i]
        if isinstance(stmt, ast.ModuleDecl):
            group = [stmt]
            i += 1
            while i < len(body) and not isinstance(body[i], ast.ModuleDecl):
                line = getattr(body[i], "line", 0) or 0
                if (line and stmt.end_line and stmt.line <= line <= stmt.end_line) or (not line and len(group) > 1) \
                        or (not stmt.end_line and not line):
                    group.append(body[i])
                    i += 1
                else:
                    break
            out.append(group)
        else:
            out.append([stmt])
            i += 1
    return out


def print_unit(unit: List[Any]) -> List[str]:
    first = unit[0]
    if not isinstance(first, ast.ModuleDecl):
        return print_stmt(first)
    lines = [f"module {first.name}"]
    if first.owns:
        lines.append(f"{IND}owns {', '.join(first.owns)}")
    for member in unit[1:]:
        lines.append("")
        lines += print_stmt(member, IND)
    if len(lines) == 1:
        raise UnparseError(f"module {first.name} needs at least one line: owns or a declaration")
    return lines


def to_source(program: ast.Program) -> str:
    chunks = ["\n".join(print_unit(u)) for u in units(program.body)]
    return "\n\n".join(chunks) + "\n"


# ── Comparing trees ──────────────────────────────────────────────────────────

_POSITION = {"line", "col", "end_line"}


def _strip(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__,) + tuple((f.name, _strip(getattr(value, f.name)))
                                               for f in dataclasses.fields(value) if f.name not in _POSITION)
    if isinstance(value, dict):
        return tuple(sorted((k, _strip(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_strip(v) for v in value)
    return value


def same_tree(a: Any, b: Any) -> bool:
    """Same program, ignoring where things are in the file."""
    return _strip(a) == _strip(b)
