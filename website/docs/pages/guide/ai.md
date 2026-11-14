# AI functions

AI calls are ordinary functions. They use Claude (`claude-opus-5-5` by default) when `ANTHROPIC_API_KEY` is set, and return clearly labelled mock answers when it isn't, so code always runs.

```bash
export ANTHROPIC_API_KEY=your-key
```

## Generate text: `ai`

```mcn
var article = "MCN is a language for building full-stack apps with AI built in."
var summary = ai("Summarise in one sentence: " + article)
var formal = ai("Rewrite formally: " + summary, {temperature: 0.2})
log(summary)
```

`llm(model, prompt, options?)` does the same with an explicit model name.

## Choose a label: `classify`

```mcn
var ticket = "I was charged twice this month"
var team = classify(ticket, ["billing", "bug", "account"])
log(team)      // billing
```

It always returns one of the labels you give it, so you can branch on the result safely.

## Pull out fields: `extract`

Describe the shape with a `contract`, then extract it from free text:

```mcn
contract Invoice
    vendor: str
    amount: float
    due_date: str

var email = "Acme Ltd invoice for $1,250.00, payment due 30 November."
var invoice = extract(email, Invoice)
log(invoice.vendor)
```

## Answer from documents: `rag`

```mcn
var docs = [
    "Refunds are issued within 5 working days.",
    "Support is available Monday to Friday, 9am to 5pm."
]
var answer = rag("How long do refunds take?", docs)
log(answer)
```

For larger collections, store documents once and search them:

```mcn
vector_upsert("refunds", "Refunds are issued within 5 working days.")
vector_upsert("hours", "Support is available Monday to Friday.")
var hits = vector_search("when will I get my money back", 1)
log(hits[0].id)       // refunds
```

`embed(text)` returns the embedding vector itself. Embeddings use OpenAI when `OPENAI_API_KEY` is set, Ollama when `OLLAMA_URL` is set, and a deterministic local fallback otherwise.

## Agents with tools: `agent_run`

`agent_run(prompt, options)` lets Claude call your MCN functions to get an answer. Name the functions in `tools`; each becomes a tool whose parameters are the function's parameters (those without a default are required). MCN runs the loop: Claude asks for a tool, MCN calls your function, sends the result back, and repeats until Claude answers.

```mcn
function lookup_order(order_id)
    var rows = query("SELECT id, status, total FROM orders WHERE id = ?", (order_id,))
    return rows[0] if len(rows) > 0 else {error: "No order " + str(order_id)}

function create_ticket(subject, priority = "normal")
    query("INSERT INTO tickets (subject, priority) VALUES (?, ?)", (subject, priority))
    return {created: true}

var result = agent_run("Where is order 1042? Open a ticket if it's late.", {
    system: "You are a support agent. Use the tools; don't guess order details.",
    tools: [
        "lookup_order",
        {name: "create_ticket", description: "Open a support ticket for a person to follow up"}
    ],
    max_steps: 6
})
log(result.reply)
for call in result.tool_calls
    log(call.name + " " + to_json(call.input))
```

| Option | Default | Meaning |
|---|---|---|
| `tools` | none | Function names, or `{name, description}` to tell Claude when to use one |
| `system` | none | Instructions for the agent |
| `history` | none | Earlier turns: a list of `{role, content}` |
| `model` | `MCN_AI_MODEL` | Claude model |
| `max_steps` | 8 (max 25) | Model calls before it stops |
| `effort` | model default | `"low"`, `"medium"`, `"high"` or `"max"` |

It returns `{reply, tool_calls, steps}`. Each entry in `tool_calls` has `name`, `input`, `output` (or `error`) and `ms`. When a function fails, the error goes back to Claude so it can try something else, and `agent_run` itself doesn't throw. Return `tool_calls` from your endpoint and the `chat` element shows a "Used N tools" list under the reply.

> **Warning** A tool can do anything its function does. Give agents functions that are safe to call with any arguments, check inputs inside them, and keep actions that send or delete things behind a person (`checkpoint`) or a draft table.

## Named agents, pipelines and knowledge sources

For longer-lived AI pieces, three helpers keep state between calls:

```mcn
// An agent with a role, memory of the conversation, and optional tools
agent("create", "analyst", {prompt: "You analyse our sales data", tools: ["revenue_by_month"]})
log(agent("think", "analyst", "Which month was best?"))
log(agent("think", "analyst", "Why?"))            // remembers the last answer
agent("reset", "analyst")

// A pipeline of steps, run on one item or a list
pipeline("create", "tickets", [
    {type: "clean"},
    {type: "ai_classify", params: {categories: ["bug", "billing", "question"]}},
    {type: "ai_extract", params: {fields: ["order_id", "product"]}},
    {type: "save_ticket"}                           // one of your functions
])
var inbox = ["The app crashes on login", "I was charged twice for order A17"]
var tickets = pipeline("run", "tickets", inbox)

// A knowledge source answered from its most relevant passages
datasource("create", "handbook", "file", "docs/handbook.md")   // also "text", "url" or "documents"
log(datasource("query", "handbook", "How many days of leave do I get?"))
```

| Call | Does |
|---|---|
| `agent("create", name, {prompt, model?, tools?})` | An agent with a role. With `tools`, it answers through `agent_run` and can call those functions |
| `agent("create_multi", name, {sub_agents, coordinator_prompt})` | A coordinator that asks each agent, then combines their answers |
| `agent("think", name, message)` | The agent's reply, using its role and the last 12 exchanges |
| `agent("reset", name)`, `agent("list")` | Forget the conversation; list the agents |
| `pipeline("create", name, steps)`, `pipeline("run", name, data)` | Steps: `clean`, `transform`, `ai_classify` (`categories`, `field`), `ai_extract` (`fields`), or a function name |
| `datasource("create", name, type, source)` | `text`, `file` (text, Markdown, CSV, JSON; PDF with `pypdf`), `url` or `documents` |
| `datasource("query", name, question)`, `datasource("search", name, question)` | An answer from the most relevant passages via `rag()`; or just those passages |

Like the other AI functions, these use mock answers when there's no API key.

## Human approval: `checkpoint`

`checkpoint(message, data)` pauses a script and asks a person to approve, reject or edit `data` before it continues — for example before sending an AI-written email.

## Teach a model your examples: `fine_tune`

When prompts alone don't get the tone, format or domain right, fine-tune a model on examples of the answers you want, then use it like any other model:

```mcn
var job = fine_tune("gpt-4.1-mini", "support_replies.csv", "support-bot", {n_epochs: 3})
log(job.status)                                   // validating_files

var status = get_training_status("support-bot")   // by the name you gave it, or the job id
log(status.status)                                // queued, running, then succeeded
log(status.message)                               // e.g. "Step 40/60: training loss=0.12"

var reply = ai("My order hasn't arrived", {model: "support-bot"})
```

**Training data.** A CSV, JSON or JSONL file, or an MCN list, with at least 10 examples. Each example is `{prompt, completion}`, `{input, output}`, `{question, answer}` or a ready-made `{messages: [...]}` conversation, with an optional `system` field. MCN checks every example first and lists problems by row number (`Example 12 has an empty completion`). Pass `{strict: false}` to skip bad rows instead.

**Where it trains.** On OpenAI's fine-tuning service, because Anthropic doesn't offer public fine-tuning for Claude. It needs `OPENAI_API_KEY`, and OpenAI charges for training. The base model must be one OpenAI can fine-tune; their [fine-tuning guide](https://platform.openai.com/docs/guides/fine-tuning) lists them. Without a key, or with `{dry_run: true}`, `fine_tune()` checks the examples and writes the training file to `~/.mcn/fine_tune/` without uploading anything.

| Option | Effect |
|---|---|
| `n_epochs`, `batch_size`, `learning_rate_multiplier` | Training settings (OpenAI picks them when you leave them out) |
| `validation_split` | Hold back a share of the examples, e.g. `0.1`, to measure the model on data it didn't train on |
| `system` | A system message added to every example |
| `seed` | Repeatable training |
| `strict` | `false` skips bad examples instead of stopping |
| `dry_run` | Check and write the file only |

**Using the model.** `ai(prompt, {model: "support-bot"})` and `llm("support-bot", prompt)` use the fine-tuned model once training has succeeded; before that they answer that it isn't ready yet. OpenAI's own model ids (`ft:gpt-4.1-mini:…`) work too. `fine_tuned_models()` lists the jobs started from this computer and `cancel_fine_tune(name)` stops one.

For predictions from your own numbers and tables (prices, churn, demand) rather than text, use `train()` and `predict()`, which run scikit-learn models locally ([machine learning](#/reference/builtins)).

## Build an app with the agent team

The agent team writes a whole MCN app from a description, the way a small product team would:

| Agent | Does |
|---|---|
| **Researcher** | Works out what this kind of app needs: users and roles, records and fields, workflows, rules. Searches the web when the domain is specialised |
| **Architect** | Plans the tables, endpoints, screens and navigation, and whether to use SSO and audit logs |
| **Designer** | Lays out each screen: which components, in what order, labels and empty states |
| **Builder** | Writes `backend/main.mcn` and `ui/app.mcn`, checked by MCN's parser. For an app with several areas, one builder per module works at the same time (see below) |
| **QA lead** | Runs the checks, then approves the app or sends a numbered list of fixes back to the builder (at most twice) |

The QA lead's checks: the type checker on both files, a call to every endpoint that needs no inputs (in a scratch copy, so your data isn't touched), and a build of the web app. In Studio it also opens the app's live preview in a real browser, visits every screen, and looks at the screenshots, console errors, failed requests and on-screen errors.

```bash
mcn generate --team "An HR portal: leave requests with manager approval, company SSO, and an audit trail"
mcn generate --team --no-research "A simple inventory tracker" --out ./inventory --build
```

In Studio, open the **Agent** panel (Cmd/Ctrl+L), choose **New app**, describe the app (and attach specs, flowcharts or mockups if you have them), and watch each agent's progress. The browser check needs Playwright: `mcn add browser-qa` (it uses your installed Google Chrome, or `python -m playwright install chromium`).

### Modules built in parallel

When the app has two or more distinct areas (sales, billing, inventory...), the architect splits it into [modules](#/guide/services): which tables each one owns, its endpoints and its screens. Then one builder per module writes it at the same time, each told what the other modules own and offer. The team then:

1. checks each builder's code on its own (it parses, has the screens it was asked for, and has no `app` block or `module` line, which are added for it);
2. puts the files together: each module's code inside its `module` block, ordered so a module comes after the modules it reads from, and the navigation built from every module's screens;
3. checks the modules against each other with the app map: a module writing another module's table, or a screen calling an endpoint nobody built, sends that module (and only that module) back to its builder once;
4. hands the app to QA. The QA lead tags each fix with its module (`[billing] ...`), and those modules are fixed in parallel. Fixes that aren't tied to one module are made to the whole app.

`mcn generate --team` prints a line per module as it's built, and Studio lists them under the Builder. A small app with one area is built by a single builder as before.

The team uses Claude (your `ANTHROPIC_API_KEY`) and makes several calls per app, so it takes a few minutes and costs more than `mcn generate` on its own.

## Seeing what happened

Studio's **AI & RAG Inspector** lists every AI call with its prompt, response, model and duration. That's the quickest way to debug a prompt.

## Mock mode

Without a key:

- `ai`, `llm`, `extract` and `rag` return text starting with `[Claude Mock — set ANTHROPIC_API_KEY to enable]`.
- `classify` returns the first label.
- `agent_run` calls each tool whose name shares a word with the prompt, passing the prompt as its first required argument, so you can test the wiring.
- `vector_search` still works, using the local fallback embeddings.

> **Note** Mock answers are for running code without a key — in class, in CI, offline. Don't judge prompt quality on them.

## Settings

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Enables real AI calls |
| `MCN_AI_MODEL` | Model for `ai()` (default `claude-opus-5-5`) |
| `MCN_CLAUDE_MODEL` | Model for Studio's Copilot and `mcn generate` |
