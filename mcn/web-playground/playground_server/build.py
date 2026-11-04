"""Compile UI to React/Flutter, download and deploy projects, SQL migrations."""
import io
import json
import os
import re
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from flask import Blueprint
from .core import (
    Response,
    _request_workspace,
    jsonify,
    request,
)
from .workspace_seed import (
    _DEFAULT_MOBILE_MANIFEST,
)

bp = Blueprint("build", __name__)

# ── Build ─────────────────────────────────────────────────────────────────────

@bp.route("/api/build", methods=["POST"])
def build_mcn():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "react")

    # Optionally pre-save both files from the request body
    for key, rel in (("backend", "backend/main.mcn"), ("ui", "ui/app.mcn")):
        if key in data and data[key]:
            (_request_workspace() / rel).parent.mkdir(parents=True, exist_ok=True)
            (_request_workspace() / rel).write_text(data[key], encoding="utf-8")

    ui_path  = _request_workspace() / "ui" / "app.mcn"
    backend_path = _request_workspace() / "backend" / "main.mcn"

    if platform == "flutter":
        try:
            result = build_flutter(_request_workspace())
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()})
        return jsonify({"success": True, "platform": "flutter", **result,
                        "stdout": f"✓ Generated the Flutter app from {result['source']}: {len(result['files'])} files in mobile/\n"})

    # Default: React Compilation via UICompiler
    out_path = _request_workspace() / "frontend"
    if not ui_path.exists():
        return jsonify({"success": False, "error": "ui/app.mcn not found. Create or select a UI template."}), 400


    try:
        try:
            from mcn.core_engine.lexer import Lexer
            from mcn.core_engine.parser import Parser
            from mcn.core_engine.mcn_interpreter import MCNInterpreter
            from mcn.core_engine.ui_compiler import UICompiler
        except ImportError:
            from core_engine.lexer import Lexer  # type: ignore
            from core_engine.parser import Parser  # type: ignore
            from core_engine.mcn_interpreter import MCNInterpreter  # type: ignore
            from core_engine.ui_compiler import UICompiler  # type: ignore
        
        code = ui_path.read_text(encoding="utf-8")
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()
        interp = MCNInterpreter()
        evaluator = interp._evaluator
        evaluator.execute_program(program)
        
        out_path.mkdir(parents=True, exist_ok=True)
        from mcn.core_engine.ui_compiler import endpoints_from_backend
        compiler = UICompiler(output_dir=out_path, endpoints=endpoints_from_backend(backend_path))
        written = compiler.compile(evaluator)
        
        files = []
        if out_path.exists():
            for p in sorted(out_path.rglob("*")):
                if p.is_file() and "node_modules" not in p.parts and ".vite" not in p.parts:
                    files.append(str(p.relative_to(_request_workspace())))
                    
        stdout = f"✓ Compiled {len(written)} frontend components into frontend/\n"
        if compiler._shadcn_needed:
            stdout += f"UI components used: {', '.join(sorted(compiler._shadcn_needed))}"
            
        return jsonify({
            "success": True,
            "platform": "react",
            "files": files,
            "stdout": stdout,
            "stderr": ""
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {str(e)}", "trace": traceback.format_exc()})


def build_flutter(ws: Path) -> dict:
    """Generate mobile/ from ui/app.mcn's components (or, without any, from mobile/ui-manifest.json)."""
    out_path = ws / "mobile"
    out_path.mkdir(parents=True, exist_ok=True)
    ui_path, backend_path = ws / "ui" / "app.mcn", ws / "backend" / "main.mcn"
    legacy_flutter = ws / "flutter"
    # Only Studio's own workspace — never a developer's project (`mcn studio <dir>`)
    if legacy_flutter.exists() and not os.environ.get("MCN_WORKSPACE"):
        import shutil
        shutil.rmtree(legacy_flutter, ignore_errors=True)

    evaluator = None
    if ui_path.exists():
        from mcn.core_engine.mcn_interpreter import MCNInterpreter
        interp = MCNInterpreter()
        interp.execute(ui_path.read_text(encoding="utf-8"), str(ui_path), quiet=True)
        if interp._evaluator.components:
            evaluator = interp._evaluator
    if evaluator is not None:
        from mcn.fullstack.flutter_compiler import FlutterCompiler
        from mcn.core_engine.ui_compiler import endpoints_from_backend
        FlutterCompiler(endpoints=endpoints_from_backend(backend_path)).compile(evaluator, out_path, "mcn_mobile_app")
        (out_path / "ui-manifest.json").unlink(missing_ok=True)     # the components are the source now
        source = "ui/app.mcn"
    else:
        manifest_path = out_path / "ui-manifest.json"
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(_DEFAULT_MOBILE_MANIFEST, indent=2), encoding="utf-8")
        from mcn.fullstack.flutter_generator import FlutterProjectGenerator
        FlutterProjectGenerator().generate_project(str(manifest_path), str(out_path), "mcn_mobile_app")
        source = "mobile/ui-manifest.json"
    files = [str(p.relative_to(ws)) for p in sorted(out_path.rglob("*"))
             if p.is_file() and not _is_build_output(p.relative_to(out_path))]
    return {"files": files, "source": source}


def build_react(ws: Path) -> list:
    """Compile ui/app.mcn to frontend/. Returns the files written."""
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    from mcn.core_engine.ui_compiler import UICompiler, endpoints_from_backend
    interp = MCNInterpreter()
    interp.execute((ws / "ui" / "app.mcn").read_text(encoding="utf-8"), quiet=True)
    return UICompiler(output_dir=ws / "frontend", endpoints=endpoints_from_backend(ws / "backend" / "main.mcn")).compile(interp._evaluator)


def _is_build_output(rel: Path) -> bool:
    """Flutter's and the toolchain's own folders inside mobile/, which don't belong in listings or zips."""
    return bool(set(rel.parts) & {"build", ".dart_tool", ".idea", ".gradle", "Pods", "node_modules"}) or rel.suffix == ".iml"


# ── Production Download & Scaffolds ───────────────────────────────────────────

_MOBILE_README = """# {name}: mobile app

The Flutter app in `mobile/` is compiled from `ui/app.mcn`, and calls the MCN
backend in `backend/`.

## Run it

1. Start the backend (install MCN first: https://github.com/LeninPrakash41/mcn):

       mcn serve backend/main.mcn --host 0.0.0.0

2. Run the app (install Flutter first: https://docs.flutter.dev/get-started/install):

       cd mobile
       flutter create .          # first time only: adds the android/ios/web folders
       flutter pub get
       flutter run --dart-define=MCN_API_URL=http://localhost:8080

   On an Android emulator use `MCN_API_URL=http://10.0.2.2:8080`; on a real
   phone use your computer's address on the same network. If the backend uses
   `auth "token"`, add `--dart-define=MCN_API_TOKEN=...`.

3. Build for release:

       flutter build apk --dart-define=MCN_API_URL=https://your-api.example.com
       flutter build ios --dart-define=MCN_API_URL=https://your-api.example.com

To change the app, edit `ui/app.mcn` and rebuild it in MCN Studio (App view),
which regenerates `mobile/lib/`.

`Dockerfile` and `docker-compose.yml` run the backend on any server.
"""


@bp.route("/api/download")
def download_project():
    """Zip the project for one platform: the React app (web) or the Flutter app (mobile),
    with the backend and the files to deploy it. The app is rebuilt first, so the zip
    always matches the code."""
    platform = request.args.get("platform", "react").lower()
    ws = _request_workspace()
    scaffolds_dir = Path(__file__).resolve().parent.parent / "scaffolds"
    has_ui = (ws / "ui" / "app.mcn").exists()
    try:
        if platform == "flutter":
            build_flutter(ws)
        elif has_ui:
            build_react(ws)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Build failed, so there's nothing to download: {exc}"}), 400

    def add_tree(zf, folder: Path, skip=lambda rel: False):
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(folder)
            if p.is_file() and not skip(rel) and "__pycache__" not in rel.parts:
                zf.write(p, p.relative_to(ws))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if platform == "flutter":
            add_tree(zf, ws / "mobile", _is_build_output)
        elif (ws / "frontend").exists():
            add_tree(zf, ws / "frontend", lambda rel: bool(set(rel.parts) & {"node_modules", ".vite", "dist"}))
        if (ws / "backend").exists():
            add_tree(zf, ws / "backend", lambda rel: rel.suffix in (".db", ".log"))
        for p in sorted(ws.glob("*.mcn")):
            zf.write(p, p.relative_to(ws))
        if (ws / "ui").exists():
            for p in sorted((ws / "ui").rglob("*.mcn")):
                zf.write(p, p.relative_to(ws))

        # Files to deploy the backend (and, for the web app, nginx and CI)
        web_only = {"nginx.conf", "ci-cd.yml"}
        if scaffolds_dir.exists():
            for sc in sorted(scaffolds_dir.rglob("*")):
                if sc.is_file() and sc.name != ".DS_Store" and not (platform == "flutter" and sc.name in web_only):
                    zf.write(sc, str(sc.relative_to(scaffolds_dir)))
        else:
            from mcn.core_engine.mcn_deployer import _DOCKERFILE
            zf.writestr("Dockerfile", _DOCKERFILE)
            zf.writestr("docker-compose.yml", "services:\n  app:\n    build: .\n    ports:\n      - \"8080:8080\"\n")
            zf.writestr(".env.example", "PORT=8080\n# A long random string, e.g. the output of: openssl rand -hex 32\nMCN_AUTH_SECRET=\nMCN_API_TOKEN=\n")
        if platform == "flutter":
            zf.writestr("README.md", _MOBILE_README.format(name=ws.name if ws.name != "playground" else "MCN app"))

    buf.seek(0)
    filename = "mcn-flutter-app.zip" if platform == "flutter" else "mcn-fullstack-app.zip"
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/api/deploy", methods=["POST"])
def deploy_project():
    """Package the workspace into a Docker-ready zip and return it as base64 JSON."""
    data     = request.get_json(silent=True) or {}
    app_name = (data.get("app_name") or "mcn-app").strip().replace(" ", "-") or "mcn-app"
    target   = data.get("target", "zip")

    try:
        try:
            from mcn.core_engine.mcn_deployer import deploy_workspace
        except ImportError:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
            from core_engine.mcn_deployer import deploy_workspace  # type: ignore

        result   = deploy_workspace(_request_workspace(), app_name=app_name, target=target)
        import base64
        zip_b64  = base64.b64encode(result["zip_bytes"]).decode()
        return jsonify({
            "success":        True,
            "app_name":       app_name,
            "target":         target,
            "files_included": result["files_included"],
            "docker_cmd":     result["docker_cmd"],
            "cloud_url":      result.get("cloud_url"),
            "zip_b64":        zip_b64,
            "zip_filename":   f"{app_name}.zip",
            "size_kb":        len(result["zip_bytes"]) // 1024,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ── Deploy to Vercel (runs in the background; the page polls for the result) ──

_VERCEL_JOB: dict = {"state": "idle"}


@bp.route("/api/deploy/vercel", methods=["POST"])
def deploy_vercel():
    import threading
    from mcn.core_engine.vercel_deploy import DeployError, deploy
    if _VERCEL_JOB.get("state") == "running":
        return jsonify({"success": False, "error": "A deployment is already running"}), 409
    if not os.environ.get("VERCEL_TOKEN"):
        return jsonify({"success": False, "needs_token": True,
                        "error": "Add a VERCEL_TOKEN in Secrets first. Create one at https://vercel.com/account/tokens"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("app_name") or "mcn-app").strip() or "mcn-app"
    workspace = _request_workspace()
    log: list = []
    _VERCEL_JOB.clear()
    _VERCEL_JOB.update({"state": "running", "log": log, "started": time.time()})

    def run():
        try:
            result = deploy(workspace, name, prod=bool(data.get("prod")), interactive=False, log=log.append)
            _VERCEL_JOB.update({"state": "done", **result})
        except DeployError as exc:
            _VERCEL_JOB.update({"state": "failed", "error": str(exc)})
        except Exception as exc:
            _VERCEL_JOB.update({"state": "failed", "error": f"Deploy failed: {exc}"})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "state": "running"})


@bp.route("/api/deploy/vercel", methods=["GET"])
def deploy_vercel_status():
    job = {k: v for k, v in _VERCEL_JOB.items() if k != "started"}
    return jsonify({"success": True, **job})


# ── Multi-Database SQL Migration Generator ────────────────────────────────────

@bp.route("/api/database/export_migrations")
def export_database_migrations():
    """Translate workspace SQLite tables and contracts into PostgreSQL / Supabase DDL migrations."""
    dialect = request.args.get("dialect", "postgres").lower()
    
    mcn_texts = []
    for f in sorted(_request_workspace().rglob("*.mcn")):
        if f.is_file() and not any(p in ("node_modules", "frontend", ".git", "__pycache__") for p in f.parts):
            try:
                mcn_texts.append(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    all_code = "\n".join(mcn_texts)
    
    lines = [
        f"-- =============================================================================",
        f"-- MCN Database Migration Schema ({dialect.upper()})",
        f"-- Generated at: {datetime.now().isoformat()}",
        f"-- =============================================================================\n",
    ]

    if dialect in ("postgres", "supabase"):
        lines.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";\n")

    # 1. Parse CREATE TABLE statements
    for m in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\(([^)]+)\)', all_code, re.IGNORECASE):
        tname = m.group(1).strip()
        body = m.group(2).strip()

        col_defs = []
        for col in body.split(","):
            col = col.strip()
            if not col: continue
            
            if dialect in ("postgres", "supabase"):
                col = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', col, flags=re.IGNORECASE)
                col = re.sub(r'\bTEXT\b', 'VARCHAR(255)', col, flags=re.IGNORECASE)
                col = re.sub(r'\bREAL\b', 'NUMERIC(12, 2)', col, flags=re.IGNORECASE)
                col = re.sub(r"DEFAULT\s*\(datetime\('now'\)\)", "DEFAULT NOW()", col, flags=re.IGNORECASE)
            col_defs.append(f"    {col}")

        lines.append(f"CREATE TABLE IF NOT EXISTS {tname} (\n" + ",\n".join(col_defs) + "\n);\n")

        if dialect == "supabase":
            lines.append(f"-- Enable Row Level Security for Supabase\nALTER TABLE {tname} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY \"Allow authenticated read\" ON {tname} FOR SELECT TO authenticated USING (true);\n")

    migration_sql = "\n".join(lines)
    return jsonify({
        "success": True,
        "dialect": dialect,
        "filename": "001_initial_schema.sql",
        "migration_sql": migration_sql
    })
