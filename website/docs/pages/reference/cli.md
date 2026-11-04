# CLI reference

Every command is a subcommand of `mcn`. Run `mcn <command> --help` for the full option list.

## Projects

| Command | What it does |
|---|---|
| `mcn init <name>` | Create a full-stack project: backend with tests, UI, README, `mcn.json`. Refuses a non-empty folder |
| `mcn validate [--path .]` | Check every `.mcn` file in a project (skips `frontend/`, `node_modules/`) and that `mcn.json`'s files exist |
| `mcn studio [folder] [--port 5003] [--host 127.0.0.1]` | Open MCN Studio. With a folder, edits that project; without, Studio's own workspace. Aliases: `playground`, `ide` |
| `mcn vscode` | Install the VS Code extension bundled with this version |

## Running code

| Command | What it does |
|---|---|
| `mcn run <file>` | Run a script. Errors print the line, a caret and a hint; exit code 1 on error |
| `mcn repl` | Interactive prompt |
| `mcn serve <file or folder>` | Serve endpoints as an HTTP API (GET and POST). Options: `--port` (default: the service's `port`, else 8080), `--host` (default 127.0.0.1), `--postman` |

## Quality

| Command | What it does |
|---|---|
| `mcn test <file or folder> [-v]` | Run `test` blocks. Exit code 1 if any fail |
| `mcn check <file>` | Syntax errors, never-defined names and type problems, without running |
| `mcn check --json <file>` | The same as JSON: `{"file", "diagnostics": [{kind, message, line, col, length, hint, severity}]}` |
| `mcn check --strict <file>` | Treat warnings as errors |
| `mcn audit [file or folder]` | Find security problems: SQL injection, hard-coded secrets, open services and more. See [security](#/guide/security) |
| `mcn audit --json` / `--fail-on high\|medium\|low` | JSON output for CI / the lowest severity that fails (default `medium`) |
| `mcn fmt <file or folder>` | Print formatted code |
| `mcn fmt --write <path>` | Format in place |
| `mcn fmt --check <path>` | Exit 1 if anything needs formatting (for CI) |

## Full stack

| Command | What it does |
|---|---|
| `mcn build <ui-file> [--out frontend]` | Compile MCN components to a React + Vite + Tailwind + shadcn/ui project |
| `mcn generate "<description>"` | Write a backend and UI with Claude, then validate them. Options: `--out DIR`, `--port`, `--build`, `--model` |
| `mcn deploy --target vercel [--name] [--prod]` | Put the React app and its backend (at `/api`) on Vercel. `--stage-only` writes the Vercel project without uploading. See [deploying](#/guide/deploy) |
| `mcn deploy [folder] [--target zip\|docker] [--name] [--out]` | Package a project as a zip with Docker files |

## Packages

| Command | What it does |
|---|---|
| `mcn packages list` | Every available package |
| `mcn packages info <name>` | A package's functions and descriptions |
| `mcn install <name>` | Check a bundled package is available |
| `mcn install --path <dir> [--name]` | Install a package from a local folder into `mcn_packages/` |
| `mcn packages remove <name>` | Uninstall |
| `mcn new-package <org/name> [--path] [--author] [--description]` | Scaffold a new package |

## Hardware

| Command | What it does |
|---|---|
| `mcn add iot` | Install hardware support: Raspberry Pi GPIO, USB serial and MQTT |
| `mcn iot firmware arduino [--out DIR]` | Write the USB firmware sketch for Arduino, ESP32 and Pico (`driver: "serial"`) |
| `mcn iot firmware esp32 [--out DIR]` | Write the WiFi + MQTT sketch for ESP32 (`driver: "mqtt"`) |
| `mcn iot ports` | List boards plugged in over USB |
| `mcn iot service <file> [--serve] [--port]` | Write a systemd unit that starts the app when a Raspberry Pi boots |

See [IoT and hardware](#/guide/iot).

## Configuration and logs

| Command | What it does |
|---|---|
| `mcn config set <key> <value>` | Save a setting, e.g. `api_key` |
| `mcn config get <key>` / `mcn config show` | Read settings (secrets are masked) |
| `mcn logs [--type errors\|debug\|all]` | Show MCN's own logs from `~/.mcn/logs` |
| `mcn --version` | Print the version |

## Exit codes

`0` means success. `1` means an error, a failing test, a check that found problems, or files that need formatting — so every command can gate a CI step.
