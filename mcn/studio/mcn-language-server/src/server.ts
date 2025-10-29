import {
  createConnection,
  TextDocuments,
  ProposedFeatures,
  InitializeParams,
  DidChangeConfigurationNotification,
  CompletionItem,
  CompletionItemKind,
  TextDocumentPositionParams,
  TextDocumentSyncKind,
  InitializeResult,
  DocumentDiagnosticReportKind,
  type DocumentDiagnosticReport
} from 'vscode-languageserver/node';

import { TextDocument } from 'vscode-languageserver-textdocument';

const connection = createConnection(ProposedFeatures.all);
const documents: TextDocuments<TextDocument> = new TextDocuments(TextDocument);

let hasConfigurationCapability = false;
let hasWorkspaceFolderCapability = false;
let hasDiagnosticRelatedInformationCapability = false;

connection.onInitialize((params: InitializeParams) => {
  const capabilities = params.capabilities;

  hasConfigurationCapability = !!(
    capabilities.workspace && !!capabilities.workspace.configuration
  );
  hasWorkspaceFolderCapability = !!(
    capabilities.workspace && !!capabilities.workspace.workspaceFolders
  );
  hasDiagnosticRelatedInformationCapability = !!(
    capabilities.textDocument &&
    capabilities.textDocument.publishDiagnostics &&
    capabilities.textDocument.publishDiagnostics.relatedInformation
  );

  const result: InitializeResult = {
    capabilities: {
      textDocumentSync: TextDocumentSyncKind.Incremental,
      completionProvider: {
        resolveProvider: true,
        triggerCharacters: ['.', '"', '(']
      },
      diagnosticProvider: {
        interFileDependencies: false,
        workspaceDiagnostics: false
      }
    }
  };

  if (hasWorkspaceFolderCapability) {
    result.capabilities.workspace = {
      workspaceFolders: {
        supported: true
      }
    };
  }
  return result;
});

connection.onInitialized(() => {
  if (hasConfigurationCapability) {
    connection.client.register(DidChangeConfigurationNotification.type, undefined);
  }
  if (hasWorkspaceFolderCapability) {
    connection.workspace.onDidChangeWorkspaceFolders(_event => {
      connection.console.log('Workspace folder change event received.');
    });
  }
});

// MCN built-in functions for completion
const mcnBuiltins: CompletionItem[] = [
  {
    label: 'log',
    kind: CompletionItemKind.Function,
    data: 1,
    detail: 'log(message)',
    documentation: 'Print message to console with timestamp'
  },
  {
    label: 'echo',
    kind: CompletionItemKind.Function,
    data: 2,
    detail: 'echo(message)',
    documentation: 'Output message without timestamp'
  },
  {
    label: 'query',
    kind: CompletionItemKind.Function,
    data: 3,
    detail: 'query(sql, params)',
    documentation: 'Execute SQL query on database'
  },
  {
    label: 'trigger',
    kind: CompletionItemKind.Function,
    data: 4,
    detail: 'trigger(url, payload, method, headers)',
    documentation: 'Make HTTP request to API endpoint'
  },
  {
    label: 'ai',
    kind: CompletionItemKind.Function,
    data: 5,
    detail: 'ai(prompt, model, options)',
    documentation: 'Call AI model for text generation'
  },
  {
    label: 'use',
    kind: CompletionItemKind.Function,
    data: 6,
    detail: 'use("package")',
    documentation: 'Load MCN package functions'
  },
  {
    label: 'task',
    kind: CompletionItemKind.Function,
    data: 7,
    detail: 'task(name, func, args)',
    documentation: 'Create async task'
  },
  {
    label: 'await',
    kind: CompletionItemKind.Function,
    data: 8,
    detail: 'await(tasks...)',
    documentation: 'Wait for task completion'
  },
  {
    label: 'type',
    kind: CompletionItemKind.Function,
    data: 9,
    detail: 'type(var, type)',
    documentation: 'Set type hint for variable'
  },
  // v3.0 AI Functions
  {
    label: 'register',
    kind: CompletionItemKind.Function,
    data: 10,
    detail: 'register(name, provider, config)',
    documentation: 'Register AI model with configuration'
  },
  {
    label: 'set_model',
    kind: CompletionItemKind.Function,
    data: 11,
    detail: 'set_model(model_name)',
    documentation: 'Set active AI model'
  },
  {
    label: 'run',
    kind: CompletionItemKind.Function,
    data: 12,
    detail: 'run(model, prompt, options)',
    documentation: 'Execute AI model with prompt'
  },
  // IoT Functions
  {
    label: 'device',
    kind: CompletionItemKind.Function,
    data: 13,
    detail: 'device(action, device_id, params)',
    documentation: 'Interact with IoT devices'
  },
  // Event System
  {
    label: 'on',
    kind: CompletionItemKind.Function,
    data: 14,
    detail: 'on event "event_name" handler_function',
    documentation: 'Register event handler'
  },
  // Pipeline Functions
  {
    label: 'pipeline',
    kind: CompletionItemKind.Function,
    data: 15,
    detail: 'pipeline(action, name, config)',
    documentation: 'Create and manage data pipelines'
  },
  // Agent Functions
  {
    label: 'agent',
    kind: CompletionItemKind.Function,
    data: 16,
    detail: 'agent(action, name, config)',
    documentation: 'Create and manage autonomous agents'
  },
  // Natural Language
  {
    label: 'translate',
    kind: CompletionItemKind.Function,
    data: 17,
    detail: 'translate(text, execute)',
    documentation: 'Translate natural language to MCN code'
  }
];

// MCN keywords
const mcnKeywords: CompletionItem[] = [
  {
    label: 'var',
    kind: CompletionItemKind.Keyword,
    data: 20,
    detail: 'var name = value',
    documentation: 'Declare a variable'
  },
  {
    label: 'if',
    kind: CompletionItemKind.Keyword,
    data: 21,
    detail: 'if condition',
    documentation: 'Conditional statement'
  },
  {
    label: 'else',
    kind: CompletionItemKind.Keyword,
    data: 22,
    detail: 'else',
    documentation: 'Alternative branch'
  },
  {
    label: 'while',
    kind: CompletionItemKind.Keyword,
    data: 23,
    detail: 'while condition',
    documentation: 'Loop statement'
  },
  {
    label: 'for',
    kind: CompletionItemKind.Keyword,
    data: 24,
    detail: 'for item in collection',
    documentation: 'For loop statement'
  },
  {
    label: 'function',
    kind: CompletionItemKind.Keyword,
    data: 25,
    detail: 'function name(params)',
    documentation: 'Function declaration'
  },
  {
    label: 'try',
    kind: CompletionItemKind.Keyword,
    data: 26,
    detail: 'try',
    documentation: 'Error handling block'
  },
  {
    label: 'catch',
    kind: CompletionItemKind.Keyword,
    data: 27,
    detail: 'catch error',
    documentation: 'Error catch block'
  },
  {
    label: 'return',
    kind: CompletionItemKind.Keyword,
    data: 28,
    detail: 'return value',
    documentation: 'Return value from function'
  },
  {
    label: 'event',
    kind: CompletionItemKind.Keyword,
    data: 29,
    detail: 'event "event_name"',
    documentation: 'Event declaration for handlers'
  }
];

// MCN packages for completion
const mcnPackages: CompletionItem[] = [
  {
    label: '"ai_v3"',
    kind: CompletionItemKind.Module,
    data: 30,
    detail: 'use "ai_v3"',
    documentation: 'AI v3.0 features: register, set_model, run'
  },
  {
    label: '"iot"',
    kind: CompletionItemKind.Module,
    data: 31,
    detail: 'use "iot"',
    documentation: 'IoT device management and automation'
  },
  {
    label: '"events"',
    kind: CompletionItemKind.Module,
    data: 32,
    detail: 'use "events"',
    documentation: 'Event-driven programming support'
  },
  {
    label: '"pipeline"',
    kind: CompletionItemKind.Module,
    data: 33,
    detail: 'use "pipeline"',
    documentation: 'Data processing pipelines'
  },
  {
    label: '"agents"',
    kind: CompletionItemKind.Module,
    data: 34,
    detail: 'use "agents"',
    documentation: 'Autonomous agent management'
  },
  {
    label: '"natural"',
    kind: CompletionItemKind.Module,
    data: 35,
    detail: 'use "natural"',
    documentation: 'Natural language processing'
  },
  {
    label: '"db"',
    kind: CompletionItemKind.Module,
    data: 36,
    detail: 'use "db"',
    documentation: 'Database operations and connectivity'
  },
  {
    label: '"http"',
    kind: CompletionItemKind.Module,
    data: 37,
    detail: 'use "http"',
    documentation: 'HTTP client and API integration'
  }
];

connection.onCompletion(
  (params: TextDocumentPositionParams): CompletionItem[] => {
    const document = documents.get(params.textDocument.uri);
    if (!document) {
      return [];
    }

    const text = document.getText();
    const position = params.position;
    const line = text.split('\n')[position.line];
    const beforeCursor = line.substring(0, position.character);

    // Context-aware completions
    if (beforeCursor.includes('use ')) {
      return mcnPackages;
    }
    
    if (beforeCursor.includes('on event ')) {
      return [
        {
          label: '"sensor_reading"',
          kind: CompletionItemKind.Event,
          detail: 'IoT sensor reading event'
        },
        {
          label: '"user_action"',
          kind: CompletionItemKind.Event,
          detail: 'User interaction event'
        },
        {
          label: '"system_alert"',
          kind: CompletionItemKind.Event,
          detail: 'System alert event'
        }
      ];
    }

    return [...mcnBuiltins, ...mcnKeywords];
  }
);

connection.onCompletionResolve(
  (item: CompletionItem): CompletionItem => {
    // Enhanced documentation for MCN functions
    const docs = {
      1: { detail: 'MCN logging function', doc: 'Prints message to console with timestamp. Usage: log "message"' },
      2: { detail: 'MCN output function', doc: 'Outputs message without timestamp. Usage: echo "message"' },
      10: { detail: 'AI model registration', doc: 'Register AI model with provider and configuration. Usage: register("model-name", "provider", {config})' },
      11: { detail: 'AI model selection', doc: 'Set the active AI model for subsequent operations. Usage: set_model("model-name")' },
      12: { detail: 'AI model execution', doc: 'Execute AI model with prompt and options. Usage: run("model", "prompt", {options})' },
      13: { detail: 'IoT device interaction', doc: 'Interact with IoT devices. Usage: device("action", "device_id", {params})' },
      15: { detail: 'Data pipeline management', doc: 'Create and manage data processing pipelines. Usage: pipeline("create", "name", [steps])' },
      16: { detail: 'Autonomous agent management', doc: 'Create and manage AI agents. Usage: agent("create", "name", {config})' },
      17: { detail: 'Natural language translation', doc: 'Translate natural language to MCN code. Usage: translate("description", execute_flag)' }
    };

    if (item.data && docs[item.data as number]) {
      const info = docs[item.data as number];
      item.detail = info.detail;
      item.documentation = info.doc;
    }
    
    return item;
  }
);

connection.languages.onDocumentDiagnostic(async (params) => {
  const document = documents.get(params.textDocument.uri);
  if (document !== undefined) {
    return {
      kind: DocumentDiagnosticReportKind.Full,
      items: validateMCNDocument(document)
    } satisfies DocumentDiagnosticReport;
  } else {
    return {
      kind: DocumentDiagnosticReportKind.Full,
      items: []
    } satisfies DocumentDiagnosticReport;
  }
});

function validateMCNDocument(textDocument: TextDocument) {
  const text = textDocument.getText();
  const diagnostics = [];
  const lines = text.split('\n');
  const usedPackages = new Set<string>();

  // Extract used packages
  for (const line of lines) {
    const useMatch = line.match(/use\s+"([^"]+)"/);
    if (useMatch) {
      usedPackages.add(useMatch[1]);
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const originalLine = lines[i];

    // Skip comments
    if (line.startsWith('//')) continue;

    // Check for common MCN syntax errors
    if (line.includes('var ') && !line.includes('=') && !line.endsWith('{')) {
      diagnostics.push({
        severity: 1, // Error
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Variable declaration missing assignment',
        source: 'mcn'
      });
    }

    // Check for unmatched quotes
    const quotes = (line.match(/"/g) || []).length;
    if (quotes % 2 !== 0) {
      diagnostics.push({
        severity: 1, // Error
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Unmatched quotes',
        source: 'mcn'
      });
    }

    // Check for missing package imports
    if ((line.includes('register(') || line.includes('set_model(') || line.includes('run(')) && !usedPackages.has('ai_v3')) {
      diagnostics.push({
        severity: 2, // Warning
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'AI v3 functions require: use "ai_v3"',
        source: 'mcn'
      });
    }

    if (line.includes('device(') && !usedPackages.has('iot')) {
      diagnostics.push({
        severity: 2, // Warning
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'IoT functions require: use "iot"',
        source: 'mcn'
      });
    }

    if (line.includes('pipeline(') && !usedPackages.has('pipeline')) {
      diagnostics.push({
        severity: 2, // Warning
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Pipeline functions require: use "pipeline"',
        source: 'mcn'
      });
    }

    if (line.includes('agent(') && !usedPackages.has('agents')) {
      diagnostics.push({
        severity: 2, // Warning
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Agent functions require: use "agents"',
        source: 'mcn'
      });
    }

    // Check for function syntax
    if (line.startsWith('function ') && !line.includes('(')) {
      diagnostics.push({
        severity: 1, // Error
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Function declaration missing parentheses',
        source: 'mcn'
      });
    }

    // Check for event handler syntax
    if (line.includes('on event') && !line.includes('"')) {
      diagnostics.push({
        severity: 1, // Error
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: originalLine.length }
        },
        message: 'Event name must be in quotes',
        source: 'mcn'
      });
    }
  }

  return diagnostics;
}

documents.onDidChangeContent(change => {
  // Validate document on change
});

documents.listen(connection);
connection.listen();
