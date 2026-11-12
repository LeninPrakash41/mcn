"""
Fine-tuning: teach a model your examples, then use it from ai() by name.

    var job = fine_tune("gpt-4.1-mini", "support_replies.csv", "support-bot")
    get_training_status("support-bot")      # validating_files → queued → running → succeeded
    ai("My order is late", {model: "support-bot"})

Training runs on OpenAI's fine-tuning service (Anthropic doesn't offer public
fine-tuning for Claude), so it needs OPENAI_API_KEY. The examples are checked and
converted to OpenAI's chat format first; without a key, fine_tune() still checks
them and writes the training file, so you can fix problems before paying for a run.

Training data: a CSV, JSON or JSONL file, or an MCN list. Each example is one of
    {prompt, completion}   {input, output}   {question, answer}   {messages: [...]}
with an optional `system` field (or params.system for all examples).

Jobs are remembered in ~/.mcn/fine_tune/jobs.json under the name you give them.
"""
from __future__ import annotations

import csv
import io
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API = "https://api.openai.com/v1"
MIN_EXAMPLES = 10                         # OpenAI's minimum
_PAIRS = (("prompt", "completion"), ("input", "output"), ("question", "answer"),
          ("user", "assistant"), ("instruction", "response"))
_DONE = ("succeeded", "failed", "cancelled")


def _home() -> Path:
    from .paths import mcn_home
    return mcn_home("fine_tune")


def _registry_path() -> Path:
    return _home() / "jobs.json"


def _load_registry() -> Dict[str, Dict[str, Any]]:
    try:
        return json.loads(_registry_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_registry(data: Dict[str, Dict[str, Any]]) -> None:
    _registry_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Training data ─────────────────────────────────────────────────────────────

def _read_rows(training_data: Any) -> List[Any]:
    if isinstance(training_data, list):
        return training_data
    path = Path(str(training_data))
    if not path.exists():
        raise ValueError(f"Training data not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return list(csv.DictReader(io.StringIO(text)))
    if suffix == ".jsonl":
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    raise ValueError(f"{path.name} line {n} isn't valid JSON")
        return rows
    if suffix == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("examples", [])
    raise ValueError("Training data must be a CSV, JSON or JSONL file, or a list of examples")


def to_chat_examples(rows: List[Any], system: str = "") -> Tuple[List[Dict[str, Any]], List[str]]:
    """Rows as OpenAI chat examples, plus a list of problems (with row numbers)."""
    examples: List[Dict[str, Any]] = []
    problems: List[str] = []
    for n, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            problems.append(f"Example {n} isn't an object")
            continue
        if isinstance(row.get("messages"), list):
            messages = [m for m in row["messages"] if isinstance(m, dict)]
            if not any(m.get("role") == "assistant" and str(m.get("content", "")).strip() for m in messages):
                problems.append(f"Example {n} has no assistant message to learn from")
                continue
            examples.append({"messages": messages})
            continue
        pair = next(((a, b) for a, b in _PAIRS if a in row and b in row), None)
        if not pair:
            problems.append(f"Example {n} needs prompt and completion (or input/output, question/answer)")
            continue
        user, answer = str(row[pair[0]] or "").strip(), str(row[pair[1]] or "").strip()
        if not user or not answer:
            problems.append(f"Example {n} has an empty {pair[0] if not user else pair[1]}")
            continue
        messages = []
        sys_text = str(row.get("system") or system or "").strip()
        if sys_text:
            messages.append({"role": "system", "content": sys_text})
        messages += [{"role": "user", "content": user}, {"role": "assistant", "content": answer}]
        examples.append({"messages": messages})
    if len(examples) < MIN_EXAMPLES:
        problems.append(f"Fine-tuning needs at least {MIN_EXAMPLES} good examples; there are {len(examples)}")
    return examples, problems


def _write_jsonl(examples: List[Dict[str, Any]], path: Path) -> Path:
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in examples), encoding="utf-8")
    return path


# ── OpenAI fine-tuning API ────────────────────────────────────────────────────

def _key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def _api(method: str, path: str, **kwargs) -> Dict[str, Any]:
    import requests
    headers = {"Authorization": f"Bearer {_key()}"}
    res = requests.request(method, f"{API}{path}", headers=headers, timeout=60, **kwargs)
    try:
        body = res.json()
    except ValueError:
        body = {}
    if res.status_code >= 400:
        message = (body.get("error") or {}).get("message") if isinstance(body, dict) else None
        raise RuntimeError(f"OpenAI refused the request ({res.status_code}): {message or res.text[:200]}")
    return body


def _upload(path: Path) -> str:
    with open(path, "rb") as f:
        return _api("POST", "/files", data={"purpose": "fine-tune"},
                    files={"file": (path.name, f, "application/jsonl")})["id"]


def _suffix(name: str) -> str:
    # OpenAI puts this in the model id (ft:<base>:<org>::<suffix>-id); up to 64 characters
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:40] or "mcn"


def fine_tune(base_model: str, training_data: Any, new_model_name: str, params: Any = None) -> Dict[str, Any]:
    """Check the examples, upload them and start a fine-tuning job. Returns the job's details."""
    params = params if isinstance(params, dict) else {}
    name = str(new_model_name or "").strip()
    if not name:
        return {"error": "Give the new model a name, e.g. fine_tune(\"gpt-4.1-mini\", \"data.csv\", \"support-bot\")"}
    if not base_model:
        return {"error": "Choose a base model that OpenAI can fine-tune, e.g. \"gpt-4.1-mini\""}
    try:
        rows = _read_rows(training_data)
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}
    examples, problems = to_chat_examples(rows, str(params.get("system") or ""))
    if problems and (len(examples) < MIN_EXAMPLES or params.get("strict", True)):
        return {"error": "The training data has problems", "problems": problems[:20],
                "good_examples": len(examples)}

    split = float(params.get("validation_split") or 0)
    validation: List[Dict[str, Any]] = []
    if 0 < split < 0.5 and len(examples) >= 2 * MIN_EXAMPLES:
        rng = random.Random(42)
        shuffled = examples[:]
        rng.shuffle(shuffled)
        cut = max(1, int(len(shuffled) * split))
        validation, examples = shuffled[:cut], shuffled[cut:]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    train_file = _write_jsonl(examples, _home() / f"{_suffix(name)}-{stamp}-train.jsonl")
    valid_file = _write_jsonl(validation, _home() / f"{_suffix(name)}-{stamp}-validation.jsonl") if validation else None
    summary = {"name": name, "base_model": base_model, "provider": "openai",
               "training_examples": len(examples), "validation_examples": len(validation),
               "training_file": str(train_file)}

    if params.get("dry_run") or not _key():
        return {**summary, "status": "not_started",
                "message": ("Checked the examples and wrote the training file. "
                            + ("Set OPENAI_API_KEY to start training." if not _key() else "dry_run: nothing uploaded."))}

    try:
        hyper = {k: params[k] for k in ("n_epochs", "batch_size", "learning_rate_multiplier") if k in params}
        job_body: Dict[str, Any] = {"model": base_model, "training_file": _upload(train_file), "suffix": _suffix(name),
                                    "method": {"type": "supervised", "supervised": {"hyperparameters": hyper}}}
        if valid_file:
            job_body["validation_file"] = _upload(valid_file)
        if params.get("seed") is not None:
            job_body["seed"] = int(params["seed"])
        job = _api("POST", "/fine_tuning/jobs", json=job_body)
    except Exception as exc:
        return {**summary, "error": str(exc)}

    registry = _load_registry()
    registry[name] = {"job_id": job["id"], "base_model": base_model, "status": job.get("status"),
                      "model": job.get("fine_tuned_model"), "created": int(time.time())}
    _save_registry(registry)
    return {**summary, "job_id": job["id"], "status": job.get("status"), "model": job.get("fine_tuned_model")}


def _job_id(job_or_name: str) -> Tuple[str, Optional[str]]:
    entry = _load_registry().get(str(job_or_name))
    return (entry["job_id"], str(job_or_name)) if entry else (str(job_or_name), None)


def get_training_status(job_or_name: str) -> Dict[str, Any]:
    """Where a fine-tuning job is: status, the trained model's id when it's done, and the latest message."""
    if not _key():
        return {"error": "Checking fine-tuning jobs needs OPENAI_API_KEY"}
    job_id, name = _job_id(job_or_name)
    try:
        job = _api("GET", f"/fine_tuning/jobs/{job_id}")
        events = _api("GET", f"/fine_tuning/jobs/{job_id}/events", params={"limit": 1}).get("data") or []
    except Exception as exc:
        return {"error": str(exc)}
    result = {"job_id": job_id, "name": name, "status": job.get("status"), "base_model": job.get("model"),
              "model": job.get("fine_tuned_model"), "trained_tokens": job.get("trained_tokens"),
              "finished": job.get("status") in _DONE,
              "message": events[0].get("message") if events else None}
    if job.get("error") and (job["error"] or {}).get("message"):
        result["error"] = job["error"]["message"]
    if name:
        registry = _load_registry()
        registry[name].update({"status": job.get("status"), "model": job.get("fine_tuned_model")})
        _save_registry(registry)
    return result


def cancel_fine_tune(job_or_name: str) -> Dict[str, Any]:
    if not _key():
        return {"error": "Cancelling fine-tuning jobs needs OPENAI_API_KEY"}
    job_id, _ = _job_id(job_or_name)
    try:
        job = _api("POST", f"/fine_tuning/jobs/{job_id}/cancel")
    except Exception as exc:
        return {"error": str(exc)}
    return {"job_id": job_id, "status": job.get("status")}


def fine_tuned_models() -> List[Dict[str, Any]]:
    """The fine-tuning jobs started from this computer, by name."""
    return [{"name": n, **e} for n, e in sorted(_load_registry().items())]


def resolve_model(model: str) -> Optional[str]:
    """The OpenAI model id for a name given to fine_tune(), once training succeeded."""
    entry = _load_registry().get(str(model))
    return entry.get("model") if entry and entry.get("model") else None
