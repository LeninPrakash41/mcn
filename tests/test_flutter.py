"""
`mcn build --target flutter`: the same MCN UI source compiles to a Flutter app.

The Flutter SDK isn't available in CI, so these tests check the generated
project's structure, the AST → widget mapping, and that every Dart file is
lexically well formed (strings closed, brackets balanced).
"""

from pathlib import Path

import pytest

from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.fullstack.flutter_app import FlutterAppCompiler, FlutterCompileError, dstr

ROOT = Path(__file__).resolve().parents[1]

SRC = '''
auth
    roles admin, sales

contract Company
    name: str
    city: str?

contract Lead
    name: str
    stage: choice("new", "won") = "new"
    company: ref Company?
    commission: float? read admin write admin
    proposal: file?

component Leads
    render
        crud_table Lead columns=["name", "stage", "company"] title="My leads"

component Activity
    render
        audit_log

component Board
    state items = []
    state query = ""
    state loading = true
    on load
        items = fetch_leads(query)
        loading = false
    on remove(id)
        if confirm("Delete it?")
            delete_lead(id)
            toast("Deleted {id}")
    render
        h1 "Board"
        input bind=query placeholder="Search…"
        button "Search" on_click=load
        if loading
            p "Loading…"
        else
            div grid_cols=2
                for i, lead in items
                    card
                        card_header "{lead.name}"
                        badge "{lead.stage}"
                        button "Remove" variant="outline" on_click=remove(lead.id)
                empty
                    alert "No leads yet"

app Sales
    title "Sales Desk"
    layout
        sidebar
            nav "Board" icon="layout-dashboard" → Board
            nav "Leads" icon="users" → Leads
            nav "Activity" icon="history" → Activity allow admin
'''


def dart_check(code: str) -> None:
    """Strings are closed and (), [], {} balance — a lexical sanity check for Dart."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []          # brackets and string-interpolation markers
    i, n = 0, len(code)

    def read_string(i):
        quote = code[i]
        triple = code[i:i + 3] == quote * 3
        i += 3 if triple else 1
        while i < n:
            c = code[i]
            if c == "\\":
                i += 2
                continue
            if triple and code[i:i + 3] == quote * 3:
                return i + 3
            if not triple and c == quote:
                return i + 1
            if not triple and c == "\n":
                raise AssertionError(f"unterminated string at {i}: {code[i-40:i]!r}")
            if code[i:i + 2] == "${":
                depth, i = 1, i + 2
                start = i
                while depth:
                    if i >= n:
                        raise AssertionError("unterminated ${")
                    ch = code[i]
                    if ch in "'\"":
                        i = read_string(i)
                        continue
                    depth += ch == "{"
                    depth -= ch == "}"
                    i += 1
                check_brackets(code[start:i - 1])
                continue
            i += 1
        raise AssertionError("unterminated string")

    def check_brackets(text):
        dart_check(text)

    while i < n:
        c = code[i]
        if code[i:i + 2] == "//":
            i = code.find("\n", i)
            i = n if i < 0 else i
            continue
        if c in "'\"":
            i = read_string(i)
            continue
        if c in "([{":
            stack.append(c)
        elif c in ")]}":
            assert stack and stack[-1] == pairs[c], f"unbalanced {c!r} near {code[max(0, i-60):i+1]!r}"
            stack.pop()
        i += 1
    assert not stack, f"unclosed {stack}"


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interp = MCNInterpreter()
    interp.execute(SRC, quiet=True)
    out = tmp_path / "mobile"
    FlutterAppCompiler(out, project_name="Sales").compile(interp._evaluator)
    return out


def test_project_layout(project):
    for rel in ["pubspec.yaml", "README.md", ".gitignore", "lib/main.dart", "lib/models.dart",
                "lib/mcn/api.dart", "lib/mcn/auth.dart", "lib/mcn/crud_screen.dart",
                "lib/mcn/audit_screen.dart", "lib/mcn/widgets.dart", "lib/mcn/models.dart",
                "lib/screens/leads.dart", "lib/screens/activity.dart", "lib/screens/board.dart"]:
        assert (project / rel).exists(), rel
    pubspec = (project / "pubspec.yaml").read_text()
    assert "name: sales" in pubspec and "http: ^" in pubspec and "file_picker:" in pubspec


def test_all_dart_is_well_formed(project):
    files = list(project.rglob("*.dart"))
    assert len(files) >= 10
    for f in files:
        try:
            dart_check(f.read_text())
        except AssertionError as exc:
            raise AssertionError(f"{f.relative_to(project)}: {exc}")


def test_models_from_contracts(project):
    models = (project / "lib" / "models.dart").read_text()
    assert "const leadResource = Resource(" in models
    assert "'list': '/list_leads'" in models and "'approve': '/approve_lead'" in models
    assert "choices: ['new', 'won']" in models and "defaultValue: 'new'" in models
    assert ("ref: RefInfo(resource: 'Company', label: 'Company', list: '/list_companies', "
            "labelField: 'name')") in models
    assert "readRoles: ['admin'], writeRoles: ['admin']" in models
    assert "type: 'file'" in models
    # Company is only referenced, not shown in a crud_table — it isn't a screen resource
    assert "companyResource" not in models


def test_crud_table_and_audit_log_screens(project):
    leads = (project / "lib" / "screens" / "leads.dart").read_text()
    assert ("CrudScreen(resource: leadResource, columns: const ['name', 'stage', 'company'], "
            "title: 'My leads')") in leads
    assert "import '../mcn/api.dart';" not in leads          # no unused imports
    activity = (project / "lib" / "screens" / "activity.dart").read_text()
    assert "const AuditScreen()" in activity


def test_render_tree_state_and_handlers(project):
    board = (project / "lib" / "screens" / "board.dart").read_text()
    assert "dynamic items = <dynamic>[];" in board
    assert "final _queryCtrl = TextEditingController();" in board
    assert "controller: _queryCtrl" in board and "onChanged: (v) => setState(() => query = v)" in board
    # on load → initState + backend call through the API client
    assert "_onLoad();" in board and "items = await api.invoke('fetch_leads', [query]);" in board
    # handler params, confirm, toast with interpolation
    assert "Future<void> _onRemove(dynamic id) async" in board
    assert "if (truthy(await mcnConfirm(context, 'Delete it?')))" in board
    assert "await api.invoke('delete_lead', [id]);" in board
    assert "if (mounted) showToast(context, 'Deleted ${mcnStr(id)}')" in board
    # if / else, for with index, empty
    assert "if (truthy(loading)) ...[" in board and "] else ...[" in board
    assert "if (mcnList(items).isEmpty) ...[McnAlert('No leads yet')]" in board
    assert "for (final (_, lead) in mcnList(items).indexed) ...[" in board
    assert "Text(mcnStr(mcnGet(lead, 'name')), style: theme.textTheme.titleMedium)" in board
    assert "OutlinedButton(onPressed: () { _onRemove(mcnGet(lead, 'id')); }" in board
    assert "ResponsiveGrid(columns: 2" in board


def test_shell_navigation_and_auth(project):
    main = (project / "lib" / "main.dart").read_text()
    assert "AuthState(enabled: true)" in main
    assert "AuthGate(title: 'Sales Desk', child: Shell())" in main
    assert "_NavItem('Board', Icons.dashboard_outlined, [], (_) => const BoardScreen())," in main
    assert "_NavItem('Activity', Icons.history, ['admin'], (_) => const ActivityScreen())," in main
    assert "auth.hasRole(i.roles)" in main
    for screen in ("board", "leads", "activity"):
        assert f"import 'screens/{screen}.dart';" in main


def test_errors_point_at_the_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interp = MCNInterpreter()
    interp.execute("component Bad\n    render\n        crud_table Nope\n", quiet=True)
    with pytest.raises(FlutterCompileError, match=r"\[3:\d+\].*no contract named 'Nope'"):
        FlutterAppCompiler(tmp_path / "m").compile(interp._evaluator)


def test_dart_string_escaping():
    assert dstr("it's $5\n") == r"'it\'s \$5\n'"


def test_crm_example_builds_to_flutter(tmp_path, monkeypatch):
    from mcn.core_engine.mcn_cli import _cmd_build
    monkeypatch.chdir(ROOT / "examples" / "crm_app")
    out = tmp_path / "crm_mobile"
    assert _cmd_build("app.mcn", str(out), "flutter") == 0
    screens = {p.stem for p in (out / "lib" / "screens").glob("*.dart")}
    assert {"dashboard", "leads", "companies", "follow_ups", "quotes", "users", "activity"} <= screens
    for f in out.rglob("*.dart"):
        dart_check(f.read_text())
    main = (out / "lib" / "main.dart").read_text()
    assert "NavigationDrawer" in main       # 7 screens → drawer
