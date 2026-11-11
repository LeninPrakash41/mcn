"""
`mcn deploy --target aws` (App Runner) and `--target cloudflare` (Containers): the
staged project, the container app, and the deploy steps with fake cloud CLIs.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import container_deploy  # noqa: E402
from mcn.core_engine.vercel_deploy import DeployError  # noqa: E402

TEMPLATE = ROOT / "mcn" / "web-playground" / "playground_server" / "templates" / "ops_dashboard"


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "app"
    shutil.copytree(TEMPLATE, ws)
    (ws / ".env").write_text("DATABASE_URL=postgres://db\nMCN_SSO_ISSUER=https://idp\nUNRELATED=x\n")
    return ws


def test_aws_stage_is_one_container_with_the_web_app(workspace):
    out = container_deploy.stage(workspace, "Ops Dashboard", "aws")
    assert out == workspace / ".mcn" / "deploy" / "ops-dashboard-aws"
    dockerfile = (out / "Dockerfile").read_text()
    assert "npm run build" in dockerfile and "frontend/dist" in dockerfile
    assert 'CMD ["python", "-m", "mcn.core_engine.container_app", "/app"]' in dockerfile
    assert (out / "frontend" / ".env.production").read_text() == "VITE_API_URL=/api\n"
    assert (out / "backend" / "main.mcn").exists()


def test_cloudflare_stage_serves_assets_and_routes_api(workspace):
    out = container_deploy.stage(workspace, "ops", "cloudflare")
    config = json.loads((out / "wrangler.jsonc").read_text())
    assert config["containers"][0]["class_name"] == "MCNApp" and config["containers"][0]["image"] == "./Dockerfile"
    assert config["durable_objects"]["bindings"][0]["name"] == "MCN_APP"
    assert config["assets"]["run_worker_first"] == ["/api/*"]
    assert config["assets"]["not_found_handling"] == "single-page-application"
    worker = (out / "src" / "index.ts").read_text()
    assert 'import { Container } from "@cloudflare/containers"' in worker
    assert "this.envVars = vars" in worker and '"MCN_SSO_ISSUER"' in worker and '"DATABASE_URL"' in worker
    assert "npm run build" not in (out / "Dockerfile").read_text()      # Cloudflare serves the web app itself
    assert json.loads((out / "package.json").read_text())["dependencies"]["@cloudflare/containers"]


def test_needs_a_service(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text('log("hi")')
    with pytest.raises(DeployError, match="service"):
        container_deploy.stage(tmp_path, "x", "aws")


def test_container_app_serves_api_and_spa(workspace, tmp_path):
    from fastapi.testclient import TestClient
    from mcn.core_engine.container_app import create_app
    out = container_deploy.stage(workspace, "ops", "aws")
    (out / "frontend" / "dist").mkdir(parents=True)
    (out / "frontend" / "dist" / "index.html").write_text("<div id=root></div>")
    (out / "frontend" / "dist" / "app.js").write_text("console.log(1)")
    client = TestClient(create_app(out, data_dir=tmp_path / "data"))
    assert client.post("/api/summary", json={}).json()["success"] is True
    assert "summary" in client.get("/api/").json()["endpoints"]
    assert client.get("/app.js").text == "console.log(1)"
    assert "root" in client.get("/orders/42").text                       # client-side route
    assert "root" in client.get("/../../etc/passwd").text                 # never a file outside dist


class FakeCLI:
    """Records commands and answers like the AWS CLI, Docker, npm and Wrangler."""

    def __init__(self, service_exists=False):
        self.calls = []
        self.service_exists = service_exists

    def __call__(self, cmd, cwd, input_text=None, env=None, capture=True):
        self.calls.append(cmd)
        out, code = "", 0
        joined = " ".join(cmd)
        if "sts get-caller-identity" in joined:
            out = json.dumps({"Account": "123456789012"})
        elif "ecr describe-repositories" in joined:
            code = 1
        elif "ecr get-login-password" in joined:
            out = "pw"
        elif "iam get-role" in joined:
            out = json.dumps({"Role": {"Arn": "arn:aws:iam::123456789012:role/MCNAppRunnerECRAccess"}})
        elif "apprunner list-services" in joined:
            out = json.dumps({"ServiceSummaryList": [{"ServiceName": "ops", "ServiceArn": "arn:svc"}]
                              if self.service_exists else []})
        elif "apprunner create-service" in joined or "apprunner update-service" in joined:
            out = json.dumps({"Service": {"ServiceUrl": "abc123.eu-west-1.awsapprunner.com"}})
        elif cmd[:3] == ["npx", "wrangler", "deploy"]:
            out = "Deployed ops\n  https://ops.acme.workers.dev\n"
        return subprocess.CompletedProcess(cmd, code, out, "")


def test_deploy_aws_creates_the_service(workspace, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")
    cli = FakeCLI()
    result = container_deploy.deploy_aws(workspace, "ops", region="eu-west-1", log=lambda m: None, run=cli)
    assert result["url"] == "https://abc123.eu-west-1.awsapprunner.com" and result["region"] == "eu-west-1"
    joined = [" ".join(c) for c in cli.calls]
    assert any("ecr create-repository --repository-name ops" in c for c in joined)
    assert any(c.startswith("docker build --platform linux/amd64 -t 123456789012.dkr.ecr.eu-west-1.amazonaws.com/ops:latest") for c in joined)
    create = next(c for c in cli.calls if "create-service" in c)
    source = json.loads(create[create.index("--source-configuration") + 1])
    env = source["ImageRepository"]["ImageConfiguration"]["RuntimeEnvironmentVariables"]
    assert env["DATABASE_URL"] == "postgres://db" and env["MCN_SSO_ISSUER"] == "https://idp"
    assert "UNRELATED" not in env and len(env["MCN_AUTH_SECRET"]) == 64
    assert all("--region" in c and "eu-west-1" in c for c in cli.calls if c[0] == "aws")


def test_deploy_aws_updates_an_existing_service(workspace, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")
    cli = FakeCLI(service_exists=True)
    container_deploy.deploy_aws(workspace, "ops", region="eu-west-1", log=lambda m: None, run=cli)
    assert any("update-service" in c for c in cli.calls) and not any("create-service" in c for c in cli.calls)


def test_deploy_cloudflare_deploys_then_sets_secrets(workspace, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")
    cli = FakeCLI()
    result = container_deploy.deploy_cloudflare(workspace, "ops", log=lambda m: None, run=cli)
    assert result["url"] == "https://ops.acme.workers.dev"
    order = [" ".join(c[:3]) for c in cli.calls]
    assert order.index("npx wrangler deploy") < order.index("npx wrangler secret")
    assert not (Path(result["folder"]) / ".secrets.json").exists()      # the secrets file is removed


def test_missing_tools_are_explained(workspace, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda tool: None)
    with pytest.raises(DeployError, match="AWS CLI"):
        container_deploy.deploy_aws(workspace, "ops")
    with pytest.raises(DeployError, match="Node.js"):
        container_deploy.deploy_cloudflare(workspace, "ops")


def test_local_mcn_source_is_copied_into_the_image(workspace, tmp_path, monkeypatch):
    from mcn.core_engine import vercel_deploy
    src = tmp_path / "mcn-checkout"
    (src / "mcn").mkdir(parents=True)
    (src / "setup.py").write_text("")
    (src / ".git").mkdir()
    monkeypatch.setattr(vercel_deploy, "SOURCE", str(src))
    out = container_deploy.stage(workspace, "ops", "aws")
    dockerfile = (out / "Dockerfile").read_text()
    assert 'RUN pip install --no-cache-dir "/tmp/mcn-src[postgres,sso]"' in dockerfile
    assert (out / "mcn-src" / "setup.py").exists() and not (out / "mcn-src" / ".git").exists()
