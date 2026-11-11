"""
An MCN app in one container: the compiled web app at / and the backend at /api.

`mcn deploy --target aws` and `--target cloudflare` build a Docker image that runs:

    python -m mcn.core_engine.container_app /app

Settings come from the environment (PORT, DATABASE_URL, MCN_AUTH_SECRET, MCN_SSO_*, ...).
The container's own disk doesn't last across restarts on these hosts, so keep data
in PostgreSQL (DATABASE_URL) rather than the default SQLite file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def create_app(root: Path, data_dir: Optional[Path] = None):
    root = Path(root).resolve()
    data_dir = Path(data_dir or os.environ.get("MCN_DATA_DIR") or "/tmp/mcn-app")
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MCN_HOME", str(data_dir / ".mcn"))
    os.environ.setdefault("MCN_IOT_SIMULATE", "1")
    os.chdir(data_dir)                        # the SQLite file, logs and audit log live here

    from fastapi import FastAPI
    from fastapi.responses import FileResponse
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
    app.mount("/api", server.app)

    dist = root / "frontend" / "dist"
    if dist.is_dir():
        index = dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        async def web(path: str):
            # Files from the build as they are; any other path is the single-page app
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(index)
    return app


def main(argv=None) -> None:
    import uvicorn
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0] if args else ".")
    uvicorn.run(create_app(root), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
