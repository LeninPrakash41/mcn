#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcn_interpreter import MCNLexer, MCNParser

code = '''function test_vars(x, y)
    var result = x + y
    echo "Inside function: " + result
    return result

var answer = test_vars(10, 5)
echo "Final answer: " + answer'''

print("=== TOKENS ===")
lexer = MCNLexer(code)
tokens = lexer.tokenize()
for i, token in enumerate(tokens):
    print(f"{i}: {token.type.value} = '{token.value}'")

print("\n=== PARSED AST ===")
parser = MCNParser(tokens)
statements = parser.parse()
for i, stmt in enumerate(statements):
    print(f"Statement {i}: {stmt}")
