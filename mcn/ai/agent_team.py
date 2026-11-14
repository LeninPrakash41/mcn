"""
MCN Agent Team: a team of specialist Claude agents that plans, designs, builds
and tests an MCN app from a description.

    researcher  what this kind of app needs: users, data, workflows, rules (can search the web)
    architect   the data model, endpoints, screens, sign-in and audit choices
    designer    each screen's layout, components, wording and empty states
    builder     writes backend/main.mcn and ui/app.mcn, checked by MCN's parser
    qa          runs the checks (types, every endpoint, the compiled UI and, in Studio,
                every screen in a real browser), looks at the screenshots, and either
                approves or sends a fix list back to the builder (at most twice)

The pipeline is fixed and driven by code, so cost and behaviour stay predictable.
Progress is reported through `emit(event)`:

    {"type": "agent", "role": "architect", "status": "working" | "done" | "skipped" | "failed", "summary": "..."}
    {"type": "token", "role": "builder", "text": "..."}
    {"type": "qa", "round": 1, "report": {...}}
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import anthropic

from .mcn_agent import DEFAULT_MODEL, MCNAgent, _extract_blocks, _validate_mcn, raise_if_refused
from .mcn_spec import MCN_SYSTEM_PROMPT

Emit = Callable[[Dict[str, Any]], None]
BrowserCheck = Callable[[Path], Dict[str, Any]]

ROLES = ("researcher", "architect", "designer", "builder", "qa")
MAX_FIX_ROUNDS = 2

_CAPABILITIES = """MCN builds an app from two files: backend/main.mcn (SQLite or Postgres tables via query(),
a `service` with `endpoint`s, optional `auth "token" | "jwt" | "sso"`, `public` endpoints, `audit`
logging, ai()/agent_run() for AI, test blocks) and ui/app.mcn (`component`s with state, `on load`
and event handlers, a render tree of kit elements: stat, data_table, bar_chart, line_chart,
area_chart, pie_chart, donut_chart, kanban, card, input, select, button, chat, empty_state,
badge, alert; and an `app` block with sidebar or tab navigation). The UI compiles to React and Flutter."""

_RESEARCHER = f"""You are the research specialist on a team that builds business apps with MCN.
{_CAPABILITIES}

Given a request, work out what a good app of this kind needs: who uses it and their roles, the
records and fields it keeps, the main workflows, numbers people watch, and any rules that apply
(privacy, finance, healthcare, approvals). Search the web only when the domain is specialised
enough that conventions matter. Reply with a <research> section of at most 350 words, as short
bullet lists. Don't write code."""

_ARCHITECT = f"""You are the software architect on a team that builds business apps with MCN.
{_CAPABILITIES}

Turn the request and the research into a build plan, inside <plan>:
- Tables: name and columns with SQL types.
- Endpoints: name(params) and what each returns ({{success, data}} shapes).
- Screens: one MCN component per screen, what it shows and which endpoints it calls.
- Navigation: sidebar groups or tabs.
- Sign-in: none, "jwt", or "sso" when the request mentions company login or SSO; `audit` when it
  mentions compliance, audit trails, approvals or sensitive data.
- Seed data: a few realistic rows so the app isn't empty.
Keep it buildable in one backend and one UI file. No code."""

_DESIGNER = f"""You are the product designer on a team that builds business apps with MCN.
{_CAPABILITIES}

Given the plan, design each screen inside <design>: the kit elements in order (stats first, then
charts, then tables or boards), grid columns, labels and button wording in plain language, filters
and search, what empty states say, and a sensible icon per navigation item. Favour clarity: one
main job per screen, the most important number first. No code."""

_QA = """You are the QA lead on a team that builds business apps with MCN.

You get the request, the plan, an automated check report (type check, every endpoint called, the
compiled web UI, and when available each screen opened in a real browser with console errors,
failed requests and on-screen errors) plus screenshots of the screens. The report's app_map lists
structural problems found in the code (a screen calling an endpoint that doesn't exist, navigation to a
missing screen, a table nothing creates); treat those as real bugs. After a fix round, last_fix says what
the builder changed and which screens and endpoints that affects: check those first.

Decide whether the app does what was asked and works. Reply with:
<verdict>pass</verdict> when it's ready, or <verdict>fix</verdict> followed by <fixes> with a
numbered list of concrete changes for the builder (which file, which endpoint or component, what
to change). Only list real problems: errors, broken screens, missing requested features, empty
screens that should show data, confusing wording. Don't ask for style preferences."""

_TAG = {"researcher": "research", "architect": "plan", "designer": "design"}


def _section(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def _first_line(text: str, limit: int = 140) -> str:
    for line in text.splitlines():
        line = line.strip(" -*#\t")
        if line:
            return line if len(line) <= limit else line[: limit - 1] + "…"
    return ""


class AgentTeam:
    """Plan, design, build and test an MCN app with a team of Claude agents."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 emit: Optional[Emit] = None, web_research: bool = True,
                 browser_check: Optional[BrowserCheck] = None,
                 client: Optional[anthropic.Anthropic] = None):
        self.client = client or anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.emit: Emit = emit or (lambda event: None)
        self.web_research = web_research
        self.browser_check = browser_check

    # ── Talking to Claude ─────────────────────────────────────────────────────

    def _ask(self, role: str, system: str, content: Any, effort: str = "medium",
             tools: Optional[list] = None, stream_tokens: bool = False) -> str:
        """One specialist turn. Continues server-tool turns (web search) until Claude finishes."""
        messages: List[Dict[str, Any]] = [{"role": "user", "content": content}]
        texts: List[str] = []
        for _ in range(4):
            kwargs: Dict[str, Any] = dict(model=self.model, max_tokens=32000, system=system,
                                          messages=messages, output_config={"effort": effort})
            if tools:
                kwargs["tools"] = tools
            with self.client.messages.stream(**kwargs) as stream:
                if stream_tokens:
                    for text in stream.text_stream:
                        self.emit({"type": "token", "role": role, "text": text})
                message = stream.get_final_message()
            raise_if_refused(message)
            texts += [b.text for b in message.content if getattr(b, "type", "") == "text"]
            if message.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": message.content})
        return "".join(texts).strip()

    def _step(self, role: str, system: str, content: Any, **kwargs) -> str:
        self.emit({"type": "agent", "role": role, "status": "working"})
        try:
            text = _section(self._ask(role, system, content, **kwargs), _TAG[role])
        except Exception as exc:
            self.emit({"type": "agent", "role": role, "status": "failed", "summary": str(exc)})
            raise
        self.emit({"type": "agent", "role": role, "status": "done", "summary": _first_line(text), "text": text})
        return text

    # ── The pipeline ──────────────────────────────────────────────────────────

    def run(self, description: str, output_dir: str, attachments: Optional[list] = None) -> Dict[str, Any]:
        out = Path(output_dir)
        request = description.strip()

        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}] if self.web_research else None
        research = self._step("researcher", _RESEARCHER, f"Request:\n{request}", effort="low", tools=tools)
        plan = self._step("architect", _ARCHITECT, f"Request:\n{request}\n\nResearch:\n{research}", effort="high")
        design = self._step("designer", _DESIGNER, f"Request:\n{request}\n\nPlan:\n{plan}", effort="medium")

        brief = (f"{request}\n\nFollow this plan from the architect:\n{plan}\n\n"
                 f"And this screen design from the designer:\n{design}")
        backend, ui, attempts = self._build(brief, out, attachments)

        report: Dict[str, Any] = {}
        verdict = "pass"
        for round_no in range(1, MAX_FIX_ROUNDS + 2):
            report = self._check(out)
            self.emit({"type": "qa", "round": round_no, "report": {k: v for k, v in report.items() if k != "screenshots"}})
            verdict, fixes = self._review(request, plan, report)
            if verdict == "pass" or round_no > MAX_FIX_ROUNDS:
                break
            self.emit({"type": "agent", "role": "builder", "status": "working",
                       "summary": f"Fixing {len(fixes)} issue(s) from QA"})
            backend, ui = self._fix(backend, ui, fixes, out)
            self.emit({"type": "agent", "role": "builder", "status": "done", "summary": "Applied QA fixes"})

        return {"backend_mcn": backend, "ui_mcn": ui, "attempts": attempts, "research": research,
                "plan": plan, "design": design, "verdict": verdict,
                "qa_report": {k: v for k, v in report.items() if k != "screenshots"}}

    def _build(self, brief: str, out: Path, attachments: Optional[list]):
        self.emit({"type": "agent", "role": "builder", "status": "working"})
        team = self

        class _Builder(MCNAgent):
            def _call_claude(self, prompt, system, verbose):
                return team._ask("builder", system, prompt, effort="high", stream_tokens=True)

        builder = _Builder.__new__(_Builder)
        builder.client, builder.model = self.client, self.model
        try:
            result = builder.generate(description=brief, attachments=attachments, output_dir=str(out), verbose=False)
        except Exception as exc:
            self.emit({"type": "agent", "role": "builder", "status": "failed", "summary": str(exc)})
            raise
        self.emit({"type": "agent", "role": "builder", "status": "done",
                   "summary": f"Wrote backend/main.mcn and ui/app.mcn ({result['attempts']} attempt(s))"})
        return result["backend_mcn"], result["ui_mcn"], result["attempts"]

    def _fix(self, backend: str, ui: str, fixes: List[str], out: Path):
        prompt = ("The QA lead tested this MCN app and asks for these changes:\n"
                  + "\n".join(f"{i}. {f}" for i, f in enumerate(fixes, 1))
                  + "\n\nReturn BOTH complete, corrected files wrapped in <backend>...</backend> and <ui>...</ui>."
                  + f"\n\nBACKEND (backend/main.mcn):\n{backend}\n\nUI (ui/app.mcn):\n{ui}")
        for _ in range(2):
            raw = self._ask("builder", MCN_SYSTEM_PROMPT, prompt, effort="high", stream_tokens=True)
            new_backend, new_ui = _extract_blocks(raw)
            errors = [e for e in (_validate_mcn(new_backend, "backend") if new_backend else "[backend] missing",
                                  _validate_mcn(new_ui, "ui") if new_ui else "[ui] missing") if e]
            if not errors:
                before = _snapshot(out)
                MCNAgent._write(out / "backend" / "main.mcn", new_backend)
                MCNAgent._write(out / "ui" / "app.mcn", new_ui)
                self._last_change = _change_impact(before, out)
                return new_backend, new_ui
            prompt += "\n\nYour last answer didn't parse:\n" + "\n".join(errors)
        return backend, ui                  # keep the last working version

    # ── QA ────────────────────────────────────────────────────────────────────

    def _check(self, out: Path) -> Dict[str, Any]:
        self.emit({"type": "agent", "role": "qa", "status": "working", "summary": "Running checks"})
        report = run_checks(out)
        if getattr(self, "_last_change", None):
            report["last_fix"] = self._last_change          # what the builder's fix changed, and what that affects
        if self.browser_check:
            try:
                report["browser"] = self.browser_check(out)
            except Exception as exc:
                report["browser"] = {"skipped": f"The browser check failed to run: {exc}"}
        else:
            report["browser"] = {"skipped": "Browser checks run in MCN Studio (install with: mcn add browser-qa)"}
        report["screenshots"] = [s for s in (report["browser"].get("screens") or []) if s.get("png")]
        return report

    def _review(self, request: str, plan: str, report: Dict[str, Any]):
        summary = {k: v for k, v in report.items() if k != "screenshots"}
        browser = dict(summary.get("browser") or {})
        browser["screens"] = [{k: v for k, v in s.items() if k != "png"} for s in browser.get("screens") or []]
        summary["browser"] = browser
        content: List[Dict[str, Any]] = []
        for shot in report.get("screenshots", [])[:6]:
            content.append({"type": "text", "text": f"Screenshot of the {shot.get('name')} screen:"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": shot["png"]}})
        import json
        content.append({"type": "text", "text": f"Request:\n{request}\n\nPlan:\n{plan}\n\n"
                                                f"Check report:\n{json.dumps(summary, indent=1, default=str)[:20000]}"})
        answer = self._ask("qa", _QA, content, effort="medium")
        verdict = "pass" if re.search(r"<verdict>\s*pass\s*</verdict>", answer, re.I) else "fix"
        fixes = [re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
                 for line in _section(answer, "fixes").splitlines() if re.match(r"^\s*\d+[.)]", line)]
        if verdict == "fix" and not fixes:
            verdict = "pass"                # nothing concrete to fix
        self.emit({"type": "agent", "role": "qa", "status": "done",
                   "summary": "Approved" if verdict == "pass" else f"{len(fixes)} issue(s) for the builder",
                   "fixes": fixes})
        return verdict, fixes


def _snapshot(app_dir: Path) -> Path:
    """A copy of the app's MCN files, to compare against after an edit."""
    import shutil
    import tempfile
    copy = Path(tempfile.mkdtemp(prefix="mcn_before_"))
    for part in ("backend", "ui"):
        if (app_dir / part).exists():
            shutil.copytree(app_dir / part, copy / part)
    return copy


def _change_impact(before: Path, after: Path) -> Dict[str, Any]:
    """What an edit changed and what depends on it (mcn impact), for the QA lead."""
    import shutil
    from mcn.core_engine.app_map import build_map, changed_between, impact
    try:
        changed = changed_between(before, after)
        result = impact(build_map(after), [c for c in changed if c in build_map(after)["nodes"]])
        return {"changed": changed, "affected_screens": [s["id"] for s in result["affected"]["screens"]],
                "affected_endpoints": [e["id"] for e in result["affected"]["endpoints"]],
                "tests": result["tests"], "untested": result["untested"]}
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        shutil.rmtree(before, ignore_errors=True)


# ── Automated checks (no AI) ─────────────────────────────────────────────────

def run_checks(app_dir: Path) -> Dict[str, Any]:
    """Type-check both files, call every endpoint in a scratch copy, and compile the web UI."""
    import contextlib
    import io
    import shutil
    import tempfile

    report: Dict[str, Any] = {"types": [], "endpoints": [], "ui_build": None}
    app_dir = Path(app_dir).resolve()
    try:
        from mcn.core_engine.app_map import build_map
        app = build_map(app_dir)
        report["app_map"] = {"summary": app["summary"], "issues": [i["message"] for i in app["issues"]
                                                                    if i.get("severity") != "note"],
                             "notes": [i["message"] for i in app["issues"] if i.get("severity") == "note"]}
    except Exception as exc:
        report["app_map"] = {"error": str(exc)}
    backend_file, ui_file = app_dir / "backend" / "main.mcn", app_dir / "ui" / "app.mcn"

    from mcn.core_engine.type_checker import check_source
    for path in (backend_file, ui_file):
        if path.exists():
            for d in check_source(path.read_text(encoding="utf-8")):
                if getattr(d, "severity", None) is not None and str(d.severity).lower().endswith("error"):
                    report["types"].append(f"{path.relative_to(app_dir)}:{getattr(d, 'line', '?')}: {getattr(d, 'message', d)}")

    scratch = Path(tempfile.mkdtemp(prefix="mcn_qa_"))
    cwd = os.getcwd()
    try:
        shutil.copytree(app_dir / "backend", scratch / "backend")
        if ui_file.exists():
            shutil.copytree(app_dir / "ui", scratch / "ui")
        os.chdir(scratch)                          # the app's database is created in the scratch copy
        from fastapi.testclient import TestClient
        from mcn.core_engine.mcn_server import MCNServer
        with contextlib.redirect_stdout(io.StringIO()):
            server = MCNServer()
            server.load_script(str(scratch / "backend" / "main.mcn"))
        client = TestClient(server.app)
        for ev in server.evaluators:
            for name, params in ev.function_params.items():
                mode = ev.endpoint_auth.get(name, "")
                if mode:
                    report["endpoints"].append({"endpoint": name, "status": "skipped", "note": f"needs auth ({mode})"})
                    continue
                if params:
                    # Calling it without inputs would only test the missing inputs; screens call it properly
                    report["endpoints"].append({"endpoint": name, "status": "not called", "note": "needs inputs"})
                    continue
                res = client.post(f"/{name}", json={})
                entry = {"endpoint": name, "status": res.status_code}
                if res.status_code >= 500:
                    entry["error"] = (res.json() or {}).get("error", res.text)[:300]
                report["endpoints"].append(entry)

        if ui_file.exists():
            from mcn.core_engine.mcn_interpreter import MCNInterpreter
            from mcn.core_engine.ui_compiler import UICompiler, endpoints_from_backend
            interp = MCNInterpreter()
            with contextlib.redirect_stdout(io.StringIO()):
                interp.execute(ui_file.read_text(encoding="utf-8"), str(ui_file), quiet=True)
                UICompiler(output_dir=scratch / "frontend",
                           endpoints=endpoints_from_backend(scratch / "backend" / "main.mcn")).compile(interp._evaluator)
            report["ui_build"] = "ok"
    except Exception as exc:
        report.setdefault("errors", []).append(str(exc)[:500])
        if report["ui_build"] is None:
            report["ui_build"] = f"failed: {str(exc)[:300]}"
    finally:
        os.chdir(cwd)
        shutil.rmtree(scratch, ignore_errors=True)
    return report
