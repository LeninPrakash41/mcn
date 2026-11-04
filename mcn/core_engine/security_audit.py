"""
`mcn audit`: scan MCN source for security problems before it ships.

Each finding has a rule id, a severity (high, medium, low), the line, what is
wrong and how to fix it. The scan reads the syntax tree; nothing is executed.

    mcn audit backend/main.mcn
    mcn audit .               # every .mcn file under the folder
    mcn audit . --json        # for CI
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterator, List, Optional, Set

from . import ast_nodes as ast
from .lexer import Lexer
from .parser import Parser

SEVERITIES = ("high", "medium", "low")

_SECRET_NAME = re.compile(r"(password|passwd|secret|token|api_?key|private_?key|access_?key|credential)", re.I)
_SECRET_VALUE = re.compile(
    r"^(sk-ant-[\w-]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[\w-]{10,}"
    r"|AIza[\w-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_PLACEHOLDER = re.compile(r"^(|x+|\*+|changeme|change[-_ ]?me|your[-_ ].*|<.*>|\$\{.*\}|test|example|placeholder|todo)$", re.I)
_INTERP = re.compile(r"(?<!\{)\{[A-Za-z_][\w.\[\]\"']*\}(?!\})")   # {name}, not {{name}}
_LOCAL_HTTP = re.compile(r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.0\.2\.2|\[::1\])([:/]|$)", re.I)

_SQL_CALLS = {"query", "db_query", "execute"}
_FILE_CALLS = {"read_file", "write_file", "append_file", "delete_file", "read_json", "write_json", "read_csv", "write_csv"}
_FETCH_CALLS = {"fetch", "http_get", "http_post"}
_LOG_CALLS = {"log", "print", "echo", "log_info", "log_warn", "log_error"}
_WEAK_HASHES = {"md5", "sha256", "hash_data", "sha1"}
_WRITE_PREFIXES = ("create_", "add_", "save_", "update_", "delete_", "remove_", "set_", "submit_", "send_",
                   "approve_", "reject_", "upload_", "import_", "reset_", "run_", "process_")


@dataclass
class Finding:
    rule: str
    severity: str
    line: int
    message: str
    fix: str
    file: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _children(node) -> Iterator:
    if not dataclasses.is_dataclass(node):
        return
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        items = value.values() if isinstance(value, dict) else value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            if isinstance(item, tuple):
                yield from (x for x in item if isinstance(x, ast.Node))
            elif isinstance(item, ast.Node):
                yield item


def _walk(node) -> Iterator:
    yield node
    for child in _children(node):
        yield from _walk(child)


def _names(expr) -> Set[str]:
    """Variables an expression reads, including {name} inside strings."""
    found = set()
    for n in _walk(expr):
        if isinstance(n, ast.Variable):
            found.add(n.name)
        elif isinstance(n, ast.Literal) and isinstance(n.value, str):
            found.update(re.split(r"[.\[]", m.group(0)[1:-1])[0] for m in _INTERP.finditer(n.value))
    return found


def _callee(call: ast.Call) -> str:
    c = call.callee
    return c.name if isinstance(c, ast.Variable) else c.name if isinstance(c, ast.Property) else ""


def _is_dynamic_string(expr) -> bool:
    """True when text is assembled from values: "a" + x, or "...{x}..."."""
    if isinstance(expr, ast.Literal):
        return isinstance(expr.value, str) and bool(_INTERP.search(expr.value))
    if isinstance(expr, ast.Binary) and expr.operator == "+":
        return bool(_names(expr)) or _is_dynamic_string(expr.left) or _is_dynamic_string(expr.right)
    return False


class Auditor:
    def __init__(self, source: str, file: str = ""):
        self.source, self.file = source, file
        self.findings: List[Finding] = []

    def add(self, rule, severity, node, message, fix):
        self.findings.append(Finding(rule, severity, getattr(node, "line", 0) or 0, message, fix, self.file))

    def run(self) -> List[Finding]:
        program = Parser(Lexer(self.source).tokenize()).parse()
        for stmt in program.body:
            self._visit(stmt, inputs=set())
        for node in _walk(program):
            if isinstance(node, ast.ServiceDecl):
                self._service(node)
            elif isinstance(node, ast.Literal) and isinstance(node.value, str):
                self._literal(node)
        seen, unique = set(), []
        for f in sorted(self.findings, key=lambda f: (SEVERITIES.index(f.severity), f.line)):
            key = (f.rule, f.line)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    # Walk statements, remembering which names hold request input
    def _visit(self, node, inputs: Set[str]):
        if isinstance(node, (ast.EndpointDecl, ast.FunctionDecl)):
            inner = set(node.params) if isinstance(node, ast.EndpointDecl) else set(inputs)
            for stmt in node.body:
                self._visit(stmt, inner)
            return
        if isinstance(node, ast.ServiceDecl):
            for ep in node.endpoints:
                self._visit(ep, set())
            return
        if isinstance(node, (ast.VarDecl, ast.AssignStmt)):
            self._secret_assignment(node)
            if node.value is not None and _names(node.value) & inputs:
                inputs.add(node.name)
        if isinstance(node, ast.Call):
            self._call(node, inputs)
        if isinstance(node, ast.ReturnStmt) and node.value is not None:
            for n in _walk(node.value):
                if isinstance(n, ast.Call) and _callee(n) in _SQL_CALLS and n.arguments:
                    sql = n.arguments[0]
                    if isinstance(sql, ast.Literal) and isinstance(sql.value, str) and re.search(r"select\s+\*\s+from\s+\w*users?\b", sql.value, re.I):
                        self.add("exposed-user-rows", "medium", n,
                                 "An endpoint returns every column of the users table, which can include password hashes.",
                                 "Select only the columns the caller needs, e.g. SELECT id, name, email FROM users.")
        for child in _children(node):
            self._visit(child, inputs)

    def _call(self, call: ast.Call, inputs: Set[str]):
        name = _callee(call)
        args = [a.value if isinstance(a, ast.NamedArg) else a for a in call.arguments]
        first = args[0] if args else None
        if name in _SQL_CALLS and first is not None and _is_dynamic_string(first):
            self.add("sql-injection", "high", call,
                     f"SQL for {name}() is built from values, so input can change the query.",
                     'Use ? placeholders and pass values separately: query("SELECT * FROM t WHERE id = ?", (id,)).')
        if name in _FILE_CALLS and first is not None and _names(first) & inputs:
            self.add("path-traversal", "high", call,
                     f"{name}() opens a path that comes from the request; ../ can reach files outside the app.",
                     "Look the file up by id, or check the name against a fixed list before opening it.")
        if name in _FETCH_CALLS and first is not None and _names(first) & inputs:
            self.add("request-forgery", "medium", call,
                     f"{name}() calls a URL taken from the request, so callers can reach internal services.",
                     "Allow only known hosts, or build the URL from a fixed base and an id.")
        if name in _LOG_CALLS and any(_SECRET_NAME.search(n) for a in args for n in _names(a)):
            self.add("secret-in-logs", "medium", call,
                     f"{name}() writes a secret value to the logs.",
                     "Log mask(value) or leave the secret out.")
        if name in _WEAK_HASHES and any(re.search(r"pass", n, re.I) for a in args for n in _names(a)):
            self.add("weak-password-hash", "high", call,
                     f"{name}() is fast to brute-force and isn't safe for passwords.",
                     "Use auth_hash_password(password) and auth_verify_password(password, hash).")

    def _secret_assignment(self, node):
        value = node.value
        if (_SECRET_NAME.search(node.name) and isinstance(value, ast.Literal) and isinstance(value.value, str)
                and len(value.value) >= 8 and not _PLACEHOLDER.match(value.value.strip())):
            self.add("hardcoded-secret", "high", node,
                     f"'{node.name}' holds a secret written into the source.",
                     f'Read it from the environment: var {node.name} = env("{node.name.upper()}").')

    def _literal(self, node: ast.Literal):
        text = node.value.strip()
        if _SECRET_VALUE.match(text):
            self.add("hardcoded-secret", "high", node, "This string looks like a real API key or private key.",
                     "Move it to an environment variable and rotate the key, since it's now in your history.")
        elif text.startswith("http://") and not _LOCAL_HTTP.match(text):
            self.add("insecure-http", "low", node, f"{text[:60]} uses plain http, so traffic can be read or changed.",
                     "Use https://.")

    def _service(self, svc: ast.ServiceDecl):
        if svc.auth:
            unknown = [p for p in svc.public if p not in {e.name for e in svc.endpoints}]
            if unknown:
                self.add("unknown-public", "low", svc, f"public lists {', '.join(unknown)}, which aren't endpoints of {svc.name}.",
                         "Fix the name, or remove it from public.")
            return
        writes = [e.name for e in svc.endpoints if e.name.startswith(_WRITE_PREFIXES)]
        if writes:
            self.add("open-service", "medium", svc,
                     f"Service {svc.name} has no auth, so anyone who can reach it can call {', '.join(writes[:3])}"
                     + ("…" if len(writes) > 3 else "") + ".",
                     'Add `auth "token"` (or "jwt") to the service, and `public name, ...` for endpoints anyone may call.')


def audit_source(source: str, file: str = "") -> List[Finding]:
    return Auditor(source, file).run()


def _files(path: str) -> List[str]:
    if os.path.isfile(path):
        return [path]
    out = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "build", "dist")]
        out += [os.path.join(root, f) for f in sorted(files) if f.endswith(".mcn")]
    return out


def audit_path(path: str, as_json: bool = False, fail_on: str = "medium") -> int:
    """Print findings for a file or folder. Exit 1 when any finding is at or above fail_on."""
    if not os.path.exists(path):
        print(f"error: not found: '{path}'", file=sys.stderr)
        return 1
    findings, errors = [], []
    for f in _files(path):
        try:
            with open(f, encoding="utf-8") as fh:
                findings += audit_source(fh.read(), f)
        except Exception as exc:  # syntax errors: `mcn check` explains them
            errors.append({"file": f, "error": str(exc).splitlines()[0] if str(exc) else type(exc).__name__})
    threshold = SEVERITIES.index(fail_on) if fail_on in SEVERITIES else 1
    failed = any(SEVERITIES.index(f.severity) <= threshold for f in findings) or bool(errors)

    if as_json:
        print(json.dumps({"findings": [f.to_dict() for f in findings], "errors": errors, "passed": not failed}, indent=2))
        return 1 if failed else 0

    for e in errors:
        print(f"  could not read {e['file']}: {e['error']}  (run mcn check)")
    if not findings:
        print(f"ok  no security problems found in {path}" if not errors else "")
        return 1 if failed else 0
    marks = {"high": "HIGH  ", "medium": "MEDIUM", "low": "LOW   "}
    for f in findings:
        print(f"{marks[f.severity]}  {f.file}:{f.line}  {f.rule}")
        print(f"        {f.message}")
        print(f"        fix: {f.fix}")
    counts = {s: sum(f.severity == s for f in findings) for s in SEVERITIES}
    print(f"\n{len(findings)} finding(s): {counts['high']} high, {counts['medium']} medium, {counts['low']} low")
    return 1 if failed else 0
