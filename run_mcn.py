#!/usr/bin/env python3
"""
MCN Runner Script - Handles direct execution without import issues
"""

import sys
import os
import argparse


def main():
    """Simple MCN runner that handles basic commands"""
    global script_dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    parser = argparse.ArgumentParser(
        description="MCN (Macincode Scripting Language) Runner"
    )
    parser.add_argument(
        "command", nargs="?", default="repl", help="Command to run (run, repl, serve)"
    )
    parser.add_argument("file", nargs="?", help="MCN file to run")
    parser.add_argument("--port", type=int, default=8000, help="Port for serve command")
    parser.add_argument("--host", default="127.0.0.1", help="Host for serve command")

    args = parser.parse_args()

    # Add paths for imports
    mcn_lang_path = os.path.join(script_dir, "mcn")
    core_engine_path = os.path.join(mcn_lang_path, "core_engine")

    sys.path.insert(0, script_dir)
    sys.path.insert(0, mcn_lang_path)
    sys.path.insert(0, core_engine_path)

    if args.command == "run" and args.file:
        return run_file(args.file)
    elif args.command == "repl":
        return run_repl()
    elif args.command == "serve":
        print(f"Serve command not yet implemented")
        return 1
    else:
        parser.print_help()
        return 1


def run_file(filepath):
    """Run a MCN file using the real interpreter"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        # Import the real MCN interpreter
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_interpreter import MCNInterpreter
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"Running MCN file: {filepath}")
        
        # Use real interpreter
        interpreter = MCNInterpreter()
        result = interpreter.execute(content, filepath, quiet=False)
        
        if result is not None:
            print(f"Script result: {result}")
        
        return 0

    except Exception as e:
        print(f"Error running file: {e}")
        return 1


def run_repl():
    """Run MCN REPL with real interpreter"""
    print("MCN (Macincode Scripting Language) REPL v3.0 - Dynamic Systems")
    print("Type 'exit' to quit, 'help' for commands")
    print("-" * 40)
    
    try:
        # Import the real MCN interpreter
        sys.path.insert(0, os.path.join(script_dir, "mcn", "core_engine"))
        from mcn_interpreter import MCNInterpreter
        
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
                    print("  Dynamic systems: db, http, ai, events, agents, storage")
                elif line == "vars":
                    if interpreter.variables:
                        for name, value in interpreter.variables.items():
                            print(f"  {name} = {repr(value)}")
                    else:
                        print("  No variables defined")
                elif line:
                    result = interpreter.execute(line, quiet=True)
                    if result is not None:
                        print(f"=> {result}")

            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
    
    except ImportError as e:
        print(f"Could not load MCN interpreter: {e}")
        print("Running in basic mode...")
        # Fallback to basic mode
        while True:
            try:
                line = input("mcn> ").strip()
                if line == "exit":
                    break
                elif line:
                    print(f"Basic mode - received: {line}")
            except KeyboardInterrupt:
                break

    return 0


if __name__ == "__main__":
    sys.exit(main())
