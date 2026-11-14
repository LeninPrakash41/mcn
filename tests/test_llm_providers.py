"""
MCN's agents work with any model that can call tools: choosing the provider, and the
OpenAI-compatible adapter (OpenAI, Gemini, OpenRouter, Ollama, any compatible server)
driving the change agent and the generator through a fake server.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.ai import llm  # noqa: E402
from mcn.ai.llm import AnthropicProvider, ModelError, OpenAICompatibleProvider, get_provider  # noqa: E402

KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_URL",
        "OLLAMA_MODEL", "MCN_AGENT_PROVIDER", "MCN_AGENT_MODEL", "MCN_AGENT_BASE_URL", "MCN_AGENT_API_KEY")


@pytest.fixture
def clean(monkeypatch, tmp_path):
    """No keys, no config: every test sets exactly what it needs."""
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(llm, "anthropic", type("A", (), {"Anthropic": lambda **kw: object()}))
    return tmp_path


def config(home, **values):
    (home / ".mcn").mkdir(exist_ok=True)
    (home / ".mcn" / "config.json").write_text(json.dumps(values))


def test_nothing_set_up_says_how(clean):
    with pytest.raises(ModelError, match="No AI model is set up"):
        get_provider()


def test_provider_from_whichever_key_is_set(clean, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    p = get_provider()
    assert (p.name, p.model) == ("gemini", "gemini-2.5-pro") and "generativelanguage" in p.base_url
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert get_provider().name == "openai"                          # OpenAI is checked before Gemini
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert isinstance(get_provider(), AnthropicProvider)            # Claude when its key is there


def test_explicit_and_config_choices(clean, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    config(clean, ai_provider="ollama", ai_model="qwen2.5-coder")
    p = get_provider()
    assert (p.name, p.model, p.base_url) == ("ollama", "qwen2.5-coder", "http://localhost:11434/v1")
    p = get_provider("compatible", "my-model", base_url="http://gpu-box:8000/v1/")
    assert (p.name, p.base_url, p.api_key) == ("compatible", "http://gpu-box:8000/v1", None)
    config(clean, ai_provider="openrouter", openrouter_api_key="sk-or-x")
    with pytest.raises(ModelError, match="Say which openrouter model"):
        get_provider()
    with pytest.raises(ModelError, match="Unknown AI provider 'mystery'"):
        get_provider("mystery")


def test_a_pasted_key_picks_its_provider(clean):
    assert isinstance(get_provider(api_key="sk-ant-abc"), AnthropicProvider)
    assert get_provider(api_key="sk-proj-abc").name == "openai"
    assert get_provider(api_key="AIzaXYZ").name == "gemini"
    with pytest.raises(ModelError, match="Say which openrouter model"):
        get_provider(api_key="sk-or-abc")


# ── The OpenAI-compatible adapter ────────────────────────────────────────────

class FakeServer:
    """Plays back /chat/completions answers and records each request."""

    def __init__(self, answers, status=200):
        self.answers, self.status, self.requests = list(answers), status, []

    def post(self, url, json=None, headers=None, timeout=None):
        self.requests.append({"url": url, "body": json, "headers": headers})
        answer = self.answers.pop(0)
        status = self.status

        class R:
            status_code = status
            text = str(answer)

            def json(self):
                return answer
        return R()


def tool_call(i, name, args):
    return {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def answer(content=None, calls=None, finish=None):
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = calls
    return {"choices": [{"message": msg, "finish_reason": finish or ("tool_calls" if calls else "stop")}]}


APP_BACKEND = '''query("CREATE TABLE IF NOT EXISTS oc_orders (id INTEGER PRIMARY KEY, total REAL)")

service shop
    endpoint create_order(total: float)
        query("INSERT INTO oc_orders (total) VALUES (?)", (total,))
        return {success: true}

test "orders can be created"
    assert create_order(5).success == true
'''

NEW_ORDER = '''endpoint create_order(total: float)
    if total <= 0
        return {success: false, error: "The total must be positive"}
    query("INSERT INTO oc_orders (total) VALUES (?)", (total,))
    return {success: true}'''


def test_the_change_agent_runs_on_an_openai_compatible_model(tmp_path, monkeypatch):
    from mcn.ai.change_agent import ChangeAgent
    from mcn.core_engine.agent_interface import AGENT_TOOLS, Workspace
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text(APP_BACKEND)
    server = FakeServer([
        answer(calls=[tool_call(1, "explain", {"target": "create_order"})]),
        answer("I'll add the check.", calls=[tool_call(2, "modify", {"target": "create_order", "source": NEW_ORDER})]),
        None,                                   # filled in once the patch id is known
    ])
    original = server.post

    def post(url, json=None, headers=None, timeout=None):
        if server.answers and server.answers[0] is None:
            patch = next(m for m in json["messages"] if m["role"] == "tool" and '"patch"' in m["content"])
            pid = __import__("json").loads(patch["content"])["patch"]
            server.answers[0] = answer(f"Orders now need a positive total.\nPATCH {pid}")
        return original(url, json=json, headers=headers, timeout=timeout)
    monkeypatch.setattr(llm.requests, "post", post)

    model = OpenAICompatibleProvider("openai", "gpt-4o", "https://api.openai.com/v1", "sk-test")
    result = ChangeAgent(provider=model).run("Orders need a positive total", str(tmp_path))
    assert result["summary"] == "Orders now need a positive total." and result["patch"]
    assert [o["name"] for o in result["operations"]] == ["explain", "modify"]
    assert Workspace(tmp_path).validate(result["patch"])["ok"]

    first, last = server.requests[0], server.requests[-1]
    assert first["url"] == "https://api.openai.com/v1/chat/completions"
    assert first["headers"]["Authorization"] == "Bearer sk-test"
    assert first["body"]["model"] == "gpt-4o" and first["body"]["max_completion_tokens"] == 16000
    assert first["body"]["messages"][0]["role"] == "system" and "MCN" in first["body"]["messages"][0]["content"]
    assert [t["function"]["name"] for t in first["body"]["tools"]] == [t["name"] for t in AGENT_TOOLS]
    assert first["body"]["tools"][0]["function"]["parameters"] == AGENT_TOOLS[0]["input_schema"]
    roles = [m["role"] for m in last["body"]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "tool"]
    assert last["body"]["messages"][2]["tool_calls"][0]["function"]["name"] == "explain"
    assert last["body"]["messages"][3]["tool_call_id"] == "call_1"


def test_the_generator_runs_on_a_local_model(tmp_path, monkeypatch):
    from mcn.ai.mcn_agent import MCNAgent
    backend = 'service s\n    endpoint hi()\n        return {ok: true}\n'
    ui = 'component Home\n    render\n        text "Hi"\n\napp A\n    title "A"\n    layout\n        tabs\n            tab "Home" Home\n'
    server = FakeServer([answer(f"<backend>{backend}</backend>\n<ui>{ui}</ui>")])
    monkeypatch.setattr(llm.requests, "post", server.post)
    tokens = []
    model = OpenAICompatibleProvider("ollama", "qwen2.5-coder", "http://localhost:11434/v1")
    result = MCNAgent(provider=model, on_text=tokens.append).generate("a hello app", output_dir=str(tmp_path), verbose=False)
    assert result["attempts"] == 1 and (tmp_path / "ui" / "app.mcn").read_text().startswith("component Home")
    assert "Authorization" not in server.requests[0]["headers"]                    # no key for a local model
    assert server.requests[0]["body"]["max_tokens"] == 64000 and tokens


def test_attachments_for_models_without_pdf_support(monkeypatch):
    model = OpenAICompatibleProvider("compatible", "m", "http://x/v1")
    monkeypatch.setattr(llm, "_pdf_text", lambda data: None)
    parts = model._messages("", [{"role": "user", "content": [
        {"type": "image", "media_type": "image/png", "data": "AAA"},
        {"type": "pdf", "name": "brd.pdf", "data": "BBB"}, {"type": "text", "text": "Build it"}]}])[0]["content"]
    assert parts[0] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}
    assert "brd.pdf is a PDF" in parts[1]["text"] and "mcn add pdf" in parts[1]["text"]
    monkeypatch.setattr(llm, "_pdf_text", lambda data: "Orders have a total")
    part = model._part({"type": "pdf", "name": "brd.pdf", "data": "BBB"})
    assert "Orders have a total" in part["text"]


def test_api_errors_and_refusals_are_readable(monkeypatch):
    model = OpenAICompatibleProvider("openai", "gpt-4o", "https://api.openai.com/v1", "bad")
    monkeypatch.setattr(llm.requests, "post", FakeServer([{"error": {"message": "Incorrect API key"}}], status=401).post)
    with pytest.raises(ModelError, match="openai answered 401: Incorrect API key"):
        model.complete("s", [{"role": "user", "content": "hi"}])
    monkeypatch.setattr(llm.requests, "post", FakeServer([answer(None, finish="content_filter")]).post)
    with pytest.raises(ModelError, match="declined"):
        model.complete("s", [{"role": "user", "content": "hi"}])


def test_claude_keeps_web_search_and_pdfs():
    class Client:
        def __init__(self):
            from types import SimpleNamespace
            self.requests = []
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **kw):
            from types import SimpleNamespace
            self.requests.append(kw)
            return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                                   content=[SimpleNamespace(type="text", text="ok")])
    client = Client()
    reply = AnthropicProvider("claude-opus-5-5", client=client).complete(
        "sys", [{"role": "user", "content": [{"type": "pdf", "name": "a.pdf", "data": "QQ=="}, "Read it"]}], web_search=3)
    sent = client.requests[0]
    assert reply.text == "ok" and sent["tools"][0]["type"].startswith("web_search")
    assert sent["messages"][0]["content"][0]["type"] == "document"
    assert sent["thinking"] == {"type": "adaptive"}
