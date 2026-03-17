# MCN Web Playground

A browser-based IDE for writing, running, building, and testing MCN scripts — no local install needed.

## Start

```bash
cd mcn/web-playground
python server.py
# → http://localhost:7842
```

## What it does

| Feature | How |
|---|---|
| Write and run MCN | Monaco editor + ▶ Run button |
| Format code | ⌥ Format button → `/api/format` |
| Type-check | ✓ Check button → `/api/check` |
| Run tests | ⚗ Test button → `/api/test` |
| Build React app | Build button → `/api/build` (MCN → Vite project) |
| Launch preview | Launch Preview → starts Vite dev server + MCN backend |
| Load example projects | Dropdown — multi-file project templates reset the workspace |

## Server API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve the IDE HTML |
| `GET` | `/api/examples` | All example snippets and project templates |
| `GET` | `/api/workspace/files` | List files in current workspace |
| `GET` | `/api/workspace/file?path=...` | Read a workspace file |
| `POST` | `/api/workspace/file` | Save a workspace file |
| `POST` | `/api/workspace/reset` | Wipe workspace and seed new files |
| `POST` | `/api/execute` | Run MCN code, stream logs |
| `POST` | `/api/format` | Format MCN code → `{formatted}` |
| `POST` | `/api/check` | Type-check → `{ok, errors, warnings}` |
| `POST` | `/api/test` | Run test blocks → `{passed, failed, output}` |
| `POST` | `/api/build` | Compile UI to React project |
| `GET` | `/api/frontend/file?path=...` | Read generated frontend file |
| `POST` | `/api/devserver/start` | Start Vite + MCN backend |
| `POST` | `/api/devserver/stop` | Stop both servers |
| `GET` | `/api/health` | Liveness check |

## Workspace layout

```
~/.mcn/playground/
  backend/
    main.mcn        MCN service / backend logic
  ui/
    app.mcn         MCN component / app declarations
  frontend/         Generated React project (after mcn build)
    src/
    package.json
    vite.config.ts
```

## Planned improvements

- Inline error squiggles (diagnostics markers via `/api/check`)
- Split editor / preview pane
- Git integration (commit, diff)
- One-click cloud deploy
