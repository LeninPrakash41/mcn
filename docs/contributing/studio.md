# Studio server

Studio is a Flask app (`mcn/web-playground/server.py`) serving a single-page IDE (`index.html` with Monaco) and a JSON API. `mcn studio` starts it in a subprocess with `MCN_PLAYGROUND_PORT`, `MCN_PLAYGROUND_HOST` and, for a project folder, `MCN_WORKSPACE`.

## Blueprints

`server.py` creates the app, installs the security guards and registers the blueprints listed in `playground_server/__init__.py`:

| Module | Routes |
|---|---|
| `site.py` | The IDE page, this website under `/website`, `/api/health` |
| `workspace.py` | List, read, save files; reset the workspace to a template |
| `execute.py` | Run MCN code; returns output and a `diagnostic` on error |
| `build.py` | Build React or Flutter, download a zip with deployment files |
| `devserver.py` | Start and stop the backend and the preview dev server |
| `simulators.py` | DB explorer, IoT simulator, AI trace |
| `agent.py` | Copilot and app generation (Claude) |
| `api_docs.py` | OpenAPI/Swagger for the workspace backend |
| `examples.py` | The 18 templates, loaded from `playground_server/templates/` |
| `auth.py`, `community.py`, `secrets_api.py`, `git_api.py` | Accounts, feedback/telemetry, secrets, git |

`core.py` holds shared state and helpers: `_request_workspace()` (the folder for the current request, per user when signed in), `_safe_path()` (rejects paths outside the workspace), and process management.

## Security model

Studio runs code, so it is locked to the local machine:

- It binds to `127.0.0.1` by default and warns loudly for any other host.
- Requests whose `Host` isn't a loopback name are rejected (DNS rebinding).
- Cross-origin requests are rejected unless the origin is loopback or listed in `MCN_PLAYGROUND_ALLOWED_ORIGINS`.
- File APIs resolve paths inside the workspace only.
- With a project folder (`MCN_WORKSPACE`), templates can't reset the workspace and generated-folder clean-up is skipped, so Studio never deletes your files.

## Front end

`index.html` is the shell; behaviour lives in `static/js/`:

| File | Responsibility |
|---|---|
| `editor.js` | Monaco setup, MCN language definition |
| `workspace.js` | File tree, tabs, save, run, error markers |
| `build.js` | Build, preview, download |
| `tools.js` | DB explorer, AI inspector, API docs |
| `mobile-simulator.js` | The App view |
| `ai.js` | Copilot |
| `community.js`, `si-wizard.js`, `ui-kit.js` | Feedback, package wizard, shared UI helpers |

Styles are in `static/css/studio.css` and the JetBrains-style theme in `theme-jetbrains.css`.

## Templates

Each template is a folder in `playground_server/templates/<id>/` with real `.mcn` files (and a mobile manifest for mobile templates), described in `templates/index.json`. Adding a folder and an index entry adds a template; `tests/test_templates_e2e.py` picks it up automatically.
