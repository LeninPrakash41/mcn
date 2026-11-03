import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient;

// ── Helpers ───────────────────────────────────────────────────────────────────

function mcnCmd(): string {
  const cfg = vscode.workspace.getConfiguration('mcn');
  return cfg.get<string>('cliPath', 'mcn');
}

/** Run `mcn <args>` in a terminal with a given name. */
function runInTerminal(name: string, args: string): vscode.Terminal {
  const terminal = vscode.window.createTerminal(name);
  terminal.show(true);
  terminal.sendText(`${mcnCmd()} ${args}`);
  return terminal;
}

/** Return the file path of the active editor if it's a .mcn/.mx file. */
function activeFilePath(): string | null {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return null;
  const lang = editor.document.languageId;
  const ext  = path.extname(editor.document.fileName);
  if (lang !== 'mcn' && ext !== '.mcn' && ext !== '.mx') return null;
  return editor.document.fileName;
}


// ── Activate ──────────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {

  // ── Language Server ─────────────────────────────────────────────────────────
  const serverModule = context.asAbsolutePath(path.join('out', 'server.js'));

  const serverOptions: ServerOptions = {
    run:   { module: serverModule, transport: TransportKind.ipc },
    debug: { module: serverModule, transport: TransportKind.ipc }
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: 'file', language: 'mcn' }, { scheme: 'untitled', language: 'mcn' }],
    initializationOptions: { cliPath: mcnCmd() },
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{mcn,mx}')
    }
  };

  client = new LanguageClient(
    'mcnLanguageServer', 'MCN Language Server',
    serverOptions, clientOptions
  );
  client.start();


  // ── Commands ────────────────────────────────────────────────────────────────

  /** mcn run <file> */
  const cmdRun = vscode.commands.registerCommand('mcn.runScript', async () => {
    await vscode.window.activeTextEditor?.document.save();
    const file = activeFilePath();
    if (!file) { vscode.window.showErrorMessage('No MCN file is open'); return; }
    runInTerminal('MCN: Run', `run "${file}"`);
  });

  /** mcn test <file> */
  const cmdTest = vscode.commands.registerCommand('mcn.testScript', async () => {
    await vscode.window.activeTextEditor?.document.save();
    const file = activeFilePath();
    if (!file) { vscode.window.showErrorMessage('No MCN file is open'); return; }
    runInTerminal('MCN: Test', `test "${file}" --verbose`);
  });

  /** mcn fmt --write <file> */
  const cmdFmt = vscode.commands.registerCommand('mcn.formatDocument', async () => {
    await vscode.window.activeTextEditor?.document.save();
    const file = activeFilePath();
    if (!file) { vscode.window.showErrorMessage('No MCN file is open'); return; }
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
    if (!file) { vscode.window.showErrorMessage('No MCN file is open'); return; }
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
    if (!file) { vscode.window.showErrorMessage('No MCN file is open'); return; }

    const port = await vscode.window.showInputBox({
      prompt: 'Port to serve on',
      value:  '8080',
      validateInput: v => (isNaN(+v) || +v < 1 || +v > 65535) ? 'Enter a valid port (1–65535)' : null
    });
    if (!port) return;

    runInTerminal('MCN: Serve', `serve "${file}" --port ${port}`);
    vscode.window.showInformationMessage(`MCN serving ${path.basename(file)} on port ${port}`);
  });

  /** Start MCN Studio on the open folder and show it in the browser */
  const cmdPlayground = vscode.commands.registerCommand('mcn.openPlayground', () => {
    const cfg    = vscode.workspace.getConfiguration('mcn');
    const port   = cfg.get<number>('playgroundPort', 5003);
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
    if (!description) return;
    const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '.';
    runInTerminal('MCN: Generate', `generate ${JSON.stringify(description)} --out "${folder}"`);
  });

  context.subscriptions.push(
    cmdRun, cmdTest, cmdFmt, cmdCheck,
    cmdRepl, cmdServe, cmdPlayground, cmdAi
  );

  // Status bar item — shows "MCN" when editing an MCN file
  const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  statusItem.text    = '$(zap) MCN';
  statusItem.tooltip = 'MCN: click to run';
  statusItem.command = 'mcn.runScript';
  context.subscriptions.push(statusItem);

  const updateStatus = (editor?: vscode.TextEditor) => {
    if (editor && (editor.document.languageId === 'mcn' ||
                   editor.document.fileName.endsWith('.mx'))) {
      statusItem.show();
    } else {
      statusItem.hide();
    }
  };
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(updateStatus)
  );
  updateStatus(vscode.window.activeTextEditor);
}


export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
