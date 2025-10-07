Amazon Q Prompt: Build MCN - A Custom AI-Aware Scripting Language

Goal:
Build a lightweight scripting language and runtime engine called MCN (Macincode Scripting Language) similar to Zoho Deluge or JavaScript, designed for creating internal business applications with AI-assisted logic, workflows, database operations, and third-party integrations.

System Overview

You are an expert in language design, compiler/interpreter development, and workflow automation.
Design a Python-based interpreter for .mcn scripts that allows business users to write automation logic like:

var name = "John"
var age = 25
if age > 18
    log "Welcome " + name
trigger webhook("https://api.company.com/notify", {"user": name})

Core Requirements

Language Basics

Support variable declaration (var name = "value")

Arithmetic, logical, and string expressions

Conditional (if, else) and looping constructs (for, while)

Function definitions and inline function calls

Exception handling (try, catch, throw)

Built-in Functions

log(message) – print to console/log file

trigger(endpoint, payload) – trigger API/webhook calls

query(sql) – run SQL on connected database

workflow(name, params) – call internal workflow

ai(prompt) – call built-in AI model for text generation

Execution Engine

Build an MCNInterpreter class with:

Expression parser and evaluator

Variable scope and type handling

Function registry for custom commands

Exception management

Integration layer for API and database operations

Extensibility

AI-native support: allow calling AI models like GPT for reasoning or prediction.

Plugin architecture: Developers can register new functions (register_function(name, func)) dynamically.

Safe sandbox execution with restricted eval or AST-based expression parsing.

File Execution

.mcn scripts should run from CLI or embedded within Python apps.

Example:

python mcn_runner.py script.mcn


Optional Enhancements

Include REPL mode for debugging and live scripting

Add import system to load other .mcn files

Enable AI-generated script suggestions (based on context)

Deliverables

mcn_interpreter.py – Core interpreter and function engine

mcn_runtime.py – Database, API, and AI integration layer

mcn_cli.py – Command-line interface for script execution

Example .mcn scripts showcasing:

Database CRUD

Workflow automation

API trigger

AI text generation

AI Integration Note

Integrate AI assistance for:

Autocompletion and syntax hints in REPL

Semantic error correction suggestions

Code block optimization (“rewrite this function for performance”)

End Output

Deliver a fully functional MCN scripting engine that:

Executes human-readable business logic like Deluge

Supports API and DB integration

Provides AI-based reasoning and automation assistance

Is modular, extensible, and production-ready
