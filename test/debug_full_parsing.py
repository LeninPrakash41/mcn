#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcn_interpreter import MCNLexer, MCNParser

# Read the actual user_functions.mcn file
with open("d:/mcn/mcn/examples/user_functions.mcn", "r") as f:
    code = f.read()

print("=== PARSING FULL FILE ===")
lexer = MCNLexer(code)
tokens = lexer.tokenize()
parser = MCNParser(tokens)
statements = parser.parse()

print(f"Total statements parsed: {len(statements)}")
for i, stmt in enumerate(statements):
    print(f"Statement {i}: {stmt['type']}")
    if stmt["type"] == "function_declaration":
        print(f"  Function '{stmt['name']}' with {len(stmt['body'])} body statements")
    elif (
        stmt["type"] == "expression_statement" and stmt["expression"]["type"] == "call"
    ):
        print(f"  Function call: {stmt['expression']['callee']['name']}")
    elif stmt["type"] == "var_declaration":
        print(f"  Variable: {stmt['name']}")
