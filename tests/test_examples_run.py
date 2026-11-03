"""
Every script in examples/ and use-cases/ must run — twice, in a fresh
directory — and pass `mcn check`. These are the first files a developer opens.

AI calls use mock mode (no API key) and HTTP calls to placeholder hosts fail
fast (MCN_HTTP_TIMEOUT), so no network access is needed for a pass.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted(
    p for d in ("examples", "use-cases") for p in (ROOT / d).glob("*.mcn")
)
IDS = [str(p.relative_to(ROOT)) for p in SCRIPTS]


def _mcn(*args, cwd):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "MCN_HTTP_TIMEOUT": "3"}
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-m", "mcn.core_engine.mcn_cli", *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def workdir(tmp_path):
    # Scripts read sample data by repo-relative paths (examples/sample_ml_data.csv)
    for d in ("examples", "use-cases"):
        (tmp_path / d).symlink_to(ROOT / d)
    return tmp_path


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_example_runs_twice(script, workdir):
    for attempt in ("first", "second"):
        res = _mcn("run", str(script), cwd=workdir)
        assert res.returncode == 0, f"{attempt} run failed:\n{res.stderr[-2000:]}"


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_example_passes_check(script, workdir):
    res = _mcn("check", "--json", str(script), cwd=workdir)
    errors = [d for d in json.loads(res.stdout)["diagnostics"] if d["severity"] == "error"]
    assert not errors, errors
