# Diagnostics and mcn check

All error reporting goes through `mcn/core_engine/diagnostics.py`.

## The Diagnostic

```python
@dataclass
class Diagnostic:
    kind: str          # "Syntax error" | "Name error" | "Runtime error" | "Type error" | "Warning"
    message: str
    line: int = 0
    col: int = 0
    hint: str = ""
    length: int = 1    # characters to underline
    severity: str = "error"
```

- `diagnose(raw)` parses an internal message like `[2:5] RuntimeError: Undefined variable: 'totl'. Did you mean 'total'?` into a `Diagnostic`. It rewrites parser jargon (`(got NEWLINE '\n')` → "but the line ended"), moves "Did you mean" into the hint, and otherwise picks a hint from the `_HINTS` table by matching the message.
- `render(diag, source)` produces the text report with the source line and caret.
- `MCNDiagnosticError` carries both, so the CLI prints the text and Studio reads `.diagnostic` to place an editor marker.

## mcn check

`check(source)` returns the problems `mcn run` would hit, without running anything:

1. **Syntax:** lex and parse; if `parser.errors` is non-empty, return the first one.
2. **Names:** `name_check.undefined_names(program)` reports every reference to a name that is never defined.

The CLI then adds `type_checker.check_source()` results (wrong argument counts for built-ins, operators on incompatible literal types), sorts everything by position, and prints text or JSON.

## Undefined-name detection

`name_check.py` is deliberately conservative — it must never flag working code:

- A name counts as defined if it's declared **anywhere** in the file, in any scope or order: `var`, functions and their parameters, loop variables, `catch` variables (a bare `catch` defines `error`), services, endpoints, components and their state, UI `on` handlers.
- Runtime names come from a fresh interpreter plus the test helpers (`assert_equal`, ...).
- `use "pkg"` adds the package's exports; an unknown package or an `include` disables the check for that file.
- Object keys (`{success: true}`) aren't references.
- In UI files, calls to unknown functions are backend endpoints, so they're allowed.

Every example, template and docs sample passes this check; `tests/test_developer_tools.py` holds the false-positive cases.

## Where diagnostics appear

| Surface | How |
|---|---|
| `mcn run` | `MCNDiagnosticError` text on stderr, exit code 1 |
| `mcn check` | Text, or `--json` for tools |
| Studio | `/api/execute` returns `diagnostic`; `workspace.js` sets a Monaco marker and shows a banner |
| VS Code | The language server runs `mcn check --json` on the unsaved text |
