#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcn_interpreter import MCNInterpreter

def main():
    filepath = "d:/mcn/mcn/examples/hello.mcn"

    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        print(f"Executing MCN code from {filepath}:")
        print(f"Code: {code}")
        print("-" * 40)

        interpreter = MCNInterpreter()
        result = interpreter.execute(code, filepath)

        if result is not None:
            print(f"Script result: {result}")

        return 0
    except Exception as e:
        print(f"Error executing script: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
