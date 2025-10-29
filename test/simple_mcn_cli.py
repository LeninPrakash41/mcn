#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcn', 'core_engine'))

from mcn.core_engine.mcn_interpreter import MCNInterpreter


def main():
    if len(sys.argv) != 2:
        print("Usage: python simple_mcn_cli.py <mcn_file>")
        return 1

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        interpreter = MCNInterpreter()
        result = interpreter.execute(code, filepath)

        if result is not None:
            print(f"Script result: {result}")

        return 0
    except Exception as e:
        print(f"Error executing script: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
