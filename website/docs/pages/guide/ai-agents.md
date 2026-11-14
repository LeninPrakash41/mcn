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

## A loop for agents

```bash
mcn describe --json            # 1. understand the app
mcn impact <what you'll change>  # 2. see what else the change touches
#                                 3. edit the .mcn files
mcn check . && mcn test .      # 4. types and tests
mcn impact --changed           # 5. confirm the change only reached what you meant, and run those tests
mcn describe --strict          # 6. no new structural problems
mcn check --strict backend/main.mcn   # 7. every endpoint parameter typed
```

`mcn agent verify <file> --json` checks one file through the lexer, parser, type checker and linter, and `mcn agent explain <topic>` gives exact syntax rules. MCN's own [agent team](#/guide/ai) uses the map in the same way: its QA lead gets the map's issues, and after each fix, what the fix changed and which screens and endpoints that affects.
