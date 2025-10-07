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
    label: 'query',
    kind: CompletionItemKind.Function,
    data: 2,
    detail: 'query(sql, params)',
    documentation: 'Execute SQL query on database'
  },
  {
    label: 'trigger',
    kind: CompletionItemKind.Function,
    data: 3,
    detail: 'trigger(url, payload, method)',
    documentation: 'Make HTTP request to API endpoint'
  },
  {
    label: 'ai',
    kind: CompletionItemKind.Function,
    data: 4,
    detail: 'ai(prompt, model, max_tokens)',
    documentation: 'Call AI model for text generation'
  },
  {
    label: 'use',
    kind: CompletionItemKind.Function,
    data: 5,
    detail: 'use("package")',
    documentation: 'Load MCN package functions'
  },
  {
    label: 'task',
    kind: CompletionItemKind.Function,
    data: 6,
    detail: 'task(name, func, args)',
    documentation: 'Create async task'
  },
  {
    label: 'await',
    kind: CompletionItemKind.Function,
    data: 7,
    detail: 'await(tasks...)',
    documentation: 'Wait for task completion'
  },
  {
    label: 'type',
    kind: CompletionItemKind.Function,
    data: 8,
    detail: 'type(var, type)',
    documentation: 'Set type hint for variable'
  }
];

// MCN keywords
const mcnKeywords: CompletionItem[] = [
  {
    label: 'var',
    kind: CompletionItemKind.Keyword,
    data: 10,
    detail: 'var name = value',
    documentation: 'Declare a variable'
  },
  {
    label: 'if',
    kind: CompletionItemKind.Keyword,
    data: 11,
    detail: 'if condition',
    documentation: 'Conditional statement'
  },
  {
    label: 'else',
    kind: CompletionItemKind.Keyword,
    data: 12,
    detail: 'else',
    documentation: 'Alternative branch'
  },
  {
    label: 'while',
    kind: CompletionItemKind.Keyword,
    data: 13,
    detail: 'while condition',
    documentation: 'Loop statement'
  },
  {
    label: 'try',
    kind: CompletionItemKind.Keyword,
    data: 14,
    detail: 'try',
    documentation: 'Error handling block'
  },
  {
    label: 'catch',
    kind: CompletionItemKind.Keyword,
    data: 15,
    detail: 'catch',
    documentation: 'Error catch block'
  }
];

connection.onCompletion(
  (_textDocumentPosition: TextDocumentPositionParams): CompletionItem[] => {
    return [...mcnBuiltins, ...mcnKeywords];
  }
);

connection.onCompletionResolve(
  (item: CompletionItem): CompletionItem => {
    if (item.data === 1) {
      item.detail = 'MCN built-in function';
      item.documentation = 'Prints message to console with timestamp';
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

  // Basic MCN syntax validation
  const lines = text.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Check for common MCN syntax errors
    if (line.includes('var ') && !line.includes('=')) {
      diagnostics.push({
        severity: 1, // Error
        range: {
          start: { line: i, character: 0 },
          end: { line: i, character: line.length }
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
          end: { line: i, character: line.length }
        },
        message: 'Unmatched quotes',
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
