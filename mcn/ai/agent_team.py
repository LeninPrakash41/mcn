"""
MCN Agent Team: a team of specialist Claude agents that plans, designs, builds
and tests an MCN app from a description.

    researcher  what this kind of app needs: users, data, workflows, rules (can search the web)
    architect   the data model, endpoints, screens, sign-in and audit choices
    designer    each screen's layout, components, wording and empty states
    builder     writes backend/main.mcn and ui/app.mcn, checked by MCN's parser. When the
                architect splits the app into modules, one builder per module works at the same
                time; each writes only its module, which is checked against the others
                (ownership, missing endpoints) before QA
    qa          runs the checks (types, every endpoint, the compiled UI and, in Studio,
                every screen in a real browser), looks at the screenshots, and either
                approves or sends a fix list back to the builder (at most twice)

The pipeline is fixed and driven by code, so cost and behaviour stay predictable.
Progress is reported through `emit(event)`:

    {"type": "agent", "role": "architect", "status": "working" | "done" | "skipped" | "failed", "summary": "..."}
    {"type": "token", "role": "builder", "text": "..."}
    {"type": "module", "name": "billing", "status": "working" | "done" | "failed", "summary": "..."}
    {"type": "qa", "round": 1, "report": {...}}
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .llm import DEFAULT_CLAUDE_MODEL, AnthropicProvider, Provider, describe, get_provider
from .mcn_agent import MCNAgent, _extract_blocks, _validate_mcn
from .mcn_spec import MCN_SYSTEM_PROMPT

Emit = Callable[[Dict[str, Any]], None]
BrowserCheck = Callable[[Path], Dict[str, Any]]

ROLES = ("researcher", "architect", "designer", "builder", "qa")
MAX_FIX_ROUNDS = 2
MAX_PARALLEL_BUILDERS = 6

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
Keep it buildable in one backend and one UI file. No code.

When the app has two or more distinct areas (for example sales, billing and inventory), also split
it into modules so several builders can work at the same time. After </plan>, add <modules> with
JSON in this shape:
{{"app": {{"name": "OpsHub", "title": "Ops Hub", "theme": "professional"}}, "auth": null, "audit": false,
 "modules": [{{"name": "billing", "about": "invoices and payments", "owns": ["invoices"],
   "endpoints": ["list_invoices()", "create_invoice(customer: str, amount: float)"],
   "screens": [{{"component": "InvoicesTable", "label": "Invoices"}}], "depends_on": ["sales"]}}]}}
auth is null, "jwt" or "sso". Module names are lowercase identifiers. Every table belongs to exactly
one module, and only that module writes it; other modules read it or call its endpoints. Endpoint
and screen names are unique across the app, and the screens are listed in navigation order. Leave
<modules> out when the app has a single area."""

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
to change). When the report lists modules, start each fix with the module it belongs to in brackets,
like "[billing] ...", or "[app]" for navigation and anything shared. Only list real problems: errors, broken screens, missing requested features, empty
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

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 emit: Optional[Emit] = None, web_research: bool = True,
                 browser_check: Optional[BrowserCheck] = None,
                 client: Any = None, provider: Any = None, base_url: Optional[str] = None):
        if isinstance(provider, Provider):
            self.llm = provider
        elif client is not None:                     # an Anthropic client (tests pass a fake one)
            self.llm = AnthropicProvider(model or DEFAULT_CLAUDE_MODEL, client=client)
        else:
            self.llm = get_provider(provider, model, api_key, base_url)
        self.emit: Emit = emit or (lambda event: None)
        self.web_research = web_research
        self.browser_check = browser_check
        self._raw: Dict[str, str] = {}
        self._spec: Optional[Dict[str, Any]] = None             # the modules, when built in parallel
        self._fragments: Dict[str, Dict[str, str]] = {}         # each module's own backend and UI code

    # ── Talking to Claude ─────────────────────────────────────────────────────

    def _ask(self, role: str, system: str, content: Any, effort: str = "medium",
             web_search: bool = False, stream_tokens: bool = False) -> str:
        """One specialist turn. Continues web-search turns until the model finishes."""
        messages: List[Dict[str, Any]] = [{"role": "user", "content": content}]
        texts: List[str] = []
        on_text = (lambda text: self.emit({"type": "token", "role": role, "text": text})) if stream_tokens else None
        search = 3 if web_search and self.llm.supports_web_search else 0
        for _ in range(4):
            reply = self.llm.complete(system, messages, max_tokens=32000, effort=effort, on_text=on_text,
                                      web_search=search)
            texts.append(reply.text)
            if reply.stop != "pause":
                break
            messages.append({"role": "assistant", "reply": reply})
        return "".join(texts).strip()

    def _step(self, role: str, system: str, content: Any, **kwargs) -> str:
        self.emit({"type": "agent", "role": role, "status": "working"})
        try:
            raw = self._ask(role, system, content, **kwargs)
            self._raw[role] = raw
            text = _section(raw, _TAG[role])
        except Exception as exc:
            self.emit({"type": "agent", "role": role, "status": "failed", "summary": str(exc)})
            raise
        self.emit({"type": "agent", "role": role, "status": "done", "summary": _first_line(text), "text": text})
        return text

    # ── The pipeline ──────────────────────────────────────────────────────────

    def run(self, description: str, output_dir: str, attachments: Optional[list] = None) -> Dict[str, Any]:
        out = Path(output_dir)
        request = description.strip()

        research = self._step("researcher", _RESEARCHER, f"Request:\n{request}", effort="low",
                              web_search=self.web_research)
        plan = self._step("architect", _ARCHITECT, f"Request:\n{request}\n\nResearch:\n{research}", effort="high")
        design = self._step("designer", _DESIGNER, f"Request:\n{request}\n\nPlan:\n{plan}", effort="medium")

        brief = (f"{request}\n\nFollow this plan from the architect:\n{plan}\n\n"
                 f"And this screen design from the designer:\n{design}")
        spec = parse_modules(self._raw.get("architect", ""))
        if spec:
            backend, ui, attempts = self._build_modules(spec, brief, out)
        else:
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
            by_module = self._fixes_by_module(fixes)
            if by_module:
                backend, ui = self._fix_modules(by_module, out)
            else:
                backend, ui = self._fix(backend, ui, fixes, out)
                self._fragments = {}            # the files were rewritten whole; fix them whole from now on
            self.emit({"type": "agent", "role": "builder", "status": "done", "summary": "Applied QA fixes"})

        return {"backend_mcn": backend, "ui_mcn": ui, "attempts": attempts, "research": research,
                "model": describe(self.llm),
                "plan": plan, "design": design, "verdict": verdict,
                "modules": [m["name"] for m in spec["modules"]] if spec else [],
                "qa_report": {k: v for k, v in report.items() if k != "screenshots"}}

    def _build(self, brief: str, out: Path, attachments: Optional[list]):
        self.emit({"type": "agent", "role": "builder", "status": "working"})
        team = self

        class _Builder(MCNAgent):
            def _call_model(self, prompt, system, verbose):
                return team._ask("builder", system, prompt, effort="high", stream_tokens=True)

        builder = _Builder(provider=self.llm)
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

    # ── Building modules in parallel ──────────────────────────────────────────

    def _build_modules(self, spec: Dict[str, Any], brief: str, out: Path):
        """One builder per module, all at once. Each writes only its own module; the files are
        assembled, checked against each other, and modules with problems are rebuilt once."""
        names = [m["name"] for m in spec["modules"]]
        self._spec = spec
        self._brief = brief
        self.emit({"type": "agent", "role": "builder", "status": "working",
                   "summary": f"Building {len(names)} modules at once: {', '.join(names)}"})
        try:
            self._fragments = dict(zip(names, self._parallel(
                lambda m: self._build_module(spec, m, brief), spec["modules"])))
            backend, ui = self._write_assembled(out)
            attempts = 1
            problems = module_problems(out, spec)
            if problems:
                attempts = 2
                redo = [m for m in spec["modules"] if m["name"] in problems]
                fixed = self._parallel(lambda m: self._build_module(
                    spec, m, brief, previous=self._fragments[m["name"]], fixes=problems[m["name"]]), redo)
                self._fragments.update(zip([m["name"] for m in redo], fixed))
                backend, ui = self._write_assembled(out)
        except Exception as exc:
            self.emit({"type": "agent", "role": "builder", "status": "failed", "summary": str(exc)})
            raise
        self.emit({"type": "agent", "role": "builder", "status": "done",
                   "summary": f"Built {len(names)} modules in parallel ({', '.join(names)})"})
        return backend, ui, attempts

    def _parallel(self, fn, items: List[Any]) -> List[Any]:
        with ThreadPoolExecutor(max_workers=max(1, min(len(items), MAX_PARALLEL_BUILDERS))) as pool:
            return list(pool.map(fn, items))

    def _build_module(self, spec: Dict[str, Any], module: Dict[str, Any], brief: str,
                      previous: Optional[Dict[str, str]] = None, fixes: Optional[List[str]] = None) -> Dict[str, str]:
        name = module["name"]
        self.emit({"type": "module", "name": name, "status": "working",
                   "summary": f"Fixing {len(fixes)} issue(s)" if fixes else module.get("about", "")})
        prompt = brief
        if previous:
            prompt += ("\n\nYou wrote this module before:\n<backend>" + previous["backend"] + "</backend>\n<ui>"
                       + previous["ui"] + "</ui>\n\nChange it to fix these problems, and return the whole "
                       "module again:\n" + "\n".join(f"{i}. {f}" for i, f in enumerate(fixes or [], 1)))
        system = MCN_SYSTEM_PROMPT + "\n\n" + _module_brief(spec, module)
        errors: List[str] = []
        for _ in range(2):
            backend, ui = _extract_blocks(self._ask("builder", system, prompt, effort="high"))
            fragment = {"backend": backend, "ui": ui}
            errors = fragment_errors(fragment, module)
            if not errors:
                self.emit({"type": "module", "name": name, "status": "done",
                           "summary": "Fixed" if fixes else f"Wrote module {name}"})
                return fragment
            prompt += "\n\nYour last answer had problems:\n" + "\n".join(errors)
        if previous:
            self.emit({"type": "module", "name": name, "status": "done", "summary": "Kept the last working version"})
            return previous
        self.emit({"type": "module", "name": name, "status": "failed", "summary": errors[0]})
        raise RuntimeError(f"The builder for module {name} didn't return valid MCN: {errors[0]}")

    def _write_assembled(self, out: Path):
        backend, ui = assemble(self._spec, self._fragments)
        before = _snapshot(out) if (out / "backend" / "main.mcn").exists() else None
        MCNAgent._write(out / "backend" / "main.mcn", backend)
        MCNAgent._write(out / "ui" / "app.mcn", ui)
        if before:
            self._last_change = _change_impact(before, out)
        return backend, ui

    def _fixes_by_module(self, fixes: List[str]) -> Dict[str, List[str]]:
        """QA fixes grouped by module, when every fix names one of the modules; otherwise {}."""
        if not self._fragments:
            return {}
        groups: Dict[str, List[str]] = {}
        for fix in fixes:
            m = re.match(r"\s*\[([A-Za-z_]\w*)\]\s*(.*)", fix, re.S)
            if not m or m.group(1) not in self._fragments:
                return {}
            groups.setdefault(m.group(1), []).append(m.group(2).strip())
        return groups

    def _fix_modules(self, by_module: Dict[str, List[str]], out: Path):
        modules = [m for m in self._spec["modules"] if m["name"] in by_module]
        fixed = self._parallel(lambda m: self._build_module(
            self._spec, m, getattr(self, "_brief", ""), previous=self._fragments[m["name"]],
            fixes=by_module[m["name"]]), modules)
        self._fragments.update(zip([m["name"] for m in modules], fixed))
        return self._write_assembled(out)

    # ── QA ────────────────────────────────────────────────────────────────────

    def _check(self, out: Path) -> Dict[str, Any]:
        self.emit({"type": "agent", "role": "qa", "status": "working", "summary": "Running checks"})
        report = run_checks(out)
        if self._fragments and self._spec:
            report["modules"] = {m["name"]: {"owns": m["owns"], "screens": [x["component"] for x in m["screens"]]}
                                 for m in self._spec["modules"]}
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
            content.append({"type": "image", "media_type": "image/png", "data": shot["png"]})
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


# ── Modules: the architect's split, each builder's brief, and putting the app together ─

_IDENT = re.compile(r"[A-Za-z_]\w*")


def parse_modules(text: str) -> Optional[Dict[str, Any]]:
    """The architect's <modules> JSON, checked; None when there is none or it can't be built in parallel."""
    m = re.search(r"<modules>(.*?)</modules>", text or "", re.S)
    if not m:
        return None
    try:
        spec = json.loads(re.sub(r"^\s*```(?:json)?|```\s*$", "", m.group(1).strip()))
    except ValueError:
        return None
    modules = spec.get("modules") if isinstance(spec, dict) else None
    if not isinstance(modules, list) or len(modules) < 2:
        return None
    seen_tables, seen_screens, names = set(), set(), []
    for mod in modules:
        if not isinstance(mod, dict) or not _IDENT.fullmatch(str(mod.get("name", ""))):
            return None
        mod["name"] = mod["name"].lower()
        mod["owns"] = [str(t) for t in mod.get("owns") or []]
        mod["endpoints"] = [str(e) for e in mod.get("endpoints") or []]
        mod["depends_on"] = [str(d) for d in mod.get("depends_on") or []]
        screens = []
        for screen in mod.get("screens") or []:
            if isinstance(screen, str):
                screen = {"component": screen}
            comp = str(screen.get("component", ""))
            if not _IDENT.fullmatch(comp) or comp in seen_screens:
                return None
            seen_screens.add(comp)
            screens.append({"component": comp, "label": str(screen.get("label") or comp).replace('"', "'")})
        mod["screens"] = screens
        if mod["name"] in names or seen_tables & set(mod["owns"]):
            return None
        names.append(mod["name"])
        seen_tables |= set(mod["owns"])
    app = spec.get("app") if isinstance(spec.get("app"), dict) else {}
    app_name = str(app.get("name") or "App")
    spec["app"] = {"name": app_name if _IDENT.fullmatch(app_name) else "App",
                   "title": str(app.get("title") or app_name).replace('"', "'"),
                   "theme": str(app.get("theme") or "professional").replace('"', "")}
    spec["auth"] = spec.get("auth") if spec.get("auth") in ("jwt", "sso", "token") else None
    spec["audit"] = bool(spec.get("audit"))
    return spec


def _module_brief(spec: Dict[str, Any], module: Dict[str, Any]) -> str:
    others = "\n".join(f"- module {m['name']}: owns {', '.join(m['owns']) or 'no tables'}; endpoints "
                       f"{', '.join(m['endpoints']) or 'none'}" for m in spec["modules"] if m is not module)
    service_lines = ([f'auth "{spec["auth"]}"'] if spec["auth"] else []) + (["audit"] if spec["audit"] else [])
    under = f" with {' and '.join(service_lines)} under it" if service_lines else ""
    return f"""You are one of several builders working at the same time, each on one module of the same
MCN app. Build ONLY module {module['name']} ({module.get('about') or 'see the plan'}).

Backend (inside <backend>):
- CREATE TABLE IF NOT EXISTS and a few seed rows for the tables this module owns: {', '.join(module['owns']) or 'none'}.
- One `service {module['name']}_api`{under}, with exactly these endpoints: {', '.join(module['endpoints']) or 'none'}.
  Give every parameter a type.
- Never INSERT, UPDATE or DELETE another module's tables. SELECT from them, or call their endpoints.
- Declare contracts only for this module's own records.

UI (inside <ui>):
- These components, one per screen: {', '.join(s['component'] for s in module['screens']) or 'none'}.
- No `app` block: navigation is put together from every module.

Write plain top-level code. Don't write a `module` line; it is added around your code.

The other modules (being built right now):
{others}

Reply with <backend>...</backend> and <ui>...</ui> only."""


def _parse_errors(code: str) -> Tuple[Optional[Any], List[str]]:
    from mcn.core_engine.lexer import Lexer
    from mcn.core_engine.parser import Parser
    try:
        parser = Parser(Lexer(code).tokenize())
        program = parser.parse()
    except Exception as exc:
        return None, [str(exc)]
    return program, [str(e) for e in getattr(parser, "errors", []) or []]


def fragment_errors(fragment: Dict[str, str], module: Dict[str, Any]) -> List[str]:
    """What's wrong with one builder's module, before it is put together with the others."""
    errors: List[str] = []
    for part in ("backend", "ui"):
        code = fragment.get(part, "")
        if not code:
            if part == "backend" or module["screens"]:
                errors.append(f"[{part}] missing")
            continue
        program, problems = _parse_errors(code)
        errors += [f"[{part}] {p}" for p in problems]
        if program is None:
            continue
        kinds = {type(s).__name__ for s in program.body}
        if "ModuleDecl" in kinds:
            errors.append(f"[{part}] don't write a `module` line; it is added for you")
        if part == "ui":
            if "AppDecl" in kinds:
                errors.append("[ui] don't write an `app` block; navigation is put together from every module")
            names = {getattr(s, "name", None) for s in program.body if type(s).__name__ == "ComponentDecl"}
            missing = [s["component"] for s in module["screens"] if s["component"] not in names]
            if missing:
                errors.append(f"[ui] missing component(s): {', '.join(missing)}")
    return errors


def _indent(code: str) -> str:
    return "\n".join(("    " + line) if line.strip() else "" for line in code.strip().splitlines())


def _ordered(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Modules with the ones they depend on first, so a module's tables exist before others read them."""
    by_name = {m["name"]: m for m in spec["modules"]}
    out: List[Dict[str, Any]] = []

    def visit(m, path=()):
        if m in out or m["name"] in path:
            return
        for dep in m["depends_on"]:
            if dep in by_name:
                visit(by_name[dep], path + (m["name"],))
        out.append(m)
    for m in spec["modules"]:
        visit(m)
    return out


def assemble(spec: Dict[str, Any], fragments: Dict[str, Dict[str, str]]) -> Tuple[str, str]:
    """backend/main.mcn and ui/app.mcn from each module's code, plus the app's navigation."""
    backend, ui = [], []
    for m in _ordered(spec):
        frag = fragments[m["name"]]
        owns = f"\n    owns {', '.join(m['owns'])}" if m["owns"] else ""
        backend.append(f"module {m['name']}{owns}\n\n{_indent(frag['backend'])}\n")
        if frag.get("ui", "").strip():
            ui.append(f"module {m['name']}\n\n{_indent(frag['ui'])}\n")
    app = spec["app"]
    nav = "\n".join(f'            nav "{s["label"]}" {s["component"]}' for m in spec["modules"] for s in m["screens"])
    ui.append(f'app {app["name"]}\n    title "{app["title"]}"\n    theme "{app["theme"]}"\n'
              f"    layout\n        sidebar\n{nav}\n")
    return "\n".join(backend), "\n".join(ui)


def module_problems(app_dir: Path, spec: Dict[str, Any]) -> Dict[str, List[str]]:
    """Problems in the assembled app, grouped by the module that has to fix them: writes to another
    module's table, screens calling endpoints nobody built, tables a module owns but never creates."""
    from mcn.core_engine.app_map import build_map
    app = build_map(app_dir)
    names = {m["name"] for m in spec["modules"]}
    problems: Dict[str, List[str]] = {}
    for issue in app["issues"]:
        if issue.get("severity") == "note" or issue["kind"] == "shared_ownership":
            continue
        node = app["nodes"].get(issue.get("where", ""), {})
        owner = node.get("module") or (node["name"] if node.get("kind") == "module" else None)
        if owner in names:
            problems.setdefault(owner, []).append(issue["message"])
    return problems

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
