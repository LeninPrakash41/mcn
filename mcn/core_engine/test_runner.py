"""
MCN Test Runner — executes `test` blocks defined in .mx/.mcn scripts.

Syntax:
    test "adds two numbers"
        assert add(2, 3) == 5

    test "classify routes correctly"
        var intent = classify("I want a refund", ["buy", "return"])
        assert intent == "return", "expected return intent"

    test "null-safe access"
        var user = null
        assert user?.name == null

Usage (CLI):
    mcn test script.mx
    mcn test tests/              ← runs all .mx/.mcn files in directory
    mcn test script.mx --verbose

Exit codes:
    0 — all tests passed
    1 — at least one test failed
"""
from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Any, List, Tuple

from .lexer     import Lexer
from .parser    import Parser
from .evaluator import Evaluator, MCNError
from . import ast_nodes as ast


# ── Colours (disabled when not a tty) ─────────────────────────────────────────
_IS_TTY = os.isatty(1)

def _green(s: str)  -> str: return f"\033[32m{s}\033[0m" if _IS_TTY else s
def _red(s: str)    -> str: return f"\033[31m{s}\033[0m" if _IS_TTY else s
def _yellow(s: str) -> str: return f"\033[33m{s}\033[0m" if _IS_TTY else s
def _bold(s: str)   -> str: return f"\033[1m{s}\033[0m"  if _IS_TTY else s
def _dim(s: str)    -> str: return f"\033[2m{s}\033[0m"  if _IS_TTY else s


# ── Result types ───────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, description: str, passed: bool,
                 error: str = "", elapsed: float = 0.0):
        self.description = description
        self.passed      = passed
        self.error       = error
        self.elapsed     = elapsed

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"TestResult({status}, {self.description!r})"


# ── Runner ─────────────────────────────────────────────────────────────────────

class TestRunner:
    """
    Discovers and runs all `test` blocks in one or more MCN source files.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    # ── Public API ─────────────────────────────────────────────────────────────

    def run_file(self, filepath: str) -> List[TestResult]:
        """Parse a single .mx/.mcn file and run all its test blocks."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            return [TestResult(f"<open {filepath}>", False, str(e))]

        return self.run_source(source, filepath)

    def run_source(self, source: str, label: str = "<source>") -> List[TestResult]:
        """Parse source code and execute every TestDecl block."""
        try:
            tokens  = Lexer(source).tokenize()
            program = Parser(tokens).parse()
        except Exception as exc:
            return [TestResult(f"<parse {label}>", False, str(exc))]

        # Separate setup statements from test blocks
        setup_stmts = [s for s in program.body if not isinstance(s, ast.TestDecl)]
        test_decls  = [s for s in program.body if isinstance(s, ast.TestDecl)]

        if not test_decls:
            return []

        # Run setup once (defines functions, variables, contracts, etc.)
        functions: dict = {}
        self._register_builtins(functions)
        evaluator = Evaluator(functions)
        try:
            evaluator._exec_block(setup_stmts, evaluator.globals)
        except Exception as exc:
            return [TestResult("<setup>", False,
                               f"Setup failed: {exc}\n{traceback.format_exc()}")]

        # Run each test block in a fresh child scope
        results: List[TestResult] = []
        for decl in test_decls:
            results.append(self._run_test(decl, evaluator))

        return results

    def run_directory(self, dirpath: str) -> List[Tuple[str, List[TestResult]]]:
        """Discover and run all .mx and .mcn files under `dirpath`."""
        root = Path(dirpath)
        files = sorted(
            list(root.rglob("*.mx")) + list(root.rglob("*.mcn"))
        )
        return [(str(f), self.run_file(str(f))) for f in files]

    # ── Core execution ─────────────────────────────────────────────────────────

    def _run_test(self, decl: ast.TestDecl,
                  evaluator: Evaluator) -> TestResult:
        """Execute a single test block; return pass/fail."""
        start = time.perf_counter()
        try:
            # Each test gets its own scope so side-effects don't leak
            from .evaluator import Environment
            test_env = Environment(evaluator.globals)
            evaluator._exec_block(decl.body, test_env)
            elapsed = time.perf_counter() - start
            return TestResult(decl.description, True, elapsed=elapsed)
        except MCNError as exc:
            elapsed = time.perf_counter() - start
            return TestResult(decl.description, False,
                              error=str(exc), elapsed=elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return TestResult(decl.description, False,
                              error=f"{type(exc).__name__}: {exc}",
                              elapsed=elapsed)

    def _register_builtins(self, functions: dict):
        """Wire the same built-ins the interpreter uses."""
        from .mcn_interpreter import MCNInterpreter
        tmp = MCNInterpreter()
        functions.update(tmp._functions)

    # ── Reporting ──────────────────────────────────────────────────────────────

    def report(self, results: List[TestResult]) -> int:
        """Print results and return exit code (0 = all pass)."""
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        for r in results:
            elapsed_str = _dim(f"  ({r.elapsed * 1000:.1f} ms)")
            if r.passed:
                print(f"  {_green('✓')} {r.description}{elapsed_str}")
                if self.verbose:
                    print()
            else:
                print(f"  {_red('✗')} {r.description}{elapsed_str}")
                print(f"    {_red(r.error)}")

        total = len(results)
        print()
        if failed == 0:
            print(_green(_bold(f"  All {total} test(s) passed.")))
        else:
            print(_red(_bold(f"  {failed}/{total} test(s) failed.")))

        return 0 if failed == 0 else 1

    def report_files(self,
                     file_results: List[Tuple[str, List[TestResult]]]) -> int:
        """Print per-file results and return exit code."""
        overall_exit = 0
        total_pass = total_fail = 0

        for filepath, results in file_results:
            if not results:
                if self.verbose:
                    print(_dim(f"\n  {filepath} — no tests"))
                continue

            passed = sum(1 for r in results if r.passed)
            failed = len(results) - passed
            total_pass += passed
            total_fail += failed

            label = _bold(filepath)
            print(f"\n{label}")
            self.report(results)
            if failed:
                overall_exit = 1

        if total_pass + total_fail > 0:
            print()
            if overall_exit == 0:
                print(_green(_bold(f"All {total_pass} test(s) passed across all files.")))
            else:
                print(_red(_bold(
                    f"{total_fail} failed, {total_pass} passed "
                    f"({total_pass + total_fail} total)."
                )))
        return overall_exit


# ── CLI entry point (called from mcn_cli.py) ───────────────────────────────────

def run_tests(path: str, verbose: bool = False) -> int:
    """
    Entry point for `mcn test <file-or-dir>`.
    Returns exit code 0 (all pass) or 1 (any failure).
    """
    runner = TestRunner(verbose=verbose)
    p = Path(path)

    if p.is_dir():
        file_results = runner.run_directory(path)
        if not any(r for _, r in file_results):
            print(_yellow(f"No test blocks found in {path}"))
            return 0
        return runner.report_files(file_results)
    else:
        results = runner.run_file(path)
        if not results:
            print(_yellow(f"No test blocks found in {path}"))
            return 0
        print(_bold(f"\n{path}"))
        return runner.report(results)
