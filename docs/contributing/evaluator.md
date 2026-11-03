# Evaluator and runtime

`evaluator.py` runs the AST directly (a tree-walking interpreter). `MCNInterpreter` in `mcn_interpreter.py` owns an `Evaluator`, registers every built-in into it, and is what the CLI, server, tests and Studio call.

```python
from mcn.core_engine.mcn_interpreter import MCNInterpreter

interp = MCNInterpreter()
interp.execute('var x = 2\nlog(x * 21)', quiet=True)
```

## Execution

- `execute_program(program)` first defines every top-level `function` (so they can be called before their definition), then runs statements in order.
- `_exec_block(stmts, env)` runs a block; `_eval(expr, env)` evaluates an expression.
- `return`, `break` and `continue` are implemented as Python exceptions (`ReturnSignal`, `BreakSignal`, `ContinueSignal`) caught by the enclosing function or loop.
- `while` loops stop with an error after a large iteration cap instead of hanging.

## Scopes

`Environment` is a dictionary with a parent pointer. Functions get a new environment whose parent is the one they were defined in (closures). Lookups walk outward; a missing name raises `Undefined variable` with a "Did you mean" suggestion from `difflib`.

Built-ins live in `Evaluator.functions` rather than the environment, so user variables can shadow them without breaking other code.

## Calls

`_eval_call` resolves the callee, evaluates positional and named arguments, and calls it:

- **User functions** check arity themselves and raise `ArgumentCountError` naming the missing or extra parameters.
- **Built-ins** are Python callables; Python's `TypeError` messages are rewritten into MCN terms (`_friendly_call_error`).
- **Methods.** For `x.name(args)`: a dict key or Python attribute of that name wins; otherwise a built-in or user function `name(x, args)` is called. A missing method raises "A text value has no method 'x'" with a suggestion.

## Values

MCN values are Python values: `int`/`float`, `str`, `bool`, `None` (null), `list` and `dict`. Property access on a dict is a key lookup that returns `None` when missing; `?.` short-circuits on `None`. Operators are applied in `_apply_binary`; a `TypeError` there becomes "Can't use '>' with a number (5) and null".

## Runtime services

| Feature | Implementation |
|---|---|
| `query()` | `MCNRuntime` in `mcn_runtime.py`: one SQLite connection per interpreter (`check_same_thread=False` plus a lock, so tasks can use it); optional PostgreSQL/MongoDB |
| `trigger()`, `fetch()` | `requests`, with a 5s connect timeout |
| `task` / `await` | `MCNAsyncRuntime` in `mcn_extensions.py`: a thread pool; `await` returns a `TaskResults` dict that also accepts positions |
| `device()` | `MCNIoTConnector` in `mcn_v3_extensions.py`, shared with Studio's simulator |
| AI | `ai_builtins.py`: provider dispatch (Anthropic, OpenAI, Ollama, mock), with each call recorded in `ai_trace.py` for the inspector |
| `use` | `mcn_packages.py`: loads a package's functions into the evaluator, flat and as a namespace object |

## Errors

Runtime errors are `MCNError(message, line, col)`. `MCNInterpreter.execute()` converts any failure into an `MCNDiagnosticError`, whose `str()` is the friendly report and whose `.diagnostic` holds the structured location. See [diagnostics](diagnostics.md).
