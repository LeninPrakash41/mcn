# MCN Starter Guide

MCN lets you build a full application (database, backend API, web UI and a
mobile app) from one or two short files. This guide gets you from nothing to a
running app in about 30 minutes.

## 1. Install (10 minutes)

Run one command. On macOS or Linux, in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh
```

On Windows, in PowerShell:

```bash
powershell -c "irm https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.ps1 | iex"
```

Open a **new** terminal, then create your first project and run its tests:

```bash
mcn init hello-app
cd hello-app
mcn test backend/main.mcn
```

You should see `All 2 test(s) passed.`

## 2. Open MCN Studio

```bash
mcn studio .
```

Open **http://localhost:5003** in your browser. Studio only accepts connections
from your own computer, so it's safe to leave running.

- **Left:** your project files (`backend/main.mcn` for the server, `ui/app.mcn` for the screens).
- **Middle:** the editor.
- **Right:** live preview, database explorer, terminal output and simulators.
- **Run** (green ▶) executes the current file. **Preview** builds the web app.

## 3. The language in five minutes

```mcn
// Variables and text
var name = "Ada"
log("Hello, " + name)

// Lists and loops
var scores = [72, 88, 95]
for s in scores
    log(s)

// Decisions: indent the lines that belong to the if (4 spaces)
if avg(scores) > 80
    log("Great work")
else
    log("Keep going")

// Functions
function double(n)
    return n * 2

// A one-line decision
var label = "pass" if avg(scores) >= 50 else "fail"

// Store data (SQLite is built in)
query("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT)")
query("INSERT INTO notes (text) VALUES (?)", ("first note",))
var notes = query("SELECT * FROM notes")

// AI is a built-in function
var summary = ai("Summarise in one line: " + name + " wrote the first program")
```

A backend is a `service` with `endpoint`s; each endpoint becomes an API route:

```mcn
service notes_api
    port 8080

    endpoint list_notes()
        return {success: true, data: query("SELECT * FROM notes")}
```

Screens are `component`s with `state`, event handlers and a `render` tree; the
`app` block arranges them. See exercise 6 for a complete example.

## 4. Reading error messages

MCN tells you **where** the problem is and usually **how to fix it**:

```
Name error on line 2, column 5: Undefined variable 'totl'
   2 | log(totl)
     |     ^^^^
Hint: Did you mean 'total'?
```

1. The first line says what kind of problem it is and where.
2. The caret (`^^^^`) points at the exact spot. Studio also underlines it in red.
3. The hint suggests a fix. Spelling mistakes get a "Did you mean" suggestion.

The most common ones:

| Message | What to do |
|---|---|
| `Expected an indented block after 'if'` | Indent the lines under `if`/`for`/`function` by 4 spaces. |
| `This line is indented N spaces, which doesn't match` | Line it up with the block above it. Don't mix tabs and spaces. |
| `This '(' is never closed` | Add the missing `)`. |
| `Unterminated string literal` | Close the quote, or use `"""triple quotes"""` for text over several lines. |
| `add() is missing an argument: b` | Pass a value for every parameter. |

## 5. AI without an API key

`ai()`, `classify()`, `extract()` and `rag()` work without a key in **mock
mode**: they return placeholder answers so your program still runs. To get real
answers, set a key before starting Studio:

```bash
export ANTHROPIC_API_KEY=your-key
```

The **AI & RAG** panel in Studio shows every AI call your program made, with the
prompt and the response.

## 6. Getting help

- Built-in examples: **Templates** menu in Studio.
- Report a bug or confusing message: the feedback button (speech bubble) in the
  top-right of Studio. Tick "attach logs" so we can see what happened.
