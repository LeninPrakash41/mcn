# MCN Web Playground → Web IDE Evolution

## Current State: Basic Playground ✅

**Features:**
- Monaco Editor with MCN syntax highlighting
- Real-time code execution via Flask backend
- Output panel with logs and errors
- Example code snippets
- Basic error handling

**Usage:**
```bash
cd web-playground
python server.py
# Open http://localhost:5000
```

## Phase 1: Enhanced Playground (1-2 weeks)

### Features to Add:
- **File Management**: Save/load .mcn files
- **Multiple Tabs**: Work on multiple scripts
- **Autocomplete**: MCN function suggestions
- **Debugger**: Step-through execution
- **Package Explorer**: Browse available MCN packages

### Implementation:
```javascript
// File manager component
class FileManager {
    constructor() {
        this.files = new Map();
        this.activeFile = null;
    }

    createFile(name, content = '') {
        this.files.set(name, { content, modified: false });
        return this.openFile(name);
    }

    openFile(name) {
        this.activeFile = name;
        editor.setValue(this.files.get(name).content);
    }
}

// Autocomplete provider
monaco.languages.registerCompletionItemProvider('mcn', {
    provideCompletionItems: (model, position) => {
        const suggestions = [
            { label: 'log', kind: monaco.languages.CompletionItemKind.Function },
            { label: 'trigger', kind: monaco.languages.CompletionItemKind.Function },
            { label: 'query', kind: monaco.languages.CompletionItemKind.Function },
            { label: 'ai', kind: monaco.languages.CompletionItemKind.Function }
        ];
        return { suggestions };
    }
});
```

## Phase 2: Web IDE Core (1-2 months)

### Architecture:
```
┌─────────────────────────────────────────┐
│              MCN Web IDE                │
├─────────────────┬───────────────────────┤
│   File Explorer │     Editor Tabs       │
│   - Projects    │     - Monaco Editor   │
│   - .mcn files  │     - Syntax Check    │
│   - Packages    │     - Live Preview    │
├─────────────────┼───────────────────────┤
│   Terminal      │     Output Panel      │
│   - MCN REPL    │     - Logs           │
│   - Commands    │     - Errors         │
│   - Package Mgr │     - Debug Info     │
└─────────────────┴───────────────────────┘
```

### Key Components:

**1. Project Management**
```typescript
interface MCNProject {
    name: string;
    files: MCNFile[];
    packages: string[];
    config: ProjectConfig;
}

class ProjectManager {
    async createProject(name: string): Promise<MCNProject>
    async loadProject(path: string): Promise<MCNProject>
    async saveProject(project: MCNProject): Promise<void>
}
```

**2. Enhanced Editor**
```typescript
class MCNEditor {
    private monaco: monaco.editor.IStandaloneCodeEditor;
    private diagnostics: MCNDiagnostics;

    constructor() {
        this.setupSyntaxHighlighting();
        this.setupErrorChecking();
        this.setupAutocomplete();
    }

    private setupErrorChecking() {
        // Real-time syntax validation
        this.monaco.onDidChangeModelContent(() => {
            this.validateSyntax();
        });
    }
}
```

**3. Integrated Terminal**
```typescript
class MCNTerminal {
    private repl: MCNRepl;

    executeCommand(command: string): Promise<string> {
        if (command.startsWith('mcn ')) {
            return this.repl.execute(command.substring(4));
        }
        return this.executeSystemCommand(command);
    }
}
```

## Phase 3: Advanced IDE Features (2-3 months)

### Features:
- **Visual Debugger**: Breakpoints, variable inspection
- **AI Assistant**: Code generation and suggestions
- **Collaboration**: Real-time multi-user editing
- **Package Manager UI**: Visual package installation
- **Deployment**: One-click deploy to MCN Cloud

### Implementation Examples:

**Visual Debugger:**
```typescript
class MCNDebugger {
    private breakpoints: Set<number> = new Set();
    private currentLine: number = 0;
    private variables: Map<string, any> = new Map();

    async stepOver(): Promise<void> {
        const response = await fetch('/api/debug/step', {
            method: 'POST',
            body: JSON.stringify({ action: 'step_over' })
        });

        const state = await response.json();
        this.updateDebugState(state);
    }

    private updateDebugState(state: DebugState) {
        this.currentLine = state.line;
        this.variables = new Map(Object.entries(state.variables));
        this.highlightCurrentLine();
        this.updateVariablePanel();
    }
}
```

**AI Assistant:**
```typescript
class MCNAIAssistant {
    async generateCode(prompt: string): Promise<string> {
        const response = await fetch('/api/ai/generate', {
            method: 'POST',
            body: JSON.stringify({
                prompt,
                context: this.getEditorContext()
            })
        });

        return response.json();
    }

    async explainCode(code: string): Promise<string> {
        // AI explains selected MCN code
    }

    async suggestFix(error: string): Promise<string> {
        // AI suggests fixes for errors
    }
}
```

## Phase 4: Full Platform Integration (3-6 months)

### Features:
- **Cloud Sync**: Sync projects across devices
- **Template Gallery**: Pre-built MCN templates
- **Marketplace**: Community packages and templates
- **Analytics**: Usage analytics and performance monitoring
- **Enterprise**: Team management and permissions

## Quick Start Implementation

To start building the enhanced playground immediately:

**1. Enhanced HTML Structure:**
```html
<div class="ide-container">
    <div class="sidebar">
        <div class="file-explorer"></div>
        <div class="package-manager"></div>
    </div>
    <div class="main-area">
        <div class="tab-bar"></div>
        <div class="editor-container"></div>
    </div>
    <div class="bottom-panel">
        <div class="terminal"></div>
        <div class="output"></div>
    </div>
</div>
```

**2. Enhanced Server API:**
```python
@app.route('/api/project/create', methods=['POST'])
def create_project():
    # Create new MCN project

@app.route('/api/project/<project_id>/files')
def get_project_files(project_id):
    # Get all files in project

@app.route('/api/debug/start', methods=['POST'])
def start_debug_session():
    # Start debugging session
```

**3. File System Integration:**
```python
class MCNProjectManager:
    def __init__(self, workspace_dir="./workspace"):
        self.workspace_dir = workspace_dir

    def create_project(self, name: str) -> dict:
        project_dir = os.path.join(self.workspace_dir, name)
        os.makedirs(project_dir, exist_ok=True)

        # Create project structure
        return {
            "name": name,
            "path": project_dir,
            "files": [],
            "created": datetime.now().isoformat()
        }
```

This evolution path takes you from a simple playground to a full-featured web IDE while maintaining backward compatibility and allowing incremental development.
