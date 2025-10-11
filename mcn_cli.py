#!/usr/bin/env python3
"""
MCN CLI - Complete command line interface with integrated development server
"""

import argparse
import sys
import os
import json
from pathlib import Path

# Add MCN to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcn'))

def run_script(file_path: str, quiet: bool = False):
    """Execute MCN script"""
    try:
        from mcn.core_engine.mcn_interpreter import MCNInterpreter
        
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found")
            return 1
        
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        interpreter = MCNInterpreter()
        result = interpreter.execute(code, file_path, quiet)
        
        if not quiet:
            print(f"Script executed successfully: {file_path}")
        
        return 0
        
    except Exception as e:
        print(f"Error executing script: {e}")
        return 1

def serve_script(file_path: str, port: int = 8000, host: str = "localhost"):
    """Serve MCN script as API"""
    try:
        from mcn.core_engine.mcn_server import MCNServer
        
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found")
            return 1
        
        server = MCNServer()
        print(f"Starting MCN server on {host}:{port}")
        print(f"Serving script: {file_path}")
        server.start(file_path, host, port)
        
        return 0
        
    except Exception as e:
        print(f"Error starting server: {e}")
        return 1

def start_repl():
    """Start interactive REPL"""
    try:
        from mcn.core_engine.mcn_interpreter import MCNInterpreter
        
        interpreter = MCNInterpreter()
        
        print("MCN Interactive REPL v3.0")
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
                    print("  vars - Show variables")
                    print("  funcs - Show functions")
                elif line == "vars":
                    print("Variables:", list(interpreter.variables.keys()))
                elif line == "funcs":
                    print("Functions:", list(interpreter.functions.keys()))
                elif line:
                    result = interpreter.execute(line, quiet=True)
                    if result is not None:
                        print(f"=> {result}")
                        
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
        
        return 0
        
    except Exception as e:
        print(f"Error starting REPL: {e}")
        return 1

def start_dev_server(mcn_file: str, frontend_dir: str = None):
    """Start integrated development server"""
    try:
        from mcn.core_engine.mcn_dev_server import start_dev_server
        
        # Auto-detect frontend directory if not specified
        if not frontend_dir:
            base_name = os.path.splitext(os.path.basename(mcn_file))[0]
            possible_dirs = [
                f"./{base_name}-app",
                f"./{base_name}_app", 
                "./frontend",
                "./react-app"
            ]
            
            for dir_path in possible_dirs:
                if os.path.exists(dir_path) and os.path.exists(os.path.join(dir_path, "package.json")):
                    frontend_dir = dir_path
                    break
        
        start_dev_server(mcn_file, frontend_dir)
        return 0
        
    except Exception as e:
        print(f"Error starting development server: {e}")
        return 1

def generate_react_app(mcn_file: str, output_dir: str = None):
    """Generate React app from MCN script"""
    try:
        from mcn.core_engine.mcn_interpreter import MCNInterpreter
        
        if not os.path.exists(mcn_file):
            print(f"Error: File '{mcn_file}' not found")
            return 1
        
        # Execute MCN script to generate UI
        with open(mcn_file, 'r', encoding='utf-8') as f:
            code = f.read()
        
        interpreter = MCNInterpreter()
        interpreter.execute(code, mcn_file)
        
        # Check if UI was exported
        if not output_dir:
            base_name = os.path.splitext(os.path.basename(mcn_file))[0]
            output_dir = f"./{base_name}-react-app"
        
        if os.path.exists(output_dir):
            print(f"✅ React app generated: {output_dir}")
            print(f"📦 To run: cd {output_dir} && npm install && npm start")
        else:
            print("❌ No React app was generated. Make sure your MCN script uses ui.export()")
        
        return 0
        
    except Exception as e:
        print(f"Error generating React app: {e}")
        return 1

def main():
    """Main CLI entry point"""
    # Check if using enhanced CLI commands
    enhanced_commands = {
        'install', 'search', 'list', 'uninstall', 'models', 
        'create-package', 'publish', 'registry', 'info', 'version'
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in enhanced_commands:
        # Use enhanced CLI
        try:
            from mcn.core_engine.mcn_cli_enhanced import main as enhanced_main
            return enhanced_main()
        except ImportError:
            print("Enhanced CLI features not available")
            return 1
    
    # Original CLI for script execution
    parser = argparse.ArgumentParser(description="MCN CLI - Full-Stack AI-Native Development")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Execute MCN script")
    run_parser.add_argument("file", help="MCN script file to execute")
    run_parser.add_argument("--quiet", action="store_true", help="Suppress output")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Serve MCN script as API")
    serve_parser.add_argument("--file", required=True, help="MCN script file to serve")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    serve_parser.add_argument("--host", default="localhost", help="Host to serve on")

    # REPL command
    repl_parser = subparsers.add_parser("repl", help="Start interactive REPL")
    
    # Dev command (integrated server)
    dev_parser = subparsers.add_parser("dev", help="Start integrated development server")
    dev_parser.add_argument("file", help="MCN script file")
    dev_parser.add_argument("--frontend", help="Frontend directory (optional)")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate React app from MCN script")
    gen_parser.add_argument("file", help="MCN script file")
    gen_parser.add_argument("--output", help="Output directory (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n🚀 MCN v3.0 - AI-Native Full-Stack Development")
        print("\nScript Commands:")
        print("  mcn run my-app.mcn")
        print("  mcn dev my-app.mcn")
        print("  mcn generate my-app.mcn")
        print("  mcn serve --file my-app.mcn")
        print("\nPackage Management:")
        print("  mcn install ai_v3")
        print("  mcn search 'machine learning'")
        print("  mcn models list")
        print("  mcn registry stats")
        return 1

    if args.command == "run":
        return run_script(args.file, args.quiet)
    elif args.command == "serve":
        return serve_script(args.file, args.port, args.host)
    elif args.command == "repl":
        return start_repl()
    elif args.command == "dev":
        return start_dev_server(args.file, args.frontend)
    elif args.command == "generate":
        return generate_react_app(args.file, args.output)
    else:
        print(f"Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())