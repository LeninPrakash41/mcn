"""The agent team's browser check: open Studio's live preview in a real (headless)
browser, visit every screen, and report what a person would see go wrong.

Needs Playwright (`mcn add browser-qa`). It uses the installed Google Chrome when
there is one, so no separate browser download is needed; otherwise Playwright's
own Chromium (`python -m playwright install chromium`).
"""
from __future__ import annotations

import base64
import contextlib
import io
from pathlib import Path
from typing import Any, Callable, Dict, List


def available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def nav_labels(app_dir: Path) -> List[str]:
    """The screens a person can open: the app's sidebar or tab labels, else the component names."""
    ui = app_dir / "ui" / "app.mcn"
    if not ui.exists():
        return []
    try:
        from mcn.core_engine.mcn_interpreter import MCNInterpreter
        interp = MCNInterpreter()
        with contextlib.redirect_stdout(io.StringIO()):
            interp.execute(ui.read_text(encoding="utf-8"), str(ui), quiet=True)
        ev = interp._evaluator
        layout = ev.app_decl.layout if ev.app_decl else None
        if layout and layout.sidebar:
            return [n.label for n in layout.sidebar]
        if layout and layout.tabs:
            return [t.label for t in layout.tabs]
        return list(ev.components)
    except Exception:
        return []


def make_check(preview_url: str, start_backend: Callable[[Path], Any]) -> Callable[[Path], Dict[str, Any]]:
    """A browser check bound to this Studio's preview page."""

    def check(app_dir: Path) -> Dict[str, Any]:
        if not available():
            return {"skipped": "Install the browser check with: mcn add browser-qa"}
        from playwright.sync_api import sync_playwright

        start_backend(app_dir)
        screens: List[Dict[str, Any]] = []
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="chrome", headless=True)
            except Exception:
                browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            console: List[str] = []
            failed: List[str] = []
            page.on("console", lambda m: m.type == "error" and console.append(m.text[:300]))
            page.on("pageerror", lambda e: console.append(f"Uncaught: {str(e)[:300]}"))
            page.on("response", lambda r: r.status >= 500 and failed.append(f"{r.status} {r.url}"))
            page.on("requestfailed", lambda r: failed.append(f"failed {r.url}"))

            page.goto(preview_url, wait_until="networkidle", timeout=45000)
            labels = nav_labels(app_dir) or ["Home"]
            for i, label in enumerate(labels[:8]):
                console.clear()
                failed.clear()
                if i or len(labels) > 1:
                    target = page.get_by_role("link", name=label, exact=True)
                    if not target.count():
                        target = page.get_by_role("button", name=label, exact=True)
                    if target.count():
                        target.first.click()
                with contextlib.suppress(Exception):
                    page.wait_for_load_state("networkidle", timeout=8000)
                page.wait_for_timeout(600)
                alerts = [t.strip()[:300] for t in page.locator("[role=alert]").all_inner_texts() if t.strip()]
                text = page.locator("main").inner_text(timeout=2000) if page.locator("main").count() else ""
                screens.append({
                    "name": label,
                    "console_errors": list(console),
                    "failed_requests": list(failed),
                    "on_screen_errors": alerts,
                    "looks_empty": len(text.strip()) < 20,
                    "png": base64.b64encode(page.screenshot(type="png")).decode(),
                })
            browser.close()
        return {"screens": screens}

    return check
