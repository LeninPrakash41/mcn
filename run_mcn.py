#!/usr/bin/env python3
"""
MCN Runner Script - Handles direct execution without import issues
"""

import sys
import os
import argparse


def main():
    """Simple MCN runner that handles basic commands"""
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
    """Run a MCN file"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        # Simple file execution
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"Running MCN file: {filepath}")
        print(f"Content preview: {content[:100]}...")
        print("Note: Full MCN interpreter not yet loaded. This is a placeholder.")
        return 0

    except Exception as e:
        print(f"Error running file: {e}")
        return 1


def run_repl():
    """Run MCN REPL"""
    print("MCN (Macincode Scripting Language) REPL v2.0")
    print("Type 'exit' to quit, 'help' for commands")
    print("-" * 40)

    while True:
        try:
            line = input("mcn> ").strip()

            if line == "exit":
                break
            elif line == "help":
                print("Available commands:")
                print("  exit - Exit REPL")
                print("  help - Show this help")
                print("  Note: Full interpreter not yet loaded")
            elif line:
                print(f"Input received: {line}")
                print(
                    "Note: Full MCN interpreter not yet loaded. This is a placeholder."
                )

        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except Exception as e:
            print(f"Error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
