# Error messages

Every error has the same shape: what went wrong and where, the line with a caret under the problem, and usually a hint.

```output
Syntax error on line 2, column 1: Expected an indented block after 'function' on line 1
   2 | return celsius * 9 / 5 + 32
     | ^
Hint: Lines inside if / for / while / function / endpoint must be indented under it.
```

`mcn run`, `mcn check`, Studio and the VS Code extension all report the same messages.

## Kinds

| Kind | Found by | Meaning |
|---|---|---|
| **Syntax error** | Before running | The code can't be read: indentation, brackets, quotes |
| **Name error** | Before running (`mcn check`) and while running | A variable or function that's never defined |
| **Runtime error** | While running | Something failed with real values: dividing by zero, comparing with null |
| **Type error** | `mcn check` | Wrong types or argument counts for built-ins |

## Common errors

| Message | Fix |
|---|---|
| `Expected an indented block after 'if'` | Indent the lines under `if`/`for`/`while`/`function` by 4 spaces |
| `This line is indented N spaces, which doesn't match any enclosing block` | Line it up with the block it belongs to; don't mix tabs and spaces |
| `This '(' is never closed` | Add the missing `)` — the caret points at the opening one |
| `Unterminated string literal` | Close the quote, or use `"""triple quotes"""` across lines |
| `Undefined variable 'x'` | Declare it with `var x = ...` first, or fix the spelling (see the hint) |
| `Undefined function 'f'` | Define it, fix the spelling, or `use` the package that provides it |
| `f() takes 1 argument (a) but 2 were given` | Pass as many values as the function has parameters |
| `f() is missing an argument: b` | Pass the missing value, or give the parameter a default |
| `A text value has no method 'x'` | The value doesn't support that method; the hint suggests the closest one |
| `Can't use '>' with a number (5) and null` | One side is null: a variable never set, a missing key, or an empty query result |
| `Division by zero` | Check the divisor before dividing |
| `Package 'x' not found` | Check the name with `mcn packages list` |

## More detail

Set `MCN_VERBOSE=1` to print the engine's internal log as well. Full error details also go to `~/.mcn/logs/mcn_errors.log`.
