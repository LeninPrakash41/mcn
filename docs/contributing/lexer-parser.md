# Lexer and parser

## Lexer

`Lexer(source).tokenize()` in `mcn/core_engine/lexer.py` returns a flat list of `Token(type, value, line, col)`.

**Indentation.** At the start of each line the lexer measures leading spaces (a tab counts as 4) and compares them with a stack of open levels, like Python's tokenizer:

- deeper than the top of the stack → emit `INDENT` and push the level;
- shallower → emit one `DEDENT` per level popped; a level that matches nothing is a `LexError` ("This line is indented N spaces, which doesn't match any enclosing block");
- blank and comment-only lines don't change indentation.

**Continuation lines.** No `NEWLINE`/`INDENT` is emitted while inside `()`, `[]` or `{}`, after a trailing operator, after a `\` at the end of a line, or after the `:` of a ternary (`cond ? a :` on one line, `b` on the next), so long expressions can wrap.

**Strings.** `"..."` and `'...'` on one line, `"""..."""` across lines. An unclosed quote is a `LexError` with a hint about triple quotes.

**Keywords.** Words like `var`, `if`, `service` and `component` have their own token types. A set of *soft keywords* (`test`, `tool`, `agent`, `state`, `layout`, `render`, `schedule` and others) are retyped as identifiers when used as names, so `agent(...)` and `var state = 1` still work.

## Parser

`Parser(tokens).parse()` in `parser.py` is a hand-written recursive-descent parser that returns an `ast.Program`.

- `_statement()` dispatches on the first token: declarations (`var`, `function`, `service`, `component`, `app`, `test`, ...), control flow, or an expression statement.
- `_expression()` is a precedence-climbing chain: ternary → `or` → `and` → equality → comparison → `+ -` → `* / %` → unary → call/index/property → primary.
- `_block()` expects `NEWLINE INDENT statements DEDENT`; a missing indent produces "Expected an indented block after 'if' on line N".

**Error recovery.** A `ParseError` is caught in `parse()`, appended to `parser.errors`, and the parser skips to the next statement (`_synchronize`). Tools that want every problem (the formatter, the legacy linter) can keep going, but `MCNInterpreter.execute()` and `mcn check` stop at `parser.errors[0]` — a half-parsed program never runs.

**Locations.** Nodes carry `line` and `col`. Calls are located at the callee, so an undefined function's caret points at its name.

## UI syntax

Inside `render`, each line is a `UIElement(tag, attrs, text, children)`. Attributes are `key=value`, where the value is any expression; JSX-style `key={expr}` is also accepted. The `app` block's `layout` produces a `LayoutBlock` with `sidebar`, `tabs`, `main` and `routes`.

## Adding syntax

1. Add the token (if any) to `TT` and the keyword table in `lexer.py`.
2. Add an AST dataclass to `ast_nodes.py`.
3. Parse it in `parser.py` (usually a new branch in `_statement` or a precedence level).
4. Execute it in `evaluator.py`, and teach `name_check.py` about any names it declares.
5. Add tests to `tests/test_regressions.py`, and update the formatter and UI compiler if they need it.
