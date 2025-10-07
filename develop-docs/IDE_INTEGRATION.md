# MCN IDE Integration Standards

## Language Server Protocol (LSP)

### MCN Language Server
- **Protocol**: LSP 3.17
- **Transport**: JSON-RPC over stdio/TCP
- **Features**: IntelliSense, diagnostics, formatting

### Supported Features
- ✅ Syntax highlighting
- ✅ Auto-completion
- ✅ Error diagnostics
- ✅ Go to definition
- ✅ Find references
- ✅ Code formatting
- ✅ Hover information
- 🔄 Refactoring (planned)
- 🔄 Debugging (planned)

## IDE Extensions

### VS Code Extension
```json
{
  "name": "mcn-language-support",
  "displayName": "MCN Language Support",
  "description": "Official MCN language extension",
  "version": "2.0.0",
  "publisher": "mcn-foundation",
  "engines": {
    "vscode": "^1.70.0"
  },
  "categories": ["Programming Languages"],
  "contributes": {
    "languages": [{
      "id": "mcn",
      "aliases": ["MCN", "mcn"],
      "extensions": [".mcn"],
      "configuration": "./language-configuration.json"
    }],
    "grammars": [{
      "language": "mcn",
      "scopeName": "source.mcn",
      "path": "./syntaxes/mcn.tmLanguage.json"
    }]
  }
}
```

### JetBrains Plugin
- IntelliJ IDEA
- PyCharm
- WebStorm
- All JetBrains IDEs

### Other Editors
- Vim/Neovim
- Emacs
- Sublime Text
- Atom (legacy)

## Syntax Highlighting

### TextMate Grammar
```json
{
  "scopeName": "source.mcn",
  "patterns": [
    {
      "name": "keyword.control.mcn",
      "match": "\\b(if|else|while|for|function|return|var|use|import)\\b"
    },
    {
      "name": "string.quoted.double.mcn",
      "begin": "\"",
      "end": "\"",
      "patterns": [
        {
          "name": "constant.character.escape.mcn",
          "match": "\\\\."
        }
      ]
    },
    {
      "name": "comment.line.double-slash.mcn",
      "match": "//.*$"
    }
  ]
}
```

## Debugging Support

### Debug Adapter Protocol (DAP)
- Breakpoints
- Step debugging
- Variable inspection
- Call stack
- Watch expressions

### Debug Configuration
```json
{
  "type": "mcn",
  "request": "launch",
  "name": "Launch MCN Script",
  "program": "${file}",
  "args": [],
  "cwd": "${workspaceFolder}",
  "env": {}
}
```

## Code Intelligence

### Auto-completion
```mcn
// Trigger: ai.
ai.analyze_sentiment(|)  // Shows parameter hints
ai.summarize(|)          // Shows function signature
```

### Error Diagnostics
```mcn
var x = undefinedVariable  // Error: Undefined variable 'undefinedVariable'
ai("prompt")              // Warning: Missing 'use "ai"' import
```

### Quick Fixes
- Import missing modules
- Fix syntax errors
- Add type annotations
- Convert to modern syntax

## Project Templates

### Basic MCN Project
```
my-mcn-project/
├── mcn.json
├── src/
│   └── main.mcn
├── test/
│   └── main.test.mcn
├── docs/
│   └── README.md
└── .mcnignore
```

### Web API Project
```
mcn-api/
├── mcn.json
├── src/
│   ├── main.mcn
│   ├── routes/
│   └── models/
├── test/
├── config/
└── deploy/
```

## Build Tools Integration

### MCN CLI
```bash
mcn init my-project          # Create new project
mcn run script.mcn          # Run script
mcn test                    # Run tests
mcn build                   # Build for production
mcn deploy                  # Deploy to cloud
```

### Task Runners
- Integration with npm scripts
- Makefile support
- GitHub Actions workflows
- Docker containers