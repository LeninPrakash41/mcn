"""
MCN Formatter — `mcn fmt`

Reformats MCN source code to a canonical style:
  - 4-space indentation (tabs → spaces)
  - One blank line between top-level declarations
  - Single space around operators and after commas
  - Trailing whitespace removed
  - Exactly one newline at end of file

Design: token-based (not AST-based) so it never loses comments.
Works even if the file has minor syntax errors.

Usage:
    mcn fmt script.mx               # print formatted to stdout
    mcn fmt --write script.mx       # rewrite file in place
    mcn fmt --check script.mx       # exit 1 if file needs formatting
    mcn fmt --write src/            # rewrite all .mx/.mcn files in dir
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .lexer import Lexer, Token, TT


# ── Token categories ──────────────────────────────────────────────────────────

_BINARY_OPS = {TT.PLUS, TT.MINUS, TT.STAR, TT.SLASH,
               TT.EQ, TT.NEQ, TT.GT, TT.GTE, TT.LT, TT.LTE,
               TT.ASSIGN, TT.AND, TT.OR}

_NO_SPACE_BEFORE = {TT.RPAREN, TT.RBRACKET, TT.RBRACE,
                    TT.COMMA, TT.COLON, TT.DOT, TT.SAFE_DOT,
                    TT.NEWLINE, TT.INDENT, TT.DEDENT, TT.EOF}

_NO_SPACE_AFTER  = {TT.LPAREN, TT.LBRACKET, TT.LBRACE,
                    TT.DOT, TT.SAFE_DOT, TT.NOT,
                    TT.INDENT, TT.DEDENT, TT.NEWLINE}

# These keywords introduce a block — followed by a newline & indent
_BLOCK_STARTERS = {TT.IF, TT.ELSE, TT.FOR, TT.WHILE, TT.FUNCTION,
                   TT.TRY, TT.CATCH,
                   TT.PIPELINE, TT.SERVICE, TT.WORKFLOW, TT.CONTRACT,
                   TT.PROMPT, TT.AGENT,
                   TT.STAGE, TT.ENDPOINT, TT.STEP,
                   TT.TEST}

# Top-level declarations that get a blank line before them
_TOP_LEVEL_DECLS = {TT.FUNCTION, TT.PIPELINE, TT.SERVICE,
                    TT.WORKFLOW, TT.CONTRACT, TT.PROMPT,
                    TT.AGENT, TT.TEST}


class Formatter:
    """
    Formats a single MCN source string.
    """

    INDENT_SIZE = 4

    def __init__(self, source: str):
        self._source = source

    def format(self) -> str:
        """Return the formatted source string."""
        try:
            tokens = Lexer(self._source).tokenize()
        except Exception:
            # Can't lex — return source unchanged
            return self._source

        return self._rebuild(tokens)

    # ── Rebuilding ────────────────────────────────────────────────────────────

    def _rebuild(self, tokens: List[Token]) -> str:
        lines: List[str]  = []
        indent_level: int = 0
        line_buf: List[str] = []
        prev_tt: Optional[TT] = None

        def flush_line():
            nonlocal line_buf
            content = "".join(line_buf).rstrip()
            if content:
                lines.append(" " * (indent_level * self.INDENT_SIZE) + content)
            else:
                lines.append("")
            line_buf = []

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            if tok.type == TT.EOF:
                break

            if tok.type == TT.INDENT:
                indent_level += 1
                i += 1
                continue

            if tok.type == TT.DEDENT:
                indent_level = max(0, indent_level - 1)
                i += 1
                continue

            if tok.type == TT.NEWLINE:
                flush_line()
                # Blank line before top-level declarations
                next_real = self._peek_real(tokens, i + 1)
                if (next_real and next_real.type in _TOP_LEVEL_DECLS
                        and indent_level == 0 and lines
                        and lines[-1] != ""):
                    lines.append("")
                i += 1
                prev_tt = TT.NEWLINE
                continue

            # Determine spacing before this token
            need_space = self._needs_space_before(tok, prev_tt)
            if need_space and line_buf:
                line_buf.append(" ")

            # Emit the token value
            line_buf.append(self._token_str(tok))

            # Space after comma
            if tok.type == TT.COMMA:
                line_buf.append(" ")

            prev_tt = tok.type
            i += 1

        flush_line()

        # Ensure exactly one trailing newline
        result = "\n".join(lines).rstrip("\n") + "\n"
        return result

    def _needs_space_before(self, tok: Token, prev_tt: Optional[TT]) -> bool:
        if prev_tt is None or prev_tt in _NO_SPACE_AFTER:
            return False
        if tok.type in _NO_SPACE_BEFORE:
            return False
        if tok.type == TT.LPAREN and prev_tt == TT.IDENTIFIER:
            return False   # function call: f(x) not f (x)
        if tok.type in _BINARY_OPS:
            return True
        if prev_tt in _BINARY_OPS:
            return True
        if tok.type in (TT.IDENTIFIER, TT.NUMBER, TT.STRING):
            return True
        return False

    def _token_str(self, tok: Token) -> str:
        if tok.type == TT.STRING:
            # Re-quote — preserve original quote char if possible
            val = tok.value
            if '"' not in val:
                return f'"{val}"'
            if "'" not in val:
                return f"'{val}'"
            # Has both — use double quotes and escape
            return '"' + val.replace('"', '\\"') + '"'
        if tok.type == TT.SAFE_DOT:
            return "?."
        return tok.value

    @staticmethod
    def _peek_real(tokens: List[Token], start: int) -> Optional[Token]:
        """Return the next non-newline, non-indent/dedent token."""
        for j in range(start, len(tokens)):
            tt = tokens[j].type
            if tt not in (TT.NEWLINE, TT.INDENT, TT.DEDENT):
                return tokens[j]
        return None


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
