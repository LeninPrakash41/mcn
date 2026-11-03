"""Preview serving and the Vite/MCN dev servers."""
import subprocess
import sys
from . import core
from flask import Blueprint
from .core import (
    _BACKEND_PORT,
    _DEV_PORT,
    _NPM_AVAILABLE,
    _ROOT_DIR,
    _request_workspace,
    _stop_process,
    jsonify,
    send_from_directory,
)
from .preview_html import (
    _generate_interactive_preview_html,
)

bp = Blueprint("devserver", __name__)

@bp.route("/preview/<path:filename>")
def serve_preview_static_file(filename):
    ws = _request_workspace()
    frontend = ws / "frontend"
    dist = frontend / "dist"
    if dist.exists() and (dist / filename).exists():
        return send_from_directory(str(dist), filename)
    if (frontend / filename).exists():
        return send_from_directory(str(frontend), filename)
    return serve_preview_index()


@bp.route("/preview/")
@bp.route("/preview")
@bp.route("/preview/index.html")
def serve_preview_index():
    ws = _request_workspace()
    frontend = ws / "frontend"
    dist = frontend / "dist"
    if dist.exists() and (dist / "index.html").exists():
        return send_from_directory(str(dist), "index.html")
    
    app_tsx = frontend / "src" / "App.tsx"
    comps_dir = frontend / "src" / "components"

    # Auto-compile ui/app.mcn on the fly if frontend files are not compiled yet
    if (not app_tsx.exists() or not app_tsx.read_text(encoding="utf-8").strip()) and (ws / "ui" / "app.mcn").exists():
        try:
            from mcn.core_engine.lexer import Lexer
            from mcn.core_engine.parser import Parser
            from mcn.core_engine.mcn_interpreter import MCNInterpreter
            from mcn.core_engine.ui_compiler import UICompiler
            
            ui_code = (ws / "ui" / "app.mcn").read_text(encoding="utf-8")
            tokens = Lexer(ui_code).tokenize()
            program = Parser(tokens).parse()
            interp = MCNInterpreter()
            evaluator = interp._evaluator
            evaluator.execute_program(program)
            compiler = UICompiler(output_dir=frontend)
            compiler.compile(evaluator)
        except Exception:
            pass
    
    app_code = app_tsx.read_text(encoding="utf-8") if app_tsx.exists() else ""
    
    components_code = {}
    if comps_dir.exists():
        for p in sorted(comps_dir.glob("*.tsx")):
            components_code[p.stem] = p.read_text(encoding="utf-8")

    return _generate_interactive_preview_html(ws, app_code, components_code)


@bp.route("/api/devserver/start", methods=["POST"])
def devserver_start():
    ws           = _request_workspace()
    frontend     = ws / "frontend"
    backend_file = ws / "backend" / "main.mcn"

    if not (frontend / "package.json").exists():
        return jsonify({"success": False, "error": "frontend/package.json not found. Run ⚡ Build first."}), 400

    if core._dev_server and core._dev_server.poll() is None:
        return jsonify({
            "success": True,
            "port": _DEV_PORT,
            "pid": core._dev_server.pid,
            "already_running": True,
            "mode": "vite",
            "preview_url": f"http://localhost:{_DEV_PORT}",
            "backend_port": _BACKEND_PORT if (core._mcn_backend and core._mcn_backend.poll() is None) else None,
        })

    # ── 1. Start MCN backend (if backend/main.mcn has a service declaration) ─
    if backend_file.exists():
        backend_src = backend_file.read_text(encoding="utf-8")
        if "service " in backend_src:
            _stop_process(core._mcn_backend)
            try:
                b_out = open(ws / "backend_stdout.log", "w", encoding="utf-8")
                b_err = open(ws / "backend_stderr.log", "w", encoding="utf-8")
                core._mcn_backend = subprocess.Popen(
                    [sys.executable, "-m", "mcn.core_engine.mcn_cli", "serve",
                     "--file", str(backend_file), "--host", "0.0.0.0",
                     "--port", str(_BACKEND_PORT)],
                    cwd=str(_ROOT_DIR),
                    stdout=b_out,
                    stderr=b_err,
                )
                b_out.close()
                b_err.close()
                import time; time.sleep(1)
            except Exception:
                pass  # Non-fatal

    # ── 2. If node_modules exists, start Vite dev server ───────────────────────
    if _NPM_AVAILABLE and (frontend / "node_modules").exists():
        stdout_file = ws / "vite_stdout.log"
        stderr_file = ws / "vite_stderr.log"
        try:
            f_out = open(stdout_file, "w", encoding="utf-8")
            f_err = open(stderr_file, "w", encoding="utf-8")
            core._dev_server = subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", str(_DEV_PORT), "--host", "--strictPort"],
                cwd=str(frontend),
                stdout=f_out,
                stderr=f_err,
            )
            f_out.close()
            f_err.close()
            import time; time.sleep(2)
            if core._dev_server.poll() is None:
                return jsonify({
                    "success":      True,
                    "port":         _DEV_PORT,
                    "pid":          core._dev_server.pid,
                    "mode":         "vite",
                    "preview_url":  f"http://localhost:{_DEV_PORT}",
                    "backend_port": _BACKEND_PORT if (core._mcn_backend and core._mcn_backend.poll() is None) else None,
                })
        except Exception:
            pass

    # ── 3. Fallback: Fast, instant interactive React Preview ──────────────────
    return jsonify({
        "success":      True,
        "port":         None,
        "mode":         "static",
        "preview_url":  "/preview/index.html",
        "backend_port": _BACKEND_PORT if (core._mcn_backend and core._mcn_backend.poll() is None) else None,
        "message":      "Serving interactive React application at /preview/index.html",
    })


@bp.route("/api/devserver/stop", methods=["POST"])
def devserver_stop():
    _stop_process(core._dev_server)
    core._dev_server = None
    _stop_process(core._mcn_backend)
    core._mcn_backend = None
    return jsonify({"success": True})


@bp.route("/api/devserver/status")
def devserver_status():
    running         = core._dev_server is not None and core._dev_server.poll() is None
    backend_running = core._mcn_backend is not None and core._mcn_backend.poll() is None
    return jsonify({
        "running":         running,
        "port":            _DEV_PORT if running else None,
        "pid":             core._dev_server.pid if running else None,
        "backend_running": backend_running,
        "backend_port":    _BACKEND_PORT if backend_running else None,
        "npm_available":   _NPM_AVAILABLE,
    })
