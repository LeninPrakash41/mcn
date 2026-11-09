"""Preview serving and the Vite/MCN dev servers."""
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Optional
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

bp = Blueprint("devserver", __name__)

# Token for services declared with `auth "token"` while previewing. The backend
# gets it as MCN_API_TOKEN and the preview sends it as a bearer token.
_DEV_TOKEN = os.getenv("MCN_API_TOKEN") or secrets.token_urlsafe(24)


def _mcn_path() -> str:
    """PYTHONPATH that lets the backend process import MCN from wherever this Studio runs it."""
    import mcn
    root = str(Path(mcn.__file__).resolve().parent.parent)
    return os.pathsep.join(filter(None, [root, os.environ.get("PYTHONPATH")]))


def _env(**extra) -> dict:
    # MCN_DEV_TOOLS lets Studio's IoT panel see and drive the backend's devices
    return {**os.environ, "MCN_API_TOKEN": _DEV_TOKEN, "MCN_DEV_TOOLS": "1",
            "MCN_IOT_SIMULATE": os.getenv("MCN_IOT_SIMULATE", "1"), **extra}

_PREVIEW_PAGE = Path(__file__).resolve().parent / "preview_live.html"


def _compile_ui(ws: Path) -> Optional[str]:
    """Compile ui/app.mcn into frontend/ when the UI is newer than the build.
    Returns an error report, or None on success."""
    ui = ws / "ui" / "app.mcn"
    app_tsx = ws / "frontend" / "src" / "App.tsx"
    if not ui.exists():
        return "There's no ui/app.mcn to preview yet."
    if app_tsx.exists() and app_tsx.stat().st_mtime >= ui.stat().st_mtime:
        return None
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.core_engine.ui_compiler import UICompiler, endpoints_from_backend
    interp = MCNInterpreter()
    try:
        interp.execute(ui.read_text(encoding="utf-8"), str(ui), quiet=True)
    except Exception as exc:           # the friendly report, with line and caret
        return str(exc)
    UICompiler(output_dir=ws / "frontend", endpoints=endpoints_from_backend(ws / "backend" / "main.mcn")) \
        .compile(interp._evaluator)
    return None


@bp.route("/preview/")
@bp.route("/preview")
@bp.route("/preview/index.html")
def serve_preview_index():
    """The live preview: runs the compiled app with the MCN UI kit in the browser."""
    return send_from_directory(str(_PREVIEW_PAGE.parent), _PREVIEW_PAGE.name, max_age=0)


@bp.route("/api/preview/source")
def preview_source():
    """The compiled app's own files (the kit comes from the preview bundle)."""
    ws = _request_workspace()
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        error = _compile_ui(ws)
    if error:
        return jsonify({"success": False, "error": error})
    src = ws / "frontend" / "src"
    files = {}
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src).as_posix()
        if p.is_file() and p.suffix in (".ts", ".tsx", ".css") and not rel.startswith(("components/ui/", "lib/")):
            files[rel] = p.read_text(encoding="utf-8")
    return jsonify({"success": True, "files": files, "api_url": f"http://localhost:{_BACKEND_PORT}",
                    "api_token": _DEV_TOKEN,
                    "backend_running": bool(core._mcn_backend and core._mcn_backend.poll() is None)})


def _backend_running() -> bool:
    return bool(core._mcn_backend and core._mcn_backend.poll() is None)


def _start_backend(ws: Path) -> bool:
    """(Re)start backend/main.mcn as an API on _BACKEND_PORT. False when there's no service to run."""
    backend_file = ws / "backend" / "main.mcn"
    if not backend_file.exists() or "service " not in backend_file.read_text(encoding="utf-8"):
        return False
    _stop_process(core._mcn_backend)
    try:
        b_out = open(ws / "backend_stdout.log", "w", encoding="utf-8")
        b_err = open(ws / "backend_stderr.log", "w", encoding="utf-8")
        core._mcn_backend = subprocess.Popen(
            [sys.executable, "-m", "mcn.core_engine.mcn_cli", "serve",
             "--file", str(backend_file), "--host", "0.0.0.0",
             "--port", str(_BACKEND_PORT)],
            # Run in the workspace so the app's database is the one DB Explorer shows
            cwd=str(ws),
            env=_env(PYTHONPATH=_mcn_path()),
            stdout=b_out,
            stderr=b_err,
        )
        b_out.close()
        b_err.close()
        import time; time.sleep(1)
        return True
    except Exception:
        return False  # Non-fatal


# ── Mobile preview: the generated Flutter app, built for the web, in the phone frame ──

_MOBILE_JOB: dict = {"state": "idle"}


def _flutter_web_build(ws: Path) -> None:
    import shutil
    mobile, log = ws / "mobile", _MOBILE_JOB["log"]

    def step(label, cmd):
        log.append(label)
        proc = subprocess.run(cmd, cwd=mobile, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-12:]
            raise RuntimeError(label + " failed:\n" + "\n".join(tail))

    try:
        flutter = shutil.which("flutter")
        if not (mobile / "web").exists():
            step("Adding web support to the Flutter project…",
                 [flutter, "create", "--platforms=web", "--project-name", "mcn_mobile_app", "."])
            (mobile / "test" / "widget_test.dart").unlink(missing_ok=True)   # the template test isn't for this app
            readme = mobile / "README.md"
            if readme.exists() and "A new Flutter project" in readme.read_text(encoding="utf-8"):
                readme.unlink()
        step("Compiling the Flutter app (the first build takes about 30 seconds)…",
             [flutter, "build", "web", "--release", "--no-web-resources-cdn", "--base-href", "/preview-mobile/",
              f"--dart-define=MCN_API_URL=http://localhost:{_BACKEND_PORT}", f"--dart-define=MCN_API_TOKEN={_DEV_TOKEN}"])
        _MOBILE_JOB.update({"state": "done", "url": f"/preview-mobile/?v={int(__import__('time').time())}"})
    except Exception as exc:
        _MOBILE_JOB.update({"state": "failed", "error": str(exc)})


@bp.route("/api/mobile/preview", methods=["POST"])
def mobile_preview():
    """Build the phone preview. With Flutter installed, it's the real Flutter app built for the
    web; without, it's the same components rendered at phone size."""
    import shutil
    import threading
    from .build import build_flutter, build_react
    ws = _request_workspace()
    if _MOBILE_JOB.get("state") == "running":
        return jsonify({"success": True, **{k: v for k, v in _MOBILE_JOB.items() if k != "log"}})
    try:
        info = build_flutter(ws)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Couldn't generate the Flutter app: {exc}"}), 400
    _start_backend(ws)
    if shutil.which("flutter") and info["source"] == "ui/app.mcn":
        _MOBILE_JOB.clear()
        _MOBILE_JOB.update({"state": "running", "mode": "flutter", "log": []})
        threading.Thread(target=_flutter_web_build, args=(ws,), daemon=True).start()
        return jsonify({"success": True, "state": "running", "mode": "flutter", "files": info["files"]})
    try:
        build_react(ws)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Couldn't build the preview: {exc}"}), 400
    reason = "Install Flutter to preview the native app here" if not shutil.which("flutter") else \
        "This project has no UI components, so the preview shows the web layout"
    return jsonify({"success": True, "state": "done", "mode": "web", "url": "/preview/", "note": reason, "files": info["files"]})


@bp.route("/api/mobile/preview", methods=["GET"])
def mobile_preview_status():
    job = dict(_MOBILE_JOB)
    job["step"] = (job.pop("log", None) or [""])[-1]
    return jsonify({"success": True, **job})


@bp.route("/preview-mobile/", defaults={"path": "index.html"})
@bp.route("/preview-mobile/<path:path>")
def mobile_preview_files(path):
    if core.is_hosted() and not core._current_user():
        return jsonify({"error": "Sign in to use MCN Studio", "needs_login": True}), 401
    web = _request_workspace() / "mobile" / "build" / "web"
    if not (web / path).is_file():
        path = "index.html"
    return send_from_directory(web, path, max_age=0)


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
    _start_backend(ws)

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
                env=_env(VITE_API_TOKEN=_DEV_TOKEN),
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
