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
const node_1 = require("vscode-languageserver/node");
const vscode_languageserver_textdocument_1 = require("vscode-languageserver-textdocument");
const cp = __importStar(require("child_process"));
const os = __importStar(require("os"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const connection = (0, node_1.createConnection)(node_1.ProposedFeatures.all);
const documents = new node_1.TextDocuments(vscode_languageserver_textdocument_1.TextDocument);
let hasConfigurationCapability = false;
let hasWorkspaceFolderCapability = false;
connection.onInitialize((params) => {
    const caps = params.capabilities;
    hasConfigurationCapability = !!(caps.workspace?.configuration);
    hasWorkspaceFolderCapability = !!(caps.workspace?.workspaceFolders);
    const result = {
        capabilities: {
            textDocumentSync: node_1.TextDocumentSyncKind.Incremental,
            completionProvider: {
                resolveProvider: true,
                triggerCharacters: ['.', '"', '(', '{', ' ']
            },
            hoverProvider: true,
            diagnosticProvider: {
                interFileDependencies: false,
                workspaceDiagnostics: false
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
        connection.client.register(node_1.DidChangeConfigurationNotification.type, undefined);
    }
});
// ── Completion items ──────────────────────────────────────────────────────────
function fn(label, detail, doc, insert) {
    return {
        label,
        kind: node_1.CompletionItemKind.Function,
        detail,
        documentation: { kind: node_1.MarkupKind.Markdown, value: doc },
        insertText: insert,
        insertTextFormat: node_1.InsertTextFormat.Snippet
    };
}
function kw(label, insert) {
    return {
        label,
        kind: node_1.CompletionItemKind.Keyword,
        insertText: insert ?? label,
        insertTextFormat: node_1.InsertTextFormat.Snippet
    };
}
// ── AI primitives ─────────────────────────────────────────────────────────────
const AI_BUILTINS = [
    fn('ai', 'ai(prompt, opts?) → str', 'Universal AI call (Anthropic / OpenAI / Ollama).\n\n```mcn\nvar reply = ai("Summarize: " + text)\nvar reply = ai("Translate", {model: "claude-3-5-sonnet-20241022", temperature: 0.3})\n```', 'ai("$1")'),
    fn('llm', 'llm(model, prompt, opts?) → str', 'AI call with explicit model. Prefix routes to provider.\n\n```mcn\nvar r = llm("claude-3-5-sonnet-20241022", "Summarize: " + text)\nvar r = llm("llama3", prompt)  // → Ollama\n```', 'llm("$1", "$2")'),
    fn('embed', 'embed(text) → float[]', 'Vector embedding for semantic search.\n\n```mcn\nvar vec = embed("customer query")\n```', 'embed("$1")'),
    fn('extract', 'extract(text, Contract) → object', 'Structured AI extraction matching a contract schema.\n\n```mcn\ncontract Order\n    id:   int\n    item: str\nvar order = extract(raw, Order)\n```', 'extract($1, $2)'),
    fn('classify', 'classify(text, labels) → str', 'Zero-shot classification — returns the best label.\n\n```mcn\nvar intent = classify(msg, ["buy", "return", "support"])\n```', 'classify($1, [$2])'),
    fn('checkpoint', 'checkpoint(message, data?)', 'Human-in-the-loop pause. Prompts [y/n/edit].\n\n```mcn\ncheckpoint("Review before sending", reply)\n```', 'checkpoint("$1")'),
    fn('rag', 'rag(query, docs?, template?) → str', 'Retrieval-augmented generation.\n\n```mcn\nvar answer = rag(user_query)\n```', 'rag($1)'),
];
// ── Core I/O & DB ─────────────────────────────────────────────────────────────
const CORE_BUILTINS = [
    fn('log', 'log(value)', 'Print to console with timestamp.\n\n```mcn\nlog("Hello {name}")\n```', 'log($1)'),
    fn('echo', 'echo(value)', 'Alias for `log()`.', 'echo($1)'),
    fn('fetch', 'fetch(url, opts?) → obj', 'HTTP GET/POST.\n\n```mcn\nvar data = fetch("https://api.example.com/users")\n```', 'fetch("$1")'),
    fn('trigger', 'trigger(url, payload, method?) → obj', 'HTTP POST.\n\n```mcn\ntrigger("https://api.example.com/orders", {id: id})\n```', 'trigger("$1", {$2})'),
    fn('http_get', 'http_get(url, headers?) → obj', 'HTTP GET with headers.', 'http_get("$1")'),
    fn('http_post', 'http_post(url, body?, headers?) → obj', 'HTTP POST.', 'http_post("$1", {$2})'),
    fn('http_put', 'http_put(url, body?, headers?) → obj', 'HTTP PUT.', 'http_put("$1", {$2})'),
    fn('http_delete', 'http_delete(url, headers?) → obj', 'HTTP DELETE.', 'http_delete("$1")'),
    fn('query', 'query(sql, params?) → list', 'SQL query.\n\n```mcn\nvar rows = query("SELECT * FROM users WHERE active = ?", (true,))\n```', 'query("$1")'),
    fn('query_one', 'query_one(sql, params?) → obj|null', 'SQL — first row or null.', 'query_one("$1")'),
    fn('execute', 'execute(sql, params?)', 'SQL INSERT/UPDATE/DELETE.', 'execute("$1")'),
    fn('db_insert', 'db_insert(table, row)', 'Insert dict into table.', 'db_insert("$1", $2)'),
    fn('db_update', 'db_update(table, row, where)', 'Update rows.', 'db_update("$1", $2, $3)'),
    fn('db_delete', 'db_delete(table, where)', 'Delete rows.', 'db_delete("$1", $2)'),
    fn('env', 'env(key) → str', 'Read environment variable.\n\n```mcn\nvar key = env("STRIPE_SECRET_KEY")\n```', 'env("$1")'),
    fn('read_file', 'read_file(path) → str', 'Read text file.', 'read_file("$1")'),
    fn('write_file', 'write_file(path, content)', 'Write text file.', 'write_file("$1", $2)'),
    fn('append_file', 'append_file(path, content)', 'Append to file.', 'append_file("$1", $2)'),
    fn('wait', 'wait(ms)', 'Pause execution (milliseconds).', 'wait($1)'),
];
// ── Session & Cache ───────────────────────────────────────────────────────────
const SESSION_CACHE_BUILTINS = [
    fn('session_set', 'session_set(key, value)', 'Store in current session.', 'session_set("$1", $2)'),
    fn('session_get', 'session_get(key) → any', 'Read from current session.', 'session_get("$1")'),
    fn('session_delete', 'session_delete(key)', 'Remove key from session.', 'session_delete("$1")'),
    fn('session_clear', 'session_clear()', 'Clear all session data.', 'session_clear()'),
    fn('cache_set', 'cache_set(key, value, ttl?)', 'Cache value with optional TTL (s).', 'cache_set("$1", $2)'),
    fn('cache_get', 'cache_get(key) → any|null', 'Get cached value (null if expired).', 'cache_get("$1")'),
    fn('cache_delete', 'cache_delete(key)', 'Remove item from cache.', 'cache_delete("$1")'),
    fn('memory_add', 'memory_add(text, meta?)', 'Add text to long-term memory.', 'memory_add($1)'),
    fn('memory_search', 'memory_search(query, n?) → list', 'Semantic search across memory.', 'memory_search("$1")'),
    fn('memory_clear', 'memory_clear()', 'Clear all memory entries.', 'memory_clear()'),
];
// ── Vector store ──────────────────────────────────────────────────────────────
const VECTOR_BUILTINS = [
    fn('vector_add', 'vector_add(id, text, meta?)', 'Add document to vector store.', 'vector_add("$1", $2)'),
    fn('vector_search', 'vector_search(query, n?) → list', 'Semantic similarity search.', 'vector_search("$1")'),
    fn('vector_delete', 'vector_delete(id)', 'Remove document from vector store.', 'vector_delete("$1")'),
];
// ── Auth ──────────────────────────────────────────────────────────────────────
const AUTH_BUILTINS = [
    fn('auth_hash_password', 'auth_hash_password(password) → str', 'Bcrypt-style password hash.', 'auth_hash_password($1)'),
    fn('auth_verify_password', 'auth_verify_password(password, hash) → bool', 'Verify password against hash.', 'auth_verify_password($1, $2)'),
    fn('auth_create_token', 'auth_create_token(payload, secret, ttl?) → str', 'Create JWT-style token.', 'auth_create_token($1, "$2")'),
    fn('auth_verify_token', 'auth_verify_token(token, secret) → obj|null', 'Verify and decode token.', 'auth_verify_token($1, "$2")'),
];
// ── Strings ───────────────────────────────────────────────────────────────────
const STRING_BUILTINS = [
    fn('to_upper', 'to_upper(s) → str', 'Uppercase string.', 'to_upper($1)'),
    fn('to_lower', 'to_lower(s) → str', 'Lowercase string.', 'to_lower($1)'),
    fn('trim', 'trim(s) → str', 'Strip whitespace.', 'trim($1)'),
    fn('split', 'split(s, sep) → list', 'Split string by separator.', 'split($1, "$2")'),
    fn('join', 'join(list, sep) → str', 'Join list into string.', 'join($1, "$2")'),
    fn('replace', 'replace(s, old, new) → str', 'Replace all occurrences.', 'replace($1, "$2", "$3")'),
    fn('starts_with', 'starts_with(s, prefix) → bool', 'Check if string starts with prefix.', 'starts_with($1, "$2")'),
    fn('ends_with', 'ends_with(s, suffix) → bool', 'Check if string ends with suffix.', 'ends_with($1, "$2")'),
    fn('contains', 'contains(s, sub) → bool', 'Check if string/list contains value.', 'contains($1, $2)'),
    fn('str_len', 'str_len(s) → int', 'String length.', 'str_len($1)'),
    fn('substr', 'substr(s, start, end?) → str', 'Substring extraction.', 'substr($1, $2)'),
    fn('format_str', 'format_str(template, args) → str', 'Format string with values.', 'format_str("$1", $2)'),
    fn('regex_match', 'regex_match(s, pattern) → bool', 'Test regex match.', 'regex_match($1, "$2")'),
    fn('regex_find', 'regex_find(s, pattern) → str|null', 'Find first regex match.', 'regex_find($1, "$2")'),
    fn('regex_replace', 'regex_replace(s, pattern, repl) → str', 'Replace via regex.', 'regex_replace($1, "$2", "$3")'),
    fn('to_str', 'to_str(v) → str', 'Convert value to string.', 'to_str($1)'),
    fn('to_int', 'to_int(v) → int', 'Convert value to integer.', 'to_int($1)'),
    fn('to_float', 'to_float(v) → float', 'Convert value to float.', 'to_float($1)'),
    fn('to_bool', 'to_bool(v) → bool', 'Convert value to bool.', 'to_bool($1)'),
];
// ── Arrays ────────────────────────────────────────────────────────────────────
const ARRAY_BUILTINS = [
    fn('len', 'len(list) → int', 'Length of list or string.', 'len($1)'),
    fn('push', 'push(list, value)', 'Append value to list.', 'push($1, $2)'),
    fn('pop', 'pop(list) → any', 'Remove and return last element.', 'pop($1)'),
    fn('shift', 'shift(list) → any', 'Remove and return first element.', 'shift($1)'),
    fn('unshift', 'unshift(list, value)', 'Prepend value to list.', 'unshift($1, $2)'),
    fn('slice', 'slice(list, start, end?) → list', 'Extract sub-list.', 'slice($1, $2)'),
    fn('map', 'map(list, fn) → list', 'Transform list elements.\n\n```mcn\nvar doubled = map(nums, n => n * 2)\n```', 'map($1, $2 => $3)'),
    fn('filter', 'filter(list, fn) → list', 'Keep elements matching predicate.\n\n```mcn\nvar evens = filter(nums, n => n % 2 == 0)\n```', 'filter($1, $2 => $3)'),
    fn('reduce', 'reduce(list, fn, init) → any', 'Accumulate list into single value.', 'reduce($1, ($2, $3) => $4, $5)'),
    fn('find', 'find(list, fn) → any|null', 'Find first matching element.', 'find($1, $2 => $3)'),
    fn('sort', 'sort(list, key?) → list', 'Sort list (returns sorted copy).', 'sort($1)'),
    fn('reverse', 'reverse(list) → list', 'Reverse list.', 'reverse($1)'),
    fn('unique', 'unique(list) → list', 'Remove duplicates.', 'unique($1)'),
    fn('flat', 'flat(list) → list', 'Flatten one level of nesting.', 'flat($1)'),
    fn('zip', 'zip(a, b) → list', 'Zip two lists into list of pairs.', 'zip($1, $2)'),
    fn('range', 'range(n) / range(start, end) → list', 'Generate integer range.', 'range($1)'),
    fn('sum', 'sum(list) → number', 'Sum numeric list.', 'sum($1)'),
    fn('avg', 'avg(list) → number', 'Average of numeric list.', 'avg($1)'),
    fn('min', 'min(list) → number', 'Minimum value.', 'min($1)'),
    fn('max', 'max(list) → number', 'Maximum value.', 'max($1)'),
    fn('count', 'count(list, val?) → int', 'Count elements.', 'count($1)'),
    fn('group_by', 'group_by(list, key) → obj', 'Group items by key into dict.', 'group_by($1, "$2")'),
];
// ── Objects / Dict ────────────────────────────────────────────────────────────
const OBJECT_BUILTINS = [
    fn('keys', 'keys(obj) → list', 'List of dict keys.', 'keys($1)'),
    fn('values', 'values(obj) → list', 'List of dict values.', 'values($1)'),
    fn('has_key', 'has_key(obj, key) → bool', 'Check if dict has key.', 'has_key($1, "$2")'),
    fn('merge', 'merge(obj1, obj2) → obj', 'Merge two dicts (obj2 wins).', 'merge($1, $2)'),
    fn('json_parse', 'json_parse(s) → obj', 'Parse JSON string.', 'json_parse($1)'),
    fn('json_str', 'json_str(obj) → str', 'Serialize to JSON string.', 'json_str($1)'),
    fn('pick', 'pick(obj, keys) → obj', 'Select subset of keys.', 'pick($1, [$2])'),
    fn('omit', 'omit(obj, keys) → obj', 'Exclude keys from object.', 'omit($1, [$2])'),
];
// ── Math ──────────────────────────────────────────────────────────────────────
const MATH_BUILTINS = [
    fn('abs', 'abs(n) → number', 'Absolute value.', 'abs($1)'),
    fn('ceil', 'ceil(n) → int', 'Round up.', 'ceil($1)'),
    fn('floor', 'floor(n) → int', 'Round down.', 'floor($1)'),
    fn('round', 'round(n, places?) → number', 'Round to decimal places.', 'round($1)'),
    fn('sqrt', 'sqrt(n) → float', 'Square root.', 'sqrt($1)'),
    fn('pow', 'pow(base, exp) → number', 'Power: base^exp.', 'pow($1, $2)'),
    fn('random', 'random() → float', 'Random float 0.0–1.0.', 'random()'),
    fn('random_int', 'random_int(min, max) → int', 'Random integer.', 'random_int($1, $2)'),
];
// ── Date / Time ───────────────────────────────────────────────────────────────
const DATE_BUILTINS = [
    fn('now', 'now() → str', 'Current UTC timestamp (ISO 8601).', 'now()'),
    fn('date_parse', 'date_parse(s) → obj', 'Parse date string.', 'date_parse($1)'),
    fn('date_format', 'date_format(ts, fmt) → str', 'Format timestamp.', 'date_format($1, "$2")'),
    fn('date_add', 'date_add(ts, n, unit) → str', 'Add time to timestamp.', 'date_add($1, $2, "$3")'),
    fn('date_diff', 'date_diff(a, b, unit) → num', 'Difference between timestamps.', 'date_diff($1, $2, "$3")'),
];
// ── Queue ─────────────────────────────────────────────────────────────────────
const QUEUE_BUILTINS = [
    fn('queue_push', 'queue_push(name, msg)', 'Enqueue a message.', 'queue_push("$1", $2)'),
    fn('queue_pop', 'queue_pop(name) → any|null', 'Dequeue the next message.', 'queue_pop("$1")'),
    fn('queue_peek', 'queue_peek(name) → any|null', 'Peek at next message.', 'queue_peek("$1")'),
    fn('queue_len', 'queue_len(name) → int', 'Number of messages in queue.', 'queue_len("$1")'),
];
// ── Crypto / UUID ─────────────────────────────────────────────────────────────
const CRYPTO_BUILTINS = [
    fn('uuid', 'uuid() → str', 'Generate UUID v4.', 'uuid()'),
    fn('hash_sha256', 'hash_sha256(s) → str', 'SHA-256 hex digest.', 'hash_sha256($1)'),
    fn('hash_md5', 'hash_md5(s) → str', 'MD5 hex digest.', 'hash_md5($1)'),
    fn('base64_encode', 'base64_encode(s) → str', 'Base64 encode.', 'base64_encode($1)'),
    fn('base64_decode', 'base64_decode(s) → str', 'Base64 decode.', 'base64_decode($1)'),
];
// ── Keywords ──────────────────────────────────────────────────────────────────
const KEYWORDS = [
    kw('var', 'var $1 = $2'),
    kw('if', 'if $1\n    $2'),
    kw('else'),
    kw('else if', 'else if $1\n    $2'),
    kw('for', 'for $1 in $2\n    $3'),
    kw('while', 'while $1\n    $2'),
    kw('function', 'function $1($2)\n    $3'),
    kw('return', 'return $1'),
    kw('break'),
    kw('continue'),
    kw('try', 'try\n    $1\ncatch $2\n    $3'),
    kw('catch'),
    kw('finally'),
    kw('throw', 'throw "$1"'),
    kw('use', 'use "$1"'),
    kw('and'),
    kw('or'),
    kw('not'),
    kw('in'),
    { label: 'true', kind: node_1.CompletionItemKind.Constant },
    { label: 'false', kind: node_1.CompletionItemKind.Constant },
    { label: 'null', kind: node_1.CompletionItemKind.Constant },
];
// ── Domain snippets ───────────────────────────────────────────────────────────
const DOMAIN_SNIPPETS = [
    {
        label: 'contract',
        kind: node_1.CompletionItemKind.Class,
        detail: 'contract — define a typed schema',
        insertText: 'contract ${1:Name}\n    ${2:field}: ${3:str}',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'pipeline',
        kind: node_1.CompletionItemKind.Module,
        detail: 'pipeline — data pipeline with stages',
        insertText: 'pipeline ${1:name}\n    stage ${2:extract}\n        $3\n\n    stage ${4:transform}(${5:data})\n        $6',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'service',
        kind: node_1.CompletionItemKind.Module,
        detail: 'service — HTTP API service',
        insertText: 'service ${1:name}\n    port ${2:8080}\n\n    endpoint ${3:get_data}(${4:id})\n        $5',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'workflow',
        kind: node_1.CompletionItemKind.Module,
        detail: 'workflow — multi-step process orchestration',
        insertText: 'workflow ${1:name}\n    step ${2:validate}(${3:input})\n        $4\n\n    step ${5:process}(${6:data})\n        $7',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'prompt',
        kind: node_1.CompletionItemKind.Module,
        detail: 'prompt — reusable AI prompt template',
        insertText: 'prompt ${1:name}\n    system "${2:You are a helpful assistant.}"\n    user   "${3:{{message}}}"\n    format ${4:text}',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'agent',
        kind: node_1.CompletionItemKind.Module,
        detail: 'agent — AI agent with model, tools, memory',
        insertText: 'agent ${1:name}\n    model  "${2:claude-3-5-sonnet-20241022}"\n    tools  ${3:ai, fetch}\n    memory ${4:session}\n\n    task ${5:run}(${6:input})\n        $7',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'component',
        kind: node_1.CompletionItemKind.Module,
        detail: 'component — UI component with state and render',
        insertText: 'component ${1:Name}\n    state ${2:value} = ${3:""}\n\n    on ${4:submit}\n        $5\n\n    render\n        card\n            input bind=${2:value} label="${6:Label}"\n            button "Submit"',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'app',
        kind: node_1.CompletionItemKind.Module,
        detail: 'app — full application declaration',
        insertText: 'app ${1:AppName}\n    title  "${2:My App}"\n    theme  "${3:default}"\n\n    layout\n        main\n            ${4:MyComponent}',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'test',
        kind: node_1.CompletionItemKind.Module,
        detail: 'test — test block',
        insertText: 'test "${1:description}"\n    assert $2',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'assert',
        kind: node_1.CompletionItemKind.Keyword,
        detail: 'assert condition [, message]',
        insertText: 'assert $1',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
    {
        label: 'use',
        kind: node_1.CompletionItemKind.Keyword,
        detail: 'use "package" — import a package',
        insertText: 'use "$1"',
        insertTextFormat: node_1.InsertTextFormat.Snippet
    },
];
const ALL_COMPLETIONS = [
    ...AI_BUILTINS,
    ...CORE_BUILTINS,
    ...SESSION_CACHE_BUILTINS,
    ...VECTOR_BUILTINS,
    ...AUTH_BUILTINS,
    ...STRING_BUILTINS,
    ...ARRAY_BUILTINS,
    ...OBJECT_BUILTINS,
    ...MATH_BUILTINS,
    ...DATE_BUILTINS,
    ...QUEUE_BUILTINS,
    ...CRYPTO_BUILTINS,
    ...KEYWORDS,
    ...DOMAIN_SNIPPETS,
];
// ── Completion handler ────────────────────────────────────────────────────────
connection.onCompletion((_pos) => {
    return ALL_COMPLETIONS;
});
connection.onCompletionResolve((item) => item);
// ── Hover handler ─────────────────────────────────────────────────────────────
const HOVER_DOCS = {
    // AI
    ai: '**ai(prompt, opts?)** → `str`\n\nUniversal AI call. Auto-detects provider from `MCN_AI_PROVIDER`, `ANTHROPIC_API_KEY`, `OLLAMA_URL`.',
    llm: '**llm(model, prompt, opts?)** → `str`\n\nAI call with explicit model. `claude-*` → Anthropic, `gpt-*` → OpenAI, `llama*`/`mistral*` → Ollama.',
    embed: '**embed(text)** → `float[]`\n\nVector embedding for semantic search.',
    extract: '**extract(text, Contract)** → `object`\n\nStructured AI extraction matching a contract schema.',
    classify: '**classify(text, labels)** → `str`\n\nZero-shot classification — returns the best label.',
    checkpoint: '**checkpoint(msg, data?)**\n\nHuman-in-the-loop pause. Prompts [y/n/edit].',
    rag: '**rag(query, docs?, template?)** → `str`\n\nRetrieval-augmented generation. Searches vector store then calls AI.',
    // Core
    log: '**log(message)**\n\nPrint to console with timestamp.',
    echo: '**echo(message)**\n\nAlias for `log()`.',
    fetch: '**fetch(url, opts?)** → `object`\n\nHTTP GET/POST request.',
    trigger: '**trigger(url, payload, method?)** → `object`\n\nHTTP POST (default) to a URL.',
    query: '**query(sql, params?)** → `list`\n\nSQL query. Use tuple params to prevent injection.',
    query_one: '**query_one(sql, params?)** → `object|null`\n\nSQL — returns first row or null.',
    execute: '**execute(sql, params?)**\n\nSQL INSERT/UPDATE/DELETE.',
    env: '**env(key)** → `str`\n\nRead environment variable.',
    // Strings
    to_str: '**to_str(v)** → `str`\n\nConvert any value to string.',
    to_int: '**to_int(v)** → `int`\n\nConvert to integer.',
    to_float: '**to_float(v)** → `float`\n\nConvert to float.',
    to_bool: '**to_bool(v)** → `bool`\n\nConvert to boolean.',
    split: '**split(s, sep)** → `list`\n\nSplit string by separator.',
    join: '**join(list, sep)** → `str`\n\nJoin list elements into a string.',
    replace: '**replace(s, old, new)** → `str`\n\nReplace all occurrences.',
    trim: '**trim(s)** → `str`\n\nStrip leading/trailing whitespace.',
    // Arrays
    len: '**len(list)** → `int`\n\nLength of list or string.',
    map: '**map(list, fn)** → `list`\n\nTransform elements: `map(nums, n => n * 2)`',
    filter: '**filter(list, fn)** → `list`\n\nKeep matching elements: `filter(items, x => x.active)`',
    reduce: '**reduce(list, fn, init)** → `any`\n\nAccumulate into single value.',
    sort: '**sort(list, key?)** → `list`\n\nSort list, returns sorted copy.',
    range: '**range(n)** or **range(start, end)** → `list`\n\nGenerate integer range.',
    sum: '**sum(list)** → `number`\n\nSum a numeric list.',
    // Math
    abs: '**abs(n)** → `number`\n\nAbsolute value.',
    round: '**round(n, places?)** → `number`\n\nRound to decimal places.',
    random: '**random()** → `float`\n\nRandom float in [0, 1).',
    random_int: '**random_int(min, max)** → `int`\n\nRandom integer in [min, max].',
    // Date
    now: '**now()** → `str`\n\nCurrent UTC timestamp as ISO 8601 string.',
    // Crypto
    uuid: '**uuid()** → `str`\n\nGenerate a UUID v4.',
    hash_sha256: '**hash_sha256(s)** → `str`\n\nSHA-256 hex digest.',
    base64_encode: '**base64_encode(s)** → `str`\n\nBase64-encode a string.',
    base64_decode: '**base64_decode(s)** → `str`\n\nBase64-decode a string.',
    // Auth
    auth_create_token: '**auth_create_token(payload, secret, ttl?)** → `str`\n\nCreate JWT-style signed token.',
    auth_verify_token: '**auth_verify_token(token, secret)** → `object|null`\n\nVerify and decode token.',
    // Domain
    contract: '**contract** — Typed schema definition. Used with `extract()` for structured AI output.',
    pipeline: '**pipeline** — Data pipeline with named stages. Each stage\'s return feeds the next.',
    service: '**service** — HTTP API service. Declares endpoints served on the given port.',
    workflow: '**workflow** — Multi-step process orchestration.',
    prompt: '**prompt** — Reusable AI prompt template with `{{variable}}` interpolation.',
    agent: '**agent** — AI agent with model, tools, memory, and callable tasks.',
    component: '**component** — UI component with reactive state, event handlers, and a render block.',
    app: '**app** — Full application declaration with layout, navigation and routing.',
    use: '**use "package"** — Import a package. Built-ins: `stripe`, `twilio`, `resend`, `slack`, `openai`, `ollama`, `healthcare`, `finance`.',
};
connection.onHover((params) => {
    const doc = documents.get(params.textDocument.uri);
    if (!doc)
        return null;
    const text = doc.getText();
    const offset = doc.offsetAt(params.position);
    let start = offset;
    while (start > 0 && /[a-zA-Z0-9_]/.test(text[start - 1]))
        start--;
    let end = offset;
    while (end < text.length && /[a-zA-Z0-9_]/.test(text[end]))
        end++;
    const word = text.slice(start, end);
    const docs = HOVER_DOCS[word];
    if (!docs)
        return null;
    return { contents: { kind: node_1.MarkupKind.Markdown, value: docs } };
});
// ── Diagnostics ───────────────────────────────────────────────────────────────
/** Run `mcn check` as subprocess, parse output. Resolves quickly. */
async function validateWithCLI(doc) {
    return new Promise((resolve) => {
        const tmp = path.join(os.tmpdir(), `mcn_check_${Date.now()}.mcn`);
        try {
            fs.writeFileSync(tmp, doc.getText(), 'utf8');
        }
        catch {
            resolve(validateDocument(doc));
            return;
        }
        cp.exec(`mcn check "${tmp}"`, { timeout: 10000 }, (err, stdout, stderr) => {
            try {
                fs.unlinkSync(tmp);
            }
            catch { /* ignore */ }
            const output = stdout + '\n' + (stderr || '');
            const diags = [];
            for (const line of output.split('\n')) {
                // Match:  path:[line:col] error   message
                //      or path:[line:col] warning  message
                const m = line.match(/\[(\d+):(\d+)\]\s+(error|warning)\s+(.*)/i);
                if (m) {
                    const [, lineStr, colStr, sev, msg] = m;
                    const ln = Math.max(0, parseInt(lineStr, 10) - 1);
                    const col = Math.max(0, parseInt(colStr, 10) - 1);
                    diags.push({
                        severity: sev.toLowerCase() === 'error'
                            ? node_1.DiagnosticSeverity.Error
                            : node_1.DiagnosticSeverity.Warning,
                        range: {
                            start: { line: ln, character: col },
                            end: { line: ln, character: 1000 }
                        },
                        message: msg.trim(),
                        source: 'mcn'
                    });
                }
            }
            // If CLI succeeded but produced no parseable diagnostics, fall back to
            // lightweight regex checks so the server still gives useful feedback.
            resolve(diags.length > 0 ? diags : validateDocument(doc));
        });
    });
}
/** Lightweight regex-based validation (fallback when `mcn` is not on PATH). */
function validateDocument(doc) {
    const text = doc.getText();
    const lines = text.split('\n');
    const diags = [];
    for (let i = 0; i < lines.length; i++) {
        const raw = lines[i];
        const trimmed = raw.trimStart();
        const indent = raw.length - trimmed.length;
        if (trimmed.startsWith('//') || trimmed === '')
            continue;
        // var without assignment
        if (/^var\s+\w+\s*$/.test(trimmed)) {
            diags.push({
                severity: node_1.DiagnosticSeverity.Error,
                range: { start: { line: i, character: indent }, end: { line: i, character: raw.length } },
                message: 'Variable declaration requires an assignment: `var name = value`',
                source: 'mcn'
            });
        }
        // function body indentation
        if (/^function\s+\w+/.test(trimmed)) {
            let next = i + 1;
            while (next < lines.length && lines[next].trim() === '')
                next++;
            if (next < lines.length) {
                const ni = lines[next].length - lines[next].trimStart().length;
                if (ni <= indent && lines[next].trim() !== '') {
                    diags.push({
                        severity: node_1.DiagnosticSeverity.Warning,
                        range: { start: { line: i, character: indent }, end: { line: i, character: raw.length } },
                        message: 'Function body should be indented',
                        source: 'mcn'
                    });
                }
            }
        }
        // top-level assert
        if (/^assert\b/.test(trimmed) && indent === 0) {
            diags.push({
                severity: node_1.DiagnosticSeverity.Warning,
                range: { start: { line: i, character: 0 }, end: { line: i, character: raw.length } },
                message: '`assert` at top level — did you mean to put this inside a `test` block?',
                source: 'mcn'
            });
        }
    }
    return diags;
}
connection.languages.diagnostics.on(async (params) => {
    const doc = documents.get(params.textDocument.uri);
    const items = doc ? await validateWithCLI(doc) : [];
    return {
        kind: node_1.DocumentDiagnosticReportKind.Full,
        items
    };
});
documents.listen(connection);
connection.listen();
//# sourceMappingURL=server.js.map