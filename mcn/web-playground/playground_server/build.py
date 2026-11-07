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

def _extract_create_tables(text: str):
    """Robustly extract table names and column definition bodies from SQL CREATE TABLE statements,
    handling nested parentheses like `DEFAULT (datetime('now'))` or `NUMERIC(12, 2)`.
    """
    results = []
    pattern = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\(', re.IGNORECASE)
    for m in pattern.finditer(text):
        tname = m.group(1).strip()
        start_idx = m.end()
        depth = 1
        i = start_idx
        in_single_quote = False
        in_double_quote = False
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif not in_single_quote and not in_double_quote:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        if depth == 0:
            body = text[start_idx:i].strip()
            results.append((tname, body))
    return results


def _split_columns(body: str):
    """Split comma-separated column definitions without splitting inside quotes or nested parentheses."""
    cols = []
    current = []
    depth = 0
    in_single_quote = False
    in_double_quote = False
    for ch in body:
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(ch)
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(ch)
        elif ch == '(' and not in_single_quote and not in_double_quote:
            depth += 1
            current.append(ch)
        elif ch == ')' and not in_single_quote and not in_double_quote:
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0 and not in_single_quote and not in_double_quote:
            c = ''.join(current).strip()
            if c:
                cols.append(c)
            current = []
        else:
            current.append(ch)
    if current:
        c = ''.join(current).strip()
        if c:
            cols.append(c)
    return cols


def _format_pg_column(col: str, dialect: str = "postgres") -> str:
    """Format and quote SQLite column definition for PostgreSQL / Supabase."""
    col = col.strip()
    if not col:
        return ""
    parts = col.split(None, 1)
    if not parts:
        return col
    col_name = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    # Quote column name if it collides with reserved words or types (e.g. `text TEXT` or `order INTEGER`)
    clean_name = col_name.strip('"`[]')
    reserved = {
        "text", "user", "order", "group", "table", "select", "check",
        "default", "limit", "offset", "primary", "from", "where", "column",
        "values", "key", "desc", "asc", "type", "all", "case"
    }
    if clean_name.lower() in reserved:
        col_name = f'"{clean_name}"'
    else:
        col_name = clean_name

    if dialect in ("postgres", "supabase"):
        rest = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'SERIAL PRIMARY KEY', rest, flags=re.IGNORECASE)
        rest = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b', 'SERIAL PRIMARY KEY', rest, flags=re.IGNORECASE)
        rest = re.sub(r'\bTEXT\b', 'VARCHAR(255)', rest, flags=re.IGNORECASE)
        rest = re.sub(r'\bREAL\b', 'NUMERIC(12, 2)', rest, flags=re.IGNORECASE)
        rest = re.sub(r"DEFAULT\s*\(datetime\('now'\)\)", "DEFAULT NOW()", rest, flags=re.IGNORECASE)
        rest = re.sub(r"DEFAULT\s*\(CURRENT_TIMESTAMP\)", "DEFAULT NOW()", rest, flags=re.IGNORECASE)

    return f"{col_name} {rest}".strip()


@bp.route("/api/database/export_migrations")
def export_database_migrations():
    """Translate workspace SQLite tables and contracts into PostgreSQL / Supabase DDL migrations."""
    import sqlite3
    dialect = request.args.get("dialect", "postgres").lower()
    
    ws = _request_workspace()
    mcn_texts = []
    
    # 1. Collect all .mcn files in the current workspace
    for f in sorted(ws.rglob("*.mcn")):
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
        lines.append('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";\n')

    created_tables = set()

    # 1. Parse CREATE TABLE statements from MCN code with paren nesting support
    for tname, body in _extract_create_tables(all_code):
        lower_tname = tname.lower()
        if lower_tname in created_tables:
            continue
        created_tables.add(lower_tname)

        col_defs = []
        for col in _split_columns(body):
            formatted_col = _format_pg_column(col, dialect=dialect)
            if formatted_col:
                col_defs.append(f"    {formatted_col}")

        lines.append(f"CREATE TABLE IF NOT EXISTS {tname} (\n" + ",\n".join(col_defs) + "\n);\n")

        if dialect == "supabase":
            lines.append(f"-- Enable Row Level Security for Supabase\nALTER TABLE {tname} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY \"Allow authenticated read\" ON {tname} FOR SELECT TO authenticated USING (true);\n")

    # 2. Inspect active workspace SQLite database (mcn_data.db) for any tables already created dynamically
    candidate_db_paths = [
        ws / "mcn_data.db",
        Path("mcn_data.db"),
        Path.home() / ".mcn" / "playground" / "mcn_data.db"
    ]
    for db_path in candidate_db_paths:
        if db_path.exists() and db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
                for tname, sql in cursor.fetchall():
                    if not sql or tname.lower() in created_tables:
                        continue
                    # Extract definition body from the sqlite sql
                    extracted = _extract_create_tables(sql)
                    if extracted:
                        _, body = extracted[0]
                    else:
                        m = re.search(r'\((.*)\)', sql, re.DOTALL)
                        body = m.group(1) if m else ""
                    if not body:
                        continue

                    created_tables.add(tname.lower())
                    col_defs = []
                    for col in _split_columns(body):
                        formatted_col = _format_pg_column(col, dialect=dialect)
                        if formatted_col:
                            col_defs.append(f"    {formatted_col}")

                    lines.append(f"-- Discovered from active SQLite store: {db_path.name}\nCREATE TABLE IF NOT EXISTS {tname} (\n" + ",\n".join(col_defs) + "\n);\n")
                    if dialect == "supabase":
                        lines.append(f"-- Enable Row Level Security for Supabase\nALTER TABLE {tname} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY \"Allow authenticated read\" ON {tname} FOR SELECT TO authenticated USING (true);\n")
                conn.close()
            except Exception:
                pass

    # 3. Parse contract declarations for any models not already translated
    type_map = {
        "str": "VARCHAR(255)",
        "int": "INTEGER",
        "float": "NUMERIC(12, 2)",
        "bool": "BOOLEAN",
        "datetime": "TIMESTAMPTZ DEFAULT NOW()",
        "date": "DATE",
        "json": "JSONB",
        "dict": "JSONB",
        "list": "JSONB"
    }
    for m in re.finditer(r'contract\s+([A-Za-z0-9_]+)\b[^\n]*\n((?:[ \t]+[A-Za-z0-9_]+[ \t]*:[ \t]*[^\n]+\n?)+)', all_code):
        cname = m.group(1).strip()
        if cname.endswith('y'):
            tname = cname[:-1].lower() + 'ies'
        elif cname.endswith('s'):
            tname = cname.lower()
        else:
            tname = cname.lower() + 's'

        if tname in created_tables:
            continue
        created_tables.add(tname)

        col_defs = ["    id SERIAL PRIMARY KEY"]
        for line in m.group(2).strip().splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            field_name, field_type = [part.strip() for part in line.split(':', 1)]
            pg_type = type_map.get(field_type.lower(), "VARCHAR(255)")
            clean_name = field_name.strip('"`[]')
            if clean_name.lower() in {"text", "user", "order", "group", "table", "select", "check", "default"}:
                field_name = f'"{clean_name}"'
            col_defs.append(f"    {field_name} {pg_type}")
        col_defs.append("    created_at TIMESTAMPTZ DEFAULT NOW()")

        lines.append(f"-- Derived from contract {cname}\nCREATE TABLE IF NOT EXISTS {tname} (\n" + ",\n".join(col_defs) + "\n);\n")
        if dialect == "supabase":
            lines.append(f"-- Enable Row Level Security for Supabase\nALTER TABLE {tname} ENABLE ROW LEVEL SECURITY;\nCREATE POLICY \"Allow authenticated read\" ON {tname} FOR SELECT TO authenticated USING (true);\n")

    migration_sql = "\n".join(lines)
    return jsonify({
        "success": True,
        "dialect": dialect,
        "filename": "001_initial_schema.sql",
        "migration_sql": migration_sql
    })
