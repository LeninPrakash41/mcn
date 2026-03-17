"""
Ollama provider for MCN AI primitives.

Calls a locally-running Ollama instance (https://ollama.ai/).

Configuration:
  OLLAMA_URL   — base URL (default: http://localhost:11434)
  OLLAMA_MODEL — default model (default: llama3)

Usage in MCN:
  use "ollama"
  var reply = ai("Explain quantum computing", {provider: "ollama", model: "llama3"})
  var reply = llm("mistral", "What is 2+2?")
"""
import hashlib
import os
from typing import List

import requests

_DEFAULT_BASE  = "http://localhost:11434"
_DEFAULT_MODEL = "llama3"


def _base_url() -> str:
    return os.getenv("OLLAMA_URL", _DEFAULT_BASE).rstrip("/")


def _default_model() -> str:
    return os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)


def ollama_complete(
    prompt:      str,
    *,
    model:       str   = "",
    system:      str   = "",
    max_tokens:  int   = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Generate a chat completion via Ollama's /api/chat endpoint.
    Falls back to a mock response if Ollama is not reachable.
    """
    model = model or _default_model()
    base  = _base_url()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{base}/api/chat",
            json={
                "model":   model,
                "messages": messages,
                "stream":  False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            # /api/chat returns {"message": {"role": "assistant", "content": "..."}}
            return data.get("message", {}).get("content", "").strip()

        try:
            err = resp.json().get("error", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        return f"[Ollama {resp.status_code}] {err}"

    except requests.exceptions.ConnectionError:
        return (
            f"[Ollama Mock — Ollama not running at {base}] "
            f"Start with: ollama serve  |  model: {model}  |  "
            f"prompt: {prompt[:80]}..."
        )
    except requests.exceptions.Timeout:
        return f"[Ollama Error] Request timed out (120 s) — model: {model}"
    except Exception as exc:
        return f"[Ollama Error] {exc}"


def ollama_embed(text: str, model: str = "nomic-embed-text") -> List[float]:
    """
    Generate a text embedding via Ollama's /api/embeddings endpoint.
    Falls back to a deterministic 128-dim mock if Ollama is not reachable.
    """
    base = _base_url()

    try:
        resp = requests.post(
            f"{base}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding", [])

        raise RuntimeError(f"Ollama embed {resp.status_code}: {resp.text[:200]}")

    except requests.exceptions.ConnectionError:
        # Deterministic mock: stable across runs for the same input
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(h >> i & 0xFF) / 255.0 for i in range(128)]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"embed() failed via Ollama: {exc}") from exc
