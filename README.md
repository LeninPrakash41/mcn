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

## Quick Start

```bash
git clone https://github.com/zeroappz/mcn
cd mt-mcn
pip install -e .
mcn run examples/hello.mcn
```

Or open the web playground:

```bash
cd mcn/web-playground
python server.py
# → http://localhost:7842
```

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

---

## Services (HTTP APIs)

Endpoints starting with `get_`, `list_`, `fetch_`, `find_` are served on **GET** (query string → args). All endpoints also accept **POST** with a JSON body. Path parameters (`/get_user/42`) are mapped to the first positional arg.

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
mcn serve --file backend/main.mcn --port 8080

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

---

## CLI Reference

```bash
# ── Script execution ─────────────────────────────────────────────────────
mcn run script.mcn
mcn repl

# ── Full-stack ───────────────────────────────────────────────────────────
mcn generate "An invoice app with PDF export"  # AI-generated app
mcn generate "..." --out ./myapp --build       # generate + compile
mcn build ui/app.mcn --out frontend           # compile MCN UI → React

# ── Server ───────────────────────────────────────────────────────────────
mcn serve --file backend/main.mcn --port 8080
mcn serve --dir endpoints/ --port 8080

# ── Quality ──────────────────────────────────────────────────────────────
mcn test script.mcn                    # run test blocks
mcn test tests/ --verbose              # all .mcn files in directory
mcn check script.mcn                   # static type check
mcn check --strict script.mcn          # warnings as errors
mcn fmt script.mcn                     # format and print
mcn fmt --write src/                   # rewrite in place
mcn fmt --check src/                   # CI check (exit 1 if dirty)

# ── Package management ───────────────────────────────────────────────────
mcn packages list                      # all available packages
mcn packages info healthcare           # exports + docs
mcn install stripe                     # verify bundled package
mcn install --path ./my_pkg            # install from local directory
mcn packages remove myorg/old          # uninstall
mcn new-package myorg/retail --path .  # scaffold a new SI package

# ── Config ───────────────────────────────────────────────────────────────
mcn config set api_key sk-ant-...
mcn config get api_key
mcn config show

# ── Project ──────────────────────────────────────────────────────────────
mcn init my-app
mcn validate
```

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
mt-mcn/
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
│   ├── web-playground/         # Browser-based IDE (Monaco + Python server)
│   └── plugin/                 # Embed MCN in Python apps
├── examples/                   # Ready-to-run .mcn scripts
└── use-cases/                  # Real-world scenario scripts
```

---

## Roadmap

| Version | Status | Focus |
|---|---|---|
| v2.0 | Released | Pipelines, services, workflows, contracts, AI primitives |
| v2.1 | Released | Test runner, formatter, type checker, MCN Agent |
| v2.2 | Released | Full-stack compiler, CRUD, charts, modals, routing |
| **v2.3** | **Current** | **100+ stdlib built-ins, package system (stripe/twilio/healthcare/finance), else-if, ternary, compound assign, property/index assign, rich test assertions, GET endpoints + path params** |
| v2.4 | Planned | `try/catch` error variable, `finally`, arrow functions, `for i, val in list`, type annotations |
| v3.0 | Planned | Cloud runtime (1-click deploy), VS Code extension, public package registry, local LLM (Ollama) |

---

## Contributing

1. Fork the repository
2. Write your feature — cover it with `test` blocks in the `.mcn` file itself
3. Run `mcn test` and `mcn check --strict` before submitting
4. Open a pull request

**Areas actively needed:**
- Cloud runtime / deploy button
- VS Code extension with MCN syntax highlighting + IntelliSense
- Public package registry (npm-style, for SI packages)
- More domain packages (`payments`, `logistics`, `hr`, `legal`)

---

## License

MIT — see [LICENSE](LICENSE).

---

*MCN v2.3 — write less, ship more. AI is a primitive, not a library.*
