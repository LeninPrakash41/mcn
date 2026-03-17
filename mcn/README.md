# MCN Core Engine

This directory contains the MCN language runtime, compiler, and CLI.

See the **[root README](../README.md)** for the full language reference, quick start, and package docs.

## Directory layout

```
core_engine/
  lexer.py            Tokeniser — handles all operators including %, +=, -=, *=, /=, %=, ?
  parser.py           Recursive-descent parser — if/else-if/else, ternary, modulo,
                      compound assign, property/index assign, object keyword keys
  evaluator.py        Tree-walking evaluator — executes all AST nodes
  ast_nodes.py        Typed AST dataclasses
  stdlib_builtins.py  100+ standard library functions:
                        session_*, cache_*, memory_*, vector_*, rag()
                        auth_hash / auth_create_token / auth_verify_token
                        parse_csv / parse_json / to_json
                        split / join / upper / lower / trim / replace / contains / ...
                        first / last / sort_list / group_by / unique / flatten / ...
                        sum_list / average / min_val / max_val / random_int / clamp
                        queue_push / queue_pop / queue_size
                        uuid / sha256 / md5
  ai_builtins.py      AI primitives: ai() llm() embed() extract() classify() checkpoint()
  mcn_packages.py     Package registry — bundled: stripe twilio resend slack openai
                        healthcare finance. Custom: mcn new-package / mcn install
  ui_compiler.py      MCN component/app → React + TypeScript + shadcn/ui
  type_checker.py     Static type checker (130+ built-in type signatures)
  formatter.py        Code formatter (mcn fmt)
  test_runner.py      Test framework + 15 assertion helpers
  mcn_server.py       HTTP server — GET/POST endpoints, path params, query strings,
                        auto GET for get_*/list_*/find_* naming convention
  mcn_cli.py          CLI: run serve test fmt check build generate install packages ...
  mcn_interpreter.py  Top-level interpreter (wires all modules together)
  runtime_types.py    MCNPipeline MCNService MCNWorkflow MCNContract MCNPrompt MCNAgent

web-playground/
  server.py           Playground backend (Flask) — /api/execute /api/build /api/test ...
  index.html          Monaco-based browser IDE

ai/
  mcn_agent.py        AI-powered full-stack app generator (mcn generate)
  mcn_spec.py         MCN language spec used as the agent system prompt

providers/
  anthropic_provider.py
  openai_provider.py

plugin/
  mcn_embedded.py     Embed MCN in Python apps
```

## Running tests

```bash
cd mt-mcn
mcn test examples/tests.mcn
mcn test use-cases/ --verbose
```

## Adding a built-in function

1. Implement in `stdlib_builtins.py` — add to `register_stdlib_builtins()`
2. Add return type + arg count to `BUILTIN_RETURN_TYPES` / `BUILTIN_ARG_COUNTS` in `type_checker.py`
3. Write a `test` block in `examples/tests.mcn`

## Adding a package

```bash
mcn new-package myorg/mypackage --path .
# edit myorg_mypackage/index.py
mcn install --path ./myorg_mypackage --name myorg/mypackage
```
