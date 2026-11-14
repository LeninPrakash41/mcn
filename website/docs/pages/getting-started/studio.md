# MCN Studio

Studio is a browser IDE for MCN: an editor, a live preview of the web and mobile app, and inspectors for the database, IoT devices and AI calls. It runs on your machine and only accepts connections from it.

```bash
mcn studio .          # open the project in the current folder
mcn studio            # open Studio's own scratch workspace (~/.mcn/playground)
mcn studio . --port 5010
```

Then open **http://localhost:5003** (or the port you chose).

> **Note** Opened on a project folder, Studio edits your files in place. Templates are disabled there so they can't overwrite your code; run `mcn studio` without a folder to try them.

## The layout

| Area | What it does |
|---|---|
| **Activity bar** (far left) | Switch between the web project and the mobile **App** view, or open the **Templates** gallery. In the App view, **App Preview** builds the Flutter app from `ui/app.mcn` and runs it in a phone frame |
| **Explorer** | Your files: `backend/main.mcn`, `ui/app.mcn`, `mobile/`, `scripts/` |
| **Editor** | Monaco (the VS Code editor) with MCN highlighting. Errors from the last run are underlined in red |
| **Right panel** | **Agent** (a chat, see below), **Preview** (the web app built from `ui/app.mcn`, talking to your running backend), **Mobile**, **REPL**, **Database**, **IoT**, **AI calls**, **Terminal** and **Build**. Cmd/Ctrl+B hides it |
| **Bottom panel** | Run output, the terminal and error details |

## Run, preview, build

1. **Run** (▶) executes the current file. For `backend/main.mcn` this starts the API on its `port`.
2. **Preview** compiles `ui/app.mcn` and runs the real app in the preview pane, using the same components as the exported React app and calling your running backend. Nothing needs installing.
3. **Build & download** produces a zip of the React project with a Dockerfile, `docker-compose.yml`, an nginx config and a CI workflow. In the App view, **Export Flutter Package** produces the Flutter project with the backend and its Docker files instead. **Build → Deploy** puts the web app and its API on Vercel and gives you the live link ([deploying](#/guide/deploy)).

## Inspectors

- **Database:** browse tables and run SQL against the same SQLite database your code uses.
- **IoT Simulator:** a live view of every device: from scripts you **Run**, and from your backend while **Preview** is running. Drag a sensor's slider, trigger a motion sensor or flip a relay, and the running app reacts; the log shows each command. Devices declared for a Raspberry Pi or Arduino are simulated here, with their pins shown. See [IoT and hardware](#/guide/iot).
- **AI calls:** every `ai`, `classify`, `extract`, `embed`, `rag` and vector search call, with the prompt, response, model and timing.
- **API Docs** (Tools menu): Swagger documentation for the endpoints in your backend.

## Templates

The **Templates** gallery (the **Templates** button in the left bar, or **Templates → Browse all templates**) has 27 starter apps you can search and filter: AI and automation (AI agent builder, voice agents on Twilio, workflow automation, operations dashboard), business apps (CRM, sales hub, analytics, inventory, construction, prompt marketplace), data and ML (data labeling studio, ML training lab), mobile apps (smart home, expense tracker, field inspection), backends (REST service, telemetry hub, AI prompt router) and short scripts for learning. Every template is run and built in CI.

## Agent

The **Agent** tab (the **Agent** button, or Cmd/Ctrl+L) is a chat beside your code with three modes:

| Mode | What it does |
|---|---|
| **Change** | Describe a change. The agent reads your app, makes the change as a checked patch, validates and tests it, and shows the summary, what it affects, the test results and the diff. Nothing is written until you click **Apply change** ([the agent interface](#/guide/ai-agents)) |
| **Ask** | Ask about your app ("which endpoints have no tests?"). The agent looks at the real code to answer and changes nothing |
| **New app** | Describe an app and the [agent team](#/guide/ai) researches, plans, builds and tests it in this workspace |

It uses your Claude key from `mcn config set api_key ...` or `ANTHROPIC_API_KEY`; if there's none, it asks for one and keeps it only for that session. Without a key, Studio and the AI functions still work: AI calls return labelled mock replies.

## Feedback

The speech-bubble button sends a bug report. Tick **attach logs** to include the run output. Reports are saved locally in `~/.mcn/telemetry_outbox.jsonl` and delivered when `MCN_FEEDBACK_ENDPOINT` is set.
