#!/usr/bin/env python3
"""
MCN Development CLI - Integrated Development Server Approach
Provides unified development experience with integrated backend/frontend server
"""

import sys
import os
import argparse
import subprocess
import threading
import time
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.core_engine.mcn_dev_server import MCNDevServer

def run_script(file_path, args=None):
    """Run MCN script directly"""
    interpreter = MCNInterpreter()
    try:
        result = interpreter.run_file(file_path, args or [])
        return result
    except Exception as e:
        print(f"Error running script: {e}")
        return None

def start_dev_server(file_path, port=3000, frontend_port=3001):
    """Start integrated development server"""
    dev_server = MCNDevServer()
    try:
        dev_server.start(file_path, port, frontend_port)
    except KeyboardInterrupt:
        print("\nShutting down development server...")
        dev_server.stop()

def generate_react_app(mcn_file, output_dir=None):
    """Generate React app from MCN script"""
    from mcn.fullstack.react_generator import ReactProjectGenerator
    
    if not output_dir:
        output_dir = f"./generated-app-{int(time.time())}"
    
    generator = ReactProjectGenerator()
    
    # Run MCN script to get UI manifest
    interpreter = MCNInterpreter()
    result = interpreter.run_file(mcn_file)
    
    if hasattr(interpreter, 'ui_manifest') and interpreter.ui_manifest:
        success = generator.generate_project(interpreter.ui_manifest, output_dir)
        if success:
            print(f"React app generated in: {output_dir}")
            print(f"To run: cd {output_dir} && npm install && npm start")
        return success
    else:
        print("No UI components found in MCN script")
        return False

def main():
    parser = argparse.ArgumentParser(description='MCN Development CLI - Integrated Approach')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run MCN script')
    run_parser.add_argument('file', help='MCN script file to run')
    run_parser.add_argument('args', nargs='*', help='Arguments to pass to script')
    
    # Dev command (integrated server)
    dev_parser = subparsers.add_parser('dev', help='Start integrated development server')
    dev_parser.add_argument('file', help='MCN script file to serve')
    dev_parser.add_argument('--port', type=int, default=3000, help='Backend port (default: 3000)')
    dev_parser.add_argument('--frontend-port', type=int, default=3001, help='Frontend port (default: 3001)')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate React app from MCN script')
    gen_parser.add_argument('file', help='MCN script file')
    gen_parser.add_argument('--output', help='Output directory for generated app')
    
    # REPL command
    repl_parser = subparsers.add_parser('repl', help='Start interactive REPL')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'run':
        run_script(args.file, args.args)
    
    elif args.command == 'dev':
        print(f"Starting integrated development server...")
        print(f"Backend: http://localhost:{args.port}")
        print(f"Frontend: http://localhost:{args.frontend_port}")
        print("Press Ctrl+C to stop")
        start_dev_server(args.file, args.port, args.frontend_port)
    
    elif args.command == 'generate':
        generate_react_app(args.file, args.output)
    
    elif args.command == 'repl':
        from mcn.core_engine.mcn_repl import MCNRepl
        repl = MCNRepl()
        repl.start()

if __name__ == '__main__':
    main()