"""
The MCN Semantic Graph (MSG): a canonical, machine-readable model of an MCN app.

    mcn describe --msg              the MSG as JSON
    mcn describe --msg-schema       its JSON Schema

An MSG has three layers:

    graph   the declarations (tables, endpoints with typed signatures, functions,
            screens, tests, modules...) and how they connect (calls, reads, writes,
            renders, covers, owns), with the problems found — what an agent reasons about
    files   every source file's complete abstract syntax tree, independent of
            formatting, plus its exact text; each graph node points into its file's tree
            with `ast_ref`, so nothing in the program is left out

`from_msg(msg)` turns the trees back into the parser's own AST (equal to parsing the
source), and `source_files(msg)` gives back the files byte for byte.

AST nodes are JSON objects with "$type" (the node class: IfStmt, EndpointDecl...) and
their fields; maps are {"$map": {...}} and tuples {"$tuple": [...]}.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ast_nodes as ast
from .app_map import _source_files, build_map
from .lexer import Lexer
from .parser import Parser

MSG_VERSION = "1.0"
_AST_CLASSES = {name: cls for name, cls in vars(ast).items()
                if isinstance(cls, type) and dataclasses.is_dataclass(cls)}


# ── AST ⇄ JSON ────────────────────────────────────────────────────────────────

def ast_to_json(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out: Dict[str, Any] = {"$type": type(value).__name__}
        for f in dataclasses.fields(value):
            out[f.name] = ast_to_json(getattr(value, f.name))
        return out
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {"$map": {str(k): ast_to_json(v) for k, v in value.items()}}
    if isinstance(value, tuple):
        return {"$tuple": [ast_to_json(v) for v in value]}
    if isinstance(value, list):
        return [ast_to_json(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Can't put a {type(value).__name__} in the MSG")


def ast_from_json(value: Any) -> Any:
    if isinstance(value, list):
        return [ast_from_json(v) for v in value]
    if isinstance(value, dict):
        if "$type" in value:
            cls = _AST_CLASSES.get(value["$type"])
            if cls is None:
                raise ValueError(f"Unknown AST node type '{value['$type']}'")
            names = {f.name for f in dataclasses.fields(cls) if f.init}
            node = cls(**{k: ast_from_json(v) for k, v in value.items() if k in names})
            for f in dataclasses.fields(cls):
                if not f.init and f.name in value:
                    setattr(node, f.name, ast_from_json(value[f.name]))
            return node
        if "$map" in value:
            return {k: ast_from_json(v) for k, v in value["$map"].items()}
        if "$tuple" in value:
            return tuple(ast_from_json(v) for v in value["$tuple"])
    return value


# ── Building the MSG ─────────────────────────────────────────────────────────

def _parse(text: str) -> ast.Program:
    parser = Parser(Lexer(text).tokenize())
    program = parser.parse()
    if getattr(parser, "errors", None):
        raise SyntaxError(str(parser.errors[0]))
    return program


def _refs(program: ast.Program) -> Dict[int, str]:
    """line → JSON pointer of the declaration on that line (top level, and endpoints inside services)."""
    refs: Dict[int, str] = {}
    for i, stmt in enumerate(program.body):
        line = getattr(stmt, "line", 0)
        if line and line not in refs:
            refs[line] = f"/body/{i}"
        if isinstance(stmt, ast.ServiceDecl):
            for j, ep in enumerate(stmt.endpoints):
                refs[("endpoint", ep.line)] = f"/body/{i}/endpoints/{j}"     # type: ignore[index]
    return refs


def _signature(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "params" not in node:
        return None
    types = node.get("types") or {}
    return {"params": [{"name": p, "type": types.get(p)} for p in node["params"]]}


def build_msg(root: Any, include_ast: bool = True) -> Dict[str, Any]:
    """The MSG for an app folder or a single .mcn file."""
    root = Path(root).resolve()
    base = root if root.is_dir() else root.parent
    app = build_map(root)
    from mcn import __version__
    files: Dict[str, Dict[str, Any]] = {}
    refs: Dict[str, Dict[Any, str]] = {}
    for path in _source_files(root):
        rel = str(path.relative_to(base))
        text = path.read_text(encoding="utf-8")
        entry: Dict[str, Any] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                 "lines": len(text.splitlines())}
        try:
            program = _parse(text)
            refs[rel] = _refs(program)
            if include_ast:
                entry["ast"] = ast_to_json(program)
        except SyntaxError as exc:
            entry["error"] = str(exc)
        if include_ast:
            entry["source"] = text
        files[rel] = entry

    nodes = []
    for node in app["nodes"].values():
        out = {k: v for k, v in node.items() if k not in ("line", "end_line", "params", "types")}
        out["span"] = {"start_line": node["line"], "end_line": node["end_line"]} if node["line"] else None
        sig = _signature(node)
        if sig:
            out["signature"] = sig
        file_refs = refs.get(node["file"], {})
        key = ("endpoint", node["line"]) if node["kind"] == "endpoint" else node["line"]
        if node["line"] and key in file_refs:
            out["ast_ref"] = f"{node['file']}#{file_refs[key]}"
        nodes.append(out)
    return {
        "msg_version": MSG_VERSION,
        "generator": f"mcn {__version__}",
        "root": str(base),
        "summary": app["summary"],
        "nodes": nodes,
        "edges": app["edges"],
        "issues": app["issues"],
        "errors": app["errors"],
        "files": files,
    }


# ── Reading an MSG back ──────────────────────────────────────────────────────

def from_msg(msg: Dict[str, Any]) -> Dict[str, ast.Program]:
    """Each file's AST, rebuilt from the MSG (equal to what the parser produces from the source)."""
    _check_version(msg)
    return {rel: ast_from_json(f["ast"]) for rel, f in msg["files"].items() if "ast" in f}


def source_files(msg: Dict[str, Any]) -> Dict[str, str]:
    """Each file's exact text, from the MSG."""
    _check_version(msg)
    return {rel: f["source"] for rel, f in msg["files"].items() if "source" in f}


def resolve_ref(msg: Dict[str, Any], ref: str) -> Any:
    """The AST JSON an `ast_ref` ("backend/main.mcn#/body/3/endpoints/1") points to."""
    rel, _, pointer = ref.partition("#")
    value: Any = msg["files"][rel]["ast"]
    for part in [p for p in pointer.split("/") if p]:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _check_version(msg: Dict[str, Any]) -> None:
    major = str(msg.get("msg_version", "")).split(".")[0]
    if major != MSG_VERSION.split(".")[0]:
        raise ValueError(f"This is MSG version {msg.get('msg_version')}; this MCN reads version {MSG_VERSION}")


def schema() -> Dict[str, Any]:
    """The JSON Schema of MSG documents."""
    return json.loads((Path(__file__).parent / "msg_schema.json").read_text(encoding="utf-8"))


def ast_types() -> List[str]:
    return sorted(_AST_CLASSES)
