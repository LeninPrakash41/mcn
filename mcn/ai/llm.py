"""
The model behind MCN's own agents (the change agent, the agent team, the app
generator), with nothing tied to one company's model.

Any model with tool calling works:

    anthropic    Claude, through the Anthropic SDK
    openai       OpenAI
    gemini       Google Gemini (its OpenAI-compatible endpoint)
    openrouter   any model on OpenRouter
    ollama       a local model in Ollama
    compatible   any other OpenAI-compatible server (vLLM, LM Studio, Together, Groq...):
                 set the base URL

Choosing one, first match wins:

    1. what the caller passes (--provider / --model / --api-key / --base-url)
    2. ~/.mcn/config.json: ai_provider, ai_model, ai_base_url, and the key
       (api_key for Claude; openai_api_key, gemini_api_key, openrouter_api_key, ai_api_key)
    3. MCN_AGENT_PROVIDER, MCN_AGENT_MODEL, MCN_AGENT_BASE_URL
    4. whichever key is set: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY (or
       GOOGLE_API_KEY), OPENROUTER_API_KEY, or OLLAMA_URL

Conversations use one neutral format, converted for each API:

    {"role": "user", "content": "text" | [parts]}       parts: {"type": "text", "text"},
                                                               {"type": "image", "media_type", "data"},
                                                               {"type": "pdf", "name", "data"}  (base64)
    {"role": "assistant", "reply": Reply}               a reply, as the model gave it
    {"role": "tool_results", "results": [{"id", "content", "is_error"}]}

Tools are JSON Schema: {"name", "description", "input_schema"}.
"""
from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    import anthropic
except ImportError:                     # only needed for Claude
    anthropic = None

DEFAULT_CLAUDE_MODEL = os.getenv("MCN_CLAUDE_MODEL", "claude-opus-5-5")

PRESETS: Dict[str, Dict[str, Any]] = {
    "openai":     {"base_url": "https://api.openai.com/v1", "keys": ["OPENAI_API_KEY"], "config_key": "openai_api_key",
                   "model": "gpt-4o"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"], "config_key": "gemini_api_key", "model": "gemini-2.5-pro"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "keys": ["OPENROUTER_API_KEY"],
                   "config_key": "openrouter_api_key", "model": None},
    "ollama":     {"base_url": None, "keys": [], "config_key": None, "model": None},
    "compatible": {"base_url": None, "keys": ["MCN_AGENT_API_KEY"], "config_key": "ai_api_key", "model": None},
}
PROVIDERS = ("anthropic",) + tuple(PRESETS)


class ModelError(RuntimeError):
    """The model can't be used as configured, or refused, or the API failed."""


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class Reply:
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop: str = "end"                    # end | tool_use | pause | max_tokens
    raw: Any = None                      # the provider's own message, for the next turn


# ── Choosing a provider ──────────────────────────────────────────────────────

def _config() -> Dict[str, Any]:
    try:
        return json.loads((Path.home() / ".mcn" / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guess_from_key(key: str) -> str:
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("sk-or-"):
        return "openrouter"
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-"):
        return "openai"
    return "anthropic"


def get_provider(provider: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None,
                 base_url: Optional[str] = None) -> "Provider":
    cfg = _config()
    name = (provider or cfg.get("ai_provider") or os.getenv("MCN_AGENT_PROVIDER") or "").strip().lower()
    model = model or cfg.get("ai_model") or os.getenv("MCN_AGENT_MODEL") or None
    base_url = base_url or cfg.get("ai_base_url") or os.getenv("MCN_AGENT_BASE_URL") or None
    if not name:
        if api_key:
            name = _guess_from_key(api_key)
        elif cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY"):
            name = "anthropic"
        elif base_url:
            name = "compatible"
        else:
            name = next((n for n, p in PRESETS.items() if p["keys"] and n != "compatible"
                         and (any(os.getenv(k) for k in p["keys"]) or cfg.get(p["config_key"]))), "")
            if not name and os.getenv("OLLAMA_URL"):
                name = "ollama"
    if not name:
        raise ModelError("No AI model is set up. Set an API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY or "
                         "OPENROUTER_API_KEY), run a local model with Ollama (set OLLAMA_URL), or run: "
                         "mcn config set ai_provider <name>")
    if name not in PROVIDERS:
        raise ModelError(f"Unknown AI provider '{name}'. Use one of: {', '.join(PROVIDERS)}")
    if name == "anthropic":
        key = api_key or cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ModelError("No Claude API key. Set ANTHROPIC_API_KEY or run: mcn config set api_key sk-ant-...")
        return AnthropicProvider(model or DEFAULT_CLAUDE_MODEL, api_key=key)
    preset = PRESETS[name]
    key = api_key or (cfg.get(preset["config_key"]) if preset["config_key"] else None) \
        or next((os.getenv(k) for k in preset["keys"] if os.getenv(k)), None)
    if name == "ollama":
        url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = model or os.getenv("OLLAMA_MODEL")
    else:
        url = base_url or preset["base_url"]
    if not url:
        raise ModelError("Set the server's address: mcn config set ai_base_url https://.../v1")
    if not key and name not in ("ollama", "compatible"):
        raise ModelError(f"No API key for {name}. Set {' or '.join(preset['keys'])}, "
                         f"or run: mcn config set {preset['config_key']} <key>")
    model = model or preset["model"]
    if not model:
        raise ModelError(f"Say which {name} model to use: mcn config set ai_model <model name>")
    if name == "ollama":
        return OllamaProvider(model, url)
    return OpenAICompatibleProvider(name, model, url, key)


def describe(provider: "Provider") -> str:
    return f"{provider.model} ({provider.name})"


# ── Providers ────────────────────────────────────────────────────────────────

class Provider:
    name = "provider"
    supports_web_search = False
    supports_pdf = False

    def __init__(self, model: str):
        self.model = model

    def complete(self, system: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
                 max_tokens: int = 16000, effort: str = "medium", on_text: Optional[Callable[[str], None]] = None,
                 web_search: int = 0) -> Reply:
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"
    supports_web_search = True
    supports_pdf = True

    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL, api_key: Optional[str] = None, client: Any = None):
        super().__init__(model)
        if client is None:
            if anthropic is None:
                raise ModelError("The Anthropic package is missing; reinstall MCN to use Claude")
            client = anthropic.Anthropic(api_key=api_key)
        self.client = client

    @staticmethod
    def _part(p: Any) -> Dict[str, Any]:
        if isinstance(p, str):
            return {"type": "text", "text": p}
        kind = p.get("type")
        if kind == "image":
            return {"type": "image", "source": {"type": "base64", "media_type": p["media_type"], "data": p["data"]}}
        if kind == "pdf":
            return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": p["data"]}}
        return {"type": "text", "text": p.get("text", "")}

    def _messages(self, messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                c = m["content"]
                out.append({"role": "user", "content": c if isinstance(c, str) else [self._part(p) for p in c]})
            elif m["role"] == "assistant":
                out.append({"role": "assistant", "content": m["reply"].raw})
            elif m["role"] == "tool_results":
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r["id"], "content": r["content"],
                     **({"is_error": True} if r.get("is_error") else {})} for r in m["results"]]})
        return out

    def complete(self, system, messages, tools=None, max_tokens=16000, effort="medium", on_text=None, web_search=0):
        kwargs: Dict[str, Any] = dict(model=self.model, max_tokens=max_tokens, system=system,
                                      messages=self._messages(messages), output_config={"effort": effort},
                                      thinking={"type": "adaptive"})
        all_tools = list(tools or [])
        if web_search:
            all_tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": web_search})
        if all_tools:
            kwargs["tools"] = all_tools
        if hasattr(self.client.messages, "stream"):
            with self.client.messages.stream(**kwargs) as stream:
                if on_text:
                    for text in stream.text_stream:
                        on_text(text)
                message = stream.get_final_message()
        else:
            message = self.client.messages.create(**kwargs)
        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            reason = getattr(details, "explanation", None) or "the request was declined"
            raise ModelError(f"The model declined this request: {reason}. Try rephrasing it.")
        content = list(message.content)
        text = "".join(b.text for b in content if getattr(b, "type", "") == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input or {})) for b in content if getattr(b, "type", "") == "tool_use"]
        stop = {"tool_use": "tool_use", "pause_turn": "pause", "max_tokens": "max_tokens"}.get(message.stop_reason, "end")
        return Reply(text=text.strip(), tool_calls=calls, stop=stop, raw=content)


def _pdf_text(data: str) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(io.BytesIO(base64.b64decode(data)))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return None


class OpenAICompatibleProvider(Provider):
    """Any server that speaks OpenAI's /chat/completions with tool calling."""

    def __init__(self, name: str, model: str, base_url: str, api_key: Optional[str] = None, timeout: int = 600):
        super().__init__(model)
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _part(self, p: Any) -> Dict[str, Any]:
        if isinstance(p, str):
            return {"type": "text", "text": p}
        kind = p.get("type")
        if kind == "image":
            return {"type": "image_url", "image_url": {"url": f"data:{p['media_type']};base64,{p['data']}"}}
        if kind == "pdf":
            text = _pdf_text(p["data"])
            name = p.get("name", "document.pdf")
            return {"type": "text", "text": f"--- {name} ---\n{text}\n--- end of {name} ---" if text else
                    f"[{name} is a PDF; this model can't read PDFs directly. Install pypdf (mcn add pdf) to send its text.]"}
        return {"type": "text", "text": p.get("text", "")}

    def _messages(self, system, messages):
        out: List[Dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "user":
                c = m["content"]
                out.append({"role": "user", "content": c if isinstance(c, str) else [self._part(p) for p in c]})
            elif m["role"] == "assistant":
                out.append(m["reply"].raw)
            elif m["role"] == "tool_results":
                out += [{"role": "tool", "tool_call_id": r["id"], "content": r["content"]} for r in m["results"]]
        return out

    def complete(self, system, messages, tools=None, max_tokens=16000, effort="medium", on_text=None, web_search=0):
        body: Dict[str, Any] = {"model": self.model, "messages": self._messages(system, messages)}
        body["max_completion_tokens" if self.name == "openai" else "max_tokens"] = max_tokens
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}} for t in tools]
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if on_text:
            body["stream"] = True
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers,
                              timeout=(15, self.timeout), stream=bool(on_text))
        except requests.RequestException as exc:
            raise ModelError(f"Couldn't reach {self.name} at {self.base_url}: {exc}") from None
        if r.status_code >= 400:
            try:
                data = r.json()
            except ValueError:
                data = {}
            err = data.get("error") if isinstance(data, dict) else None
            message = (err.get("message") if isinstance(err, dict) else err) or r.text[:300]
            raise ModelError(f"{self.name} answered {r.status_code}: {message}")
        if on_text:
            data = self._collect_stream(r, on_text)
            on_text = None                               # already sent piece by piece
        else:
            try:
                data = r.json()
            except ValueError:
                raise ModelError(f"{self.name} returned something that isn't JSON") from None
        choices = data.get("choices") or []
        if not choices:
            raise ModelError(f"{self.name} returned no answer")
        msg = choices[0].get("message") or {}
        finish = choices[0].get("finish_reason")
        if finish == "content_filter" or msg.get("refusal"):
            raise ModelError(f"The model declined this request: {msg.get('refusal') or 'content filter'}. Try rephrasing it.")
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {"_unparsed": fn.get("arguments")}
            calls.append(ToolCall(tc.get("id") or fn.get("name", "call"), fn.get("name", ""),
                                  args if isinstance(args, dict) else {"value": args}))
        text = msg.get("content") or ""
        if isinstance(text, list):                       # some servers send content parts
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        if on_text and text:
            on_text(text)
        raw = {"role": "assistant", "content": text or None}
        if msg.get("tool_calls"):
            raw["tool_calls"] = msg["tool_calls"]
        stop = "tool_use" if calls else ("max_tokens" if finish == "length" else "end")
        return Reply(text=text.strip(), tool_calls=calls, stop=stop, raw=raw)

    @staticmethod
    def _collect_stream(r, on_text) -> Dict[str, Any]:
        """Server-sent chunks → one /chat/completions answer, sending text as it arrives."""
        content, calls, finish, refusal = [], {}, None, None
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except ValueError:
                continue
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    content.append(delta["content"])
                    on_text(delta["content"])
                if delta.get("refusal"):
                    refusal = delta["refusal"]
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc.get("index", 0), {"id": None, "type": "function",
                                                                "function": {"name": "", "arguments": ""}})
                    slot["id"] = tc.get("id") or slot["id"]
                    fn = tc.get("function") or {}
                    slot["function"]["name"] += fn.get("name") or ""
                    slot["function"]["arguments"] += fn.get("arguments") or ""
                finish = choice.get("finish_reason") or finish
        msg: Dict[str, Any] = {"role": "assistant", "content": "".join(content) or None}
        if calls:
            msg["tool_calls"] = [dict(c, id=c["id"] or f"call_{i}") for i, c in sorted(calls.items())]
        if refusal:
            msg["refusal"] = refusal
        return {"choices": [{"message": msg, "finish_reason": finish}]}


class OllamaProvider(OpenAICompatibleProvider):
    """A local model in Ollama, through its own API, which (unlike its OpenAI-compatible one) can set the
    context window: MCN's language guide alone is about 4,000 tokens. MCN_OLLAMA_CONTEXT sets it (default 32768)."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout: int = 900):
        base = base_url.rstrip("/")
        super().__init__("ollama", model, base[:-3] if base.endswith("/v1") else base, None, timeout)
        self.context = int(os.getenv("MCN_OLLAMA_CONTEXT", "32768"))

    def _part(self, p):
        return super()._part(p)

    def _ollama_messages(self, system, messages):
        out: List[Dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        names: Dict[str, str] = {}
        for m in messages:
            if m["role"] == "user":
                c = m["content"]
                if isinstance(c, str):
                    out.append({"role": "user", "content": c})
                    continue
                texts, images = [], []
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "image":
                        images.append(p["data"])
                    else:
                        texts.append(self._part(p)["text"])
                out.append({"role": "user", "content": "\n\n".join(texts), **({"images": images} if images else {})})
            elif m["role"] == "assistant":
                raw = m["reply"].raw
                for tc in raw.get("tool_calls") or []:
                    names[tc.get("id", "")] = tc["function"]["name"]
                out.append(raw)
            elif m["role"] == "tool_results":
                out += [{"role": "tool", "content": r["content"], "tool_name": names.get(r["id"], "")}
                        for r in m["results"]]
        return out

    def complete(self, system, messages, tools=None, max_tokens=16000, effort="medium", on_text=None, web_search=0):
        body: Dict[str, Any] = {"model": self.model, "messages": self._ollama_messages(system, messages), "stream": True,
                                "options": {"num_ctx": self.context, "num_predict": max_tokens}}
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}} for t in tools]
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=body, timeout=(15, self.timeout), stream=True)
        except requests.RequestException as exc:
            raise ModelError(f"Couldn't reach Ollama at {self.base_url}: {exc}. Is it running?") from None
        if r.status_code >= 400:
            try:
                message = r.json().get("error") or r.text[:300]
            except ValueError:
                message = r.text[:300]
            raise ModelError(f"Ollama answered {r.status_code}: {message}")
        text, calls, done_reason = [], [], None
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            if chunk.get("error"):
                raise ModelError(f"Ollama: {chunk['error']}")
            msg = chunk.get("message") or {}
            if msg.get("content"):
                text.append(msg["content"])
                if on_text:
                    on_text(msg["content"])
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {"_unparsed": args}
                calls.append(ToolCall(f"call_{len(calls)}", fn.get("name", ""), args if isinstance(args, dict) else {}))
            if chunk.get("done"):
                done_reason = chunk.get("done_reason")
        content = "".join(text)
        raw = {"role": "assistant", "content": content}
        if calls:
            raw["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.input}}
                                 for c in calls]
        stop = "tool_use" if calls else ("max_tokens" if done_reason == "length" else "end")
        return Reply(text=content.strip(), tool_calls=calls, stop=stop, raw=raw)
