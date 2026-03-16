"""
MCN Lexer — tokenizes MCN source code into a flat token stream.

Key improvements over v1:
  - Column tracking on every token (enables precise IDE errors: line:col)
  - INDENT / DEDENT tokens for proper indentation-based block parsing
    (same model as Python's tokenizer — eliminates all heuristic parsing)
  - Dedicated LexError with line + col context
  - Tab-to-spaces normalization (1 tab = 4 spaces)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List


# ── Token types ────────────────────────────────────────────────────────────────

class TT(Enum):
    # Literals
    NUMBER     = auto()
    STRING     = auto()

    # Identifiers & keywords
    IDENTIFIER = auto()
    VAR        = auto()
    IF         = auto()
    ELSE       = auto()
    FOR        = auto()
    IN         = auto()
    WHILE      = auto()
    FUNCTION   = auto()
    TRY        = auto()
    CATCH      = auto()
    THROW      = auto()
    RETURN     = auto()
    TASK       = auto()
    AWAIT      = auto()
    USE        = auto()
    AND        = auto()
    OR         = auto()
    NOT        = auto()

    # Operators
    ASSIGN = auto()   # =
    PLUS   = auto()   # +
    MINUS  = auto()   # -
    STAR   = auto()   # *
    SLASH  = auto()   # /
    EQ     = auto()   # ==
    NEQ    = auto()   # !=
    GT     = auto()   # >
    LT     = auto()   # <
    GTE    = auto()   # >=
    LTE    = auto()   # <=

    # Punctuation
    LPAREN   = auto()  # (
    RPAREN   = auto()  # )
    LBRACE   = auto()  # {
    RBRACE   = auto()  # }
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    COLON    = auto()  # :
    DOT      = auto()  # .
    COMMA    = auto()  # ,

    # 2030 language primitives
    PIPELINE = auto()   # pipeline
    SERVICE  = auto()   # service
    CONTRACT = auto()   # contract
    WORKFLOW = auto()   # workflow
    STAGE    = auto()   # stage  (inside pipeline)
    ENDPOINT = auto()   # endpoint (inside service)
    STEP     = auto()   # step  (inside workflow)
    PORT     = auto()   # port  (inside service)

    # AI / intelligent primitives (Layer 1 + Layer 2)
    PROMPT   = auto()   # prompt  (prompt template declaration)
    AGENT    = auto()   # agent   (agent declaration)

    # Loop control
    BREAK    = auto()   # break
    CONTINUE = auto()   # continue

    # Null-safe access
    SAFE_DOT = auto()   # ?.

    # Test framework
    TEST     = auto()   # test
    ASSERT   = auto()   # assert

    # UI / Frontend primitives
    COMPONENT = auto()  # component
    RENDER    = auto()  # render
    STATE     = auto()  # state   (inside component)
    ON        = auto()  # on      (event handler inside component)
    APP       = auto()  # app     (top-level app declaration)
    LAYOUT    = auto()  # layout  (inside app)
    INCLUDE   = auto()  # include (multi-file)
    ROUTE     = auto()  # route   (URL routing inside app)

    # Structure
    NEWLINE = auto()
    INDENT  = auto()
    DEDENT  = auto()
    EOF     = auto()


KEYWORDS: dict[str, TT] = {
    "var":      TT.VAR,
    "if":       TT.IF,
    "else":     TT.ELSE,
    "for":      TT.FOR,
    "in":       TT.IN,
    "while":    TT.WHILE,
    "function": TT.FUNCTION,
    "try":      TT.TRY,
    "catch":    TT.CATCH,
    "throw":    TT.THROW,
    "return":   TT.RETURN,
    "task":     TT.TASK,
    "await":    TT.AWAIT,
    "use":      TT.USE,
    "and":      TT.AND,
    "or":       TT.OR,
    "not":      TT.NOT,
    # 2030 language primitives
    "pipeline": TT.PIPELINE,
    "service":  TT.SERVICE,
    "contract": TT.CONTRACT,
    "workflow": TT.WORKFLOW,
    "stage":    TT.STAGE,
    "endpoint": TT.ENDPOINT,
    "step":     TT.STEP,
    "port":     TT.PORT,
    # AI / intelligent primitives
    "prompt":   TT.PROMPT,
    "agent":    TT.AGENT,
    # Loop control
    "break":    TT.BREAK,
    "continue": TT.CONTINUE,
    # Test framework
    "test":     TT.TEST,
    "assert":   TT.ASSERT,
    # UI / Frontend primitives
    "component": TT.COMPONENT,
    "render":    TT.RENDER,
    "state":     TT.STATE,
    "on":        TT.ON,
    "app":       TT.APP,
    "layout":    TT.LAYOUT,
    "include":   TT.INCLUDE,
    "route":     TT.ROUTE,
}


# ── Token dataclass ────────────────────────────────────────────────────────────

@dataclass
class Token:
    type:  TT
    value: str
    line:  int
    col:   int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


# ── Errors ─────────────────────────────────────────────────────────────────────

class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"[{line}:{col}] LexError: {message}")
        self.line = line
        self.col  = col


# ── Lexer ──────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Converts MCN source text into a token list.

    Indentation model (Python-style):
      - At the start of each non-blank, non-comment line, the leading
        whitespace is measured.
      - If it is deeper than the current level: emit INDENT, push level.
      - If it is shallower: pop levels and emit DEDENT for each.
      - Inconsistent dedent (not matching any prior level) is a LexError.
    """

    TAB_WIDTH = 4  # 1 tab counts as this many spaces

    def __init__(self, source: str):
        self._src            = source
        self._pos            = 0
        self._line           = 1
        self._col            = 1
        self._indent_stack: List[int] = [0]
        self._tokens: List[Token]     = []
        self._at_line_start           = True

    # ── Public API ─────────────────────────────────────────────────────────────

    def tokenize(self) -> List[Token]:
        while self._pos < len(self._src):
            if self._at_line_start:
                self._process_line_start()
            else:
                self._scan_one()

        # Close any open indentation blocks
        while len(self._indent_stack) > 1:
            self._indent_stack.pop()
            self._push(TT.DEDENT, "")

        self._push(TT.EOF, "")
        return self._tokens

    # ── Line-start indentation handling ────────────────────────────────────────

    def _process_line_start(self):
        """
        Called at the start of every new line.
        Measures indentation and emits INDENT / DEDENT as needed,
        then hands off to normal scanning.
        """
        indent, skipped = self._measure_indent()

        # If we exhausted the source while measuring, we're done
        if self._pos >= len(self._src):
            return

        ch = self._src[self._pos]

        # Blank line (only whitespace before newline)
        if ch == "\n":
            self._pos += 1
            self._line += 1
            self._col = 1
            return

        # Comment-only line — don't change indentation level
        if ch == "/" and self._peek() in ("/", "*"):
            self._at_line_start = False
            self._col = indent + 1
            return

        # Real content — resolve indentation
        self._col = indent + 1
        current = self._indent_stack[-1]

        if indent > current:
            self._indent_stack.append(indent)
            self._push(TT.INDENT, "")
        elif indent < current:
            while self._indent_stack[-1] > indent:
                self._indent_stack.pop()
                self._push(TT.DEDENT, "")
            if self._indent_stack[-1] != indent:
                raise LexError(
                    f"Inconsistent dedent "
                    f"(expected level {self._indent_stack[-1]}, got {indent})",
                    self._line, 1,
                )

        self._at_line_start = False

    def _measure_indent(self) -> tuple[int, int]:
        """
        Count leading spaces/tabs from current position.
        Returns (indent_level, chars_consumed).
        Advances self._pos past the whitespace.
        """
        indent = 0
        while self._pos < len(self._src) and self._src[self._pos] in (" ", "\t"):
            if self._src[self._pos] == "\t":
                indent += self.TAB_WIDTH
            else:
                indent += 1
            self._pos += 1
        return indent, 0  # second value reserved for future use

    # ── Token scanning ─────────────────────────────────────────────────────────

    def _scan_one(self):
        if self._pos >= len(self._src):
            return

        ch = self._src[self._pos]

        # Inline whitespace (not newline)
        if ch in (" ", "\t", "\r"):
            self._skip_inline_whitespace()
            return

        # Newline — end of logical line
        if ch == "\n":
            self._push(TT.NEWLINE, "\\n")
            self._pos  += 1
            self._line += 1
            self._col   = 1
            self._at_line_start = True
            return

        # Single-line comment  //
        if ch == "/" and self._peek() == "/":
            while self._pos < len(self._src) and self._src[self._pos] != "\n":
                self._pos += 1
                self._col += 1
            return

        # Block comment  /* ... */
        if ch == "/" and self._peek() == "*":
            self._scan_block_comment()
            return

        # String literals — triple-quoted (multi-line) or normal
        if ch in ('"', "'"):
            if self._src[self._pos : self._pos + 3] in ('"""', "'''"):
                self._scan_triple_string(ch)
            else:
                self._scan_string(ch)
            return

        # Numbers
        if ch.isdigit():
            self._scan_number()
            return

        # Identifiers & keywords
        if ch.isalpha() or ch == "_":
            self._scan_identifier()
            return

        # Two-character operators (check before single-char)
        two = self._src[self._pos : self._pos + 2]
        two_ops = {"==": TT.EQ, "!=": TT.NEQ, ">=": TT.GTE, "<=": TT.LTE,
                   "?.": TT.SAFE_DOT}
        if two in two_ops:
            self._push(two_ops[two], two)
            self._pos += 2
            self._col += 2
            return

        # Single-character tokens
        one_ops = {
            "=": TT.ASSIGN, "+": TT.PLUS,  "-": TT.MINUS,
            "*": TT.STAR,   "/": TT.SLASH,
            ">": TT.GT,     "<": TT.LT,
            "(": TT.LPAREN, ")": TT.RPAREN,
            "{": TT.LBRACE, "}": TT.RBRACE,
            "[": TT.LBRACKET, "]": TT.RBRACKET,
            ":": TT.COLON,  ".": TT.DOT,   ",": TT.COMMA,
        }
        if ch in one_ops:
            self._push(one_ops[ch], ch)
            self._pos += 1
            self._col += 1
            return

        # Unknown character — skip silently (could raise LexError in strict mode)
        self._pos += 1
        self._col += 1

    # ── Scanners ───────────────────────────────────────────────────────────────

    def _skip_inline_whitespace(self):
        while self._pos < len(self._src) and self._src[self._pos] in (" ", "\t", "\r"):
            self._pos += 1
            self._col += 1

    def _scan_block_comment(self):
        start_line, start_col = self._line, self._col
        self._pos += 2   # skip /*
        self._col += 2
        while self._pos < len(self._src) - 1:
            if self._src[self._pos] == "*" and self._src[self._pos + 1] == "/":
                self._pos += 2
                self._col += 2
                return
            if self._src[self._pos] == "\n":
                self._line += 1
                self._col   = 1
            else:
                self._col += 1
            self._pos += 1
        raise LexError("Unterminated block comment", start_line, start_col)

    def _scan_string(self, quote: str):
        start_line, start_col = self._line, self._col
        self._pos += 1   # opening quote
        self._col += 1
        buf: List[str] = []
        escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}

        while self._pos < len(self._src):
            ch = self._src[self._pos]
            if ch == quote:
                self._pos += 1
                self._col += 1
                self._push(TT.STRING, "".join(buf), start_line, start_col)
                return
            if ch == "\n":
                raise LexError("Unterminated string literal", start_line, start_col)
            if ch == "\\":
                self._pos += 1
                self._col += 1
                esc = self._src[self._pos] if self._pos < len(self._src) else ""
                buf.append(escapes.get(esc, esc))
            else:
                buf.append(ch)
            self._pos += 1
            self._col += 1

        raise LexError("Unterminated string literal", start_line, start_col)

    def _scan_triple_string(self, quote: str):
        """
        Scan a triple-quoted string:  \"\"\"...\"\"\"  or  '''...'''
        Allows embedded newlines.  No escape processing — what you write
        is what you get (useful for SQL, prompts, templates).
        """
        start_line, start_col = self._line, self._col
        triple = quote * 3
        self._pos += 3   # skip opening triple-quote
        self._col += 3
        buf: List[str] = []

        while self._pos < len(self._src):
            if self._src[self._pos : self._pos + 3] == triple:
                self._pos += 3
                self._col += 3
                self._push(TT.STRING, "".join(buf), start_line, start_col)
                return
            ch = self._src[self._pos]
            if ch == "\n":
                self._line += 1
                self._col = 1
            else:
                self._col += 1
            buf.append(ch)
            self._pos += 1

        raise LexError("Unterminated triple-quoted string", start_line, start_col)

    def _scan_number(self):
        start     = self._pos
        start_col = self._col
        has_dot   = False
        while self._pos < len(self._src):
            ch = self._src[self._pos]
            if ch == "." and not has_dot:
                has_dot = True
                self._pos += 1
                self._col += 1
            elif ch.isdigit():
                self._pos += 1
                self._col += 1
            else:
                break
        self._push(TT.NUMBER, self._src[start : self._pos], self._line, start_col)

    def _scan_identifier(self):
        start     = self._pos
        start_col = self._col
        while self._pos < len(self._src) and (
            self._src[self._pos].isalnum() or self._src[self._pos] == "_"
        ):
            self._pos += 1
            self._col += 1
        word = self._src[start : self._pos]
        tt   = KEYWORDS.get(word, TT.IDENTIFIER)
        self._push(tt, word, self._line, start_col)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _peek(self) -> str:
        nxt = self._pos + 1
        return self._src[nxt] if nxt < len(self._src) else ""

    def _push(self, tt: TT, value: str, line: int = 0, col: int = 0):
        self._tokens.append(
            Token(tt, value, line or self._line, col or self._col)
        )


# ── Backward-compat alias ──────────────────────────────────────────────────────
# Tests that import MCNLexer from the old location still work.
MCNLexer = Lexer
