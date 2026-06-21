"""
OpenAI provider for MCN AI primitives.

Used as secondary provider and for embed() (Anthropic has no embeddings API).
Set OPENAI_API_KEY to enable real calls.
"""
import hashlib
import os
from typing import List

import requests

_CHAT_URL  = "https://api.openai.com/v1/chat/completions"
_EMBED_URL = "https://api.openai.com/v1/embeddings"

DEFAULT_CHAT_MODEL  = "gpt-4o"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"


def openai_complete(
    prompt:      str,
    *,
    model:       str   = DEFAULT_CHAT_MODEL,
    system:      str   = "",
    max_tokens:  int   = 1024,
    temperature: float = 0.7,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return f"[OpenAI Mock — set OPENAI_API_KEY to enable] {prompt[:100]}..."

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            _CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       model or DEFAULT_CHAT_MODEL,
                "messages":    messages,
                "max_tokens":  max_tokens,
                "temperature": temperature,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()

        try:
            err = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        return f"[OpenAI {resp.status_code}] {err}"

    except requests.exceptions.Timeout:
        return "[OpenAI Error] Request timed out (60 s)"
    except Exception as exc:
        return f"[OpenAI Error] {exc}"


def openai_embed(text: str, model: str = DEFAULT_EMBED_MODEL) -> List[float]:
    """
    Generate a text embedding via OpenAI.
    Falls back to a deterministic 128-dim mock if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        # Deterministic mock: stable across runs for the same input
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(h >> i & 0xFF) / 255.0 for i in range(128)]

    try:
        resp = requests.post(
            _EMBED_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={"model": model, "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]

        raise RuntimeError(f"OpenAI embed {resp.status_code}: {resp.text[:200]}")

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"embed() failed: {exc}") from exc
