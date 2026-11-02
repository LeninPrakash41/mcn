"""
Flutter target for `mcn build`:

    mcn build app.mcn --target flutter --out mobile

Compiles the same MCN UI source as the React build (components, render trees,
`crud_table`, `audit_log`, `auth`, the app's sidebar navigation) into a Flutter
project. Most of the Dart is a fixed, readable runtime (lib/mcn/*.dart); the
generated parts are lib/models.dart, lib/screens/*.dart and lib/main.dart.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set

from mcn.core_engine import ast_nodes as ast
from mcn.core_engine.crud import crud_names, display_field, plural

RUNTIME_DIR = Path(__file__).parent / "flutter_runtime"
RUNTIME_FILES = ("api.dart", "auth.dart", "models.dart", "widgets.dart",
                 "crud_screen.dart", "audit_screen.dart")

# lucide (web) icon names → Material icons
_ICONS = {
    "layout-dashboard": "dashboard_outlined", "dashboard": "dashboard_outlined",
    "users": "people_outline", "user": "person_outline", "building-2": "business_outlined",
    "building": "business_outlined", "calendar-check": "event_available_outlined",
    "calendar": "calendar_today_outlined", "calendarclock": "schedule", "calendar-clock": "schedule",
    "file-text": "description_outlined", "file": "insert_drive_file_outlined",
    "shield": "admin_panel_settings_outlined", "history": "history", "settings": "settings_outlined",
    "home": "home_outlined", "rocket": "rocket_launch_outlined", "message-square": "chat_outlined",
    "mail": "mail_outline", "inbox": "inbox_outlined", "bar-chart": "bar_chart",
    "trendingup": "trending_up", "trending-up": "trending_up", "trophy": "emoji_events_outlined",
    "dollarsign": "attach_money", "dollar-sign": "attach_money", "shopping-cart": "shopping_cart_outlined",
    "package": "inventory_2_outlined", "truck": "local_shipping_outlined", "clipboard": "assignment_outlined",
    "check": "check_circle_outline", "list": "list_alt", "listchecks": "checklist", "list-checks": "checklist",
    "briefcase": "work_outline", "credit-card": "credit_card", "wallet": "account_balance_wallet_outlined",
    "heart": "favorite_border", "star": "star_border", "bell": "notifications_none",
}

_STAT_COLORS = {"blue": "0xFF2563EB", "green": "0xFF16A34A", "red": "0xFFDC2626",
                "amber": "0xFFD97706", "purple": "0xFF9333EA"}


def dstr(s) -> str:
    """Python string → Dart single-quoted string literal."""
    s = str(s)
    s = (s.replace("\\", "\\\\").replace("'", "\\'").replace("$", "\\$")
          .replace("\n", "\\n").replace("\r", "").replace("\t", "\\t"))
    return f"'{s}'"


def _pascal(name: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[_\-\s]+", name) if w)


def _lower_camel(name: str) -> str:
    p = _pascal(name)
    return p[:1].lower() + p[1:]


def _snake(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return re.sub(r"[^a-z0-9_]", "_", s.lower())


def _field_key(label: str) -> str:
    key = re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").lower()
    return key or label


def _icon(name: str, default: str = "circle_outlined") -> str:
    key = (name or "").strip().lower()
    return "Icons." + _ICONS.get(key, _ICONS.get(key.replace("-", ""), default))


_DART_RESERVED = {"abstract", "as", "assert", "async", "await", "break", "case", "catch", "class",
                  "const", "continue", "default", "do", "dynamic", "else", "enum", "export",
                  "extends", "external", "factory", "false", "final", "finally", "for", "get",
                  "if", "implements", "import", "in", "is", "late", "library", "new", "null",
                  "operator", "part", "required", "rethrow", "return", "set", "static", "super",
                  "switch", "sync", "this", "throw", "true", "try", "typedef", "var", "void",
                  "while", "with", "yield", "context", "widget", "mounted"}


def _var(name: str) -> str:
    """MCN variable name → safe Dart identifier."""
    return f"{name}_" if name in _DART_RESERVED else name


class FlutterCompileError(Exception):
    """A problem in the UI source for the Flutter target (has [line:col])."""


# ── project compiler ─────────────────────────────────────────────────────────

class FlutterAppCompiler:
    def __init__(self, output_dir: Path, project_name: str = "mcn_app"):
        self.out = Path(output_dir)
        self.project_name = re.sub(r"[^a-z0-9_]", "_", _snake(project_name)).strip("_") or "mcn_app"
        if self.project_name[0].isdigit():
            self.project_name = "app_" + self.project_name

    def compile(self, evaluator) -> List[Path]:
        from mcn.core_engine.runtime_types import MCNContract
        written: List[Path] = []
        lib = self.out / "lib"
        (lib / "mcn").mkdir(parents=True, exist_ok=True)
        (lib / "screens").mkdir(parents=True, exist_ok=True)

        self.app = evaluator.app_decl
        self.auth = getattr(evaluator, "auth_config", None)
        self.contracts = {n: v for n, v in evaluator.globals.as_dict.items()
                          if isinstance(v, MCNContract)}
        self.used_resources: Dict[str, object] = {}
        components: Dict[str, ast.ComponentDecl] = evaluator.components

        def write(path: Path, text: str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(path)
            print(f"  write  {path.relative_to(self.out.parent)}")

        for name in RUNTIME_FILES:
            write(lib / "mcn" / name, (RUNTIME_DIR / name).read_text(encoding="utf-8"))

        screens = {}
        for name, comp in components.items():
            code = ComponentCompiler(self, comp).compile()
            fname = _snake(name)
            write(lib / "screens" / f"{fname}.dart", code)
            screens[name] = fname

        write(lib / "models.dart", self._models())
        write(lib / "main.dart", self._main(components, screens))
        write(self.out / "pubspec.yaml", self._pubspec())
        write(self.out / "README.md", self._readme())
        write(self.out / ".gitignore", ".dart_tool/\nbuild/\n.flutter-plugins*\n.packages\n"
                                       "pubspec.lock\nandroid/\nios/\n")
        return written

    # ── models.dart ──────────────────────────────────────────────────────────

    def resource_var(self, contract_name: str) -> str:
        return f"{_lower_camel(contract_name)}Resource"

    def _models(self) -> str:
        lines = ["// Data models — generated by `mcn build --target flutter` from your MCN contracts.",
                 "// Edit the contract in your .mcn file and rebuild; don't edit this file.",
                 "import 'mcn/models.dart';", ""]
        for name, contract in self.used_resources.items():
            n = crud_names(name)
            endpoints = {k: f"/{n[k]}" for k in ("list", "get", "create", "update", "delete")}
            endpoints.update(approve=f"/approve_{n['singular']}", reject=f"/reject_{n['singular']}")
            ep = ", ".join(f"{dstr(k)}: {dstr(v)}" for k, v in endpoints.items())
            fields = []
            for s in contract.specs:
                args = [f"name: {dstr(s.name)}", f"label: {dstr(_label(s.name))}",
                        f"type: {dstr(s.type)}"]
                if s.required:
                    args.append("required: true")
                if s.choices:
                    args.append("choices: [" + ", ".join(dstr(c) for c in s.choices) + "]")
                    args.append(f"pluralLabel: {dstr(_label(plural(s.name)))}")
                if s.has_default and s.default is not None:
                    args.append(f"defaultValue: {_dart_const(s.default)}")
                if s.read_roles:
                    args.append("readRoles: [" + ", ".join(dstr(r) for r in s.read_roles) + "]")
                if s.write_roles:
                    args.append("writeRoles: [" + ", ".join(dstr(r) for r in s.write_roles) + "]")
                if s.type == "ref":
                    target = self.contracts.get(s.ref)
                    lf = display_field(target.specs) if target is not None else None
                    rn = crud_names(s.ref)
                    args.append(f"ref: RefInfo(resource: {dstr(s.ref)}, label: {dstr(_label(rn['singular']))}, "
                                f"list: {dstr('/' + rn['list'])}"
                                + (f", labelField: {dstr(lf)}" if lf else "") + ")")
                fields.append("    Field(" + ", ".join(args) + "),")
            lines += [
                f"const {self.resource_var(name)} = Resource(",
                f"  name: {dstr(name)},",
                f"  label: {dstr(_label(n['singular']))},",
                f"  plural: {dstr(_label(n['plural']))},",
                f"  endpoints: {{{ep}}},",
                "  fields: [",
                *fields,
                "  ],",
                ");",
                "",
            ]
        return "\n".join(lines)

    # ── main.dart ────────────────────────────────────────────────────────────

    def _seed_color(self) -> str:
        from mcn.core_engine.ui_compiler import _THEMES
        from mcn.core_engine.ui_pwa import hsl_to_hex
        theme = self.app.theme if self.app else "default"
        primary = _THEMES.get(theme, _THEMES.get("default", {})).get("--primary", "221.2 83.2% 53.3%")
        hexc = hsl_to_hex(primary).lstrip("#")
        # very dark seeds (e.g. slate) give a grey palette; nudge toward blue
        if hexc in ("0f172a", "020817"):
            hexc = "334155"
        return f"Color(0xFF{hexc.upper()})"

    def _main(self, components: Dict[str, ast.ComponentDecl], screens: Dict[str, str]) -> str:
        title = (self.app.title if self.app and self.app.title else "MCN App")
        auth_on = "true" if self.auth is not None else "false"
        imports = [f"import 'screens/{f}.dart';" for f in screens.values()]
        nav = self.app.layout.sidebar if (self.app and self.app.layout) else []
        if not nav and self.app and self.app.layout and self.app.layout.tabs:
            nav = [ast.NavItem(label=t.label, component=t.component) for t in self.app.layout.tabs]
        if not nav:
            nav = [ast.NavItem(label=_label(_snake(n)), component=n) for n in components]
        items = []
        for n in nav:
            comp = n.component or _pascal(n.label)
            if comp not in components:
                raise FlutterCompileError(f"[{n.line}:{n.col}] nav \"{n.label}\": no component named '{comp}'")
            roles = ", ".join(dstr(r) for r in n.allow)
            items.append(f"    _NavItem({dstr(n.label)}, {_icon(n.icon or n.label.lower())}, "
                         f"[{roles}], (_) => const {comp}Screen()),")
        return f"""// App shell — generated by `mcn build --target flutter`.
import 'package:flutter/material.dart';

import 'mcn/auth.dart';
{chr(10).join(imports)}

void main() {{
  runApp(const App());
}}

class App extends StatefulWidget {{
  const App({{super.key}});

  @override
  State<App> createState() => _AppState();
}}

class _AppState extends State<App> {{
  final _auth = AuthState(enabled: {auth_on});

  @override
  void initState() {{
    super.initState();
    _auth.init();
  }}

  @override
  Widget build(BuildContext context) {{
    const seed = {self._seed_color()};
    return AuthScope(
      auth: _auth,
      child: MaterialApp(
        title: {dstr(title)},
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true),
        darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark, useMaterial3: true),
        home: const AuthGate(title: {dstr(title)}, child: Shell()),
      ),
    );
  }}
}}

class _NavItem {{
  const _NavItem(this.label, this.icon, this.roles, this.builder);

  final String label;
  final IconData icon;
  final List<String> roles;
  final WidgetBuilder builder;
}}

class Shell extends StatefulWidget {{
  const Shell({{super.key}});

  @override
  State<Shell> createState() => _ShellState();
}}

class _ShellState extends State<Shell> {{
  int _index = 0;

  static final _items = <_NavItem>[
{chr(10).join(items)}
  ];

  @override
  Widget build(BuildContext context) {{
    final auth = AuthScope.of(context);
    final items = _items.where((i) => auth.hasRole(i.roles)).toList();
    final index = _index < items.length ? _index : 0;
    final current = items[index];
    final useBar = items.length >= 2 && items.length <= 5;
    final useDrawer = items.length > 5;
    final user = auth.user;
    return Scaffold(
      appBar: AppBar(
        title: Text(current.label),
        actions: [
          if (auth.enabled && user != null)
            PopupMenuButton<String>(
              tooltip: 'Account',
              icon: CircleAvatar(
                radius: 15,
                child: Text((user['name'] ?? '?').toString().substring(0, 1).toUpperCase()),
              ),
              onSelected: (v) {{
                if (v == 'logout') auth.logout();
              }},
              itemBuilder: (_) => [
                PopupMenuItem<String>(
                  enabled: false,
                  child: Text('${{user['name'] ?? ''}} · ${{user['role'] ?? ''}}\\n${{user['email'] ?? ''}}'),
                ),
                const PopupMenuItem<String>(value: 'logout', child: Text('Sign out')),
              ],
            ),
        ],
      ),
      drawer: useDrawer
          ? NavigationDrawer(
              selectedIndex: index,
              onDestinationSelected: (i) {{
                setState(() => _index = i);
                Navigator.of(context).pop();
              }},
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(28, 20, 16, 12),
                  child: Text({dstr(title)}, style: Theme.of(context).textTheme.titleMedium),
                ),
                for (final item in items)
                  NavigationDrawerDestination(icon: Icon(item.icon), label: Text(item.label)),
              ],
            )
          : null,
      body: KeyedSubtree(key: ValueKey(current.label), child: current.builder(context)),
      bottomNavigationBar: useBar
          ? NavigationBar(
              selectedIndex: index,
              onDestinationSelected: (i) => setState(() => _index = i),
              destinations: [
                for (final item in items) NavigationDestination(icon: Icon(item.icon), label: item.label),
              ],
            )
          : null,
    );
  }}
}}
"""

    def _pubspec(self) -> str:
        title = (self.app.title if self.app and self.app.title else "MCN App")
        return f"""name: {self.project_name}
description: {json.dumps(title + " — generated by mcn build --target flutter")}
publish_to: none
version: 1.0.0+1

environment:
  sdk: ^3.11.0
  flutter: ">=3.41.0"

dependencies:
  flutter:
    sdk: flutter
  http: ^1.6.0
  shared_preferences: ^2.5.6
  file_picker: ^13.3.2
  url_launcher: ^6.3.3

flutter:
  uses-material-design: true
"""

    def _readme(self) -> str:
        title = (self.app.title if self.app and self.app.title else "MCN App")
        return f"""# {title} (Flutter)

Generated by `mcn build --target flutter`. Rebuilding overwrites `lib/` — change the
`.mcn` source instead.

## Run it

```bash
flutter create --platforms=android,ios .
flutter pub get
flutter run --dart-define=MCN_API_URL=http://10.0.2.2:8080
```

`flutter create .` adds the `android/` and `ios/` folders around the generated `lib/`.
`MCN_API_URL` is the address of your MCN backend (`mcn serve`): `10.0.2.2` is your
computer as seen from the Android emulator; use your computer's LAN address on a real
phone, or an `https://` address in production.

**Plain `http://` during development:** Android blocks it by default. Add
`android:usesCleartextTraffic="true"` to the `<application>` tag in
`android/app/src/main/AndroidManifest.xml` (development only), or use HTTPS.
On iOS, allow local networking in `ios/Runner/Info.plist` (`NSAppTransportSecurity` →
`NSAllowsLocalNetworking`).

## What's inside

| File | |
|---|---|
| `lib/main.dart` | App shell: theme, sign-in gate, navigation (bottom bar, or a drawer for more than 5 screens) |
| `lib/models.dart` | Your contracts as `Resource`s |
| `lib/screens/*.dart` | One screen per MCN component |
| `lib/mcn/*.dart` | Runtime: API client, sign-in, list/form screens, activity log, widgets |
"""


def _label(name: str) -> str:
    text = name.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _dart_const(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if v is None:
        return "null"
    return dstr(v)


# ── component compiler ───────────────────────────────────────────────────────

_WIDGET_HELPERS = re.compile(r"\b(truthy|mcnGet|mcnIndex|mcnAdd|mcnStr|mcnList|mcnConfirm|formatNumber|"
                             r"humanize|badgeColor|McnBadge|StatCard|McnAlert|ResponsiveGrid|McnTable|showToast)\b")


def _imports_for(code: str, extra: Set[str]) -> List[str]:
    """Only the imports the generated code uses (keeps `flutter analyze` clean)."""
    imports = set(extra)
    if "api." in code:
        imports.add("import '../mcn/api.dart';")
    if _WIDGET_HELPERS.search(code):
        imports.add("import '../mcn/widgets.dart';")
    pkg = sorted(i for i in imports if "package:" in i)
    rel = sorted(i for i in imports if "package:" not in i)
    return pkg + ([""] if pkg and rel else []) + rel

_INTERP_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\]|\["[^"]*"\])*)\}')


class ComponentCompiler:
    def __init__(self, project: FlutterAppCompiler, comp: ast.ComponentDecl):
        self.p = project
        self.comp = comp
        self.states = [s.name for s in comp.states]
        self.handlers = {h.event: h for h in comp.handlers}
        self.bound: Set[str] = set()           # state vars bound to text inputs
        self.scope: Set[str] = set(self.states)
        self.form_handler: Optional[str] = None
        self.uses_controllers = False

    # ── entry ─────────────────────────────────────────────────────────────────

    def compile(self) -> str:
        name = self.comp.name
        roots = self.comp.render.elements if self.comp.render else []
        imports = {"import 'package:flutter/material.dart';"}
        # A screen that is just a crud_table / audit_log
        if len(roots) == 1 and isinstance(roots[0], ast.UIElement) and roots[0].tag in ("crud_table", "audit_log") \
                and not self.comp.states and not self.comp.handlers:
            body = self._special(roots[0], imports)
            return "\n".join(["// Generated by `mcn build --target flutter` from component " + name + ".",
                              *_imports_for(body, imports), "",
                              f"class {name}Screen extends StatelessWidget {{",
                              f"  const {name}Screen({{super.key}});", "",
                              "  @override",
                              "  Widget build(BuildContext context) {",
                              f"    return {body};",
                              "  }", "}", ""])

        self._collect_bound(roots)
        build_children = self.children(roots, imports)
        fields = [f"  dynamic {_var(s.name)} = {self.expr(s.value, render=False)};" for s in self.comp.states]
        ctrls = [f"  final _{s}Ctrl = TextEditingController();" for s in sorted(self.bound)]
        init_lines = [f"    _{s}Ctrl.text = mcnStr({_var(s)});" for s in sorted(self.bound)]
        if "load" in self.handlers:
            init_lines.append("    _onLoad();")
        methods = []
        for event, h in self.handlers.items():
            methods.append(self._handler(event, h))
        dispose = ""
        if self.bound:
            dispose = ("  @override\n  void dispose() {\n"
                       + "".join(f"    _{s}Ctrl.dispose();\n" for s in sorted(self.bound))
                       + "    super.dispose();\n  }\n")
        init = ""
        if init_lines:
            init = "  @override\n  void initState() {\n    super.initState();\n" + "\n".join(init_lines) + "\n  }\n"
        body = ",\n".join("          " + c for c in build_children)
        methods_code = "\n".join(methods)
        refresh = ("  void _refresh() {\n    if (mounted) setState(() {});\n  }\n\n"
                   if "_refresh()" in methods_code else "")
        theme = "    final theme = Theme.of(context);\n" if "theme." in body else ""
        all_code = body + methods_code + "\n".join(fields)
        return f"""// Generated by `mcn build --target flutter` from component {name}.
{chr(10).join(_imports_for(all_code, imports))}

class {name}Screen extends StatefulWidget {{
  const {name}Screen({{super.key}});

  @override
  State<{name}Screen> createState() => _{name}ScreenState();
}}

class _{name}ScreenState extends State<{name}Screen> {{
{chr(10).join(fields + ctrls)}

{init}{dispose}
{refresh}{methods_code}
  @override
  Widget build(BuildContext context) {{
{theme}    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 12,
        children: [
{body}
        ],
      ),
    );
  }}
}}
"""

    # ── handlers ──────────────────────────────────────────────────────────────

    def _handler_name(self, event: str) -> str:
        return "_on" + _pascal(event)

    def _handler(self, event: str, h: ast.OnHandler) -> str:
        from mcn.core_engine.ui_compiler import _vars_needing_hoist
        saved = set(self.scope)
        self.scope |= set(h.params)
        hoisted = _vars_needing_hoist(h.body)
        self.scope |= hoisted
        lines = []
        if hoisted:
            lines.append("      dynamic " + ", ".join(_var(n) for n in sorted(hoisted)) + ";")
        lines += self.stmts(h.body, 6, hoisted)
        self.scope = saved
        params = ", ".join(f"dynamic {_var(p)}" for p in h.params)
        body = "\n".join(lines) if lines else "      // (empty)"
        return (f"  Future<void> {self._handler_name(event)}({params}) async {{\n"
                "    try {\n"
                f"{body}\n"
                "    } catch (e) {\n"
                "      if (mounted) showToast(context, e);\n"
                "    }\n"
                "  }\n")

    def stmts(self, body: List[ast.Stmt], indent: int, hoisted: Set[str]) -> List[str]:
        pad = " " * indent
        out: List[str] = []
        for st in body:
            if isinstance(st, ast.VarDecl):
                self.scope.add(st.name)
                val = self.expr(st.value, render=False)
                out.append(f"{pad}{_var(st.name)} = {val};" if st.name in hoisted
                           else f"{pad}var {_var(st.name)} = {val};")
            elif isinstance(st, ast.AssignStmt):
                out.append(f"{pad}{_var(st.name)} = {self.expr(st.value, render=False)};")
                if st.name in self.states:
                    if st.name in self.bound:
                        out.append(f"{pad}_{st.name}Ctrl.text = mcnStr({_var(st.name)});")
                    out.append(f"{pad}_refresh();")
            elif isinstance(st, ast.CompoundAssignStmt):
                cur, val = _var(st.name), self.expr(st.value, render=False)
                rhs = f"mcnAdd({cur}, {val})" if st.op == "+" else f"({cur} {st.op} {val})"
                out.append(f"{pad}{cur} = {rhs};")
                if st.name in self.states:
                    out.append(f"{pad}_refresh();")
            elif isinstance(st, ast.ExprStmt):
                code = self.expr(st.expression, render=False)
                # the screen may be gone after an await
                guard = "if (mounted) " if code.startswith("showToast(") else ""
                out.append(f"{pad}{guard}{code};")
            elif isinstance(st, ast.IfStmt):
                out.append(f"{pad}if (truthy({self.expr(st.condition, render=False)})) {{")
                out += self.stmts(st.then_body, indent + 2, hoisted)
                if st.else_body:
                    out.append(f"{pad}}} else {{")
                    out += self.stmts(st.else_body, indent + 2, hoisted)
                out.append(f"{pad}}}")
            elif isinstance(st, ast.ForStmt):
                self.scope.add(st.variable)
                out.append(f"{pad}for (final {_var(st.variable)} in mcnList({self.expr(st.iterable, render=False)})) {{")
                out += self.stmts(st.body, indent + 2, hoisted)
                out.append(f"{pad}}}")
            elif isinstance(st, ast.ReturnStmt):
                out.append(f"{pad}return;")
            else:
                out.append(f"{pad}// not supported on Flutter yet: {type(st).__name__}")
        return out

    # ── expressions ───────────────────────────────────────────────────────────

    def expr(self, e: Optional[ast.Expr], render: bool = True) -> str:
        if e is None:
            return "null"
        if isinstance(e, ast.Literal):
            v = e.value
            if isinstance(v, bool):
                return "true" if v else "false"
            if v is None:
                return "null"
            if isinstance(v, (int, float)):
                return repr(v)
            return self.string(str(v))
        if isinstance(e, ast.Variable):
            if e.name in ("true", "false", "null"):
                return e.name
            if e.name in self.scope:
                return _var(e.name)
            return f"null /* unknown: {e.name} */"
        if isinstance(e, ast.Property):
            return f"mcnGet({self.expr(e.object, render)}, {dstr(e.name)})"
        if isinstance(e, ast.Index):
            return f"mcnIndex({self.expr(e.object, render)}, {self.expr(e.index, render)})"
        if isinstance(e, ast.Binary):
            a, b, op = self.expr(e.left, render), self.expr(e.right, render), e.operator
            if op == "+":
                return f"mcnAdd({a}, {b})"
            if op == "and":
                return f"(truthy({a}) && truthy({b}))"
            if op == "or":
                return f"(truthy({a}) || truthy({b}))"
            return f"({a} {op} {b})"
        if isinstance(e, ast.Unary):
            inner = self.expr(e.operand, render)
            return f"!truthy({inner})" if e.operator == "not" else f"-({inner})"
        if isinstance(e, ast.TernaryExpr):
            return (f"(truthy({self.expr(e.condition, render)}) ? {self.expr(e.then_expr, render)}"
                    f" : {self.expr(e.else_expr, render)})")
        if isinstance(e, ast.Array):
            return "<dynamic>[" + ", ".join(self.expr(x, render) for x in e.elements) + "]"
        if isinstance(e, ast.MCNObject):
            pairs = []
            for k, v in e.properties:
                key = k.name if isinstance(k, ast.Variable) else (k.value if isinstance(k, ast.Literal) else "?")
                pairs.append(f"{dstr(key)}: {self.expr(v, render)}")
            return "<String, dynamic>{" + ", ".join(pairs) + "}"
        if isinstance(e, ast.Call) and isinstance(e.callee, ast.Variable):
            fn = e.callee.name
            args = [self.expr(a, render) for a in e.arguments]
            if fn == "toast" or fn == "alert":
                return f"showToast(context, {args[0] if args else dstr('')})"
            if fn == "log":
                return f"debugPrint(mcnStr({args[0] if args else dstr('')}))"
            if fn == "confirm":
                return f"await mcnConfirm(context, {args[0] if args else dstr('Are you sure?')})"
            if fn in self.handlers:
                return f"{self._handler_name(fn)}({', '.join(args)})"
            if render:
                return f"null /* {fn}() runs on the server — call it from an `on` handler */"
            return f"await api.invoke({dstr(fn)}, [{', '.join(args)}])"
        return f"null /* not supported on Flutter yet: {type(e).__name__} */"

    def string(self, value: str) -> str:
        """MCN string with {path} placeholders → Dart string with ${…} slots."""
        out, pos = [], 0
        for m in _INTERP_RE.finditer(value):
            path = m.group(1)
            root = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", path).group(0)
            if root not in self.scope:
                continue
            out.append(dstr(value[pos:m.start()])[1:-1])
            out.append("${mcnStr(" + self._path(path) + ")}")
            pos = m.end()
        out.append(dstr(value[pos:])[1:-1])
        joined = "".join(out)
        m = re.fullmatch(r"\$\{(mcnStr\((?:[^{}]|\{[^{}]*\})*\))\}", joined)
        if m:
            return m.group(1)
        return "'" + joined + "'"

    def _path(self, path: str) -> str:
        root = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", path).group(0)
        code = _var(root)
        for prop, idx, key in re.findall(r'\.([a-zA-Z_][a-zA-Z0-9_]*)|\[(\d+)\]|\["([^"]*)"\]', path[len(root):]):
            if prop:
                code = f"mcnGet({code}, {dstr(prop)})"
            elif idx:
                code = f"mcnIndex({code}, {idx})"
            else:
                code = f"mcnGet({code}, {dstr(key)})"
        return code

    def text(self, e: Optional[ast.Expr]) -> str:
        """Expression as display text."""
        if isinstance(e, ast.Literal) and isinstance(e.value, str):
            return self.string(e.value)
        return f"mcnStr({self.expr(e)})"

    # ── render tree ───────────────────────────────────────────────────────────

    def _collect_bound(self, nodes):
        for n in nodes:
            if isinstance(n, ast.UIElement) and n.tag in ("input", "textarea"):
                b = self._attr(n, "bind")
                if isinstance(b, ast.Variable) and b.name in self.states:
                    self.bound.add(b.name)
            self._collect_bound(getattr(n, "children", []))

    @staticmethod
    def _attr(el, key):
        a = next((a for a in el.attrs if a.key == key), None)
        return a.value if a is not None else None

    @staticmethod
    def _has(el, key) -> bool:
        return any(a.key == key for a in el.attrs)

    def children(self, nodes, imports) -> List[str]:
        """Render nodes → Dart collection elements (widgets, `if`, `for`)."""
        out: List[str] = []
        for n in nodes:
            if isinstance(n, ast.UIIf):
                out.append(self._if(n, imports))
            elif isinstance(n, ast.UIFor):
                out.append(self._for(n, imports, lambda body: self.children(body, imports)))
            else:
                show = self._attr(n, "show") if isinstance(n, ast.UIElement) else None
                w = self.widget(n, imports)
                out.append(f"if (truthy({self.expr(show)})) {w}" if show is not None else w)
        return out

    def _if(self, n: ast.UIIf, imports) -> str:
        then = ", ".join(self.children(n.then_children, imports))
        code = f"if (truthy({self.expr(n.condition)})) ...[{then}]"
        if len(n.else_children) == 1 and isinstance(n.else_children[0], ast.UIIf):
            code += " else " + self._if(n.else_children[0], imports)
        elif n.else_children:
            code += " else ...[" + ", ".join(self.children(n.else_children, imports)) + "]"
        return code

    def _for(self, n: ast.UIFor, imports, body_fn) -> str:
        items = f"mcnList({self.expr(n.iterable)})"
        saved = set(self.scope)
        self.scope |= {n.variable} | ({n.index_var} if n.index_var else set())
        body = ", ".join(body_fn(n.body))
        self.scope = saved
        idx = _var(n.index_var) if n.index_var else "_"
        if n.index_var and not re.search(rf"\b{re.escape(idx)}\b", body):
            idx = "_"
        head = (f"for (final ({idx}, {_var(n.variable)}) in {items}.indexed)"
                if n.index_var else f"for (final {_var(n.variable)} in {items})")
        loop = f"{head} ...[{body}]"
        if n.empty:
            empty = ", ".join(body_fn(n.empty))
            return f"if ({items}.isEmpty) ...[{empty}] else {loop}"
        return loop

    def _column(self, kids: List[str], spacing: int = 8) -> str:
        return ("Column(crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"spacing: {spacing}, children: [{', '.join(kids)}])")

    def _style(self, el, base: str) -> str:
        cls = self._attr(el, "class_name")
        cls = cls.value if isinstance(cls, ast.Literal) else ""
        style = base
        if "text-sm" in cls or "text-xs" in cls:
            style = "theme.textTheme.bodySmall"
        if "font-semibold" in cls or "font-medium" in cls or "font-bold" in cls:
            style = f"{style}?.copyWith(fontWeight: FontWeight.w600)"
        if "text-muted-foreground" in cls:
            style = f"{style}?.copyWith(color: theme.colorScheme.onSurfaceVariant)"
        return style

    def widget(self, el, imports) -> str:
        tag = el.tag
        text_attr = self._attr(el, "text")
        text = el.text if el.text is not None else text_attr
        kids = lambda: self.children(el.children, imports)

        if tag in ("crud_table", "audit_log"):
            return f"SizedBox(height: 560, child: {self._special(el, imports)})"
        if tag == "div":
            cols = self._attr(el, "grid_cols")
            if cols is not None:
                n = cols.value if isinstance(cols, ast.Literal) else 2
                return f"ResponsiveGrid(columns: {int(n)}, children: [{', '.join(kids())}])"
            return self._column(kids())
        if tag == "card":
            return ("Card(child: Padding(padding: const EdgeInsets.all(16), child: "
                    f"{self._column(kids())}))")
        if tag == "card_header":
            title = f"Text({self.text(text)}, style: theme.textTheme.titleMedium)" if text is not None else None
            parts = ([title] if title else []) + kids()
            return parts[0] if len(parts) == 1 else self._column(parts)
        if tag in ("card_content", "card_footer", "section", "article", "main", "header", "footer",
                   "nav", "scroll_area", "ul", "ol"):
            return self._column(kids())
        if tag == "form":
            saved = self.form_handler
            h = self._attr(el, "on_submit")
            if isinstance(h, ast.Variable) and h.name in self.handlers:
                self.form_handler = self._handler_name(h.name) + "()"
            col = self._column(kids(), 12)
            self.form_handler = saved
            return col
        if tag in ("h1", "h2", "h3", "h4", "p", "span", "text", "label", "li", "a"):
            base = {"h1": "theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)",
                    "h2": "theme.textTheme.titleLarge", "h3": "theme.textTheme.titleMedium",
                    "h4": "theme.textTheme.titleSmall"}.get(tag, "theme.textTheme.bodyMedium")
            if text is None and el.children:
                return self._column(kids())
            return f"Text({self.text(text)}, style: {self._style(el, base)})"
        if tag == "badge":
            return f"McnBadge({self.text(text)})"
        if tag == "button":
            label = f"Text({self.text(text)})" if text is not None else "const Text('OK')"
            action = self._action(self._attr(el, "on_click")) or (
                f"() {{ {self.form_handler}; }}" if self.form_handler else "() {}")
            variant = self._attr(el, "variant")
            v = variant.value if isinstance(variant, ast.Literal) else ""
            kind = {"outline": "OutlinedButton", "ghost": "TextButton", "link": "TextButton",
                    "secondary": "FilledButton.tonal"}.get(v, "FilledButton")
            return f"{kind}(onPressed: {action}, child: {label})"
        if tag in ("input", "textarea"):
            bind = self._attr(el, "bind")
            label = self._attr(el, "label")
            hint = self._attr(el, "placeholder")
            deco = ["border: const OutlineInputBorder()"]
            if label is not None:
                deco.append(f"labelText: {self.text(label)}")
            if hint is not None:
                deco.append(f"hintText: {self.text(hint)}")
            parts = [f"decoration: InputDecoration({', '.join(deco)})"]
            if tag == "textarea":
                parts.append("maxLines: 4")
            if isinstance(bind, ast.Variable) and bind.name in self.bound:
                parts.insert(0, f"controller: _{bind.name}Ctrl")
                parts.append(f"onChanged: (v) => setState(() => {_var(bind.name)} = v)")
            if self._attr(el, "type") is not None and isinstance(self._attr(el, "type"), ast.Literal) \
                    and self._attr(el, "type").value == "password":
                parts.append("obscureText: true")
            if self.form_handler and tag == "input":
                parts.append(f"onSubmitted: (_) {{ {self.form_handler}; }}")
            return f"TextField({', '.join(parts)})"
        if tag == "select":
            bind = self._attr(el, "bind")
            opts = self._attr(el, "options")
            label = self._attr(el, "label")
            change = self._attr(el, "on_change")
            items = []
            if isinstance(opts, ast.Array):
                for o in opts.elements:
                    items.append(f"DropdownMenuItem<String>(value: {self.text(o)}, child: Text(humanize({self.text(o)})))")
            var = _var(bind.name) if isinstance(bind, ast.Variable) else None
            on = "(v) {"
            if var:
                on += f" setState(() => {var} = v);"
            if isinstance(change, ast.Variable) and change.name in self.handlers:
                on += f" {self._handler_name(change.name)}();"
            on += " }"
            deco = f"InputDecoration(labelText: {self.text(label)}, border: const OutlineInputBorder())" \
                if label is not None else "const InputDecoration(border: OutlineInputBorder())"
            value = f"initialValue: {var} is String ? {var} as String : null, " if var else ""
            return (f"DropdownButtonFormField<String>({value}decoration: {deco}, "
                    f"items: [{', '.join(items)}], onChanged: {on})")
        if tag in ("checkbox", "switch"):
            bind = self._attr(el, "bind")
            label = self._attr(el, "label")
            var = _var(bind.name) if isinstance(bind, ast.Variable) else None
            return (f"SwitchListTile(contentPadding: EdgeInsets.zero, "
                    f"title: Text({self.text(label) if label is not None else self.text(text) if text is not None else dstr('')}), "
                    f"value: truthy({var or 'false'}), "
                    f"onChanged: (v) {{ {'setState(() => ' + var + ' = v);' if var else ''} }})")
        if tag in ("stat", "stat_card"):
            label = self._attr(el, "label") or self._attr(el, "title")
            value = self._attr(el, "value") or self._attr(el, "val")
            unit = self._attr(el, "unit")
            icon = self._attr(el, "icon")
            color = self._attr(el, "color")
            c = _STAT_COLORS.get(color.value) if isinstance(color, ast.Literal) else None
            args = [f"label: {self.text(label)}", f"value: {self.text(value)}"]
            if unit is not None:
                args.append(f"unit: {self.text(unit)}")
            if isinstance(icon, ast.Literal):
                args.append(f"icon: {_icon(icon.value, 'insights_outlined')}")
            if c:
                args.append(f"color: const Color({c})")
            return f"StatCard({', '.join(args)})"
        if tag == "alert":
            variant = self._attr(el, "variant")
            destructive = isinstance(variant, ast.Literal) and variant.value == "destructive"
            return f"McnAlert({self.text(text)}{', destructive: true' if destructive else ''})"
        if tag == "separator":
            return "const Divider()"
        if tag == "progress":
            v = self._attr(el, "value")
            return f"LinearProgressIndicator(value: ((({self.expr(v)}) as num?) ?? 0) / 100)"
        if tag == "img":
            src = self._attr(el, "src")
            return f"Image.network(mcnStr({self.expr(src)}))"
        if tag == "table":
            return self._table(el, imports)
        if tag in ("bar_chart", "line_chart", "pie_chart", "data_grid", "gantt_chart", "modal",
                   "dialog", "sheet", "tabs", "accordion", "dropdown_menu", "tooltip", "pagination"):
            return (f"Card(child: Padding(padding: const EdgeInsets.all(16), child: "
                    f"Text({dstr(tag.replace('_', ' ') + ' is shown in the web app (not on mobile yet)')}, "
                    f"style: theme.textTheme.bodySmall)))")
        # Unknown / custom tag: show its content
        if el.children:
            return self._column(kids())
        if text is not None:
            return f"Text({self.text(text)})"
        return "const SizedBox.shrink()"

    def _action(self, v) -> Optional[str]:
        """on_click=handler / handler(args) / backend_call(args)."""
        if v is None:
            return None
        if isinstance(v, ast.Variable) and v.name in self.handlers:
            return f"() {{ {self._handler_name(v.name)}(); }}"
        if isinstance(v, ast.Call) and isinstance(v.callee, ast.Variable):
            args = ", ".join(self.expr(a) for a in v.arguments)
            if v.callee.name in self.handlers:
                return f"() {{ {self._handler_name(v.callee.name)}({args}); }}"
            return f"() async {{ await api.invoke({dstr(v.callee.name)}, [{args}]); }}"
        return None

    def _table(self, el, imports) -> str:
        headers: List[str] = []
        body = None
        for child in el.children:
            if child.tag == "table_header":
                for row in child.children:
                    if isinstance(row, ast.UIElement) and row.tag == "table_row":
                        headers = [self.text(th.text) if th.text is not None else "''"
                                   for th in row.children if isinstance(th, ast.UIElement)]
            elif child.tag == "table_body":
                body = child
        rows: List[str] = []
        if body is not None and body.children:
            rows = self._rows(body.children, imports)
        elif body is not None:
            # Empty table_body: rows from the first list state, columns from the headers
            arr = next((s.name for s in self.comp.states if isinstance(s.value, ast.Array)), None)
            if arr:
                keys = []
                for child in el.children:
                    if child.tag == "table_header":
                        for row in child.children:
                            keys = [_field_key(str(th.text.value)) for th in row.children
                                    if isinstance(th, ast.UIElement) and isinstance(th.text, ast.Literal)]
                cells = ", ".join(f"Text(mcnStr(mcnGet(row, {dstr(k)})))" for k in keys)
                rows = [f"for (final row in mcnList({_var(arr)})) <Widget>[{cells}]"]
        hdr = ", ".join(f"mcnStr({h})" if not h.startswith("'") else h for h in headers)
        return f"McnTable(headers: [{hdr}], rows: [{', '.join(rows)}])"

    def _rows(self, nodes, imports) -> List[str]:
        """table_body children → collection elements of `List<Widget>` rows."""
        out = []
        for n in nodes:
            if isinstance(n, ast.UIFor):
                out.append(self._for(n, imports, lambda body: self._rows(body, imports)))
            elif isinstance(n, ast.UIIf):
                then = ", ".join(self._rows(n.then_children, imports))
                code = f"if (truthy({self.expr(n.condition)})) ...[{then}]"
                if n.else_children:
                    code += " else ...[" + ", ".join(self._rows(n.else_children, imports)) + "]"
                out.append(code)
            elif n.tag == "table_row":
                cells = []
                for c in n.children:
                    if not isinstance(c, ast.UIElement):
                        continue
                    if c.children:
                        inner = self.children(c.children, imports)
                        cells.append(inner[0] if len(inner) == 1 and not inner[0].startswith(("if ", "for "))
                                     else f"Wrap(spacing: 4, children: [{', '.join(inner)}])")
                    else:
                        t = c.text if c.text is not None else self._attr(c, "text")
                        cells.append(f"Text({self.text(t) if t is not None else dstr('')})")
                out.append(f"<Widget>[{', '.join(cells)}]")
        return out

    def _special(self, el, imports) -> str:
        if el.tag == "audit_log":
            imports.add("import '../mcn/audit_screen.dart';")
            title = self._attr(el, "title")
            return f"AuditScreen(title: {self.text(title)})" if title is not None else "const AuditScreen()"
        name = next((a.key for a in el.attrs if a.value is None), None)
        contracts = self.p.contracts
        if name is None or name not in contracts:
            known = ", ".join(sorted(contracts)) or "none"
            raise FlutterCompileError(f"[{el.line}:{el.col}] crud_table {name or ''}: no contract named "
                                      f"'{name}' (known: {known})")
        self.p.used_resources[name] = contracts[name]
        imports.add("import '../mcn/crud_screen.dart';")
        imports.add("import '../models.dart';")
        args = [f"resource: {self.p.resource_var(name)}"]
        cols = self._attr(el, "columns")
        if isinstance(cols, ast.Array):
            args.append("columns: const [" + ", ".join(
                dstr(c.value) for c in cols.elements if isinstance(c, ast.Literal)) + "]")
        title = self._attr(el, "title")
        if isinstance(title, ast.Literal):
            args.append(f"title: {dstr(title.value)}")
        return f"CrudScreen({', '.join(args)})"
