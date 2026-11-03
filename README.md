# MCN — Macincode Scripting Language

A full-stack scripting language built for the AI era. Write backend services, data pipelines, AI workflows, and React UIs — all in a single `.mcn` file. AI is a language primitive, not a library call.

```mcn
use "healthcare"

var patient = {id: "P001", name: "John Doe"}
var admission = admit_patient(patient)

var risk = ai("Assess risk for: " + to_json(patient))
var token = auth_create_token({user: "nurse_01", role: "staff"})

log("Admitted {admission.patient_id} — risk: {risk}")
```

---

## Why MCN?

| Problem | MCN's answer |
|---|---|
| AI requires 50 lines of SDK boilerplate | `ai(prompt)` is a single expression |
| Full-stack apps need 3 separate codebases | One `.mcn` file generates backend + React UI |
| SIs re-implement domain logic for every client | Package it once: `use "accenture/healthcare"` |
| Bolt.new / v0 generate code you still have to maintain | MCN is the runtime — no generated mess |
| Non-technical builders can't use code-gen output | MCN reads like English, executes like a program |

---

## Internal Low/No-Code Platform

MCN is designed to act as an **Internal Low/No-Code Platform** engine (ideal for ecosystems like ClopsAI). It replaces the need to write traditional React + Node.js boilerplates when building internal tools, admin panels, or CRM dashboards.

### The Architecture: No Backend Boilerplate

Unlike other app builders that generate separate frontend and backend codebases, **MCN itself acts as the backend server.**

1. **Write the backend (`backend/main.mcn`):** tables, a `service` with `endpoint`s, AI calls and `test` blocks.
2. **Write the UI (`ui/app.mcn`):** `component`s with `state`, `on submit` / `on load` handlers and a `render` tree, plus an `app` layout. `mcn build ui/app.mcn` compiles it to a React + Tailwind + shadcn/ui project whose API client calls your endpoints; Studio also renders it as a Flutter app.
3. **Run the backend:** `mcn serve backend/main.mcn` starts an HTTP API (GET and POST for every endpoint, interactive docs at `/docs`).

### Why this works:
- **Zero API Boilerplate:** You never have to write REST APIs. The React frontend is automatically wired to execute the Python-based MCN functions via HTTP/WebSockets.
- **Generate from a description:** `mcn generate "A leave tracker with manager approval"` writes the backend and UI with Claude, then validates them.
- **Secure Integration:** Database credentials and API keys stay firmly on the MCN backend server, never touching the React View layer.

---

## Quick Start

Requires **Python 3.10+**. Node.js is only needed to run the generated React app.

```bash
pip install mcn-lang              # from a clone: pip install -e .
mcn init my-app                   # a working full-stack app: backend, tests, UI
cd my-app
mcn test backend/main.mcn         # run its tests
mcn studio .                      # open it in MCN Studio → http://localhost:5003
```

From a clone of this repository, use `pip install -e .` instead (inside a virtual environment):

```bash
git clone https://github.com/LeninPrakash41/mcn
cd mcn
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

**MCN Studio** is a browser IDE: edit, **Run** the backend, **Preview** the web app, switch to **App** for the mobile (Flutter) version, and inspect the database, IoT devices and AI calls. `mcn studio` with no folder opens Studio's own workspace, where the **Templates** menu has 18 starter apps. Studio only accepts connections from your own machine.

**Editor support.** `mcn vscode` installs the bundled VS Code extension: highlighting, completions, hover docs, errors underlined as you type, and commands to run, test, serve and open Studio.

**Errors** show the line, a caret and a hint:

```
Name error on line 2, column 5: Undefined variable 'totl'
   2 | log(totl)
     |     ^^^^
Hint: Did you mean 'total'?
```

`mcn check file.mcn` finds the same errors without running the code (`--json` for editors and CI). Set `MCN_VERBOSE=1` to see engine debug logs; MCN's own logs go to `~/.mcn/logs`.

**Mobile app (Flutter, optional).** With the backend running (press **Run** in the playground), start the generated app and point it at the backend:

```bash
cd mcn/web-playground/workspace/mobile
flutter create --platforms=web .        # first time only
flutter run -d chrome --dart-define=MCN_API_URL=http://localhost:8080
```

On an Android emulator use `--dart-define=MCN_API_URL=http://10.0.2.2:8080`. Without a running backend the app shows demo data.

**AI features.** Set `ANTHROPIC_API_KEY` to enable `ai()` calls and the Copilot. MCN uses `claude-opus-5-5` by default; override with `MCN_AI_MODEL` (for `ai()`) or `MCN_CLAUDE_MODEL` (for Copilot).

The Web Playground includes built-in **Interactive Simulators** in the preview pane:
* **DB Explorer**: Inspect database tables, explore generated schemas, and write SQL queries against the live SQLite instance.
* **IoT Simulator**: Slide sensor values (temperature, humidity) or toggle motion triggers to override inputs and test automation handlers.
* **AI & RAG Inspector**: Trace prompt execution pipelines, vector databases search operations, and retrieval matches in real time.

---

## Language at a Glance

### Variables, operators, control flow

```mcn
var score = 85
var grade = score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : "F"

// Compound assignment
var total = 0
total += score
total *= 1.1

// else if chains
if grade == "A"
    log("Excellent")
else if grade == "B"
    log("Good")
else
    log("Keep going")

// Modulo
var is_even = score % 2 == 0 ? "even" : "odd"
```

### Mutable objects and arrays

```mcn
var user = {name: "Alice", role: "viewer", score: 0}
user.role  = "admin"          // property assignment
user.score += 10              // compound on property (via temp var)

var items = ["a", "b", "c"]
items[1] = "B"                // index assignment

// String interpolation — simple vars and dotted paths
log("User: {user.name}, role: {user.role}")
log("Items count: {items.length}")
```

### Functions, recursion, defaults

```mcn
function greet(name, greeting = "Hello")
    return "{greeting}, {name}!"

function factorial(n)
    return n <= 1 ? 1 : n * factorial(n - 1)

log(greet("Lenin"))           // Hello, Lenin!
log(factorial(6))             // 720
```

### Try / catch

```mcn
try
    var data = fetch("https://api.example.com/data")
    log("Got {data.count} records")
catch
    log("Request failed — using cached data")
    var data = cache_get("last_response")
```

---

## AI Primitives

```mcn
// Free-form generation
var summary = ai("Summarize in 3 bullets: " + article)

// Explicit model routing
var fast   = llm("claude-haiku-4-5", "Quick answer: " + question)
var deep   = llm("claude-opus-4-6",  "Detailed analysis: " + question)

// Zero-shot classification
var intent = classify(message, ["buy", "refund", "support"])

// Structured extraction (validated against a contract)
contract Order
    id:     int
    amount: float
    item:   str

var order = extract(raw_text, Order)
log("Order #{order.id} — {order.item} at ${order.amount}")

// Embeddings
var vec = embed("semantic search query")

// Prompt templates
prompt support_reply
    system "You are a helpful customer support agent."
    user   "Customer said: {{message}}"
    format text

var reply = support_reply.run({message: customer_input})

// Human-in-the-loop
checkpoint("Review before sending", reply)
```

### RAG — Retrieval-Augmented Generation

```mcn
// Index your documents
vector_upsert("doc1", "MCN supports pipelines, services, and agents")
vector_upsert("doc2", "Use `use \"stripe\"` to process payments")
vector_upsert("doc3", "The `rag()` function retrieves then answers")

// Ask a question — retrieve + answer in one call
var answer = rag("How do I process a payment in MCN?")
log(answer)
```

### AI Model Management (v3.0)

```mcn
use "ai_v3"

// Register and manage multiple AI models
register("my-gpt4", "openai", {"temperature": 0.7})
set_model("my-gpt4")

// Fine-tune models on your data
train("gpt-3.5-turbo", "sales_data.csv", "sales-predictor")

// Use different models for different tasks
var summary = run("my-gpt4", "Summarize quarterly report")
var prediction = run("sales-predictor", "Predict next quarter")
```

### Natural Language Programming (v3.0)

```mcn
use "natural"

// Write code in plain English
var code1 = translate("create a variable name with value John")
// Result: var name = "John"

var code2 = translate("if age greater than 18 then print adult")
// Result: if age > 18 { echo("adult") }

// Execute natural language directly
translate("send welcome email to new users", true)
```

---

## Standard Library (100+ built-ins)

No `use` statement needed — available in every script.

### Session & Cache

```mcn
session_set("user_id", "u_42")
var uid = session_get("user_id")

cache_set("exchange_rate", 1.08, 3600)   // TTL: 1 hour
var rate = cache_get("exchange_rate")
```

### Agent Memory

```mcn
var mid = memory_store("Customer prefers email over phone", {category: "prefs"})
var hits = memory_search("contact preference", 5)
log("Found {hits.length} relevant memories")
```

### Auth

```mcn
var hashed = auth_hash("mysecret123")
var ok     = auth_verify_hash("mysecret123", hashed)   // true

var token   = auth_create_token({user_id: "u_42", role: "admin"}, "my-secret")
var payload = auth_verify_token(token, "my-secret")
log("Token user: {payload.user_id}")
```

### Data & Strings

```mcn
var rows    = parse_csv("name,score\nAlice,90\nBob,85")
var js      = to_json({name: "test", value: 42})
var words   = split("hello world mcn", " ")
var joined  = join(words, "-")                 // "hello-world-mcn"
var upped   = upper("mcn lang")               // "MCN LANG"
var matches = regex_extract("user@example.com", "[a-z]+@[a-z]+\.[a-z]+")
```

### Arrays & Math

```mcn
var scores = [90, 85, 92, 78, 95]
var avg    = average(scores)              // 88.0
var top    = sort_list(scores, "", true)  // descending
var groups = group_by(users, "department")
var uniq   = unique([1, 2, 2, 3, 3, 3])  // [1, 2, 3]

log("Max: {max_val(scores)}, Min: {min_val(scores)}")
var roll = random_int(1, 6)
```

### Queue & Crypto

```mcn
queue_push("jobs", {task: "send_email", to: "user@example.com"})
var job = queue_pop("jobs")
log("Processing: {job.task}")

var id   = uuid()
var hash = sha256("hello mcn")
```

---

## Package System

MCN has a built-in package registry. Bundled packages work out of the box; custom packages install from local directories.

### Bundled packages

```bash
mcn packages list
# stripe, twilio, resend, slack, openai, healthcare, finance
```

```mcn
use "stripe"
var payment = charge(299.99, "usd", "Premium subscription")
log("Payment: {payment.id}")

use "twilio"
send_sms("+14155551234", "Your OTP is 847293")

use "resend"
send_email("user@example.com", "Welcome to MCN", "Thanks for signing up!")

use "slack"
post_message("#alerts", "Deploy complete — v2.3 is live")
```

### Vertical domain packages (SI ecosystem)

```mcn
use "healthcare"

var admission = admit_patient({id: "P001", name: "John", ward: "cardiology"})
var appt      = schedule_appointment("P001", "echocardiogram", "high")
var drugs     = check_drug_interactions(["warfarin", "aspirin"])
var audit     = hipaa_audit_log("READ", "nurse_01", "P001", "vitals")
```

```mcn
use "finance"

var kyc    = kyc_check({name: "Alice Smith", country: "US"})
var aml    = aml_screen({amount: 75000, currency: "USD"})
var credit = calculate_credit_score({annual_income: 95000, total_debt: 12000})
log("Credit: {credit.score} (grade {credit.grade})")
```

### Author and publish your own package

```bash
# Scaffold a new package
mcn new-package accenture/crm --path . --description "CRM workflows"

# Edit index.py with your domain logic, then install
mcn install --path ./accenture_crm --name accenture/crm

# Use it
# use "accenture/crm"
```

**Package authoring** — `index.py`:

```python
def onboard_customer(data: dict) -> dict:
    """Validate, enrich, and register a new customer."""
    return {"customer_id": "c_" + data["email"][:6], "status": "active"}

MCN_EXPORTS = [onboard_customer]
```

Or write pure MCN in `index.mcn`:

```mcn
function onboard_customer(data)
    var id = "c_" + data.email
    return {customer_id: id, status: "active"}
```

CLI reference:

```bash
mcn install stripe                         # confirm bundled package
mcn install --path ./my_pkg               # install from local path
mcn packages list                         # all installed + bundled
mcn packages info healthcare              # show exports + docs
mcn packages remove myorg/old-pkg         # uninstall
mcn new-package myorg/retail --path .     # scaffold new package
```

---

## Pipelines

```mcn
pipeline etl
    stage extract
        var records = parse_csv(read_file("data/leads.csv"))
        log("Extracted {records.length} records")
        return records

    stage transform(data)
        var total = 0
        for r in data
            total = total + r.score
        var avg = total / data.length
        log("Average score: {avg}")
        return {count: data.length, average: avg}

    stage load(report)
        query("INSERT INTO reports (count, average) VALUES (?, ?)",
              (report.count, report.average))
        log("Pipeline complete — {report.count} records, avg {report.average}")

etl.run()
```

### AI-Powered Data Pipelines (v3.0)

MCN allows creating intelligent pipelines where stages can invoke AI tasks, clean data dynamically, and route results seamlessly.

```mcn
use "pipeline"

// Create intelligent pipeline
pipeline("create", "feedback_processor", [
    {"type": "clean", "params": {"remove_special_chars": true}},
    {"type": "ai_classify", "params": {"categories": ["positive", "negative"]}},
    {"type": "ai_extract", "params": {"type": "entities"}}
])

// Process data
var result = pipeline("run", "feedback_processor", "Great product! Love it!")
log("Pipeline processed: {result.status}")
```

---

## Services (HTTP APIs)

Every endpoint accepts **POST** with a JSON body and **GET** with a query string (`/list_users?limit=10`, numbers converted). A path segment fills the first parameter (`/get_user/42`). `GET /` lists the endpoints; with FastAPI installed, `/docs` is interactive API documentation.

```mcn
service users_api
    port 8080

    endpoint get_user(id)
        var user = query("SELECT * FROM users WHERE id = ?", (id,))
        return user[0] or {error: "not found"}

    endpoint list_users(limit = 50, offset = 0)
        return query("SELECT * FROM users LIMIT ? OFFSET ?", (limit, offset))

    endpoint create_user(name, email)
        query("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        return {success: true, id: query("SELECT last_insert_rowid() as id")[0].id}

    endpoint delete_user(id)
        query("DELETE FROM users WHERE id = ?", (id,))
        return {success: true}
```

```bash
mcn serve backend/main.mcn       # port comes from the service's `port` line (default 8080)

# GET /list_users?limit=10
# GET /get_user/42
# POST /create_user  {"name": "Alice", "email": "alice@example.com"}
```

---

## Full-Stack Compiler (`mcn build`)

```mcn
component Dashboard
    state deals     = []
    state revenue   = 0

    on load
        var data  = fetch("/api/dashboard")
        deals   = data.deals
        revenue = data.revenue

    render
        div grid_cols=4
            stat_card label="Total Deals"   value=deals.length color="blue"   icon="TrendingUp"
            stat_card label="Revenue"       value=revenue      color="green"  icon="DollarSign" unit="$"
        card
            card_header "Recent Deals"
            table
                table_header
                    table_row
                        table_head "Name"
                        table_head "Stage"
                        table_head "Value"
                table_body

app CRM
    title "CRM Dashboard"
    theme "professional"
    layout
        sidebar
            nav "Dashboard"  Dashboard
            nav "Contacts"   ContactList
            nav "Reports"    Reports
```

```bash
mcn build ui/app.mcn --out frontend
cd frontend && npm install && npm run dev
```

**Supported UI elements:**

| Category | Elements |
|---|---|
| Layout | `div`, `div grid_cols=N`, `card`, `card_header`, `card_content`, `card_footer` |
| Forms | `form`, `input`, `textarea`, `select`, `button`, `checkbox`, `switch`, `radio` |
| Data display | `table`, `badge`, `alert`, `separator`, `progress`, `skeleton`, `avatar` |
| Charts | `bar_chart`, `line_chart`, `pie_chart` (via Recharts) |
| KPI | `stat_card label="..." value=var color="blue" icon="TrendingUp" trend=5` |
| Navigation | `tabs`, `tab`, `sidebar`, `nav`, `scroll_area` |
| Overlays | `modal show=boolVar`, `sheet`, `dropdown_menu`, `tooltip` |
| Misc | `accordion`, `pagination page=var total=var page_size=N` |

Themes: `"professional"` · `"modern"` · `"minimal"` · `"default"`

---

## AI App Generator (`mcn generate`)

```bash
mcn config set api_key sk-ant-...

mcn generate "A CRM with contacts, notes, and pipeline dashboard"
# Streams MCN code, validates it, writes backend/ and ui/ dirs

mcn generate "..." --out ./my-app --build
# Also compiles the React frontend
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--out <dir>` | `.` | Output directory |
| `--build` | off | Also compile React frontend |
| `--model <id>` | `claude-opus-4-6` | Claude model |
| `--api-key <key>` | config / env | Override for this run |
| `--quiet` | off | Suppress streaming |

---

## Testing

MCN has a built-in test framework with 15+ assertion helpers.

```mcn
function divide(a, b)
    if b == 0
        throw "Division by zero"
    return a / b

test "basic arithmetic"
    assert_equal(divide(10, 2), 5.0)
    assert_equal(10 % 3, 1)

test "ternary and else-if"
    var x = 75
    var grade = x >= 90 ? "A" : x >= 80 ? "B" : x >= 70 ? "C" : "F"
    assert_equal(grade, "C")

test "collections"
    var items = [1, 2, 3, 4, 5]
    assert_len(items, 5)
    assert_contains(items, 3)
    assert_gt(max_val(items), 4)

test "auth tokens"
    var token   = auth_create_token({user: "alice"}, "secret")
    var payload = auth_verify_token(token, "secret")
    assert_not_null(payload)
    assert_equal(payload.user, "alice")

test "null safety"
    var obj = null
    assert_null(obj?.name)
    assert_truthy("hello" or "fallback")
```

**Assertion helpers:**

`assert_equal` · `assert_not_equal` · `assert_null` · `assert_not_null` · `assert_truthy` · `assert_falsy` · `assert_contains` · `assert_not_contains` · `assert_gt` · `assert_gte` · `assert_lt` · `assert_lte` · `assert_type` · `assert_len` · `assert_throws`

```bash
mcn test script.mcn
mcn test tests/ --verbose
```

---

## Workflows & Agents

### Workflow (step-by-step with history and replay)

```mcn
workflow order_processing
    step validate(order_id)
        var order = query("SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order
            throw "Order not found: {order_id}"
        return order[0]

    step charge(order)
        use "stripe"
        return charge(order.amount, "usd", "Order #{order.id}")

    step notify(order, payment)
        use "resend"
        send_email(order.email, "Order confirmed", "Payment {payment.id} received")
        return {order_id: order.id, status: "complete"}
```

### Agent

```mcn
agent researcher
    model  "claude-opus-4-6"
    tools  fetch, query, ai
    memory session

    task analyze(topic)
        var docs    = fetch("https://api.example.com?q=" + topic)
        var summary = ai("Key insights from: " + to_json(docs))
        memory_store(summary, {topic: topic})
        return summary

var result = researcher.analyze("MCN competitive landscape")
```

## IoT & Edge Computing (v3.0)

MCN provides first-class support for registering and communicating with IoT devices and edge nodes directly from your scripting environment.

```mcn
use "iot"

// Connect and configure devices
device("register", "temp_sensor", {"type": "temperature_sensor"})
device("register", "smart_light", {"type": "smart_light"})

// Read state and send commands
var temp = device("read", "temp_sensor")
if temp > 25 {
    device("command", "smart_light", {"action": "turn_on"})
}
```

## Event-Driven Programming (v3.0)

Build reactive applications by registering asynchronous event listeners and triggering events dynamically.

```mcn
use "events"

// Register event handler
on event "high_temp" handle_alert

function handle_alert(data) {
    log("ALERT: Temperature reached {data.temp}")
}

// Trigger event execution
trigger("high_temp", {temp: 28})
```

---

## CLI Reference

```bash
# ── Projects ─────────────────────────────────────────────────────────────
mcn init my-app                        # new full-stack project (backend, tests, UI)
mcn studio [folder]                    # browser IDE (default port 5003)
mcn validate [--path .]                # check every .mcn file in a project
mcn vscode                             # install the VS Code extension

# ── Running ──────────────────────────────────────────────────────────────
mcn run script.mcn
mcn repl
mcn serve backend/main.mcn             # HTTP API; --port N, --postman to export a collection
mcn serve endpoints/                   # every .mcn file in a folder

# ── Quality ──────────────────────────────────────────────────────────────
mcn test script.mcn                    # run test blocks
mcn test tests/ --verbose              # all .mcn files in directory
mcn check script.mcn                   # syntax, undefined names, types — without running
mcn check --json script.mcn            # machine-readable, for editors and CI
mcn check --strict script.mcn          # warnings as errors
mcn fmt script.mcn                     # format and print
mcn fmt --write src/                   # rewrite in place
mcn fmt --check src/                   # CI check (exit 1 if dirty)

# ── Full-stack ───────────────────────────────────────────────────────────
mcn build ui/app.mcn --out frontend    # compile MCN UI → React
mcn generate "An invoice app with PDF export"  # AI-generated app (needs ANTHROPIC_API_KEY)
mcn generate "..." --out ./myapp --build       # generate + compile

# ── Packages ─────────────────────────────────────────────────────────────
mcn packages list                      # all available packages
mcn packages info healthcare           # exports + docs
mcn install stripe                     # verify bundled package
mcn install --path ./my_pkg            # install from local directory
mcn packages remove myorg/old          # uninstall
mcn new-package myorg/retail --path .  # scaffold a new SI package

# ── Config ───────────────────────────────────────────────────────────────
mcn config set api_key sk-ant-...
mcn config show
```

| Environment variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Enables `ai()`, `classify()`, `extract()`, `mcn generate` and the Copilot (mock replies without it) |
| `MCN_AI_MODEL`, `MCN_CLAUDE_MODEL` | Override the model (default `claude-opus-5-5`) |
| `MCN_HOME` | Where MCN keeps logs, packages and Studio's workspace (default `~/.mcn`) |
| `MCN_HTTP_TIMEOUT` | Seconds before `trigger()` gives up (default 5s to connect, 30s to respond) |
| `MCN_VERBOSE` | Print engine debug logs |

---

## Embedding MCN in Python

```python
from mcn.plugin.mcn_embedded import MCNEmbedded

mcn = MCNEmbedded()
result = mcn.execute("""
    var total = price * qty
    var tax   = total * 0.1
    return {total: total, tax: tax, grand: total + tax}
""", context={"price": 9.99, "qty": 3})

print(result)   # {"total": 29.97, "tax": 2.997, "grand": 32.967}
```

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
```

---

## Project Structure

```
mcn/
├── mcn/
│   ├── core_engine/
│   │   ├── lexer.py            # Tokeniser
│   │   ├── parser.py           # Recursive-descent parser
│   │   ├── evaluator.py        # Tree-walking evaluator
│   │   ├── ast_nodes.py        # AST node dataclasses
│   │   ├── stdlib_builtins.py  # 100+ built-in functions
│   │   ├── ai_builtins.py      # AI primitives (ai, llm, embed, extract, classify)
│   │   ├── mcn_packages.py     # Package registry (stripe, healthcare, finance, ...)
│   │   ├── ui_compiler.py      # MCN → React + shadcn/ui
│   │   ├── type_checker.py     # Static type checker
│   │   ├── diagnostics.py      # Error reports (line, caret, hint) and `mcn check`
│   │   ├── name_check.py       # Undefined-name detection
│   │   ├── project_init.py     # `mcn init` / `mcn validate`
│   │   ├── formatter.py        # Code formatter
│   │   ├── test_runner.py      # Test framework + 15 assertion helpers
│   │   ├── mcn_server.py       # HTTP server (GET/POST, path params, query strings)
│   │   └── mcn_cli.py          # CLI entry point
│   ├── ai/
│   │   ├── mcn_agent.py        # AI-powered app generator
│   │   └── mcn_spec.py         # Language spec (system prompt)
│   ├── providers/
│   │   ├── anthropic_provider.py
│   │   └── openai_provider.py
│   ├── web-playground/         # MCN Studio: server.py, playground_server/ blueprints, static/, templates
│   ├── studio/vscode-mcn/      # VS Code extension + language server (TypeScript)
│   ├── fullstack/              # Flutter project generator
│   └── plugin/                 # Embed MCN in Python apps
├── examples/                   # Ready-to-run .mcn scripts (each one is run in CI)
├── use-cases/                  # Real-world scenario scripts
├── docs/                       # Guides, language spec, student pilot kit
└── tests/                      # pytest suite
```

---

## Packaging & Distribution

To package and deploy MCN across enterprise clusters and edge environments:

### 1. Python Wheel & Source Build
Compile MCN into a universal wheel distribution:
```bash
pip install build && python3 -m build
```
This produces a wheel and source archive in `dist/` that can be pushed to a private PyPI registry (e.g., AWS CodeArtifact, JFrog Artifactory) and installed via:
```bash
pip install mcn-lang --extra-index-url https://registry.company.com/simple
```

### 2. Docker Container Deployment
Run MCN as a containerized microservice:
```bash
docker-compose up -d --build
```
This spins up the production API execution server and playground in an isolated, lightweight container.

---

## Roadmap

| Version | Status | Focus |
|---|---|---|
| v2.0–2.3 | Released | Pipelines, services, workflows, AI primitives, test runner, formatter, full-stack compiler, 100+ built-ins, packages |
| **v2.4** | **Current** | Friendly errors and `mcn check` (syntax + undefined names), `mcn init` full-stack projects, `mcn studio <folder>`, working VS Code extension with live errors, GET for every endpoint, parallel `task`/`await`, every example run in CI |
| v2.5 | Planned | Error on null property access (opt-in strict mode), arrow functions with statement bodies, public package registry |
| v3.0 | Planned | Hosted Studio, 1-click deploy, local LLM (Ollama) |

---

## Contributing

1. Fork the repository
2. Write your feature — cover it with `test` blocks in the `.mcn` file itself
3. Run `mcn test`, `mcn check --strict` and `python -m pytest` before submitting
4. Open a pull request

To work on the VS Code extension: `cd mcn/studio/vscode-mcn && npm install && npm run compile`, then `npx vsce package` to rebuild the `.vsix` that `mcn vscode` installs.

**Areas actively needed:**
- Cloud runtime / deploy button
- Rewriting the scripts in `examples/legacy/` for current MCN
- Public package registry (npm-style, for SI packages)
- More domain packages (`payments`, `logistics`, `hr`, `legal`)



---

## License

MIT — see [LICENSE](LICENSE).

---

*MCN v2.4 — write less, ship more. AI is a primitive, not a library.*
