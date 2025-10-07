#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcn.core_engine.mcn_interpreter import MCNInterpreter

# Test basic functionality
interpreter = MCNInterpreter()

print("Available functions:", list(interpreter.functions.keys()))

# Test simple log
code = 'log "Hello World!"'
print(f"\nTesting: {code}")
try:
    result = interpreter.execute(code)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")

# Test echo
code = 'echo "Hello Echo!"'
print(f"\nTesting: {code}")
try:
    result = interpreter.execute(code)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
