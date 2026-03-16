import {
  createConnection,
  TextDocuments,
  ProposedFeatures,
  InitializeParams,
  DidChangeConfigurationNotification,
  CompletionItem,
  CompletionItemKind,
  InsertTextFormat,
  TextDocumentPositionParams,
  TextDocumentSyncKind,
  InitializeResult,
  DocumentDiagnosticReportKind,
  DiagnosticSeverity,
  Hover,
  MarkupKind,
  type DocumentDiagnosticReport
} from 'vscode-languageserver/node';

import { TextDocument } from 'vscode-languageserver-textdocument';

const connection = createConnection(ProposedFeatures.all);
const documents: TextDocuments<TextDocument> = new TextDocuments(TextDocument);

let hasConfigurationCapability       = false;
let hasWorkspaceFolderCapability     = false;

connection.onInitialize((params: InitializeParams) => {
  const caps = params.capabilities;
  hasConfigurationCapability      = !!(caps.workspace?.configuration);
  hasWorkspaceFolderCapability    = !!(caps.workspace?.workspaceFolders);
  // relatedInformation capability noted but not used in current diagnostics

  const result: InitializeResult = {
    capabilities: {
      textDocumentSync:   TextDocumentSyncKind.Incremental,
      completionProvider: {
        resolveProvider:   true,
        triggerCharacters: ['.', '"', '(', '{']
      },
      hoverProvider: true,
      diagnosticProvider: {
        interFileDependencies: false,
        workspaceDiagnostics:  false
      }
    }
  };

  if (hasWorkspaceFolderCapability) {
    result.capabilities.workspace = { workspaceFolders: { supported: true } };
  }
  return result;
});

connection.onInitialized(() => {
  if (hasConfigurationCapability) {
    connection.client.register(DidChangeConfigurationNotification.type, undefined);
  }
});


// ── Completion items ──────────────────────────────────────────────────────────

/** AI built-in functions */
const AI_BUILTINS: CompletionItem[] = [
  {
    label: 'ai',
    kind: CompletionItemKind.Function,
    detail: 'ai(prompt, opts?) → str',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Call AI (Anthropic / OpenAI) for text generation.\n\n```mcn\nvar reply = ai("Summarize: " + text)\nvar reply = ai("Translate", {model: "claude-3-5-sonnet-20241022", temperature: 0.3})\n```'
    },
    insertText: 'ai("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'llm',
    kind: CompletionItemKind.Function,
    detail: 'llm(model, prompt, opts?) → str',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'AI call with explicit model selection. Prefix routes to provider.\n\n```mcn\nvar r = llm("claude-3-5-sonnet-20241022", "Summarize: " + text)\nvar r = llm("gpt-4o", "Explain: " + topic)\n```'
    },
    insertText: 'llm("$1", "$2")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'embed',
    kind: CompletionItemKind.Function,
    detail: 'embed(text) → float[]',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Get a vector embedding for semantic search / similarity.\n\n```mcn\nvar vec = embed("customer query")\n```'
    },
    insertText: 'embed("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'extract',
    kind: CompletionItemKind.Function,
    detail: 'extract(text, Contract) → object',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Structured AI extraction — returns an object matching the contract schema.\n\n```mcn\ncontract Order\n    id:     int\n    item:   str\n    amount: float\n\nvar order = extract(raw_text, Order)\nlog(order.item)\n```'
    },
    insertText: 'extract($1, $2)',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'classify',
    kind: CompletionItemKind.Function,
    detail: 'classify(text, labels) → str',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Zero-shot classification — returns the best matching label.\n\n```mcn\nvar intent = classify(message, ["buy", "return", "support"])\n```'
    },
    insertText: 'classify($1, [$2])',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'checkpoint',
    kind: CompletionItemKind.Function,
    detail: 'checkpoint(message, data?)',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Human-in-the-loop pause — shows data and prompts [y/n/edit] before continuing.\n\n```mcn\ncheckpoint("Review before sending", reply)\n```'
    },
    insertText: 'checkpoint("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  }
];

/** Core built-in functions */
const CORE_BUILTINS: CompletionItem[] = [
  {
    label: 'log',
    kind: CompletionItemKind.Function,
    detail: 'log(message)',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Print to console with timestamp.\n\n```mcn\nlog("Hello {name}")\n```'
    },
    insertText: 'log($1)',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'echo',
    kind: CompletionItemKind.Function,
    detail: 'echo(message)',
    documentation: { kind: MarkupKind.Markdown, value: 'Alias for `log()`.' },
    insertText: 'echo($1)',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'fetch',
    kind: CompletionItemKind.Function,
    detail: 'fetch(url, headers?) → object',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'HTTP GET request.\n\n```mcn\nvar data = fetch("https://api.example.com/users")\nlog(data.name)\n```'
    },
    insertText: 'fetch("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'trigger',
    kind: CompletionItemKind.Function,
    detail: 'trigger(url, payload, method?) → object',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'HTTP POST (or any method).\n\n```mcn\nvar res = trigger("https://api.example.com/orders", {id: order_id})\n```'
    },
    insertText: 'trigger("$1", {$2})',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'query',
    kind: CompletionItemKind.Function,
    detail: 'query(sql, params?) → list',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Execute a SQL query. Use tuple for parameters (avoids SQL injection).\n\n```mcn\nvar users = query("SELECT * FROM users WHERE active = ?", (true,))\n```'
    },
    insertText: 'query("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'env',
    kind: CompletionItemKind.Function,
    detail: 'env(key) → str',
    documentation: {
      kind: MarkupKind.Markdown,
      value: 'Read an environment variable.\n\n```mcn\nvar key = env("STRIPE_SECRET_KEY")\n```'
    },
    insertText: 'env("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'read_file',
    kind: CompletionItemKind.Function,
    detail: 'read_file(path) → str',
    insertText: 'read_file("$1")',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'write_file',
    kind: CompletionItemKind.Function,
    detail: 'write_file(path, content)',
    insertText: 'write_file("$1", $2)',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'append_file',
    kind: CompletionItemKind.Function,
    detail: 'append_file(path, content)',
    insertText: 'append_file("$1", $2)',
    insertTextFormat: InsertTextFormat.Snippet
  }
];

/** Language keywords */
const KEYWORDS: CompletionItem[] = [
  { label: 'var',      kind: CompletionItemKind.Keyword, insertText: 'var $1 = $2', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'if',       kind: CompletionItemKind.Keyword, insertText: 'if $1\n    $2', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'else',     kind: CompletionItemKind.Keyword },
  { label: 'for',      kind: CompletionItemKind.Keyword, insertText: 'for $1 in $2\n    $3', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'while',    kind: CompletionItemKind.Keyword, insertText: 'while $1\n    $2', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'function', kind: CompletionItemKind.Keyword, insertText: 'function $1($2)\n    $3', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'return',   kind: CompletionItemKind.Keyword, insertText: 'return $1', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'break',    kind: CompletionItemKind.Keyword },
  { label: 'continue', kind: CompletionItemKind.Keyword },
  { label: 'try',      kind: CompletionItemKind.Keyword, insertText: 'try\n    $1\ncatch\n    $2', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'catch',    kind: CompletionItemKind.Keyword },
  { label: 'throw',    kind: CompletionItemKind.Keyword, insertText: 'throw "$1"', insertTextFormat: InsertTextFormat.Snippet },
  { label: 'and',      kind: CompletionItemKind.Keyword },
  { label: 'or',       kind: CompletionItemKind.Keyword },
  { label: 'not',      kind: CompletionItemKind.Keyword },
  { label: 'in',       kind: CompletionItemKind.Keyword },
  { label: 'true',     kind: CompletionItemKind.Constant },
  { label: 'false',    kind: CompletionItemKind.Constant },
  { label: 'null',     kind: CompletionItemKind.Constant }
];

/** Domain primitive snippets */
const DOMAIN_SNIPPETS: CompletionItem[] = [
  {
    label: 'contract',
    kind: CompletionItemKind.Class,
    detail: 'contract Name — define a typed schema',
    insertText: 'contract ${1:Name}\n    ${2:field}: ${3:str}',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'pipeline',
    kind: CompletionItemKind.Module,
    detail: 'pipeline — define a data pipeline with stages',
    insertText: 'pipeline ${1:name}\n    stage ${2:extract}\n        $3\n\n    stage ${4:transform}(${5:data})\n        $6',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'service',
    kind: CompletionItemKind.Module,
    detail: 'service — declare an HTTP API service',
    insertText: 'service ${1:name}\n    port ${2:8080}\n\n    endpoint ${3:get_data}(${4:id})\n        $5',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'workflow',
    kind: CompletionItemKind.Module,
    detail: 'workflow — orchestrate multi-step processes',
    insertText: 'workflow ${1:name}\n    step ${2:validate}(${3:input})\n        $4\n\n    step ${5:process}(${6:data})\n        $7',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'prompt',
    kind: CompletionItemKind.Module,
    detail: 'prompt — reusable AI prompt template',
    insertText: 'prompt ${1:name}\n    system "${2:You are a helpful assistant.}"\n    user   "${3:{{message}}}"\n    format ${4:text}',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'agent',
    kind: CompletionItemKind.Module,
    detail: 'agent — AI agent with tasks and memory',
    insertText: 'agent ${1:name}\n    model  "${2:claude-3-5-sonnet-20241022}"\n    tools  ${3:ai, fetch}\n    memory ${4:session}\n\n    task ${5:run}(${6:input})\n        $7',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'test',
    kind: CompletionItemKind.Module,
    detail: 'test — define a test block',
    insertText: 'test "${1:description}"\n    ${2:assert $3}',
    insertTextFormat: InsertTextFormat.Snippet
  },
  {
    label: 'assert',
    kind: CompletionItemKind.Keyword,
    detail: 'assert condition [, message]',
    insertText: 'assert $1',
    insertTextFormat: InsertTextFormat.Snippet
  }
];

const ALL_COMPLETIONS = [...AI_BUILTINS, ...CORE_BUILTINS, ...KEYWORDS, ...DOMAIN_SNIPPETS];


// ── Completion handler ────────────────────────────────────────────────────────

connection.onCompletion((_pos: TextDocumentPositionParams): CompletionItem[] => {
  return ALL_COMPLETIONS;
});

connection.onCompletionResolve((item: CompletionItem): CompletionItem => item);


// ── Hover handler ─────────────────────────────────────────────────────────────

const HOVER_DOCS: Record<string, string> = {
  ai:         '**ai(prompt, opts?)** → `str`\n\nUniversal AI call. Reads `MCN_AI_PROVIDER` or auto-detects from API keys.',
  llm:        '**llm(model, prompt)** → `str`\n\nAI call with explicit model. Prefix routes to provider (`claude-*` → Anthropic, `gpt-*` → OpenAI).',
  embed:      '**embed(text)** → `float[]`\n\nVector embedding for semantic search.',
  extract:    '**extract(text, Contract)** → `object`\n\nStructured AI extraction matching a contract schema.',
  classify:   '**classify(text, labels)** → `str`\n\nZero-shot classification — returns the best label.',
  checkpoint: '**checkpoint(msg, data?)** \n\nHuman-in-the-loop pause. Prompts [y/n/edit].',
  log:        '**log(message)**\n\nPrint to console with timestamp.',
  fetch:      '**fetch(url, headers?)** → `object`\n\nHTTP GET.',
  trigger:    '**trigger(url, payload, method?)** → `object`\n\nHTTP POST (or any method).',
  query:      '**query(sql, params?)** → `list`\n\nSQL query. Use tuple params to prevent injection.',
  env:        '**env(key)** → `str`\n\nRead environment variable.',
  contract:   '**contract** — Typed schema definition.\n\nUsed with `extract()` for structured AI output.',
  pipeline:   '**pipeline** — Data pipeline with named stages.',
  service:    '**service** — HTTP API service declaration.',
  workflow:   '**workflow** — Multi-step process orchestration.',
  prompt:     '**prompt** — Reusable AI prompt template with `{{variable}}` interpolation.',
  agent:      '**agent** — AI agent with model, tools, memory, and callable tasks.',
};

connection.onHover((params): Hover | null => {
  const doc  = documents.get(params.textDocument.uri);
  if (!doc) return null;

  const text  = doc.getText();
  const offset = doc.offsetAt(params.position);

  // Walk backwards to find word start
  let start = offset;
  while (start > 0 && /[a-zA-Z_]/.test(text[start - 1])) start--;
  let end = offset;
  while (end < text.length && /[a-zA-Z_]/.test(text[end])) end++;

  const word = text.slice(start, end);
  const docs = HOVER_DOCS[word];
  if (!docs) return null;

  return {
    contents: { kind: MarkupKind.Markdown, value: docs }
  };
});


// ── Diagnostics ───────────────────────────────────────────────────────────────

connection.languages.onDocumentDiagnostic(async (params: { textDocument: { uri: string } }) => {
  const doc = documents.get(params.textDocument.uri);
  return {
    kind:  DocumentDiagnosticReportKind.Full,
    items: doc ? validateDocument(doc) : []
  } satisfies DocumentDiagnosticReport;
});

function validateDocument(doc: TextDocument) {
  const text  = doc.getText();
  const lines = text.split('\n');
  const diags: any[] = [];

  for (let i = 0; i < lines.length; i++) {
    const raw      = lines[i];
    const trimmed  = raw.trimStart();
    const indent   = raw.length - trimmed.length;

    // Skip comments and blank lines
    if (trimmed.startsWith('//') || trimmed === '') continue;

    // var without = (and not a continuation line)
    if (/^var\s+\w+\s*$/.test(trimmed)) {
      diags.push({
        severity: DiagnosticSeverity.Error,
        range:    { start: { line: i, character: indent }, end: { line: i, character: raw.length } },
        message:  'Variable declaration requires an assignment: `var name = value`',
        source:   'mcn'
      });
    }

    // function without body hint (next non-blank line should be indented)
    if (/^function\s+\w+/.test(trimmed)) {
      let nextIdx = i + 1;
      while (nextIdx < lines.length && lines[nextIdx].trim() === '') nextIdx++;
      if (nextIdx < lines.length) {
        const nextIndent = lines[nextIdx].length - lines[nextIdx].trimStart().length;
        if (nextIndent <= indent && lines[nextIdx].trim() !== '') {
          diags.push({
            severity: DiagnosticSeverity.Warning,
            range:    { start: { line: i, character: indent }, end: { line: i, character: raw.length } },
            message:  'Function body should be indented',
            source:   'mcn'
          });
        }
      }
    }

    // assert outside test block (warn)
    if (/^assert\b/.test(trimmed) && indent === 0) {
      diags.push({
        severity: DiagnosticSeverity.Warning,
        range:    { start: { line: i, character: 0 }, end: { line: i, character: raw.length } },
        message:  '`assert` at top level — did you mean to put this inside a `test` block?',
        source:   'mcn'
      });
    }
  }

  return diags;
}

documents.listen(connection);
connection.listen();
