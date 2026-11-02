"""
MCN Formatter — `mcn fmt`

Reformats MCN source code to a canonical style:
  - 4-space indentation (tabs → spaces)
  - One blank line between top-level declarations
  - Single space around operators and after commas
  - Trailing whitespace removed, runs of blank lines collapsed to one
  - Exactly one newline at end of file

Design: line-based (not AST-based) so it never loses comments; string
literals and comments are copied verbatim.  As a safety net the output is
re-lexed and must yield exactly the same tokens as the input — otherwise the
source is returned unchanged, so formatting can never change what a program
means.  Lines inside multi-line strings / bracketed expressions keep their
original layout.

Usage:
    mcn fmt script.mx               # print formatted to stdout
    mcn fmt --write script.mx       # rewrite file in place
    mcn fmt --check script.mx       # exit 1 if file needs formatting
    mcn fmt --write src/            # rewrite all .mx/.mcn files in dir
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

from .lexer import KEYWORDS, Lexer, TT


# ── Lexical tables ────────────────────────────────────────────────────────────

_KEYWORDS       = set(KEYWORDS)                 # var, if, for, in, return, ...
_VALUE_KEYWORDS = {"true", "false", "null", "none", "True", "False", "None"}

# Keywords that are also commonly called like functions: agent("create", ...)
_CALLABLE_KEYWORDS = {"agent", "pipeline", "workflow", "service", "contract",
                      "prompt", "mcp", "component", "app", "task", "stage",
                      "endpoint", "step", "port", "route", "include"}

# Longest first so that "+=" wins over "+", "?." over "?", etc.
_OPERATORS = sorted([
    "==", "!=", ">=", "<=", "+=", "-=", "*=", "/=", "%=", "=>", "?.",
    "=", "+", "-", "*", "/", "%", ">", "<", "?", ":", ",", ".",
    "(", ")", "[", "]", "{", "}",
], key=len, reverse=True)

# Operators rendered with one space on each side.
_SPACED_OPS = {"==", "!=", ">=", "<=", "+=", "-=", "*=", "/=", "%=", "=>",
               "=", "+", "-", "*", "/", "%", ">", "<", "?"}
_OPEN, _CLOSE = "([{", ")]}"

# After these a `{` opens an object literal (mirrors the lexer's rule);
# otherwise, at bracket depth 0, it opens a curly-brace statement block.
_EXPR_EXPECTING_OPS   = _SPACED_OPS | {"(", "[", "{", ",", ":"}
_EXPR_EXPECTING_WORDS = {"return", "and", "or", "not"}

# Top-level declarations that get a blank line before them
_TOP_LEVEL_DECLS = {"function", "pipeline", "service", "workflow", "contract",
                    "prompt", "agent", "test", "component", "app", "mcp"}


class _Piece:
    """One lexical piece of a physical line."""
    __slots__ = ("kind", "text", "space_before")

    def __init__(self, kind: str, text: str, space_before: bool):
        self.kind         = kind          # word | num | str | op | comment | other
        self.text         = text
        self.space_before = space_before  # whitespace preceded it in the source


class _ScanState:
    """Lexical state carried from one physical line to the next."""
    __slots__ = ("brackets", "open_block")

    def __init__(self):
        self.brackets: List[bool] = []    # open ( [ {: True = grouping bracket
        self.open_block: Optional[str] = None   # terminator of a construct
                                                # spanning lines: '"""', "'''",
                                                # '*/', or a quote char

    @property
    def depth(self) -> int:
        return sum(self.brackets)

    @property
    def continues(self) -> bool:
        """True if the logical line continues on the next physical line."""
        return self.open_block is not None or self.depth > 0


class Formatter:
    """
    Formats a single MCN source string.
    """

    INDENT_SIZE = 4

    def __init__(self, source: str):
        self._source = source

    def format(self) -> str:
        """Return the formatted source string (or the input, if unsafe)."""
        try:
            original = _token_signature(self._source)
        except Exception:
            return self._source               # can't lex — leave it alone
        try:
            formatted = self._format_lines(self._source)
            if _token_signature(formatted) != original:
                return self._source           # would change meaning — refuse
        except Exception:
            return self._source
        return formatted

    # ── Line pass ─────────────────────────────────────────────────────────────

    def _format_lines(self, source: str) -> str:
        text = source.replace("\r\n", "\n").replace("\r", "\n")
        src_lines = [l.expandtabs(Lexer.TAB_WIDTH) for l in text.split("\n")]

        out: List[str]          = []
        pending: List[Tuple[int, str]] = []   # (width, text) comment/blank lines
        indent_stack: List[int] = [0]
        state                   = _ScanState()
        render_level: Optional[int] = None    # level of an enclosing `render`

        def emit_blank():
            if out and out[-1] != "":
                out.append("")

        def flush_pending(code_width: int, level: int, old_stack: List[int]):
            for width, body in pending:
                if body == "":
                    emit_blank()
                    continue
                if width > code_width:
                    # e.g. a trailing comment at the end of a deeper block
                    lvl = max(i for i, w in enumerate(old_stack) if w <= width)
                else:
                    lvl = level
                out.append(" " * (lvl * self.INDENT_SIZE) + body)
            pending.clear()

        for raw in src_lines:
            line = raw.rstrip()

            # Physical line inside a multi-line string / comment / bracket
            # expression: copy verbatim, but keep tracking lexical state.
            if state.continues:
                _scan_line(line, state)
                out.append(line)
                continue

            stripped = line.lstrip()
            if not stripped:
                pending.append((0, ""))
                continue

            width  = len(line) - len(stripped)
            pieces = _scan_line(stripped, state)

            if pieces and pieces[0].kind == "comment" and not state.continues:
                pending.append((width, stripped))
                continue

            # Resolve indentation level exactly like the lexer does.
            old_stack = list(indent_stack)
            if width > indent_stack[-1]:
                indent_stack.append(width)
            else:
                while indent_stack[-1] > width:
                    indent_stack.pop()
                if indent_stack[-1] != width:
                    raise ValueError("inconsistent dedent")
            level = len(indent_stack) - 1

            if render_level is not None and level <= render_level:
                render_level = None
            in_render = render_level is not None

            first = pieces[0].text if pieces else ""
            if level == 0 and first in _TOP_LEVEL_DECLS:
                emit_blank()
            flush_pending(width, level, old_stack)

            if state.continues:
                body = stripped      # statement spans lines: keep its spacing
            else:
                body = _join(pieces, tight_assign=in_render)
            out.append(" " * (level * self.INDENT_SIZE) + body)

            if first == "render" and len(pieces) == 1:
                render_level = level

        flush_pending(0, 0, indent_stack)
        while out and out[0] == "":
            out.pop(0)
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"


def _token_signature(source: str) -> List[tuple]:
    """Token stream used to verify that formatting preserved meaning.

    Runs of NEWLINE tokens are collapsed (blank / comment-only lines and a
    missing final newline carry no meaning)."""
    sig: List[tuple] = []
    for t in Lexer(source + "\n").tokenize():
        if t.type == TT.NEWLINE and sig and sig[-1][0] == TT.NEWLINE:
            continue
        sig.append((t.type, t.value))
    return sig


def _find_close(text: str, term: str, start: int) -> int:
    """Index just past `term` in text[start:], or -1.  Honours backslash
    escapes for single-character quote terminators."""
    if len(term) > 1:
        end = text.find(term, start)
        return -1 if end < 0 else end + len(term)
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == term:
            return i + 1
        i += 1
    return -1


def _scan_line(text: str, state: _ScanState) -> List[_Piece]:
    """Split one physical line into pieces, updating the carried state."""
    pieces: List[_Piece] = []
    i, n  = 0, len(text)
    space = False

    if state.open_block is not None:          # finish a construct from above
        end = _find_close(text, state.open_block, 0)
        if end < 0:
            return pieces
        state.open_block = None
        i = end

    while i < n:
        ch = text[i]
        if ch in " \t":
            space = True
            i += 1
            continue
        start = i
        if text.startswith("//", i):
            pieces.append(_Piece("comment", text[i:], space))
            break
        if text.startswith("/*", i) or text.startswith('"""', i) or \
                text.startswith("'''", i):
            opener = text[i:i + 2] if text.startswith("/*", i) else text[i:i + 3]
            term   = "*/" if opener == "/*" else opener
            end    = _find_close(text, term, i + len(opener))
            kind   = "comment" if opener == "/*" else "str"
            if end < 0:
                pieces.append(_Piece(kind, text[i:], space))
                state.open_block = term
                break
            pieces.append(_Piece(kind, text[i:end], space))
            i = end
        elif ch in "\"'":
            end = _find_close(text, ch, i + 1)
            if end < 0:                       # string continues (inside brackets)
                pieces.append(_Piece("str", text[i:], space))
                state.open_block = ch
                break
            pieces.append(_Piece("str", text[i:end], space))
            i = end
        elif ch.isdigit():
            while i < n and (text[i].isdigit() or
                             (text[i] == "." and i + 1 < n and text[i + 1].isdigit())):
                i += 1
            pieces.append(_Piece("num", text[start:i], space))
        elif ch.isalpha() or ch == "_":
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            pieces.append(_Piece("word", text[start:i], space))
        else:
            op = next((o for o in _OPERATORS if text.startswith(o, i)), None)
            if op is None:
                pieces.append(_Piece("other", ch, space))
                i += 1
            else:
                if op in _OPEN:
                    prev = pieces[-1] if pieces else None
                    grouping = (op != "{" or state.depth > 0 or (prev is not None and (
                        (prev.kind == "op" and prev.text in _EXPR_EXPECTING_OPS) or
                        (prev.kind == "word" and prev.text in _EXPR_EXPECTING_WORDS))))
                    state.brackets.append(grouping)
                elif op in _CLOSE and state.brackets:
                    state.brackets.pop()
                pieces.append(_Piece("op", op, space))
                i += len(op)
        space = False
    return pieces


def _is_operand_end(p: Optional[_Piece]) -> bool:
    """True if `p` can end an operand (so a following '-' is binary)."""
    if p is None:
        return False
    if p.kind in ("num", "str"):
        return True
    if p.kind == "word":
        return p.text not in _KEYWORDS or p.text in _VALUE_KEYWORDS
    return p.kind == "op" and p.text in _CLOSE


def _join(pieces: List[_Piece], tight_assign: bool = False) -> str:
    """Re-join the pieces of one complete logical line with canonical spacing.

    tight_assign: inside a `render` block, `key=value` UI attributes stay tight.
    """
    out: List[str] = []
    prev: Optional[_Piece] = None
    prev_unary = False
    ternary    = 0
    for p in pieces:
        t     = p.text
        is_op = p.kind == "op"
        unary = is_op and t in ("-", "+") and not _is_operand_end(prev)
        if is_op and t == "?":
            ternary += 1

        if prev is None:
            sep = ""
        elif p.kind == "comment":
            sep = " "
        elif tight_assign and "=" in ((t if is_op else ""),
                                      (prev.text if prev.kind == "op" else "")):
            sep = ""                                    # label="Tasks"
        elif prev.kind == "op" and prev.text in _OPEN:
            sep = ""
        elif is_op and (t in _CLOSE or t in (",", ".", "?.")):
            sep = ""
        elif prev.kind == "op" and prev.text in (".", "?."):
            sep = ""
        elif prev_unary:
            sep = ""
        elif is_op and t == ":":
            if ternary > 0:
                ternary -= 1
                sep = " "
            else:
                sep = ""
        elif prev.kind == "op" and prev.text in (",", ":"):
            sep = " "
        elif is_op and t in ("(", "[") and prev.kind == "word":
            # f(x) / items[0], but `if (x)` / `return [..]` for keywords
            keyword = (prev.text in _KEYWORDS and prev.text not in _VALUE_KEYWORDS
                       and prev.text not in _CALLABLE_KEYWORDS)
            sep = " " if keyword else ""
        elif is_op and t in ("(", "[") and (
                prev.kind in ("num", "str") or
                (prev.kind == "op" and prev.text in _CLOSE)):
            sep = ""                                    # f(a)(b), m[0][1]
        elif is_op and t in _SPACED_OPS and not unary:
            sep = " "
        elif prev.kind == "op" and prev.text in _SPACED_OPS:
            sep = " "
        elif p.kind == "other" or prev.kind == "other":
            sep = " " if p.space_before else ""
        else:
            sep = " "
        out.append(sep + t)
        prev, prev_unary = p, unary
    return "".join(out)


# ── File-level helpers ────────────────────────────────────────────────────────

def format_source(source: str) -> str:
    return Formatter(source).format()


def format_file(filepath: str, write: bool = False,
                check: bool = False) -> int:
    """
    Format a single file.

    write=False, check=False → print to stdout
    write=True               → rewrite file in place, print diff summary
    check=True               → exit 1 if formatting would change the file
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()
    except OSError as e:
        print(f"fmt: cannot read '{filepath}': {e}")
        return 1

    formatted = format_source(original)

    if check:
        if formatted != original:
            print(f"fmt: {filepath} — needs formatting")
            return 1
        return 0

    if write:
        if formatted != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"fmt: {filepath} — reformatted")
        else:
            print(f"fmt: {filepath} — already formatted")
        return 0

    # Default: print to stdout
    print(formatted, end="")
    return 0


def format_directory(dirpath: str, write: bool = False,
                     check: bool = False) -> int:
    """Format all .mx and .mcn files under `dirpath`."""
    root  = Path(dirpath)
    files = sorted(list(root.rglob("*.mx")) + list(root.rglob("*.mcn")))

    if not files:
        print(f"fmt: no .mx or .mcn files found in {dirpath}")
        return 0

    exit_code = 0
    for f in files:
        code = format_file(str(f), write=write, check=check)
        if code != 0:
            exit_code = code
    return exit_code


# ── CLI entry point ───────────────────────────────────────────────────────────

def run_fmt(path: str, write: bool = False, check: bool = False) -> int:
    """Entry point for `mcn fmt <file-or-dir>`."""
    p = Path(path)
    if p.is_dir():
        return format_directory(path, write=write, check=check)
    return format_file(path, write=write, check=check)
