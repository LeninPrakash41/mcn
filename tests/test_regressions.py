"""
Regression tests for launch-blocking bugs: generated Dart escaping, the Claude
provider behind ai(), and clean CLI output. Runs offline (no API key needed).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.fullstack.flutter_generator import FlutterProjectGenerator  # noqa: E402
import mcn.providers.anthropic_provider as anthropic_provider  # noqa: E402


# ── Flutter generator: user text must not break Dart string literals ─────────

@pytest.mark.parametrize("raw, escaped", [
    ("Pay $5", "Pay \\$5"),
    ('Say "hi"', 'Say \\"hi\\"'),
    ("back\\slash", "back\\\\slash"),
    ("two\nlines", "two\\nlines"),
])
def test_dart_escape(raw, escaped):
    assert FlutterProjectGenerator._dart_escape(raw) == escaped


def test_generated_button_escapes_dollar():
    dart = FlutterProjectGenerator()._component_to_dart({"type": "button", "props": {"text": "Buy $9"}})
    assert 'text: "Buy \\$9"' in dart


# ── Claude provider used by ai()/llm() ───────────────────────────────────────

def _fake_response(payload):
    return SimpleNamespace(status_code=200, json=lambda: payload)


def test_provider_uses_current_model_and_skips_thinking(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(json)
        return _fake_response({
            "stop_reason": "end_turn",
            "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Hello!"}],
        })

    with mock.patch.object(anthropic_provider.requests, "post", fake_post):
        out = anthropic_provider.anthropic_complete("hi", model=None, max_tokens=1024, temperature=0.3)

    assert out == "Hello!"
    assert sent["model"] == anthropic_provider.DEFAULT_MODEL
    assert "temperature" not in sent  # current Claude models reject sampling params
    assert sent["max_tokens"] >= 4096  # room for thinking plus the answer


def test_provider_reports_refusal(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    refusal = {"stop_reason": "refusal", "stop_details": {"explanation": "policy"}, "content": []}
    with mock.patch.object(anthropic_provider.requests, "post", lambda *a, **k: _fake_response(refusal)):
        assert anthropic_provider.anthropic_complete("x").startswith("[Claude declined]")


def test_provider_mock_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert anthropic_provider.anthropic_complete("hello").startswith("[Claude Mock")


# ── CLI: program output only, no duplicated engine logs ──────────────────────

def test_cli_hello_output_is_clean():
    proc = subprocess.run(
        [sys.executable, "-m", "mcn.core_engine.mcn_cli", "run", "examples/hello.mcn"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr
    lines = [l for l in (proc.stdout + proc.stderr).splitlines() if l.strip()]
    assert lines == ["Output Hello World!", "Adult"]
