"""
mcn_deployer.py — Package an MCN workspace into a Docker-ready deployment zip.

Output structure inside the zip:
  <app-name>/
    backend/main.mcn          (all *.mcn files from workspace)
    ui/app.mcn                (if present)
    Dockerfile
    requirements.txt
    start.sh
    docker-compose.yml
    .env.example
    DEPLOY.md

Usage:
    from mcn.core_engine.mcn_deployer import deploy_workspace
    result = deploy_workspace("/path/to/workspace", app_name="my-app", target="zip")
    # result["zip_bytes"]   — bytes of the zip file
    # result["docker_cmd"]  — ready-to-run docker command string
    # result["cloud_url"]   — cloud URL if MCN_DEPLOY_URL is set, else None
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Templates ─────────────────────────────────────────────────────────────────

_DOCKERFILE = """FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc curl && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCN source
COPY . .

EXPOSE 8080

CMD ["python", "-m", "mcn.core_engine.mcn_cli", "run", "backend/main.mcn", \\
     "--serve", "--host", "0.0.0.0", "--port", "8080"]
"""

_REQUIREMENTS = """# MCN runtime
requests>=2.31.0
flask>=3.0.0
flask-cors>=4.0.0

# AI providers (install the ones you need)
# anthropic>=0.30.0
# openai>=1.0.0

# Database (install as needed)
# psycopg2-binary>=2.9.0
# pymysql>=1.1.0
# sqlalchemy>=2.0.0
"""

_DOCKER_COMPOSE = """\
services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - MCN_AI_PROVIDER=${MCN_AI_PROVIDER:-anthropic}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - OLLAMA_URL=${OLLAMA_URL:-}
      - DATABASE_URL=${DATABASE_URL:-}
    restart: unless-stopped
"""

_ENV_EXAMPLE = """\
# AI Provider — "anthropic" | "openai" | "ollama"
MCN_AI_PROVIDER=anthropic

# API keys (set the one you use)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_URL=http://localhost:11434

# Database (optional)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Stripe (optional)
STRIPE_SECRET_KEY=sk_live_...
"""

_START_SH = """\
#!/bin/bash
set -e
exec python -m mcn.core_engine.mcn_cli run backend/main.mcn \\
     --serve --host 0.0.0.0 --port "${PORT:-8080}"
"""

_DEPLOY_MD = """\
# Deploy your MCN app

## Quick start (Docker)

```bash
# Build and run
docker build -t {app_name} .
docker run -p 8080:8080 --env-file .env {app_name}
```

## Docker Compose

```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

## Manual (without Docker)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m mcn.core_engine.mcn_cli run backend/main.mcn --serve --port 8080
```

## Cloud platforms

### Railway
```bash
railway init && railway up
```

### Render
Connect your GitHub repo — use `start.sh` as the start command.

### Fly.io
```bash
fly launch --dockerfile Dockerfile
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy
```
"""


# ── Main function ──────────────────────────────────────────────────────────────

def deploy_workspace(
    workspace: "str | Path",
    app_name:  str  = "mcn-app",
    target:    str  = "zip",
) -> Dict[str, Any]:
    """
    Package a workspace directory into a deployable zip.

    Parameters
    ----------
    workspace : path to the MCN workspace (must contain backend/ and/or ui/)
    app_name  : name used for the root folder inside the zip and Docker image tag
    target    : "zip" | "docker" | "cloud"
                - "zip"    → just build and return the zip
                - "docker" → zip + emit a docker-build-and-run command
                - "cloud"  → zip + POST to MCN_DEPLOY_URL if set

    Returns
    -------
    dict with keys:
      zip_bytes        bytes
      files_included   list[str]
      docker_cmd       str   (ready to copy-paste)
      cloud_url        str | None
    """
    ws = Path(workspace).resolve()

    # ── Collect MCN source files ───────────────────────────────────────────────
    mcn_files: List[Path] = sorted(ws.rglob("*.mcn"))

    # Exclude generated frontend and hidden dirs
    mcn_files = [
        f for f in mcn_files
        if not any(p.startswith(".") or p in ("frontend", "node_modules", "__pycache__")
                   for p in f.relative_to(ws).parts)
    ]

    if not mcn_files:
        raise ValueError(f"No .mcn files found in workspace: {ws}")

    # ── Build zip in memory ────────────────────────────────────────────────────
    buf = io.BytesIO()
    included: List[str] = []

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        prefix = f"{app_name}/"

        # MCN source files
        for f in mcn_files:
            arc = prefix + str(f.relative_to(ws))
            zf.writestr(arc, f.read_text(encoding="utf-8"))
            included.append(arc)

        # Generated artifacts
        zf.writestr(prefix + "Dockerfile",          _DOCKERFILE)
        zf.writestr(prefix + "requirements.txt",    _REQUIREMENTS)
        zf.writestr(prefix + "docker-compose.yml",  _DOCKER_COMPOSE)
        zf.writestr(prefix + "start.sh",            _START_SH)
        zf.writestr(prefix + ".env.example",        _ENV_EXAMPLE)
        zf.writestr(prefix + "DEPLOY.md",           _DEPLOY_MD.format(app_name=app_name))

        included += [
            prefix + "Dockerfile",
            prefix + "requirements.txt",
            prefix + "docker-compose.yml",
            prefix + "DEPLOY.md",
        ]

    zip_bytes = buf.getvalue()

    # ── Docker command ─────────────────────────────────────────────────────────
    docker_cmd = (
        f"unzip {app_name}.zip && "
        f"cd {app_name} && "
        f"docker build -t {app_name} . && "
        f"docker run -p 8080:8080 --env-file .env {app_name}"
    )

    # ── Cloud upload (optional) ────────────────────────────────────────────────
    cloud_url: Optional[str] = None
    if target == "cloud":
        cloud_url = _upload_to_cloud(zip_bytes, app_name)

    return {
        "zip_bytes":      zip_bytes,
        "files_included": included,
        "docker_cmd":     docker_cmd,
        "cloud_url":      cloud_url,
    }


def _upload_to_cloud(zip_bytes: bytes, app_name: str) -> Optional[str]:
    """
    POST the zip to MCN_DEPLOY_URL (if set).
    Returns the deployment URL on success, None otherwise.

    Set MCN_DEPLOY_URL to your own deploy endpoint:
      export MCN_DEPLOY_URL=https://deploy.yourmcncloud.com/api/deploy
    """
    deploy_url = os.getenv("MCN_DEPLOY_URL", "").strip()
    if not deploy_url:
        return None

    try:
        import requests  # type: ignore
        resp = requests.post(
            deploy_url,
            files={"app": (f"{app_name}.zip", zip_bytes, "application/zip")},
            data={"app_name": app_name},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("url") or data.get("deploy_url") or deploy_url
        print(f"[mcn deploy] Cloud upload failed: {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        print(f"[mcn deploy] Cloud upload error: {exc}")

    return None
