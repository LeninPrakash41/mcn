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
from typing import Any, Callable, Dict, List, Optional

from mcn.core_engine.agent_interface import AGENT_TOOLS, Workspace, call_tool

from .llm import DEFAULT_CLAUDE_MODEL, AnthropicProvider, Provider, get_provider
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

_ASK_INSTRUCTIONS = """You answer a developer's questions about their MCN app. Use the read-only operations
(inspect, find, explain) to look at the real code before answering; never guess. Answer in plain language,
briefly, naming the screens, endpoints and tables involved (with file:line where it helps). You can't change
anything; if they ask for a change, say what you'd change and suggest Change mode."""

READ_ONLY_TOOLS = ("inspect", "semantic_graph", "find", "explain")

Emit = Callable[[Dict[str, Any]], None]


class ChangeAgent:
    """Works with any model that can call tools (see mcn.ai.llm)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, emit: Optional[Emit] = None,
                 client: Any = None, provider: Any = None, base_url: Optional[str] = None):
        if isinstance(provider, Provider):
            self.llm = provider
        elif client is not None:                     # an Anthropic client (tests pass a fake one)
            self.llm = AnthropicProvider(model or DEFAULT_CLAUDE_MODEL, client=client)
        else:
            self.llm = get_provider(provider, model, api_key, base_url)
        self.emit: Emit = emit or (lambda event: None)

    def ask(self, question: str, app_dir: str) -> Dict[str, Any]:
        """Answer a question about the app with the read-only operations. Returns {"summary", "operations"}."""
        return self.run(question, app_dir, mode="ask")

    def run(self, request: str, app_dir: str, mode: str = "change") -> Dict[str, Any]:
        """Returns {"summary", "patch" (id or None), "operations": [...]}."""
        ws = Workspace(app_dir)
        asking = mode == "ask"
        tools = [t for t in AGENT_TOOLS if t["name"] in READ_ONLY_TOOLS] if asking else AGENT_TOOLS
        messages: List[Dict[str, Any]] = [{"role": "user", "content": (
            f"Question:\n{request.strip()}" if asking else f"Request:\n{request.strip()}")}]
        system = MCN_SYSTEM_PROMPT + "\n\n" + (_ASK_INSTRUCTIONS if asking else _INSTRUCTIONS)
        operations: List[Dict[str, Any]] = []
        patch_id: Optional[str] = None
        text = ""
        for _ in range(MAX_TURNS):
            reply = self.llm.complete(system, messages, tools=tools, max_tokens=16000, effort="high")
            messages.append({"role": "assistant", "reply": reply})
            text = reply.text
            uses = reply.tool_calls
            if reply.stop != "tool_use" or not uses:
                break
            results = []
            for use in uses:
                self.emit({"type": "operation", "name": use.name, "input": _brief(use.input)})
                if asking and use.name not in READ_ONLY_TOOLS:
                    result: Any = {"error": f"'{use.name}' isn't available when answering questions"}
                else:
                    result = call_tool(ws, use.name, dict(use.input or {}))
                if isinstance(result, dict) and result.get("patch") and use.name in ("create", "modify", "remove"):
                    patch_id = result["patch"]
                operations.append({"name": use.name, "input": _brief(use.input), "error": _error(result)})
                self.emit({"type": "result", "name": use.name, "error": _error(result),
                           "ok": result.get("ok") if isinstance(result, dict) else None})
                body = json.dumps(result, default=str)
                if len(body) > MAX_RESULT_CHARS:
                    body = body[:MAX_RESULT_CHARS] + '..." (cut short)'
                results.append({"id": use.id, "content": body, "is_error": bool(_error(result))})
            messages.append({"role": "tool_results", "results": results})
        for line in text.splitlines():
            if line.strip().startswith("PATCH "):
                patch_id = line.strip().split(None, 1)[1].strip() or patch_id
        if asking:
            patch_id = None
        summary = "\n".join(l for l in text.splitlines() if not l.strip().startswith("PATCH ")).strip()
        return {"summary": summary, "patch": patch_id, "operations": operations}


def _brief(args: Any) -> Dict[str, Any]:
    out = {}
    for k, v in dict(args or {}).items():
        out[k] = (v[:80] + "…") if isinstance(v, str) and len(v) > 80 else v
    return out


def _error(result: Any) -> Optional[str]:
    return result.get("error") if isinstance(result, dict) else None
