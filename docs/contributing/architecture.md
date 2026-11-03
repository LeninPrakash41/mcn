# Architecture

MCN is a Python package. Source text goes through a lexer and parser to an AST, which a tree-walking evaluator runs; the same AST feeds the static checker, the formatter and the React compiler.

```text
             source (.mcn)
                  │
            lexer.py ── tokens, INDENT/DEDENT
                  │
            parser.py ── AST (ast_nodes.py)
     ┌────────────┼───────────────┬──────────────────┐
evaluator.py  diagnostics.py   ui_compiler.py     formatter.py
(run)         name_check.py    (React project)    (mcn fmt)
              type_checker.py
              (mcn check)
     │
mcn_interpreter.py ── wires built-ins, packages, AI, runtime
     │
 ┌───┴───────────────┬────────────────┐
mcn_cli.py      mcn_server.py     web-playground/ (Studio)
(mcn …)         (mcn serve)       Flask + Monaco
```

## Repository layout

| Path | Contents |
|---|---|
| `mcn/core_engine/` | The language: lexer, parser, AST, evaluator, interpreter, built-ins, checker, compiler, server, CLI |
| `mcn/ai/` | `mcn generate` (`mcn_agent.py`) and the language spec given to the model |
| `mcn/fullstack/` | Flutter project generator |
| `mcn/web-playground/` | Studio: `server.py`, `playground_server/` blueprints, `static/` CSS and JS, `index.html` |
| `mcn/studio/vscode-mcn/` | VS Code extension and language server (TypeScript) |
| `examples/`, `use-cases/` | Scripts, each run twice in CI |
| `docs/pilot/` | Student pilot kit |
| `website/` | This site (`build_docs.py` builds the docs data) |
| `tests/` | pytest suite |

## Core engine files

| File | Role |
|---|---|
| `lexer.py` | Characters → tokens, with line/column on each and INDENT/DEDENT for blocks |
| `parser.py` | Recursive-descent parser: tokens → `Program` AST; collects syntax errors |
| `ast_nodes.py` | Dataclasses for every statement and expression |
| `evaluator.py` | Runs the AST: scopes, calls, operators, control flow, runtime errors |
| `mcn_interpreter.py` | The public entry point: registers built-ins and packages, runs code, turns errors into friendly reports |
| `stdlib_builtins.py`, `ai_builtins.py`, `mcn_runtime.py` | Built-in functions (text, lists, time, crypto, AI, HTTP, database) |
| `mcn_packages.py` | The package registry: bundled packages, local packages, `use` |
| `diagnostics.py`, `name_check.py`, `type_checker.py` | Error formatting and the static checks behind `mcn check` |
| `ui_compiler.py` | Components → a React + Tailwind + shadcn/ui project |
| `mcn_server.py` | `mcn serve`: endpoints over HTTP, with FastAPI or the standard library |
| `test_runner.py`, `formatter.py` | `mcn test` and `mcn fmt` |
| `project_init.py` | `mcn init` and `mcn validate` |
| `mcn_cli.py` | Argument parsing and dispatch for every `mcn` command |

## Design choices

- **One AST, many consumers.** The checker, compiler and formatter read the same tree the evaluator runs, so they can't disagree about what code means.
- **Errors are data.** Every error becomes a `Diagnostic` (kind, message, line, column, length, hint). The CLI renders it as text, Studio as an editor marker and VS Code as a squiggle.
- **Friendly over clever.** The language favours forgiving reads (`null` for missing keys, method calls on built-ins) and strict, explained failures (`5 > null` is an error naming the null side).
- **Everything is tested end to end.** Templates are built and type-checked, examples run twice, and documentation samples are checked.
