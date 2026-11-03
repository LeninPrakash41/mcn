# MCN contributor docs

How MCN is built, for people working on the language, Studio and tools. User documentation is on the website (`website/docs/`).

| Page | Covers |
|---|---|
| [Contributing](contributing.md) | Setup, the test suite, making a change, editing the docs |
| [Architecture](architecture.md) | Repository layout and how the pieces fit |
| [Lexer and parser](lexer-parser.md) | Tokens, indentation, the AST, error recovery, adding syntax |
| [Evaluator and runtime](evaluator.md) | Execution, scopes, calls, values, runtime services |
| [Diagnostics](diagnostics.md) | Error reports and `mcn check` |
| [UI compiler](ui-compiler.md) | Components → React, and the Flutter generator |
| [Studio server](studio.md) | Blueprints, security model, front end, templates |
| [VS Code extension](vscode-extension.md) | Client, language server, building |
| [Installer](installer.md) | The one-line installers and `mcn add` / `upgrade` / `uninstall` |
