#!/usr/bin/env python3
import sys
import os
import argparse
import json
from pathlib import Path

# Handle both direct execution and module import
try:
    from .mcn_interpreter import MCNInterpreter
    from .mcn_logger import log_step, log_error, mcn_logger
    from .mcn_project_manager import mcn_project_manager
    from .mcn_frontend import mcn_frontend
except ImportError:
    # Direct execution fallback
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mcn_interpreter import MCNInterpreter
    from mcn_logger import log_step, log_error, mcn_logger
    from mcn_project_manager import mcn_project_manager
    from mcn_frontend import mcn_frontend


class MCNREPL:
    def __init__(self):
        self.interpreter = MCNInterpreter()
        self.history = []

    def run(self):
        print("MCN (Macincode Scripting Language) REPL v1.0")
        print("Type 'exit' to quit, 'help' for commands")
        print("-" * 40)

        while True:
            try:
                line = input("mcn> ").strip()

                if line == "exit":
                    break
                elif line == "help":
                    self._show_help()
                elif line == "vars":
                    self._show_variables()
                elif line == "clear":
                    os.system("cls" if os.name == "nt" else "clear")
                elif line == "history":
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
MCN Commands:
  exit      - Exit REPL
  help      - Show this help
  vars      - Show all variables
  clear     - Clear screen
  history   - Show command history

MCN Syntax:
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


def check_file(filepath: str, strict: bool = False) -> int:
    """
    Static-check a MCN script without executing it.

    Runs:
      1. Lexing + parsing  — catches syntax errors
      2. Type inference    — catches type errors and suspicious patterns

    Exit codes:
      0  — no issues (or only warnings when --strict is NOT set)
      1  — at least one ERROR found (or any issue when --strict IS set)
    """
    try:
        from .type_checker import check_source, Severity
    except ImportError:
        from type_checker import check_source, Severity

    if not os.path.exists(filepath):
        print(f"error: file not found: '{filepath}'")
        return 1

    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    issues = check_source(code)

    if not issues:
        print(f"ok  {filepath}")
        return 0

    errors   = [i for i in issues if i.severity == Severity.ERROR]
    warnings = [i for i in issues if i.severity == Severity.WARNING]

    for issue in sorted(issues, key=lambda i: (i.line, i.col)):
        print(f"{filepath}:{issue}")

    total = len(errors)
    if strict:
        total += len(warnings)

    summary = []
    if errors:   summary.append(f"{len(errors)} error(s)")
    if warnings: summary.append(f"{len(warnings)} warning(s)")
    print(f"\n{'FAIL' if total else 'PASS'}  {', '.join(summary)}")

    return 1 if total else 0


def run_file(filepath: str):
    """Execute MCN script from file"""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found")
        return 1

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        interpreter = MCNInterpreter()
        result = interpreter.execute(code, filepath, quiet=False)

        if result is not None:
            print(f"Script result: {result}")

        return 0
    except Exception as e:
        print(f"Error executing script: {e}")
        return 1


def init_project(name: str, frontend: str = None):
    """Initialize new MCN project"""
    try:
        result = mcn_project_manager.create_project_structure(
            name, include_frontend=bool(frontend), frontend_framework=frontend
        )

        print(f"Created MCN project: {name}")
        print(f"Project path: {result['project_path']}")

        if frontend:
            print(f"Frontend framework: {frontend}")
            print(f"API client generated")

        print("\nNext steps:")
        print(f"   cd {name}")
        print("   pip install -r requirements.txt")
        print("   python -m mcn.mcn_cli mcn/main.mcn")

        return 0
    except Exception as e:
        log_error("PROJECT_INIT_ERROR", f"Failed to initialize project: {e}")
        return 1


def validate_project(path: str = "."):
    """Validate MCN project structure"""
    try:
        result = mcn_project_manager.validate_project_structure(path)

        if result["valid"]:
            print("Project structure is valid")
        else:
            print("Project structure issues found:")

            if result["missing_files"]:
                print("\nMissing files:")
                for file in result["missing_files"]:
                    print(f"  - {file}")

            if result["missing_dirs"]:
                print("\nMissing directories:")
                for dir in result["missing_dirs"]:
                    print(f"  - {dir}")

            if result["recommendations"]:
                print("\n💡 Recommendations:")
                for rec in result["recommendations"]:
                    print(f"  • {rec}")

        return 0 if result["valid"] else 1
    except Exception as e:
        log_error("PROJECT_VALIDATION_ERROR", f"Failed to validate project: {e}")
        return 1


def add_frontend(framework: str, path: str = "."):
    """Add frontend integration to existing project"""
    try:
        project_path = Path(path)

        # Detect existing endpoints
        endpoints = []
        mcn_files = list(project_path.glob("**/*.mcn"))

        for mcn_file in mcn_files:
            name = mcn_file.stem
            endpoints.append({"name": name, "path": f"/{name}", "method": "POST"})

        if not endpoints:
            endpoints = [{"name": "main", "path": "/main", "method": "POST"}]

        # Setup frontend
        frontend_dir = project_path / "frontend"
        frontend_dir.mkdir(exist_ok=True)

        mcn_frontend.project_path = frontend_dir
        config = mcn_frontend.create_frontend_config(framework, endpoints)

        print(f"Added {framework} frontend integration")
        print(f"API client: {config['client_file']}")
        print(f"Environment: {config['env_file']}")

        return 0
    except Exception as e:
        log_error("FRONTEND_ADD_ERROR", f"Failed to add frontend: {e}")
        return 1


def show_logs(log_type: str = "all"):
    """Show MCN logs"""
    try:
        logs_dir = Path("logs")
        if not logs_dir.exists():
            print("No logs directory found")
            return 1

        log_files = {
            "errors": logs_dir / "mcn_errors.log",
            "debug": logs_dir / "mcn_debug.log",
            "all": None,
        }

        if log_type == "all":
            for name, file_path in log_files.items():
                if name != "all" and file_path and file_path.exists():
                    print(f"\n=== {name.upper()} LOGS ===")
                    with open(file_path, "r") as f:
                        print(f.read()[-2000:])  # Last 2000 chars
        else:
            file_path = log_files.get(log_type)
            if file_path and file_path.exists():
                with open(file_path, "r") as f:
                    print(f.read())
            else:
                print(f"Log file not found: {log_type}")
                return 1

        return 0
    except Exception as e:
        log_error("LOGS_SHOW_ERROR", f"Failed to show logs: {e}")
        return 1


def _cmd_build(mcn_file: str, out_dir: str) -> int:
    """
    mcn build <file> [--out <dir>]

    Parses the MCN file, collects all component/app declarations via the
    evaluator, then runs the UICompiler to emit a React + shadcn/ui project.
    """
    from pathlib import Path
    src = Path(mcn_file)
    if not src.exists():
        print(f"Error: file not found: {mcn_file}")
        return 1

    out = Path(out_dir)

    try:
        from .lexer       import Lexer
        from .parser      import Parser
        from .evaluator   import Evaluator
        from .ui_compiler import UICompiler
        from .mcn_interpreter import MCNInterpreter
    except ImportError:
        from lexer       import Lexer
        from parser      import Parser
        from evaluator   import Evaluator
        from ui_compiler import UICompiler
        from mcn_interpreter import MCNInterpreter

    code = src.read_text(encoding="utf-8")

    # Parse
    tokens  = Lexer(code).tokenize()
    program = Parser(tokens).parse()

    # Run evaluator — registers components/app but doesn't serve
    interp    = MCNInterpreter()
    evaluator = interp._evaluator
    evaluator.execute_program(program)

    n_components = len(evaluator.components)
    has_app      = evaluator.app_decl is not None

    if n_components == 0 and not has_app:
        print(f"No component or app declarations found in {mcn_file}")
        return 1

    app_name = evaluator.app_decl.name if has_app else "App"
    print(f"\nBuilding: {app_name}")
    print(f"Components: {', '.join(evaluator.components) or 'none'}")
    print(f"Output:    {out}/\n")

    compiler = UICompiler(output_dir=out)
    compiler.compile(evaluator)

    print(f"\n✓ Frontend generated in {out}/")
    print(f"\nNext steps:")
    print(f"  cd {out}")
    print(f"  npm install")
    if compiler._shadcn_needed:
        pkgs = " ".join(sorted(compiler._shadcn_needed))
        print(f"  npx shadcn@latest add {pkgs}")
    print(f"  npm run dev")
    return 0


_MCN_CONFIG_PATH = Path.home() / ".mcn" / "config.json"


def _load_config() -> dict:
    if _MCN_CONFIG_PATH.exists():
        import json as _json
        try:
            return _json.loads(_MCN_CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_config(data: dict) -> None:
    import json as _json
    _MCN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MCN_CONFIG_PATH.write_text(_json.dumps(data, indent=2))


def _cmd_config(args) -> int:
    """mcn config set <key> <value>  |  mcn config get <key>  |  mcn config show"""
    cfg = _load_config()

    if args.config_action == "set":
        cfg[args.key] = args.value
        _save_config(cfg)
        print(f"Saved: {args.key} = {'*' * len(args.value)}")
        return 0

    elif args.config_action == "get":
        val = cfg.get(args.key)
        if val is None:
            print(f"Not set: {args.key}")
            return 1
        # Mask secret-looking values
        if "key" in args.key.lower() or "secret" in args.key.lower():
            print(f"{args.key} = {val[:8]}{'*' * max(0, len(val) - 8)}")
        else:
            print(f"{args.key} = {val}")
        return 0

    elif args.config_action == "show":
        if not cfg:
            print("No configuration saved. Use `mcn config set <key> <value>`.")
            return 0
        for k, v in cfg.items():
            is_secret = "key" in k.lower() or "secret" in k.lower()
            masked = v[:4] + "*" * max(4, len(v) - 4) if is_secret else v
            print(f"  {k} = {masked}")
        return 0

    print(f"Unknown config action: {args.config_action}")
    return 1


def _cmd_generate(args) -> int:
    """
    mcn generate "<description>" [--out <dir>] [--port N] [--build] [--model M] [--api-key K] [--quiet]

    Uses the MCNAgent to turn a natural-language description into a full
    MCN application (backend/main.mcn + ui/app.mcn), validates both files,
    and optionally compiles the React frontend.

    API key resolution order:
      1. --api-key flag
      2. ~/.mcn/config.json  (set with: mcn config set api_key sk-ant-...)
      3. ANTHROPIC_API_KEY env var
    """
    cfg = _load_config()
    api_key = (
        getattr(args, "api_key", None)
        or cfg.get("api_key")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    if not api_key:
        print("Error: No Claude API key found.")
        print("  Option 1 (recommended): mcn config set api_key sk-ant-...")
        print("  Option 2 (one-time):    mcn generate ... --api-key sk-ant-...")
        print("  Option 3 (env var):     export ANTHROPIC_API_KEY=sk-ant-...")
        return 1

    try:
        # Import from sibling package — works whether run as module or installed
        try:
            from mcn.ai.mcn_agent import MCNAgent
        except ImportError:
            # Fallback when running from within core_engine directory directly
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from ai.mcn_agent import MCNAgent
    except ImportError as exc:
        print(f"Error: could not import MCNAgent — {exc}")
        print("       Make sure `anthropic` is installed:  pip install anthropic")
        return 1

    agent = MCNAgent(api_key=api_key, model=args.model)
    verbose = not args.quiet

    if getattr(args, "build", False):
        result = agent.generate_and_build(
            description=args.description,
            output_dir=args.out,
            port=args.port,
            verbose=verbose,
        )
        build_rc = result.get("build_result", {}).get("returncode", 0)
        return 0 if build_rc == 0 else 1
    else:
        result = agent.generate(
            description=args.description,
            output_dir=args.out,
            port=args.port,
            verbose=verbose,
        )
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="MCN (Macincode Scripting Language) CLI v2.0"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command (default)
    run_parser = subparsers.add_parser("run", help="Run MCN script")
    run_parser.add_argument("file", help="MCN script file to execute")
    run_parser.add_argument(
        "--serve", action="store_true", help="Serve script as API endpoint"
    )
    run_parser.add_argument("--host", default="127.0.0.1", help="Server host")
    run_parser.add_argument("--port", type=int, default=8000, help="Server port")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize new MCN project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument(
        "--frontend",
        choices=["react", "vue", "angular", "vanilla"],
        help="Include frontend framework",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate project structure"
    )
    validate_parser.add_argument("--path", default=".", help="Project path to validate")

    # Add-frontend command
    frontend_parser = subparsers.add_parser(
        "add-frontend", help="Add frontend integration"
    )
    frontend_parser.add_argument(
        "framework",
        choices=["react", "vue", "angular", "vanilla"],
        help="Frontend framework",
    )
    frontend_parser.add_argument("--path", default=".", help="Project path")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show MCN logs")
    logs_parser.add_argument(
        "--type",
        choices=["errors", "debug", "all"],
        default="all",
        help="Log type to show",
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check", help="Static type-check a MCN script without running it"
    )
    check_parser.add_argument("file", help="MCN script file to check")
    check_parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors (exit 1 if any issues)"
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test", help="Run test blocks in MCN scripts"
    )
    test_parser.add_argument(
        "path", help="MCN script file or directory to test"
    )
    test_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Fmt command
    fmt_parser = subparsers.add_parser(
        "fmt", help="Format MCN source code"
    )
    fmt_parser.add_argument(
        "path", help="MCN script file or directory to format"
    )
    fmt_parser.add_argument(
        "--write", "-w", action="store_true",
        help="Rewrite file(s) in place (default: print to stdout)"
    )
    fmt_parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 if any file needs formatting (CI mode)"
    )

    # REPL command
    repl_parser = subparsers.add_parser("repl", help="Start interactive REPL")

    # Build command — compile MCN component/app blocks → React + shadcn frontend
    build_parser = subparsers.add_parser(
        "build", help="Compile MCN UI components to React + shadcn/ui"
    )
    build_parser.add_argument(
        "file", help="MCN source file containing component/app declarations"
    )
    build_parser.add_argument(
        "--out", default="frontend",
        help="Output directory for generated React project (default: frontend/)"
    )

    # Generate command — AI agent: natural language → MCN → React app
    gen_parser = subparsers.add_parser(
        "generate", aliases=["gen"],
        help="Generate a full MCN app from a natural-language description (requires ANTHROPIC_API_KEY)"
    )
    gen_parser.add_argument(
        "description",
        help="Natural-language description of the app to build"
    )
    gen_parser.add_argument(
        "--out", default=".",
        help="Output directory (default: current directory)"
    )
    gen_parser.add_argument(
        "--port", type=int, default=8080,
        help="Backend server port (default: 8080)"
    )
    gen_parser.add_argument(
        "--build", action="store_true",
        help="Also run `mcn build` on the generated UI after writing files"
    )
    gen_parser.add_argument(
        "--model", default="claude-opus-4-6",
        help="Claude model to use (default: claude-opus-4-6)"
    )
    gen_parser.add_argument(
        "--api-key", dest="api_key", default=None,
        help="Claude API key (overrides config file and env var)"
    )
    gen_parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress streaming output"
    )

    # Config command — store Claude API key and other settings
    config_parser = subparsers.add_parser(
        "config", help="Get or set MCN configuration (e.g. Claude API key)"
    )
    config_sub = config_parser.add_subparsers(dest="config_action")

    cfg_set = config_sub.add_parser("set", help="Set a config value")
    cfg_set.add_argument("key",   help="Config key   (e.g. api_key)")
    cfg_set.add_argument("value", help="Config value (e.g. sk-ant-...)")

    cfg_get = config_sub.add_parser("get", help="Get a config value")
    cfg_get.add_argument("key", help="Config key to retrieve")

    config_sub.add_parser("show", help="Show all saved config values")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Serve MCN scripts as APIs")
    serve_parser.add_argument("--dir", help="Directory containing MCN scripts")
    serve_parser.add_argument("--file", help="Single MCN script to serve")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Server host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")

    # Legacy support - direct file execution
    parser.add_argument("--repl", action="store_true", help="Start REPL mode (legacy)")
    parser.add_argument(
        "--serve", action="store_true", help="Serve script as API (legacy)"
    )
    parser.add_argument("--serve-dir", help="Serve directory as APIs (legacy)")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (legacy)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (legacy)")
    parser.add_argument("--version", action="version", version="MCN 2.0")

    args = parser.parse_args()

    # Handle new subcommands
    if args.command in ("generate", "gen"):
        return _cmd_generate(args)

    elif args.command == "config":
        if not getattr(args, "config_action", None):
            print("Usage: mcn config {set|get|show}")
            return 1
        return _cmd_config(args)

    elif args.command == "build":
        return _cmd_build(args.file, args.out)

    elif args.command == "test":
        try:
            from .test_runner import run_tests
        except ImportError:
            from test_runner import run_tests
        return run_tests(args.path, verbose=getattr(args, "verbose", False))

    elif args.command == "fmt":
        try:
            from .formatter import run_fmt
        except ImportError:
            from formatter import run_fmt
        return run_fmt(args.path,
                       write=getattr(args, "write", False),
                       check=getattr(args, "check", False))

    elif args.command == "check":
        return check_file(args.file, strict=getattr(args, "strict", False))
    elif args.command == "init":
        return init_project(args.name, args.frontend)
    elif args.command == "validate":
        return validate_project(args.path)
    elif args.command == "add-frontend":
        return add_frontend(args.framework, args.path)
    elif args.command == "logs":
        return show_logs(args.type)
    elif args.command == "repl":
        repl = MCNREPL()
        repl.run()
        return 0
    elif args.command == "run":
        if hasattr(args, "serve") and args.serve:
            try:
                from .mcn_server import serve_script
            except ImportError:
                from mcn_server import serve_script
            serve_script(args.file, args.host, args.port)
            return 0
        else:
            return run_file(args.file)
    elif args.command == "serve":
        try:
            from .mcn_server import serve_script, serve_directory
        except ImportError:
            from mcn_server import serve_script, serve_directory
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
        from mcn_server import serve_script

        serve_script(args.file, args.host, args.port)
        return 0
    elif args.serve_dir:
        from mcn_server import serve_directory

        serve_directory(args.serve_dir, args.host, args.port)
        return 0
    elif hasattr(args, "file") and args.file:
        return run_file(args.file)
    elif args.repl or len(sys.argv) == 1:
        repl = MCNREPL()
        repl.run()
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
