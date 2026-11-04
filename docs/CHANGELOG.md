# Changelog

All notable changes to MCN will be documented in this file.

## [Unreleased]

### Added
- **MCN UI kit** (`mcn/ui-kit/react`): one component library for exported apps and Studio's preview
  - App frame: collapsible sidebar with groups, mobile drawer, breadcrumb, ⌘K search, notification bell, dark mode, footer
  - `data_table` (search, column filters, sorting, pagination, table/grid/list views, CSV export, row actions), `kanban`
  - SVG charts: `bar_chart` (multi-series, stacked), `line_chart`, `area_chart`, `pie_chart`, `donut_chart`, `sparkline`
  - `chat` / `chat_widget`, `agent_builder`, `workflow_builder`, `breadcrumb`, `empty_state`, `notify()`
  - `app` blocks take `footer` and `logo`; `nav` items take `group`
- **Live preview**: Studio runs the actual compiled app in the browser with the kit, against the running backend (it used to show an approximation with sample data)
- Templates: Operations Dashboard, AI Agent Builder, Workflow Automation (21 in total)

### Fixed
- Exported apps read `.data` from an unresolved promise (`items = list_tasks().data` left lists empty)
- State read right after an assignment in a handler saw the old value
- Endpoint calls with literal arguments sent `arg0` instead of the parameter name (the backend is now consulted)
- A handler named after a JavaScript keyword (`on delete`) produced invalid code
- `a or b` was typed as a boolean by `mcn check`
- UI attributes can use keyword names (`chat endpoint=ask`)

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
