#!/usr/bin/env python3
"""
MCN Runner - Standalone runner that avoids relative import issues
"""

import sys
import os
import argparse

# Add the MCN core engine to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
core_engine_path = os.path.join(current_dir, "mcn", "core_engine")
sys.path.insert(0, core_engine_path)

# Import MCN components
try:
    from mcn_interpreter import MCNInterpreter
    from mcn_logger import log_step, log_error
    INTERPRETER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import MCN interpreter: {e}")
    INTERPRETER_AVAILABLE = False


def run_file(filepath):
    """Run a MCN file"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    if not INTERPRETER_AVAILABLE:
        print("Error: MCN interpreter not available")
        return 1

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"Running MCN file: {filepath}")
        
        # Use real interpreter with dynamic systems
        interpreter = MCNInterpreter()
        result = interpreter.execute(content, filepath, quiet=False)
        
        if result is not None:
            print(f"Script result: {result}")
        
        return 0

    except Exception as e:
        print(f"Error running file: {e}")
        return 1


def run_repl():
    """Run MCN REPL"""
    if not INTERPRETER_AVAILABLE:
        print("Error: MCN interpreter not available")
        return 1
        
    print("MCN (Macincode Scripting Language) REPL v3.0 - Dynamic Systems")
    print("Type 'exit' to quit, 'help' for commands")
    print("-" * 50)
    
    interpreter = MCNInterpreter()
    
    while True:
        try:
            line = input("mcn> ").strip()

            if line == "exit":
                break
            elif line == "help":
                print("Available commands:")
                print("  exit - Exit REPL")
                print("  help - Show this help")
                print("  vars - Show variables")
                print("  packages - Show available packages")
                print("")
                print("Dynamic systems available:")
                print("  use \"db\" - Database operations")
                print("  use \"http\" - HTTP requests")
                print("  use \"ai\" - AI model management")
                print("  use \"storage\" - File storage")
                print("  use \"analytics\" - Event tracking")
                print("  use \"auth\" - Authentication")
            elif line == "vars":
                if interpreter.variables:
                    print("Variables:")
                    for name, value in interpreter.variables.items():
                        print(f"  {name} = {repr(value)}")
                else:
                    print("No variables defined")
            elif line == "packages":
                print("Available packages:")
                print("  db, http, ai, storage, analytics, auth, workflows, notifications")
            elif line:
                result = interpreter.execute(line, quiet=True)
                if result is not None:
                    print(f"=> {result}")

        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except Exception as e:
            print(f"Error: {e}")

    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="MCN (Macincode Scripting Language) Runner v3.0"
    )
    parser.add_argument(
        "command", nargs="?", default="repl", help="Command to run (run, repl)"
    )
    parser.add_argument("file", nargs="?", help="MCN file to run")

    args = parser.parse_args()

    if args.command == "run" and args.file:
        return run_file(args.file)
    elif args.command == "repl":
        return run_repl()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())