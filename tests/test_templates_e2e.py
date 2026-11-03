"""
End-to-end checks for every playground template.

Always run (fast, Python only):
  * every single-file template executes successfully
  * every template .mcn file parses with no (silently recovered) syntax errors
  * every project template builds for React and for Flutter

Opt-in (need Node.js / Flutter; enabled in CI jobs):
  MCN_E2E_REACT=1    type-check each generated React app with `tsc --noEmit`
  MCN_E2E_FLUTTER=1  run `flutter analyze` on each generated Flutter app
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from playground_app import load, quiet
from mcn.core_engine.lexer import Lexer
from mcn.core_engine.parser import Parser

pg, client = load()

TEMPLATES = client.get("/api/examples").get_json()
SCRIPTS = [t for t in TEMPLATES if "code" in t]
PROJECTS = [t for t in TEMPLATES if "files" in t]
MCN_FILES = [(t["id"], t["code"]) for t in SCRIPTS] + [
    (f'{t["id"]}:{f["path"]}', f["content"]) for t in PROJECTS for f in t["files"] if f["path"].endswith(".mcn")
]


def _build(project, platform):
    quiet(client.post, "/api/workspace/reset", json={"files": project["files"]})
    return quiet(client.post, "/api/build", json={"platform": platform}).get_json()


@pytest.mark.parametrize("template", SCRIPTS, ids=[t["id"] for t in SCRIPTS])
def test_script_template_runs(template):
    res = quiet(client.post, "/api/execute", json={"code": template["code"]}).get_json()
    assert res.get("success") is True, res.get("error")


@pytest.mark.parametrize("name, source", MCN_FILES, ids=[n for n, _ in MCN_FILES])
def test_template_parses_cleanly(name, source):
    parser = Parser(Lexer(source).tokenize())
    parser.parse()
    assert parser.errors == [], f"{name}: {parser.errors[0]}"


@pytest.mark.parametrize("platform", ["react", "flutter"])
@pytest.mark.parametrize("project", PROJECTS, ids=[t["id"] for t in PROJECTS])
def test_project_builds(project, platform):
    res = _build(project, platform)
    assert res.get("success") is True, res.get("error")


# ── Opt-in compile checks ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def shared_node_modules(tmp_path_factory):
    """Install the generated app's dependencies once; every project reuses them."""
    if not shutil.which("npm"):
        pytest.skip("npm not installed")
    _build(PROJECTS[0], "react")
    base = tmp_path_factory.mktemp("node")
    shutil.copy(Path(pg.app.config["WORKSPACE"]) / "frontend" / "package.json", base / "package.json")
    subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
                   cwd=base, check=True, capture_output=True, text=True)
    return base / "node_modules"


@pytest.mark.skipif(not os.getenv("MCN_E2E_REACT"), reason="set MCN_E2E_REACT=1 (needs Node.js)")
@pytest.mark.parametrize("project", PROJECTS, ids=[t["id"] for t in PROJECTS])
def test_react_app_typechecks(project, shared_node_modules):
    assert _build(project, "react").get("success") is True
    frontend = Path(pg.app.config["WORKSPACE"]) / "frontend"
    (frontend / "node_modules").symlink_to(shared_node_modules, target_is_directory=True)
    proc = subprocess.run(["npx", "tsc", "--noEmit", "-p", "."], cwd=frontend,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-3000:]


@pytest.mark.skipif(not os.getenv("MCN_E2E_FLUTTER"), reason="set MCN_E2E_FLUTTER=1 (needs Flutter)")
@pytest.mark.parametrize("project", PROJECTS, ids=[t["id"] for t in PROJECTS])
def test_flutter_app_analyzes(project):
    if not shutil.which("flutter"):
        pytest.skip("flutter not installed")
    assert _build(project, "flutter").get("success") is True
    app_dir = next(p for p in (Path(pg.app.config["WORKSPACE"]) / "mobile", Path(pg.app.config["WORKSPACE"]) / "flutter") if (p / "pubspec.yaml").exists())
    subprocess.run(["flutter", "pub", "get"], cwd=app_dir, check=True, capture_output=True, text=True)
    proc = subprocess.run(["flutter", "analyze", "--no-fatal-infos", "--no-fatal-warnings", "lib"],
                          cwd=app_dir, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-3000:]


# ── IDE page: every stylesheet and script it references is served ────────────

def test_ide_assets_served():
    html = client.get("/").get_data(as_text=True)
    assets = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert len(assets) >= 10, assets
    for path in assets:
        assert client.get(path).status_code == 200, path


# ── Example programs in the repo parse (examples/legacy is the old brace syntax) ─

REPO_EXAMPLES = sorted(
    p for pattern in ("examples/**/*.mcn", "use-cases/**/*.mcn")
    for p in Path(pg.__file__).resolve().parents[2].glob(pattern) if "legacy" not in p.parts
)


@pytest.mark.parametrize("path", REPO_EXAMPLES, ids=[p.name for p in REPO_EXAMPLES])
def test_repo_example_parses(path):
    parser = Parser(Lexer(path.read_text(encoding="utf-8")).tokenize())
    parser.parse()
    assert parser.errors == [], parser.errors[0]
