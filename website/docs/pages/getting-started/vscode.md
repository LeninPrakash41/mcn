# VS Code extension

The MCN extension adds highlighting, completions, hover docs and live errors to VS Code, plus commands to run, test, serve and open Studio.

## Install

```bash
mcn vscode
```

This installs the extension that ships with your version of MCN. It needs VS Code's `code` command on your PATH: in VS Code, open the Command Palette and run **Shell Command: Install 'code' command in PATH**.

To install by hand, open the Extensions view, choose **… → Install from VSIX**, and pick `mcn/studio/vscode-mcn/mcn-vscode-<version>.vsix`.

## Features

| Feature | Details |
|---|---|
| Live errors | Problems are underlined as you type, using `mcn check` on the unsaved text, with the same message and hint as `mcn run` |
| Completions | Built-in functions with signatures and examples, keywords and snippets |
| Hover | Short docs for keywords like `component`, `agent` and `use` |
| Status bar | Click **MCN** to run the current file |

## Commands

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and type **MCN**:

| Command | Runs |
|---|---|
| MCN: Run Script | `mcn run <file>` |
| MCN: Run Tests | `mcn test <file>` |
| MCN: Format Document | `mcn fmt --write <file>` |
| MCN: Type Check | `mcn check <file>` |
| MCN: Serve as API | `mcn serve <file> --port N` |
| MCN: Open REPL | `mcn repl` |
| MCN: Open Studio | `mcn studio <workspace folder>`, then opens the browser |
| MCN: Generate App with AI | `mcn generate "<description>"` (needs `ANTHROPIC_API_KEY`) |

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `mcn.cliPath` | `mcn` | The `mcn` command, if it isn't on your PATH (for example `~/.mcn/bin/mcn`) |
| `mcn.playgroundPort` | `5003` | Port for **Open Studio** |
| `mcn.formatOnSave` | `false` | Run `mcn fmt` on save |

> **Tip** If you only see basic checks, the extension can't find `mcn`. It shows a warning once; set `mcn.cliPath` to the full path of the command.
