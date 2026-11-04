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
from mcn.core_engine.ui_compiler import UICompiler, _SHADCN, _KIT_DIR

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
    assert "onSend={async (message: string, history: any[]) => api.post('/ask', { message, history })}" in deals
    assert "onMove={async (item: any, to: string) => api.post('/move_deal', { id: item.id, stage: to, item })}" in deals
    # `on delete` is a handler (delete is reserved in JavaScript) that receives the row
    assert "onDelete={(row: any) => onDelete(row)}" in deals
    assert "const onDelete = useCallback(async (e?: any)" in deals and "const row: any = e" in deals


def test_endpoint_calls_use_backend_parameter_names_and_await():
    from mcn.core_engine.ui_compiler import _expr_to_ts
    UICompiler(output_dir=Path("."), endpoints=ENDPOINTS)
    expr = Parser(Lexer('var x = add_note(7, "hello").data').tokenize()).parse().body[0].value
    assert _expr_to_ts(expr) == "(await api.post('/add_note', {deal_id: 7, text: \"hello\"})).data"


def test_state_reads_after_assignment_see_the_new_value(compiled):
    deals = (compiled / "components" / "Deals.tsx").read_text()
    m = re.search(r"const (_stats\d+) = \(await api.post\('/deal_stats', \{\}\)\).data", deals)
    assert m, deals
    assert f"if (({m.group(1)}.open > 0))" in deals


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
