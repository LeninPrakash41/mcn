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
    const serverModule = context.asAbsolutePath(path.join('out', 'server.js'));
    const serverOptions = {
        run: { module: serverModule, transport: node_1.TransportKind.ipc },
        debug: { module: serverModule, transport: node_1.TransportKind.ipc }
    };
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'mcn' }, { scheme: 'untitled', language: 'mcn' }],
        initializationOptions: { cliPath: mcnCmd() },
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
        runInTerminal('MCN: Serve', `serve "${file}" --port ${port}`);
        vscode.window.showInformationMessage(`MCN serving ${path.basename(file)} on port ${port}`);
    });
    /** Start MCN Studio on the open folder and show it in the browser */
    const cmdPlayground = vscode.commands.registerCommand('mcn.openPlayground', () => {
        const cfg = vscode.workspace.getConfiguration('mcn');
        const port = cfg.get('playgroundPort', 5003);
        const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        runInTerminal('MCN Studio', `studio ${folder ? `"${folder}" ` : ''}--port ${port}`);
        setTimeout(() => vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`)), 2500);
    });
    /** mcn generate "<description>" — builds a full-stack app with Claude */
    const cmdAi = vscode.commands.registerCommand('mcn.aiAssistant', async () => {
        const description = await vscode.window.showInputBox({
            prompt: 'Describe the app to generate (needs ANTHROPIC_API_KEY)',
            placeHolder: 'A leave request tracker with manager approval',
        });
        if (!description)
            return;
        const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '.';
        runInTerminal('MCN: Generate', `generate ${JSON.stringify(description)} --out "${folder}"`);
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
//# sourceMappingURL=extension.js.map