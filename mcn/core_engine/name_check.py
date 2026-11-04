"""
Static check for names that are never defined anywhere in a program.

Deliberately conservative: a name counts as defined if it is declared
*anywhere* in the file (any scope, any order) or is a runtime built-in, so
the check only reports what is certain to fail when reached, typically a typo.
Files whose names can't be known statically (an `include`, or a `use` of a
package that isn't installed) are skipped.
"""
from dataclasses import fields, is_dataclass
from typing import Iterator, List, Optional, Set, Tuple

from . import ast_nodes as ast

# Nodes whose `name` field declares something callable or referenceable.
# (Variable, Property, NamedArg, ContractField ... use `name` for other things.)
_DECLARING = (
    ast.VarDecl, ast.FunctionDecl, ast.AssignStmt, ast.CompoundAssignStmt,
    ast.ContractDecl, ast.StageDecl, ast.PipelineDecl, ast.EndpointDecl,
    ast.ServiceDecl, ast.ScheduleDecl, ast.StepDecl, ast.WorkflowDecl,
    ast.PromptDecl, ast.AgentTaskDecl, ast.AgentDecl, ast.MCPToolDecl,
    ast.MCPServerDecl, ast.ComponentStateDecl, ast.ComponentDecl, ast.AppDecl,
)

# Handlers the UI compiler generates for CRUD tables and edit modals, and the
# value a handler wired to a kit component receives (`on delete` gets `row`, …)
_UI_COMPILER_NAMES = {"handleSave", "handleEdit", "handleDelete",
                      "row", "item", "agent", "workflow", "message"}

_runtime_names: Optional[Set[str]] = None


def runtime_names() -> Set[str]:
    """Every name a fresh interpreter can resolve before running any code."""
    global _runtime_names
    if _runtime_names is None:
        import contextlib, io
        from .mcn_interpreter import MCNInterpreter
        from .test_runner import TestRunner
        helpers: dict = {}
        with contextlib.redirect_stdout(io.StringIO()):
            ev = MCNInterpreter()._evaluator
            TestRunner()._register_builtins(helpers)     # assert_equal & co. for test blocks
        _runtime_names = set(ev.functions) | set(ev.globals.as_dict) | set(helpers)
    return _runtime_names


def _children(node) -> Iterator:
    for f in fields(node):
        value = getattr(node, f.name)
        items = value if isinstance(value, list) else \
            list(value.values()) if isinstance(value, dict) else [value]
        for item in items:
            if isinstance(item, tuple):
                yield from (x for x in item if is_dataclass(x))
            elif is_dataclass(item):
                yield item


def _walk(node) -> Iterator:
    yield node
    for child in _children(node):
        yield from _walk(child)


def _package_names(spec: str) -> Optional[Set[str]]:
    from .mcn_packages import get_registry, PackageNotFoundError
    try:
        exports = get_registry().load(spec)
    except (PackageNotFoundError, Exception):
        return None
    return set(exports) | {spec.split("/")[-1].replace("-", "_")}


def _use_spec(stmt: ast.UseStmt) -> Optional[str]:
    pkg = stmt.package
    if isinstance(pkg, ast.Literal):
        return str(pkg.value)
    return getattr(pkg, "name", None)


def undefined_names(program: ast.Program) -> List[Tuple[str, int, int, str]]:
    """Return (name, line, col, kind) for each reference to a never-defined name.

    kind is "function" for a call, "variable" otherwise.
    """
    nodes = list(_walk(program))
    defined = set(runtime_names())
    is_ui_file = False

    for n in nodes:
        if isinstance(n, ast.IncludeStmt):
            return []
        if isinstance(n, ast.UseStmt):
            spec = _use_spec(n)
            names = _package_names(spec) if spec else None
            if names is None:
                return []
            defined |= names
        if isinstance(n, (ast.ComponentDecl, ast.AppDecl)):
            is_ui_file = True
            defined |= _UI_COMPILER_NAMES
        if isinstance(n, _DECLARING) and isinstance(n.name, str):
            defined.add(n.name)
        for attr in ("params",):
            defined.update(p for p in getattr(n, attr, []) or [] if isinstance(p, str))
        if isinstance(n, ast.ForStmt):
            defined.update(v for v in (n.variable, n.index_var) if v)
        if isinstance(n, ast.TryStmt):
            defined.add(n.catch_var or "error")   # bare `catch` binds `error`
        if isinstance(n, ast.UIElement) and n.for_var:
            defined.add(n.for_var)
        if isinstance(n, ast.OnHandler):
            defined.add(n.event)        # on submit → referenced as {submit}

    callees = {id(n.callee) for n in nodes if isinstance(n, ast.Call)}
    # {success: true} — bare object keys parse as Variables but are just labels
    keys = {id(k) for n in nodes if isinstance(n, ast.MCNObject) for k, _ in n.properties}
    # chat endpoint=ask_bot / data_table on_delete=remove: names a backend endpoint or a handler
    if is_ui_file:
        keys |= {id(n.value) for n in nodes if isinstance(n, ast.UIAttr) and isinstance(n.value, ast.Variable)
                 and (n.key == "endpoint" or n.key.startswith("on_"))}
    found = []
    for n in nodes:
        if not isinstance(n, ast.Variable) or n.name in defined or id(n) in keys:
            continue
        is_call = id(n) in callees
        # UI files call the backend's endpoints, which live in another file
        if is_call and is_ui_file:
            continue
        found.append((n.name, n.line, n.col, "function" if is_call else "variable"))
    return found


def did_you_mean(name: str, program: ast.Program) -> str:
    from .evaluator import _did_you_mean
    candidates = {n.name for n in _walk(program) if isinstance(n, _DECLARING) and isinstance(n.name, str)}
    for n in _walk(program):
        candidates.update(p for p in getattr(n, "params", []) or [] if isinstance(p, str))
    return _did_you_mean(name, sorted(candidates | runtime_names()))
