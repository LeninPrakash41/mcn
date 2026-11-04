# Introduction

MCN is a language for building complete applications: database, HTTP API, web and mobile UI, AI agents and the devices an app controls, from a few short files. AI is a built-in function, errors explain how to fix themselves, and a browser IDE comes with it.

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

That file is a running API: `mcn serve` turns each `endpoint` into a GET and POST route, and the same endpoints can be called directly from MCN UI components, which compile to React and Flutter.

## What kind of language is MCN?

MCN is a **high-level, interpreted scripting language with dynamic typing**, designed for building applications. In more detail:

| | What it means for you |
|---|---|
| **Scripting language** | A program is a plain `.mcn` text file. You write statements from top to bottom; there's no `main` function, class or boilerplate to start with |
| **Interpreted** | `mcn run app.mcn` runs your code straight away, with no compile step. `mcn repl` lets you try one line at a time |
| **Dynamically typed** | Variables hold any kind of value and you don't declare types. You can add optional type hints, `var age: int = 18`, and `mcn check` reports values that don't match before you run |
| **Indentation-based** | Blocks (`if`, `for`, `function`, `service`…) are marked by indenting 4 spaces. No braces or semicolons |
| **Multi-paradigm** | Mostly step-by-step (imperative) code with functions. Functions are values too, so `map(prices, p => p * 2)` works. Apps are described declaratively, with `service`, `component`, `app` and `test` blocks |
| **Garbage-collected** | Memory is managed for you |
| **Application-focused** | The things apps need are part of the language: `query()` for the database, `service` for APIs, `component` for UIs, `ai()` and `agent_run()` for AI, `device()` for hardware, `test` blocks for testing |

Its values are numbers, text, `true`/`false`, `null`, lists (`[1, 2, 3]`), objects (`{name: "Ana", age: 20}`) and functions. Errors are handled with `try` / `catch` / `throw`, background work with `task` and `await`, and events with `on` and `trigger`.

Where MCN fits:

- **Like other scripting languages**, it's quick to start: write a line, run it, see the result.
- **Unlike general-purpose languages**, you don't pick and wire up frameworks for the web server, database, UI, AI and testing. They're built in, so a beginner's second program can be a working app.
- **It isn't a low-code tool.** Everything is code you can read, test, review and keep in Git. The UI compiles to standard React and Flutter projects that you own.

## What you can build

- **Internal tools:** CRMs, admin panels, approval flows and dashboards, without separate frontend and backend codebases.
- **Web and mobile apps:** one UI file becomes a React web app and a Flutter phone app.
- **APIs and automations:** HTTP services, data pipelines and scheduled jobs.
- **AI features and agents:** classification, extraction, summaries, retrieval-augmented answers, and agents that call your own functions as tools.
- **IoT projects:** Raspberry Pi and Arduino apps, simulated in Studio until the hardware is ready.
- **Coursework:** a first program on day one and a full-stack app with AI by the second session.

## How it fits together

| You write | MCN gives you |
|---|---|
| `backend/main.mcn`: tables, a `service`, `test` blocks | An HTTP API (`mcn serve`) with interactive docs |
| `ui/app.mcn`: `component`s and an `app` layout | A React + Tailwind project (`mcn build`) and a Flutter app (Studio's **App** view) |
| `device(...)` calls | Devices simulated in Studio, real on a Raspberry Pi or Arduino |
| `mcn deploy --target vercel` | Your web app and API online at one URL |
| Anything | Clear errors from `mcn run`, `mcn check`, Studio and VS Code |

## Where to go next

<!-- cards -->
- [Installation](#/getting-started/installation) Install MCN with one command.
- [Quick start](#/getting-started/quick-start) Create, test and run a full-stack app in a few minutes.
- [Language basics](#/guide/language-basics) Variables, decisions, loops and functions.
- [CLI reference](#/reference/cli) Every `mcn` command.
