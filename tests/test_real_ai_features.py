"""
Features that used to return simulated output now do the real thing: agents,
pipelines, data sources, translate(), the model registry, workflows and the
Salesforce integration. AI and HTTP calls are faked so the tests run offline.
"""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import ai_builtins  # noqa: E402
from mcn.core_engine.mcn_interpreter import MCNInterpreter  # noqa: E402
from mcn.core_engine.mcn_v3_extensions import (  # noqa: E402
    MCNAgentSystem, MCNDataPipeline, MCNDataSourceSystem, MCNModelRegistry, MCNNaturalLanguage)


@pytest.fixture
def model(monkeypatch):
    """A fake AI provider: records each call and answers with `answer(prompt, opts)`."""
    calls = []
    state = SimpleNamespace(calls=calls, answer=lambda prompt, opts: f"reply to: {prompt[-40:]}")

    def fake(prompt, opts):
        calls.append({"prompt": prompt, **{k: v for k, v in opts.items() if not k.startswith("_")}})
        return state.answer(prompt, opts)
    monkeypatch.setattr(ai_builtins, "_provider_complete", fake)
    return state


def run(code):
    out = io.StringIO()
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(out):
        interp.execute(code, quiet=True)
    return interp, out.getvalue()


# ── Agents ────────────────────────────────────────────────────────────────────

def test_agents_answer_with_the_model_and_remember(model):
    agents = MCNAgentSystem(MCNModelRegistry())
    agents.create_agent("analyst", "You analyse sales data.")
    model.answer = lambda prompt, opts: "March was the best month."
    assert agents.agent_think("analyst", "Which month was best?") == "March was the best month."
    assert model.calls[0]["system"] == "You analyse sales data."
    agents.agent_think("analyst", "Why?")
    assert "Which month was best?" in model.calls[1]["prompt"] and "March was the best month." in model.calls[1]["prompt"]
    agents.reset_agent("analyst")
    agents.agent_think("analyst", "Hello")
    assert "Conversation so far" not in model.calls[2]["prompt"]


def test_coordinator_combines_its_team(model):
    agents = MCNAgentSystem(MCNModelRegistry())
    agents.create_agent("optimist", "Look for upside.")
    agents.create_agent("skeptic", "Look for risks.")
    agents.create_multi_agent("lead", ["optimist", "skeptic"], "Decide.")
    model.answer = lambda prompt, opts: {"Look for upside.": "Grow fast.", "Look for risks.": "Cash is low."}.get(
        opts.get("system"), "Grow carefully.")
    assert agents.agent_think("lead", "Should we hire?") == "Grow carefully."
    final = model.calls[-1]["prompt"]
    assert "optimist: Grow fast." in final and "skeptic: Cash is low." in final
    with pytest.raises(Exception, match="Create these agents first"):
        agents.create_multi_agent("x", ["nobody"], "p")


def test_agents_with_tools_use_agent_run(model):
    agents = MCNAgentSystem(MCNModelRegistry())
    seen = {}
    agents.tool_runner = lambda prompt, opts: seen.update(opts) or {"reply": "Revenue was 120k.", "tool_calls": []}
    agents.create_agent("finance", "You answer finance questions.", tools=["revenue"])
    assert agents.agent_think("finance", "What was revenue?") == "Revenue was 120k."
    assert seen["tools"] == ["revenue"] and seen["system"] == "You answer finance questions."


def test_agent_builtin_from_mcn(model):
    model.answer = lambda prompt, opts: "Hi Ana."
    _, out = run('agent("create", "greeter", {prompt: "Greet people"})\nlog(agent("think", "greeter", "I am Ana"))\n'
                 'log(agent("explode", "greeter"))')
    assert "Hi Ana." in out and "Unknown agent operation 'explode'" in out


# ── Pipelines ─────────────────────────────────────────────────────────────────

def test_pipeline_ai_steps_use_classify_and_extract(model):
    pipe = MCNDataPipeline(MCNModelRegistry())
    model.answer = lambda prompt, opts: ("complaint" if opts.get("system", "").startswith("You are a classifier")
                                         else json.dumps({"order_id": "A17"}))
    pipe.create_pipeline("tickets", [{"type": "clean"},
                                     {"type": "ai_classify", "params": {"categories": ["complaint", "question"]}},
                                     {"type": "ai_extract", "params": {"fields": ["order_id"]}}])
    out = pipe.run_pipeline("tickets", ["  Order   A17 is broken  ", "Where is A17?"])
    assert len(out) == 2 and out[0]["classification"] == "complaint" and out[0]["order_id"] == "A17"
    assert out[0]["data"] == "Order A17 is broken"


def test_pipeline_rejects_unknown_steps_and_calls_functions():
    pipe = MCNDataPipeline(MCNModelRegistry())
    with pytest.raises(Exception, match="Unknown pipeline step 'shred'"):
        pipe.create_pipeline("p", [{"type": "shred"}])
    pipe.function_lookup = lambda name: (lambda d: d * 2) if name == "double" else None
    pipe.create_pipeline("p", [{"type": "double"}])
    assert pipe.run_pipeline("p", 21) == 42


# ── Data sources ──────────────────────────────────────────────────────────────

def test_datasource_reads_files_and_answers_from_relevant_chunks(model, tmp_path):
    handbook = tmp_path / "handbook.md"
    handbook.write_text("Holidays\n\nEveryone gets 25 days of paid leave a year.\n\n"
                        "Expenses\n\nSubmit receipts within 30 days.\n\nParking\n\nThe garage closes at 9pm.")
    ds = MCNDataSourceSystem()
    assert "chunks" in ds.create_datasource("handbook", "file", str(handbook))
    hits = ds.search("handbook", "How many days of paid leave?")
    assert "25 days" in hits[0]["text"]
    model.answer = lambda prompt, opts: "You get 25 days."
    assert ds.query_rag("handbook", "How many days of paid leave?") == "You get 25 days."
    assert "25 days of paid leave" in model.calls[-1]["prompt"]
    with pytest.raises(Exception, match="File not found"):
        ds.create_datasource("x", "file", str(tmp_path / "missing.md"))
    with pytest.raises(Exception, match="Unknown source type"):
        ds.create_datasource("x", "magic", "")


def test_datasource_reads_web_pages(monkeypatch):
    import requests
    page = "<html><nav>Menu</nav><h1>Help</h1><p>Returns are free for 60 days.</p><script>x()</script></html>"
    monkeypatch.setattr(requests, "get", lambda url, **k: SimpleNamespace(
        text=page, headers={"content-type": "text/html"}, raise_for_status=lambda: None))
    ds = MCNDataSourceSystem()
    ds.create_datasource("site", "url", "https://example.com/help")
    text = " ".join(d["text"] for d in ds.datasources["site"]["documents"])
    assert "Returns are free for 60 days." in text and "x()" not in text and "Menu" not in text


# ── translate() ───────────────────────────────────────────────────────────────

def test_translate_offline_writes_todays_syntax(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_URL"):
        monkeypatch.delenv(key, raising=False)
    nl = MCNNaturalLanguage(MCNModelRegistry())
    assert nl.translate("if age is greater than 18 then print adult") == "if age > 18\n    log(adult)"
    assert nl.translate("create a variable name with value John") == 'var name = "John"'
    assert nl.translate("select name, email from users") == 'query("SELECT name, email FROM users")'
    assert nl.translate("build me a CRM").startswith("// translate() needs an AI key")


def test_translate_with_ai_checks_and_retries(model, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    answers = iter(["if total > 100 {\n  log(\"big\")\n}", "if total > 100\n    log(\"big\")"])
    model.answer = lambda prompt, opts: next(answers)
    nl = MCNNaturalLanguage(MCNModelRegistry())
    assert nl.translate("if the total is over 100 say big") == 'if total > 100\n    log("big")'
    assert "didn't parse" in model.calls[1]["prompt"]


def test_translate_and_run_in_the_programs_scope(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_URL"):
        monkeypatch.delenv(key, raising=False)
    _, out = run('use "natural"\ntranslate("create variable greeting with value welcome", true)\nlog(greeting)')
    assert "welcome" in out


# ── Model registry ────────────────────────────────────────────────────────────

def test_registry_has_no_fake_models():
    reg = MCNModelRegistry()
    assert reg.models == {} and reg.get_model() is None
    reg.register_model("careful", "anthropic", temperature=0.1)
    assert reg.options_for("careful") == {"temperature": 0.1, "model": "careful", "provider": "anthropic"}


# ── Workflows ─────────────────────────────────────────────────────────────────

def test_workflows_run_the_functions_their_steps_name(tmp_path, monkeypatch):
    from mcn.core_engine import mcn_business_packages as biz
    monkeypatch.setattr(biz.workflow_engine, "db_path", tmp_path / "wf.db")
    biz.workflow_engine._init_database()
    code = '''use "workflows"
function check_stock(data)
    return {in_stock: data.qty <= 5}
function charge(data)
    if not data.in_stock
        throw "Out of stock"
    return {charged: data.qty * 10}
create_workflow("order", ["check_stock", "charge"])
var ok = trigger_workflow("order", {qty: 3})
log(ok.result.data.charged)
var bad = trigger_workflow("order", {qty: 9})
log(bad.status)
log(bad.result.error)
'''
    _, out = run(code)
    assert "30" in out and "failed" in out and "Step 'charge' failed" in out and "Out of stock" in out


def test_workflow_step_without_a_function_fails_clearly(tmp_path, monkeypatch):
    from mcn.core_engine import mcn_business_packages as biz
    engine = biz.WorkflowEngine.__new__(biz.WorkflowEngine)
    engine.db_path, engine.resolver = tmp_path / "wf.db", None
    engine._init_database()
    engine.create_workflow("w", ["missing_step"])
    result = engine.trigger_workflow("w", {})
    assert result["status"] == "failed" and "No function named 'missing_step'" in result["result"]["error"]


# ── Salesforce ────────────────────────────────────────────────────────────────

def test_salesforce_sync_calls_the_rest_api(monkeypatch):
    import requests
    from mcn.core_engine.mcn_business_packages import IntegrationSystem
    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, **k: SimpleNamespace(
        status_code=200, json=lambda: {"access_token": "tok", "instance_url": "https://acme.my.salesforce.com"}))

    def fake_get(url, params=None, headers=None, timeout=None):
        sent.update(url=url, q=params["q"], auth=headers["Authorization"])
        return SimpleNamespace(status_code=200, json=lambda: {"totalSize": 2, "records": [
            {"attributes": {"type": "Contact"}, "Id": "1", "Name": "Ana"}, {"attributes": {}, "Id": "2", "Name": "Bo"}]})
    monkeypatch.setattr(requests, "get", fake_get)
    integ = IntegrationSystem()
    integ.setup_integration("salesforce", {"instance_url": "https://acme.my.salesforce.com",
                                           "client_id": "id", "client_secret": "secret"})
    result = integ.sync_data("salesforce", "contacts")
    assert result["records"] == 2 and result["data"][0] == {"Id": "1", "Name": "Ana"}
    assert "FROM Contact" in sent["q"] and sent["auth"] == "Bearer tok" and "/services/data/" in sent["url"]
    integ.setup_integration("salesforce", {"client_id": "id", "client_secret": "s"})
    assert "instance_url" in integ.sync_data("salesforce", "contacts")["error"]
