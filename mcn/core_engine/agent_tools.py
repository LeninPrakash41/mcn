"""
agent_run(): an AI agent that calls MCN functions as tools.

    var result = agent_run("Find overdue invoices and remind the owners", {
        system: "You are a finance assistant.",
        tools: [
            {name: "find_invoices", description: "List invoices by status"},
            {name: "send_reminder", description: "Email a reminder to an invoice owner"}
        ]
    })
    log(result.reply)
    log(result.tool_calls)      // [{name, input, output, error}]

Each tool is an MCN function (or built-in). Claude decides which to call and
with which arguments; MCN runs the function and sends the result back, until
Claude has an answer. Without ANTHROPIC_API_KEY a labelled mock plans the
calls with simple keyword matching, so the flow still runs in class and CI.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_MODEL = os.getenv("MCN_AI_MODEL", "claude-opus-5-5")
MAX_RESULT_CHARS = 20_000          # tool output sent back to the model
_IDENT = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ToolSpec:
    def __init__(self, name: str, description: str, fn: Callable, params: List[str], required: List[str]):
        self.name, self.description, self.fn = name, description, fn
        self.params, self.required = params, required

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description or f"Runs the MCN function {self.name}().",
            "input_schema": {
                "type": "object",
                "properties": {p: {"description": f"Value for {p}"} for p in self.params},
                "required": self.required,
            },
        }

    def call(self, args: Dict[str, Any]) -> Any:
        unknown = set(args) - set(self.params)
        if unknown:
            raise ValueError(f"{self.name}() has no parameter named {', '.join(sorted(unknown))}")
        missing = [p for p in self.required if p not in args]
        if missing:
            raise ValueError(f"{self.name}() is missing {', '.join(missing)}")
        return self.fn(*[args[p] for p in self.params if p in args])


def resolve_tools(tools: Any, functions: Dict[str, Callable]) -> List[ToolSpec]:
    """Turn ["search_docs", {name, description}] into ToolSpecs bound to MCN functions."""
    specs: List[ToolSpec] = []
    for item in tools or []:
        if isinstance(item, str):
            name, description = item, ""
        elif isinstance(item, dict) and item.get("name"):
            name, description = str(item["name"]), str(item.get("description") or "")
        else:
            raise ValueError("each tool must be a function name or {name, description}")
        if not _IDENT.match(name):
            raise ValueError(f"'{name}' isn't a valid tool name")
        fn = functions.get(name)
        if not callable(fn):
            raise ValueError(f"tool '{name}' isn't a function in this program")
        params = list(getattr(fn, "mcn_params", None) or _python_params(fn))
        required = list(getattr(fn, "mcn_required", None) or _python_required(fn))
        specs.append(ToolSpec(name, description, fn, params, required))
    return specs


def _python_params(fn: Callable) -> List[str]:
    import inspect
    try:
        return [p.name for p in inspect.signature(fn).parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    except (TypeError, ValueError):
        return []


def _python_required(fn: Callable) -> List[str]:
    import inspect
    try:
        return [p.name for p in inspect.signature(fn).parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
    except (TypeError, ValueError):
        return []


def _as_text(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + " …(truncated)"


def _run_tool(spec: ToolSpec, args: Dict[str, Any], log: List[dict]) -> Tuple[str, bool]:
    started = time.time()
    entry: Dict[str, Any] = {"name": spec.name, "input": args}
    try:
        output = spec.call(args)
        entry["output"] = output
        return _as_text(output), False
    except Exception as exc:                       # the model sees the error and can recover
        message = getattr(exc, "message", None) or str(exc)
        entry["error"] = message
        return f"Error: {message}", True
    finally:
        entry["ms"] = int((time.time() - started) * 1000)
        log.append(entry)


def _history_messages(history: Any) -> List[dict]:
    out: List[dict] = []
    for m in history or []:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            out.append({"role": m["role"], "content": str(m["content"])})
    while out and out[0]["role"] != "user":        # the API requires a user turn first
        out.pop(0)
    return out


def _mock_run(prompt: str, specs: List[ToolSpec]) -> dict:
    """No API key: call the tools whose name words appear in the prompt."""
    log: List[dict] = []
    words = set(re.findall(r"[a-z]+", prompt.lower()))
    for spec in specs:
        parts = [w for w in spec.name.lower().split("_") if len(w) > 2]
        if parts and any(w in words or w.rstrip("s") in words for w in parts):
            args = {p: prompt for p in spec.required[:1]}   # first required parameter gets the request
            _run_tool(spec, args, log)
    used = ", ".join(c["name"] for c in log) or "no tools"
    return {
        "reply": f"[Claude Mock — set ANTHROPIC_API_KEY to enable] Used {used} for: {prompt[:120]}",
        "tool_calls": log, "steps": 1, "mock": True,
    }


def run_agent(prompt: Any, options: Any, functions: Dict[str, Callable]) -> dict:
    """The agent loop. Returns {reply, tool_calls, steps} and never raises for model errors."""
    from . import ai_trace

    opts = options if isinstance(options, dict) else {}
    prompt = str(prompt)
    specs = resolve_tools(opts.get("tools"), functions)
    max_steps = max(1, min(int(opts.get("max_steps") or 8), 25))
    started = time.time()

    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        result = _mock_run(prompt, specs)
        ai_trace.record("agent", prompt, result["reply"], model="mock", provider="anthropic", started=started)
        return result

    import anthropic
    client = anthropic.Anthropic()
    model = str(opts.get("model") or DEFAULT_MODEL)
    system = str(opts.get("system") or "")
    by_name = {s.name: s for s in specs}
    messages: List[dict] = [*_history_messages(opts.get("history")), {"role": "user", "content": prompt}]
    log: List[dict] = []
    request: Dict[str, Any] = {"model": model, "max_tokens": 16000, "messages": messages}
    if system:
        request["system"] = system
    if specs:
        request["tools"] = [s.schema() for s in specs]
    if opts.get("effort"):
        request["output_config"] = {"effort": str(opts["effort"])}

    reply, steps = "", 0
    try:
        while steps < max_steps:
            steps += 1
            response = client.messages.create(**request)
            # Keep the full content (thinking and tool_use blocks) in the history
            messages.append({"role": "assistant", "content": response.content})
            text = "".join(b.text for b in response.content if b.type == "text")
            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                reply = f"[Claude declined] {getattr(details, 'explanation', None) or 'request declined'}"
                break
            if response.stop_reason == "pause_turn":
                continue                           # resend so the model can finish its turn
            if response.stop_reason != "tool_use":
                reply = text
                break
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                spec = by_name.get(block.name)
                args = block.input if isinstance(block.input, dict) else {}
                if spec is None:
                    content, is_error = f"Error: there's no tool named {block.name}", True
                else:
                    content, is_error = _run_tool(spec, args, log)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
            # Every result for this turn goes back in one message
            messages.append({"role": "user", "content": results})
        else:
            reply = reply or f"[Stopped after {max_steps} steps without a final answer]"
    except anthropic.RateLimitError:
        reply = "[Anthropic rate limit] Try again in a moment."
    except anthropic.AuthenticationError:
        reply = "[Anthropic] The API key was rejected."
    except anthropic.APIStatusError as exc:
        reply = f"[Anthropic {exc.status_code}] {exc.message}"
    except anthropic.APIConnectionError:
        reply = "[Anthropic] Couldn't reach the API. Check your connection."

    ai_trace.record("agent", prompt, reply, model=model, provider="anthropic", started=started)
    return {"reply": reply, "tool_calls": log, "steps": steps}
