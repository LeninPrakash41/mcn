#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcn_interpreter import MCNLexer, MCNParser

# Just test the calculate_discount function
code = '''function calculate_discount(price, discount_percent)
    var discount = price * (discount_percent / 100)
    var final_price = price - discount
    return final_price

var result = calculate_discount(100, 20)
log "Result: " + result'''

print("=== PARSED AST ===")
lexer = MCNLexer(code)
tokens = lexer.tokenize()
parser = MCNParser(tokens)
statements = parser.parse()

for i, stmt in enumerate(statements):
    print(f"Statement {i}: {stmt}")
    if stmt['type'] == 'function_declaration':
        print(f"  Function body has {len(stmt['body'])} statements:")
        for j, body_stmt in enumerate(stmt['body']):
            print(f"    {j}: {body_stmt}")
