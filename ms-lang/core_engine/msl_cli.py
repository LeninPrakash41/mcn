#!/usr/bin/env python3
import sys
import os
import argparse
import json
from pathlib import Path
# Handle both direct execution and module import
try:
    from .msl_interpreter import MSLInterpreter
    from .msl_logger import log_step, log_error, msl_logger
    from .msl_project_manager import msl_project_manager
    from .msl_frontend import msl_frontend
except ImportError:
    # Direct execution fallback
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from msl_interpreter import MSLInterpreter
    from msl_logger import log_step, log_error, msl_logger
    from msl_project_manager import msl_project_manager
    from msl_frontend import msl_frontend

class MSLREPL:
    def __init__(self):
        self.interpreter = MSLInterpreter()
        self.history = []
    
    def run(self):
        print("MSL (Macincode Scripting Language) REPL v1.0")
        print("Type 'exit' to quit, 'help' for commands")
        print("-" * 40)
        
        while True:
            try:
                line = input("msl> ").strip()
                
                if line == 'exit':
                    break
                elif line == 'help':
                    self._show_help()
                elif line == 'vars':
                    self._show_variables()
                elif line == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                elif line == 'history':
                    self._show_history()
                elif line:
                    self.history.append(line)
                    result = self.interpreter.execute(line)
                    if result is not None:
                        print(f"=> {result}")
                        
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
    
    def _show_help(self):
        help_text = """
MSL Commands:
  exit      - Exit REPL
  help      - Show this help
  vars      - Show all variables
  clear     - Clear screen
  history   - Show command history

MSL Syntax:
  var name = "value"           - Variable declaration
  if condition                 - Conditional statement
  log("message")              - Print to console
  trigger("url", {data})      - API call
  query("SELECT * FROM table") - Database query
  ai("prompt")                - AI text generation
        """
        print(help_text)
    
    def _show_variables(self):
        if self.interpreter.variables:
            print("Variables:")
            for name, value in self.interpreter.variables.items():
                print(f"  {name} = {repr(value)}")
        else:
            print("No variables defined")
    
    def _show_history(self):
        if self.history:
            print("Command History:")
            for i, cmd in enumerate(self.history, 1):
                print(f"  {i}: {cmd}")
        else:
            print("No command history")

def run_file(filepath: str):
    """Execute MSL script from file"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        interpreter = MSLInterpreter()
        result = interpreter.execute(code, filepath, quiet=False)
        
        if result is not None:
            print(f"Script result: {result}")
        
        return 0
    except Exception as e:
        print(f"Error executing script: {e}")
        return 1

def init_project(name: str, frontend: str = None):
    """Initialize new MSL project"""
    try:
        result = msl_project_manager.create_project_structure(
            name, 
            include_frontend=bool(frontend),
            frontend_framework=frontend
        )
        
        print(f"Created MSL project: {name}")
        print(f"Project path: {result['project_path']}")
        
        if frontend:
            print(f"Frontend framework: {frontend}")
            print(f"API client generated")
            
        print("\nNext steps:")
        print(f"   cd {name}")
        print("   pip install -r requirements.txt")
        print("   python -m msl.msl_cli msl/main.msl")
        
        return 0
    except Exception as e:
        log_error('PROJECT_INIT_ERROR', f'Failed to initialize project: {e}')
        return 1

def validate_project(path: str = '.'):
    """Validate MSL project structure"""
    try:
        result = msl_project_manager.validate_project_structure(path)
        
        if result['valid']:
            print("Project structure is valid")
        else:
            print("Project structure issues found:")
            
            if result['missing_files']:
                print("\nMissing files:")
                for file in result['missing_files']:
                    print(f"  - {file}")
                    
            if result['missing_dirs']:
                print("\nMissing directories:")
                for dir in result['missing_dirs']:
                    print(f"  - {dir}")
                    
            if result['recommendations']:
                print("\n💡 Recommendations:")
                for rec in result['recommendations']:
                    print(f"  • {rec}")
                    
        return 0 if result['valid'] else 1
    except Exception as e:
        log_error('PROJECT_VALIDATION_ERROR', f'Failed to validate project: {e}')
        return 1

def add_frontend(framework: str, path: str = '.'):
    """Add frontend integration to existing project"""
    try:
        project_path = Path(path)
        
        # Detect existing endpoints
        endpoints = []
        msl_files = list(project_path.glob('**/*.msl'))
        
        for msl_file in msl_files:
            name = msl_file.stem
            endpoints.append({
                'name': name,
                'path': f'/{name}',
                'method': 'POST'
            })
            
        if not endpoints:
            endpoints = [{'name': 'main', 'path': '/main', 'method': 'POST'}]
            
        # Setup frontend
        frontend_dir = project_path / 'frontend'
        frontend_dir.mkdir(exist_ok=True)
        
        msl_frontend.project_path = frontend_dir
        config = msl_frontend.create_frontend_config(framework, endpoints)
        
        print(f"Added {framework} frontend integration")
        print(f"API client: {config['client_file']}")
        print(f"Environment: {config['env_file']}")
        
        return 0
    except Exception as e:
        log_error('FRONTEND_ADD_ERROR', f'Failed to add frontend: {e}')
        return 1

def show_logs(log_type: str = 'all'):
    """Show MSL logs"""
    try:
        logs_dir = Path('logs')
        if not logs_dir.exists():
            print("No logs directory found")
            return 1
            
        log_files = {
            'errors': logs_dir / 'msl_errors.log',
            'debug': logs_dir / 'msl_debug.log',
            'all': None
        }
        
        if log_type == 'all':
            for name, file_path in log_files.items():
                if name != 'all' and file_path and file_path.exists():
                    print(f"\n=== {name.upper()} LOGS ===")
                    with open(file_path, 'r') as f:
                        print(f.read()[-2000:])  # Last 2000 chars
        else:
            file_path = log_files.get(log_type)
            if file_path and file_path.exists():
                with open(file_path, 'r') as f:
                    print(f.read())
            else:
                print(f"Log file not found: {log_type}")
                return 1
                
        return 0
    except Exception as e:
        log_error('LOGS_SHOW_ERROR', f'Failed to show logs: {e}')
        return 1

def main():
    parser = argparse.ArgumentParser(description='MSL (Macincode Scripting Language) CLI v2.0')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command (default)
    run_parser = subparsers.add_parser('run', help='Run MSL script')
    run_parser.add_argument('file', help='MSL script file to execute')
    run_parser.add_argument('--serve', action='store_true', help='Serve script as API endpoint')
    run_parser.add_argument('--host', default='127.0.0.1', help='Server host')
    run_parser.add_argument('--port', type=int, default=8000, help='Server port')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize new MSL project')
    init_parser.add_argument('name', help='Project name')
    init_parser.add_argument('--frontend', choices=['react', 'vue', 'angular', 'vanilla'], 
                           help='Include frontend framework')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate project structure')
    validate_parser.add_argument('--path', default='.', help='Project path to validate')
    
    # Add-frontend command
    frontend_parser = subparsers.add_parser('add-frontend', help='Add frontend integration')
    frontend_parser.add_argument('framework', choices=['react', 'vue', 'angular', 'vanilla'],
                               help='Frontend framework')
    frontend_parser.add_argument('--path', default='.', help='Project path')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show MSL logs')
    logs_parser.add_argument('--type', choices=['errors', 'debug', 'all'], default='all',
                           help='Log type to show')
    
    # REPL command
    repl_parser = subparsers.add_parser('repl', help='Start interactive REPL')
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Serve MSL scripts as APIs')
    serve_parser.add_argument('--dir', help='Directory containing MSL scripts')
    serve_parser.add_argument('--file', help='Single MSL script to serve')
    serve_parser.add_argument('--host', default='127.0.0.1', help='Server host')
    serve_parser.add_argument('--port', type=int, default=8000, help='Server port')
    
    # Legacy support - direct file execution
    parser.add_argument('--repl', action='store_true', help='Start REPL mode (legacy)')
    parser.add_argument('--serve', action='store_true', help='Serve script as API (legacy)')
    parser.add_argument('--serve-dir', help='Serve directory as APIs (legacy)')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (legacy)')
    parser.add_argument('--port', type=int, default=8000, help='Server port (legacy)')
    parser.add_argument('--version', action='version', version='MSL 2.0')
    
    args = parser.parse_args()
    
    # Handle new subcommands
    if args.command == 'init':
        return init_project(args.name, args.frontend)
    elif args.command == 'validate':
        return validate_project(args.path)
    elif args.command == 'add-frontend':
        return add_frontend(args.framework, args.path)
    elif args.command == 'logs':
        return show_logs(args.type)
    elif args.command == 'repl':
        repl = MSLREPL()
        repl.run()
        return 0
    elif args.command == 'run':
        if hasattr(args, 'serve') and args.serve:
            try:
                from .msl_server import serve_script
            except ImportError:
                from msl_server import serve_script
            serve_script(args.file, args.host, args.port)
            return 0
        else:
            return run_file(args.file)
    elif args.command == 'serve':
        try:
            from .msl_server import serve_script, serve_directory
        except ImportError:
            from msl_server import serve_script, serve_directory
        if args.file:
            serve_script(args.file, args.host, args.port)
        elif args.dir:
            serve_directory(args.dir, args.host, args.port)
        else:
            print("Error: Must specify --file or --dir for serve command")
            return 1
        return 0
    
    # Legacy support
    elif args.serve and args.file:
        from msl_server import serve_script
        serve_script(args.file, args.host, args.port)
        return 0
    elif args.serve_dir:
        from msl_server import serve_directory
        serve_directory(args.serve_dir, args.host, args.port)
        return 0
    elif hasattr(args, 'file') and args.file:
        return run_file(args.file)
    elif args.repl or len(sys.argv) == 1:
        repl = MSLREPL()
        repl.run()
        return 0
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())