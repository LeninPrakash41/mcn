# VS Code extension

The extension lives in `mcn/studio/vscode-mcn/`. It has two halves that run in separate processes: a client (`src/extension.ts`) inside VS Code, and a language server (`src/server.ts`) speaking the Language Server Protocol.

## Client

`activate()`:

- starts the language server (`out/server.js`) over IPC, passing `mcn.cliPath` as an initialization option;
- registers the commands (run, test, format, check, serve, REPL, open Studio, generate). Each runs the `mcn` CLI in an integrated terminal;
- shows the **MCN** status-bar item on `.mcn` files.

## Language server

- **Diagnostics** (pull model): on request, the server writes the document's unsaved text to a temp file, runs `mcn check --json`, and maps each diagnostic to an LSP range using `line`, `col` and `length`, with the hint appended to the message. If `mcn` can't be found it warns once and falls back to a few regex checks.
- **Completions:** a static list of built-ins with signatures and Markdown docs, keywords and snippets.
- **Hover:** short descriptions of keywords.

Using the CLI means the editor reports exactly what `mcn run` would, with no second parser to keep in sync.

## Building

```bash
cd mcn/studio/vscode-mcn
npm install
npm run compile                          # tsc → out/
npx vsce package                         # → mcn-vscode-<version>.vsix
```

The `.vsix` is committed and packaged with MCN, so `mcn vscode` can install it without Node. Bump `version` in `package.json` together with `mcn/version.py`.

## Testing the server

The server can be driven without VS Code by speaking LSP over stdio: send `initialize`, `textDocument/didOpen` and `textDocument/diagnostic`, and check the returned items. Grammar and snippet files are plain JSON in `syntaxes/` and `snippets/`.
