"""
`mcn deploy --target vercel`: the staged project, the function that serves the
backend at /api, and the upload (with a fake Vercel CLI).
"""
import json
import runpy
import shutil
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import vercel_deploy  # noqa: E402

TEMPLATE = ROOT / "mcn" / "web-playground" / "playground_server" / "templates" / "ops_dashboard"


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "app"
    shutil.copytree(TEMPLATE, ws)
    (ws / ".env").write_text("ANTHROPIC_API_KEY=sk-test\nMCN_API_TOKEN=abc\nUNRELATED=nope\n")
    return ws


def test_stage_writes_a_vercel_project(workspace):
    out = vercel_deploy.stage(workspace, "Ops Dashboard")
    assert out == workspace / ".mcn" / "deploy" / "ops-dashboard"
    config = json.loads((out / "vercel.json").read_text())
    assert config["outputDirectory"] == "frontend/dist"
    assert config["functions"]["api/index.py"]["includeFiles"] == "backend/**"
    assert {"source": "/api/(.*)", "destination": "/api/index"} in config["rewrites"]
    assert (out / "frontend" / ".env.production").read_text() == "VITE_API_URL=/api\n"
    assert (out / "frontend" / "src" / "App.tsx").exists()
    assert (out / "backend" / "main.mcn").exists()
    assert "mcn-lang[postgres] @" in (out / "requirements.txt").read_text()


def test_restaging_keeps_the_vercel_link(workspace):
    out = vercel_deploy.stage(workspace, "app")
    (out / ".vercel").mkdir()
    (out / ".vercel" / "project.json").write_text("{}")
    vercel_deploy.stage(workspace, "app")
    assert (out / ".vercel" / "project.json").exists()


def test_function_serves_the_backend_at_api(workspace, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    out = vercel_deploy.stage(workspace, "app")
    monkeypatch.setenv("MCN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    app = runpy.run_path(str(out / "api" / "index.py"))["app"]
    client = TestClient(app)
    res = client.post("/api/summary", json={})
    assert res.status_code == 200 and res.json()["success"] is True
    assert res.headers["x-content-type-options"] == "nosniff"
    assert client.post("/api/query", json={}).status_code == 404
    assert (tmp_path / "data" / "mcn_data.db").exists()        # SQLite lives in the writable folder


def test_needs_a_backend_service(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text('log("no service")')
    with pytest.raises(vercel_deploy.DeployError, match="service"):
        vercel_deploy.stage(tmp_path, "app")


def test_deploy_runs_the_cli_with_settings(workspace, tmp_path, monkeypatch):
    args_file = tmp_path / "args.json"
    fake = tmp_path / "vercel"
    fake.write_text("#!/usr/bin/env python3\nimport json, sys\n"
                    f"json.dump(sys.argv[1:], open({str(args_file)!r}, 'w'))\n"
                    "print('https://ops-dashboard-abc123.vercel.app')\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(vercel_deploy, "vercel_command", lambda: [str(fake)])
    result = vercel_deploy.deploy(workspace, "ops-dashboard", prod=True, token="tok", interactive=False, log=lambda m: None)
    assert result["url"] == "https://ops-dashboard-abc123.vercel.app"
    args = json.loads(args_file.read_text())
    assert args[:3] == ["deploy", "--yes", "--prod"] and args[-2:] == ["--token", "tok"]
    envs = dict(a.split("=", 1) for a in args[args.index("--env") + 1::2] if "=" in a)
    assert envs["ANTHROPIC_API_KEY"] == "sk-test" and envs["MCN_API_TOKEN"] == "abc"
    assert "UNRELATED" not in envs and len(envs["MCN_AUTH_SECRET"]) == 64
    first_secret = envs["MCN_AUTH_SECRET"]
    vercel_deploy.deploy(workspace, "ops-dashboard", token="tok", interactive=False, log=lambda m: None)
    again = json.loads(args_file.read_text())
    assert f"MCN_AUTH_SECRET={first_secret}" in again          # the same secret every deploy


def test_studio_needs_a_token(monkeypatch):
    from playground_app import load, quiet
    _, client = load()
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    res = quiet(client.post, "/api/deploy/vercel", json={"app_name": "x"})
    assert res.status_code == 400 and res.get_json()["needs_token"] is True


def test_postgres_placeholders():
    from mcn.core_engine.mcn_runtime import _pg_placeholders
    assert _pg_placeholders("SELECT * FROM t WHERE a = ? AND b LIKE '5%?' AND c > ?") == \
        "SELECT * FROM t WHERE a = %s AND b LIKE '5%%?' AND c > %s"
