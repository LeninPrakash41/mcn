"""
Change an existing MCN app from a request, through the MCN agent interface.

    mcn change "Add a customer verification step before creating an order"

Claude never sees or rewrites whole files. It works only through the interface's
operations: inspect the app, find and explain what's relevant, build one patch out
of create / modify / remove operations, then validate and test it until both pass.
It can't write anything itself: the finished patch is shown to a person, with its
diff, what it affects and the test results, and only applied when they approve.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import anthropic

from mcn.core_engine.agent_interface import AGENT_TOOLS, Workspace, call_tool

from .mcn_agent import DEFAULT_MODEL, raise_if_refused
from .mcn_spec import MCN_SYSTEM_PROMPT

MAX_TURNS = 40
MAX_RESULT_CHARS = 24000

_INSTRUCTIONS = """You change an existing MCN app for a developer. You can only work through the MCN agent
interface's operations; you never rewrite whole files.

1. inspect the app first. Then find and explain the declarations the request touches.
2. Make the change as ONE patch: the first create/modify/remove returns a patch id; pass it to every
   later operation. modify replaces a declaration's complete code, so keep everything that shouldn't change.
3. Add or update a test block that checks the new behaviour.
4. validate the patch. Fix every parse error, type error and new issue it reports (with more operations
   on the same patch), and validate again.
5. test the patch. Fix failures and run it again.
6. Stop when validate says ok and the tests pass. Reply with a short plain-language summary of the change
   and the patch id on its own line as: PATCH <id>

If the request can't be done safely, say why instead of guessing. Applying the patch is not your job:
a person reviews and approves it."""

Emit = Callable[[Dict[str, Any]], None]


class ChangeAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, emit: Optional[Emit] = None,
                 client: Optional[anthropic.Anthropic] = None):
        self.client = client or anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.emit: Emit = emit or (lambda event: None)

    def run(self, request: str, app_dir: str) -> Dict[str, Any]:
        """Returns {"summary", "patch" (id or None), "operations": [...]}."""
        ws = Workspace(app_dir)
        messages: List[Dict[str, Any]] = [{"role": "user", "content": f"Request:\n{request.strip()}"}]
        system = MCN_SYSTEM_PROMPT + "\n\n" + _INSTRUCTIONS
        operations: List[Dict[str, Any]] = []
        patch_id: Optional[str] = None
        text = ""
        for _ in range(MAX_TURNS):
            message = self.client.messages.create(
                model=self.model, max_tokens=16000, system=system, tools=AGENT_TOOLS, messages=messages,
                thinking={"type": "adaptive"}, output_config={"effort": "high"})
            raise_if_refused(message)
            messages.append({"role": "assistant", "content": message.content})
            text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text").strip()
            uses = [b for b in message.content if getattr(b, "type", "") == "tool_use"]
            if message.stop_reason != "tool_use" or not uses:
                break
            results = []
            for use in uses:
                self.emit({"type": "operation", "name": use.name, "input": _brief(use.input)})
                result = call_tool(ws, use.name, dict(use.input or {}))
                if isinstance(result, dict) and result.get("patch") and use.name in ("create", "modify", "remove"):
                    patch_id = result["patch"]
                operations.append({"name": use.name, "input": _brief(use.input), "error": _error(result)})
                self.emit({"type": "result", "name": use.name, "error": _error(result),
                           "ok": result.get("ok") if isinstance(result, dict) else None})
                body = json.dumps(result, default=str)
                if len(body) > MAX_RESULT_CHARS:
                    body = body[:MAX_RESULT_CHARS] + '..." (cut short)'
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": body,
                                **({"is_error": True} if _error(result) else {})})
            messages.append({"role": "user", "content": results})
        for line in text.splitlines():
            if line.strip().startswith("PATCH "):
                patch_id = line.strip().split(None, 1)[1].strip() or patch_id
        summary = "\n".join(l for l in text.splitlines() if not l.strip().startswith("PATCH ")).strip()
        return {"summary": summary, "patch": patch_id, "operations": operations}


def _brief(args: Any) -> Dict[str, Any]:
    out = {}
    for k, v in dict(args or {}).items():
        out[k] = (v[:80] + "…") if isinstance(v, str) and len(v) > 80 else v
    return out


def _error(result: Any) -> Optional[str]:
    return result.get("error") if isinstance(result, dict) else None
