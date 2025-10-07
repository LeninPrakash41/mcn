import * as vscode from 'vscode';
import * as path from 'path';
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from 'vscode-languageclient/node';

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {
    // Language Server setup
    const serverModule = context.asAbsolutePath(path.join('..', 'msl-language-server', 'out', 'server.js'));
    
    const serverOptions: ServerOptions = {
        run: { module: serverModule, transport: TransportKind.ipc },
        debug: { module: serverModule, transport: TransportKind.ipc }
    };

    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: 'file', language: 'msl' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/.msl')
        }
    };

    client = new LanguageClient('mslLanguageServer', 'MSL Language Server', serverOptions, clientOptions);
    client.start();

    // Register commands
    const runScript = vscode.commands.registerCommand('msl.runScript', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'msl') {
            vscode.window.showErrorMessage('No MSL file is currently open');
            return;
        }

        const config = vscode.workspace.getConfiguration('msl');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mslPath = config.get<string>('mslPath') || 'msl_cli.py';
        
        const terminal = vscode.window.createTerminal('MSL Runner');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mslPath} "${editor.document.fileName}"`);
    });

    const openRepl = vscode.commands.registerCommand('msl.openRepl', () => {
        const config = vscode.workspace.getConfiguration('msl');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mslPath = config.get<string>('mslPath') || 'msl_cli.py';
        
        const terminal = vscode.window.createTerminal('MSL REPL');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mslPath} --repl`);
    });

    const serveAsApi = vscode.commands.registerCommand('msl.serveAsApi', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'msl') {
            vscode.window.showErrorMessage('No MSL file is currently open');
            return;
        }

        const port = await vscode.window.showInputBox({
            prompt: 'Enter port number',
            value: '8000',
            validateInput: (value) => {
                const num = parseInt(value);
                return (isNaN(num) || num < 1 || num > 65535) ? 'Invalid port number' : null;
            }
        });

        if (!port) return;

        const config = vscode.workspace.getConfiguration('msl');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mslPath = config.get<string>('mslPath') || 'msl_cli.py';
        
        const terminal = vscode.window.createTerminal('MSL API Server');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mslPath} "${editor.document.fileName}" --serve --port ${port}`);
        
        vscode.window.showInformationMessage(`MSL API server starting on port ${port}`);
    });

    // AI Assistant Panel
    const aiAssistant = vscode.commands.registerCommand('msl.aiAssistant', () => {
        const panel = vscode.window.createWebviewPanel(
            'mslAiAssistant',
            'MSL AI Assistant',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        panel.webview.html = getAiAssistantHtml();
        
        panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'generateCode':
                    const code = await generateMslCode(message.prompt);
                    panel.webview.postMessage({ command: 'codeGenerated', code });
                    break;
            }
        });
    });

    context.subscriptions.push(runScript, openRepl, serveAsApi, aiAssistant);
}

export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}

function getAiAssistantHtml(): string {
    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>MSL AI Assistant</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .chat-container { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
            .input-container { display: flex; gap: 10px; }
            input { flex: 1; padding: 8px; }
            button { padding: 8px 16px; }
            .message { margin-bottom: 10px; padding: 8px; border-radius: 4px; }
            .user { background-color: #e3f2fd; }
            .ai { background-color: #f3e5f5; }
            .code { background-color: #f5f5f5; font-family: monospace; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h2>MSL AI Assistant</h2>
        <div id="chat" class="chat-container"></div>
        <div class="input-container">
            <input type="text" id="prompt" placeholder="Describe what you want to build in MSL..." />
            <button onclick="generateCode()">Generate Code</button>
        </div>
        
        <script>
            const vscode = acquireVsCodeApi();
            
            function generateCode() {
                const prompt = document.getElementById('prompt').value;
                if (!prompt) return;
                
                addMessage('user', prompt);
                document.getElementById('prompt').value = '';
                
                vscode.postMessage({
                    command: 'generateCode',
                    prompt: prompt
                });
            }
            
            function addMessage(type, content) {
                const chat = document.getElementById('chat');
                const message = document.createElement('div');
                message.className = 'message ' + type;
                message.textContent = content;
                chat.appendChild(message);
                chat.scrollTop = chat.scrollHeight;
            }
            
            window.addEventListener('message', event => {
                const message = event.data;
                if (message.command === 'codeGenerated') {
                    addMessage('ai', 'Generated MSL code:');
                    const codeDiv = document.createElement('div');
                    codeDiv.className = 'message code';
                    codeDiv.textContent = message.code;
                    document.getElementById('chat').appendChild(codeDiv);
                }
            });
            
            document.getElementById('prompt').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    generateCode();
                }
            });
        </script>
    </body>
    </html>`;
}

async function generateMslCode(prompt: string): Promise<string> {
    // Mock AI code generation - in real implementation, call OpenAI API
    const templates = {
        'user management': `var user_name = "Alice"
var user_email = "alice@example.com"

query("INSERT INTO users (name, email) VALUES (?, ?)", (user_name, user_email))
log "User created: " + user_name`,
        
        'api integration': `var api_url = "https://api.example.com/data"
var response = trigger(api_url, {"key": "value"})

if response.success
    log "API call successful: " + response.data
else
    log "API call failed: " + response.error`,
        
        'ai analysis': `var text_data = "Sample text for analysis"
var sentiment = ai("Analyze sentiment of: " + text_data)
log "Sentiment analysis: " + sentiment`
    };
    
    // Simple keyword matching for demo
    for (const [key, template] of Object.entries(templates)) {
        if (prompt.toLowerCase().includes(key)) {
            return template;
        }
    }
    
    return `// Generated MSL code for: ${prompt}
var result = ai("${prompt}")
log "Result: " + result`;
}