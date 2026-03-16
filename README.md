# MCN — Macincode Scripting Language

A production-grade scripting language with first-class AI, database, API, and full-stack primitives. Write less, ship more — AI is a language primitive, not a library call.

## Why MCN?

MCN sits in the space Python occupies for data science — but built for the AI era. Every intelligent operation (`ai`, `classify`, `extract`) is a one-liner. Backend services, databases, and React UIs all compile from a single `.mcn` file. And the **MCN Agent** turns a sentence into a complete, runnable full-stack application.

```mcn
// Classify, extract, respond — three lines
var intent  = classify(message, ["buy", "refund", "support"])
var details = extract(message, OrderContract)
var reply   = ai("Draft a {intent} response for: {details.summary}")
log(reply)
```

---

## Quick Start

```bash
git clone https://github.com/zeroappz/mcn
cd mcn
pip install -e .
mcn run examples/hello.mcn
```

---

## MCN Agent — Generate Full-Stack Apps from Natural Language

The MCN Agent uses Claude to turn a plain-English description into a complete, runnable full-stack application — backend API, SQLite database, and a React + shadcn/ui frontend — in seconds.

### 1. Save your Claude API key (once)

```bash
mcn config set api_key sk-ant-...
```

That's it. The key is stored in `~/.mcn/config.json` and used automatically for all future `mcn generate` runs. No environment variables needed.

### 2. Generate an app

```bash
mcn generate "An expense tracker with title, amount, and category. Table with edit/delete. Bar chart of spending by category."
```

Output:
```
[MCN Agent] Generating MCN for: 'An expense tracker ...'

<backend>
contract Expense
    title: str
    amount: float
    category: str
...
</backend>

  ✓ MCN validated on attempt 1

[MCN Agent] Written:
  backend → ./backend/main.mcn
  ui      → ./ui/app.mcn

[MCN Agent] Next step:
  mcn build ./ui/app.mcn --out ./frontend
```

### 3. Build the React frontend

```bash
mcn build ./ui/app.mcn --out ./frontend
cd frontend && npm install && npm run dev
```

### Generate + build in one command

```bash
mcn generate "A CRM with contacts, notes, and pipeline dashboard" --out ./crm --build
```

### All `mcn generate` options

| Flag | Default | Description |
|---|---|---|
| `--out <dir>` | `.` | Output directory for `backend/` and `ui/` |
| `--port <N>` | `8080` | Backend server port |
| `--build` | off | Also compile the React frontend after writing |
| `--model <id>` | `claude-opus-4-6` | Claude model to use |
| `--api-key <key>` | config / env | Override API key for this run only |
| `--quiet / -q` | off | Suppress streaming output |

### Config commands

```bash
mcn config set api_key sk-ant-...   # save API key
mcn config get api_key              # check saved key (masked)
mcn config show                     # show all saved config
```

**Key resolution order:** `--api-key` flag → `~/.mcn/config.json` → `ANTHROPIC_API_KEY` env var.

---

## Full-Stack Compiler (`mcn build`)

MCN compiles component and app declarations directly to a React + TypeScript + shadcn/ui project.

### Backend — service, endpoints, AI

```mcn
contract Item
    name: str
    price: float
    status: str

query("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, status TEXT, created_at TEXT DEFAULT (datetime('now')))")

service items_api
    port 8080

    endpoint create_item(name, price, status)
        var category = classify(name, ["electronics", "clothing", "food", "other"])
        query("INSERT INTO items (name, price, status) VALUES (?, ?, ?)", (name, price, status))
        var id = query("SELECT last_insert_rowid() as id")[0].id
        return {success: true, id: id}

    endpoint list_items(limit = 50, offset = 0)
        var items = query("SELECT * FROM items ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        var insight = ai("Give a one-sentence business insight on these records: {items}")
        return {success: true, data: items, total: items, insight: insight}

    endpoint update_item(id, name, price, status)
        query("UPDATE items SET name = ?, price = ?, status = ? WHERE id = ?", (name, price, status, id))
        return {success: true}

    endpoint delete_item(id)
        query("DELETE FROM items WHERE id = ?", (id,))
        return {success: true}
```

### UI — components, CRUD, charts, modals

```mcn
component ItemTable
    state items           = []
    state insight         = ""
    state edit_name       = ""
    state edit_price      = 0
    state edit_status     = ""
    state edit_item       = null        // enables CRUD mode (Edit/Delete auto-injected)
    state show_edit_modal = false

    on load
        var response = list_items()
        items   = response.data
        insight = response.insight

    render
        card
            card_header "All Items"
            div
                text insight
            table
                table_header
                    table_row
                        table_head "id"
                        table_head "name"
                        table_head "price"
                        table_head "status"
                        table_head "created_at"
                table_body
        modal show=show_edit_modal
            card_header "Edit Item"
            form on_submit=handleSave
                input bind=edit_name label="Name"
                input bind=edit_price label="Price" type="number"
                button "Save Changes" variant="default"

app ItemManager
    title  "Item Manager"
    theme  "professional"
    layout
        tabs
            tab "Add Item"   ItemForm
            tab "All Items"  ItemTable
```

```bash
mcn build ui/app.mcn --out frontend
cd frontend && npm install && npm run dev
```

### Supported UI tags

| Category | Tags |
|---|---|
| Layout | `div`, `div grid_cols=N`, `card`, `card_header`, `card_content`, `card_footer` |
| Forms | `form`, `input`, `textarea`, `select`, `button` |
| Data | `table`, `table_header`, `table_row`, `table_head`, `table_body`, `badge`, `alert`, `separator`, `progress`, `skeleton` |
| Charts | `bar_chart`, `line_chart`, `pie_chart` (recharts) |
| KPI | `stat_card label="..." value=var unit="..."` |
| Navigation | `tabs`, `tabs_list`, `tab_trigger`, `tab_content`, `scroll_area` |
| Modal | `modal show=boolVar` |
| Conditional | `div show=boolVar`, `text show=boolVar` |
| Pagination | `pagination page=var total=var page_size=N` |

Themes: `"professional"` (blue) · `"modern"` (dark) · `"minimal"` (clean) · `"default"`

---

## Language Reference

### Variables & Types

```mcn
var name    = "Lenin"
var score   = 42
var active  = true
var nothing = null

// Bare reassignment (no var keyword)
score = score + 10
```

### String Interpolation & Multi-line Strings

```mcn
var lang = "MCN"
log("Hello from {lang}!")           // → Hello from MCN!

var prompt_text = """
You are a helpful assistant.
Language: {lang}
"""
```

### Operators

```mcn
// Arithmetic
var total = (price * qty) + tax

// Comparison
if score >= 90
    log("A grade")

// and / or return values (not booleans)
var user    = null
var display = user or "Anonymous"   // → "Anonymous"

// Null-safe access
var city = user?.address?.city      // → null if user or address is null
```

### Control Flow

```mcn
// if / else
if score >= 90
    log("A")
else
    log("B or lower")

// for / while with break and continue
for item in items
    if item == "skip"
        continue
    log(item)

// try / catch / throw
try
    var data = fetch("https://api.example.com/data")
catch
    throw "Fetch failed: {error}"
```

### Functions & Default Parameters

```mcn
function greet(name, greeting = "Hello")
    return "{greeting}, {name}!"

log(greet("Lenin"))           // → Hello, Lenin!
log(greet("World", "Hi"))    // → Hi, World!
```

### Collections

```mcn
var nums = [1, 2, 3, 4, 5]
var user = {name: "Lenin", role: "admin"}

log(nums[0])         // → 1
log(user.name)       // → Lenin

// Tuples (SQL parameter binding)
var rows = query("SELECT * FROM users WHERE id = ?", (user_id,))
```

---

## AI Primitives

```mcn
// Free-form generation
var summary = ai("Summarize: " + article)

// Structured extraction (validates against a contract)
var order = extract(raw_text, OrderContract)

// Zero-shot classification
var intent = classify(message, ["buy", "return", "support"])

// Explicit model routing
var haiku = llm("claude-haiku", "Quick answer: " + question)

// Embeddings
var vec = embed("semantic search query")

// Human-in-the-loop checkpoint
checkpoint("Review before sending", reply)
```

### Prompt Templates

```mcn
prompt support_reply
    system "You are a helpful customer support agent."
    user   "Customer said: {{message}}"
    format text

var reply = support_reply.run({message: customer_input})
```

### Agent Declarations

```mcn
agent researcher
    model  "claude-opus-4-6"
    tools  fetch, query, ai
    memory session

    task analyze(topic)
        var data     = fetch("https://api.example.com?q=" + topic)
        var findings = ai("Key insights from: " + data)
        return findings

var result = researcher.analyze("AI trends 2025")
```

---

## Domain Primitives

### Contracts (typed schemas)

```mcn
contract User
    id:    int
    name:  str
    email: str

var user = extract(raw_json, User)
log(user.email)
```

### Pipelines

```mcn
pipeline data_pipeline
    stage extract
        var raw = query("SELECT * FROM events")
        return raw

    stage transform(data)
        var clean = ai("Normalize this JSON: " + data)
        return clean

    stage load(data)
        query("INSERT INTO clean_events VALUES ?", data)
```

### Services (HTTP APIs)

```mcn
service user_api
    port 8080

    endpoint get_user(id)
        var user = query("SELECT * FROM users WHERE id = ?", (id,))
        return user

    endpoint create_user(name, email)
        query("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        return {success: true}
```

### Workflows

```mcn
workflow order_processing
    step validate(order_id)
        var order = query("SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order
            throw "Order not found: {order_id}"
        return order

    step charge(order)
        var result = trigger("https://payments.api/charge", order)
        return result

    step notify(order, result)
        ai("Send confirmation email for order {order.id}")
```

---

## Built-in Functions

| Function | Description |
|---|---|
| `log(msg)` | Print to console |
| `fetch(url)` | HTTP GET |
| `trigger(url, data)` | HTTP POST |
| `query(sql, params?)` | Database query (SQLite) |
| `ai(prompt)` | AI text generation |
| `llm(model, prompt)` | AI with explicit model |
| `embed(text)` | Vector embedding |
| `extract(text, schema)` | Structured extraction |
| `classify(text, labels)` | Zero-shot classification |
| `checkpoint(msg, data?)` | Human-in-the-loop |
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write file |
| `env(key)` | Read environment variable |

---

## CLI Commands

```bash
# ── AI App Generation ───────────────────────────────────────────────────
mcn config set api_key sk-ant-...              # save Claude API key (once)
mcn generate "A todo app with priorities"      # generate full-stack app
mcn generate "..." --out ./myapp --build       # also compile React frontend
mcn generate "..." --api-key sk-ant-...        # one-off key override

# ── Compiler ────────────────────────────────────────────────────────────
mcn build ui/app.mcn --out frontend           # compile MCN UI → React project

# ── Runtime ─────────────────────────────────────────────────────────────
mcn run script.mcn                             # run a script
mcn repl                                       # interactive REPL

# ── Quality ─────────────────────────────────────────────────────────────
mcn test script.mcn                            # run test blocks
mcn test tests/ --verbose                      # all .mcn files in directory
mcn check script.mcn                           # static type check
mcn check --strict script.mcn                 # warnings as errors
mcn fmt script.mcn                             # print formatted output
mcn fmt --write src/                           # rewrite files in place
mcn fmt --check src/                           # CI mode (exit 1 if unformatted)

# ── Server ──────────────────────────────────────────────────────────────
mcn serve --file script.mcn --port 8080
mcn serve --dir endpoints/ --port 8080

# ── Project ─────────────────────────────────────────────────────────────
mcn init my-app
mcn validate
```

---

## Testing

```mcn
function add(a, b)
    return a + b

test "addition works"
    assert add(2, 3) == 5

test "null-safe operator"
    var obj = null
    assert obj?.name == null
```

```bash
mcn test examples/tests.mcn
#   ✓ addition works  (0.1 ms)
#   ✓ null-safe operator  (0.0 ms)
#   All 2 test(s) passed.
```

---

## Project Structure

```
mcn/
├── core_engine/        # Lexer, parser, evaluator, type checker, CLI, UI compiler
│   ├── lexer.py
│   ├── parser.py
│   ├── evaluator.py
│   ├── ast_nodes.py
│   ├── ui_compiler.py  # MCN → React + shadcn/ui
│   ├── type_checker.py
│   ├── formatter.py
│   ├── test_runner.py
│   └── mcn_cli.py
├── ai/                 # MCN Agent (Claude-powered app generator)
│   ├── mcn_agent.py    # MCNAgent class
│   └── mcn_spec.py     # MCN language spec (system prompt)
├── fullstack/          # Template-based fullstack generator
├── providers/          # AI provider adapters
├── web-playground/     # Browser-based IDE
└── plugin/             # Embed MCN in Python apps
examples/               # Ready-to-run .mcn scripts
use-cases/              # Real-world scenario scripts
```

---

## Embedding MCN in Python

```python
from mcn.plugin.mcn_embedded import MCNEmbedded

mcn = MCNEmbedded()
result = mcn.execute("""
    var total = price * qty
    return total
""", context={"price": 9.99, "qty": 3})

print(result)   # 29.97
```

### Programmatic agent usage

```python
from mcn.ai.mcn_agent import MCNAgent

agent = MCNAgent(api_key="sk-ant-...")
result = agent.generate(
    "A leave request tracker with approval workflow",
    output_dir="./leave_app",
    port=8080,
)
print(result["backend_path"])   # ./leave_app/backend/main.mcn
print(result["ui_path"])        # ./leave_app/ui/app.mcn
print(result["attempts"])       # 1  (self-corrected 0 times)
```

---

## Roadmap

| Version | Focus |
|---|---|
| v2.1 | AI primitives, test runner, formatter, type checker |
| v2.2 (current) | MCN Agent, full-stack compiler (CRUD, charts, modals, routing) |
| v2.3 | More shadcn components (checkbox, switch, combobox, date picker), form validation, toast notifications |
| v3.0 | LSP server, WASM runtime, multi-target code generation |

---

## Contributing

1. Fork the repository
2. Write your feature — cover it with `test` blocks in the `.mcn` file itself
3. Run `mcn test` and `mcn check --strict` before submitting
4. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE).

---

*MCN v2.2 — describe it, ship it.*
