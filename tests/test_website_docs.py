"""
The website's docs stay true: pages.js matches the Markdown sources, every
page in the nav exists, internal links point at real pages, and every MCN
code sample passes `mcn check` (samples marked ```mcn fragment are partial).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from mcn.core_engine.diagnostics import check

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "website" / "docs" / "pages"
NAV = json.loads((PAGES / "_nav.json").read_text())
SLUGS = [slug for group in NAV for slug in group["pages"]]
SOURCES = [PAGES / f"{s}.md" for s in SLUGS if (PAGES / f"{s}.md").exists()]


def _blocks():
    for path in SOURCES:
        text = path.read_text()
        for m in re.finditer(r"```mcn( fragment)?\n(.*?)```", text, re.S):
            if not m.group(1):
                line = text[:m.start()].count("\n") + 1
                yield pytest.param(m.group(2), id=f"{path.relative_to(PAGES)}:{line}")


def test_pages_js_is_up_to_date():
    res = subprocess.run([sys.executable, str(ROOT / "website" / "build_docs.py"), "--check"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_every_nav_page_exists():
    missing = [s for s in SLUGS if s != "reference/builtins" and not (PAGES / f"{s}.md").exists()]
    assert not missing


def test_internal_links_resolve():
    broken = []
    for path in SOURCES + [ROOT / "website" / "index.html"]:
        for target in re.findall(r"#/([a-z0-9/-]+)", path.read_text()):
            if target not in SLUGS:
                broken.append(f"{path.name}: #/{target}")
    assert not broken


@pytest.mark.parametrize("source", list(_blocks()))
def test_docs_sample_passes_check(source):
    errors = [d for d in check(source) if d.severity == "error"]
    assert not errors, [f"{d.line}:{d.col} {d.message}" for d in errors]
