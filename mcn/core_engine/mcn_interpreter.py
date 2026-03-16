"""
MCN Interpreter — public orchestration layer.

All language implementation lives in dedicated modules:
  lexer.py      — tokenisation with column tracking + INDENT/DEDENT
  parser.py     — token stream → typed AST (ast_nodes.py)
  evaluator.py  — tree-walking execution with lexical scoping

This file wires those three modules together and registers all built-in
functions.  The public API is unchanged: MCNInterpreter.execute(code).

Backward-compat exports:
  MCNLexer  = Lexer    (used by test/debug scripts)
  MCNParser = Parser   (used by test/debug scripts)
  TokenType = TT       (alias for token-type enum)
"""
import os
import traceback
import time
from typing import Any, Callable, Dict, Optional

from .mcn_logger import log_error, log_step, log_performance
from .lexer     import Lexer, TT, Token
from .parser    import Parser
from .evaluator import Evaluator, MCNError

# ── Backward-compat aliases ────────────────────────────────────────────────────
MCNLexer  = Lexer
MCNParser = Parser
TokenType = TT

# ── Core protection metadata ───────────────────────────────────────────────────
MCN_CORE_VERSION     = "2.0.0"
MCN_CORE_SIGNATURE   = "MCN-OFFICIAL-INTERPRETER"
MCN_TRADEMARK_NOTICE = "MCN is a trademark of MCN Foundation"
MCN_COPYRIGHT        = "Copyright (c) 2025 MCN Foundation"


def verify_mcn_authenticity() -> bool:
    """Verify this is an official MCN distribution."""
    sig = os.path.join(os.path.dirname(__file__), ".mcn_official")
    return os.path.exists(sig)


class ReturnValue(Exception):
    """Kept for any external code that may catch it."""
    def __init__(self, value: Any):
        self.value = value
        super().__init__()


# ── Main interpreter ───────────────────────────────────────────────────────────

class MCNInterpreter:
    """
    High-level MCN interpreter.

    Lifecycle:
      1. Instantiate once (registers built-ins, initialises v2 features).
      2. Call .execute(code) one or more times.
      3. Optionally call .register_function(name, fn) to add external callables.

    The underlying Evaluator maintains a persistent global environment across
    multiple .execute() calls in the same session (REPL mode), which matches
    the previous behaviour.
    """

    def __init__(self):
        # Built-in function registry — shared with the Evaluator so that
        # user-defined functions declared during execution are also visible.
        self._functions: Dict[str, Callable] = {}
        self._register_builtin_functions()
        self._init_v2_features()

        # Create the evaluator with the shared functions dict
        self._evaluator = Evaluator(self._functions)

    # ── Backward-compat properties (used by tests / server) ───────────────────

    @property
    def variables(self) -> Dict[str, Any]:
        """Flat view of the global scope (backward-compat)."""
        return self._evaluator.variables

    @property
    def functions(self) -> Dict[str, Callable]:
        return self._functions

    @property
    def user_functions(self) -> Dict[str, Callable]:
        return self._functions

    # ── Public API ─────────────────────────────────────────────────────────────

    def register_function(self, name: str, func: Callable) -> None:
        """Expose a Python callable to MCN scripts."""
        self._functions[name] = func

    def execute(self, code: str, file_path: str = None,
                quiet: bool = False) -> Any:
        """
        Lex, parse, and evaluate a MCN source string.

        Parameters
        ----------
        code      : MCN source text
        file_path : used in error / log messages only
        quiet     : suppress step-level logging (used in production/server mode)
        """
        start = time.time()
        try:
            if not quiet:
                log_step("Starting MCN execution", file_path=file_path)

            # ── Lexical analysis ──────────────────────────────────────────────
            tokens = Lexer(code).tokenize()
            if not quiet:
                log_step("Tokenisation complete", token_count=len(tokens))

            # ── Parsing ───────────────────────────────────────────────────────
            program = Parser(tokens).parse()
            if not quiet:
                log_step("Parsing complete",
                         statement_count=len(program.body))

            # ── Execution ─────────────────────────────────────────────────────
            result = self._evaluator.execute_program(program)
            elapsed = time.time() - start
            if not quiet:
                log_performance(
                    "MCN execution", elapsed,
                    statements=len(program.body),
                    variables=len(self.variables),
                    functions=len(self._functions),
                )
            return result

        except Exception as exc:
            elapsed = time.time() - start
            msg     = str(exc)

            if "LexError" in msg or "ParseError" in msg:
                error_type = "SYNTAX_ERROR"
            elif "Undefined variable" in msg or "Undefined function" in msg:
                error_type = "REFERENCE_ERROR"
            elif "RuntimeError" in msg:
                error_type = "RUNTIME_ERROR"
            else:
                error_type = "RUNTIME_ERROR"

            log_error(
                error_type, msg,
                context={
                    "code_snippet": code[:200] + ("..." if len(code) > 200 else ""),
                    "execution_time": elapsed,
                    "traceback": traceback.format_exc(),
                },
                file_path=file_path,
            )
            raise Exception(f"MCN {error_type}: {msg}") from exc

    # ── Built-in function registration ─────────────────────────────────────────

    def _register_builtin_functions(self):
        from .mcn_runtime import MCNRuntime
        self.runtime = MCNRuntime()

        # ── Core runtime built-ins ────────────────────────────────────────────
        self._functions.update({
            "log":                self.runtime.log,
            "echo":               self._echo,
            "trigger":            self.runtime.trigger,
            "query":              self.runtime.query,
            "workflow":           self.runtime.workflow,
            "env":                self._env,
            "read_file":          self._read_file,
            "write_file":         self._write_file,
            "append_file":        self._append_file,
            "fetch":              self._fetch,
            "send_email":         self.runtime.send_email,
            "hash_data":          self.runtime.hash_data,
            "encode_base64":      self.runtime.encode_base64,
            "decode_base64":      self.runtime.decode_base64,
            "now":                self.runtime.now,
            "format_date":        self.runtime.format_date,
            "connect_postgresql": self.runtime.connect_postgresql,
            "connect_mongodb":    self.runtime.connect_mongodb,
        })

        # ── AI / intelligent primitives (Layer 1) ─────────────────────────────
        from .ai_builtins import register_ai_builtins
        register_ai_builtins(self._functions)

    def _init_v2_features(self):
        """Initialise MCN 2.0 features (packages, async, type hints, AI context)."""
        from .mcn_extensions import (
            MCNAIContext, MCNPackageManager, MCNAsyncRuntime, MCNTypeChecker,
            create_db_package, create_http_package, create_ai_package,
        )

        self.ai_context      = MCNAIContext()
        self.package_manager = MCNPackageManager()
        self.async_runtime   = MCNAsyncRuntime()
        self.type_checker    = MCNTypeChecker()

        self.package_manager.add_package("db",   create_db_package())
        self.package_manager.add_package("http", create_http_package())
        self.package_manager.add_package("ai",   create_ai_package())

        self._functions.update({
            "task": self._create_task,
            "await": self._await_tasks,
            "use":  self._use_package,
            "type": self._set_type_hint,
        })

    # ── Built-in implementations ───────────────────────────────────────────────

    def _echo(self, message: Any) -> None:
        print(message)

    def _env(self, key: str) -> Optional[str]:
        return os.getenv(key)

    def _read_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            raise Exception(f"Failed to read file '{filepath}': {exc}") from exc

    def _write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as exc:
            raise Exception(f"Failed to write file '{filepath}': {exc}") from exc

    def _append_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as exc:
            raise Exception(f"Failed to append to '{filepath}': {exc}") from exc

    def _fetch(self, url: str) -> Dict:
        import requests
        try:
            resp = requests.get(url, timeout=30)
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else resp.text
            )
            return {
                "status_code": resp.status_code,
                "data":        body,
                "success":     200 <= resp.status_code < 300,
            }
        except Exception as exc:
            return {"status_code": 0, "data": str(exc), "success": False}

    def _create_task(self, name: str, func_name: str, *args: Any) -> str:
        if func_name in self._functions:
            task = self.async_runtime.create_task(
                name, self._functions[func_name], *args
            )
            return f"Task '{name}' created"
        raise Exception(f"Function '{func_name}' not found")

    def _await_tasks(self, *task_names: str) -> Any:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.async_runtime.await_tasks(*task_names)
            )
        finally:
            loop.close()

    def _use_package(self, package_name: str) -> str:
        pkg_fns = self.package_manager.get_package_functions(package_name)
        if pkg_fns:
            self._functions.update(pkg_fns)
            return f"Package '{package_name}' loaded"
        raise Exception(f"Package '{package_name}' not found")

    def _set_type_hint(self, var_name: str, var_type: str) -> str:
        self.type_checker.add_type_hint(var_name, var_type)
        return f"Type hint set: {var_name} -> {var_type}"
