import * as vscode from 'vscode';
import * as path from 'path';
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from 'vscode-languageclient/node';

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {
    // Language Server setup
    const serverModule = context.asAbsolutePath(path.join('..', 'mcn-language-server', 'out', 'server.js'));

    const serverOptions: ServerOptions = {
        run: { module: serverModule, transport: TransportKind.ipc },
        debug: { module: serverModule, transport: TransportKind.ipc }
    };

    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: 'file', language: 'mcn' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/.mcn')
        }
    };

    client = new LanguageClient('mcnLanguageServer', 'MCN Language Server', serverOptions, clientOptions);
    client.start();

    // Register commands
    const runScript = vscode.commands.registerCommand('mcn.runScript', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'mcn') {
            vscode.window.showErrorMessage('No MCN file is currently open');
            return;
        }

        const config = vscode.workspace.getConfiguration('mcn');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mcnPath = config.get<string>('mcnPath') || 'mcn_cli.py';

        const terminal = vscode.window.createTerminal('MCN Runner');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mcnPath} "${editor.document.fileName}"`);
    });

    const openRepl = vscode.commands.registerCommand('mcn.openRepl', () => {
        const config = vscode.workspace.getConfiguration('mcn');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mcnPath = config.get<string>('mcnPath') || 'mcn_cli.py';

        const terminal = vscode.window.createTerminal('MCN REPL');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mcnPath} --repl`);
    });

    const serveAsApi = vscode.commands.registerCommand('mcn.serveAsApi', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'mcn') {
            vscode.window.showErrorMessage('No MCN file is currently open');
            return;
        }

        const port = await vscode.window.showInputBox({
            prompt: 'Enter port number',
            value: '8000',
            validateInput: (value: any) => {
                const num = parseInt(value);
                return (isNaN(num) || num < 1 || num > 65535) ? 'Invalid port number' : null;
            }
        });

        if (!port) return;

        const config = vscode.workspace.getConfiguration('mcn');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const mcnPath = config.get<string>('mcnPath') || 'mcn_cli.py';

        const terminal = vscode.window.createTerminal('MCN API Server');
        terminal.show();
        terminal.sendText(`${pythonPath} ${mcnPath} "${editor.document.fileName}" --serve --port ${port}`);

        vscode.window.showInformationMessage(`MCN API server starting on port ${port}`);
    });

    // AI Assistant Panel
    const aiAssistant = vscode.commands.registerCommand('mcn.aiAssistant', () => {
        const panel = vscode.window.createWebviewPanel(
            'mcnAiAssistant',
            'MCN AI Assistant',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.file(context.extensionPath)]
            }
        );

        panel.webview.html = getAiAssistantHtml();

        panel.webview.onDidReceiveMessage(async (message: any) => {
            switch (message.command) {
                case 'generateCode':
                    const code = await generateMcnCode(message.prompt);
                    panel.webview.postMessage({ command: 'codeGenerated', code });
                    break;
                case 'insertCode':
                    const editor = vscode.window.activeTextEditor;
                    if (editor) {
                        const position = editor.selection.active;
                        editor.edit(editBuilder => {
                            editBuilder.insert(position, message.code);
                        });
                    }
                    break;
                case 'explainCode':
                    const explanation = await explainMcnCode(message.code);
                    panel.webview.postMessage({ command: 'codeExplained', explanation });
                    break;
            }
        });
    });

    // New commands for enhanced functionality
    const validateScript = vscode.commands.registerCommand('mcn.validateScript', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'mcn') {
            vscode.window.showErrorMessage('No MCN file is currently open');
            return;
        }

        const diagnostics = await validateMcnScript(editor.document.getText());
        if (diagnostics.length === 0) {
            vscode.window.showInformationMessage('MCN script is valid!');
        } else {
            vscode.window.showWarningMessage(`Found ${diagnostics.length} issues in MCN script`);
        }
    });

    const generateTests = vscode.commands.registerCommand('mcn.generateTests', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'mcn') {
            vscode.window.showErrorMessage('No MCN file is currently open');
            return;
        }

        const tests = await generateMcnTests(editor.document.getText());
        const testUri = vscode.Uri.file(editor.document.fileName.replace('.mcn', '_test.mcn'));
        
        const testDoc = await vscode.workspace.openTextDocument(testUri.with({ scheme: 'untitled' }));
        const testEditor = await vscode.window.showTextDocument(testDoc);
        
        testEditor.edit(editBuilder => {
            editBuilder.insert(new vscode.Position(0, 0), tests);
        });
    });

    context.subscriptions.push(runScript, openRepl, serveAsApi, aiAssistant, validateScript, generateTests);
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
        <title>MCN AI Assistant</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                padding: 0; margin: 0; 
                background: var(--vscode-editor-background);
                color: var(--vscode-editor-foreground);
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            .header {
                background: var(--vscode-titleBar-activeBackground);
                padding: 10px 15px;
                border-bottom: 1px solid var(--vscode-panel-border);
                font-weight: bold;
            }
            .chat-container { 
                flex: 1;
                overflow-y: auto; 
                padding: 15px; 
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .input-container { 
                padding: 15px;
                border-top: 1px solid var(--vscode-panel-border);
                background: var(--vscode-input-background);
            }
            .input-row {
                display: flex;
                gap: 8px;
                margin-bottom: 8px;
            }
            input { 
                flex: 1; 
                padding: 8px 12px;
                background: var(--vscode-input-background);
                color: var(--vscode-input-foreground);
                border: 1px solid var(--vscode-input-border);
                border-radius: 4px;
            }
            button { 
                padding: 8px 16px;
                background: var(--vscode-button-background);
                color: var(--vscode-button-foreground);
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background: var(--vscode-button-hoverBackground);
            }
            .message { 
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 8px;
                max-width: 85%;
            }
            .user { 
                background: var(--vscode-textBlockQuote-background);
                align-self: flex-end;
                border-left: 4px solid var(--vscode-textLink-foreground);
            }
            .ai { 
                background: var(--vscode-textCodeBlock-background);
                align-self: flex-start;
                border-left: 4px solid var(--vscode-debugTokenExpression-name);
            }
            .code { 
                background: var(--vscode-textPreformat-background);
                font-family: var(--vscode-editor-font-family);
                white-space: pre-wrap;
                border: 1px solid var(--vscode-panel-border);
                border-radius: 4px;
                position: relative;
                padding-top: 30px;
            }
            .code-header {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                background: var(--vscode-tab-activeBackground);
                padding: 4px 8px;
                font-size: 12px;
                border-bottom: 1px solid var(--vscode-panel-border);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .code-actions {
                display: flex;
                gap: 5px;
            }
            .code-btn {
                padding: 2px 6px;
                font-size: 11px;
                background: var(--vscode-button-secondaryBackground);
                color: var(--vscode-button-secondaryForeground);
            }
            .templates {
                display: flex;
                gap: 5px;
                flex-wrap: wrap;
                margin-bottom: 8px;
            }
            .template-btn {
                padding: 4px 8px;
                font-size: 12px;
                background: var(--vscode-badge-background);
                color: var(--vscode-badge-foreground);
            }
        </style>
    </head>
    <body>
        <div class="header">
            🤖 MCN AI Assistant - Enhanced with v3.0 Features
        </div>
        
        <div id="chat" class="chat-container">
            <div class="message ai">
                Welcome! I can help you with MCN code generation, explanation, and best practices. Try asking me to:
                <ul>
                    <li>Generate MCN code for specific tasks</li>
                    <li>Explain existing MCN code</li>
                    <li>Create AI integrations, IoT automations, or data pipelines</li>
                    <li>Suggest improvements and optimizations</li>
                </ul>
            </div>
        </div>
        
        <div class="input-container">
            <div class="templates">
                <button class="template-btn" onclick="useTemplate('ai')">AI Integration</button>
                <button class="template-btn" onclick="useTemplate('iot')">IoT Automation</button>
                <button class="template-btn" onclick="useTemplate('pipeline')">Data Pipeline</button>
                <button class="template-btn" onclick="useTemplate('api')">API Integration</button>
            </div>
            <div class="input-row">
                <input type="text" id="prompt" placeholder="Describe what you want to build in MCN..." />
                <button onclick="generateCode()">Generate</button>
                <button onclick="explainCurrentCode()">Explain</button>
            </div>
        </div>

        <script>
            const vscode = acquireVsCodeApi();
            let messageId = 0;

            function generateCode() {
                const prompt = document.getElementById('prompt').value;
                if (!prompt) return;

                addMessage('user', prompt);
                document.getElementById('prompt').value = '';
                
                addMessage('ai', 'Generating MCN code...');

                vscode.postMessage({
                    command: 'generateCode',
                    prompt: prompt
                });
            }
            
            function explainCurrentCode() {
                addMessage('user', 'Please explain the current MCN code');
                vscode.postMessage({
                    command: 'explainCode',
                    code: 'current'
                });
            }
            
            function useTemplate(type) {
                const templates = {
                    'ai': 'Create an AI-powered customer service chatbot that can classify intents and generate responses',
                    'iot': 'Build an IoT automation system that monitors temperature and controls smart lights',
                    'pipeline': 'Create a data pipeline that processes customer feedback and extracts sentiment',
                    'api': 'Build an API integration that fetches user data and processes it with AI'
                };
                
                document.getElementById('prompt').value = templates[type] || '';
            }

            function addMessage(type, content) {
                const chat = document.getElementById('chat');
                const message = document.createElement('div');
                message.className = 'message ' + type;
                message.textContent = content;
                chat.appendChild(message);
                chat.scrollTop = chat.scrollHeight;
                return message;
            }
            
            function addCodeMessage(code, language = 'mcn') {
                const chat = document.getElementById('chat');
                const container = document.createElement('div');
                container.className = 'message ai';
                
                const codeDiv = document.createElement('div');
                codeDiv.className = 'code';
                
                const header = document.createElement('div');
                header.className = 'code-header';
                header.innerHTML = \`
                    <span>Generated MCN Code</span>
                    <div class="code-actions">
                        <button class="code-btn" onclick="insertCode('\${messageId}')">Insert</button>
                        <button class="code-btn" onclick="copyCode('\${messageId}')">Copy</button>
                    </div>
                \`;
                
                const codeContent = document.createElement('div');
                codeContent.textContent = code;
                codeContent.id = 'code-' + messageId;
                
                codeDiv.appendChild(header);
                codeDiv.appendChild(codeContent);
                container.appendChild(codeDiv);
                chat.appendChild(container);
                chat.scrollTop = chat.scrollHeight;
                
                messageId++;
            }
            
            function insertCode(id) {
                const codeElement = document.getElementById('code-' + id);
                if (codeElement) {
                    vscode.postMessage({
                        command: 'insertCode',
                        code: codeElement.textContent
                    });
                }
            }
            
            function copyCode(id) {
                const codeElement = document.getElementById('code-' + id);
                if (codeElement) {
                    navigator.clipboard.writeText(codeElement.textContent);
                }
            }

            window.addEventListener('message', event => {
                const message = event.data;
                switch (message.command) {
                    case 'codeGenerated':
                        // Remove loading message
                        const messages = document.querySelectorAll('.message.ai');
                        const lastMessage = messages[messages.length - 1];
                        if (lastMessage && lastMessage.textContent.includes('Generating')) {
                            lastMessage.remove();
                        }
                        
                        addMessage('ai', 'Here\'s your generated MCN code:');
                        addCodeMessage(message.code);
                        break;
                    case 'codeExplained':
                        addMessage('ai', message.explanation);
                        break;
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

async function generateMcnCode(prompt: string): Promise<string> {
    const templates = {
        'ai': `use "ai_v3"

// AI-powered solution
register("gpt-3.5", "openai", {"temperature": 0.7})
set_model("gpt-3.5")

var user_input = "${prompt}"
var ai_response = run("gpt-3.5", "Process this request: " + user_input)

log "AI Response: " + ai_response
ai_response`,

        'iot': `use "iot"
use "events"

// IoT automation system
device("register", "sensor_1", {"type": "temperature", "location": "room1"})
device("register", "actuator_1", {"type": "smart_switch", "location": "room1"})

// Event-driven automation
on event "sensor_reading" handle_sensor_data

function handle_sensor_data(data) {
    log "Sensor reading: " + data.value
    
    if data.value > 25
        device("command", "actuator_1", {"action": "turn_on"})
        log "Actuator activated due to high reading"
}

// Simulate sensor reading
var reading = device("read", "sensor_1")
trigger("sensor_reading", {"value": reading, "sensor": "sensor_1"})`,

        'pipeline': `use "pipeline"
use "ai_v3"

// Data processing pipeline
pipeline("create", "data_processor", [
    {"type": "validate", "params": {"required_fields": ["text", "timestamp"]}},
    {"type": "clean", "params": {"remove_special_chars": true}},
    {"type": "ai_analyze", "params": {"model": "gpt-3.5", "task": "sentiment"}},
    {"type": "store", "params": {"table": "processed_data"}}
])

// Process data through pipeline
var input_data = {
    "text": "This is sample data for processing",
    "timestamp": "2024-01-01T10:00:00Z",
    "source": "user_input"
}

var result = pipeline("run", "data_processor", input_data)
log "Pipeline result: " + result.status
log "Processed data ID: " + result.id`,

        'api': `use "http"

// API integration with error handling
var api_endpoint = "https://api.example.com/data"
var headers = {"Authorization": "Bearer YOUR_TOKEN", "Content-Type": "application/json"}
var payload = {"query": "${prompt}", "limit": 10}

try {
    var response = trigger(api_endpoint, payload, "POST", headers)
    
    if response.status_code == 200
        log "API call successful"
        var data = response.data
        
        // Process response data
        for item in data.items
            log "Item: " + item.name + " - " + item.description
        
        data
    else
        log "API error: " + response.status_code + " - " + response.message
        null
} catch error {
    log "Request failed: " + error.message
    null
}`,

        'chatbot': `use "ai_v3"
use "agents"

// AI-powered chatbot
agent("create", "customer_service", {
    "model": "gpt-3.5-turbo",
    "prompt": "You are a helpful customer service assistant",
    "tools": ["query", "trigger", "log"]
})

function process_user_message(message) {
    // Classify intent
    var intent = ai("Classify the intent of this message: " + message)
    log "Detected intent: " + intent
    
    // Generate contextual response
    var context = {"user_message": message, "intent": intent}
    var response = agent("think", "customer_service", context)
    
    log "Bot response: " + response
    return response
}

// Example usage
var user_input = "I need help with my order"
var bot_response = process_user_message(user_input)
log "Final response: " + bot_response`,

        'database': `use "db"

// Database operations with transactions
try {
    // Start transaction
    query("BEGIN TRANSACTION")
    
    // Create user
    var user_id = query("INSERT INTO users (name, email) VALUES (?, ?) RETURNING id", 
                       ["John Doe", "john@example.com"])
    log "User created with ID: " + user_id
    
    // Create user profile
    query("INSERT INTO profiles (user_id, preferences) VALUES (?, ?)", 
          [user_id, '{"theme": "dark", "notifications": true}'])
    log "Profile created for user: " + user_id
    
    // Commit transaction
    query("COMMIT")
    log "Transaction completed successfully"
    
    user_id
} catch error {
    query("ROLLBACK")
    log "Transaction failed: " + error.message
    null
}`
    };

    // Enhanced keyword matching
    const prompt_lower = prompt.toLowerCase();
    
    if (prompt_lower.includes('ai') || prompt_lower.includes('artificial intelligence') || prompt_lower.includes('chatbot') || prompt_lower.includes('chat')) {
        return prompt_lower.includes('chatbot') || prompt_lower.includes('chat') ? templates.chatbot : templates.ai;
    }
    if (prompt_lower.includes('iot') || prompt_lower.includes('sensor') || prompt_lower.includes('device') || prompt_lower.includes('automation')) {
        return templates.iot;
    }
    if (prompt_lower.includes('pipeline') || prompt_lower.includes('data processing') || prompt_lower.includes('etl')) {
        return templates.pipeline;
    }
    if (prompt_lower.includes('api') || prompt_lower.includes('http') || prompt_lower.includes('rest') || prompt_lower.includes('endpoint')) {
        return templates.api;
    }
    if (prompt_lower.includes('database') || prompt_lower.includes('sql') || prompt_lower.includes('query') || prompt_lower.includes('user management')) {
        return templates.database;
    }

    // Default: AI-powered solution
    return `// Generated MCN code for: ${prompt}
use "ai_v3"

// Register AI model
register("gpt-3.5", "openai", {"temperature": 0.7})
set_model("gpt-3.5")

// Process the request
var request = "${prompt}"
var result = run("gpt-3.5", "Help me with: " + request)

log "Request: " + request
log "AI Result: " + result

result`;
}

async function explainMcnCode(code: string): Promise<string> {
    if (code === 'current') {
        // Get current editor content
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return "No active MCN file to explain.";
        }
        code = editor.document.getText();
    }

    // Simple code analysis for explanation
    const lines = code.split('\n').filter(line => line.trim());
    let explanation = "MCN Code Explanation:\n\n";

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('//')) {
            continue; // Skip comments
        }
        
        if (trimmed.startsWith('use ')) {
            const pkg = trimmed.match(/use "(.+)"/)?.[1];
            explanation += `• Imports the '${pkg}' package for enhanced functionality\n`;
        } else if (trimmed.startsWith('var ')) {
            const varName = trimmed.split('=')[0].replace('var ', '').trim();
            explanation += `• Declares variable '${varName}'\n`;
        } else if (trimmed.startsWith('function ')) {
            const funcName = trimmed.split('(')[0].replace('function ', '').trim();
            explanation += `• Defines function '${funcName}'\n`;
        } else if (trimmed.includes('register(')) {
            explanation += `• Registers an AI model for use\n`;
        } else if (trimmed.includes('device(')) {
            explanation += `• Performs IoT device operation\n`;
        } else if (trimmed.includes('pipeline(')) {
            explanation += `• Executes data pipeline operation\n`;
        } else if (trimmed.includes('query(')) {
            explanation += `• Executes database query\n`;
        } else if (trimmed.includes('trigger(')) {
            explanation += `• Makes HTTP API call\n`;
        } else if (trimmed.includes('log ')) {
            explanation += `• Outputs log message\n`;
        }
    }

    explanation += "\nThis MCN script demonstrates modern features like AI integration, IoT automation, and data processing capabilities.";
    return explanation;
}

async function validateMcnScript(code: string): Promise<any[]> {
    const diagnostics = [];
    const lines = code.split('\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Check for common syntax errors
        if (line.includes('var ') && !line.includes('=') && !line.endsWith('{')) {
            diagnostics.push({
                line: i + 1,
                message: 'Variable declaration missing assignment',
                severity: 'error'
            });
        }
        
        // Check for unmatched quotes
        const quotes = (line.match(/"/g) || []).length;
        if (quotes % 2 !== 0) {
            diagnostics.push({
                line: i + 1,
                message: 'Unmatched quotes',
                severity: 'error'
            });
        }
        
        // Check for missing 'use' statements for v3 features
        if ((line.includes('register(') || line.includes('set_model(') || line.includes('run(')) && !code.includes('use "ai_v3"')) {
            diagnostics.push({
                line: i + 1,
                message: 'AI v3 functions require: use "ai_v3"',
                severity: 'warning'
            });
        }
    }

    return diagnostics;
}

async function generateMcnTests(code: string): Promise<string> {
    const lines = code.split('\n');
    let tests = `// Auto-generated tests for MCN script\n// Generated on ${new Date().toISOString()}\n\n`;
    
    // Extract functions for testing
    const functions = lines.filter(line => line.trim().startsWith('function '))
                          .map(line => line.trim().split('(')[0].replace('function ', ''));
    
    if (functions.length > 0) {
        tests += `// Function tests\n`;
        for (const func of functions) {
            tests += `\n// Test ${func}\ntry {\n    var result = ${func}("test_input")\n    log "${func} test passed: " + result\n} catch error {\n    log "${func} test failed: " + error.message\n}\n`;
        }
    }
    
    // Add integration tests
    tests += `\n// Integration tests\nlog "Starting integration tests..."\n\n`;
    
    if (code.includes('use "ai_v3"')) {
        tests += `// AI integration test\ntry {\n    var ai_test = ai("test prompt")\n    log "AI integration test passed"\n} catch error {\n    log "AI integration test failed: " + error.message\n}\n\n`;
    }
    
    if (code.includes('query(')) {
        tests += `// Database test\ntry {\n    var db_test = query("SELECT 1 as test")\n    log "Database test passed"\n} catch error {\n    log "Database test failed: " + error.message\n}\n\n`;
    }
    
    tests += `log "All tests completed"`;
    
    return tests;
}
