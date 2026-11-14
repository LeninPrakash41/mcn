"""
A map of an MCN app, read from its source without running it, for people and AI agents.

    mcn describe [folder] [--json]      what the app is made of and how the parts connect
    mcn impact <name>... [--json]        what a change to tables, endpoints, functions, contracts
    mcn impact --changed [--base REF]    or screens would affect, and which tests cover it

The map lists tables, services and endpoints (with auth, audit, and the tables each one
reads and writes), functions, contracts, workflows, schedules, tests, screens and the app's
navigation, plus the edges between them: a screen calls an endpoint, an endpoint calls a
function and writes a table, a test covers what it calls. It also points out problems an
agent should fix: calls to endpoints that don't exist, navigation to missing screens,
endpoints nothing uses, and endpoints no test covers.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import fields as dc_fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import ast_nodes as ast
from .lexer import Lexer
from .parser import Parser

_SQL_READ = re.compile(r"\b(?:FROM|JOIN)\s+[\"`]?(\w+)", re.I)
_SQL_WRITE = re.compile(r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\s+[\"`]?(\w+)", re.I)
_SQL_CREATE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)", re.I)
_SQL_KEYWORDS = {"select", "where", "set", "values", "table", "dual", "information_schema"}


# ── Walking the syntax tree ───────────────────────────────────────────────────

def _walk(node: Any) -> Iterable[Any]:
    """Every node below `node` (statements, expressions, UI elements)."""
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, (list, tuple)):
            stack.extend(reversed(n))
            continue
        if isinstance(n, dict):
            stack.extend(n.values())
            continue
        if not is_dataclass(n):
            continue
        yield n
        for f in dc_fields(n):
            value = getattr(n, f.name, None)
            if is_dataclass(value) or isinstance(value, (list, tuple, dict)):
                stack.append(value)


def _calls(node: Any) -> Set[str]:
    return {n.callee.name for n in _walk(node) if isinstance(n, ast.Call) and isinstance(n.callee, ast.Variable)}


def _names(node: Any) -> Set[str]:
    return {n.name for n in _walk(node) if isinstance(n, ast.Variable)}


def _strings(node: Any) -> List[str]:
    return [n.value for n in _walk(node) if isinstance(n, ast.Literal) and isinstance(n.value, str)]


def _sql_tables(node: Any) -> Tuple[Set[str], Set[str]]:
    reads, writes = set(), set()
    for text in _strings(node):
        if not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|REPLACE)\b", text, re.I):
            continue
        w = {t for t in _SQL_WRITE.findall(text)}
        writes |= w
        # DELETE FROM t counts as a write, not a read
        reads |= {t for t in _SQL_READ.findall(re.sub(r"\bDELETE\s+FROM\s+\w+", "", text, flags=re.I))}
    clean = lambda s: {t for t in s if t.lower() not in _SQL_KEYWORDS}
    return clean(reads), clean(writes)


def _ui_names(elements: List[Any]) -> Tuple[Set[str], Set[str]]:
    """(tags used, names referenced in attributes) for a render tree."""
    tags, refs = set(), set()
    for el in _walk(elements):
        if isinstance(el, ast.UIElement):
            tags.add(el.tag)
            for attr in el.attrs:
                if isinstance(attr.value, ast.Variable):
                    refs.add(attr.value.name)
                refs |= _calls(attr.value) if attr.value is not None else set()
    return tags, refs


def _implicit_crud(comp: Any, columns: List[str], endpoints: Dict[str, List[str]]) -> Set[str]:
    """The endpoints a table screen's generated buttons call (mirrors ui_compiler): create_, update_ and
    delete_<entity> when the backend has them and the table supplies their parameters (all three when
    there's no backend), and list_<entities> to refresh the table after one of them."""
    if not (columns or any(s.name == "edit_item" for s in comp.states)):
        return set()
    from .ui_compiler import _get_entity_names, crud_endpoint_fits
    one, many = _get_entity_names(comp.name, set(endpoints))
    edit_cols = [s.name[5:] for s in comp.states if s.name.startswith("edit_")]
    ops = {f"{verb}_{one}" for verb in ("create", "update", "delete")
           if crud_endpoint_fits(f"{verb}_{one}", columns + (edit_cols if verb == "update" else []), endpoints)}
    return ops | {f"list_{many}"} if ops else set()


def _table_columns(elements: List[Any]) -> List[str]:
    cols: List[str] = []
    for el in elements or []:
        if getattr(el, "tag", None) == "table_head" and isinstance(getattr(el, "text", None), ast.Literal):
            col = str(el.text.value).strip("\"'")
            if col and col not in cols:
                cols.append(col)
        else:
            cols.extend(c for c in _table_columns(getattr(el, "children", [])) if c not in cols)
    return cols



# ── Building the map ──────────────────────────────────────────────────────────

def _parse(path: Path) -> Tuple[Optional[ast.Program], Optional[str]]:
    try:
        parser = Parser(Lexer(path.read_text(encoding="utf-8")).tokenize())
        program = parser.parse()
    except Exception as exc:
        return None, str(exc)
    return program, (str(parser.errors[0]) if getattr(parser, "errors", None) else None)


def _source_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    skip = {"node_modules", ".mcn", "frontend", "mobile", "dist", "build", ".git"}
    return sorted(p for p in root.rglob("*.mcn") if not skip & set(p.relative_to(root).parts))


def _ranges(body: List[Any], end_line: int) -> List[Tuple[Any, int, int]]:
    """(node, first line, last line) for each declaration in a list of statements."""
    out = []
    for i, node in enumerate(body):
        start = getattr(node, "line", 0) or 0
        nxt = next((getattr(n, "line", 0) for n in body[i + 1:] if getattr(n, "line", 0)), 0)
        out.append((node, start, (nxt - 1) if nxt else end_line))
    return out


def build_map(root: Any) -> Dict[str, Any]:
    root = Path(root).resolve()
    base = root if root.is_dir() else root.parent
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, str]] = []
    errors: List[str] = []
    pending: List[Tuple[str, Set[str], Set[str], Set[str], Set[str]]] = []   # (id, calls, names, reads, writes)
    crud_screens: List[Tuple[str, Any, Set[str]]] = []

    current_module: List[Any] = [None]       # (name, file, first line, last line) of the module being read

    def add(kind: str, name: str, path: Path, start: int, end: int, **info) -> str:
        node_id = f"{kind}:{name}"
        file = str(path.relative_to(base))
        nodes[node_id] = {"id": node_id, "kind": kind, "name": name,
                          "file": file, "line": start, "end_line": end, **info}
        mod = current_module[0]
        if kind not in ("module", "table") and mod and mod[1] == file and mod[2] <= start <= mod[3]:
            nodes[node_id]["module"] = mod[0]
        return node_id

    for path in _source_files(root):
        program, error = _parse(path)
        if program is None or error:
            errors.append(f"{path.relative_to(base)}: {error}")
            if program is None:
                continue
        last = len(path.read_text(encoding="utf-8").splitlines())
        for text in _strings(program):
            for table in _SQL_CREATE.findall(text):
                if f"table:{table}" not in nodes:
                    add("table", table, path, 0, 0)
        current_module[0] = None
        for stmt, start, end in _ranges(program.body, last):
            if isinstance(stmt, ast.ModuleDecl):
                file = str(path.relative_to(base))
                existing = nodes.get(f"module:{stmt.name}")
                if existing and file in existing["files"]:
                    errors.append(f"{file}: module '{stmt.name}' is declared twice")
                elif existing:            # the same module's screens in ui/, its endpoints in backend/
                    existing["files"].append(file)
                    existing["owns"] += [t for t in stmt.owns if t not in existing["owns"]]
                else:
                    add("module", stmt.name, path, stmt.line, stmt.end_line, owns=list(stmt.owns), files=[file])
                current_module[0] = (stmt.name, str(path.relative_to(base)), stmt.line, stmt.end_line)
                continue
            mod = current_module[0]
            if mod and start > mod[3]:
                current_module[0] = None
            if isinstance(stmt, ast.ServiceDecl):
                svc = add("service", stmt.name, path, start, end, auth=stmt.auth or None, audit=stmt.audit,
                          port=stmt.port, endpoints=[e.name for e in stmt.endpoints])
                for ep, ep_start, ep_end in _ranges(stmt.endpoints, end):
                    reads, writes = _sql_tables(ep.body)
                    ep_id = add("endpoint", ep.name, path, ep_start, ep_end, service=stmt.name, params=list(ep.params),
                                types=dict(getattr(ep, "param_types", {}) or {}),
                                auth=None if ep.name in stmt.public else (stmt.auth or None), audited=stmt.audit,
                                reads=sorted(reads), writes=sorted(writes))
                    edges.append({"from": svc, "to": ep_id, "kind": "contains"})
                    pending.append((ep_id, _calls(ep.body), _names(ep.body), reads, writes))
            elif isinstance(stmt, ast.FunctionDecl):
                reads, writes = _sql_tables(stmt.body)
                fn_id = add("function", stmt.name, path, start, end, params=list(stmt.params),
                            reads=sorted(reads), writes=sorted(writes))
                pending.append((fn_id, _calls(stmt.body), _names(stmt.body), reads, writes))
            elif isinstance(stmt, ast.ContractDecl):
                add("contract", stmt.name, path, start, end,
                    fields={f.name: getattr(f, "type_name", None) or getattr(f, "type", None) for f in stmt.fields})
            elif isinstance(stmt, ast.TestDecl):
                t_id = add("test", stmt.description, path, start, end)
                pending.append((t_id, _calls(stmt.body), _names(stmt.body), set(), set()))
            elif isinstance(stmt, (ast.WorkflowDecl, ast.ScheduleDecl)):
                kind = "workflow" if isinstance(stmt, ast.WorkflowDecl) else "schedule"
                reads, writes = _sql_tables(stmt)
                w_id = add(kind, stmt.name, path, start, end, reads=sorted(reads), writes=sorted(writes))
                pending.append((w_id, _calls(stmt), _names(stmt), reads, writes))
            elif isinstance(stmt, ast.ComponentDecl):
                tags, refs = _ui_names(stmt.render.elements if stmt.render else [])
                handlers = ast.Program(body=[s for h in stmt.handlers for s in h.body])
                c_id = add("component", stmt.name, path, start, end,
                           states=[s.name for s in stmt.states], handlers=[h.event for h in stmt.handlers],
                           generated_calls=[])
                crud_screens.append((c_id, stmt, tags))
                pending.append((c_id, _calls(handlers) | (refs - {s.name for s in stmt.states}), _names(handlers) | tags,
                                set(), set()))
            elif isinstance(stmt, ast.AppDecl):
                layout = stmt.layout
                items = [(n.label, n.component or n.label.replace(" ", "")) for n in (layout.sidebar if layout else [])] + \
                        [(t.label, t.component or t.label.replace(" ", "")) for t in (layout.tabs if layout else [])] + \
                        [(m, m) for m in (layout.main if layout else [])]
                a_id = add("app", stmt.name, path, start, end, title=stmt.title or stmt.name,
                           navigation=[{"label": label, "screen": comp} for label, comp in items])
                pending.append((a_id, set(), {comp for _, comp in items}, set(), set()))

    # Resolve references now that every declaration is known
    endpoint_params = {n["name"]: n["params"] for n in nodes.values() if n["kind"] == "endpoint"}
    for c_id, comp, tags in crud_screens:
        generated = _implicit_crud(comp, _table_columns(comp.render.elements if comp.render else []), endpoint_params)
        nodes[c_id]["generated_calls"] = sorted(generated)
        for i, entry in enumerate(pending):
            if entry[0] == c_id:
                pending[i] = (c_id, entry[1] | generated, *entry[2:])
    by_name: Dict[str, List[str]] = {}
    for node_id, node in nodes.items():
        by_name.setdefault(node["name"], []).append(node_id)
    issues: List[Dict[str, str]] = []
    endpoint_names = {n["name"] for n in nodes.values() if n["kind"] == "endpoint"}
    for src, calls, names, reads, writes in pending:
        kind = nodes[src]["kind"]
        for name in sorted(calls | names):
            for target in by_name.get(name, []):
                t_kind = nodes[target]["kind"]
                if target == src or t_kind in ("table", "service", "app", "test"):
                    continue
                if t_kind == "component" and kind not in ("component", "app"):
                    continue
                relation = {"contract": "uses", "component": "shows" if kind == "app" else "renders"}.get(t_kind, "calls")
                edges.append({"from": src, "to": target, "kind": "covers" if kind == "test" else relation})
        for table in sorted(reads):
            edges.append({"from": src, "to": f"table:{table}", "kind": "reads"})
            if f"table:{table}" not in nodes:
                issues.append({"kind": "unknown_table", "where": src, "message": f"{src} reads table '{table}', which no CREATE TABLE defines"})
        for table in sorted(writes):
            edges.append({"from": src, "to": f"table:{table}", "kind": "writes"})
            if f"table:{table}" not in nodes:
                issues.append({"kind": "unknown_table", "where": src, "message": f"{src} writes table '{table}', which no CREATE TABLE defines"})
        if kind == "component":
            known = set(by_name) | _BUILTIN_CALLS
            generated = nodes[src].get("generated_calls", [])
            for name in sorted(calls - known):
                if re.fullmatch(r"[a-z_][a-z0-9_]*", name) and name not in nodes[src]["handlers"]:
                    message = (f"{src}'s table buttons call '{name}', which the backend doesn't have"
                               if name in generated else f"{src} calls '{name}', which isn't an endpoint or function")
                    issues.append({"kind": "unknown_endpoint", "where": src, "message": message})
        if kind == "app":
            for item in nodes[src]["navigation"]:
                if f"component:{item['screen']}" not in nodes:
                    issues.append({"kind": "missing_screen", "where": src,
                                   "message": f"Navigation item '{item['label']}' shows '{item['screen']}', which isn't a component"})

    issues.extend(_module_rules(nodes, edges))
    edges = [dict(t) for t in {tuple(sorted(e.items())) for e in edges}]
    edges.sort(key=lambda e: (e["from"], e["kind"], e["to"]))
    used = {e["to"] for e in edges if e["kind"] in ("calls", "covers")}
    covered = {e["to"] for e in edges if e["kind"] == "covers"}
    has_ui = any(n["kind"] == "component" for n in nodes.values())
    for node in nodes.values():
        if node["kind"] == "endpoint":
            if has_ui and node["id"] not in used:
                issues.append({"kind": "unused_endpoint", "severity": "note", "where": node["id"],
                               "message": f"Nothing calls {node['id']} (no screen, function or test)"})
            node["tested"] = node["id"] in covered
    return {"root": str(base), "nodes": dict(sorted(nodes.items())), "edges": edges, "issues": issues,
            "errors": errors, "summary": _summary(nodes, edges, issues)}


def _module_rules(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Ownership: each table has at most one owning module, and only that module writes it.
    Also fills in each module's members and the other modules it depends on."""
    issues: List[Dict[str, str]] = []
    modules = {n["name"]: n for n in nodes.values() if n["kind"] == "module"}
    if not modules:
        return issues
    owner: Dict[str, str] = {}
    for mod in modules.values():
        for table in mod["owns"]:
            if table in owner and owner[table] != mod["name"]:
                issues.append({"kind": "shared_ownership", "where": mod["id"],
                               "message": f"Table '{table}' is owned by both module {owner[table]} and module {mod['name']}"})
                continue
            owner[table] = mod["name"]
            if f"table:{table}" in nodes:
                nodes[f"table:{table}"]["owner"] = mod["name"]
                edges.append({"from": mod["id"], "to": f"table:{table}", "kind": "owns"})
            else:
                issues.append({"kind": "unknown_table", "where": mod["id"],
                               "message": f"module {mod['name']} owns table '{table}', which no CREATE TABLE defines"})
        mod["members"] = sorted(n["id"] for n in nodes.values() if n.get("module") == mod["name"])
        mod["depends_on"] = []
    for node in nodes.values():
        for table in node.get("writes", []) or []:
            if table in owner and node.get("module") != owner[table]:
                where = f"module {node['module']}" if node.get("module") else "code outside any module"
                issues.append({"kind": "foreign_write", "where": node["id"],
                               "message": f"{node['id']} ({where}) writes table '{table}', which module {owner[table]} owns"})
    for e in edges:
        src, dst = nodes.get(e["from"], {}), nodes.get(e["to"], {})
        mine = src.get("module")
        theirs = dst.get("module") or (dst.get("owner") if dst.get("kind") == "table" else None)
        if mine and theirs and mine != theirs and e["kind"] in ("calls", "reads", "writes", "uses"):
            deps = modules[mine]["depends_on"]
            if theirs not in deps:
                deps.append(theirs)
                deps.sort()
    return issues


_BUILTIN_CALLS = {"notify", "toast", "log", "confirm", "alert", "str", "len", "int", "float", "round", "abs",
                  "min", "max", "upper", "lower", "join", "trim", "contains", "push", "map", "filter", "sum",
                  "now", "navigate", "go", "set_token"}


def _summary(nodes, edges, issues) -> Dict[str, int]:
    count = lambda kind: sum(1 for n in nodes.values() if n["kind"] == kind)
    endpoints = [n for n in nodes.values() if n["kind"] == "endpoint"]
    return {"tables": count("table"), "endpoints": count("endpoint"), "functions": count("function"),
            "screens": count("component"), "tests": count("test"), "contracts": count("contract"),
            "workflows": count("workflow"), "schedules": count("schedule"), "modules": count("module"),
            "untested_endpoints": sum(1 for e in endpoints if not e.get("tested")), "issues": len(issues)}


# ── Impact ────────────────────────────────────────────────────────────────────

def resolve(app_map: Dict[str, Any], target: str) -> List[str]:
    """Node ids for a name (`orders`), a typed name (`table:orders`) or `file.mcn:LINE`."""
    nodes = app_map["nodes"]
    if target in nodes:
        return [target]
    m = re.fullmatch(r"(.+\.mcn):(\d+)", target)
    if m:
        line = int(m.group(2))
        hits = [n["id"] for n in nodes.values() if n["file"].endswith(m.group(1)) and n["line"] <= line <= n["end_line"]
                and n["kind"] != "service"]
        return hits or [n["id"] for n in nodes.values() if n["file"].endswith(m.group(1)) and n["line"] <= line <= n["end_line"]]
    return [n["id"] for n in nodes.values() if n["name"] == target]


def impact(app_map: Dict[str, Any], targets: List[str]) -> Dict[str, Any]:
    """What depends on the targets (callers, readers, screens, navigation) and which tests cover them."""
    nodes, edges = app_map["nodes"], app_map["edges"]
    start: Set[str] = set()
    unknown = []
    for t in targets:
        ids = resolve(app_map, t)
        start |= set(ids)
        if not ids:
            unknown.append(t)
    for mod_id in [i for i in start if nodes[i]["kind"] == "module"]:      # a module: everything in it
        start |= {i for i in nodes[mod_id].get("members", []) if not i.startswith("service:")} | {f"table:{t}" for t in nodes[mod_id]["owns"]
                                                          if f"table:{t}" in nodes}
    dependents: Dict[str, List[Tuple[str, str]]] = {}
    for e in edges:
        if e["kind"] in ("calls", "renders", "shows", "uses", "reads", "writes", "contains"):
            dependents.setdefault(e["to"], []).append((e["from"], e["kind"]))
    affected: Dict[str, str] = {}
    queue = list(start)
    while queue:
        current = queue.pop()
        for parent, kind in dependents.get(current, []):
            if parent in start or parent in affected or nodes[parent]["kind"] == "service":
                continue
            affected[parent] = f"{kind} {current}"
            queue.append(parent)
    scope = start | set(affected)
    tests = sorted({e["from"] for e in edges if e["kind"] == "covers" and e["to"] in scope})
    touched_code = [i for i in scope if nodes[i]["kind"] in ("endpoint", "function")]
    covered = {e["to"] for e in edges if e["kind"] == "covers"}
    group = lambda kind: sorted([{"id": i, "why": affected[i]} for i in affected if nodes[i]["kind"] == kind],
                                key=lambda d: d["id"])
    screens = [i for i in scope if nodes[i]["kind"] == "component"]
    navigation = sorted({item["label"] for n in nodes.values() if n["kind"] == "app" for item in n["navigation"]
                         if f"component:{item['screen']}" in screens})
    return {
        "targets": sorted(start), "unknown": unknown,
        "affected": {"endpoints": group("endpoint"), "functions": group("function"), "screens": group("component"),
                     "workflows": group("workflow") + group("schedule"), "tables": group("table")},
        "navigation": navigation,
        "tests": tests,
        "untested": sorted(i for i in touched_code if i not in covered),
        "files": sorted({nodes[i]["file"] for i in scope}),
        "modules": sorted({nodes[i].get("module") or nodes[i].get("owner") for i in scope} - {None}),
    }


def outside_module(app_map: Dict[str, Any], changed: List[str], module: str) -> List[str]:
    """Changed declarations that don't belong to `module`: its members, the module itself and the tables it owns.
    An agent assigned one module should change nothing else."""
    nodes = app_map["nodes"]
    if f"module:{module}" not in nodes:
        raise ValueError(f"No module named '{module}'")
    inside = lambda i: (i == f"module:{module}" or nodes.get(i, {}).get("module") == module
                        or nodes.get(i, {}).get("owner") == module)
    return sorted(i for i in changed if not inside(i))


def changed_targets(root: Any, base_ref: str = "HEAD") -> List[str]:
    """Declarations touched by uncommitted changes (or changes since base_ref), from `git diff`."""
    root = Path(root).resolve()
    work = root if root.is_dir() else root.parent
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=work, capture_output=True, text=True,
                             check=True).stdout.strip()
        diff = subprocess.run(["git", "diff", "-U0", base_ref, "--", "*.mcn"], cwd=work, capture_output=True,
                              text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Couldn't read changes from git: {getattr(exc, 'stderr', '') or exc}")
    current = build_map(root)
    hits: Set[str] = set()
    file = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            file = None if line[4:] == "/dev/null" else line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if not m or not file:
            continue
        new_start, new_len = int(m.group(3)), int(m.group(4) or 1)
        lines = range(new_start, new_start + max(new_len, 1))
        absolute = (Path(top) / file).resolve()
        for node in current["nodes"].values():
            node_file = (Path(current["root"]) / node["file"]).resolve()
            if node_file == absolute and node["kind"] not in ("service", "table", "module") and \
                    any(node["line"] <= ln <= node["end_line"] for ln in lines):
                hits.add(node["id"])
            if node_file == absolute and node["kind"] == "module":
                members = [current["nodes"][i] for i in node.get("members", [])]
                if any(node["line"] <= ln <= node["end_line"] and
                       not any(m["line"] <= ln <= m["end_line"] for m in members) for ln in lines):
                    hits.add(node["id"])             # its own lines: the header or `owns`
    # Tables whose CREATE TABLE line changed
    for line in diff.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            for table in _SQL_CREATE.findall(line):
                if f"table:{table}" in current["nodes"]:
                    hits.add(f"table:{table}")
    return sorted(hits)


# ── Text output ───────────────────────────────────────────────────────────────

def render_map(app_map: Dict[str, Any]) -> str:
    nodes, edges = app_map["nodes"], app_map["edges"]
    out = []
    s = app_map["summary"]
    out.append(f"{s['screens']} screens · {s['endpoints']} endpoints · {s['tables']} tables · {s['functions']} functions · "
               f"{s['tests']} tests" + (f" · {s['modules']} modules" if s.get("modules") else ""))
    out_edges = lambda src, kinds: [e["to"].split(":", 1)[1] for e in edges if e["from"] == src and e["kind"] in kinds]
    for app in (n for n in nodes.values() if n["kind"] == "app"):
        out.append(f"\nApp {app['title']}")
        for item in app["navigation"]:
            out.append(f"  {item['label']} → {item['screen']}")
    screens = [n for n in nodes.values() if n["kind"] == "component"]
    if screens:
        out.append("\nScreens")
        for c in screens:
            calls = out_edges(c["id"], ("calls",))
            out.append(f"  {c['name']}" + (f" → {', '.join(calls)}" if calls else "") + f"   ({c['file']}:{c['line']})")
    eps = [n for n in nodes.values() if n["kind"] == "endpoint"]
    if eps:
        out.append("\nEndpoints")
        for e in eps:
            bits = []
            if e["reads"]:
                bits.append("reads " + ", ".join(e["reads"]))
            if e["writes"]:
                bits.append("writes " + ", ".join(e["writes"]))
            flags = [f"auth {e['auth']}"] if e["auth"] else ["public"]
            if e.get("audited"):
                flags.append("audited")
            flags.append("tested" if e.get("tested") else "untested")
            sig = ", ".join(f"{p}: {e.get('types', {})[p]}" if p in e.get("types", {}) else p for p in e["params"])
            out.append(f"  {e['name']}({sig})" + (f"  {'; '.join(bits)}" if bits else "") +
                       f"  [{', '.join(flags)}]")
    modules = [n for n in nodes.values() if n["kind"] == "module"]
    if modules:
        out.append("\nModules")
        for m in modules:
            names = [i.split(":", 1)[1] for i in m.get("members", []) if not i.startswith("service:")]
            out.append(f"  {m['name']}: owns {', '.join(m['owns']) or '—'}; "
                       f"{len(names)} declaration{'' if len(names) == 1 else 's'}; depends on {', '.join(m.get('depends_on', [])) or 'nothing'}"
                       f"   ({m['file']}:{m['line']})")
    tables = [n for n in nodes.values() if n["kind"] == "table"]
    if tables:
        out.append("\nTables")
        for t in tables:
            readers = sorted({e["from"].split(":", 1)[1] for e in edges if e["to"] == t["id"] and e["kind"] == "reads"})
            writers = sorted({e["from"].split(":", 1)[1] for e in edges if e["to"] == t["id"] and e["kind"] == "writes"})
            out.append(f"  {t['name']}: read by {', '.join(readers) or '—'}; written by {', '.join(writers) or '—'}")
    if app_map["issues"]:
        out.append("\nIssues")
        out += [f"  • {i['message']}" for i in app_map["issues"]]
    if app_map["errors"]:
        out.append("\nFiles that don't parse")
        out += [f"  • {e}" for e in app_map["errors"]]
    return "\n".join(out)


def render_impact(result: Dict[str, Any]) -> str:
    out = []
    if result["unknown"]:
        out.append(f"Not found: {', '.join(result['unknown'])}")
    if not result["targets"]:
        return "\n".join(out or ["Nothing to check."])
    out.append(f"Changing {', '.join(result['targets'])} affects:")
    labels = {"endpoints": "Endpoints", "functions": "Functions", "screens": "Screens", "workflows": "Workflows",
              "tables": "Tables"}
    anything = False
    for key, label in labels.items():
        items = result["affected"][key]
        if items:
            anything = True
            out.append(f"  {label}: " + ", ".join(f"{i['id'].split(':', 1)[1]} ({i['why'].split(':', 1)[0].split(' ')[0]})"
                                                    for i in items))
    if result["navigation"]:
        out.append(f"  In the app: {', '.join(result['navigation'])}")
    if result.get("modules"):
        out.append(f"  Modules: {', '.join(result['modules'])}")
    if not anything:
        out.append("  Nothing else depends on it.")
    out.append(f"Tests to run: {', '.join(t.split(':', 1)[1] for t in result['tests']) or 'none cover this'}")
    if result["untested"]:
        out.append(f"No test covers: {', '.join(i.split(':', 1)[1] for i in result['untested'])}")
    return "\n".join(out)


def changed_between(old_root: Any, new_root: Any) -> List[str]:
    """Declarations added, removed or edited between two copies of an app."""
    def sources(root: Any) -> Dict[str, str]:
        m = build_map(root)
        out = {}
        for node in m["nodes"].values():
            if node["kind"] in ("service",) or not node["line"]:
                continue
            path = Path(m["root"]) / node["file"]
            lines = path.read_text(encoding="utf-8").splitlines()
            out[node["id"]] = "\n".join(l.rstrip() for l in lines[node["line"] - 1:node["end_line"]]).strip()
        for node in m["nodes"].values():
            if node["kind"] == "table":
                out.setdefault(node["id"], "")
        return out
    before, after = sources(old_root), sources(new_root)
    return sorted(i for i in set(before) | set(after) if before.get(i) != after.get(i))
