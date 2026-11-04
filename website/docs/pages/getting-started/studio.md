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
| **Activity bar** (far left) | Switch between the web project and the mobile **App** view |
| **Explorer** | Your files: `backend/main.mcn`, `ui/app.mcn`, `mobile/`, `scripts/` |
| **Editor** | Monaco (the VS Code editor) with MCN highlighting. Errors from the last run are underlined in red |
| **Preview** | The web app built from `ui/app.mcn`, talking to your running backend |
| **Bottom panel** | Run output, the terminal and error details |

## Run, preview, build

1. **Run** (▶) executes the current file. For `backend/main.mcn` this starts the API on its `port`.
2. **Preview** compiles `ui/app.mcn` and runs the real app in the preview pane, using the same components as the exported React app and calling your running backend. Nothing needs installing.
3. **Build & download** produces a zip of the React project (or the Flutter app in the App view) with a Dockerfile, `docker-compose.yml` and a CI workflow. **Build → Deploy** puts the web app and its API on Vercel and gives you the live link ([deploying](#/guide/deploy)).

## Inspectors

- **DB Explorer:** browse tables and run SQL against the same SQLite database your code uses.
- **IoT Simulator:** a live view of every device: from scripts you **Run**, and from your backend while **Preview** is running. Drag a sensor's slider, trigger a motion sensor or flip a relay, and the running app reacts; the log shows each command. Devices declared for a Raspberry Pi or Arduino are simulated here, with their pins shown. See [IoT and hardware](#/guide/iot).
- **AI & RAG Inspector:** every `ai`, `classify`, `extract`, `embed`, `rag` and vector search call, with the prompt, response, model and timing.
- **API Docs** (Tools menu): Swagger documentation for the endpoints in your backend.

## Templates

The **Templates** gallery (the **Templates** button in the left bar, or **Templates → Browse all templates**) has 23 starter apps you can search and filter: AI and automation (AI agent builder, workflow automation, operations dashboard), business apps (CRM, sales hub, analytics, inventory, construction, prompt marketplace), data and ML (data labeling studio, ML training lab), mobile apps (smart home, expense tracker, field inspection), backends (REST service, telemetry hub, AI prompt router) and short scripts for learning. Every template is run and built in CI.

## Copilot

With `ANTHROPIC_API_KEY` set, the Copilot panel answers questions about your code and can write MCN for you. Without a key, Studio and the AI functions still work: AI calls return labelled mock replies.

## Feedback

The speech-bubble button sends a bug report. Tick **attach logs** to include the run output. Reports are saved locally in `~/.mcn/telemetry_outbox.jsonl` and delivered when `MCN_FEEDBACK_ENDPOINT` is set.
