"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const cp = __importStar(require("child_process"));
const node_1 = require("vscode-languageclient/node");
let client;
// ── Helpers ───────────────────────────────────────────────────────────────────
function mcnCmd() {
    const cfg = vscode.workspace.getConfiguration('mcn');
    return cfg.get('cliPath', 'mcn');
}
function pythonCmd() {
    const cfg = vscode.workspace.getConfiguration('mcn');
    return cfg.get('pythonPath', 'python3');
}
/** Run `mcn <args>` in a terminal with a given name. */
function runInTerminal(name, args) {
    const terminal = vscode.window.createTerminal(name);
    terminal.show(true);
    terminal.sendText(`${mcnCmd()} ${args}`);
    return terminal;
}
/** Return the file path of the active editor if it's a .mcn/.mx file. */
function activeFilePath() {
    const editor = vscode.window.activeTextEditor;
    if (!editor)
        return null;
    const lang = editor.document.languageId;
    const ext = path.extname(editor.document.fileName);
    if (lang !== 'mcn' && ext !== '.mcn' && ext !== '.mx')
        return null;
    return editor.document.fileName;
}
// ── Activate ──────────────────────────────────────────────────────────────────
function activate(context) {
    // ── Language Server ─────────────────────────────────────────────────────────
    const serverModule = context.asAbsolutePath(path.join('..', 'mcn-language-server', 'out', 'server.js'));
    const serverOptions = {
        run: { module: serverModule, transport: node_1.TransportKind.ipc },
        debug: { module: serverModule, transport: node_1.TransportKind.ipc }
    };
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'mcn' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{mcn,mx}')
        }
    };
    client = new node_1.LanguageClient('mcnLanguageServer', 'MCN Language Server', serverOptions, clientOptions);
    client.start();
    // ── Commands ────────────────────────────────────────────────────────────────
    /** mcn run <file> */
    const cmdRun = vscode.commands.registerCommand('mcn.runScript', async () => {
        await vscode.window.activeTextEditor?.document.save();
        const file = activeFilePath();
        if (!file) {
            vscode.window.showErrorMessage('No MCN file is open');
            return;
        }
        runInTerminal('MCN: Run', `run "${file}"`);
    });
    /** mcn test <file> */
    const cmdTest = vscode.commands.registerCommand('mcn.testScript', async () => {
        await vscode.window.activeTextEditor?.document.save();
        const file = activeFilePath();
        if (!file) {
            vscode.window.showErrorMessage('No MCN file is open');
            return;
        }
        runInTerminal('MCN: Test', `test "${file}" --verbose`);
    });
    /** mcn fmt --write <file> */
    const cmdFmt = vscode.commands.registerCommand('mcn.formatDocument', async () => {
        await vscode.window.activeTextEditor?.document.save();
        const file = activeFilePath();
        if (!file) {
            vscode.window.showErrorMessage('No MCN file is open');
            return;
        }
        // Run format and reload
        cp.exec(`${mcnCmd()} fmt --write "${file}"`, (err, stdout, stderr) => {
            if (err) {
                vscode.window.showErrorMessage(`mcn fmt failed: ${stderr || err.message}`);
                return;
            }
            // Reload the file in the editor
            vscode.commands.executeCommand('workbench.action.revertFile');
            vscode.window.setStatusBarMessage('MCN: formatted', 3000);
        });
    });
    /** mcn check <file> */
    const cmdCheck = vscode.commands.registerCommand('mcn.checkScript', async () => {
        await vscode.window.activeTextEditor?.document.save();
        const file = activeFilePath();
        if (!file) {
            vscode.window.showErrorMessage('No MCN file is open');
            return;
        }
        runInTerminal('MCN: Check', `check "${file}"`);
    });
    /** mcn repl */
    const cmdRepl = vscode.commands.registerCommand('mcn.openRepl', () => {
        runInTerminal('MCN: REPL', 'repl');
    });
    /** mcn serve --file <file> --port <N> */
    const cmdServe = vscode.commands.registerCommand('mcn.serveAsApi', async () => {
        await vscode.window.activeTextEditor?.document.save();
        const file = activeFilePath();
        if (!file) {
            vscode.window.showErrorMessage('No MCN file is open');
            return;
        }
        const port = await vscode.window.showInputBox({
            prompt: 'Port to serve on',
            value: '8080',
            validateInput: v => (isNaN(+v) || +v < 1 || +v > 65535) ? 'Enter a valid port (1–65535)' : null
        });
        if (!port)
            return;
        runInTerminal('MCN: Serve', `serve --file "${file}" --port ${port}`);
        vscode.window.showInformationMessage(`MCN serving ${path.basename(file)} on port ${port}`);
    });
    /** Open the web playground in the browser */
    const cmdPlayground = vscode.commands.registerCommand('mcn.openPlayground', () => {
        const cfg = vscode.workspace.getConfiguration('mcn');
        const port = cfg.get('playgroundPort', 5000);
        vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
    });
    /** AI assistant side panel */
    const cmdAi = vscode.commands.registerCommand('mcn.aiAssistant', () => {
        const panel = vscode.window.createWebviewPanel('mcnAiAssistant', 'MCN AI Assistant', vscode.ViewColumn.Beside, { enableScripts: true, retainContextWhenHidden: true });
        panel.webview.html = aiAssistantHtml();
        panel.webview.onDidReceiveMessage(async (msg) => {
            if (msg.command === 'generate') {
                const code = generateSnippet(msg.prompt);
                panel.webview.postMessage({ command: 'result', code });
            }
            if (msg.command === 'insertCode') {
                const editor = vscode.window.activeTextEditor;
                if (editor) {
                    editor.edit(eb => eb.insert(editor.selection.active, msg.code));
                }
            }
        });
    });
    context.subscriptions.push(cmdRun, cmdTest, cmdFmt, cmdCheck, cmdRepl, cmdServe, cmdPlayground, cmdAi);
    // Status bar item — shows "MCN" when editing an MCN file
    const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
    statusItem.text = '$(zap) MCN';
    statusItem.tooltip = 'MCN: click to run';
    statusItem.command = 'mcn.runScript';
    context.subscriptions.push(statusItem);
    const updateStatus = (editor) => {
        if (editor && (editor.document.languageId === 'mcn' ||
            editor.document.fileName.endsWith('.mx'))) {
            statusItem.show();
        }
        else {
            statusItem.hide();
        }
    };
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(updateStatus));
    updateStatus(vscode.window.activeTextEditor);
}
function deactivate() {
    return client?.stop();
}
// ── AI Assistant webview ──────────────────────────────────────────────────────
function aiAssistantHtml() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--vscode-font-family); font-size: 13px;
           background: var(--vscode-editor-background);
           color: var(--vscode-editor-foreground); padding: 12px; }
    h3 { margin-bottom: 10px; font-size: 14px; }
    textarea { width: 100%; height: 70px; resize: vertical; padding: 8px;
               background: var(--vscode-input-background);
               color: var(--vscode-input-foreground);
               border: 1px solid var(--vscode-input-border, #555);
               border-radius: 3px; font-family: inherit; font-size: 13px; }
    .row { display: flex; gap: 8px; margin: 8px 0; }
    button { padding: 6px 14px; border: none; border-radius: 3px; cursor: pointer;
             background: var(--vscode-button-background);
             color: var(--vscode-button-foreground); font-size: 12px; font-weight: 600; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    .btn-insert { background: var(--vscode-button-secondaryBackground);
                  color: var(--vscode-button-secondaryForeground); }
    pre { background: var(--vscode-textCodeBlock-background, #1e1e1e);
          border: 1px solid var(--vscode-panel-border, #444);
          border-radius: 3px; padding: 10px; overflow-x: auto;
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 12px; white-space: pre-wrap; margin-top: 10px; }
    .hint { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 6px; }
  </style>
</head>
<body>
  <h3>MCN AI Assistant</h3>
  <textarea id="prompt" placeholder="Describe what you want to build…
e.g. &quot;a service that classifies customer feedback&quot;"></textarea>
  <div class="row">
    <button onclick="generate()">Generate</button>
  </div>
  <div id="output" style="display:none">
    <pre id="code"></pre>
    <div class="row">
      <button class="btn-insert" onclick="insertCode()">Insert into editor</button>
    </div>
  </div>
  <div class="hint">Tip: Ctrl+Enter to run the file after inserting.</div>

  <script>
    const vscode = acquireVsCodeApi();
    let lastCode = '';

    document.getElementById('prompt').addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generate();
    });

    function generate() {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) return;
      vscode.postMessage({ command: 'generate', prompt });
    }

    function insertCode() {
      if (lastCode) vscode.postMessage({ command: 'insertCode', code: lastCode });
    }

    window.addEventListener('message', e => {
      if (e.data.command === 'result') {
        lastCode = e.data.code;
        document.getElementById('code').textContent = lastCode;
        document.getElementById('output').style.display = 'block';
      }
    });
  </script>
</body>
</html>`;
}
// ── Snippet generator (offline fallback) ──────────────────────────────────────
function generateSnippet(prompt) {
    const p = prompt.toLowerCase();
    if (p.includes('sentiment') || p.includes('classify') || p.includes('feedback')) {
        return `contract Feedback
    sentiment: str
    score:     int

service feedback_api
    port 8080

    endpoint analyze(text)
        var result = extract(text, Feedback)
        return result`;
    }
    if (p.includes('agent') || p.includes('researcher')) {
        return `agent researcher
    model  "claude-3-5-sonnet-20241022"
    tools  ai, fetch
    memory session

    task analyze(topic)
        var data     = fetch("https://api.example.com?q=" + topic)
        var findings = ai("Key insights from: " + data)
        return findings`;
    }
    if (p.includes('pipeline') || p.includes('etl') || p.includes('data')) {
        return `pipeline data_pipeline
    stage extract
        var rows = query("SELECT * FROM events WHERE processed = false")
        return rows

    stage transform(data)
        var clean = ai("Normalize and deduplicate: " + data)
        return clean

    stage load(data)
        query("INSERT INTO clean_events VALUES ?", data)
        log("Loaded {data} records")`;
    }
    if (p.includes('api') || p.includes('service') || p.includes('endpoint')) {
        return `service my_api
    port 8080

    endpoint get_item(id)
        var item = query("SELECT * FROM items WHERE id = ?", (id,))
        if not item
            throw "Item not found: {id}"
        return item

    endpoint create_item(name, description)
        query("INSERT INTO items (name, description) VALUES (?, ?)", (name, description))
        return {success: true, name: name}`;
    }
    if (p.includes('test') || p.includes('unit')) {
        return `function add(a, b)
    return a + b

function clamp(val, lo, hi)
    if val < lo
        return lo
    if val > hi
        return hi
    return val

test "addition works"
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

test "clamping"
    assert clamp(15, 0, 10) == 10
    assert clamp(-5, 0, 10) == 0`;
    }
    if (p.includes('prompt') || p.includes('template')) {
        return `prompt support_reply
    system "You are a helpful customer support agent. Be concise and friendly."
    user   "Customer message: {{message}}"
    format text

var reply = support_reply.run({message: customer_input})
log(reply)`;
    }
    // Generic fallback
    return `// MCN snippet for: ${prompt}
var result = ai("${prompt}")
log("Result: {result}")`;
}
//# sourceMappingURL=extension.js.map