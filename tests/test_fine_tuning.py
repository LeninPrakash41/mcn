"""
fine_tune(): checking and converting examples, a real job on (a fake) OpenAI
fine-tuning API, status, and ai() using the fine-tuned model by name.
"""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import fine_tuning  # noqa: E402
from mcn.core_engine.fine_tuning import fine_tune, get_training_status, to_chat_examples  # noqa: E402

ROWS = [{"prompt": f"Where is order {i}?", "completion": f"Order {i} ships tomorrow."} for i in range(12)]


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MCN_HOME", str(tmp_path / "mcn"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


class FakeOpenAI:
    """Answers the fine-tuning endpoints and records each request."""

    def __init__(self):
        self.calls = []
        self.status = "validating_files"
        self.model = None

    def __call__(self, method, url, headers=None, timeout=None, **kwargs):
        path = url.split("/v1", 1)[1]
        self.calls.append({"method": method, "path": path, **kwargs})
        if path == "/files":
            name = kwargs["files"]["file"][0]
            body = {"id": f"file-{'val' if 'validation' in name else 'train'}"}
        elif path == "/fine_tuning/jobs" and method == "POST":
            body = {"id": "ftjob-123", "status": "validating_files", "fine_tuned_model": None}
        elif path.endswith("/events"):
            body = {"data": [{"message": "Step 40/60: training loss=0.12"}]}
        elif path.endswith("/cancel"):
            body = {"id": "ftjob-123", "status": "cancelled"}
        else:
            body = {"id": "ftjob-123", "status": self.status, "model": "gpt-4.1-mini",
                    "fine_tuned_model": self.model, "trained_tokens": 4200 if self.model else None, "error": None}
        return SimpleNamespace(status_code=200, json=lambda: body, text=json.dumps(body))


@pytest.fixture
def openai(monkeypatch):
    import requests
    fake = FakeOpenAI()
    monkeypatch.setattr(requests, "request", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    return fake


def test_examples_become_chat_messages():
    rows = ROWS[:10] + [{"question": "Refunds?", "answer": "Within 30 days.", "system": "Be brief."},
                        {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}]
    examples, problems = to_chat_examples(rows, system="You are a support agent.")
    assert problems == [] and len(examples) == 12
    assert examples[0]["messages"] == [{"role": "system", "content": "You are a support agent."},
                                       {"role": "user", "content": "Where is order 0?"},
                                       {"role": "assistant", "content": "Order 0 ships tomorrow."}]
    assert examples[10]["messages"][0] == {"role": "system", "content": "Be brief."}


def test_problems_are_reported_with_row_numbers():
    rows = ROWS[:10] + [{"prompt": "x", "completion": ""}, {"title": "nope"}]
    result = fine_tune("gpt-4.1-mini", rows, "bot")
    assert result["error"] == "The training data has problems"
    assert result["problems"] == ["Example 11 has an empty completion",
                                  "Example 12 needs prompt and completion (or input/output, question/answer)"]
    assert "at least 10" in fine_tune("gpt-4.1-mini", ROWS[:3], "bot")["problems"][-1]
    # strict: false skips bad rows when enough good ones remain
    assert fine_tune("gpt-4.1-mini", rows, "bot", {"strict": False})["status"] == "not_started"


def test_without_a_key_it_checks_and_writes_the_file(home):
    result = fine_tune("gpt-4.1-mini", ROWS, "support-bot")
    assert result["status"] == "not_started" and "OPENAI_API_KEY" in result["message"]
    lines = Path(result["training_file"]).read_text().splitlines()
    assert len(lines) == 12 and json.loads(lines[0])["messages"][0]["content"] == "Where is order 0?"


def test_reads_csv_and_jsonl_files(home):
    csv_file = home / "data.csv"
    csv_file.write_text("input,output\n" + "".join(f"q{i},a{i}\n" for i in range(10)))
    assert fine_tune("gpt-4.1-mini", str(csv_file), "csv-bot")["training_examples"] == 10
    jl = home / "data.jsonl"
    jl.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    assert fine_tune("gpt-4.1-mini", str(jl), "jl-bot")["training_examples"] == 12
    assert "not found" in fine_tune("gpt-4.1-mini", str(home / "missing.csv"), "x")["error"]


def test_starts_a_real_job_and_remembers_it(openai):
    rows = ROWS * 2
    result = fine_tune("gpt-4.1-mini", rows, "Support Bot", {"n_epochs": 3, "validation_split": 0.2, "seed": 7})
    assert result["job_id"] == "ftjob-123" and result["status"] == "validating_files"
    assert result["training_examples"] == 20 and result["validation_examples"] == 4
    uploads = [c for c in openai.calls if c["path"] == "/files"]
    assert len(uploads) == 2 and all(c["data"] == {"purpose": "fine-tune"} for c in uploads)
    job = next(c for c in openai.calls if c["path"] == "/fine_tuning/jobs")["json"]
    assert job["model"] == "gpt-4.1-mini" and job["training_file"] == "file-train"
    assert job["validation_file"] == "file-val" and job["suffix"] == "support-bot" and job["seed"] == 7
    assert job["method"] == {"type": "supervised", "supervised": {"hyperparameters": {"n_epochs": 3}}}
    assert fine_tuning.fine_tuned_models()[0]["job_id"] == "ftjob-123"


def test_status_by_name_and_using_the_model_from_ai(openai, monkeypatch):
    from mcn.core_engine import ai_builtins
    fine_tune("gpt-4.1-mini", ROWS, "support-bot")
    status = get_training_status("support-bot")
    assert status["status"] == "validating_files" and status["finished"] is False
    assert status["message"] == "Step 40/60: training loss=0.12"
    # Not trained yet: ai() says so instead of calling a model that doesn't exist
    assert "isn't ready yet" in ai_builtins.mcn_ai("hi", {"model": "support-bot"})

    openai.status, openai.model = "succeeded", "ft:gpt-4.1-mini:acme:support-bot:abc123"
    sent = {}
    monkeypatch.setattr("mcn.providers.openai_provider.openai_complete",
                        lambda prompt, **kw: sent.update(kw) or "Order 5 ships tomorrow.")
    assert ai_builtins.mcn_ai("Where is order 5?", {"model": "support-bot"}) == "Order 5 ships tomorrow."
    assert sent["model"] == "ft:gpt-4.1-mini:acme:support-bot:abc123"
    assert get_training_status("ftjob-123")["trained_tokens"] == 4200


def test_cancel(openai):
    fine_tune("gpt-4.1-mini", ROWS, "bot")
    assert fine_tuning.cancel_fine_tune("bot") == {"job_id": "ftjob-123", "status": "cancelled"}


def test_from_mcn_code(home):
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    import contextlib
    code = ('var rows = []\nfor i in range(10)\n    rows = rows + [{prompt: "q" + str(i), completion: "a" + str(i)}]\n'
            'var job = fine_tune("gpt-4.1-mini", rows, "mcn-bot")\nlog(job.status)\n')
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        MCNInterpreter().execute(code, quiet=True)
    assert "not_started" in out.getvalue()


def test_api_errors_are_readable(openai, monkeypatch):
    import requests
    monkeypatch.setattr(requests, "request", lambda *a, **k: SimpleNamespace(
        status_code=400, json=lambda: {"error": {"message": "Model gpt-x is not available for fine-tuning"}}, text=""))
    result = fine_tune("gpt-x", ROWS, "bot")
    assert "not available for fine-tuning" in result["error"] and result["training_examples"] == 12
