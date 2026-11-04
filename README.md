# MCN — Macincode Scripting Language

A full-stack scripting language built for the AI era. Write the backend, web and mobile UI, AI agents and the devices your app controls in `.mcn` files, then put it online with one command. AI is a language primitive, not a library call.

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
| Agents need tool-calling plumbing | `agent_run(prompt, {tools: ["lookup_order"]})` lets Claude call your MCN functions |
| Web and mobile apps are two codebases | One `ui/app.mcn` compiles to React and to Flutter |
| IoT prototypes get rewritten for real hardware | The same `device()` code is simulated in Studio and drives a Raspberry Pi, Arduino or ESP32 |
| Security gets bolted on late | `auth "token"`, rate limits and security headers are built in; `mcn audit` checks your code |
| Deploying a full-stack app takes a day | `mcn deploy --target vercel` puts the web app and its API online at one URL |

---

## Internal Low/No-Code Platform

MCN is designed to act as an **Internal Low/No-Code Platform** engine (ideal for ecosystems like ClopsAI). It replaces the need to write traditional React + Node.js boilerplates when building internal tools, admin panels, or CRM dashboards.

### The Architecture: No Backend Boilerplate

Unlike other app builders that generate separate frontend and backend codebases, **MCN itself acts as the backend server.**

1. **Write the backend (`backend/main.mcn`):** tables, a `service` with `endpoint`s, AI calls and `test` blocks.
2. **Write the UI (`ui/app.mcn`):** `component`s with `state`, `on submit` / `on load` handlers and a `render` tree, plus an `app` layout. `mcn build ui/app.mcn` compiles it to a React + Tailwind project whose API client calls your endpoints, and Studio compiles the same file to a Flutter app.
3. **Run the backend:** `mcn serve backend/main.mcn` starts an HTTP API (GET and POST for every endpoint, interactive docs at `/docs`).
4. **Ship it:** `mcn deploy --target vercel` puts the React app and the API online at one URL.

### Why this works:
- **Zero API Boilerplate:** You never have to write REST APIs. The React and Flutter apps are automatically wired to call your MCN endpoints over HTTP.
- **Generate from a description:** `mcn generate "A leave tracker with manager approval"` writes the backend and UI with Claude, then validates them.
- **Secure Integration:** Database credentials and API keys stay firmly on the MCN backend server, never touching the React View layer.

---

## Quick Start

Install MCN with one command:

```bash
# macOS and Linux
curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.ps1 | iex"
```

Then create and open your first app:

```bash
mcn init my-app                   # a working full-stack app: backend, tests, UI
cd my-app
mcn test backend/main.mcn         # run its tests
mcn studio .                      # open it in MCN Studio → http://localhost:5003
```

`mcn upgrade` updates MCN, `mcn add ml` (or `postgres`, `mongodb`, `scheduler`) adds optional features, and `mcn uninstall` removes it. Node.js is only needed to run the generated React app.

**MCN Studio** is a browser IDE: edit, **Run** the backend, **Preview** the web app, switch to **App** for the mobile (Flutter) version, inspect the database, IoT devices and AI calls, and deploy with **Build → Deploy**. `mcn studio` with no folder opens Studio's own workspace, where the **Templates** gallery (the button in the left bar) has 23 starter apps, searchable by category. Studio only accepts connections from your own machine.

**Editor support.** `mcn vscode` installs the bundled VS Code extension: highlighting, completions, hover docs, errors underlined as you type, and commands to run, test, serve and open Studio.

**Errors** show the line, a caret and a hint:

```
Name error on line 2, column 5: Undefined variable 'totl'
   2 | log(totl)
     |     ^^^^
Hint: Did you mean 'total'?
```

`mcn check file.mcn` finds the same errors without running the code (`--json` for editors and CI).

**Security.** Add `auth "token"` or `auth "jwt"` to a service to require a bearer token (`public name, ...` keeps some endpoints open). Every service gets security headers, rate limiting and a body size limit, and only declared endpoints are reachable. Check functions such as `validate`, `sanitize_html`, `rate_limit`, `require` and `audit_log` are built in, and `mcn audit .` finds SQL injection, hard-coded secrets, open services and more before you ship. Set `MCN_VERBOSE=1` to see engine debug logs; MCN's own logs go to `~/.mcn/logs`.

**Mobile app (Flutter, optional).** Studio's **App** view compiles the same `ui/app.mcn` to Flutter: each component becomes a screen with the same state, handlers and endpoint calls. With the backend running, start it and point it at the backend:

```bash
cd mobile                               # in the project Studio builds
flutter create .                        # first time only
flutter run -d chrome --dart-define=MCN_API_URL=http://localhost:8080
```

On an Android emulator use `--dart-define=MCN_API_URL=http://10.0.2.2:8080`. For a service with `auth`, also pass `--dart-define=MCN_API_TOKEN=...`.

**IoT in Studio.** Open an IoT file (or the **Smart Home** template) and press **Run**: every device it registers appears in the **IoT Simulator** panel, live. Drag a sensor's slider, trigger a motion sensor or flip a relay, and your `watch` automations react. Press **Preview** instead to run the backend as an API with its web app; the panel then shows and drives the backend's devices. Devices declared for a Raspberry Pi or Arduino are simulated in Studio with their pins shown.

**Deploy.** `mcn deploy --target vercel` (or **Build → Deploy** in Studio) compiles the UI to React and puts it on Vercel with your backend at `/api`, on one URL. `mcn deploy --target docker` writes a zip for any container host. See the [deploying guide](website/docs/pages/guide/deploy.md).

**AI features.** Set `ANTHROPIC_API_KEY` to enable `ai()` calls and the Copilot. `agent_run(prompt, {tools: ["lookup_order"]})` lets Claude call your MCN functions as tools and returns the reply with every tool call. MCN uses `claude-opus-5-5` by default; override with `MCN_AI_MODEL` (for `ai()`) or `MCN_CLAUDE_MODEL` (for Copilot).

The Web Playground includes built-in **Interactive Simulators** in the preview pane:
* **DB Explorer**: Inspect database tables, explore generated schemas, and write SQL queries against the live SQLite instance.
* **IoT Simulator**: Slide sensor values (temperature, humidity) or toggle motion triggers to override inputs and test automation handlers.
* **AI & RAG Inspector**: Trace prompt execution pipelines, vector databases search operations, and retrieval matches in real time.

---

## Documentation

The full guide — install, quick start, language guide, and CLI and built-in reference — is in [`website/docs`](website/docs/pages). Read it in Studio at http://localhost:5003/website/docs/ (run `mcn studio`), or as Markdown in this repository.

---

## Language at a Glance

### Variables, operators, control flow

```mcn
var score = 85
var grade = score >= 90 ? "A" : (score >= 80 ? "B" : (score >= 70 ? "C" : "F"))

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
user.score = user.score + 10  // update a property

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
var article  = "MCN compiles one UI file to React and Flutter..."
var question = "What does MCN compile to?"
var message  = "I want my money back for order 1042"
var raw_text = "Order 1042 for Ana Silva, 3 items, total $59.90"

// Free-form generation
var summary = ai("Summarize in 3 bullets: " + article)

// Explicit model routing
var fast   = llm("claude-haiku-5-5", "Quick answer: " + question)
var deep   = llm("claude-opus-5-5",  "Detailed analysis: " + question)

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

var reply = support_reply.run({message: message})

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

### Agents that use your functions

`agent_run` gives Claude your MCN functions as tools. MCN runs the loop (Claude asks for a tool, MCN calls the function, sends the result back) until Claude answers.

```mcn
function lookup_order(order_id)
    return {id: order_id, status: "shipped", eta: "Friday"}

function create_ticket(subject, priority = "normal")
    return {created: true, subject: subject}

var result = agent_run("Where is order 1042? Open a ticket if it's late.", {
    system: "You are a support agent. Use the tools; don't guess.",
    tools: ["lookup_order", {name: "create_ticket", description: "Open a ticket for a person to follow up"}]
})
log(result.reply)              // the answer
log(len(result.tool_calls))    // every tool call, with its input and output
```

Return `tool_calls` from an endpoint and the `chat` element shows "Used N tools" under the reply. Without an API key it runs in mock mode, so the wiring can be tested in class or CI.

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
var users  = [{name: "Ana", department: "Sales"}, {name: "Ben", department: "Ops"}]
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

# Edit index.mcn with your domain logic, then install
mcn install --path ./accenture_crm --name accenture/crm

# Use it
# use "accenture/crm"
```

**Package authoring** — `index.mcn`:

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

The same file compiles to Flutter in Studio's **App** view, with native screens, navigation and charts.

**UI elements** (all from the built-in MCN UI kit, with React as the only dependency):

| Category | Elements |
|---|---|
| App frame | `app` with `sidebar`/`tabs` layouts, `nav` groups, ⌘K search, notifications, dark mode |
| Data | `data_table` (search, filters, sorting, pagination, CSV export), `kanban` (mouse, touch and keyboard), `stat_card` |
| Charts | `bar_chart`, `line_chart`, `area_chart`, `pie_chart`, `donut_chart`, `sparkline` |
| AI | `chat` / `chat_widget` (shows agent tool calls), `agent_builder`, `workflow_builder` |
| Layout | `div grid_cols=N`, `card`, `card_header`, `card_content`, `tabs`, `accordion`, `modal`, `separator` |
| Forms | `form`, `input`, `textarea`, `select`, `checkbox`, `switch`, `radio_group`, `button` |
| Feedback | `alert`, `badge`, `empty_state`, `progress`, `notify(message, kind)` |

The full list, with which elements appear on mobile, is in the [UI elements reference](website/docs/pages/reference/ui-elements.md).

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
    var grade = x >= 90 ? "A" : (x >= 80 ? "B" : (x >= 70 ? "C" : "F"))
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

## IoT & Hardware

The same `device()` code is simulated in Studio and drives real hardware: Raspberry Pi pins (`driver: "gpio"`), an Arduino, ESP32 or Pico over USB (`"serial"`), ESP32 and smart-home gear over MQTT (`"mqtt"`), or an HTTP device (`"http"`).

```mcn
device("register", "greenhouse_temp", {type: "temperature_sensor", driver: "gpio", pin: 4, sensor: "dht22"})
device("register", "vent_fan", {type: "fan", driver: "gpio", pin: 17})
device("register", "soil", {type: "soil_moisture", driver: "serial", pin: "A0", scale: [0, 100]})

function on_temperature(value)
    if value > 28
        device("on", "vent_fan")
    if value < 25
        device("off", "vent_fan")

device("watch", "greenhouse_temp", on_temperature, 2)
log("Soil moisture: " + str(device("read", "soil").value) + "%")
```

```bash
mcn add iot                       # on the Pi: hardware support
mcn iot firmware arduino          # the USB firmware sketch for Arduino / ESP32 / Pico
mcn iot firmware esp32            # the WiFi + MQTT sketch for ESP32
mcn iot service backend/main.mcn  # start the app when the Pi boots
```

`MCN_IOT_SIMULATE=0` makes missing hardware an error (use it in production); unset, MCN simulates whatever isn't connected and says so. The [IoT and hardware guide](website/docs/pages/guide/iot.md) lists the 28 device types, wiring for each part and the MQTT options.

## Security

```mcn
service orders_api
    auth "token"                  // or "jwt"
    public health                 // endpoints anyone may call

    endpoint health()
        return {ok: true}

    endpoint delete_order(id)
        require(id > 0, "Pick an order")
        query("DELETE FROM orders WHERE id = ?", (id,))
        audit_log("delete_order", {id: id})
        return {success: true}
```

- Only declared endpoints are reachable over HTTP; every response gets security headers; requests are rate-limited and body size is capped.
- Built-in checks: `validate`, `sanitize_html`, `escape_html`, `is_email`, `password_strength`, `rate_limit`, `require`, `secure_token`, `safe_equals`, `mask`, and a tamper-evident `audit_log`.
- `mcn audit .` finds SQL injection, hard-coded secrets, open services, unsafe file paths and weak password hashing before you ship (`--json` for CI).

See the [security guide](website/docs/pages/guide/security.md).

## Deploying

```bash
mcn deploy --target vercel          # React app + API (at /api) on Vercel, one URL
mcn deploy --target vercel --prod   # production
mcn deploy --target docker          # zip with Dockerfile and docker-compose for any host
```

The first Vercel deploy asks you to log in (Studio uses a `VERCEL_TOKEN` from **Secrets**). Keys like `ANTHROPIC_API_KEY` come from the project's `.env`. On Vercel, SQLite data is temporary, so use PostgreSQL (`connect_postgresql(env("DATABASE_URL"))`) for data that must last; `watch`, schedules and hardware need an always-on host or a Pi. See the [deploying guide](website/docs/pages/guide/deploy.md).

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

# ── Ship & secure ────────────────────────────────────────────────────────
mcn deploy --target vercel [--prod]    # web app + API on Vercel
mcn deploy --target docker             # zip with Docker files
mcn audit .                            # security scan; --json, --fail-on high|medium|low

# ── Hardware ─────────────────────────────────────────────────────────────
mcn add iot                            # Raspberry Pi GPIO, USB serial, MQTT
mcn iot firmware arduino|esp32         # write the board firmware
mcn iot ports                          # boards plugged in over USB
mcn iot service app.mcn                # start on boot (systemd)

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
| `MCN_AUTH_SECRET`, `MCN_API_TOKEN` | Secret for signed tokens; token for services with `auth "token"` |
| `MCN_CORS_ORIGINS`, `MCN_RATE_LIMIT` | Allowed browser origins; requests per minute per client (default 600) |
| `MCN_IOT_SIMULATE` | `1` simulate all devices, `0` require hardware, unset: simulate what isn't connected |
| `MCN_MQTT_URL` | Broker for MQTT devices |
| `VERCEL_TOKEN` | Lets Studio deploy to Vercel |

---

## Roadmap

| Version | Status | Focus |
|---|---|---|
| v2.0–2.3 | Released | Pipelines, services, workflows, AI primitives, test runner, formatter, full-stack compiler, 100+ built-ins, packages |
| v2.4 | Released | Friendly errors and `mcn check`, `mcn init` projects, `mcn studio <folder>`, VS Code extension with live errors, GET for every endpoint, parallel `task`/`await` |
| **Next** | **On `main`** | MCN UI kit with live Studio preview; Flutter apps compiled from MCN components; `agent_run` with real tool calls; service auth, security checks and `mcn audit`; IoT hardware (Raspberry Pi, Arduino, ESP32, MQTT) with a live simulator; **1-click deploy to Vercel** |
| v3.0 | Planned | Hosted Studio, more 1-click targets (Railway, Fly.io, Render), local LLM (Ollama), error on null property access (opt-in strict mode), public package registry |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setting up a development copy and running the tests, and [`docs/contributing/`](docs/contributing/README.md) for how MCN is built.

**Areas actively needed:**
- More deploy targets (Railway, Fly.io, Render) next to Vercel
- Trying the IoT drivers on more boards (ESP8266, Pico, Arduino R4)
- Rewriting the scripts in `examples/legacy/` for current MCN
- Public package registry (npm-style, for SI packages)
- More domain packages (`payments`, `logistics`, `hr`, `legal`)

---

## License

MIT — see [LICENSE](LICENSE).

---

*MCN v2.4 — write less, ship more. AI is a primitive, not a library.*
