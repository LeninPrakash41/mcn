"""Every MCN sample in README.md passes `mcn check`, so the front page never shows broken code."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.diagnostics import check  # noqa: E402

SAMPLES = [(ROOT / "README.md").read_text(encoding="utf-8")[:m.start()].count("\n") + 1
           for m in re.finditer(r"```mcn\n", (ROOT / "README.md").read_text(encoding="utf-8"))]
CODE = re.findall(r"```mcn\n(.*?)```", (ROOT / "README.md").read_text(encoding="utf-8"), re.S)


@pytest.mark.parametrize("line, code", list(zip(SAMPLES, CODE)), ids=[f"line {n}" for n in SAMPLES])
def test_readme_sample_passes_check(line, code):
    problems = [d for d in check(code) if d.severity == "error"]
    assert not problems, f"README line {line}: {problems[0].message}"
