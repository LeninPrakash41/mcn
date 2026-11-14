# Changelog

All notable changes to MCN will be documented in this file.

## [Unreleased]

### Added
- **`mcn describe`**: a map of the app read from source (tables, services, endpoints with auth and the tables they read and write, functions, contracts, workflows, tests, screens, navigation) with the edges between them, as text or `--json`; it reports calls to missing endpoints (including a table screen's generated create/update/delete calls), navigation to missing screens, SQL on undefined tables, and unused endpoints. `--strict` for CI
- **`mcn impact`**: what changing a table, endpoint, function, contract or screen affects (by name, `kind:name`, `file:line`, or `--changed` from git), and which tests cover it
- The agent team's QA lead gets the map's issues, and after each fix, what changed and what that affects
- **Typed endpoint parameters**: `endpoint add(customer: str, amount: float, who: Customer)`. Every call is checked before the endpoint runs (text like `"42"` is accepted for an `int`); wrong or missing values get a 400 naming the parameter. Contracts work as types. The type checker uses the types inside the endpoint and reports unknown types; `mcn check --strict` requires a type on every endpoint parameter. The map shows them
- **Modules**: `module billing` / `owns invoices` blocks. Their code runs as if written at the top level; `mcn describe` reports code that writes another module's table and tables owned twice, and lists each module's members and the modules it depends on. `mcn impact` names the modules a change reaches, takes a module as a target, and `--module NAME` exits with code 1 when a change goes outside that module, so several agents can work on one app at once
- Table screens offer only the actions the backend has: **New**, **Edit** and **Delete** appear when `create_`/`update_`/`delete_<item>` exists and the table's columns supply its parameters, and show the server's error if one fails. Before, every table showed all three, even when the endpoints didn't exist
- The Construction template has full create, edit and delete on every table (new `update_*`, `delete_procurement`, `update_approval`, `delete_approval` endpoints) and typed endpoints that pass `mcn check --strict`
- Fixed: table screens guessed endpoint names with bad plurals (`ResourcesTable` called `create_resourc`); they now prefer the backend's real endpoint names
- **No more simulated AI features**: `agent("think", …)` calls the model with the agent's role, conversation memory and tools (via `agent_run`), and coordinators combine their sub-agents' real answers; pipeline `ai_classify`/`ai_extract` use `classify()`/`extract()` (per item for lists, function steps, unknown steps are errors); `datasource()` reads files, PDFs and web pages and answers from the most relevant passages with `rag()`; `translate()` has AI write MCN and checks it with the parser (offline patterns now produce today's syntax, and `use "natural"` runs code in the program's scope); `use "workflows"` steps run the functions they name, with retries; `use "integrations"` syncs Salesforce through its REST API and any HubSpot object; unknown `agent`/`pipeline`/`datasource` operations explain the valid ones instead of returning "simulated"
- Removed fake model catalogs and dead simulated modules (`mcn_ai_models.py`, `mcn_cli_enhanced.py`, the runtime's unused AI helpers)
- **Real fine-tuning**: `fine_tune(base_model, data, name, options)` checks and converts examples (CSV, JSON, JSONL or an MCN list) to chat format, uploads them and starts a job on OpenAI's fine-tuning API; `get_training_status(name)`, `cancel_fine_tune(name)` and `fine_tuned_models()`; `ai()` and `llm()` use the model by name once it's trained. Replaces a simulation that never trained anything. `use "ai_v3"`'s `train` and `run` now call the real code
- **Single sign-on for services**: `auth "sso"` signs people in with Okta, Microsoft Entra ID, Google Workspace, Auth0, Keycloak or any OpenID Connect provider (PKCE, nonce, signature, issuer and audience checks; no server-side state, so it works on serverless hosts). `current_user()` has `sub`, `email`, `name` and `roles`; the generated web app redirects to sign-in and keeps the session token. `mcn add sso`
- **Automatic audit logs**: `audit` in a service logs every call (actor, endpoint, masked arguments, status, duration, IP) to the tamper-evident log; `mcn audit-log verify` and `mcn audit-log export --format ocsf|jsonl|csv`; `MCN_AUDIT_WEBHOOK` streams OCSF events to a SIEM. The audit log now reads only its last entry per write
- **Deploy to AWS and Cloudflare**: `mcn deploy --target aws [--region]` runs one container (web app at `/`, API at `/api`) on AWS App Runner in your account; `--target cloudflare` serves the web app from Cloudflare and runs the API in a Cloudflare container. `MCN_DEPLOY_SOURCE` can point at a local checkout
- **The agent team**: `mcn generate --team` and Studio's Generate dialog run a researcher (with web search), architect, designer, builder and QA lead. QA type-checks, calls every endpoint, builds the web app and, in Studio, opens every screen in headless Chrome (`mcn add browser-qa`), then sends fixes back to the builder up to twice
- Landing page: an "own your software" section with a tool-stack cost estimator, what every MCN app comes with, and FAQ entries on AI app builders, SSO and audit logs, and AWS/Cloudflare deploys
- Hosted Studio limits sign-in attempts (per account and per network address), sign-ups, sign-in code requests and wrong codes, answering 429 with `Retry-After`; `MCN_TRUST_PROXY=1` behind a reverse proxy
- The admin panel shows the installed MCN version instead of a fixed "3.0.0"; removed the unused `static/js/admin.js`
- **Generated code you'd commit**: `mcn build` and Studio's App view produce typed, lint-clean, formatted and tested projects
  - React: state typed from its starting value and from backend tables (`Order[]` from `SELECT * FROM orders`), `BackendValue` instead of `any`, a typed API client, and screens using kit components such as `<Stat>`
  - Each screen shows a loading bar and load errors with Retry; failed actions show an error notification; independent backend calls run in parallel (`Promise.all` / `Future.wait`)
  - React projects include ESLint, Prettier and Vitest with a smoke test per screen (`npm run lint`, `format`, `test`, `typecheck`); output is Prettier-formatted once dependencies are installed
  - Flutter: typed state fields, `flutter_lints` with no blanket ignore list, `dart format`, and a widget smoke test per screen
  - UI kit: no `any`, lint-clean and Prettier-formatted; new `LoadStatus`, richer `Stat` (icon, tone, change), `Badge` variants
- `MCN_BACKEND_PORT` moves Studio's preview backend off 8080
- **Accounts across installs**: installed Studio has no accounts of its own; hosted Studio (`mcn studio --hosted`, `MCN_STUDIO_MODE=hosted`) requires sign-in, gives each person a workspace and is the account server for installed copies
  - Installed Studio's **Sign In** and `mcn login` / `mcn whoami` / `mcn logout` sign in through the browser with a device code; the token stays in `~/.mcn/credentials.json`
  - Admins see each user's signed-in computers at `/admin` and can sign them out; `MCN_ADMIN_EMAILS` makes the first admins, `MCN_STUDIO_SIGNUP_DOMAINS` limits sign-up
  - Admin pages escape user-supplied text, and sign-up checks the email address
- **MCN UI kit** (`mcn/ui-kit/react`): one component library for exported apps and Studio's preview
  - App frame: collapsible sidebar with groups, mobile drawer, breadcrumb, ⌘K search, notification bell, dark mode, footer
  - `data_table` (search, column filters, sorting, pagination, table/grid/list views, CSV export, row actions), `kanban`
  - SVG charts: `bar_chart` (multi-series, stacked), `line_chart`, `area_chart`, `pie_chart`, `donut_chart`, `sparkline`
  - `chat` / `chat_widget`, `agent_builder`, `workflow_builder`, `breadcrumb`, `empty_state`, `notify()`
  - `app` blocks take `footer` and `logo`; `nav` items take `group`
- **Live preview**: Studio runs the actual compiled app in the browser with the kit, against the running backend (it used to show an approximation with sample data)
- Templates: Operations Dashboard, AI Agent Builder, Workflow Automation, Data Labeling Studio, ML Training Lab (23 in total)
- **`agent_run(prompt, options)`**: Claude calls MCN functions as tools. Parameters become the tool schema; MCN runs the loop and returns `{reply, tool_calls, steps}`. The AI Agent Builder template's tools (search docs, look up customers, create tasks, draft emails, notify the team) now really run, and `chat` shows the tools used under each reply
- **Mobile apps compiled from MCN components**: `ui/app.mcn` compiles to Flutter screens with state, handlers, endpoint calls and navigation, instead of a separate screen manifest
- `kanban` cards move by touch (drag the grip) and keyboard (← →), with screen-reader announcements
- **Template gallery** in Studio: a searchable, categorized gallery from the left bar, the Templates menu and the welcome screen, shown once to newcomers
- Flutter apps are native Material 3: bottom navigation (rail on tablets, drawer beyond five sections), a page history per tab with back navigation, collapsing large titles, pull to refresh, list rows that open detail pages and swipe to delete, kanban columns that snap per screen, adaptive switches and dialogs, haptics, the web kit's Lucide icons and fl_chart charts. Needs Flutter 3.27 or newer
- Studio's App view runs the real Flutter app in the phone frame (built for the web from `ui/app.mcn` when Flutter is installed, the components at phone size otherwise), replacing hard-coded mock screens
- Studio's file explorer shows nested folders (`frontend/src/components/ui`) instead of a flat list
- **Deploy to Vercel**: `mcn deploy --target vercel [--prod]` and Studio's **Build → Deploy** put the React app and its backend (at `/api`) online at one URL; settings come from `.env`, with a stable `MCN_AUTH_SECRET`
- **IoT hardware**: the same `device()` code is simulated in Studio and drives real hardware
  - Drivers: `gpio` (Raspberry Pi pins, DHT sensors, MCP3008), `serial` (Arduino, ESP32, Pico over USB), `mqtt` (ESP32, Tasmota, Zigbee2MQTT, Home Assistant) and `http`
  - 28 device types; `on`, `off`, `toggle`, `write`, `watch`, `list` and `remove`
  - `mcn iot firmware arduino|esp32` writes board firmware; `mcn iot ports`; `mcn iot service` starts an app when a Pi boots; `mcn add iot`
  - `MCN_IOT_SIMULATE`: simulate, require hardware, or fall back to simulation
  - Studio's IoT Simulator updates live, controls every device type, and shows and drives the devices of the running backend
  - Smart Home template rebuilt on real devices and automations; Telemetry Hub takes readings over HTTP and MQTT and sounds an Arduino alarm
- **Security**
  - `auth "token" | "jwt"` and `public ...` in services; `current_user()` in endpoints
  - Check functions: `validate`, `escape_html`, `sanitize_html`, `is_email`, `is_url`, `password_strength`, `rate_limit`, `require`, `secure_token`, `safe_equals`, `mask`, `audit_log`, `verify_audit_log`
  - `mcn audit`: finds SQL injection, hard-coded secrets, request-controlled file paths and URLs, weak password hashing, open services and plain-http URLs
  - Servers send security headers, rate-limit (`MCN_RATE_LIMIT`), cap body size (`MCN_MAX_BODY_BYTES`) and restrict CORS with `MCN_CORS_ORIGINS`
  - Generated React and Flutter apps and Studio's preview send a bearer token

### Fixed
- Exported apps read `.data` from an unresolved promise (`items = list_tasks().data` left lists empty)
- State read right after an assignment in a handler saw the old value
- Endpoint calls with literal arguments sent `arg0` instead of the parameter name (the backend is now consulted)
- A handler named after a JavaScript keyword (`on delete`) produced invalid code
- `a or b` was typed as a boolean by `mcn check`
- UI attributes can use keyword names (`chat endpoint=ask`)
- **Security:** the built-in HTTP server let requests call any function, including built-ins such as `query` and `write_file`; only declared endpoints are reachable now
- **Security:** tokens were signed with a built-in default secret when `MCN_AUTH_SECRET` wasn't set; each install now generates its own
- The IoT Simulator didn't show the devices of a running backend, and the IoT templates didn't use `device()`
- Pressing Run reset the IoT Simulator's demo devices, and running a script again doubled its `watch` handlers
- Studio's deploy dialog couldn't be opened from any menu
- **Servers stopped answering after about 100 requests**: the statement limit was shared by every request for the life of the process. Each run, request, `watch` handler and test now gets its own budget (default 5 million statements, `MCN_MAX_STEPS`)
- **Export Flutter Package** downloaded the React project; it now holds the Flutter app, the backend and its Docker files, and a README
- The App view hid `ui/app.mcn`, the source of the Flutter app, and kept writing a stale `ui-manifest.json`
- MCN's internal databases (`mcn_auth.db` and others) were created in the project folder; they're in `~/.mcn/data` now
- Flutter stat cards broke words on narrow phones
- Studio's backend wrote its database outside the workspace, so DB Explorer showed different data
- `log`, `str`, `+` and `{interpolation}` printed `True`, `None` and `{'a': None}`; they now print `true`, `null` and `{a: null}`, as MCN writes them
- The Flutter runtime and board firmware were missing from installed packages
- Docs pages could show a stale copy after an update (the build now versions its files)
- **Security:** serving a file without a `service` ran the whole script per request and returned its variables; it now serves nothing

### Changed
- Generated React apps depend only on React: the kit replaces recharts, sonner, lucide-react, react-router, clsx and tailwind-merge

## [2.4.0] - 2026-11-03

### Added
- `mcn init` creates a working full-stack project (backend with tests, UI, README, `mcn.json`); `mcn validate` checks every `.mcn` file in it
- `mcn studio [folder]` opens a project folder in Studio; `mcn vscode` installs the bundled VS Code extension
- `mcn check` reports syntax errors and names that are never defined (with "Did you mean" hints), and `--json` output for editors and CI
- VS Code extension: language server packaged inside it, errors underlined as you type, `Generate App with AI` runs `mcn generate`
- `mcn serve file.mcn`: GET and POST for every endpoint, port taken from the service, `GET /` route list, `--postman` opt-in
- `sleep(seconds)` and `now_ms()` built-ins; built-ins callable as methods (`text.contains("a")`)
- Every example and use-case is run twice and checked in CI (`tests/test_examples_run.py`)

### Fixed
- `task` / `await` never ran tasks; they now run in parallel and `await` results work by name or position
- The runtime silently pre-created `users`/`tasks` tables, overriding a script's own `CREATE TABLE`
- `query(sql, "one value")` bound each character; objects and lists are stored as JSON
- The ML module failed to import (syntax error); `train`/`fine_tune` accept a parameters object
- Type errors in operators (`5 > null`) now report the line and a hint
- Flutter build failed from a pip install (`mcn.fullstack` wasn't packaged)
- Studio no longer deletes or overwrites files in a project folder opened with `mcn studio <folder>`
- `trigger()` gives up on unreachable hosts after 5s instead of 30s
- The wheel no longer ships `node_modules`, Studio's workspace or scratch files (17 MB → 1 MB)
- MCN's own logs and package metadata live in `~/.mcn`, not the project folder

### Changed
- One version number everywhere (`mcn/version.py`)
- Scripts using an API that was never built moved to `examples/legacy/`

## [2.0.0] - 2025-10-07

### Added
- Complete MCN interpreter with lexer, parser, and runtime
- AI integration with multiple model support
- Database connectivity (PostgreSQL, MongoDB)
- HTTP client and server capabilities
- Async task system with await functionality
- Package system for extensions
- Type checking system
- Enhanced error logging and debugging
- VS Code extension support
- Web playground for online testing
- Docker and Kubernetes deployment configs
- Comprehensive documentation and examples

### Features
- Variables and expressions
- Control flow (if/else, for, while)
- Functions with parameters and return values
- Exception handling (try/catch/throw)
- Built-in functions (log, echo, query, ai, etc.)
- File operations (read, write, append)
- Environment variable access
- HTTP requests and responses
- Email sending capabilities
- Data encoding/decoding (base64, hashing)
- Date/time operations

### Developer Experience
- Zero-setup execution with `python run_mcn.py`
- Interactive REPL mode
- API server mode
- Cross-platform support (Windows, macOS, Linux)
- Rich error messages with suggestions
- Performance monitoring and logging

## [1.0.0] - 2025-08-03

### Added
- Initial MCN prototype
- Basic scripting capabilities
- Simple business automation features
