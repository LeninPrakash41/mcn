"""
An MCN backend as a Vercel function.

`mcn deploy --target vercel` writes api/index.py, which calls create_app() with
the project folder. Every endpoint is then served at /api/<endpoint>.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def create_app(root: Path, data_dir: Optional[Path] = None):
    root = Path(root).resolve()
    # Vercel's filesystem is read-only except /tmp: logs, the auth secret and
    # the SQLite file go there (and last only as long as the instance)
    data_dir = Path(data_dir or os.environ.get("MCN_DATA_DIR") or "/tmp/mcn-app")
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MCN_HOME", str(data_dir / ".mcn"))
    os.environ.setdefault("MCN_IOT_SIMULATE", "1")          # no hardware on a serverless host
    os.chdir(data_dir)

    from fastapi import FastAPI
    from .mcn_server import MCNServer

    files = sorted((root / "backend").rglob("*.mcn"))
    if not files:
        raise RuntimeError(f"No backend .mcn files in {root / 'backend'}")
    server = MCNServer()
    for f in files:
        server.load_script(str(f))

    @server.app.get("/", include_in_schema=False)
    async def health():
        return {"status": "ok", "endpoints": sorted(n for ev in server.evaluators for n in ev.function_params)}

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/api", server.app)     # Vercel passes the original path, /api/<endpoint>
    app.mount("/", server.app)
    return app
