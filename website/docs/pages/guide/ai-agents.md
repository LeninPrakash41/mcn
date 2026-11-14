# Building with AI agents

Most languages were designed for people typing code. MCN is also designed for AI agents that read, write and change it. That matters because an agent's mistakes are usually not syntax: they're changes that quietly break something else.

| An agent needs | MCN gives it |
|---|---|
| Little syntax to get wrong | Indented plain words: `service`, `endpoint`, `component`, `on load`, `test`. No braces, imports or boilerplate |
| Building blocks with one meaning | A `service` is an API, an `endpoint` is a route, a `component` is a screen, `auth "sso"` is company sign-in, `audit` is a log of every call. The meaning doesn't depend on a framework |
| The whole app in view | An app is usually two files, and `mcn describe` maps every part and how they connect |
| Changes that don't break other parts | `mcn impact` says what a change affects and which tests cover it, before and after the edit |
| A way to check its own work | `mcn check`, `mcn test`, `mcn agent verify` and the compiled React and Flutter builds |
| Exact inputs for every endpoint | Typed parameters (`amount: float`, `who: Customer`), refused with a 400 when wrong, and required by `mcn check --strict` |
| Room to work alongside other agents | `module` blocks that own their tables, and `mcn impact --changed --module <name>` to prove a change stayed inside one |
| A model of the app it can read in one go | The MCN Semantic Graph (`mcn describe --msg`): versioned JSON with every declaration, signature and connection, plus each file's complete syntax tree |
| Freedom to use any model | MCN's own agents and the agent interface work with Claude, OpenAI, Gemini, OpenRouter, a local model in Ollama, or any OpenAI-compatible server |
| Changes as checked operations, not rewritten files | The agent interface (`mcn op`): find and explain declarations, then create, modify or remove them as a patch that is validated, tested and applied only when a person approves |

## The map: `mcn describe`

```bash
mcn describe              # a readable summary
mcn describe --json       # the full map, for agents and tools
mcn describe --strict     # exit code 1 when it finds problems (for CI)
```

```text
3 screens · 8 endpoints · 2 tables · 0 functions · 2 tests

App Operations
  Overview → Overview
  Orders → Orders

Screens
  Orders → delete_order, list_orders   (ui/app.mcn:32)

Endpoints
  delete_order(id)  writes orders  [public, untested]
  list_orders()  reads orders  [public, untested]
  summary()  reads orders  [public, tested]

Tables
  orders: read by list_orders, summary; written by delete_order
```

The JSON has three parts:

- **`nodes`**: every table, service, endpoint, function, contract, workflow, schedule, test, screen and the app, each with its file and lines. Endpoints also say how they're protected (`auth`), whether they're audited, which tables they read and write, and whether a test covers them.
- **`edges`**: how the parts connect: `calls` (a screen or function calls an endpoint or function), `reads` and `writes` (an endpoint or function and a table), `covers` (a test and what it calls), `renders` and `shows` (screens and navigation), and `uses` (a contract).
- **`issues`**: problems in the code: a screen calling an endpoint that doesn't exist (including the create, update and delete calls a table screen makes for you), navigation to a missing screen, SQL on a table nothing creates, and, as notes, endpoints nothing calls.

The map is read from the source without running anything, so it's safe and fast to call before every change.

## The MCN Semantic Graph (MSG)

```bash
mcn describe --msg              # the full MSG as JSON
mcn describe --msg --no-ast     # just the graph: small enough to hand an agent whole
mcn describe --msg-schema       # its JSON Schema
```

The MSG is MCN's canonical, machine-readable model of an app, versioned (`"msg_version": "1.0"`) and described by a published JSON Schema. It has three layers:

- **The graph**: every declaration (`nodes`) with its kind, file and lines, typed signature, the tables it reads and writes, how it's protected and whether a test covers it; how they connect (`edges`: calls, reads, writes, renders, shows, covers, uses, owns, contains); and the problems found (`issues`).
- **The syntax trees**: each file's complete abstract syntax tree (`files[path].ast`), independent of formatting. Every graph node has an `ast_ref` (its file, then a JSON pointer such as `/body/7/endpoints/2`) pointing at its own subtree, so nothing in the program is left out of the model.
- **The source**: each file's exact text and SHA-256.

It round-trips: the trees rebuild exactly the AST the parser produces from the source, and the sources come back byte for byte. That is checked on every template in CI. An LLM can read the graph to understand the app far more easily than a long source file, and read a declaration's subtree when it needs the details. Agents get it through the agent interface's `semantic_graph` operation, including over MCP.

## What a change affects: `mcn impact`

```bash
mcn impact orders                    # a table, endpoint, function, contract or screen
mcn impact endpoint:list_orders      # when a name is used for more than one kind of thing
mcn impact backend/main.mcn:42       # whatever is declared at that line
mcn impact --changed                 # everything changed since the last commit
mcn impact --changed --base main     # ... or since another branch
```

```text
Changing table:orders affects:
  Endpoints: delete_order (writes), list_orders (reads), summary (reads)
  Screens: Orders (calls), Overview (calls)
  In the app: Orders, Overview
Tests to run: summary adds up paid revenue
No test covers: delete_order, list_orders
```

It follows the map backwards: who reads or writes the table, who calls those endpoints and functions, which screens call them, where those screens are in the app's navigation, and which tests cover any of it. `--json` gives the same as data.

## Strict types

```mcn fragment
service billing
    endpoint add_invoice(customer: str, amount: float, due: Invoice)
```

With types, the map tells an agent exactly what each endpoint takes, the type checker uses them inside the endpoint, and the running API refuses wrong input with a 400 that names the parameter. `mcn check --strict` fails when an endpoint parameter has no type. See [typed parameters](#/guide/services).

## Several agents at once: modules

```mcn fragment
module billing
    owns invoices, payments

    service billing_api
        endpoint invoice(order_id: int)
            ...
```

A module owns its tables: only its own code may write them, and `mcn describe` reports any other code that does. Give each agent (or person) a module, and check each one's change with:

```bash
mcn impact --changed --module billing    # exit code 1 if anything outside billing changed
```

The map lists each module's members, owned tables and the modules it depends on, so you can see which pieces can be built in parallel. See [modules](#/guide/services).

## The agent interface: change an app through operations

Letting an AI rewrite whole files is how unrelated code gets lost. The agent interface lets an agent ask the MCN engine for specific changes instead:

| Operation | Does |
|---|---|
| `inspect` | The app's structure: modules, tables with their `CREATE` statements, endpoints with typed signatures, screens, navigation, tests and current problems |
| `find <text>` | Declarations by name, or by text in their code, with their source |
| `explain <name>` | What a declaration is, the tables it reads and writes, what it calls, what calls it, which tests cover it, and what changing it affects |
| `create <kind>` | Add an endpoint (into a service), function, contract, workflow, test, table or screen. With `--module`, it goes inside that module (a table is added to the module's `owns`); a screen with `--nav` also gets a navigation item |
| `modify <name>` | Replace one declaration's code, keeping its place and indentation |
| `remove <name>` | Delete one declaration |
| `validate <patch>` | Every changed file parses and type-checks; no new problems in the app map (a screen calling a removed endpoint, a write to another module's table); what changed, what it affects, which tests to run. A patch made for one module must stay inside it |
| `test <patch>` | Every `test` block, with the patch applied, against a fresh database |
| `execute <patch> --yes` | Write the patch to the files |

`create`, `modify` and `remove` don't touch your files. They build up a **patch** (pass `--patch <id>` to add to one), saved in `.mcn/patches/`. `execute` writes it only after it passed `validate` and `test`, only with `--yes` (someone reviewed it), and only if the files haven't changed since the patch was made.

```bash
mcn op explain create_order
mcn op modify create_order --source new_create_order.mcn --reason "verify the customer first"
mcn op create test --source verify_test.mcn --patch 20261114-095431-9b6db5
mcn op validate 20261114-095431-9b6db5
mcn op test 20261114-095431-9b6db5
mcn op show 20261114-095431-9b6db5          # the diff
mcn op execute 20261114-095431-9b6db5 --yes
```

Every operation takes `--json`, for tools and agents.

### `mcn change`: an AI agent that works only through the interface

```bash
mcn change "Add a customer verification step before creating an order"
```

Claude gets the operations as tools, never your files. It inspects the app, finds and explains what the request touches, builds one patch, adds a test, then validates and tests until both pass. It can't apply anything. You see the diff, what it affects and the test results, and answer **Apply this change? [y/N]**. `--yes` applies it without asking, but only when validation and tests passed.

In Studio, the **Agent** panel's **Change** mode (Cmd/Ctrl+L) works the same way. It saves your open files, shows each operation as the agent works, then shows a review card: the summary, whether the patch is valid, what it affects, the test results and the diff. Nothing is written until you click **Apply change**, and Apply is only offered when validation and tests passed. **Fix with the Agent** (on an error, or Edit → Fix Errors with the Agent) starts a change with the error filled in.

### Any agent: the MCP server

`mcn mcp` serves the same operations over the [Model Context Protocol](https://modelcontextprotocol.io), so agents you already use (Claude Code, Claude Desktop, Cursor, VS Code, or your own) can change an MCN app through checked patches.

```bash
claude mcp add mcn -- mcn mcp --dir /path/to/my-app     # Claude Code
mcn mcp --dir /path/to/my-app --print-config            # the JSON for other clients' settings
```

```json
{
  "mcpServers": {
    "mcn": { "command": "mcn", "args": ["mcp", "--dir", "/path/to/my-app"] }
  }
}
```

The tools are `inspect`, `find`, `explain`, `create`, `modify`, `remove`, `validate`, `test`, `show` (a patch's diff and results), `patches`, and `language_guide` (MCN's syntax, for an agent that hasn't seen MCN before). The read-only ones are marked as such, so a client can allow them without asking.

By default the agent can't apply anything: it hands you a patch id, and you apply it with `mcn op execute <id> --yes` after reading `mcn op show <id>`. Start the server with `--allow-execute` to also offer `execute` (your client still asks before each call). Even then, `execute` only applies a patch that passed `validate` and `test` and whose files haven't changed since. The server needs nothing beyond MCN itself.

The operations are also a Python API (`mcn.core_engine.agent_interface.Workspace`) with tool definitions as plain JSON Schema (`AGENT_TOOLS`), so your own agents can use them the same way, with any model.

## Choosing the model

MCN doesn't depend on one company's model. `mcn change`, the agent team (`mcn generate --team`), `mcn generate` and Studio's Agent panel work with any model that can call tools:

| Provider | Set up with | Default model |
|---|---|---|
| `anthropic` (Claude) | `ANTHROPIC_API_KEY`, or `mcn config set api_key ...` | `claude-opus-5-5` (`MCN_CLAUDE_MODEL`) |
| `openai` | `OPENAI_API_KEY`, or `mcn config set openai_api_key ...` | `gpt-4o` |
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), or `gemini_api_key` | `gemini-2.5-pro` |
| `openrouter` | `OPENROUTER_API_KEY`, or `openrouter_api_key` | choose with `ai_model` |
| `ollama` (local) | `OLLAMA_URL` (default `http://localhost:11434`) | choose with `ai_model` or `OLLAMA_MODEL` |
| `compatible` | `ai_base_url` (any OpenAI-compatible server: vLLM, LM Studio, Together, Groq...), and `ai_api_key` if it needs one | choose with `ai_model` |

```bash
mcn config set ai_provider gemini            # or pass --provider on each command
mcn config set ai_model gemini-2.5-flash
mcn change "Add a search box to the orders table" --provider ollama --model qwen2.5-coder
mcn generate --team "A clinic booking app" --provider compatible --base-url http://gpu-box:8000/v1 --model my-model
```

Without a setting, MCN uses whichever key you have, checking Claude first, then OpenAI, Gemini and OpenRouter. A key pasted into Studio's Agent panel picks its provider from its prefix. Two things depend on the model: the agent team's researcher searches the web only on Claude (elsewhere it works from the request alone), and PDF attachments are read directly only by Claude; for other models MCN sends the PDF's text when `pypdf` is installed (`mcn add pdf`).

## A loop for agents

```bash
mcn describe --msg --no-ast    # 1. understand the app
mcn impact <what you'll change>  # 2. see what else the change touches
#                                 3. edit the .mcn files
mcn check . && mcn test .      # 4. types and tests
mcn impact --changed           # 5. confirm the change only reached what you meant, and run those tests
mcn describe --strict          # 6. no new structural problems
mcn check --strict backend/main.mcn   # 7. every endpoint parameter typed
```

`mcn agent verify <file> --json` checks one file through the lexer, parser, type checker and linter, and `mcn agent explain <topic>` gives exact syntax rules. MCN's own [agent team](#/guide/ai) uses the map in the same way: it builds an app's modules in parallel and uses the map's ownership check to send a module back to its builder; its QA lead gets the map's issues, and after each fix, what the fix changed and which screens and endpoints that affects.
