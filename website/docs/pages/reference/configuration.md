# Configuration

MCN is configured with environment variables. Set them in your shell (`export NAME=value`) or in your deployment.

## AI

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables real AI calls with Claude and lets MCN's agents use Claude. Without any key, AI functions return mock replies |
| `MCN_AI_MODEL` | `claude-opus-5-5` | Model for `ai()`, `classify()`, `extract()` and `rag()` |
| `MCN_CLAUDE_MODEL` | `claude-opus-5-5` | Claude model for MCN's agents (`mcn change`, `mcn generate`, the agent team, Studio's Agent) |
| `MCN_AGENT_PROVIDER` | the key you have | Which model provider MCN's agents use: `anthropic`, `openai`, `gemini`, `openrouter`, `ollama` or `compatible` (config: `ai_provider`). See [choosing the model](#/guide/ai-agents) |
| `MCN_AGENT_MODEL` | the provider's | The agents' model name (config: `ai_model`) |
| `MCN_AGENT_BASE_URL` | — | An OpenAI-compatible server for the agents (config: `ai_base_url`) |
| `GEMINI_API_KEY`, `OPENROUTER_API_KEY` | — | Let the agents use Gemini or OpenRouter |
| `OPENAI_API_KEY` | — | Use OpenAI embeddings for `embed()` and vector search, and lets MCN's agents use OpenAI |
| `OLLAMA_URL` | — | Use a local Ollama server for embeddings |

## Developer Club

| Variable | Default | Effect |
|---|---|---|
| `MCN_CLUB_SIGNATORY` | — | `Name|Title` printed as the signature on [Developer Club](#/guide/developer-club) certificates |

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
| `MCN_APP_AUDIT_LOG` | `~/.mcn/audit/app_audit.jsonl` | File used by `audit_log()` and `audit` services |
| `MCN_AUDIT_WEBHOOK` | — | Also post each audit entry, as an OCSF event, to this URL (a SIEM or log collector) |
| `MCN_AUDIT_WEBHOOK_TOKEN` | — | Bearer token for `MCN_AUDIT_WEBHOOK` |
| `MCN_SSO_ISSUER` | — | The identity provider's issuer URL, for `auth "sso"` |
| `MCN_SSO_CLIENT_ID` | — | The app's client ID at the identity provider |
| `MCN_SSO_CLIENT_SECRET` | — | The client secret (omit for public clients) |
| `MCN_SSO_REDIRECT_URL` | `<server>/_auth/callback` | The callback URL registered with the provider (set it behind a proxy) |
| `MCN_SSO_SCOPES` | `openid email profile` | Scopes to ask for |
| `MCN_SSO_ALLOWED_DOMAINS` | — | Comma-separated email domains allowed to sign in |
| `MCN_SSO_ROLES_CLAIM` | `roles`, then `groups` | ID token claim that becomes `current_user().roles` |
| `MCN_SSO_SESSION_HOURS` | `8` | How long a sign-in lasts |
| `MCN_SSO_RETURN_ORIGINS` | — | Extra origins sign-in may send people back to |

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
| `MCN_DEPLOY_SOURCE` | MCN on GitHub | Where deployments install MCN from (a URL, or a local checkout for testing unreleased changes) |
| `AWS_REGION` | `us-east-1` | Region for `mcn deploy --target aws` when `--region` isn't given |
| `CLOUDFLARE_API_TOKEN` | — | Lets `mcn deploy --target cloudflare` deploy without logging in |

## Studio

| Variable | Default | Effect |
|---|---|---|
| `MCN_WORKSPACE` | `~/.mcn/playground` | Folder Studio edits (set by `mcn studio <folder>`) |
| `MCN_PLAYGROUND_PORT` | `5003` | Port (set by `mcn studio --port`) |
| `MCN_PLAYGROUND_HOST` | `127.0.0.1` | Interface to bind. Anything other than localhost exposes code execution to the network |
| `MCN_PLAYGROUND_ALLOWED_ORIGINS` | — | Extra comma-separated origins allowed to call Studio's API |
| `MCN_BACKEND_PORT` | `8080` | Port for the backend Studio runs for **Preview**, when 8080 is taken by something else |
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
