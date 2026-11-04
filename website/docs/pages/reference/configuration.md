# Configuration

MCN is configured with environment variables. Set them in your shell (`export NAME=value`) or in your deployment.

## AI

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables real AI calls, Studio's Copilot and `mcn generate`. Without it, AI functions return mock replies |
| `MCN_AI_MODEL` | `claude-opus-5-5` | Model for `ai()`, `classify()`, `extract()` and `rag()` |
| `MCN_CLAUDE_MODEL` | `claude-opus-5-5` | Model for the Copilot and `mcn generate` |
| `OPENAI_API_KEY` | — | Use OpenAI embeddings for `embed()` and vector search |
| `OLLAMA_URL` | — | Use a local Ollama server for embeddings |

## Runtime

| Variable | Default | Effect |
|---|---|---|
| `MCN_HOME` | `~/.mcn` | Where MCN keeps its logs, package metadata, settings and Studio's workspace |
| `MCN_HTTP_TIMEOUT` | 5s connect, 30s read | Seconds before `trigger()` gives up on a request |
| `MCN_VERBOSE` | off | Print the engine's debug log |
| `MCN_MAX_STEPS` | `5000000` | Statements one run, request, `watch` handler or test may execute before it's stopped (catches runaway loops) |
| `MCN_AUDIT_LOG` | `~/.mcn/audit/hipaa_audit.jsonl` | File used by `healthcare`'s `hipaa_audit_log()` |

## Security

| Variable | Default | Effect |
|---|---|---|
| `MCN_AUTH_SECRET` | random, saved in `~/.mcn/auth_secret` | Secret that signs tokens (`jwt_sign`, `auth_create_token`). Set the same value on every server |
| `MCN_API_TOKEN` | — | Token callers send to services with `auth "token"`. Unset means those endpoints are closed |
| `MCN_CORS_ORIGINS` | `*` | Comma-separated sites allowed to call your API from a browser |
| `MCN_RATE_LIMIT` | `600` | Requests per minute per client. `0` turns it off |
| `MCN_MAX_BODY_BYTES` | `1048576` | Largest request body accepted |
| `MCN_APP_AUDIT_LOG` | `~/.mcn/audit/app_audit.jsonl` | File used by `audit_log()` |

## IoT

| Variable | Default | Effect |
|---|---|---|
| `MCN_IOT_SIMULATE` | not set (Studio: `1`) | `1` simulates every device; `0` requires the hardware; unset uses hardware when it's there and simulates otherwise |
| `MCN_MQTT_URL` | `mqtt://localhost:1883` | Broker for `driver: "mqtt"` devices that don't set `broker` |
| `MCN_MQTT_USER` / `MCN_MQTT_PASSWORD` | — | Broker login |

## Deploying

| Variable | Default | Effect |
|---|---|---|
| `VERCEL_TOKEN` | — | Lets Studio (and `mcn deploy --target vercel` without logging in) deploy to Vercel. Create one at vercel.com/account/tokens |
| `MCN_DEPLOY_SOURCE` | MCN on GitHub | Where a Vercel deployment installs MCN from |

## Studio

| Variable | Default | Effect |
|---|---|---|
| `MCN_WORKSPACE` | `~/.mcn/playground` | Folder Studio edits (set by `mcn studio <folder>`) |
| `MCN_PLAYGROUND_PORT` | `5003` | Port (set by `mcn studio --port`) |
| `MCN_PLAYGROUND_HOST` | `127.0.0.1` | Interface to bind. Anything other than localhost exposes code execution to the network |
| `MCN_PLAYGROUND_ALLOWED_ORIGINS` | — | Extra comma-separated origins allowed to call Studio's API |
| `MCN_FEEDBACK_ENDPOINT` | — | Where Studio's feedback reports are delivered |

## Generated apps

| Variable | Default | Effect |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8080` | API base URL for the React app from `mcn build` |
| `VITE_API_TOKEN` | — | Bearer token the React app sends (a token in `localStorage` key `mcn_token` wins) |
| `MCN_API_URL` | `http://localhost:8080` | API base URL for the Flutter app (`flutter run --dart-define=MCN_API_URL=...`) |
| `MCN_API_TOKEN` (Flutter) | — | Bearer token the Flutter app sends (`--dart-define=MCN_API_TOKEN=...`) |

## Files MCN creates

| File | Where | What |
|---|---|---|
| `mcn_data.db` | The folder you run from | Your app's SQLite database |
| `mcn_packages/` | The project | Packages installed with `mcn install --path` |
| `~/.mcn/logs/` | Home | MCN's own logs |
| `~/.mcn/playground/` | Home | Studio's scratch workspace |
