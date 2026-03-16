"""
MCN AI Built-ins — Layer 1 intelligent primitives.

These are registered as global built-in functions in MCNInterpreter, making
them available in every MCN script without any `use` statement:

    ai(prompt)                      → str
    ai(prompt, {model, temperature, max_tokens, system})  → str

    llm("claude-3-5-sonnet", prompt)                → str
    llm("gpt-4o", prompt, {temperature: 0.2})       → str

    embed(text)                     → list[float]

    extract(text, ContractVar)      → dict

    classify(text, ["a","b","c"])   → str   (the winning label)

    checkpoint("Review before publish", data)        → data (or edited value)

Provider selection:
  1. MCN_AI_PROVIDER env var  ("anthropic" | "openai")
  2. Whichever key is present: ANTHROPIC_API_KEY wins over OPENAI_API_KEY
  3. No key → deterministic mock (safe for dev / CI)
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional

# ── Agent-model context (set by MCNAgent when running a task) ─────────────────
# Lets ai() inside an agent task automatically inherit the agent's model.
_agent_context = threading.local()


def _get_provider(opts: dict) -> str:
    """Pick provider from options → env var → key presence → default."""
    if opts.get("provider"):
        return str(opts["provider"])
    explicit = os.getenv("MCN_AI_PROVIDER", "").lower()
    if explicit in ("anthropic", "openai"):
        return explicit
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"          # mock mode


def _provider_complete(prompt: str, opts: dict) -> str:
    """Dispatch a completion call to the right provider."""
    from ..providers.anthropic_provider import anthropic_complete
    from ..providers.openai_provider    import openai_complete

    provider = _get_provider(opts)
    model    = opts.get("model") or getattr(_agent_context, "model", None) or ""
    system   = opts.get("system", "")
    max_tok  = int(opts.get("max_tokens", 1024))
    temp     = float(opts.get("temperature", 0.7))

    if provider == "openai":
        return openai_complete(prompt, model=model or "gpt-4o",
                               system=system, max_tokens=max_tok,
                               temperature=temp)
    # default → anthropic
    return anthropic_complete(prompt, model=model or "claude-3-5-sonnet-20241022",
                              system=system, max_tokens=max_tok, temperature=temp)


# ── ai() ──────────────────────────────────────────────────────────────────────

def mcn_ai(prompt: str, options: Any = None) -> str:
    """
    Universal AI completion.

    ai("Write a haiku about rain")
    ai("Summarize: " + doc, {model: "claude-3-5-sonnet", temperature: 0.2})
    """
    if not isinstance(prompt, str):
        prompt = str(prompt)
    opts = options if isinstance(options, dict) else {}
    return _provider_complete(prompt, opts)


# ── llm() ─────────────────────────────────────────────────────────────────────

def mcn_llm(model: str, prompt: str, options: Any = None) -> str:
    """
    Explicit model + prompt call.

    llm("claude-3-5-sonnet", "Analyse this code: " + src)
    llm("gpt-4o", prompt, {temperature: 0.0, max_tokens: 256})
    """
    opts = dict(options) if isinstance(options, dict) else {}
    opts["model"] = str(model)
    # Route by model prefix
    if model.startswith("claude"):
        opts.setdefault("provider", "anthropic")
    elif model.startswith(("gpt", "o1", "o3", "o4")):
        opts.setdefault("provider", "openai")
    return _provider_complete(str(prompt), opts)


# ── embed() ───────────────────────────────────────────────────────────────────

def mcn_embed(text: str) -> List[float]:
    """
    Generate a text embedding (1536-dim via OpenAI text-embedding-3-small).
    Falls back to a 128-dim deterministic mock when OPENAI_API_KEY is absent.

    embed("cloud cost optimisation")
    var vec = embed(user_query)
    var results = query("SELECT * FROM docs ORDER BY dist(embedding, ?) LIMIT 5", vec)
    """
    from ..providers.openai_provider import openai_embed
    return openai_embed(str(text))


# ── extract() ─────────────────────────────────────────────────────────────────

def mcn_extract(text: str, contract: Any) -> Dict[str, Any]:
    """
    Structured extraction: parse free text into a validated dict.

    contract Invoice
        vendor:   str
        amount:   float
        due_date: str

    var inv = extract(raw_text, Invoice)
    # → {"vendor": "Acme", "amount": 1500.0, "due_date": "2026-04-01"}
    """
    # Build a field description from the contract
    fields_desc = ""
    if hasattr(contract, "fields") and contract.fields:
        fields_desc = ", ".join(
            f"{name} ({type_name})" for name, type_name in contract.fields
        )
    elif hasattr(contract, "schema"):
        schema = contract.schema()
        props  = schema.get("properties", {})
        fields_desc = ", ".join(
            f"{k} ({v.get('type', 'any')})" for k, v in props.items()
        )
    else:
        fields_desc = "all relevant fields"

    system = (
        "You are a precise structured-data extractor. "
        "Extract information from the given text and return ONLY valid JSON — "
        "no markdown, no explanation, no code fences."
    )
    prompt = (
        f"Extract these fields: {fields_desc}\n\n"
        f"Text:\n{text}\n\n"
        "Return a single JSON object."
    )

    raw = _provider_complete(prompt, {"system": system, "temperature": 0.0,
                                      "max_tokens": 1024})

    # Strip markdown fences if the model included them
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts   = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) > 1 else cleaned

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {"_raw": raw}

    # Validate against the contract if it supports it
    if hasattr(contract, "validate"):
        contract.validate(result)

    return result


# ── classify() ────────────────────────────────────────────────────────────────

def mcn_classify(text: str, labels: Any) -> str:
    """
    Zero-shot text classification.  Returns the single best label.

    var intent = classify(user_message, ["purchase", "return", "complaint"])
    """
    if not isinstance(labels, list) or not labels:
        raise TypeError("classify() expects a non-empty list as second argument")

    labels_str = ", ".join(f'"{l}"' for l in labels)
    system = (
        "You are a classifier. Given text and candidate labels, "
        "respond with ONLY the single most appropriate label — "
        "no punctuation, no explanation, no quotes."
    )
    prompt = f"Labels: [{labels_str}]\n\nText: {text}\n\nBest label:"

    result = _provider_complete(prompt, {"system": system, "temperature": 0.0,
                                         "max_tokens": 32})
    result = result.strip().strip('"').strip("'").strip()

    # Exact match first
    result_lower = result.lower()
    for label in labels:
        if label.lower() == result_lower:
            return label
    # Partial match fallback
    for label in labels:
        if label.lower() in result_lower or result_lower in label.lower():
            return label
    return result   # return as-is — LLM might return something creative


# ── checkpoint() ──────────────────────────────────────────────────────────────

def mcn_checkpoint(message: str, data: Any = None) -> Any:
    """
    Human-in-the-loop gate.  Pauses execution, displays `data`, and waits
    for human approval, rejection, or an in-place edit.

    workflow publish_article
        step draft(brief)
            return ai("Write a blog post: " + brief)
        step review(content)
            checkpoint("Review before publishing", content)
            return content
        step publish(content)
            trigger("https://cms.acme.com/posts", {body: content})
    """
    separator = "─" * 60

    print(f"\n{separator}")
    print(f"  ⏸  CHECKPOINT  — {message}")
    print(separator)

    if data is not None:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(str(data))
        print(separator)

    print("  [y] Approve and continue")
    print("  [n] Abort / reject")
    print("  [e] Edit value before continuing")
    print(separator)

    while True:
        try:
            choice = input("  Choice [y/n/e]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            raise RuntimeError(f"Checkpoint '{message}' aborted (no tty / Ctrl-C)")

        if choice in ("y", "yes", ""):
            print("  Approved.\n")
            return data

        if choice in ("n", "no"):
            raise RuntimeError(f"Checkpoint rejected by human: {message}")

        if choice in ("e", "edit"):
            print("  Enter replacement value (JSON object/array, or plain text):")
            try:
                raw = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                raise RuntimeError(f"Checkpoint '{message}' aborted during edit")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        print("  Please enter y, n, or e.")


# ── Registration helper ────────────────────────────────────────────────────────

def register_ai_builtins(functions: dict) -> None:
    """
    Called by MCNInterpreter._register_builtin_functions() to add every
    AI primitive to the shared function registry.
    """
    functions["ai"]         = mcn_ai
    functions["llm"]        = mcn_llm
    functions["embed"]      = mcn_embed
    functions["extract"]    = mcn_extract
    functions["classify"]   = mcn_classify
    functions["checkpoint"] = mcn_checkpoint
