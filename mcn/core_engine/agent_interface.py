"""
The MCN agent interface: structured operations an AI agent (or a person, or a tool)
uses to understand and change an MCN app, instead of rewriting whole files.

    inspect()                      the app's structure: modules, screens, endpoints, tables, issues
    find(query, kind)              declarations by name, or by text in their code
    explain(target)                what a declaration does, what it uses and what depends on it
    create(kind, source, ...)      add a declaration           ─┐
    modify(target, source)         replace a declaration        ├─ build up a patch; nothing is written
    remove(target)                 delete a declaration        ─┘
    validate(patch)                parse, types, new problems in the app map, what the patch affects
    test(patch)                    run the app's test blocks with the patch applied
    execute(patch, approved=True)  write a validated, tested patch to the files

A patch is a set of edits to declarations, stored in .mcn/patches/<id>.json. It is
only written to the app's files by execute(), after validate() and test() have
passed and someone approved it. If a file changed after the patch was made,
execute() refuses, so a stale patch never overwrites newer work.

Every operation returns plain JSON-able data. AGENT_TOOLS describes them as tool
definitions for Claude, and call_tool() runs one by name.
"""
from __future__ import annotations

import contextlib
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import ast_nodes as ast
from .app_map import build_map, changed_between, impact, outside_module, resolve
from .lexer import Lexer
from .parser import Parser

KINDS = ("endpoint", "function", "contract", "workflow", "schedule", "test", "component", "table", "module", "app")
_BACKEND_KINDS = {"endpoint", "function", "contract", "workflow", "schedule", "test", "table", "module"}


class InterfaceError(ValueError):
    """An operation that can't be done as asked (unknown target, missing service, stale patch...)."""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("//")


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _reindent(source: str, indent: str) -> List[str]:
    lines = textwrap.dedent(source.expandtabs(4)).strip("\n").splitlines()
    return [(indent + l) if l.strip() else "" for l in lines]


def _parse(text: str) -> Tuple[Optional[ast.Program], List[str]]:
    try:
        parser = Parser(Lexer(text).tokenize())
        program = parser.parse()
    except Exception as exc:
        return None, [str(exc)]
    return program, [str(e) for e in getattr(parser, "errors", []) or []]


class Workspace:
    """One MCN app (a folder with backend/ and ui/, or a single .mcn file)."""

    def __init__(self, root: Any = "."):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise InterfaceError(f"No app at {self.root}")
        self.base = self.root if self.root.is_dir() else self.root.parent
        self.patch_dir = self.base / ".mcn" / "patches"

    # ── Reading the app ───────────────────────────────────────────────────────

    def _files(self) -> Dict[str, str]:
        """Every MCN source file, relative path → text."""
        from .app_map import _source_files
        return {str(p.relative_to(self.base)): p.read_text(encoding="utf-8") for p in _source_files(self.root)}

    def _map(self, files: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if files is None:
            return build_map(self.root)
        with self._materialised(files) as root:
            m = build_map(root)
        m["root"] = str(self.base)
        return m

    @contextlib.contextmanager
    def _materialised(self, files: Dict[str, str]):
        """A scratch copy of the app with these file contents."""
        tmp = Path(tempfile.mkdtemp(prefix="mcn_patch_"))
        try:
            for rel, text in files.items():
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_text(text, encoding="utf-8")
            yield tmp if self.root.is_dir() else tmp / self.root.name
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @staticmethod
    def _span(node: Dict[str, Any], lines: List[str]) -> Tuple[int, int]:
        """0-based [start, end) of a declaration's own lines, without trailing blank lines and comments
        (those usually belong to the next declaration)."""
        start, end = node["line"] - 1, min(node["end_line"], len(lines))
        while end > start + 1 and _is_comment_or_blank(lines[end - 1]):
            end -= 1
        return start, end

    def _source_of(self, node: Dict[str, Any], files: Dict[str, str]) -> str:
        if node["kind"] == "table":
            found = self._table_statement(node["name"], files)
            return found[3] if found else ""
        lines = files[node["file"]].splitlines()
        start, end = self._span(node, lines)
        return "\n".join(lines[start:end])

    def _table_statement(self, table: str, files: Dict[str, str]) -> Optional[Tuple[str, int, int, str]]:
        """(file, start, end, text) of the statement that creates a table."""
        pattern = re.compile(rf"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?{re.escape(table)}\b", re.I)
        for rel, text in files.items():
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if pattern.search(line):
                    end, depth = i, 0
                    for j in range(i, len(lines)):
                        depth += lines[j].count("(") - lines[j].count(")")
                        end = j
                        if depth <= 0:
                            break
                    return rel, i, end + 1, "\n".join(lines[i:end + 1])
        return None

    def _one(self, app_map: Dict[str, Any], target: str) -> Dict[str, Any]:
        ids = resolve(app_map, target)
        if not ids:
            close = difflib.get_close_matches(target.split(":")[-1], [n["name"] for n in app_map["nodes"].values()], 3)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            raise InterfaceError(f"Nothing called '{target}' in this app.{hint}")
        if len(ids) > 1:
            raise InterfaceError(f"'{target}' is ambiguous: {', '.join(ids)}. Use the full id.")
        return app_map["nodes"][ids[0]]

    # ── inspect / find / explain ──────────────────────────────────────────────

    def inspect(self) -> Dict[str, Any]:
        """The app's structure: what an agent needs before changing anything."""
        m = self._map()
        nodes = list(m["nodes"].values())
        by = lambda kind: [n for n in nodes if n["kind"] == kind]

        def signature(n):
            types = n.get("types") or {}
            return f"{n['name']}(" + ", ".join(f"{p}: {types[p]}" if p in types else p for p in n["params"]) + ")"

        files = self._files()
        return {
            "root": str(self.base),
            "summary": m["summary"],
            "modules": [{"name": n["name"], "owns": n["owns"], "depends_on": n.get("depends_on", []),
                         "members": n.get("members", [])} for n in by("module")],
            "tables": [{"name": n["name"], "owner": n.get("owner"),
                        "create": (self._table_statement(n["name"], files) or (None,) * 4)[3]} for n in by("table")],
            "endpoints": [{"id": n["id"], "signature": signature(n), "service": n["service"], "module": n.get("module"),
                           "auth": n.get("auth"), "reads": n["reads"], "writes": n["writes"], "tested": n.get("tested")}
                          for n in by("endpoint")],
            "functions": [{"id": n["id"], "signature": signature(n), "module": n.get("module")} for n in by("function")],
            "screens": [{"id": n["id"], "module": n.get("module"), "states": n["states"], "handlers": n["handlers"],
                         "table_buttons_call": n.get("generated_calls", [])} for n in by("component")],
            "navigation": [item for n in by("app") for item in n["navigation"]],
            "workflows": [n["id"] for n in by("workflow") + by("schedule")],
            "contracts": [{"id": n["id"], "fields": n.get("fields")} for n in by("contract")],
            "tests": [n["id"] for n in by("test")],
            "issues": [i["message"] for i in m["issues"]],
            "errors": m["errors"],
        }

    def semantic_graph(self, include_ast: bool = False) -> Dict[str, Any]:
        """The MCN Semantic Graph (MSG): declarations, signatures and connections; with include_ast, every
        file's full syntax tree and source too."""
        from .msg import build_msg
        return build_msg(self.root, include_ast=include_ast)

    def find(self, query: str, kind: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Declarations whose name contains `query`; if none, declarations whose code contains it."""
        if kind and kind not in KINDS and kind != "service":
            raise InterfaceError(f"Unknown kind '{kind}'. Use one of: {', '.join(KINDS)}")
        m, files = self._map(), self._files()
        q = query.lower().strip()
        nodes = [n for n in m["nodes"].values() if not kind or n["kind"] == kind]
        hits = [n for n in nodes if q in n["name"].lower() or q == n["id"].lower()]
        match = "name"
        if not hits:
            hits = [n for n in nodes if n["kind"] not in ("service", "module")
                    and q in self._source_of(n, files).lower()]
            match = "code"
        hits.sort(key=lambda n: (n["name"].lower() != q, n["kind"], n["name"]))
        return [{"id": n["id"], "kind": n["kind"], "file": n["file"], "line": n["line"], "module": n.get("module"),
                 "matched": match, "source": self._source_of(n, files)} for n in hits[:limit]]

    def explain(self, target: str) -> Dict[str, Any]:
        """What a declaration is, what it uses, what uses it, which tests cover it, and what a change would reach."""
        m = self._map()
        node = self._one(m, target)
        nid = node["id"]
        out_edges = [e for e in m["edges"] if e["from"] == nid]
        in_edges = [e for e in m["edges"] if e["to"] == nid]
        reach = impact(m, [nid])
        facts = {k: node[k] for k in ("params", "types", "service", "auth", "reads", "writes", "states", "handlers",
                                      "owns", "members", "depends_on", "owner", "fields", "navigation",
                                      "generated_calls", "tested") if node.get(k) not in (None, [], {})}
        info = {
            "id": nid, "kind": node["kind"], "file": node["file"], "line": node["line"], "module": node.get("module"),
            **facts,
            "uses": sorted(f"{e['kind']} {e['to']}" for e in out_edges if e["kind"] not in ("contains",)),
            "used_by": sorted(f"{e['from']} ({e['kind']})" for e in in_edges if e["kind"] not in ("contains", "covers")),
            "tests": sorted(e["from"] for e in in_edges if e["kind"] == "covers"),
            "a_change_affects": {k: [d["id"] for d in v] for k, v in reach["affected"].items() if v},
            "source": self._source_of(node, self._files()),
        }
        info["text"] = self._describe(info)
        return info

    @staticmethod
    def _describe(info: Dict[str, Any]) -> str:
        kind, name = info["kind"], info["id"].split(":", 1)[1]
        types = info.get("types") or {}
        head = {
            "endpoint": lambda: f"Endpoint {name}(" + ", ".join(f"{p}: {types[p]}" if p in types else p
                                                                for p in info.get("params", [])) + ")"
                                + f" in service {info.get('service')}",
            "component": lambda: f"Screen {name}",
            "table": lambda: f"Table {name}" + (f", owned by module {info['owner']}" if info.get("owner") else ""),
            "module": lambda: f"Module {name}, owning " + (", ".join(info.get("owns", [])) or "no tables"),
        }.get(kind, lambda: f"{kind.capitalize()} {name}")()
        lines = [head + (f" (module {info['module']})" if info.get("module") else "") + f", {info['file']}:{info['line']}."]
        if info.get("auth"):
            lines.append(f"Needs sign-in ({info['auth']}).")
        if info.get("reads"):
            lines.append("Reads " + ", ".join(info["reads"]) + ".")
        if info.get("writes"):
            lines.append("Writes " + ", ".join(info["writes"]) + ".")
        calls = [u.split(" ", 1)[1] for u in info["uses"] if u.startswith(("calls ", "renders ", "uses "))]
        if calls:
            lines.append("Uses " + ", ".join(calls) + ".")
        if info.get("generated_calls"):
            lines.append("Its table buttons call " + ", ".join(info["generated_calls"]) + ".")
        if info["used_by"]:
            lines.append("Used by " + ", ".join(info["used_by"]) + ".")
        elif kind in ("endpoint", "function"):
            lines.append("Nothing calls it.")
        if kind in ("endpoint", "function", "component", "workflow"):
            lines.append(("Covered by " + ", ".join(info["tests"]) + ".") if info["tests"] else "No test covers it.")
        reach = info["a_change_affects"]
        if reach.get("screens"):
            lines.append("Changing it affects the screens " + ", ".join(reach["screens"]) + ".")
        return " ".join(lines)

    # ── Patches: create / modify / remove ─────────────────────────────────────

    def _new_patch(self, reason: str, module: Optional[str]) -> Dict[str, Any]:
        return {"id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "created": time.time(),
                "reason": reason, "module": module, "status": "proposed", "operations": [], "base": {}, "files": {}}

    def _load(self, patch_id: str) -> Dict[str, Any]:
        path = self.patch_dir / f"{patch_id}.json"
        if not re.fullmatch(r"[\w-]+", patch_id or "") or not path.exists():
            raise InterfaceError(f"No patch '{patch_id}'")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, patch: Dict[str, Any]) -> None:
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        (self.patch_dir / f"{patch['id']}.json").write_text(json.dumps(patch, indent=1), encoding="utf-8")

    def _patched_files(self, patch: Dict[str, Any]) -> Dict[str, str]:
        files = self._files()
        files.update(patch["files"])
        return files

    def _edit(self, patch_id: Optional[str], reason: str, module: Optional[str], operation: Dict[str, Any],
              change) -> Dict[str, Any]:
        """Apply `change(files, app_map) -> {file: new text}` on top of the patch (or a new one)."""
        patch = self._load(patch_id) if patch_id else self._new_patch(reason, module)
        if module and not patch.get("module"):
            patch["module"] = module
        current = self._patched_files(patch)
        edits = change(dict(current), self._map(current))
        for rel, text in edits.items():
            if not text.endswith("\n"):
                text += "\n"
            original = self._files().get(rel)
            patch["base"].setdefault(rel, _hash(original) if original is not None else None)
            patch["files"][rel] = text
        problems = [f"{rel}: {e}" for rel in edits for e in _parse(patch["files"][rel])[1]]
        operation["parses"] = not problems
        patch["operations"].append(operation)
        patch["status"] = "proposed"
        patch.pop("validation", None)
        patch.pop("tests", None)
        self._save(patch)
        return self._summary(patch, problems)

    def _summary(self, patch: Dict[str, Any], problems: Optional[List[str]] = None) -> Dict[str, Any]:
        out = {"patch": patch["id"], "status": patch["status"], "operations": len(patch["operations"]),
               "diff": self.diff(patch["id"], patch)}
        if problems:
            out["parse_errors"] = problems[:5]
        return out

    def diff(self, patch_id: str, patch: Optional[Dict[str, Any]] = None) -> str:
        patch = patch or self._load(patch_id)
        files = self._files()
        chunks = []
        for rel, new in sorted(patch["files"].items()):
            old = files.get(rel, "")
            chunks += difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}", n=2)
        return "".join(chunks)

    def create(self, kind: str, source: str, *, module: Optional[str] = None, service: Optional[str] = None,
               nav: Optional[str] = None, patch: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        """Add a declaration. Endpoints go into a service; with `module`, the code goes inside that module;
        a component with `nav` also gets a navigation item."""
        if kind not in KINDS or kind in ("app",):
            raise InterfaceError(f"Can't create a '{kind}'. Use one of: {', '.join(k for k in KINDS if k != 'app')}")
        program = _parse_declaration(source)

        def change(files: Dict[str, str], m: Dict[str, Any]) -> Dict[str, str]:
            nodes = m["nodes"]
            name = self._declared_name(kind, program, source)
            if name and kind != "table" and f"{kind}:{name}" in nodes:
                raise InterfaceError(f"{kind}:{name} already exists; use modify")
            if kind == "endpoint":
                services = [n for n in nodes.values() if n["kind"] == "service"
                            and (not service or n["name"] == service)
                            and (not module or n.get("module") == module or service)]
                if len(services) != 1:
                    names = ", ".join(n["name"] for n in nodes.values() if n["kind"] == "service") or "none"
                    raise InterfaceError(f"Say which service the endpoint goes in (services: {names})")
                svc = services[0]
                lines = files[svc["file"]].splitlines()
                eps = [nodes[f"endpoint:{e}"] for e in svc["endpoints"] if f"endpoint:{e}" in nodes]
                if eps:
                    last = max(eps, key=lambda n: n["line"])
                    _, at = self._span(last, lines)
                    indent = _indent_of(lines[last["line"] - 1])
                else:
                    _, at = self._span(svc, lines)
                    indent = _indent_of(lines[svc["line"] - 1]) + "    "
                lines[at:at] = [""] + _reindent(source, indent)
                return {svc["file"]: "\n".join(lines)}

            rel = self._target_file(kind, module, files, m)
            lines = files.get(rel, "").splitlines()
            region = self._module_region(lines, module) if module else None
            if module and region is None:
                if kind == "component" or rel not in files:
                    # the module isn't in this file yet: start its block
                    block = [f"module {module}", ""] + _reindent(source, "    ")
                    at = self._before_app(lines)
                    lines[at:at] = block + [""] if at < len(lines) else [""] + block
                    return self._with_nav({rel: "\n".join(lines)}, files, kind, name, nav, m)
                raise InterfaceError(f"No module '{module}'")
            indent = "    " if region else ""
            if region:
                start, end = region
                at = end
                if kind == "table":
                    self._add_owned(lines, start, name)
                    start, end = self._module_region(lines, module)
                    creates = [i for i in range(start, end) if re.search(r"CREATE\s+TABLE", lines[i], re.I)]
                    at = (creates[-1] + 1) if creates else self._after_owns(lines, start)
            else:
                if kind == "table":
                    creates = [i for i, l in enumerate(lines) if re.search(r"CREATE\s+TABLE", l, re.I)]
                    at = (creates[-1] + 1) if creates else 0
                elif kind == "component":
                    at = self._before_app(lines)
                else:
                    at = len(lines)
            new = _reindent(source, indent)
            block = ([""] if at > 0 and lines[at - 1:at] and lines[at - 1].strip() and kind != "table" else []) + new
            if at < len(lines) and lines[at].strip() and kind != "table":
                block += [""]
            lines[at:at] = block
            return self._with_nav({rel: "\n".join(lines)}, files, kind, name, nav, m)

        return self._edit(patch, reason, module, {"op": "create", "kind": kind, "module": module,
                                                  "service": service, "nav": nav}, change)

    def modify(self, target: str, source: str, *, patch: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        """Replace a declaration's code (its whole block, keeping its place and indentation)."""
        program = _parse_declaration(source)

        def change(files: Dict[str, str], m: Dict[str, Any]) -> Dict[str, str]:
            node = self._one(m, target)
            return self._replace(node, files, _reindent_block(source), m)

        return self._edit(patch, reason, None, {"op": "modify", "target": target}, change)

    def remove(self, target: str, *, patch: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        """Delete a declaration."""
        def change(files: Dict[str, str], m: Dict[str, Any]) -> Dict[str, str]:
            node = self._one(m, target)
            if node["kind"] in ("service", "module", "app"):
                raise InterfaceError(f"Removing a whole {node['kind']} isn't supported; remove its declarations")
            return self._replace(node, files, None, m)

        return self._edit(patch, reason, None, {"op": "remove", "target": target}, change)

    def _replace(self, node: Dict[str, Any], files: Dict[str, str], source: Optional[str],
                 m: Dict[str, Any]) -> Dict[str, str]:
        if node["kind"] == "table":
            found = self._table_statement(node["name"], files)
            if not found:
                raise InterfaceError(f"No CREATE TABLE statement for {node['name']}")
            rel, start, end, _ = found
        else:
            if node["kind"] == "service":
                raise InterfaceError("Modify the service's endpoints one by one")
            rel = node["file"]
            start, end = self._span(node, files[rel].splitlines())
        lines = files[rel].splitlines()
        indent = _indent_of(lines[start])
        if source is None:
            del lines[start:end]
            while start < len(lines) and start > 0 and not lines[start].strip() and not lines[start - 1].strip():
                del lines[start]
        else:
            lines[start:end] = _reindent(source, indent)
        return {rel: "\n".join(lines)}

    # placement helpers

    @staticmethod
    def _declared_name(kind: str, program: ast.Program, source: str) -> Optional[str]:
        if kind == "table":
            m = re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", source, re.I)
            if not m:
                raise InterfaceError("A table is created with a query(\"CREATE TABLE ...\") statement")
            return m.group(1)
        first = next((s for s in program.body if not isinstance(s, ast.ModuleDecl)), None)
        if kind == "endpoint":
            if not isinstance(first, ast.FunctionDecl) and not re.match(r"\s*endpoint\b", textwrap.dedent(source)):
                raise InterfaceError("An endpoint starts with: endpoint name(params)")
            m = re.match(r"\s*endpoint\s+(\w+)", textwrap.dedent(source))
            return m.group(1) if m else None
        expected = {"function": ast.FunctionDecl, "contract": ast.ContractDecl, "workflow": ast.WorkflowDecl,
                    "schedule": ast.ScheduleDecl, "test": ast.TestDecl, "component": ast.ComponentDecl}.get(kind)
        if expected and not isinstance(first, expected):
            raise InterfaceError(f"The source isn't a {kind} declaration")
        if kind == "module":
            m = re.match(r"\s*module\s+(\w+)", textwrap.dedent(source))
            return m.group(1) if m else None
        return getattr(first, "description", None) if kind == "test" else getattr(first, "name", None)

    def _target_file(self, kind: str, module: Optional[str], files: Dict[str, str], m: Dict[str, Any]) -> str:
        if self.root.is_file():
            return self.root.name
        if kind == "component":
            ui = [f for f in files if f.startswith("ui/")]
            return "ui/app.mcn" if "ui/app.mcn" in files or not ui else ui[0]
        if module and f"module:{module}" in m["nodes"]:
            for f in m["nodes"][f"module:{module}"].get("files", [m["nodes"][f"module:{module}"]["file"]]):
                if not f.startswith("ui/"):
                    return f
        backend = [f for f in files if not f.startswith("ui/")]
        return "backend/main.mcn" if "backend/main.mcn" in files or not backend else backend[0]

    @staticmethod
    def _module_region(lines: List[str], module: str) -> Optional[Tuple[int, int]]:
        """0-based [start, end) of a module block in a file: its header to its last indented line."""
        for i, line in enumerate(lines):
            if re.fullmatch(rf"module\s+{re.escape(module)}\s*", line.rstrip()):
                end = i + 1
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith((" ", "\t")):
                        break
                    if lines[j].strip():
                        end = j + 1
                return i, end
        return None

    @staticmethod
    def _after_owns(lines: List[str], start: int) -> int:
        at = start + 1
        while at < len(lines) and re.match(r"\s+owns\b", lines[at]):
            at += 1
        return at

    @staticmethod
    def _add_owned(lines: List[str], start: int, table: Optional[str]) -> None:
        if not table:
            return
        if start + 1 < len(lines) and re.match(r"\s+owns\b", lines[start + 1]):
            owned = [t.strip() for t in lines[start + 1].split("owns", 1)[1].split(",")]
            if table not in owned:
                lines[start + 1] = lines[start + 1].rstrip() + f", {table}"
        else:
            lines.insert(start + 1, f"    owns {table}")

    @staticmethod
    def _before_app(lines: List[str]) -> int:
        for i, line in enumerate(lines):
            if re.match(r"app\s+\w+", line):
                at = i
                while at > 0 and _is_comment_or_blank(lines[at - 1]) and lines[at - 1].strip():
                    at -= 1
                return at
        return len(lines)

    def _with_nav(self, edits: Dict[str, str], files: Dict[str, str], kind: str, name: Optional[str],
                  nav: Optional[str], m: Dict[str, Any]) -> Dict[str, str]:
        if kind != "component" or not nav:
            return edits
        apps = [n for n in m["nodes"].values() if n["kind"] == "app"]
        if not apps:
            raise InterfaceError("There's no app block to add navigation to")
        rel = apps[0]["file"]
        lines = (edits.get(rel) or files[rel]).splitlines()
        navs = [i for i, l in enumerate(lines) if re.match(r"\s+(nav|tab)\s+\"", l)]
        if not navs:
            raise InterfaceError("The app block has no sidebar or tabs to add the screen to")
        last = navs[-1]
        word = lines[last].strip().split()[0]
        lines.insert(last + 1, f'{_indent_of(lines[last])}{word} "{nav.replace(chr(34), chr(39))}" {name}')
        edits[rel] = "\n".join(lines)
        return edits

    # ── validate / test / execute ─────────────────────────────────────────────

    def validate(self, patch_id: str, strict: bool = False) -> Dict[str, Any]:
        """Check a patch without writing it: does every changed file parse and type-check, does it add
        problems to the app map (missing endpoints, writes to another module's table...), what does
        it affect, and (for a patch made for one module) does it stay inside that module."""
        from .type_checker import Severity, check_source
        patch = self._load(patch_id)
        files = self._patched_files(patch)
        result: Dict[str, Any] = {"patch": patch_id, "parse_errors": [], "type_errors": [], "warnings": []}
        for rel in sorted(patch["files"]):
            text = files[rel]
            _, problems = _parse(text)
            result["parse_errors"] += [f"{rel}: {p}" for p in problems]
            if not problems:
                for issue in check_source(text, strict=strict):
                    where = f"{rel}:{getattr(issue, 'line', '?')}: {issue.message}"
                    (result["type_errors"] if issue.severity == Severity.ERROR else result["warnings"]).append(where)
        before, after = self._map(), self._map(files)
        old = {i["message"] for i in before["issues"] if i.get("severity") != "note"}
        new = {i["message"] for i in after["issues"] if i.get("severity") != "note"}
        result["new_issues"] = sorted(new - old)
        result["fixed_issues"] = sorted(old - new)
        result["map_errors"] = [e for e in after["errors"] if e not in before["errors"]]
        with self._materialised(files) as patched:
            changed = changed_between(self.root, patched)
        for op in patch["operations"]:
            if op.get("op") in ("modify", "remove") and str(op.get("target", "")).startswith("table:"):
                changed.append(op["target"])
        # a module counts as changed only when its own declaration did (its name or the tables it owns),
        # not whenever something inside it changed
        owns = lambda m, i: m["nodes"][i]["owns"] if i in m["nodes"] else None
        changed = [c for c in changed if not c.startswith("module:") or owns(before, c) != owns(after, c)]
        result["changed"] = sorted(set(changed))
        present = [c for c in result["changed"] if c in after["nodes"]]
        reach = impact(after, present) if present else {"affected": {}, "tests": [], "untested": []}
        result["affects"] = {k: [d["id"] for d in v] for k, v in reach["affected"].items() if v}
        result["tests_to_run"] = reach["tests"]
        result["untested"] = reach["untested"]
        if patch.get("module"):
            try:
                scoped = result["changed"]
                if not any(op.get("op") != "create" and str(op.get("target", "")).startswith("app:")
                           for op in patch["operations"]):
                    scoped = [c for c in scoped if not c.startswith("app:")]    # a nav item for the module's screen
                result["outside_module"] = outside_module(after, scoped, patch["module"])
            except ValueError as exc:
                result["outside_module"] = [str(exc)]
        failed = (result["parse_errors"] or result["type_errors"] or result["new_issues"] or result["map_errors"]
                  or result.get("outside_module") or (strict and result["warnings"]))
        result["ok"] = not failed
        patch["validation"] = result
        patch["status"] = "validated" if result["ok"] else "invalid"
        self._save(patch)
        result["status"] = patch["status"]
        return result

    def test(self, patch_id: Optional[str] = None) -> Dict[str, Any]:
        """Run every test block, with the patch applied (or the app as it is), against a fresh database."""
        from .test_runner import TestRunner
        patch = self._load(patch_id) if patch_id else None
        files = self._patched_files(patch) if patch else self._files()
        results: List[Dict[str, Any]] = []
        cwd = os.getcwd()
        with self._materialised(files) as root:
            base = root if root.is_dir() else root.parent
            try:
                os.chdir(base)                     # the app's database is created in the scratch copy
                runner = TestRunner()
                for rel in sorted(files):
                    with contextlib.redirect_stdout(io.StringIO()):
                        for r in runner.run_file(str(base / rel)):
                            results.append({"file": rel, "test": r.description, "passed": r.passed,
                                            "error": r.error.strip().splitlines()[0][:300] if r.error else ""})
            finally:
                os.chdir(cwd)
        out = {"patch": patch_id, "passed": sum(r["passed"] for r in results),
               "failed": [r for r in results if not r["passed"]], "total": len(results)}
        out["ok"] = not out["failed"]
        if patch:
            patch["tests"] = out
            self._save(patch)
        return out

    def execute(self, patch_id: str, approved: bool = False, require_tests: bool = True) -> Dict[str, Any]:
        """Write an approved patch to the app's files. Refuses a patch that hasn't passed validate()
        (and test(), unless require_tests is False), or whose files changed since it was made."""
        patch = self._load(patch_id)
        if patch["status"] == "applied":
            raise InterfaceError(f"Patch {patch_id} was already applied")
        if not approved:
            raise InterfaceError("execute needs approval: show the diff and validation to a person first")
        if patch["status"] != "validated":
            raise InterfaceError(f"Patch {patch_id} is {patch['status']}; it must pass validate first")
        if require_tests and not (patch.get("tests") or {}).get("ok"):
            raise InterfaceError(f"Patch {patch_id} must pass test first")
        current = self._files()
        stale = [rel for rel, h in patch["base"].items()
                 if (current.get(rel) and _hash(current[rel])) != h and not (h is None and rel not in current)]
        if stale:
            raise InterfaceError(f"{', '.join(stale)} changed since the patch was made; make the patch again")
        for rel, text in patch["files"].items():
            path = self.base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        patch["status"] = "applied"
        patch["applied"] = time.time()
        self._save(patch)
        return {"patch": patch_id, "status": "applied", "files": sorted(patch["files"])}

    def patches(self) -> List[Dict[str, Any]]:
        if not self.patch_dir.exists():
            return []
        out = []
        for path in sorted(self.patch_dir.glob("*.json")):
            p = json.loads(path.read_text(encoding="utf-8"))
            out.append({"patch": p["id"], "status": p["status"], "reason": p.get("reason", ""),
                        "operations": [f"{o['op']} {o.get('target') or o.get('kind')}" for o in p["operations"]]})
        return out

    def show(self, patch_id: str) -> Dict[str, Any]:
        p = self._load(patch_id)
        return {"patch": p["id"], "status": p["status"], "reason": p.get("reason", ""), "module": p.get("module"),
                "operations": p["operations"], "validation": p.get("validation"), "tests": p.get("tests"),
                "diff": self.diff(patch_id, p)}


def _parse_declaration(source: str) -> ast.Program:
    """Parse one declaration on its own. An endpoint is checked inside a stand-in service."""
    code = textwrap.dedent(source.expandtabs(4)).strip("\n")
    if re.match(r"endpoint\b", code):
        program, problems = _parse("service _check\n" + "\n".join("    " + l for l in code.splitlines()))
        if program is not None and not problems:
            program = ast.Program(body=[program.body[0].endpoints[0]] if program.body[0].endpoints else [])
    else:
        program, problems = _parse(code)
    if program is None or problems:
        raise InterfaceError(f"The source doesn't parse: {(problems or ['?'])[0]}")
    return program


def _reindent_block(source: str) -> str:
    return textwrap.dedent(source.expandtabs(4)).strip("\n")


# ── As tools for an AI agent ─────────────────────────────────────────────────

_PATCH = {"type": "string", "description": "Add this change to an existing patch (its id). Leave out to start a new patch."}
_REASON = {"type": "string", "description": "One line: why this change is made."}

AGENT_TOOLS: List[Dict[str, Any]] = [
    {"name": "inspect", "description": "The app's structure: modules, tables (with their CREATE statements), "
     "endpoints with typed signatures, screens, navigation, tests, and current problems. Call this first.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "semantic_graph", "description": "The MCN Semantic Graph (MSG): every declaration with its typed "
     "signature, the tables it reads and writes, and every connection (calls, reads, writes, renders, covers, owns), "
     "as versioned JSON. include_ast adds each file's complete syntax tree and source (large).",
     "input_schema": {"type": "object", "properties": {"include_ast": {"type": "boolean"}}}},
    {"name": "find", "description": "Find declarations by name, or by text in their code. Returns their source.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "kind": {"type": "string", "enum": list(KINDS) + ["service"]}}, "required": ["query"]}},
    {"name": "explain", "description": "What a declaration does: its signature, tables it reads and writes, what it "
     "calls, what calls it, which tests cover it, what changing it affects, and its source.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string",
                      "description": "A name (create_order) or id (endpoint:create_order, table:orders)"}},
                      "required": ["target"]}},
    {"name": "create", "description": "Add one declaration to a patch: an endpoint (into a service), function, "
     "contract, workflow, test, table (a query(\"CREATE TABLE ...\") statement), or component (with nav to add it "
     "to navigation). Nothing is written to the app until the patch is executed.",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": [k for k in KINDS if k not in ("app", "module")]},
         "source": {"type": "string", "description": "The complete MCN declaration"},
         "service": {"type": "string", "description": "For an endpoint: the service it belongs to"},
         "module": {"type": "string", "description": "Put it inside this module"},
         "nav": {"type": "string", "description": "For a component: the navigation label"},
         "patch": _PATCH, "reason": _REASON}, "required": ["kind", "source"]}},
    {"name": "modify", "description": "Replace one declaration's complete code in a patch (the whole endpoint, "
     "function, component, table statement...). Keep everything that shouldn't change.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"}, "source": {"type": "string", "description": "The complete new declaration"},
         "patch": _PATCH, "reason": _REASON}, "required": ["target", "source"]}},
    {"name": "remove", "description": "Delete one declaration in a patch.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "patch": _PATCH,
                                                       "reason": _REASON}, "required": ["target"]}},
    {"name": "validate", "description": "Check a patch without writing it: parse and type errors, new problems in "
     "the app (missing endpoints, writes to another module's tables...), what it changes and affects.",
     "input_schema": {"type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]}},
    {"name": "test", "description": "Run the app's test blocks with the patch applied, against a fresh database.",
     "input_schema": {"type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]}},
]


def call_tool(ws: Workspace, name: str, args: Dict[str, Any]) -> Any:
    """Run one AGENT_TOOLS operation. Errors come back as {"error": ...} so an agent can correct itself."""
    try:
        if name == "inspect":
            return ws.inspect()
        if name == "semantic_graph":
            return ws.semantic_graph(bool(args.get("include_ast")))
        if name == "find":
            return ws.find(args["query"], args.get("kind"))
        if name == "explain":
            return ws.explain(args["target"])
        if name == "create":
            return ws.create(args["kind"], args["source"], module=args.get("module"), service=args.get("service"),
                             nav=args.get("nav"), patch=args.get("patch"), reason=args.get("reason", ""))
        if name == "modify":
            return ws.modify(args["target"], args["source"], patch=args.get("patch"), reason=args.get("reason", ""))
        if name == "remove":
            return ws.remove(args["target"], patch=args.get("patch"), reason=args.get("reason", ""))
        if name == "validate":
            return ws.validate(args["patch"])
        if name == "test":
            return ws.test(args["patch"])
    except (InterfaceError, KeyError) as exc:
        return {"error": str(exc).strip("'\"")}
    return {"error": f"Unknown operation '{name}'"}
