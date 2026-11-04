"""Run, format, check and test MCN code; REPL state."""
import queue
import threading
from flask import Blueprint
from mcn.core_engine.display import to_text
from .core import (
    MCNInterpreter,
    Response,
    Severity,
    TestRunner,
    _EXEC_TIMEOUT_S,
    seed_demo_devices,
    _capture_stdout,
    _run_with_timeout,
    _sse,
    _validate_code,
    check_source,
    format_source,
    jsonify,
    request,
    stream_with_context,
)

bp = Blueprint("execute", __name__)

# ── MCN execute / format / check / test ───────────────────────────────────────

_REPL_INTERPRETERS = {}

@bp.route("/api/execute", methods=["POST"])
def execute_mcn():
    data = request.get_json(silent=True) or {}
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err, "output": []}), 400

    code = data.get("code", "")
    output_lines = []
    is_repl = bool(data.get("is_repl", False))
    session_id = data.get("session_id", "default")

    def run():
        if is_repl:
            if session_id not in _REPL_INTERPRETERS:
                _REPL_INTERPRETERS[session_id] = MCNInterpreter()
            interp = _REPL_INTERPRETERS[session_id]
        else:
            interp = MCNInterpreter()

        def _capture_log(*args):
            output_lines.append(" ".join(to_text(a) for a in args))
        interp._functions["log"]  = _capture_log
        interp._functions["echo"] = _capture_log

        # Demo devices for the IoT panel (kept between runs, so the panel's values stick)
        from mcn.core_engine.iot import shared_registry
        seed_demo_devices(shared_registry())

        with _capture_stdout() as buf:
            result = interp.execute(code, quiet=True)
            printed = buf.getvalue()
        if printed:
            output_lines.extend(printed.splitlines())
        return result

    try:
        result = _run_with_timeout(run, _EXEC_TIMEOUT_S)
        return jsonify({"success": True, "output": output_lines,
                        "result": to_text(result) if result is not None else None})
    except TimeoutError as e:
        return jsonify({"success": False, "error": str(e), "output": output_lines}), 408
    except Exception as e:
        diag = getattr(e, "diagnostic", None)   # set by MCNInterpreter for located errors
        return jsonify({"success": False, "error": str(e), "output": output_lines,
                        "diagnostic": diag.to_dict() if diag else None})


@bp.route("/api/repl/reset", methods=["POST"])
def repl_reset():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    if session_id in _REPL_INTERPRETERS:
        del _REPL_INTERPRETERS[session_id]
    return jsonify({"success": True})


_RESERVED_ENV_KEYS = {"true", "false", "null", "request_data"}

@bp.route("/api/repl/vars", methods=["GET"])
def repl_vars():
    session_id = request.args.get("session_id", "default")
    interp = _REPL_INTERPRETERS.get(session_id)
    if not interp:
        return jsonify({"vars": {}})
    vars_dict = {}
    evaluator = getattr(interp, "_evaluator", None)
    if evaluator and hasattr(evaluator, "globals") and hasattr(evaluator.globals, "_vars"):
        for k, v in evaluator.globals._vars.items():
            if not k.startswith("_") and k not in _RESERVED_ENV_KEYS and not callable(v):
                vars_dict[k] = str(v)
    return jsonify({"vars": vars_dict})


@bp.route("/api/format", methods=["POST"])
def fmt_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        formatted = format_source(data["code"])
        return jsonify({"success": True, "formatted": formatted, "changed": formatted != data["code"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/check", methods=["POST"])
def check_mcn():
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        issues = check_source(data["code"])
        error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
        return jsonify({
            "success":       True,
            "ok":            error_count == 0,
            "errors":        [f"Line {i.line}: {i.message}" for i in issues if i.severity == Severity.ERROR],
            "warnings":      [f"Line {i.line}: {i.message}" for i in issues if i.severity == Severity.WARNING],
            "issues":        [{"severity": i.severity.value, "line": i.line,
                               "col": i.col, "message": i.message} for i in issues],
            "error_count":   error_count,
            "warning_count": sum(1 for i in issues if i.severity == Severity.WARNING),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/test", methods=["POST"])
def test_mcn():
    """Batch test endpoint (non-streaming, for CLI / simple clients)."""
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return jsonify({"success": False, "error": err}), 400
    try:
        runner  = TestRunner(verbose=False)
        results = runner.run_source(data["code"], label="<playground>")
        passed  = sum(1 for r in results if r.passed)
        failed  = len(results) - passed
        output  = []
        for r in results:
            status = "✓" if r.passed else "✗"
            output.append(f"{status} {r.description}")
            if not r.passed and r.error:
                output.append(f"  {r.error}")
        if not results:
            output.append("(no tests found)")
        return jsonify({
            "success": failed == 0,
            "total": len(results), "passed": passed, "failed": failed,
            "output": output,
            "results": [{"description": r.description, "passed": r.passed,
                         "error": r.error if not r.passed else None,
                         "elapsed_ms": round(r.elapsed * 1000, 2)} for r in results],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/test/stream", methods=["POST"])
def test_mcn_stream():
    """Streaming SSE endpoint — emits each test result as it completes."""
    data = request.get_json(silent=True)
    err  = _validate_code(data)
    if err:
        return Response(_sse({"type": "error", "message": err}),
                        mimetype="text/event-stream"), 400

    code = data["code"]

    # Run tests in a background thread; feed results into a queue for SSE yield
    result_q: queue.Queue = queue.Queue()

    def _run_tests():
        runner = TestRunner(verbose=False)
        try:
            # Parse manually so we can stream per-test
            from mcn.core_engine.lexer    import Lexer as _L
            from mcn.core_engine.parser   import Parser as _P
            from mcn.core_engine.evaluator import Evaluator as _E
            import mcn.core_engine.ast_nodes as _ast
        except ImportError:
            try:
                from core_engine.lexer    import Lexer as _L    # type: ignore
                from core_engine.parser   import Parser as _P   # type: ignore
                from core_engine.evaluator import Evaluator as _E  # type: ignore
                import core_engine.ast_nodes as _ast             # type: ignore
            except ImportError:
                result_q.put({"type": "error", "message": "Cannot import MCN core"})
                result_q.put(None)
                return

        try:
            tokens  = _L(code).tokenize()
            program = _P(tokens).parse()
        except Exception as exc:
            result_q.put({"type": "error", "message": str(exc)})
            result_q.put(None)
            return

        setup_stmts = [s for s in program.body if not isinstance(s, _ast.TestDecl)]
        test_decls  = [s for s in program.body if isinstance(s, _ast.TestDecl)]

        if not test_decls:
            result_q.put({"type": "done", "total": 0, "passed": 0, "failed": 0})
            result_q.put(None)
            return

        result_q.put({"type": "start", "total": len(test_decls)})

        functions: dict = {}
        runner._register_builtins(functions)
        evaluator = _E(functions)
        try:
            evaluator._exec_block(setup_stmts, evaluator.globals)
        except Exception as exc:
            result_q.put({"type": "result", "description": "<setup>", "passed": False,
                          "error": f"Setup failed: {exc}", "elapsed_ms": 0})
            result_q.put({"type": "done", "total": 1, "passed": 0, "failed": 1})
            result_q.put(None)
            return

        passed = 0
        failed = 0
        for decl in test_decls:
            r = runner._run_test(decl, evaluator)
            passed += r.passed
            failed += not r.passed
            result_q.put({
                "type":        "result",
                "description": r.description,
                "passed":      r.passed,
                "error":       r.error if not r.passed else None,
                "elapsed_ms":  round(r.elapsed * 1000, 2),
            })

        result_q.put({"type": "done",
                      "total": len(test_decls), "passed": passed, "failed": failed})
        result_q.put(None)  # sentinel

    threading.Thread(target=_run_tests, daemon=True).start()

    def generate():
        while True:
            try:
                item = result_q.get(timeout=30)
            except queue.Empty:
                yield _sse({"type": "error", "message": "Test timeout"})
                break
            if item is None:
                break
            yield _sse(item)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
