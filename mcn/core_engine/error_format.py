"""
Friendly, compiler-style error messages for MCN.

    error: Undefined variable 'totl'. Did you mean 'total'?
      --> app.mcn:12:9
       |
    12 |     log(totl)
       |         ^

Used by the CLI (`mcn run`, `mcn test`) and anything else that shows MCN errors
to people.  Works on LexError, ParseError(s) and runtime MCNError.
"""

from __future__ import annotations

import os
import re
import sys
from typing import List, Optional, Tuple

_LOC_RE = re.compile(r"^\[(\d+):(\d+)\]\s*(LexError|ParseError|RuntimeError):\s*(.*)$", re.S)
_GOT_RE = re.compile(r"\s*\(got ([A-Z_]+) (.*)\)\s*$")

_TOKEN_NAMES = {
    "NEWLINE": "end of line", "EOF": "end of file",
    "INDENT": "an indented block", "DEDENT": "the end of a block",
}


def _describe_found(tt: str, raw: str) -> str:
    if tt in _TOKEN_NAMES:
        return _TOKEN_NAMES[tt]
    val = raw.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        val = val[1:-1]
    if tt == "STRING":
        return f'the string "{val}"'
    return f"'{val}'"


def _split(message: str) -> Tuple[int, int, str, str]:
    """'[3:5] ParseError: Expected X (got NEWLINE '\\n')' → (3, 5, kind, text)."""
    m = _LOC_RE.match(message.strip())
    if not m:
        return 0, 0, "error", message.strip()
    line, col, kind, text = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    g = _GOT_RE.search(text)
    if g:
        found = _describe_found(g.group(1), g.group(2))
        head  = text[:g.start()]
        if head.strip() == "Unexpected token":
            text = {"INDENT": "Unexpected indentation",
                    "DEDENT": "Unexpected end of block"}.get(
                        g.group(1), f"Unexpected {found}")
        else:
            text = f"{head}, but found {found}"
    label = "syntax error" if kind in ("LexError", "ParseError") else "error"
    return line, col, label, text.strip()


def error_entries(exc: BaseException) -> List[Tuple[int, int, str, str]]:
    """(line, col, label, message) for every problem carried by `exc`."""
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:   # unwrap "raise X from exc"
        seen.add(id(cur))
        errors = getattr(cur, "errors", None)
        if isinstance(errors, list) and errors and all(isinstance(e, str) for e in errors):
            return [_split(e) for e in errors]
        if type(cur).__name__ in ("MCNError", "ParseError", "LexError"):
            line, col, label, text = _split(str(cur))
            msg = getattr(cur, "message", None)
            if label == "error" and isinstance(msg, str):
                text = msg
            return [(line or getattr(cur, "line", 0) or 0,
                     col or getattr(cur, "col", 0) or 0, label, text)]
        cur = cur.__cause__
    text = str(exc)
    text = re.sub(r"^MCN [A-Z_]+:\s*", "", text)
    return [_split(text)]


def _color(code: str, text: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def use_color(stream=None) -> bool:
    stream = stream or sys.stderr
    return (hasattr(stream, "isatty") and stream.isatty()
            and not os.environ.get("NO_COLOR"))


def format_error(exc: BaseException, source: Optional[str] = None,
                 file_path: Optional[str] = None, color: bool = False) -> str:
    """Render `exc` as one compiler-style message per problem."""
    lines = source.splitlines() if source else []
    where = file_path or "<input>"
    out: List[str] = []
    for line, col, label, text in error_entries(exc):
        out.append(_color("1;31", label, color) + _color("1", f": {text}", color))
        if line:
            out.append(f"  --> {where}:{line}:{col}")
            if 0 < line <= len(lines):
                src   = lines[line - 1].expandtabs(4)
                gut   = " " * len(str(line))
                caret = " " * max(col - 1, 0) + "^"
                out.append(f"{gut} |")
                out.append(f"{line} | {src}")
                out.append(f"{gut} | " + _color("1;31", caret, color))
        elif file_path:
            out.append(f"  --> {where}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
