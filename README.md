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

1. **Write an MCN Script (Low Code):** A single `.mcn` file defines your database schema, AI agents, and UI layout using simplified MCN syntax (`ui("table", ...)`).
2. **Generate the Frontend:** The `ui("export", "./app")` command automatically translates your UI definitions into a production-ready React + Tailwind application. It also generates a dedicated `mcn-client.tsx` SDK that wires up all events directly to your backend.
3. **Run the Backend:** Execute your script with `python run_mcn.py serve --file your_app.mcn`. The Python MCN engine instantly spins up a secure, live API server. 

### Why this works:
- **Zero API Boilerplate:** You never have to write REST APIs. The React frontend is automatically wired to execute the Python-based MCN functions via HTTP/WebSockets.
- **Natural Language Translation:** Non-technical staff can use the `ai_v3` translate module (`translate("show all products")`) to generate applications purely from text.
- **Secure Integration:** Database credentials and API keys stay firmly on the MCN backend server, never touching the React View layer.

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

### Rules worth knowing (they match Python)

| Rule | Example |
|---|---|
| `null`, `false`, `0`, `""`, `[]`, `{}` are false | `if items` → only when the list has items |
| `and` / `or` stop early and return a value | `user and user.name`, `name or "guest"` |
| Variables declared in `if` / `for` / `while` / `try` / `catch` stay visible after the block | `for x in rows` … then use `x` |
| Functions have their own local variables | a `var` inside a function never leaks out |
| Negative indexes count from the end; out of range gives `null` | `items[-1]` |
| `for k, v in dict` gives key and value; `for i, x in list` gives index and item | |

Errors point at the exact spot, with a suggestion when you mistype a name:

```
error: Undefined variable 'totl'. Did you mean 'total'?
  --> app.mcn:4:5
  |
4 | log(totl)
  |     ^
```

Logs are written to `~/.mcn/logs` (override with `MCN_LOG_DIR`), not your project folder.

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

### CRUD from a contract (`crud` + `crud_table`)

Describe your data once; MCN creates the table, the API and the screen.
See [`examples/crm_app`](examples/crm_app) for a complete Sales CRM.

```mcn
// models.mcn — shared by backend and UI
contract Lead
    name:      str                                    // required
    email:     str unique
    phone:     str?                                   // ? = optional
    stage:     choice("new", "contacted", "won", "lost") = "new"
    value:     float = 0
    notes:     text?                                  // long text → textarea
    follow_up: date?

// backend.mcn
include "models.mcn"
service crm
    crud Lead
        search    name, email
        sort      created_at desc
        page_size 25

// app.mcn
include "models.mcn"
component Leads
    render
        crud_table Lead columns=["name", "email", "stage", "value"]
```

| Field syntax | Meaning |
|---|---|
| `str`, `text`, `int`, `float`, `bool`, `date`, `datetime` | Type (also picks the form input) |
| `?` after the type | Optional |
| `= value` | Default |
| `unique` | No two records may share the value |
| `choice("a", "b")` | Only these values (dropdown + coloured badge) |
| `ref Company` | Link to a record of another contract (dropdown + name in tables) |

**Relations.** `company: ref Company?` stores the company's id and returns
`company_label` (its `name`, `title` or first text field) with every record. The id must
exist (`"must be an existing company"`), `?company=3` filters, and a company can't be deleted
while leads still use it (`"Can't delete company “AcmeSoft”: used by 2 leads"`).
Edits to a ref are logged by name (`AcmeSoft → Finly`). `ref User` links to app users.

`crud Lead` creates the `leads` table (plus `id`, `created_at`, `updated_at`) and:

| Endpoint | Does |
|---|---|
| `GET /list_leads?search=&page=&page_size=&sort=value desc&stage=won` | `{items, total, page, page_size}` |
| `GET /get_lead/<id>` | One record (404 if missing) |
| `POST /create_lead` | Validate, then insert |
| `POST /update_lead` | Validate the fields sent, then update |
| `POST /delete_lead` | Delete |

Invalid input returns `400 {"errors": {"email": "already exists", "stage": "must be one of …"}}`.
Adding a field to a contract adds the column on the next start; columns are never dropped.
`PurchaseOrder` becomes `list_purchase_orders`, table `purchase_orders`.
From MCN code the endpoints are plain functions: `create_lead({name: "Asha", email: "a@x.in"})`.

`crud_table` renders a table with search, a filter for the first `choice` field, sortable
columns, pagination, an add/edit form generated from the contract, field errors and a delete
confirmation. It compiles to a readable `CrudTable.tsx` you can customise.

Number helpers: `format_currency(123456)` → `₹1,23,456`, `format_number(1234567, 0, "intl")` → `1,234,567`.

### Sign-in, roles and the activity log (`auth`, `allow`, `audit`)

```mcn
// models.mcn — shared by backend and UI
auth
    roles         admin, sales, viewer     // the first role is the administrator
    session_hours 12

// backend.mcn
service crm
    crud Lead
        allow read:   admin, sales, viewer
        allow write:  admin, sales         // create + update
        allow delete: admin
        audit                              // record every create / update / delete

    endpoint get_dashboard()               // any signed-in user (default)
        return {me: current_user.name}
    endpoint pipeline() allow admin, sales
        return ...
    endpoint health() public               // no sign-in needed
        return {ok: true}

// app.mcn
component Users
    render
        crud_table User                    // built-in user management
component Activity
    render
        audit_log                          // who changed what, and when
app CRM
    layout
        sidebar
            nav "Leads"    icon="users"   component=Leads
            nav "Users"    icon="shield"  component=Users     allow admin
            nav "Activity" icon="history" component=Activity  allow admin
```

With an `auth` block:

- Every endpoint needs a signed-in user unless it is marked `public`; `allow` limits it to roles.
  The server answers 401 when signed out and 403 for the wrong role. Unknown role names are an error.
- Built-in endpoints: `POST /login`, `GET /me` (user + the endpoints they may call),
  `GET /auth_status`, `POST /setup` (creates the first administrator while there are no users),
  and admin-only `list_users` / `create_user` / `update_user` / `delete_user` / `list_audit_log`.
- Passwords are stored as PBKDF2 hashes and never returned. Admins can't remove their own access.
- Inside endpoints, `current_user` is the signed-in user (`current_user.role`, `current_user.email`).
- The UI gets a sign-in screen (and a "create the admin account" screen on first run), the signed-in
  user with a sign-out button, nav items per role, and tables that hide Add / Edit / Delete when the
  role can't use them.
- `audit` records changes with before/after values; sign-ins and failed sign-ins are recorded too.
- Sessions are signed with `MCN_SECRET`; without it, a random secret is generated once and kept in the database.

### Workflows, schedules and approvals

```mcn
service crm
    crud Quote
        approval                              // approve / reject before it counts
            approvers admin, manager
            when      record.discount > 10    // optional: only some records need it
        import                                // CSV import  (import_quotes)
        export                                // CSV export  (export_quotes)

    // Triggers run after a change is saved: create | update | delete | approve | reject
    on update Lead
        if changed("stage") and record.stage == "won"
            send_email("manager@acme.in", "Won: {record.name} ({format_currency(record.value)})", "🎉")
            create_follow_up({title: "Kick-off", lead: record.id, due: add_days(today(), 2)})

    on approve Quote
        var pdf = make_pdf("Quote {record.title}", ["Approved by {record.approval_by}",
                           [["Item", "Amount"], ["Total", format_currency(record.amount)]]])
        send_email("sales@acme.in", "Approved: {record.title}", "Attached.", [pdf])

    // Scheduled jobs (server local time): every N minutes|hours|days|weeks, or a weekday
    job overdue_digest every day at "09:00"
        ...
    job sync every 15 minutes
        ...
```

- **Triggers** see `record` (after), `old` (before) and `changed("field")`. A failing trigger is
  logged (and recorded in the activity log) but doesn't undo the change; triggers nested more than
  5 deep are skipped to stop loops.
- **Approvals** add `approval_status` (pending / approved / rejected), `approval_by`, `approval_at`,
  `approval_note` and `requested_by`, plus `approve_quote` / `reject_quote` endpoints for the
  approver roles. Nobody can approve their own request, and an edit by the requester sends it back
  for approval. The UI shows Pending / Approved / Rejected tabs and approve / reject buttons.
- **Jobs**: `mcn serve` runs them in the background; admins can see them with `list_jobs` and run one
  now with `run_job {name}`.
- **CSV**: imports match columns by field name or label, accept a linked record's name for `ref`
  fields, and report every bad row with its line number while importing the rest.

### Files, PDFs and email

```mcn
contract Expense
    receipt: file?                    // upload in the form, link in the table

var pdf = make_pdf("Invoice #42", ["Thanks for your order.", [["Item", "Qty"], ["Pen", 2]]])
send_email("a@x.in, b@x.in", "Your invoice", "Attached.", [pdf])
```

- Uploads go to `POST /upload` (signed-in users) and are stored in `uploads/`; links are signed and
  expire after 24 hours, so they work in `<a href>` without a token.
- `make_pdf(title, content)` needs no dependencies: content is text, a list of paragraphs,
  tables (lists of rows or of objects) and `{heading: "…"}`.
- `send_email` uses SMTP when `MCN_SMTP_HOST` is set. Without it, emails are printed and kept in the
  outbox (`list_outbox`, admin) — handy in development.

### Field-level permissions

```mcn
contract Employee
    name:   str
    salary: float?  read admin, hr  write admin     // hidden from everyone else
```

Hidden fields are removed from responses, exports, search and sorting; writing a field your role
can't change is a validation error. The UI hides the column and the form field, or shows it read-only.

### Single sign-on

```mcn
auth
    roles admin, staff
    sso
        issuer        "https://accounts.google.com"    // Microsoft, Okta, Keycloak, Zoho … (OpenID Connect)
        client_id     env("SSO_CLIENT_ID")
        client_secret env("SSO_CLIENT_SECRET")
        allow_domains "acme.in"
        default_role  staff
```

Register `<backend>/sso_callback` as the redirect URL at your provider. The sign-in screen gets a
"Sign in with Google" button; new people are created with `default_role` (the very first one becomes
the administrator). Set `MCN_APP_URL` to your app's address in production — the session token is only
sent back to allowed addresses (localhost is allowed for development).

### Mobile

Every `mcn build` output is an installable web app: a manifest, icons and a service worker that caches
the app itself (never API data). On Android and iOS, "Add to Home Screen" gives a full-screen app with
its own icon; the layout switches to a phone-friendly header and navigation.

For a native Android/iOS app, build the same source for Flutter:

```bash
mcn build ui/app.mcn --target flutter --out mobile
cd mobile
flutter create --platforms=android,ios .     # adds the android/ and ios/ folders
flutter pub get
flutter run --dart-define=MCN_API_URL=http://10.0.2.2:8080
```

The Flutter app talks to the same `mcn serve` backend and keeps the same rules:

| MCN | Flutter |
|---|---|
| `crud_table Lead` | Searchable list with filters, pull-to-refresh, a form screen for add/edit, delete, approve/reject |
| `ref`, `file`, `choice`, `date` fields | Dropdown of related records, upload/open, dropdown, date picker |
| `read admin` / `write admin` on a field | Hidden or read-only for other roles |
| `auth` | Sign-in and first-run setup screens; the session is kept on the device |
| `nav … allow admin` | Navigation shows only the screens your role can open (bottom bar, or a drawer for more than 5) |
| `audit_log` | Activity screen |
| `state`, `on load`, `on remove(id)`, `if`/`for`/`empty`, `toast`, `confirm` | A Flutter screen with the same state, handlers and conditions |
| `card`, `stat_card`, `badge`, `alert`, `table`, `input bind=`, `select`, `switch`, `div grid_cols=N` | Material 3 widgets; grids collapse to one column on phones |

Charts, data grids, Gantt charts and modals are web-only for now and show a note in the app.
`10.0.2.2` is your computer as seen from the Android emulator; Android blocks plain `http://` unless
you allow it for development (see the generated `README.md`).

### Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `MCN_SECRET` | Signs sessions and file links (else a random secret is kept in the database) |
| `MCN_APP_URL` | Your app's address(es), comma-separated — where SSO may send people back |
| `MCN_PUBLIC_URL` | The backend's public address (for the SSO redirect URL behind a proxy) |
| `MCN_SMTP_HOST`, `MCN_SMTP_PORT`, `MCN_SMTP_USER`, `MCN_SMTP_PASSWORD`, `MCN_SMTP_FROM`, `MCN_SMTP_TLS` | Email delivery |
| `MCN_UPLOAD_DIR`, `MCN_MAX_UPLOAD_MB` | Where uploads are stored (default `uploads/`) and the size limit (default 10) |
| `MCN_LOG_DIR` | Log files (default `~/.mcn/logs`) |

### Lists, conditions and row actions in `render`

```mcn
component TaskBoard
    state tasks   = []
    state loading = true

    on load
        tasks   = list_tasks()
        loading = false

    on remove(id)                       // handlers can take parameters
        delete_task(id)
        tasks = list_tasks()

    render
        if loading
            p "Loading…"
        else if tasks.length > 50
            alert text="Showing the first 50 tasks"
        else
            p "You have {tasks.length} tasks"    // strings interpolate

        for task in tasks                         // or: for i, task in tasks
            card
                card_header "{task.title}"
                badge text=task.done ? "Done" : "Open"
                button "Delete" on_click=remove(task.id)
        empty                                     // shown when the list is empty
            p "No tasks yet"
```

- `if / else if / else` and `for … in` work anywhere inside `render`, including inside `table_body`.
- `empty` is optional, and only has a meaning directly after a `for` block.
- React keys are added for you (`task.id` when present, otherwise the index).
- `on_click=remove(task.id)` calls a component handler; `on_click=delete_task(task.id)` calls the backend directly.
- Words like `task`, `test`, `state` and `step` can be used as names (`for task in tasks`); they only act as keywords at the start of a declaration.

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
# ── Script execution ─────────────────────────────────────────────────────
mcn run script.mcn
mcn repl

# ── Full-stack ───────────────────────────────────────────────────────────
mcn generate "An invoice app with PDF export"  # AI-generated app
mcn generate "..." --out ./myapp --build       # generate + compile
mcn build ui/app.mcn --out frontend           # compile MCN UI → React
mcn build ui/app.mcn --target flutter          # compile MCN UI → Flutter (mobile/)

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

## Packaging & Distribution

To package and deploy MCN across enterprise clusters and edge environments:

### 1. Python Wheel & Source Build
Compile MCN into a universal wheel distribution:
```bash
python3 setup.py sdist bdist_wheel
```
This produces PEP 517 artifacts in `dist/` that can be pushed to secure private PyPI registries (e.g., AWS CodeArtifact, JFrog Artifactory) and installed via:
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
