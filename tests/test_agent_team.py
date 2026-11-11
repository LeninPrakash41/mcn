"""
The agent team (researcher, architect, designer, builder, QA) with a fake Claude
client: the pipeline order, QA sending fixes back, web-search continuation, the
automated checks, and Studio's streaming endpoint.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.ai import agent_team  # noqa: E402
from mcn.ai.agent_team import AgentTeam, run_checks  # noqa: E402

TEMPLATE = ROOT / "mcn" / "web-playground" / "playground_server" / "templates" / "ops_dashboard"
BACKEND = (TEMPLATE / "backend" / "main.mcn").read_text()
UI = (TEMPLATE / "ui" / "app.mcn").read_text()


def _message(text, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop, stop_details=None)


class FakeClient:
    """Answers by role (recognised from the system prompt); records every request."""

    def __init__(self, qa_answers=None, research_pauses=0):
        self.calls = []
        self.qa_answers = list(qa_answers or ["<verdict>pass</verdict>"])
        self.research_pauses = research_pauses
        self.messages = SimpleNamespace(stream=self._stream)

    def _answer(self, kwargs):
        system = kwargs["system"]
        if "research specialist" in system:
            if self.research_pauses:
                self.research_pauses -= 1
                return _message("Searching…", stop="pause_turn")
            return _message("<research>- Users: ops managers\n- Orders with status and amount</research>")
        if "software architect" in system:
            return _message("<plan>Tables: orders(id, customer, amount). Screens: Overview, Orders.</plan>")
        if "product designer" in system:
            return _message("<design>Overview: four stats then a revenue chart.</design>")
        if "QA lead" in system:
            return _message(self.qa_answers.pop(0) if self.qa_answers else "<verdict>pass</verdict>")
        return _message(f"<backend>{BACKEND}</backend>\n<ui>{UI}</ui>")       # the builder

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        message = self._answer(kwargs)
        client = self

        class Stream:
            text_stream = iter([b.text for b in message.content])

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get_final_message(self):
                return message
        return Stream()


def roles_of(client):
    out = []
    for call in client.calls:
        s = call["system"]
        out.append("researcher" if "research specialist" in s else "architect" if "software architect" in s
                   else "designer" if "product designer" in s else "qa" if "QA lead" in s else "builder")
    return out


def test_pipeline_runs_each_specialist_in_order(tmp_path):
    client, events = FakeClient(), []
    result = AgentTeam(client=client, emit=events.append).run("An operations dashboard", str(tmp_path))
    assert roles_of(client) == ["researcher", "architect", "designer", "builder", "qa"]
    assert (tmp_path / "backend" / "main.mcn").read_text().strip() == BACKEND.strip()
    assert result["verdict"] == "pass" and "orders" in result["plan"]

    # The architect sees the research; the builder sees the plan and design
    assert "ops managers" in client.calls[1]["messages"][0]["content"]
    builder_prompt = client.calls[3]["messages"][0]["content"]
    assert "Tables: orders" in builder_prompt and "four stats" in builder_prompt
    # Effort per role, and the researcher may search the web
    assert [c["output_config"]["effort"] for c in client.calls] == ["low", "high", "medium", "high", "medium"]
    assert client.calls[0]["tools"][0]["type"] == "web_search_20260209"
    assert all(c["model"] == "claude-opus-5-5" for c in client.calls)

    done = [e["role"] for e in events if e["type"] == "agent" and e["status"] == "done"]
    assert done == ["researcher", "architect", "designer", "builder", "qa"]
    report = next(e for e in events if e["type"] == "qa")["report"]
    assert report["ui_build"] == "ok" and report["types"] == []
    assert "skipped" in report["browser"]                 # no browser outside Studio


def test_qa_fixes_go_back_to_the_builder(tmp_path):
    fixed_ui = UI.replace('"Operations"', '"Operations Hub"')
    client = FakeClient(qa_answers=["<verdict>fix</verdict><fixes>\n1. Rename the app to Operations Hub\n</fixes>",
                                    "<verdict>pass</verdict>"])
    original = client._answer

    def answer(kwargs):
        if "QA lead tested this MCN app" in str(kwargs["messages"][0]["content"]):
            return _message(f"<backend>{BACKEND}</backend><ui>{fixed_ui}</ui>")
        return original(kwargs)
    client._answer = answer
    events = []
    result = AgentTeam(client=client, emit=events.append, web_research=False).run("dashboard", str(tmp_path))
    assert roles_of(client) == ["researcher", "architect", "designer", "builder", "qa", "builder", "qa"]
    assert "Operations Hub" in (tmp_path / "ui" / "app.mcn").read_text()
    assert result["verdict"] == "pass"
    assert "tools" not in client.calls[0]                  # research without web search
    qa_done = [e for e in events if e["type"] == "agent" and e["role"] == "qa" and e["status"] == "done"]
    assert qa_done[0]["fixes"] == ["Rename the app to Operations Hub"]


def test_qa_stops_after_two_fix_rounds(tmp_path):
    client = FakeClient(qa_answers=["<verdict>fix</verdict><fixes>1. Something</fixes>"] * 5)
    result = AgentTeam(client=client, web_research=False).run("dashboard", str(tmp_path))
    assert roles_of(client).count("qa") == 3 and result["verdict"] == "fix"


def test_research_continues_after_a_search_pause(tmp_path):
    client = FakeClient(research_pauses=1)
    AgentTeam(client=client).run("dashboard", str(tmp_path))
    assert roles_of(client)[:2] == ["researcher", "researcher"]
    assert client.calls[1]["messages"][-1]["role"] == "assistant"   # the paused turn is sent back


def test_browser_check_results_and_screenshots_reach_qa(tmp_path):
    client = FakeClient()
    shots = {"screens": [{"name": "Overview", "console_errors": ["boom"], "failed_requests": [],
                          "on_screen_errors": [], "looks_empty": False, "png": "iVBORw0KGgo="}]}
    AgentTeam(client=client, browser_check=lambda d: shots).run("dashboard", str(tmp_path))
    qa_content = client.calls[-1]["messages"][0]["content"]
    assert any(b.get("type") == "image" for b in qa_content)
    report_text = qa_content[-1]["text"]
    assert "boom" in report_text and "iVBORw0KGgo=" not in report_text   # screenshots go as images, not text


def test_run_checks_on_a_template():
    report = run_checks(TEMPLATE)
    assert report["ui_build"] == "ok" and report["types"] == []
    statuses = {e["endpoint"]: e["status"] for e in report["endpoints"]}
    assert statuses["summary"] == 200 and statuses["delete_order"] == "not called"


def test_refusals_stop_the_team(tmp_path):
    client = FakeClient()
    client._answer = lambda kwargs: SimpleNamespace(content=[], stop_reason="refusal",
                                                    stop_details=SimpleNamespace(explanation="not allowed"))
    events = []
    with pytest.raises(RuntimeError, match="declined"):
        AgentTeam(client=client, emit=events.append).run("x", str(tmp_path))
    assert events[-1]["status"] == "failed" and events[-1]["role"] == "researcher"


def test_studio_streams_the_team(monkeypatch):
    from playground_app import load, quiet
    _, client = load()

    class FakeTeam:
        def __init__(self, emit, **kwargs):
            self.emit, self.kwargs = emit, kwargs

        def run(self, description, out, attachments=None):
            self.emit({"type": "agent", "role": "architect", "status": "done", "summary": "Plan ready"})
            return {"backend_mcn": BACKEND, "ui_mcn": UI, "verdict": "pass", "qa_report": {"ui_build": "ok"},
                    "plan": "p", "design": "d"}

    monkeypatch.setattr(agent_team, "AgentTeam", FakeTeam)
    res = quiet(client.post, "/api/agent/team", json={"description": "a CRM", "api_key": "sk-test"})
    events = [json.loads(line[5:]) for line in res.get_data(as_text=True).split("\n\n") if line.startswith("data:")]
    assert events[0]["role"] == "architect" and events[-1]["type"] == "done" and events[-1]["verdict"] == "pass"
    assert quiet(client.post, "/api/agent/team", json={}).status_code == 400


def test_nav_labels_from_the_app_block():
    from playground_server.browser_qa import nav_labels
    assert nav_labels(TEMPLATE) == ["Overview", "Orders", "Tasks"]
