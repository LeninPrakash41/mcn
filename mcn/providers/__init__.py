"""
MCN AI Providers — pluggable backend adapters for AI primitives.

Provider selection order:
  1. MCN_AI_PROVIDER env var  ("anthropic" | "openai")
  2. Whichever API key is present (ANTHROPIC_API_KEY wins)
  3. Falls back to a deterministic mock (safe for dev / CI)

Imported by ai_builtins.py — do NOT import from evaluator or parser here.
"""
from .anthropic_provider import anthropic_complete
from .openai_provider    import openai_complete, openai_embed

__all__ = ["anthropic_complete", "openai_complete", "openai_embed"]
