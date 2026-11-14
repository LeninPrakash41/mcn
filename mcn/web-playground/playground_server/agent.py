"""AI coding agent endpoints and app generation (SSE)."""
import queue
import threading
from flask import Blueprint
from .core import (
    Response,
    _request_workspace,
    _sse,
    jsonify,
    request,
    stream_with_context,
)

bp = Blueprint("agent", __name__)


def _agent_model(data: dict):
    """The model for MCN's agents (Claude, OpenAI, Gemini, a local model...), or (None, error response)."""
    from mcn.ai.llm import ModelError, get_provider
    try:
        return get_provider(api_key=(data.get("api_key") or "").strip() or None), None
    except ModelError as exc:
        return None, (jsonify({"error": str(exc)}), 400)

@bp.route("/api/agent/verify", methods=["POST"])
def agent_verify_endpoint():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"success": False, "error": "Missing 'code' field"}), 400
    try:
        from mcn.core_engine.agent_toolkit import verify_agent_code
    except ImportError:
        from core_engine.agent_toolkit import verify_agent_code
    result = verify_agent_code(code)
    return jsonify({"success": True, "result": result})


@bp.route("/api/agent/repair", methods=["POST"])
def agent_repair_endpoint():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"success": False, "error": "Missing 'code' field"}), 400
    try:
        from mcn.core_engine.agent_toolkit import generate_repair_prompt
    except ImportError:
        from core_engine.agent_toolkit import generate_repair_prompt
    prompt = generate_repair_prompt(code)
    return jsonify({"success": True, "repair_prompt": prompt})


@bp.route("/api/agent/scaffold", methods=["GET", "POST"])
def agent_scaffold_endpoint():
    template = "sales_calendar"
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        template = data.get("template", "sales_calendar")
    else:
        template = request.args.get("template", "sales_calendar")
    try:
        from mcn.core_engine.agent_toolkit import get_agent_scaffold
    except ImportError:
        from core_engine.agent_toolkit import get_agent_scaffold
    code = get_agent_scaffold(template)
    return jsonify({"success": True, "template": template, "code": code})


@bp.route("/api/agent/explain", methods=["GET", "POST"])
def agent_explain_endpoint():
    query = ""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        query = data.get("query", "")
    else:
        query = request.args.get("query", "")
    if not query:
        return jsonify({"success": False, "error": "Missing 'query' parameter"}), 400
    try:
        from mcn.core_engine.agent_toolkit import explain_syntax
    except ImportError:
        from core_engine.agent_toolkit import explain_syntax
    info = explain_syntax(query)
    return jsonify({"success": True, "query": query, "info": info})


# ── AI Generate (SSE) ─────────────────────────────────────────────────────────

@bp.route("/api/generate", methods=["POST"])
def generate_mcn():
    data        = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    attachments = data.get("attachments", []) or []

    if not description and not attachments:
        return jsonify({"error": "Missing 'description' or 'attachments'"}), 400
    if not description and attachments:
        description = f"Build a complete full-stack application according to the {len(attachments)} attached specification documents, flowcharts, and Figma design mockups."
    model, problem = _agent_model(data)
    if problem:
        return problem

    ws = _request_workspace()
    token_queue: queue.Queue = queue.Queue()
    result_box = [None]  # filled by thread: {backend, ui, attempts} or {error}

    def _agent_thread():
        try:
            from mcn.ai.mcn_agent import MCNAgent
            agent = MCNAgent(provider=model, on_text=lambda text: token_queue.put({"type": "token", "text": text}))

            status_msg = f"Generating MCN app with {len(attachments)} attachment(s)…" if attachments else "Generating MCN app…"
            token_queue.put({"type": "status", "text": status_msg})

            result = agent.generate(
                description=description,
                attachments=attachments,
                output_dir=str(ws),
                verbose=False,
            )

            token_queue.put({"type": "status",
                             "text": f"✓ Validated in {result['attempts']} attempt(s)"})
            result_box[0] = {
                "backend":  result["backend_mcn"],
                "ui":       result["ui_mcn"],
                "attempts": result["attempts"],
            }
        except Exception as exc:
            import traceback as _tb
            result_box[0] = {"error": str(exc), "trace": _tb.format_exc()}
        finally:
            token_queue.put(None)  # sentinel — always sent

    threading.Thread(target=_agent_thread, daemon=True).start()

    def _stream():
        while True:
            try:
                item = token_queue.get(timeout=120)
            except queue.Empty:
                yield _sse({"type": "error", "message": "Generation timed out after 120s"})
                return
            if item is None:
                r = result_box[0] or {}
                if "error" in r:
                    yield _sse({"type": "error", "message": r["error"]})
                else:
                    yield _sse({"type": "done", **r})
                return
            yield _sse(item)

    resp = Response(stream_with_context(_stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"]     = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ── AI Agent Team (SSE) ───────────────────────────────────────────────────────

@bp.route("/api/agent/team", methods=["POST"])
def agent_team():
    """Research, plan, design, build and test an app with the agent team, streaming progress."""
    data        = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    attachments = data.get("attachments") or []
    if not description and not attachments:
        return jsonify({"error": "Describe the app the team should build"}), 400
    if not description:
        description = "Build a complete full-stack application according to the attached documents and designs."
    model, problem = _agent_model(data)
    if problem:
        return problem

    ws = _request_workspace()
    preview_url = request.host_url.rstrip("/") + "/preview/"
    events: queue.Queue = queue.Queue()
    result_box = [None]

    def run():
        try:
            from mcn.ai.agent_team import AgentTeam
            from . import browser_qa
            from .devserver import _start_backend
            check = browser_qa.make_check(preview_url, _start_backend) if data.get("browser", True) else None
            team = AgentTeam(provider=model, emit=events.put, web_research=bool(data.get("research", True)),
                             browser_check=check)
            result_box[0] = team.run(description, str(ws), attachments=attachments)
        except Exception as exc:
            result_box[0] = {"error": str(exc)}
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=300)
            except queue.Empty:
                yield _sse({"type": "error", "message": "The agent team stopped responding for 5 minutes"})
                return
            if item is None:
                result = result_box[0] or {}
                if "error" in result:
                    yield _sse({"type": "error", "message": result["error"]})
                else:
                    yield _sse({"type": "done", "backend": result["backend_mcn"], "ui": result["ui_mcn"],
                                "verdict": result["verdict"], "qa_report": result["qa_report"],
                                "plan": result["plan"], "design": result["design"]})
                return
            yield _sse(item)

    resp = Response(stream_with_context(stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ── Change the app through the agent interface (SSE) ─────────────────────────

_AREAS = {
    "ui": "Focus on the screens in ui/app.mcn; change the backend only if the screens need it.",
    "backend": "Focus on the backend (services, endpoints, tables); change screens only if they need it.",
}


def _patch_review(ws_obj, patch_id: str) -> dict:
    """What a person needs to approve a patch: diff, validation and test results."""
    validation = ws_obj.validate(patch_id)
    tests = ws_obj.test(patch_id)
    shown = ws_obj.show(patch_id)
    return {"patch": patch_id, "diff": shown["diff"], "files": sorted({l[6:] for l in shown["diff"].splitlines()
                                                                       if l.startswith("+++ b/")}),
            "validation": validation, "tests": tests, "ok": bool(validation["ok"] and tests["ok"])}


@bp.route("/api/agent/change", methods=["POST"])
def agent_change():
    """An AI agent changes the workspace app through the agent interface; streams its operations and ends
    with a patch to review. Nothing is written until /api/agent/change/apply. With mode "ask" it only
    answers a question, using the read-only operations."""
    data    = request.get_json(silent=True) or {}
    prompt  = (data.get("prompt") or "").strip()
    area    = data.get("area") if data.get("area") in _AREAS else None
    mode    = "ask" if data.get("mode") == "ask" else "change"
    if not prompt:
        return jsonify({"error": "Describe the change"}), 400
    model, problem = _agent_model(data)
    if problem:
        return problem
    ws = _request_workspace()
    if not any(ws.rglob("*.mcn")):
        return jsonify({"error": "There's no app in this workspace yet. Generate one first."}), 400

    events: queue.Queue = queue.Queue()
    request_text = prompt + (f"\n\n{_AREAS[area]}" if area else "")

    def run():
        try:
            from mcn.ai.change_agent import ChangeAgent
            from mcn.core_engine.agent_interface import Workspace
            agent = ChangeAgent(provider=model, emit=events.put)
            if mode == "ask":
                result = agent.ask(prompt, str(ws))
            else:
                result = agent.run(request_text, str(ws))
            done = {"type": "done", "mode": mode, "summary": result["summary"], "patch": result.get("patch")}
            if done["patch"]:
                done.update(_patch_review(Workspace(ws), done["patch"]))
            events.put(done)
        except Exception as exc:
            events.put({"type": "error", "message": str(exc)})
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=300)
            except queue.Empty:
                yield _sse({"type": "error", "message": "The agent stopped responding for 5 minutes"})
                return
            if item is None:
                return
            yield _sse(item)

    resp = Response(stream_with_context(stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@bp.route("/api/agent/change/apply", methods=["POST"])
def agent_change_apply():
    """Write a reviewed patch to the workspace (it must have passed validation and tests)."""
    from mcn.core_engine.agent_interface import InterfaceError, Workspace
    data = request.get_json(silent=True) or {}
    ws = _request_workspace()
    try:
        result = Workspace(ws).execute(str(data.get("patch") or ""), approved=True)
    except InterfaceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    result["contents"] = {rel: (ws / rel).read_text(encoding="utf-8") for rel in result["files"]}
    return jsonify({"success": True, **result})
