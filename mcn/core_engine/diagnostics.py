"""
Student-friendly error reports.

Every lexer, parser and runtime error goes through `diagnose()`, which turns
"[2:5] RuntimeError: Undefined variable: 'totl'. Did you mean 'total'?" into:

    Name error on line 2, column 5: Undefined variable 'totl'
       2 | log(totl)
         |     ^^^^
    Hint: Did you mean 'total'?
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_LOCATED = re.compile(r"^\[(\d+):(\d+)\]\s*(LexError|ParseError|RuntimeError):\s*(.*)$", re.S)

# What a "(got TYPE 'value')" suffix means in plain words
_FOUND = {
    "EOF": "reached the end of the file",
    "NEWLINE": "the line ended",
    "DEDENT": "the indented block ended",
    "INDENT": "found an unexpected indent",
}

# message pattern → hint shown under the source line
_HINTS = [
    (r"Unterminated string",
     'Close the string with a matching quote on the same line, or use triple quotes """...""" '
     "for text that spans several lines."),
    (r"doesn't match any enclosing block|unindent",
     "Line this up with the block it belongs to. Use 4 spaces per level and don't mix tabs and spaces."),
    (r"Expected an indented block",
     "Lines inside if / for / while / function / endpoint must be indented under it."),

    (r"Expected '\]'.*end of the file",
     "A '[' is never closed. Add the missing ']'."),
    (r"Can't use '.*' with .*null",
     "One side is null: a variable that was never set, a missing object key, or a query that returned no rows."),
    (r"Can't use '.*' with",
     "Convert first, e.g. int(text) or str(number), or check which value has the wrong type."),
    (r"Division by zero",
     "Check that the divisor isn't 0 before dividing."),
    (r"Undefined variable",
     "Declare it first with `var name = ...`, or check the spelling."),
    (r"Undefined function",
     "Define it with `function name(...)`, or check the spelling. Built-in packages need `use package_name`."),
    (r"is missing (an argument|arguments)|takes .* argument",
     "Check the number of values you pass matches the function's parameters."),
    (r"Package '.*' not found",
     "Check the package name, or run `mcn packages` to list what's available."),
]


@dataclass
class Diagnostic:
    kind: str          # "Syntax error" | "Name error" | "Runtime error"
    message: str
    line: int = 0
    col: int = 0
    hint: str = ""
    length: int = 1    # how many characters to underline
    severity: str = "error"   # "error" | "warning"

    def to_dict(self) -> dict:
        return asdict(self)


def diagnose(raw: str) -> Diagnostic:
    """Parse a raw MCN error message into a Diagnostic."""
    raw = raw.strip()
    for prefix in ("MCN SYNTAX_ERROR: ", "MCN REFERENCE_ERROR: ", "MCN RUNTIME_ERROR: "):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    m = _LOCATED.match(raw)
    line = col = 0
    stage = "RuntimeError"
    message = raw
    if m:
        line, col, stage, message = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4).strip()

    # "(got TYPE 'value')" → ", but found 'value'" / ", but the line ended"
    def _found(g: re.Match) -> str:
        ttype, value = g.group(1), g.group(2)
        return f", but {_FOUND[ttype]}" if ttype in _FOUND else f", but found '{value}'"
    message = re.sub(r"\s*\(got (\w+) '((?:[^'\\]|\\.)*)'\)", _found, message)
    message = re.sub(r"(, but [^,]+)\1", r"\1", message)   # parser sometimes repeats the suffix

    hint = ""
    dym = re.search(r"\s*Did you mean (.+\?)\s*$", message)
    if dym:
        hint = "Did you mean " + dym.group(1)
        message = message[:dym.start()]
    message = message.rstrip(". ")
    message = re.sub(r"^(Undefined (?:variable|function)): '([^']+)'", r"\1 '\2'", message)

    if stage in ("LexError", "ParseError"):
        kind = "Syntax error"
    elif message.startswith("Undefined"):
        kind = "Name error"
    else:
        kind = "Runtime error"

    if not hint:
        for pattern, text in _HINTS:
            if re.search(pattern, message):
                hint = text
                break

    name = re.search(r"'([A-Za-z_]\w*)'", message)
    length = len(name.group(1)) if name and kind == "Name error" else 1
    return Diagnostic(kind=kind, message=message, line=line, col=col, hint=hint, length=length)


def render(diag: Diagnostic, source: str = "") -> str:
    """Multi-line report with the offending source line and a caret."""
    where = f" on line {diag.line}, column {diag.col}" if diag.line else ""
    out = [f"{diag.kind}{where}: {diag.message}"]
    lines = source.splitlines()
    if diag.line and 0 < diag.line <= len(lines):
        text = lines[diag.line - 1].rstrip()
        gutter = f"{diag.line:>4} | "
        out.append(gutter + text)
        out.append(" " * (len(gutter) - 2) + "| " + " " * max(diag.col - 1, 0) + "^" * max(diag.length, 1))
    if diag.hint:
        out.append(f"Hint: {diag.hint}")
    return "\n".join(out)

def check(source: str) -> list:
    """Find problems without running the code: the first syntax error, or
    else every reference to a name that is never defined.

    Shared by `mcn check`, the Studio editor and the VS Code extension, so all
    three report exactly what `mcn run` would.
    """
    from .lexer import Lexer
    from .parser import Parser
    from .name_check import undefined_names, did_you_mean
    try:
        parser = Parser(Lexer(source).tokenize())
        program = parser.parse()
    except Exception as exc:
        return [diagnose(str(exc))]
    if parser.errors:
        return [diagnose(str(parser.errors[0]))]
    return [
        diagnose(f"[{line}:{col}] RuntimeError: Undefined {kind}: '{name}'.{did_you_mean(name, program)}")
        for name, line, col, kind in undefined_names(program)
    ]


class MCNDiagnosticError(Exception):
    """Raised by MCNInterpreter.execute: str() is the friendly report;
    `.diagnostic` carries the structured location for editors."""

    def __init__(self, diagnostic: Diagnostic, source: str = "", error_type: str = "RUNTIME_ERROR"):
        self.diagnostic = diagnostic
        self.error_type = error_type
        super().__init__(render(diagnostic, source))
