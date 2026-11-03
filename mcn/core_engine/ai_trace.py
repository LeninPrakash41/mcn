"""
Records recent AI and RAG operations so tools (the playground's AI & RAG
inspector) can show what a script actually sent and received.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any, Dict, List

_MAX_ENTRIES = 200
_MAX_TEXT = 4000          # keep the trace small; long prompts are truncated

_lock = threading.Lock()
_entries: deque = deque(maxlen=_MAX_ENTRIES)


def _clip(value: Any) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + f"… [{len(text) - _MAX_TEXT} more chars]"


def record(kind: str, prompt: Any, response: Any, *, model: str = "", provider: str = "",
           started: float | None = None, **extra: Any) -> None:
    """Add one operation (ai, llm, extract, classify, embed, vector_search, rag)."""
    now = time.time()
    entry: Dict[str, Any] = {
        "type": kind,
        "timestamp": now,
        "prompt": _clip(prompt),
        "response": _clip(response),
        "model": model,
        "provider": provider,
    }
    if started is not None:
        entry["duration_ms"] = round((now - started) * 1000, 1)
    entry.update(extra)
    with _lock:
        _entries.append(entry)


def recent() -> List[Dict[str, Any]]:
    """Oldest first."""
    with _lock:
        return list(_entries)


def clear() -> None:
    with _lock:
        _entries.clear()


def active_model_label() -> str:
    """Human-readable description of the model ai() calls will use right now."""
    from ..providers.anthropic_provider import DEFAULT_MODEL
    from .ai_builtins import _get_provider

    provider = _get_provider({})
    if provider == "openai":
        return "openai: gpt-4o"
    if provider == "ollama":
        return f"ollama: {os.getenv('OLLAMA_MODEL', 'default')}"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return f"anthropic: {DEFAULT_MODEL} (mock mode: set ANTHROPIC_API_KEY for real responses)"
    return f"anthropic: {DEFAULT_MODEL}"
