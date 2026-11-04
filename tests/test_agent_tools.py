"""
agent_run: MCN functions become real tools the model can call. The Claude
client is stubbed so these run without a key or network.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402
from mcn.core_engine.mcn_interpreter import MCNInterpreter  # noqa: E402

TOOLS = '''
var created = []

function add_numbers(a, b)
    return a + b

function create_task(title, owner = "support")
    created.push({title: title, owner: owner})
    return {ok: true, title: title}
'''


def block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class FakeClient:
    """Answers with the scripted responses in order and records each request."""
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append({**request, "messages": list(request["messages"])})
        return self.responses.pop(0)


def run_with(monkeypatch, responses, code):
    fake = FakeClient(responses)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: fake)
    interp = MCNInterpreter()
    interp.execute(TOOLS + "\n" + code, quiet=True)
    return interp, fake


def test_tool_call_runs_mcn_function_and_returns_result(monkeypatch):
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            block("text", text="Let me add those."),
            block("tool_use", id="t1", name="add_numbers", input={"a": 2, "b": 40}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text="The answer is 42.")]),
    ]
    interp, fake = run_with(monkeypatch, responses,
                            'var r = agent_run("What is 2 + 40?", {tools: ["add_numbers"], system: "Be brief"})')
    r = interp.variables["r"]
    assert r["reply"] == "The answer is 42."
    assert r["steps"] == 2
    assert r["tool_calls"][0]["name"] == "add_numbers" and r["tool_calls"][0]["output"] == 42

    first = fake.requests[0]
    schema = first["tools"][0]
    assert schema["name"] == "add_numbers"
    assert set(schema["input_schema"]["required"]) == {"a", "b"}
    assert first["system"] == "Be brief"
    # The tool result goes back to the model in one user message
    result_msg = fake.requests[1]["messages"][-1]
    assert result_msg["role"] == "user"
    assert result_msg["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "42", "is_error": False}


def test_optional_params_and_side_effects(monkeypatch):
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            block("tool_use", id="t1", name="create_task", input={"title": "Call Ana"}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text="Done.")]),
    ]
    interp, fake = run_with(monkeypatch, responses,
                            'var r = agent_run("Make a task", {tools: [{name: "create_task", description: "Add a task"}]})')
    assert interp.variables["created"] == [{"title": "Call Ana", "owner": "support"}]
    schema = fake.requests[0]["tools"][0]
    assert schema["description"] == "Add a task"
    assert schema["input_schema"]["required"] == ["title"]


def test_tool_errors_go_back_to_the_model(monkeypatch):
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            block("tool_use", id="t1", name="add_numbers", input={"a": 1}),
            block("tool_use", id="t2", name="no_such_tool", input={}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text="Sorry.")]),
    ]
    interp, fake = run_with(monkeypatch, responses, 'var r = agent_run("go", {tools: ["add_numbers"]})')
    results = fake.requests[1]["messages"][-1]["content"]
    assert [r["is_error"] for r in results] == [True, True]
    assert interp.variables["r"]["reply"] == "Sorry."


def test_stops_after_max_steps(monkeypatch):
    loop = SimpleNamespace(stop_reason="tool_use", content=[block("tool_use", id="t", name="add_numbers", input={"a": 1, "b": 1})])
    interp, fake = run_with(monkeypatch, [loop] * 3, 'var r = agent_run("go", {tools: ["add_numbers"], max_steps: 3})')
    assert len(fake.requests) == 3
    assert "Stopped after 3 steps" in interp.variables["r"]["reply"]


def test_mock_mode_calls_tools_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    interp = MCNInterpreter()
    interp.execute(TOOLS + '\nvar r = agent_run("please create a task for the refund", {tools: ["create_task"]})', quiet=True)
    r = interp.variables["r"]
    assert r["tool_calls"] and r["tool_calls"][0]["name"] == "create_task"
    assert interp.variables["created"]
