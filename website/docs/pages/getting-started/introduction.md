# Introduction

MCN is a language for building complete applications: database, HTTP API and web UI, from one or two short files. AI is a built-in function, errors explain how to fix themselves, and a browser IDE comes with it.

```mcn
query("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT)")

service notes_api
    port 8080

    endpoint add_note(text)
        query("INSERT INTO notes (text) VALUES (?)", (text,))
        return {success: true, summary: ai("Summarise in five words: " + text)}

    endpoint list_notes()
        return {success: true, data: query("SELECT * FROM notes")}
```

That file is a running API: `mcn serve` turns each `endpoint` into a GET and POST route, and the same endpoints can be called directly from MCN UI components, which compile to React.

## What you can build

- **Internal tools:** CRMs, admin panels, approval flows and dashboards, without separate frontend and backend codebases.
- **APIs and automations:** HTTP services, data pipelines, scheduled jobs and IoT handlers.
- **AI features:** classification, extraction, summaries and retrieval-augmented answers, each a single function call.
- **Coursework:** a first program on day one and a full-stack app with AI by the second session.

## How it fits together

| You write | MCN gives you |
|---|---|
| `backend/main.mcn`: tables, a `service`, `test` blocks | An HTTP API (`mcn serve`) with interactive docs |
| `ui/app.mcn`: `component`s and an `app` layout | A React + Tailwind + shadcn/ui project (`mcn build`) |
| Anything | Clear errors from `mcn run`, `mcn check`, Studio and VS Code |

## Where to go next

<!-- cards -->
- [Installation](#/getting-started/installation) Install MCN with one command.
- [Quick start](#/getting-started/quick-start) Create, test and run a full-stack app in a few minutes.
- [Language basics](#/guide/language-basics) Variables, decisions, loops and functions.
- [CLI reference](#/reference/cli) Every `mcn` command.
