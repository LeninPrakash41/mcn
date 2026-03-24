# MCN Developer Guide

## Table of Contents

1. [Installation](#1-installation)
2. [Language Syntax](#2-language-syntax)
3. [Built-in Functions & Packages](#3-built-in-functions--packages)
4. [Agentic System Primitives](#4-agentic-system-primitives)
5. [Frontend UI Primitives](#5-frontend-ui-primitives)
6. [Building a Full-Stack Agentic App](#6-building-a-full-stack-agentic-app)
7. [CLI Reference](#7-cli-reference)
8. [Running the Application](#8-running-the-application)
9. [Configuration & API Keys](#9-configuration--api-keys)
10. [Best Practices](#10-best-practices)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Installation

```bash
git clone <repository>
cd mt-mcn
pip install -r requirements.txt
```

Verify the install:

```bash
python -m mcn --version
# MCN 2.0
```

---

## 2. Language Syntax

### Variables

```mcn
var name     = "Alice"
var age      = 25
var active   = true
var scores   = [85, 92, 78]
var profile  = {"role": "engineer", "level": 3}
```

### Type Hints (optional)

```mcn
type "user_id" "number"
type "email"   "string"
type "tags"    "array"

var user_id = 123
var email   = "alice@example.com"
```

### Conditionals

```mcn
if age >= 18
    log "Adult"
else
    log "Minor"
```

### Loops

```mcn
var i = 0
while i < 5
    log "Count: " + i
    i = i + 1

for item in scores
    log "Score: " + item
```

### Functions

```mcn
function greet(name, role)
    var msg = "Hello " + name + ", you are a " + role
    return msg

var result = greet("Alice", "engineer")
log result
```

### Error Handling

```mcn
try
    var result = trigger("https://api.example.com/data")
catch
    log "Failed: " + error
    var result = {"data": "fallback"}
```

### Parallel Tasks

```mcn
task "email"    "trigger" "https://mail.api.com/send"  {"to": "user@example.com"}
task "log_db"   "query"   "INSERT INTO logs VALUES (?)" ("sent")
task "ai_reply" "ai"      "Generate a follow-up message"

var results = await "email" "log_db" "ai_reply"
log "All done: " + results
```

---

## 3. Built-in Functions & Packages

### Core Built-ins

| Function | Description |
|---|---|
| `log(msg)` | Print with timestamp |
| `query(sql, params)` | SQLite database operations |
| `trigger(url, data, method)` | HTTP requests to any API |
| `ai(prompt, model, tokens)` | LLM call (OpenAI / Anthropic / Ollama) |

```mcn
// Database — parameterized query
var users = query("SELECT * FROM users WHERE age > ?", (18,))

// HTTP — POST to external API
var res = trigger("https://api.example.com/data", {"key": "value"})

// AI — call LLM
var summary = ai("Summarize this: " + users)
```

### Package System

Load packages at the top of any `.mcn` file:

```mcn
use "db"
use "http"
use "ai"
```

#### `db` package

```mcn
use "db"
batch_insert("users", [{"name": "Alice"}, {"name": "Bob"}])
backup_table("users")
```

#### `http` package

```mcn
use "http"
var data = get_json("https://api.example.com/users")
post_form("https://forms.example.com", {"name": "Alice"})
```

#### `ai` package

```mcn
use "ai"
var sentiment = analyze_sentiment("I love this product!")
var summary   = summarize("Long text here...")
var trend     = predict_trend([1, 2, 3, 4, 5])
```

---

## 4. Agentic System Primitives

MCN has four first-class primitives for building agentic systems: `prompt`, `agent`, `pipeline`, and `service`.

### `prompt` — Reusable AI prompt templates

Define prompts once, reference them anywhere. Supports `{{variable}}` placeholders.

```mcn
prompt outreach_message
    system "You are an expert B2B sales copywriter."
    user   "Write a LinkedIn message for {{name}}, {{title}} at {{company}}. Tone: {{tone}}. Max 280 chars."
    format text

prompt classify_intent
    system "You are a sales intent classifier."
    user   "Classify this reply as: interested / not_interested / needs_info. Reply: {{reply}}"
    format text
```

`format` can be `text` or `json`.

---

### `agent` — AI agent with tools and memory

An agent groups related AI tasks under a single model + toolset. Each `task` inside an agent is a callable function.

```mcn
agent lead_gen_agent
    model  "gpt-4o"
    tools  query, trigger, ai
    memory session

    task run_campaign(campaign_id, industry, tone)
        var leads = trigger("https://leads-api.example.com/search", {
            "industry": industry,
            "limit":    20
        })

        var i = 0
        while i < leads.length
            var msg = ai(
                "Write a LinkedIn message for " + leads[i].name +
                ", " + leads[i].title + " at " + leads[i].company +
                ". Tone: " + tone + ". Max 280 chars."
            )
            trigger("https://api.phantombuster.com/launch", {
                "profile_url": leads[i].linkedin_url,
                "message":     msg
            })
            query(
                "INSERT INTO leads (name, company, message, status) VALUES (?, ?, ?, 'sent')",
                (leads[i].name, leads[i].company, msg)
            )
            i = i + 1

        return {"sent": leads.length}

    task process_replies()
        var replies = trigger("https://api.phantombuster.com/replies", {"status": "unread"})

        var i = 0
        while i < replies.length
            var intent = ai("Classify: interested / not_interested / needs_info. Reply: " + replies[i].text)

            if intent.contains("interested")
                var booking = ai("Write a reply to book a 15-min call. Name: " + replies[i].sender_name)
                trigger("https://api.phantombuster.com/reply", {
                    "thread_id": replies[i].thread_id,
                    "message":   booking
                })
                query("UPDATE leads SET status = 'meeting_booked' WHERE linkedin = ?", (replies[i].profile_url))

            if intent.contains("needs_info")
                var answer = ai("Answer helpfully: " + replies[i].text)
                trigger("https://api.phantombuster.com/reply", {
                    "thread_id": replies[i].thread_id,
                    "message":   answer
                })
                query("UPDATE leads SET status = 'nurturing' WHERE linkedin = ?", (replies[i].profile_url))

            i = i + 1

        return {"processed": replies.length}
```

**Agent options:**

| Option | Values | Description |
|---|---|---|
| `model` | `"gpt-4o"`, `"claude-3-5-sonnet"`, `"ollama/llama3"` | LLM to use |
| `tools` | `query, trigger, ai, fetch` | Built-ins the agent can call |
| `memory` | `"session"`, `"persistent"`, `""` | Context retention scope |

---

### `pipeline` — Multi-stage data pipelines

```mcn
pipeline data_pipeline
    stage extract
        var raw = get_json("https://api.example.com/data")
        return raw

    stage transform(data)
        var cleaned = ai("Clean and normalize this JSON: " + data)
        return cleaned

    stage load(data)
        batch_insert("processed_data", data)
        return {"loaded": true}
```

---

### `service` — REST API server

A `service` block exposes functions as HTTP endpoints. MCN's server runtime reads this block and starts an HTTP server automatically.

```mcn
service linkedin_api
    port 8080

    endpoint run_campaign(campaign_id, industry, tone)
        var result = lead_gen_agent.run_campaign(campaign_id, industry, tone)
        return {"status": "ok", "data": result}

    endpoint process_replies()
        var result = lead_gen_agent.process_replies()
        return {"status": "ok", "data": result}

    endpoint list_leads(status)
        if status == null
            var leads = query("SELECT * FROM leads ORDER BY created_at DESC")
        else
            var leads = query("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC", (status))
        return {"status": "ok", "data": leads}

    endpoint create_campaign(name, industry, tone)
        query("INSERT INTO campaigns (name, industry, tone) VALUES (?, ?, ?)", (name, industry, tone))
        var campaign = query("SELECT * FROM campaigns ORDER BY id DESC LIMIT 1")
        return {"status": "ok", "data": campaign[0]}
```

Endpoint HTTP method is inferred automatically:
- Names starting with `get_`, `list_`, `fetch_`, `search_` → `GET` + `POST`
- All others → `POST`

---

## 5. Frontend UI Primitives

MCN compiles `component` and `app` blocks into a full React + shadcn/ui + Tailwind project via `mcn build`.

### `component` — React component

A component has three sections: `state`, `on` (event handlers), and `render` (UI tree).

```mcn
component CampaignForm
    state camp_name = ""
    state industry  = ""
    state tone      = "professional"
    state result    = ""

    on submit
        var camp = create_campaign(camp_name, industry, tone)
        var run  = run_campaign(camp.data.id, industry, tone)
        result   = "Launched! Sent to " + run.data.sent + " leads."

    render
        card
            card_header "Launch Campaign"
            card_content
                form on_submit=submit
                    input  bind=camp_name label="Campaign Name"
                    input  bind=industry  label="Target Industry"
                    select bind=tone label="Tone" options=["professional", "casual", "direct"]
                    button "Launch"
                    alert text=result show=result
```

**State** — reactive variables, map to React `useState`:

```mcn
state items   = []
state loading = false
state query   = ""
```

**On handlers** — map to React event handlers or `useEffect`:

| Event | React equivalent |
|---|---|
| `on load` | `useEffect(() => {}, [])` |
| `on submit` | `onSubmit` on a `<form>` |
| `on search` | `useCallback` handler |
| `on filter_change` | `useCallback` handler |

**Render tree** — UI elements:

| MCN tag | Renders as |
|---|---|
| `card` | shadcn `<Card>` |
| `card_header "Title"` | `<CardHeader><h2>Title</h2></CardHeader>` |
| `input bind=x label="L"` | shadcn `<Input>` with `<Label>` + two-way binding |
| `button "Text"` | shadcn `<Button>` |
| `select bind=x options=[...]` | shadcn `<Select>` |
| `table` | shadcn `<Table>` with auto-generated body rows |
| `stat_card` | KPI card with icon, value, trend |
| `alert text=x show=x` | shadcn `<Alert>` with conditional render |
| `modal show=x` | shadcn `<Dialog>` |
| `bar_chart data=x x_key="k" y_key="v"` | Recharts `<BarChart>` |
| `line_chart` | Recharts `<LineChart>` |
| `pie_chart` | Recharts `<PieChart>` |
| `badge`, `separator`, `progress`, `avatar` | shadcn equivalents |
| `tabs`, `tab_trigger`, `tab_content` | shadcn `<Tabs>` |
| `accordion`, `accordion_item` | shadcn `<Accordion>` |
| `dropdown_menu` | shadcn `<DropdownMenu>` |
| `sheet` | shadcn `<Sheet>` |
| `checkbox`, `switch`, `radio_group` | shadcn form controls |

**CRUD table** — add `edit_item` state to get Edit/Delete buttons auto-injected:

```mcn
component LeadsTable
    state items     = []
    state edit_item = null
    state edit_name = ""
    state show_edit_modal = false

    on load
        var res = list_leads()
        items = res.data

    render
        card
            card_header "Leads"
            card_content
                table
                    table_header
                        table_row
                            table_head "Name"
                            table_head "Company"
                            table_head "Status"
                    table_body

        modal show=show_edit_modal
            card_header "Edit Lead"
            card_content
                input bind=edit_name label="Name"
                button "Save"
```

The compiler auto-injects Edit/Delete buttons in the table body and wires `handleEdit`, `handleDelete`, `handleSave` handlers.

---

### `app` — App shell with layout

```mcn
app LinkedInLeadGen
    title "LinkedIn Lead Gen Agent"
    theme "professional"

    layout
        sidebar
            nav "Dashboard"  icon="layout-dashboard" component=StatsPanel
            nav "Campaigns"  icon="rocket"            component=CampaignForm
            nav "Leads"      icon="users"             component=LeadsTable
            nav "Replies"    icon="message-square"    component=ReplyProcessor
        main
            StatsPanel
            CampaignForm
            LeadsTable
            ReplyProcessor
```

**Theme options:** `"professional"`, `"modern"`, `"minimal"`, `"default"`

**Layout options:**

```mcn
// Sidebar navigation
layout
    sidebar
        nav "Label" icon="icon-name" component=ComponentName

// Tab navigation
layout
    tabs
        tab "Label" component=ComponentName

// URL routing (react-router-dom)
layout
    routes
        route "/" Dashboard
        route "/leads" LeadsTable
        route "/settings" Settings
```

---

## 6. Building a Full-Stack Agentic App

A complete MCN app has two files:

```
my_app/
├── main.mcn    ← backend: db setup, prompts, agent, service
└── app.mcn     ← frontend: components, app shell
```

### `main.mcn` structure

```mcn
// 1. Packages
use "db"
use "ai"
use "http"

// 2. Database schema
query("CREATE TABLE IF NOT EXISTS ...")

// 3. Prompts
prompt my_prompt
    system "..."
    user   "... {{variable}} ..."
    format text

// 4. Agent with tasks
agent my_agent
    model  "gpt-4o"
    tools  query, trigger, ai
    memory session

    task do_something(param)
        // logic using query(), trigger(), ai()
        return result

// 5. Service (REST API)
service my_api
    port 8080

    endpoint my_endpoint(param)
        var result = my_agent.do_something(param)
        return {"status": "ok", "data": result}
```

### `app.mcn` structure

```mcn
// 1. Components
component MyComponent
    state data = []

    on load
        var res = my_endpoint()
        data = res.data

    render
        card
            card_header "Title"
            card_content
                // UI elements

// 2. App shell
app MyApp
    title "My App"
    theme "professional"

    layout
        sidebar
            nav "Home" component=MyComponent
        main
            MyComponent
```

---

## 7. CLI Reference

| Command | Description |
|---|---|
| `mcn run <file>` | Execute a `.mcn` script |
| `mcn serve --file <file> --port N` | Start HTTP server from a `service` block |
| `mcn build <file> --out <dir>` | Compile `component`/`app` blocks → React project |
| `mcn check <file>` | Static type-check without running |
| `mcn check <file> --strict` | Treat warnings as errors |
| `mcn fmt <file>` | Format MCN source |
| `mcn fmt <file> --write` | Format and rewrite in place |
| `mcn test <file>` | Run `test` blocks |
| `mcn repl` | Interactive REPL |
| `mcn init <name>` | Scaffold a new project |
| `mcn generate "<description>"` | AI-generate a full app from natural language |
| `mcn config set api_key <key>` | Save Claude/OpenAI API key |
| `mcn config show` | Show saved config |
| `mcn install <package>` | Install a MCN package |
| `mcn packages list` | List installed packages |
| `mcn deploy --target zip` | Package app for deployment |

---

## 8. Running the Application

### Step 1 — Start the backend

The `mcn serve` command reads the `service` block in `main.mcn` and exposes each `endpoint` as an HTTP route.

```bash
cd mt-mcn

python -m mcn serve --file examples/linkedin_agent/main.mcn --host 0.0.0.0 --port 8080
```

Expected output:

```
Loading: examples/linkedin_agent/main.mcn

MCN server running on http://localhost:8080
Endpoints:
  POST /run_campaign      ← campaign_id, industry, tone
  POST /process_replies   ← (no params)
  POST /get_stats         ← (no params)
  POST /list_leads        ← status
  POST /create_campaign   ← name, industry, tone

Press Ctrl+C to stop.
```

Test an endpoint:

```bash
curl -X POST http://localhost:8080/list_leads \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Step 2 — Build the frontend

The `mcn build` command runs the UI compiler. It reads all `component` and `app` blocks from `app.mcn` and generates a complete React + shadcn/ui + Tailwind project.

```bash
python -m mcn build examples/linkedin_agent/app.mcn --out examples/linkedin_agent/frontend
```

Expected output:

```
Building: LinkedInLeadGen
Components: StatsPanel, CampaignForm, LeadsTable, ReplyProcessor
Output:    examples/linkedin_agent/frontend/

  write  frontend/src/lib/utils.ts
  write  frontend/src/components/StatsPanel.tsx
  write  frontend/src/components/CampaignForm.tsx
  write  frontend/src/components/LeadsTable.tsx
  write  frontend/src/components/ReplyProcessor.tsx
  write  frontend/src/services/api.ts
  write  frontend/src/App.tsx
  write  frontend/src/main.tsx
  write  frontend/src/globals.css
  write  frontend/package.json
  write  frontend/tailwind.config.ts
  write  frontend/vite.config.ts
  write  frontend/index.html

  shadcn  npx shadcn@latest add card input button select table alert dialog badge

✓ Frontend generated in frontend/

Next steps:
  cd frontend
  npm install
  npx shadcn@latest add card input button select table alert dialog badge
  npm run dev
```

---

### Step 3 — Install and run the frontend

```bash
cd examples/linkedin_agent/frontend

npm install

npx shadcn@latest add card input button select table alert dialog badge separator

npm run dev
```

Frontend runs on `http://localhost:5173`. It connects to the MCN backend at `http://localhost:8080` via the auto-generated `src/services/api.ts`.

---

### Step 4 — Set your AI API key

The `ai()` calls in the agent need an API key. Set it once and MCN stores it in `~/.mcn/config.json`.

```bash
# OpenAI
python -m mcn config set api_key sk-...your-openai-key...

# Anthropic
python -m mcn config set api_key sk-ant-...your-anthropic-key...
```

Or use environment variables:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

---

### Full architecture

```
app.mcn  ──[mcn build]──►  React + shadcn/ui  (npm run dev → :5173)
                                    │
                              src/services/api.ts
                              (fetch POST to :8080)
                                    │
main.mcn ──[mcn serve]──►  MCN HTTP Server (:8080)
                                    │
                    ┌───────────────┼───────────────┐
                  agent           query()        trigger()
                tasks             SQLite       External APIs
                  │                              (LinkedIn,
                ai()                           Phantombuster)
              OpenAI/Anthropic
```

---

### Running both together

Terminal 1 — backend:

```bash
python -m mcn serve --file examples/linkedin_agent/main.mcn --port 8080
```

Terminal 2 — frontend:

```bash
cd examples/linkedin_agent/frontend && npm run dev
```

Or add to the project `Makefile`:

```makefile
run:
	python -m mcn serve --file examples/linkedin_agent/main.mcn --port 8080 &
	cd examples/linkedin_agent/frontend && npm run dev
```

---

## 9. Configuration & API Keys

```bash
# Save key
python -m mcn config set api_key sk-...

# View saved config (keys are masked)
python -m mcn config show

# Get a specific value
python -m mcn config get api_key
```

Config is stored at `~/.mcn/config.json`. Key resolution order for `ai()` calls:

1. `--api-key` flag (CLI only)
2. `~/.mcn/config.json`
3. `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env var

---

## 10. Best Practices

### Always use parameterized queries

```mcn
// Good
var user = query("SELECT * FROM users WHERE id = ?", (user_id))

// Bad — SQL injection risk
var user = query("SELECT * FROM users WHERE id = " + user_id)
```

### Wrap external calls in try/catch

```mcn
try
    var res = trigger("https://api.example.com/data")
catch
    log "API failed: " + error
    var res = {"data": []}
```

### Use parallel tasks for independent operations

```mcn
// Good — runs concurrently
task "notify" "trigger" "https://notify.com/send" {"msg": "Done"}
task "log"    "query"   "INSERT INTO logs VALUES (?)" ("completed")
var results = await "notify" "log"

// Bad — sequential when they don't depend on each other
trigger("https://notify.com/send", {"msg": "Done"})
query("INSERT INTO logs VALUES (?)", ("completed"))
```

### Load packages at the top

```mcn
// Always at the top of the file
use "db"
use "http"
use "ai"
```

### Keep agent tasks focused

Each `task` inside an `agent` should do one thing. Compose them in the `service` endpoints.

```mcn
agent my_agent
    task fetch_leads(industry)      // only fetches
    task generate_message(lead)     // only generates
    task send_outreach(lead, msg)   // only sends

service my_api
    endpoint run_campaign(industry)
        var leads = my_agent.fetch_leads(industry)
        // compose tasks here
```

---

## 11. Troubleshooting

**`ModuleNotFoundError` on serve/build**

```bash
pip install -r requirements.txt
```

**`No component or app declarations found`**

The `build` command requires at least one `component` or `app` block in the file. Check that `app.mcn` contains these blocks, not `main.mcn`.

**CORS errors in the browser**

The MCN server sends `Access-Control-Allow-Origin: *` by default. If you still see CORS errors, confirm the frontend is calling the correct port (`8080`) and the backend is running with `--host 0.0.0.0`.

**`ai()` returns empty or errors**

```bash
# Check your key is saved
python -m mcn config show

# Or set it explicitly
python -m mcn config set api_key sk-...
```

**Frontend can't reach backend**

The generated `src/services/api.ts` reads `VITE_API_URL` from the environment. Create a `.env` file in the frontend directory:

```bash
# frontend/.env
VITE_API_URL=http://localhost:8080
```

**Static type errors before running**

```bash
python -m mcn check examples/linkedin_agent/main.mcn
python -m mcn check examples/linkedin_agent/app.mcn --strict
```

**View runtime logs**

```bash
python -m mcn logs --type errors
python -m mcn logs --type debug
```
