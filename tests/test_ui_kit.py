"""
The MCN UI kit: the compiler emits kit components, every module it imports
exists in the kit and in the preview bundle, and Studio's live preview serves
the compiled app.
"""
import contextlib
import io
import json
import re
from pathlib import Path

import pytest

from playground_app import load, quiet
from mcn.core_engine.lexer import Lexer
from mcn.core_engine.parser import Parser
from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.core_engine.ui_compiler import UICompiler, _SHADCN, _DESIGN, _KIT_DIR, brand_colors

ROOT = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / "mcn" / "web-playground" / "static" / "preview"

UI = '''
component Deals
    state items = []
    state stats = {open: 0}

    on load
        items = list_deals().data
        stats = deal_stats().data
        if stats.open > 0
            notify(str(stats.open) + " open deals", "info")

    on delete
        delete_deal(row.id)
        items = list_deals().data

    render
        breadcrumb items=["Sales", "Deals"]
        div grid_cols=3
            bar_chart data=items x_key="title" y_key=["value"] stacked
            donut_chart data=items name_key="stage" value_key="value"
            sparkline data=[1, 3, 2]
        data_table title="Deals" columns=["title", "stage"] filters=["stage"] on_delete=delete
        kanban group_by="stage" on_move=move_deal
        chat "Assistant" endpoint=ask suggestions=["Hi"]
        agent_builder on_save=save_agent on_test=test_agent
        workflow_builder on_save=save_workflow on_run=run_workflow
        empty_state "Nothing yet" icon="Inbox"

app Sales
    title "Sales"
    footer "Acme"
    logo "Rocket"
    layout
        sidebar
            nav "Deals" Deals icon="TrendingUp" group="Pipeline"
'''

ENDPOINTS = {"list_deals": [], "deal_stats": [], "delete_deal": ["id"], "move_deal": ["id", "stage"],
             "ask": ["message", "history"], "add_note": ["deal_id", "text"]}


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    out = tmp_path_factory.mktemp("ui") / "frontend"
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(UI, quiet=True)
        UICompiler(output_dir=out, endpoints=ENDPOINTS).compile(interp._evaluator)
    return out / "src"


def test_kit_elements_compile_to_kit_components(compiled):
    deals = (compiled / "components" / "Deals.tsx").read_text()
    for tag in ["<Breadcrumb", "<BarChart", "<DonutChart", "<Sparkline", "<DataTable", "<Kanban",
                "<ChatBot", "<AgentBuilder", "<WorkflowBuilder", "<EmptyState"]:
        assert tag in deals, tag
    assert 'import { notify } from "@/components/ui/toast"' in deals
    assert "recharts" not in deals and "lucide-react" not in deals and "sonner" not in deals


def test_actions_call_endpoints_or_handlers(compiled):
    deals = (compiled / "components" / "Deals.tsx").read_text()
    # Long callbacks break after the arrow, as Prettier writes them
    assert 'onSend={async (message: string, history: { role: string; content: string }[]) =>\n' \
           '          api.post("/ask", { message, history })\n        }' in deals
    assert 'onMove={async (item: Row, to: string) => api.post("/move_deal", { id: item.id, stage: to, item })}' in deals
    # `on delete` is a handler (delete is reserved in JavaScript) that receives the row
    assert "onDelete={(row: Row) => onDelete(row)}" in deals
    assert "const onDelete = useCallback(async (e?: unknown)" in deals and "const row = e as Row" in deals
    # A failing action tells the user instead of failing silently
    assert 'notify(errorMessage(err), "error")' in deals


def test_endpoint_calls_use_backend_parameter_names_and_await():
    from mcn.core_engine.ui_compiler import _expr_to_ts
    UICompiler(output_dir=Path("."), endpoints=ENDPOINTS)
    expr = Parser(Lexer('var x = add_note(7, "hello").data').tokenize()).parse().body[0].value
    assert _expr_to_ts(expr) == '(await api.post("/add_note", { deal_id: 7, text: "hello" })).data'


def test_state_reads_after_assignment_see_the_new_value(compiled):
    deals = (compiled / "components" / "Deals.tsx").read_text()
    # deal_stats runs alongside the other independent calls; later lines read its result
    m = re.search(r"const (_stats\d+) = _results\d+\[(\d+)\]\.data", deals)
    assert m and 'api.post("/deal_stats", {})' in deals, deals
    assert f"if ({m.group(1)}.open > 0)" in deals


def test_app_uses_app_shell(compiled):
    app = (compiled / "App.tsx").read_text()
    assert 'layout="sidebar"' in app and 'footer={"Acme"}' in app and 'logo={"Rocket"}' in app
    assert 'group: "Pipeline"' in app and 'icon: "TrendingUp"' in app


def test_text_attributes_are_js_strings(tmp_path):
    """JSX doesn't decode escapes in attribute strings: "·" written as "\\u00b7" showed literally."""
    src = 'component Home\n    render\n        empty_state "Nothing" description="Add one \u00b7 now"\n\napp A\n    footer "A \u00b7 B"\n    nav "Home" Home\n'
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
        UICompiler(output_dir=tmp_path, endpoints={}).compile(interp._evaluator)
    text = "".join(p.read_text() for p in (tmp_path / "src").rglob("*.tsx"))
    assert 'footer={"A \\u00b7 B"}' in text and 'description={"Add one \\u00b7 now"}' in text


def test_generated_app_depends_only_on_react(compiled):
    deps = json.loads((compiled.parent / "package.json").read_text())["dependencies"]
    assert set(deps) == {"react", "react-dom"}


def test_every_compiler_module_exists_in_the_kit_and_preview_bundle():
    bundle = (PREVIEW / "mcn-ui.js").read_text()
    for slug in {slug for _, slug, _ in _SHADCN.values()}:
        assert (_KIT_DIR / "components" / "ui" / f"{slug}.tsx").exists(), slug
        assert f'"@/components/ui/{slug}"' in bundle, slug
    for name, module, _ in _DESIGN.values():
        source = (_KIT_DIR / "components" / "ui" / f"{module}.tsx").read_text()
        assert f"export function {name}(" in source, name
        assert f'"@/components/ui/{module}"' in bundle, module


def test_preview_assets_are_built():
    for name in ["react.js", "react-dom.js", "mcn-ui.js", "mcn-transform.js", "mcn-ui.css"]:
        assert (PREVIEW / name).stat().st_size > 1000, name


def test_live_preview_serves_the_compiled_app():
    _, client = load()
    files = [{"path": "backend/main.mcn", "content": "service s\n    port 8080\n    endpoint list_deals()\n        return {data: []}\n"},
             {"path": "ui/app.mcn", "content": "component Deals\n    state items = []\n    render\n        data_table title=\"Deals\"\n\napp A\n    title \"A\"\n    layout\n        main\n            Deals\n"}]
    quiet(client.post, "/api/workspace/reset", json={"files": files})
    page = client.get("/preview/").get_data(as_text=True)
    assert "/static/preview/mcn-ui.js" in page
    src = quiet(client.get, "/api/preview/source").get_json()
    assert src["success"] is True
    assert "App.tsx" in src["files"] and "components/Deals.tsx" in src["files"]
    assert not any(k.startswith("components/ui/") for k in src["files"])     # the kit comes from the bundle


def test_live_preview_reports_ui_errors():
    _, client = load()
    quiet(client.post, "/api/workspace/reset", json={"files": [{"path": "ui/app.mcn", "content": "component X\n    render\n        card\n      text \"misaligned\"\n"}]})
    src = quiet(client.get, "/api/preview/source").get_json()
    assert src["success"] is False and "line 4" in src["error"]


def test_component_named_like_a_kit_component(tmp_path):
    """`component Label` used to clash with the kit's Label import."""
    src = ('component Label\n    state name = ""\n    render\n        form\n            input bind=name label="Name"\n\n'
           'app A\n    nav "Label" Label\n')
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
        UICompiler(output_dir=tmp_path, endpoints={}).compile(interp._evaluator)
    code = (tmp_path / "src" / "components" / "Label.tsx").read_text()
    assert "function LabelScreen()" in code and "export { LabelScreen as Label }" in code


def test_accordion_items_keep_their_titles(tmp_path):
    """accordion_item "Question" names the section on the web and on phones (it showed "Item 1")."""
    from mcn.fullstack.flutter_compiler import FlutterCompiler
    src = ('component Faq\n    render\n        accordion\n            accordion_item "Can I cancel?"\n'
           '                p "Yes, any time."\n\napp A\n    nav "Faq" Faq\n')
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
        UICompiler(output_dir=tmp_path / "web", endpoints={}).compile(interp._evaluator)
        FlutterCompiler({}).compile(interp._evaluator, tmp_path / "mobile", "a")
    web = (tmp_path / "web" / "src" / "components" / "Faq.tsx").read_text()
    assert re.search(r'<AccordionTrigger>\{?"?Can I cancel\?"?\}?</AccordionTrigger>', web), web
    phone = (tmp_path / "mobile" / "lib" / "screens" / "faq.dart").read_text()
    assert "Can I cancel?" in phone and "Yes, any time." in phone


def test_icons_match_on_web_and_mobile():
    """Every web kit icon has a Flutter equivalent, so a name never shows a blank circle on phones."""
    names = re.findall(r'"([A-Za-z0-9]+)":\[\[', (ROOT / "mcn/ui-kit/react/src/components/ui/icons-data.ts").read_text())
    dart = (ROOT / "mcn/fullstack/flutter_runtime.dart").read_text()
    phone = set(re.findall(r"'([a-z0-9]+)': LucideIcons\.", dart))
    assert {"Footprints", "HeartPulse", "Dumbbell"} <= set(names)
    assert not [n for n in names if n.lower() not in phone]


LANDING = """
component Landing
    state email = ""

    on join
        notify("Thanks", "success")

    on pick
        notify(item.title, "info")

    render
        navbar "Pulse" logo="Activity" links=["Features", "Pricing"] cta="Get the app" cta_link="#join"
        hero "Train smarter." eyebrow="New" subtitle="A plan that adapts." primary="Get the app" on_primary=join secondary="Pricing" secondary_link="#pricing"
            progress_ring value=76 label="Move" color="rose"
        feature_grid "Features" id="features"
            feature "Adaptive plans" icon="Sparkles" description="Rebuilds itself."
        pricing "Pricing" id="pricing"
            plan "Plus" price="$8" period="/month" features=["Coach", "Plans"] cta="Try it" highlight
        testimonials "Reviews"
            testimonial "Love it." author="Priya Shah" role="Runner"
        logo_cloud "Trusted by" names=["Acme", "Globex"]
        faq "Questions"
            question "Can I cancel?" answer="Any time."
        carousel "Up next"
            for w in [{title: "Run"}, {title: "Swim"}]
                list_item {w.title} subtitle="30 min" icon="Footprints" item=w on_click=pick
        avatar "Maya Patel" size=48 online
        cta_band "Ready?" id="join" cta="Join" on_click=join
        site_footer "Pulse" text="(c) 2026" links=["Features"]

app Site
    title "Pulse"
    brand "violet"
    layout
        page
            Landing
"""


def _compile_landing(tmp_path):
    from mcn.fullstack.flutter_compiler import FlutterCompiler
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(LANDING, quiet=True)
        UICompiler(output_dir=tmp_path / "web", endpoints={}).compile(interp._evaluator)
        FlutterCompiler({}).compile(interp._evaluator, tmp_path / "mobile", "a")
    return interp


def test_page_layout_and_brand_are_parsed():
    prog = Parser(Lexer(LANDING).tokenize()).parse()
    app = next(s for s in prog.body if type(s).__name__ == "AppDecl")
    assert app.brand == "violet" and app.layout.page and app.layout.main == ["Landing"]


def test_landing_sections_compile_to_kit_components(tmp_path):
    _compile_landing(tmp_path)
    src = tmp_path / "web" / "src"
    page = (src / "components" / "Landing.tsx").read_text()
    for tag in ("Navbar", "Hero", "FeatureGrid", "Feature", "Pricing", "Plan", "Testimonials", "Testimonial",
                "LogoCloud", "Faq", "Question", "Carousel", "ListItem", "PersonAvatar", "CtaBand", "SiteFooter", "ProgressRing"):
        assert f"<{tag}" in page, tag
    assert 'from "@/components/ui/landing"' in page and 'from "@/components/ui/design"' in page
    assert 'ctaLink="#join"' in page or 'ctaLink={"#join"}' in page          # snake_case attributes become camelCase props
    assert re.search(r"<Plan [^>]*highlight", page)                            # a bare flag is a boolean prop
    assert re.search(r"onPrimary=\{\(\) => join\(\)\}", page)          # on_* calls the `on` handler
    assert re.search(r"onClick=\{\(\) => pick\(w\)\}", page)           # item= is the value the handler gets
    assert re.search(r'<PersonAvatar name=\{?"Maya Patel"', page)              # an avatar's text is its name
    app = (src / "App.tsx").read_text()
    assert "<SitePage>" in app and "AppShell" not in app                       # a page has no app frame
    css = (src / "globals.css").read_text()
    assert brand_colors("violet")["light"]["--primary"] in css


def test_landing_sections_compile_to_native_widgets(tmp_path):
    _compile_landing(tmp_path)
    screen = (tmp_path / "mobile" / "lib" / "screens" / "landing.dart").read_text()
    for widget in ("MCNNavbar(", "MCNHero(", "MCNFeatureGrid(", "MCNPlan(", "MCNTestimonial(", "MCNLogoCloud(",
                   "MCNFaq(", "MCNQuestion(", "MCNCarousel(", "MCNListItem(", "MCNAvatar(", "MCNCtaBand(",
                   "MCNSiteFooter(", "MCNProgressRing("):
        assert widget in screen, widget
    assert "highlight: true" in screen and "onClick: () => _onPick(w)" in screen and "onPrimary: () => _onJoin()" in screen
    main = (tmp_path / "mobile" / "lib" / "main.dart").read_text()
    assert "brand: '#7c3aed'" in main and "page: true" in main
    runtime = (ROOT / "mcn/fullstack/flutter_runtime.dart").read_text()
    from mcn.fullstack.flutter_compiler import _DESIGN as FLUTTER
    for tag, (widget, params) in FLUTTER.items():          # every parameter the compiler passes exists on the widget
        assert f"class {widget} " in runtime, widget
        ctor = re.search(rf"const {widget}\(\{{([^}}]*)\}}\)", runtime).group(1)
        for p in params:
            assert f"this.{p}" in ctor, (widget, p)


def test_brand_colors():
    assert brand_colors("#7c3aed")["light"]["--primary"] == brand_colors("violet")["light"]["--primary"]
    assert brand_colors("#fde047")["light"]["--primary-foreground"] != "0 0% 100%"   # dark text on a light brand
    assert brand_colors("not a color") is None
