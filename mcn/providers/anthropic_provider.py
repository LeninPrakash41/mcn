"""
Anthropic Claude provider for MCN AI primitives.

Uses the raw HTTP API via `requests` so no extra SDK dependency is needed.
Set ANTHROPIC_API_KEY in the environment to enable real calls.
Without it, every call returns a clearly-labelled mock string.
"""
import os
from typing import Optional

import requests

_API_URL = "https://api.anthropic.com/v1/messages"
_VERSION  = "2023-06-01"

# Default model — latest fast Sonnet.  Override via MCN_AI_MODEL or options.
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"


def anthropic_complete(
    prompt:      str,
    *,
    model:       str            = DEFAULT_MODEL,
    system:      str            = "",
    max_tokens:  int            = 1024,
    temperature: float          = 0.7,
) -> str:
    """
    Send a single-turn completion to Claude.

    Returns the assistant text or a bracketed error/mock string so callers
    never receive an exception from a provider call.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return f"[Claude Mock — set ANTHROPIC_API_KEY to enable] {prompt[:100]}..."

    payload: dict = {
        "model":       model or DEFAULT_MODEL,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "messages":    [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(
            _API_URL,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": _VERSION,
                "Content-Type":      "application/json",
            },
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"]

        # Surface the API error message if available
        try:
            err = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        return f"[Anthropic {resp.status_code}] {err}"

    except requests.exceptions.Timeout:
        return "[Anthropic Error] Request timed out (60 s)"
    except Exception as exc:
        return f"[Anthropic Error] {exc}"
