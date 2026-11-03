// ── Monaco init ─────────────────────────────────────────────────────────
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' } })
require(['vs/editor/editor.main'], function () {

  monaco.languages.register({ id: 'mcn' })
  monaco.languages.setMonarchTokensProvider('mcn', {
    keywords: ['var','function','return','if','else','for','in','while','break','continue',
               'try','catch','throw','true','false','null','and','or','not',
               'contract','service','endpoint','agent','task','pipeline','stage',
               'workflow','step','prompt','system','user','format','memory',
               'component','state','on','render','app','title','theme','layout',
               'tabs','tab','sidebar','nav','route','test','assert'],
    builtins: ['log','echo','fetch','http_get','http_post','http_put','http_delete',
               'query','query_one','execute','db_insert','db_update','db_delete',
               'ai','llm','embed','extract','classify','checkpoint','rag',
               'session_set','session_get','session_delete','session_clear',
               'cache_set','cache_get','cache_delete',
               'memory_add','memory_search','memory_clear',
               'vector_add','vector_search','vector_delete',
               'auth_hash_password','auth_verify_password','auth_create_token','auth_verify_token',
               'to_upper','to_lower','trim','split','join','replace','starts_with','ends_with',
               'contains','str_len','substr','format_str','regex_match','regex_find','regex_replace',
               'to_str','to_int','to_float','to_bool',
               'len','push','pop','shift','unshift','slice','map','filter','reduce','find',
               'sort','reverse','unique','flat','zip','range','sum','avg','min','max',
               'count','group_by','keys','values','has_key','merge',
               'json_parse','json_str','pick','omit',
               'abs','ceil','floor','round','sqrt','pow','random','random_int',
               'now','date_parse','date_format','date_add','date_diff',
               'queue_push','queue_pop','queue_peek','queue_len',
               'uuid','hash_sha256','hash_md5','base64_encode','base64_decode',
               'trigger','wait','read_file','write_file','env'],
    tokenizer: {
      root: [
        [/\/\/.*$/, 'comment'],
        [/"""[\s\S]*?"""/, 'string'],
        [/"(?:[^"\\]|\\.)*"/, 'string'],
        [/\b(true|false|null)\b/, 'constant.language'],
        [/\b\d+(\.\d+)?\b/, 'number'],
        [/\b(var|function|return|if|else|for|in|while|break|continue|try|catch|finally|throw|and|or|not|use)\b/, 'keyword'],
        [/\b(contract|service|endpoint|agent|task|pipeline|stage|workflow|step|prompt)\b/, 'keyword.declaration'],
        [/\b(component|state|on|render|app|title|theme|layout|tabs|tab|sidebar|nav|route)\b/, 'keyword.control'],
        [/\b(test|assert)\b/, 'keyword.other'],
        [/\b(log|echo|fetch|http_get|http_post|http_put|http_delete|query|query_one|execute|db_insert|db_update|db_delete|ai|llm|embed|extract|classify|checkpoint|rag|session_set|session_get|session_delete|session_clear|cache_set|cache_get|cache_delete|memory_add|memory_search|memory_clear|vector_add|vector_search|vector_delete|auth_hash_password|auth_verify_password|auth_create_token|auth_verify_token|to_upper|to_lower|trim|split|join|replace|starts_with|ends_with|contains|str_len|substr|format_str|regex_match|regex_find|regex_replace|to_str|to_int|to_float|to_bool|len|push|pop|shift|unshift|slice|map|filter|reduce|find|sort|reverse|unique|flat|zip|range|sum|avg|min|max|count|group_by|keys|values|has_key|merge|json_parse|json_str|pick|omit|abs|ceil|floor|round|sqrt|pow|random|random_int|now|date_parse|date_format|date_add|date_diff|queue_push|queue_pop|queue_peek|queue_len|uuid|hash_sha256|hash_md5|base64_encode|base64_decode|trigger|wait|read_file|write_file|env)\b/, 'support.function'],
        [/[a-zA-Z_]\w*/, 'identifier'],
      ]
    }
  })

  // ── IntelliSense: completion items ──────────────────────────────────────
  const _CK = monaco.languages.CompletionItemKind
  const _mcnBuiltins = [
    // Core I/O
    { label: 'log',         kind: _CK.Function, detail: 'log(value)',               documentation: 'Print value to console/output' },
    { label: 'echo',        kind: _CK.Function, detail: 'echo(value)',              documentation: 'Alias for log()' },
    { label: 'read_file',   kind: _CK.Function, detail: 'read_file(path)',          documentation: 'Read text file contents' },
    { label: 'write_file',  kind: _CK.Function, detail: 'write_file(path, content)', documentation: 'Write text to file' },
    { label: 'env',         kind: _CK.Function, detail: 'env(key)',                 documentation: 'Read environment variable' },
    // HTTP
    { label: 'fetch',       kind: _CK.Function, detail: 'fetch(url, options?)',     documentation: 'HTTP GET/POST request' },
    { label: 'http_get',    kind: _CK.Function, detail: 'http_get(url, headers?)', documentation: 'HTTP GET' },
    { label: 'http_post',   kind: _CK.Function, detail: 'http_post(url, body?, headers?)', documentation: 'HTTP POST' },
    { label: 'http_put',    kind: _CK.Function, detail: 'http_put(url, body?, headers?)',  documentation: 'HTTP PUT' },
    { label: 'http_delete', kind: _CK.Function, detail: 'http_delete(url, headers?)',      documentation: 'HTTP DELETE' },
    // DB
    { label: 'query',       kind: _CK.Function, detail: 'query(sql, params?)',      documentation: 'Run SQL query, returns list of rows' },
    { label: 'query_one',   kind: _CK.Function, detail: 'query_one(sql, params?)', documentation: 'Run SQL, return first row or null' },
    { label: 'execute',     kind: _CK.Function, detail: 'execute(sql, params?)',   documentation: 'Run SQL INSERT/UPDATE/DELETE' },
    { label: 'db_insert',   kind: _CK.Function, detail: 'db_insert(table, row)',   documentation: 'Insert a dict into a table' },
    { label: 'db_update',   kind: _CK.Function, detail: 'db_update(table, row, where)', documentation: 'Update rows in a table' },
    { label: 'db_delete',   kind: _CK.Function, detail: 'db_delete(table, where)', documentation: 'Delete rows from a table' },
    // AI
    { label: 'ai',          kind: _CK.Function, detail: 'ai(prompt, options?)',     documentation: 'Call AI with a prompt. Options: {model, temperature, system}' },
    { label: 'llm',         kind: _CK.Function, detail: 'llm(model, prompt, opts?)', documentation: 'Explicit model call: llm("claude-3-5-sonnet", prompt)' },
    { label: 'embed',       kind: _CK.Function, detail: 'embed(text)',              documentation: 'Generate text embedding vector' },
    { label: 'extract',     kind: _CK.Function, detail: 'extract(text, contract)',  documentation: 'Extract structured data matching a contract' },
    { label: 'classify',    kind: _CK.Function, detail: 'classify(text, labels)',   documentation: 'Classify text into one of the labels' },
    { label: 'checkpoint',  kind: _CK.Function, detail: 'checkpoint(label, data)',  documentation: 'Human-in-the-loop approval step' },
    { label: 'rag',         kind: _CK.Function, detail: 'rag(query, docs?, template?)', documentation: 'Retrieval-augmented generation' },
    // Session
    { label: 'session_set', kind: _CK.Function, detail: 'session_set(key, value)', documentation: 'Store value in current session' },
    { label: 'session_get', kind: _CK.Function, detail: 'session_get(key)',        documentation: 'Read value from current session' },
    { label: 'session_delete', kind: _CK.Function, detail: 'session_delete(key)', documentation: 'Remove key from current session' },
    { label: 'session_clear', kind: _CK.Function, detail: 'session_clear()',      documentation: 'Clear all session data' },
    // Cache
    { label: 'cache_set',   kind: _CK.Function, detail: 'cache_set(key, value, ttl?)', documentation: 'Cache a value with optional TTL (seconds)' },
    { label: 'cache_get',   kind: _CK.Function, detail: 'cache_get(key)',           documentation: 'Get cached value (null if expired/absent)' },
    { label: 'cache_delete', kind: _CK.Function, detail: 'cache_delete(key)',       documentation: 'Remove item from cache' },
    // Memory
    { label: 'memory_add',  kind: _CK.Function, detail: 'memory_add(text, meta?)', documentation: 'Add text to long-term memory store' },
    { label: 'memory_search', kind: _CK.Function, detail: 'memory_search(query, n?)', documentation: 'Semantic search across memory store' },
    { label: 'memory_clear', kind: _CK.Function, detail: 'memory_clear()',         documentation: 'Clear all memory entries' },
    // Vector / RAG
    { label: 'vector_add',  kind: _CK.Function, detail: 'vector_add(id, text, meta?)', documentation: 'Add document to vector store' },
    { label: 'vector_search', kind: _CK.Function, detail: 'vector_search(query, n?)',  documentation: 'Semantic similarity search' },
    { label: 'vector_delete', kind: _CK.Function, detail: 'vector_delete(id)',         documentation: 'Remove document from vector store' },
    // Auth
    { label: 'auth_hash_password', kind: _CK.Function, detail: 'auth_hash_password(password)', documentation: 'Bcrypt-style password hash' },
    { label: 'auth_verify_password', kind: _CK.Function, detail: 'auth_verify_password(password, hash)', documentation: 'Verify password against hash' },
    { label: 'auth_create_token', kind: _CK.Function, detail: 'auth_create_token(payload, secret, ttl?)', documentation: 'Create JWT-style token' },
    { label: 'auth_verify_token', kind: _CK.Function, detail: 'auth_verify_token(token, secret)', documentation: 'Verify and decode token' },
    // Strings
    { label: 'to_upper',    kind: _CK.Function, detail: 'to_upper(s)',             documentation: 'Uppercase string' },
    { label: 'to_lower',    kind: _CK.Function, detail: 'to_lower(s)',             documentation: 'Lowercase string' },
    { label: 'trim',        kind: _CK.Function, detail: 'trim(s)',                 documentation: 'Strip whitespace from both ends' },
    { label: 'split',       kind: _CK.Function, detail: 'split(s, sep)',           documentation: 'Split string by separator' },
    { label: 'join',        kind: _CK.Function, detail: 'join(list, sep)',         documentation: 'Join list into string' },
    { label: 'replace',     kind: _CK.Function, detail: 'replace(s, old, new)',    documentation: 'Replace all occurrences' },
    { label: 'starts_with', kind: _CK.Function, detail: 'starts_with(s, prefix)', documentation: 'Check if string starts with prefix' },
    { label: 'ends_with',   kind: _CK.Function, detail: 'ends_with(s, suffix)',   documentation: 'Check if string ends with suffix' },
    { label: 'contains',    kind: _CK.Function, detail: 'contains(s, sub)',        documentation: 'Check if string/list contains value' },
    { label: 'str_len',     kind: _CK.Function, detail: 'str_len(s)',              documentation: 'String length' },
    { label: 'substr',      kind: _CK.Function, detail: 'substr(s, start, end?)', documentation: 'Substring extraction' },
    { label: 'format_str',  kind: _CK.Function, detail: 'format_str(template, args)', documentation: 'Format string with values' },
    { label: 'regex_match', kind: _CK.Function, detail: 'regex_match(s, pattern)', documentation: 'Test regex match' },
    { label: 'regex_find',  kind: _CK.Function, detail: 'regex_find(s, pattern)', documentation: 'Find first regex match' },
    { label: 'regex_replace', kind: _CK.Function, detail: 'regex_replace(s, pattern, repl)', documentation: 'Replace via regex' },
    { label: 'to_str',      kind: _CK.Function, detail: 'to_str(v)',              documentation: 'Convert value to string' },
    { label: 'to_int',      kind: _CK.Function, detail: 'to_int(v)',              documentation: 'Convert value to integer' },
    { label: 'to_float',    kind: _CK.Function, detail: 'to_float(v)',            documentation: 'Convert value to float' },
    { label: 'to_bool',     kind: _CK.Function, detail: 'to_bool(v)',             documentation: 'Convert value to bool' },
    // Arrays
    { label: 'len',         kind: _CK.Function, detail: 'len(list)',              documentation: 'Length of list or string' },
    { label: 'push',        kind: _CK.Function, detail: 'push(list, value)',      documentation: 'Append value to list (mutates)' },
    { label: 'pop',         kind: _CK.Function, detail: 'pop(list)',              documentation: 'Remove and return last element' },
    { label: 'shift',       kind: _CK.Function, detail: 'shift(list)',            documentation: 'Remove and return first element' },
    { label: 'unshift',     kind: _CK.Function, detail: 'unshift(list, value)',   documentation: 'Prepend value to list' },
    { label: 'slice',       kind: _CK.Function, detail: 'slice(list, start, end?)', documentation: 'Extract sub-list' },
    { label: 'map',         kind: _CK.Function, detail: 'map(list, fn)',          documentation: 'Transform list elements' },
    { label: 'filter',      kind: _CK.Function, detail: 'filter(list, fn)',       documentation: 'Keep elements matching predicate' },
    { label: 'reduce',      kind: _CK.Function, detail: 'reduce(list, fn, init)', documentation: 'Accumulate list into single value' },
    { label: 'find',        kind: _CK.Function, detail: 'find(list, fn)',         documentation: 'Find first matching element' },
    { label: 'sort',        kind: _CK.Function, detail: 'sort(list, key?)',       documentation: 'Sort list (returns sorted copy)' },
    { label: 'reverse',     kind: _CK.Function, detail: 'reverse(list)',          documentation: 'Reverse list (returns reversed copy)' },
    { label: 'unique',      kind: _CK.Function, detail: 'unique(list)',           documentation: 'Remove duplicate elements' },
    { label: 'flat',        kind: _CK.Function, detail: 'flat(list)',             documentation: 'Flatten one level of nesting' },
    { label: 'zip',         kind: _CK.Function, detail: 'zip(a, b)',              documentation: 'Zip two lists into list of pairs' },
    { label: 'range',       kind: _CK.Function, detail: 'range(n) / range(start, end)', documentation: 'Generate integer range list' },
    { label: 'sum',         kind: _CK.Function, detail: 'sum(list)',              documentation: 'Sum numeric list' },
    { label: 'avg',         kind: _CK.Function, detail: 'avg(list)',              documentation: 'Average of numeric list' },
    { label: 'min',         kind: _CK.Function, detail: 'min(list)',              documentation: 'Minimum value in list' },
    { label: 'max',         kind: _CK.Function, detail: 'max(list)',              documentation: 'Maximum value in list' },
    { label: 'count',       kind: _CK.Function, detail: 'count(list, val?)',      documentation: 'Count elements (or occurrences of val)' },
    { label: 'group_by',    kind: _CK.Function, detail: 'group_by(list, key)',    documentation: 'Group list items by key into dict' },
    // Object / dict
    { label: 'keys',        kind: _CK.Function, detail: 'keys(obj)',              documentation: 'List of dict keys' },
    { label: 'values',      kind: _CK.Function, detail: 'values(obj)',            documentation: 'List of dict values' },
    { label: 'has_key',     kind: _CK.Function, detail: 'has_key(obj, key)',      documentation: 'Check if dict has key' },
    { label: 'merge',       kind: _CK.Function, detail: 'merge(obj1, obj2)',      documentation: 'Merge two dicts (obj2 wins)' },
    { label: 'json_parse',  kind: _CK.Function, detail: 'json_parse(s)',          documentation: 'Parse JSON string to object' },
    { label: 'json_str',    kind: _CK.Function, detail: 'json_str(obj)',          documentation: 'Serialize object to JSON string' },
    { label: 'pick',        kind: _CK.Function, detail: 'pick(obj, keys)',        documentation: 'Select subset of object keys' },
    { label: 'omit',        kind: _CK.Function, detail: 'omit(obj, keys)',        documentation: 'Exclude keys from object' },
    // Math
    { label: 'abs',         kind: _CK.Function, detail: 'abs(n)',                documentation: 'Absolute value' },
    { label: 'ceil',        kind: _CK.Function, detail: 'ceil(n)',               documentation: 'Round up' },
    { label: 'floor',       kind: _CK.Function, detail: 'floor(n)',              documentation: 'Round down' },
    { label: 'round',       kind: _CK.Function, detail: 'round(n, places?)',     documentation: 'Round to decimal places' },
    { label: 'sqrt',        kind: _CK.Function, detail: 'sqrt(n)',               documentation: 'Square root' },
    { label: 'pow',         kind: _CK.Function, detail: 'pow(base, exp)',        documentation: 'Power: base ^ exp' },
    { label: 'random',      kind: _CK.Function, detail: 'random()',             documentation: 'Random float 0.0–1.0' },
    { label: 'random_int',  kind: _CK.Function, detail: 'random_int(min, max)', documentation: 'Random integer in [min, max]' },
    // Date / time
    { label: 'now',         kind: _CK.Function, detail: 'now()',                 documentation: 'Current UTC timestamp (ISO string)' },
    { label: 'date_parse',  kind: _CK.Function, detail: 'date_parse(s)',         documentation: 'Parse date string to timestamp dict' },
    { label: 'date_format', kind: _CK.Function, detail: 'date_format(ts, fmt)',  documentation: 'Format timestamp with strftime pattern' },
    { label: 'date_add',    kind: _CK.Function, detail: 'date_add(ts, n, unit)', documentation: 'Add time to timestamp' },
    { label: 'date_diff',   kind: _CK.Function, detail: 'date_diff(a, b, unit)', documentation: 'Difference between two timestamps' },
    // Queue
    { label: 'queue_push',  kind: _CK.Function, detail: 'queue_push(name, msg)', documentation: 'Enqueue a message' },
    { label: 'queue_pop',   kind: _CK.Function, detail: 'queue_pop(name)',       documentation: 'Dequeue the next message' },
    { label: 'queue_peek',  kind: _CK.Function, detail: 'queue_peek(name)',      documentation: 'Peek at next message without removing' },
    { label: 'queue_len',   kind: _CK.Function, detail: 'queue_len(name)',       documentation: 'Number of messages in queue' },
    // Crypto / ID
    { label: 'uuid',        kind: _CK.Function, detail: 'uuid()',               documentation: 'Generate UUID v4' },
    { label: 'hash_sha256', kind: _CK.Function, detail: 'hash_sha256(s)',       documentation: 'SHA-256 hex digest' },
    { label: 'hash_md5',    kind: _CK.Function, detail: 'hash_md5(s)',          documentation: 'MD5 hex digest' },
    { label: 'base64_encode', kind: _CK.Function, detail: 'base64_encode(s)',   documentation: 'Base64 encode' },
    { label: 'base64_decode', kind: _CK.Function, detail: 'base64_decode(s)',   documentation: 'Base64 decode' },
    // Workflow
    { label: 'trigger',     kind: _CK.Function, detail: 'trigger(event, data?)', documentation: 'Emit an event to trigger a handler' },
    { label: 'wait',        kind: _CK.Function, detail: 'wait(ms)',              documentation: 'Pause execution for ms milliseconds' },
    // Analytics & Reporting (use analytics)
    { label: 'report',         kind: _CK.Function, detail: 'report(table, metrics, group_by?, filter?)', documentation: 'Generate multi-dimensional aggregation report from SQLite table' },
    { label: 'generate_report',kind: _CK.Function, detail: 'generate_report(table, ...)',               documentation: 'Alias for report()' },
    { label: 'kpi',            kind: _CK.Function, detail: 'kpi(table, metric, label?, filter?)',         documentation: 'Compute single KPI metric (e.g. sum:amount, avg:price)' },
    { label: 'kpi_summary',    kind: _CK.Function, detail: 'kpi_summary(table, metrics, filter?)',       documentation: 'Compute multi-metric KPI executive summary card values' },
    { label: 'trend',          kind: _CK.Function, detail: 'trend(table, date_field, value_field, interval, agg)', documentation: 'Compute time-series trends (daily, weekly, monthly, quarterly, yearly)' },
    { label: 'distribution',   kind: _CK.Function, detail: 'distribution(table, category_field, value_field?, agg?, pareto?)', documentation: 'Compute category share distribution and Pareto 80/20 analysis' },
    { label: 'pivot',          kind: _CK.Function, detail: 'pivot(table, row_field, col_field, value_field, agg)', documentation: 'Compute 2D cross-tabulation pivot matrix' },
    { label: 'chart_data',     kind: _CK.Function, detail: 'chart_data(table, x, y, agg?, filter?)',      documentation: 'Transform table records into chart series data' },
    { label: 'export_report',  kind: _CK.Function, detail: 'export_report(report_data, format)',          documentation: 'Export report data to markdown, html, csv, or json format' },
  ]

  const _mcnKeywords = [
    'var','function','return','if','else','for','in','while','break','continue',
    'try','catch','finally','throw','true','false','null','and','or','not','use',
    'contract','service','endpoint','agent','task','pipeline','stage',
    'workflow','step','prompt','memory','component','state','on','render',
    'app','title','theme','layout','tabs','tab','sidebar','nav','route',
    'test','assert','debugger',
  ]

  const _mcnSnippets = [
    { label: 'use analytics',  kind: _CK.Snippet, insertText: 'use analytics\n\nvar summary = kpi_summary("${1:table}", metrics=["sum:${2:amount}", "count:*"])\nvar trends = trend("${1:table}", date_field="created_at", value_field="${2:amount}", interval="monthly", agg="sum")', insertTextRules: 4, detail: 'Analytics & Reporting setup' },
    { label: 'kpi_summary',    kind: _CK.Snippet, insertText: 'var ${1:kpis} = kpi_summary("${2:table}", metrics=["sum:${3:amount}", "avg:${3:amount}", "count:*"])', insertTextRules: 4, detail: 'Compute KPI summary' },
    { label: 'trend',          kind: _CK.Snippet, insertText: 'var ${1:trends} = trend("${2:table}", date_field="${3:created_at}", value_field="${4:amount}", interval="monthly", agg="sum")', insertTextRules: 4, detail: 'Time-series trend' },
    { label: 'distribution',   kind: _CK.Snippet, insertText: 'var ${1:dist} = distribution("${2:table}", category_field="${3:category}", value_field="${4:amount}", pareto=true)', insertTextRules: 4, detail: 'Category distribution' },
    { label: 'pivot',          kind: _CK.Snippet, insertText: 'var ${1:matrix} = pivot("${2:table}", row_field="${3:region}", col_field="${4:category}", value_field="${5:amount}")', insertTextRules: 4, detail: 'Pivot table matrix' },
    { label: 'function',      kind: _CK.Snippet, insertText: 'function ${1:name}(${2:params})\n    ${3:// body}', insertTextRules: 4, detail: 'Function declaration' },
    { label: 'if',            kind: _CK.Snippet, insertText: 'if ${1:condition}\n    ${2:// then}', insertTextRules: 4, detail: 'If statement' },
    { label: 'if-else',       kind: _CK.Snippet, insertText: 'if ${1:condition}\n    ${2:// then}\nelse\n    ${3:// else}', insertTextRules: 4, detail: 'If-else statement' },
    { label: 'for',           kind: _CK.Snippet, insertText: 'for ${1:item} in ${2:list}\n    ${3:log(item)}', insertTextRules: 4, detail: 'For-in loop' },
    { label: 'for-enum',      kind: _CK.Snippet, insertText: 'for ${1:i}, ${2:item} in ${3:list}\n    ${4:log(item)}', insertTextRules: 4, detail: 'For-in with index' },
    { label: 'while',         kind: _CK.Snippet, insertText: 'while ${1:condition}\n    ${2:// body}', insertTextRules: 4, detail: 'While loop' },
    { label: 'try',           kind: _CK.Snippet, insertText: 'try\n    ${1:// body}\ncatch ${2:e}\n    log(${2:e}.message)', insertTextRules: 4, detail: 'Try-catch' },
    { label: 'var',           kind: _CK.Snippet, insertText: 'var ${1:name} = ${2:value}', insertTextRules: 4, detail: 'Variable declaration' },
    { label: 'contract',      kind: _CK.Snippet, insertText: 'contract ${1:Name}\n    ${2:field}: ${3:str}', insertTextRules: 4, detail: 'Contract declaration' },
    { label: 'service',       kind: _CK.Snippet, insertText: 'service ${1:name}\n    port ${2:8080}\n\n    endpoint ${3:get_data}\n        return query("SELECT * FROM ${4:table}")', insertTextRules: 4, detail: 'Service declaration' },
    { label: 'pipeline',      kind: _CK.Snippet, insertText: 'pipeline ${1:name}\n    stage ${2:extract}\n        ${3:// fetch data}\n\n    stage ${4:transform}(${5:data})\n        ${6:// process}', insertTextRules: 4, detail: 'Pipeline declaration' },
    { label: 'agent',         kind: _CK.Snippet, insertText: 'agent ${1:name}\n    model "${2:claude-3-5-sonnet}"\n    tools ${3:fetch, ai}\n\n    task ${4:run}(${5:input})\n        return ai(${5:input})', insertTextRules: 4, detail: 'Agent declaration' },
    { label: 'component',     kind: _CK.Snippet, insertText: 'component ${1:Name}\n    state ${2:value} = ${3:""}\n\n    render\n        card\n            input bind=${2:value} label="${4:Label}"\n            button "Submit"', insertTextRules: 4, detail: 'UI Component' },
    { label: 'prompt',        kind: _CK.Snippet, insertText: 'prompt ${1:name}\n    system "${2:You are a helpful assistant.}"\n    user "${3:{input}}"\n    format text', insertTextRules: 4, detail: 'Prompt declaration' },
    { label: 'test',          kind: _CK.Snippet, insertText: 'test "${1:description}"\n    assert ${2:condition}, "${3:message}"', insertTextRules: 4, detail: 'Test declaration' },
    { label: 'debugger',      kind: _CK.Snippet, insertText: 'debugger', insertTextRules: 4, detail: 'Debugger statement' },
  ]

  monaco.languages.registerCompletionItemProvider('mcn', {
    triggerCharacters: ['.', ' ', '('],
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position)
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber:   position.lineNumber,
        startColumn:     word.startColumn,
        endColumn:       word.endColumn,
      }

      const suggestions = []

      // Built-in functions
      for (const b of _mcnBuiltins) {
        suggestions.push({ ...b, range,
          insertText: b.insertText || b.label,
          sortText: '0' + b.label,
        })
      }

      // Keywords
      for (const kw of _mcnKeywords) {
        suggestions.push({
          label: kw, kind: _CK.Keyword, insertText: kw, range,
          sortText: '1' + kw,
        })
      }

      // Snippets
      for (const s of _mcnSnippets) {
        suggestions.push({ ...s, range, sortText: '2' + s.label })
      }

      return { suggestions }
    }
  })

  // AI Inline Completions (Copilot-style Ghost Text)
  monaco.languages.registerInlineCompletionsProvider('mcn', {
    provideInlineCompletions: async function (model, position, context, token) {
      const code = model.getValue()
      const offset = model.getOffsetAt(position)
      const prefix = code.substring(0, offset)
      const suffix = code.substring(offset)

      // Get API Key from localStorage or assume set via ENV
      const apiKey = localStorage.getItem('mcn_api_key') || ''

      try {
        const r = await fetch('/api/autocomplete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prefix, suffix, api_key: apiKey })
        })
        const data = await r.json()
        if (data.success && data.completion) {
          return {
            items: [{
              insertText: data.completion,
              range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column)
            }]
          }
        }
      } catch (e) {
        // ignore fetch aborts or errors
      }
      return { items: [] }
    },
    freeInlineCompletions(completions) {}
  })

  // Hover provider — show doc strings on hover
  monaco.languages.registerHoverProvider('mcn', {
    provideHover(model, position) {
      const word = model.getWordAtPosition(position)
      if (!word) return null
      const fn = _mcnBuiltins.find(b => b.label === word.word)
      if (!fn) return null
      return {
        range: new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
        contents: [
          { value: '**`' + fn.detail + '`**' },
          { value: fn.documentation },
        ]
      }
    }
  })

  monaco.editor.defineTheme('mcn-coral-blue', {
    base: 'vs-dark', inherit: true,
    // JetBrains New UI "Dark" editor scheme (Darcula successor)
    rules: [
      { token: '',                   foreground: 'BCBEC4' },
      { token: 'comment',            foreground: '7A7E85', fontStyle: 'italic' },
      { token: 'keyword',            foreground: 'CF8E6D' },
      { token: 'keyword.declaration',foreground: 'CF8E6D' },
      { token: 'keyword.control',    foreground: 'CF8E6D' },
      { token: 'keyword.other',      foreground: 'CF8E6D' },
      { token: 'support.function',   foreground: '56A8F5' },
      { token: 'string',             foreground: '6AAB73' },
      { token: 'number',             foreground: '2AACB8' },
      { token: 'constant.language',  foreground: 'CF8E6D' },
      { token: 'type',               foreground: 'BCBEC4' },
      { token: 'delimiter',          foreground: 'BCBEC4' },
    ],
    colors: {
      'editor.background': '#1E1F22',
      'editor.foreground': '#BCBEC4',
      'editor.lineHighlightBackground': '#26282E',
      'editor.lineHighlightBorder': '#00000000',
      'editorLineNumber.foreground': '#4B5059',
      'editorLineNumber.activeForeground': '#A1A3AB',
      'editorCursor.foreground': '#CED0D6',
      'editor.selectionBackground': '#214283',
      'editor.inactiveSelectionBackground': '#2B3A5C',
      'editorIndentGuide.background1': '#313438',
      'editorIndentGuide.activeBackground1': '#4B5059',
      'editorGutter.background': '#1E1F22',
      'editorWidget.background': '#2B2D30',
      'editorWidget.border': '#43454A',
      'editorSuggestWidget.background': '#2B2D30',
      'editorSuggestWidget.selectedBackground': '#2E436E',
      'editor.wordHighlightBackground': '#3A3C4280',
      'editor.wordHighlightStrongBackground': '#3A3C42A0',
      'editor.selectionHighlightBackground': '#32427080',
      'scrollbarSlider.background': '#FFFFFF20',
      'scrollbarSlider.hoverBackground': '#FFFFFF33',
    }
  })

  window._editor = monaco.editor.create(document.getElementById('monaco-container'), {
    theme:             'mcn-coral-blue',
    language:          'mcn',
    automaticLayout:   true,
    fontSize:          13.5,
    fontFamily:        '"JetBrains Mono", "Cascadia Code", Consolas, monospace',
    lineNumbers:       'on',
    minimap:           { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap:          'on',
    padding:           { top: 14, bottom: 14 },
    renderWhitespace:  'selection',
    bracketPairColorization: { enabled: true },
    inlineSuggest:     { enabled: true }
  })

  window._replEditor = monaco.editor.create(document.getElementById('repl-input'), {
    theme:             'mcn-coral-blue',
    language:          'mcn',
    automaticLayout:   true,
    fontSize:          12.5,
    fontFamily:        '"JetBrains Mono", "Cascadia Code", Consolas, monospace',
    lineNumbers:       'off',
    minimap:           { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap:          'off',
    padding:           { top: 10, bottom: 0 },
    renderLineHighlight: 'none',
    scrollbar:         { vertical: 'hidden', horizontal: 'hidden' },
    overviewRulerLanes: 0,
    hideCursorInOverviewRuler: true,
    inlineSuggest:     { enabled: true }
  })

  let _replHistoryList = [];
  let _replHistoryIndex = -1;

  window._replEditor.addCommand(monaco.KeyCode.Enter, async () => {
    const cmd = window._replEditor.getValue().trim();
    if (!cmd) return;
    _replHistoryList.push(cmd);
    _replHistoryIndex = _replHistoryList.length;
    window._replEditor.setValue('');
    await executeReplCommand(cmd);
  });

  window._replEditor.addCommand(monaco.KeyCode.UpArrow, () => {
    if (_replHistoryList.length === 0) return;
    if (_replHistoryIndex > 0) {
      _replHistoryIndex--;
      window._replEditor.setValue(_replHistoryList[_replHistoryIndex]);
      window._replEditor.setPosition({ lineNumber: 1, column: _replHistoryList[_replHistoryIndex].length + 1 });
    }
  });

  window._replEditor.addCommand(monaco.KeyCode.DownArrow, () => {
    if (_replHistoryIndex < _replHistoryList.length - 1) {
      _replHistoryIndex++;
      window._replEditor.setValue(_replHistoryList[_replHistoryIndex]);
      window._replEditor.setPosition({ lineNumber: 1, column: _replHistoryList[_replHistoryIndex].length + 1 });
    } else {
      _replHistoryIndex = _replHistoryList.length;
      window._replEditor.setValue('');
    }
  });

  window._editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, runActiveFile)
  window._editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveActiveTab)

  let _verifyDebounce = null;
  window._editor.onDidChangeModelContent(() => {
    const m = window._editor.getModel()
    if (!m) return
    const p = m.uri.path.slice(1)
    if (_tabState.has(p)) { _tabState.get(p).dirty = true; renderTabs() }

    clearTimeout(_verifyDebounce);
    _verifyDebounce = setTimeout(async () => {
      const code = m.getValue();
      if (!code.trim()) { dismissDiagnosticBanner(); return; }
      try {
        const res = await apiFetch('/api/agent/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code })
        });
        const data = await res.json();
        if (data.success && data.result) {
          updateDiagnosticsState(data.result);
        }
      } catch (e) {}
    }, 600);
  })

  // Cursor position listener for Status Bar
  window._editor.onDidChangeCursorPosition((e) => {
    const pos = e.position;
    const statusDiv = document.getElementById('status-text');
    if (statusDiv) {
      const p = _active || 'untitled';
      statusDiv.textContent = `Ln ${pos.lineNumber}, Col ${pos.column}`;
    }
  })

  initApp()
})

