# MCN Language Support for Visual Studio Code

Official VS Code extension for **MCN (Micro Code Native / Machine Code Native)** — the unified declarative full-stack application development language.

---

## Features

- 🎨 **Full Syntax Highlighting**: Contracts, Services, Endpoints, Components, Analytics (`use analytics`), AI Pipelines (`use ai`), Layouts, and Annotations (`@guard`, `@auth`).
- ⚡ **Rich Snippets**: Instant scaffolding for services, endpoints, data contracts, UI components, SQLite analytics queries, and multi-stage ETL pipelines.
- 📐 **Language Configuration**: Auto-closing brackets, smart indentation rules, and folding markers for MCN blocks.
- 🔍 **File Associations**: Automatic detection of `.mcn` and `.msl` files.

---

## Installation

### From Source / Local Testing
1. Clone this repository or copy `mcn-vscode-extension` to your VS Code extensions folder:
   ```bash
   cp -r mcn-vscode-extension ~/.vscode/extensions/mcn-lang
   ```
2. Reload Visual Studio Code (`Cmd+Shift+P` $\rightarrow$ `Developer: Reload Window`).

---

## Available Snippets

| Prefix | Description |
|---|---|
| `service` | Scaffold a new MCN backend service with SQLite endpoints |
| `endpoint` | Define a new service endpoint |
| `guard_endpoint` | Define an RBAC role-guarded endpoint (`@guard`) |
| `contract` | Define a data contract schema |
| `component` | Create a reactive UI component with state and lifecycle hooks |
| `analytics` | Native SQLite KPI summary, monthly trends, distribution, and pivot matrix |
| `pipeline` | Multi-stage extraction, transform, and load pipeline |
| `app` | Application root layout with sidebar/tabs navigation |

---

## License
MIT License. Part of the MCN Language ecosystem.
