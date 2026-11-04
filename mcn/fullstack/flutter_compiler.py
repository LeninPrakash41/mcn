"""
MCN components → a Flutter app.

The mobile counterpart of ui_compiler.py: each `component` becomes a screen
(a StatefulWidget) whose `state`, `on load` and handlers are compiled to Dart,
and whose render tree becomes native widgets from flutter_runtime.dart. The
`app` layout becomes bottom navigation (up to five sections) or a drawer.

    FlutterCompiler(endpoints={"list_tasks": []}).compile(evaluator, "mobile", "my_app")
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from mcn.core_engine import ast_nodes as ast

_RUNTIME = Path(__file__).resolve().parent / "flutter_runtime.dart"

_DART_RESERVED = {"abstract", "as", "assert", "async", "await", "break", "case", "catch", "class", "const", "continue",
                  "default", "deferred", "do", "dynamic", "else", "enum", "export", "extends", "extension", "external",
                  "factory", "false", "final", "finally", "for", "function", "get", "if", "implements", "import", "in",
                  "interface", "is", "late", "library", "mixin", "new", "null", "on", "operator", "part", "required",
                  "rethrow", "return", "set", "show", "static", "super", "switch", "sync", "this", "throw", "true", "try",
                  "typedef", "var", "void", "while", "with", "yield", "context", "widget", "mounted", "state", "build"}

_WEB_ONLY = {"agent_builder": "Agent builder", "workflow_builder": "Workflow builder"}
_SKIP = {"breadcrumb", "modal", "dialog", "sheet", "tooltip", "table_header", "table_row", "table_head", "table_body"}


def _cls(name: str) -> str:
    """Screen class name: Deals → DealsScreen (avoids clashes with Flutter's own Builder, Table, Card…)."""
    return name if name.endswith("Screen") else f"{name}Screen"


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _ident(name: str) -> str:
    return f"{name}_" if name in _DART_RESERVED else name


def _dstr(value) -> str:
    """A Dart string literal."""
    s = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("$", "\\$").replace("\n", "\\n")
    return f"'{s}'"


class FlutterCompiler:
    def __init__(self, endpoints: Optional[Dict[str, List[str]]] = None):
        self.endpoints = endpoints or {}

    # ── Public API ──────────────────────────────────────────────────────────

    def compile(self, evaluator, output_dir, project_name: str = "mcn_mobile_app") -> List[Path]:
        from .flutter_generator import FlutterProjectGenerator
        out = Path(output_dir)
        lib = out / "lib"
        (lib / "screens").mkdir(parents=True, exist_ok=True)
        (lib / "services").mkdir(parents=True, exist_ok=True)
        (lib / "mcn").mkdir(parents=True, exist_ok=True)
        gen = FlutterProjectGenerator()
        gen._generate_pubspec_yaml(out, project_name)
        gen._generate_mcn_client(out)
        written = [out / "pubspec.yaml", lib / "services" / "mcn_client.dart"]

        runtime = lib / "mcn" / "mcn_runtime.dart"
        runtime.write_text(_RUNTIME.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(runtime)

        components: Dict[str, ast.ComponentDecl] = evaluator.components
        for stale in (lib / "screens").glob("*.dart"):      # components removed since the last build
            stale.unlink()
        for name, comp in components.items():
            path = lib / "screens" / f"{_snake(name)}.dart"
            path.write_text(self._screen(comp), encoding="utf-8")
            written.append(path)

        main = lib / "main.dart"
        main.write_text(self._main(evaluator.app_decl, components), encoding="utf-8")
        written.append(main)
        # Old pages from the manifest generator would no longer compile against this app
        old_pages = lib / "pages"
        if old_pages.exists():
            for p in old_pages.glob("*.dart"):
                p.unlink()
        return written

    # ── App ─────────────────────────────────────────────────────────────────

    def _main(self, app: Optional[ast.AppDecl], components: Dict[str, ast.ComponentDecl]) -> str:
        from mcn.core_engine.ui_compiler import UICompiler
        icon_for = UICompiler(Path("."))._nav_icon
        layout = app.layout if app else None
        sections = []
        if layout and layout.sidebar:
            sections = [(n.label, n.icon or icon_for(n.label), n.component or n.label.replace(" ", "")) for n in layout.sidebar]
        elif layout and layout.tabs:
            sections = [(t.label, icon_for(t.label), t.component or t.label.replace(" ", "")) for t in layout.tabs]
        sections = [s for s in sections if s[2] in components]
        if not sections:
            names = (layout.main if layout and layout.main else list(components)) or []
            sections = [(n, "home", n) for n in names if n in components]
        imports = "\n".join(f"import 'screens/{_snake(c)}.dart';" for c in sorted({s[2] for s in sections}))
        items = ",\n      ".join(f"MCNSection({_dstr(label)}, {_dstr(icon)}, () => const {_cls(comp)}())" for label, icon, comp in sections)
        title = (app.title or app.name) if app else "MCN App"
        return f"""// Generated by MCN from ui/app.mcn — edit the MCN file, not this one.
import 'package:flutter/material.dart';
import 'mcn/mcn_runtime.dart';
{imports}

void main() => runApp(MCNApp(
    title: {_dstr(title)},
    sections: [
      {items}
    ],
  ));
"""

    # ── Screens ─────────────────────────────────────────────────────────────

    def _screen(self, comp: ast.ComponentDecl) -> str:
        self.comp = comp
        self.states: Set[str] = {s.name for s in comp.states}
        self.bound: Dict[str, bool] = {}          # state bound to an input → numeric?
        self._find_bindings(comp.render.elements if comp.render else [])
        self.handlers = {h.event for h in comp.handlers}

        fields = []
        for st in comp.states:
            fields.append(f"  dynamic {_ident(st.name)} = {self._expr(st.value, {}) if st.value is not None else 'null'};")
        for name in self.bound:
            fields.append(f"  late final TextEditingController _{name}Ctl = TextEditingController(text: mcnStr({_ident(name)}));")

        methods = []
        init = ""
        for h in comp.handlers:
            if h.event == "load":
                init = "    _onLoad();\n"
                methods.append(self._handler("_onLoad", h.body))
            else:
                methods.append(self._handler(self._handler_name(h.event), h.body))
        dispose = ""
        if self.bound:
            dispose = "  @override\n  void dispose() {\n" + "".join(f"    _{n}Ctl.dispose();\n" for n in self.bound) + "    super.dispose();\n  }\n\n"

        body = self._children(comp.render.elements if comp.render else [], in_form=None)
        return f"""// Generated by MCN from ui/app.mcn — edit the MCN file, not this one.
// ignore_for_file: unused_import, unused_element_parameter, prefer_const_constructors, unnecessary_this, dead_code, unused_local_variable
import 'package:flutter/material.dart';
import '../mcn/mcn_runtime.dart';
import '../services/mcn_client.dart';

class {_cls(comp.name)} extends StatefulWidget {{
  const {_cls(comp.name)}({{super.key}});
  @override
  State<{_cls(comp.name)}> createState() => _{_cls(comp.name)}State();
}}

class _{_cls(comp.name)}State extends State<{_cls(comp.name)}> {{
  final MCNClient _mcn = MCNClient();
{chr(10).join(fields)}

  @override
  void initState() {{
    super.initState();
{init}  }}

{dispose}{chr(10).join(methods)}
  @override
  Widget build(BuildContext context) {{
    return ListView(
      padding: const EdgeInsets.all(16),
      children: _spaced([
{body}
      ]),
    );
  }}

  List<Widget> _spaced(List<Widget> items) =>
      [for (var i = 0; i < items.length; i++) ...[if (i > 0) const SizedBox(height: 16), items[i]]];
}}
"""

    def _handler_name(self, event: str) -> str:
        return "_on" + "".join(p.capitalize() for p in event.split("_"))

    def _find_bindings(self, elements):
        for el in elements:
            bind = next((a for a in el.attrs if a.key == "bind" and isinstance(a.value, ast.Variable)), None)
            if bind and el.tag in ("input", "textarea"):
                numeric = any(a.key == "type" and isinstance(a.value, ast.Literal) and a.value.value == "number" for a in el.attrs)
                self.bound[bind.value.name] = numeric
            self._find_bindings(el.children)

    def _handler(self, name: str, body: List[ast.Stmt]) -> str:
        # The value a handler is about (row, item…), unless the component has state of that name
        implicit = [n for n in ("row", "item", "agent", "workflow", "message") if n not in self.states and any(
            isinstance(x, ast.Variable) and x.name == n for x in _walk(body))]
        binds = "".join(f"    final dynamic {n} = e;\n" for n in implicit)
        stmts = self._stmts(body, 4, set(implicit))
        return f"  Future<dynamic> {name}([dynamic e]) async {{\n{binds}{stmts}    if (mounted) setState(() {{}});\n    return null;\n  }}\n"

    # ── Statements ──────────────────────────────────────────────────────────

    def _stmts(self, stmts: List[ast.Stmt], indent: int, local: Set[str]) -> str:
        pad = " " * indent
        out = []
        for s in stmts:
            if isinstance(s, ast.VarDecl):
                local.add(s.name)
                out.append(f"{pad}dynamic {_ident(s.name)} = {self._expr(s.value, local)};")
            elif isinstance(s, (ast.AssignStmt, ast.CompoundAssignStmt)):
                value = self._expr(s.value, local)
                if isinstance(s, ast.CompoundAssignStmt):
                    target = _ident(s.name)
                    value = f"mcnAdd({target}, {value})" if s.op == "+" else f"(mcnNum({target}) {s.op} mcnNum({value}))"
                out.append(f"{pad}{_ident(s.name)} = {value};")
                if s.name in self.states and s.name not in local:
                    if s.name in self.bound:
                        out.append(f"{pad}_{s.name}Ctl.text = mcnStr({_ident(s.name)});")
                    out.append(f"{pad}if (mounted) setState(() {{}});")
            elif isinstance(s, ast.PropertyAssignStmt):
                out.append(f"{pad}({self._expr(s.object, local)} as Map)[{_dstr(s.prop)}] = {self._expr(s.value, local)};")
            elif isinstance(s, ast.IndexAssignStmt):
                out.append(f"{pad}({self._expr(s.object, local)})[{self._expr(s.index, local)}] = {self._expr(s.value, local)};")
            elif isinstance(s, ast.IfStmt):
                out.append(f"{pad}if (mcnTruthy({self._expr(s.condition, local)})) {{")
                out.append(self._stmts(s.then_body, indent + 2, set(local)).rstrip("\n"))
                if s.else_body:
                    out.append(f"{pad}}} else {{")
                    out.append(self._stmts(s.else_body, indent + 2, set(local)).rstrip("\n"))
                out.append(f"{pad}}}")
            elif isinstance(s, ast.ForStmt):
                inner = set(local) | {s.variable} | ({s.index_var} if s.index_var else set())
                if s.index_var:
                    out.append(f"{pad}final _list = mcnList({self._expr(s.iterable, local)});")
                    out.append(f"{pad}for (var {_ident(s.index_var)} = 0; {_ident(s.index_var)} < _list.length; {_ident(s.index_var)}++) {{")
                    out.append(f"{pad}  final dynamic {_ident(s.variable)} = _list[{_ident(s.index_var)}];")
                else:
                    out.append(f"{pad}for (final dynamic {_ident(s.variable)} in mcnList({self._expr(s.iterable, local)})) {{")
                out.append(self._stmts(s.body, indent + 2, inner).rstrip("\n"))
                out.append(f"{pad}}}")
            elif isinstance(s, ast.WhileStmt):
                out.append(f"{pad}while (mcnTruthy({self._expr(s.condition, local)})) {{")
                out.append(self._stmts(s.body, indent + 2, set(local)).rstrip("\n"))
                out.append(f"{pad}}}")
            elif isinstance(s, ast.ReturnStmt):
                out.append(f"{pad}if (mounted) setState(() {{}});")
                out.append(f"{pad}return {self._expr(s.value, local) if s.value is not None else 'null'};")
            elif isinstance(s, ast.BreakStmt):
                out.append(f"{pad}break;")
            elif isinstance(s, ast.ContinueStmt):
                out.append(f"{pad}continue;")
            elif isinstance(s, ast.ExprStmt):
                out.append(f"{pad}{self._expr(s.expression, local)};")
        return "\n".join(l for l in out if l.strip()) + "\n" if out else ""

    # ── Expressions ─────────────────────────────────────────────────────────

    def _expr(self, e, local: Set[str]) -> str:
        if e is None:
            return "null"
        if isinstance(e, ast.Literal):
            v = e.value
            if v is None:
                return "null"
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, (int, float)):
                return repr(v)
            return _dstr(v)
        if isinstance(e, ast.Variable):
            if e.name in ("true", "false", "null"):     # MCN's built-in constants
                return e.name
            return _ident(e.name)
        if isinstance(e, ast.Property):
            return f"mcnGet({self._expr(e.object, local)}, {_dstr(e.name)})"
        if isinstance(e, ast.Index):
            return f"mcnIndex({self._expr(e.object, local)}, {self._expr(e.index, local)})"
        if isinstance(e, ast.Array):
            return "<dynamic>[" + ", ".join(self._expr(x, local) for x in e.elements) + "]"
        if isinstance(e, ast.MCNTuple):
            return "<dynamic>[" + ", ".join(self._expr(x, local) for x in e.elements) + "]"
        if isinstance(e, ast.MCNObject):
            pairs = []
            for k, v in e.properties:
                key = k.name if isinstance(k, ast.Variable) else (k.value if isinstance(k, ast.Literal) else None)
                pairs.append(f"{_dstr(key)}: {self._expr(v, local)}")
            return "<String, dynamic>{" + ", ".join(pairs) + "}"
        if isinstance(e, ast.Unary):
            if e.operator == "not":
                return f"!mcnTruthy({self._expr(e.operand, local)})"
            return f"(-mcnNum({self._expr(e.operand, local)}))"
        if isinstance(e, ast.TernaryExpr):
            return f"(mcnTruthy({self._expr(e.condition, local)}) ? {self._expr(e.then_expr, local)} : {self._expr(e.else_expr, local)})"
        if isinstance(e, ast.Binary):
            a, b, op = self._expr(e.left, local), self._expr(e.right, local), e.operator
            if op == "+":
                return f"mcnAdd({a}, {b})"
            if op in ("-", "*", "/", "%"):
                return f"(mcnNum({a}) {'~/' if False else op} mcnNum({b}))"
            if op in ("<", ">", "<=", ">="):
                return f"(mcnNum({a}) {op} mcnNum({b}))"
            if op == "==":
                return f"({a} == {b})"
            if op == "!=":
                return f"({a} != {b})"
            if op == "and":
                return f"(mcnTruthy({a}) ? {b} : {a})"
            if op == "or":
                return f"(mcnTruthy({a}) ? {a} : {b})"
        if isinstance(e, ast.Call):
            return self._call(e, local)
        if isinstance(e, ast.ArrowFunc):
            params = ", ".join(f"dynamic {_ident(p)}" for p in e.params)
            return f"(({params}) => {self._expr(e.body, local | set(e.params))})"
        return "null"

    def _call(self, e: ast.Call, local: Set[str]) -> str:
        args = [self._expr(a, local) for a in e.arguments if not isinstance(a, ast.NamedArg)]
        if isinstance(e.callee, ast.Property):        # text.upper() etc.
            obj = self._expr(e.callee.object, local)
            return self._builtin(e.callee.name, [obj, *args]) or f"null /* .{e.callee.name}() */"
        name = getattr(e.callee, "name", "")
        builtin = self._builtin(name, args)
        if builtin is not None:
            return builtin
        if name in self.handlers:
            return f"(await {self._handler_name(name)}({', '.join(args[:1])}))"
        # A backend endpoint
        params = self.endpoints.get(name)
        if params is not None:
            body = ", ".join(f"{_dstr(p)}: {a}" for p, a in zip(params, args))
        else:
            keys = [a.name if isinstance(a, ast.Variable) else f"arg{i}" for i, a in enumerate(e.arguments)]
            body = ", ".join(f"{_dstr(k)}: {a}" for k, a in zip(keys, args))
        return f"(await _mcn.call({_dstr(name)}, <String, dynamic>{{{body}}}))"

    def _builtin(self, name: str, a: List[str]) -> Optional[str]:
        one = a[0] if a else "null"
        table = {
            "str": f"mcnStr({one})", "len": f"mcnLen({one})", "upper": f"mcnStr({one}).toUpperCase()",
            "lower": f"mcnStr({one}).toLowerCase()", "trim": f"mcnStr({one}).trim()",
            "int": f"mcnNum({one}).toInt()", "float": f"mcnNum({one}).toDouble()",
            "abs": f"mcnNum({one}).abs()", "round": f"mcnRound({', '.join(a)})",
            "contains": f"mcnContains({', '.join(a[:2])})", "log": f"debugPrint(mcnStr({one}))",
            "join": f"mcnList({one}).map(mcnStr).join({a[1] if len(a) > 1 else _dstr('')})",
            "notify": f"mcnNotify(context, {', '.join(a[:2])})", "toast": f"mcnNotify(context, {one})",
            "push": f"(mcnList({one}) as List).add({a[1] if len(a) > 1 else 'null'})",
            "map": f"mcnList({one}).map({a[1] if len(a) > 1 else '(x) => x'}).toList()",
            "filter": f"mcnList({one}).where((x) => mcnTruthy(({a[1] if len(a) > 1 else '(x) => true'})(x))).toList()",
            "sum": f"mcnList({one}).fold<num>(0, (s, x) => s + mcnNum(x))",
            "now": "DateTime.now().toIso8601String()",
        }
        return table.get(name)

    # ── Render tree ─────────────────────────────────────────────────────────

    def _attr(self, el: ast.UIElement, key: str):
        return next((a.value for a in el.attrs if a.key == key), None)

    def _has(self, el, key):
        return any(a.key == key for a in el.attrs)

    def _children(self, elements: List[ast.UIElement], in_form: Optional[str]) -> str:
        parts = [w for w in (self._widget(el, in_form) for el in elements) if w]
        return ",\n".join("        " + p for p in parts)

    def _lit(self, el, key, default=None):
        v = self._attr(el, key)
        return self._expr(v, set()) if v is not None else default

    def _first_list_state(self) -> str:
        lists = [s.name for s in self.comp.states if isinstance(s.value, ast.Array)]
        return _ident(lists[0]) if lists else "const []"

    def _action(self, el, key: str, params: str, payload: str) -> Optional[str]:
        v = self._attr(el, key)
        if not isinstance(v, ast.Variable):
            return None
        first = params.split(",")[0].split()[-1] if params else ""
        if v.name in self.handlers:
            return f"({params}) async => {self._handler_name(v.name)}({first})"
        return f"({params}) async => _mcn.call({_dstr(v.name)}, {payload})"

    def _widget(self, el: ast.UIElement, in_form: Optional[str]) -> Optional[str]:
        tag = el.tag
        text = self._expr(el.text, set()) if el.text is not None else None
        if tag in _SKIP:
            return None
        if tag in _WEB_ONLY:
            return f"const MCNWebOnly({_dstr(_WEB_ONLY[tag])})"
        if tag == "for" and el.for_var:
            inner = [w for w in (self._widget(c, in_form) for c in el.children) if w]
            body = inner[0] if len(inner) == 1 else f"Column(crossAxisAlignment: CrossAxisAlignment.start, children: [{', '.join(inner)}])"
            return f"...mcnList({self._expr(el.for_iterable, set())}).map((dynamic {_ident(el.for_var)}) => {body})"

        show = self._attr(el, "show")
        if show is not None and tag not in ("modal", "dialog", "sheet"):
            rest = ast.UIElement(tag=el.tag, attrs=[a for a in el.attrs if a.key != "show"], text=el.text, children=el.children)
            inner = self._widget(rest, in_form)
            return f"if (mcnTruthy({self._expr(show, set())})) {inner}" if inner else None

        if tag in ("div", "section", "main", "header", "footer", "card_content", "nav", "ul", "ol"):
            cols = self._attr(el, "grid_cols")
            kids = self._children(el.children, in_form)
            if cols is not None:
                return f"MCNGrid(columns: {self._expr(cols, set()).strip(chr(39))}, children: [\n{kids}\n        ])"
            return f"Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [\n{kids}\n        ])"
        if tag == "card":
            header = next((c for c in el.children if c.tag == "card_header"), None)
            title = self._expr(header.text, set()) if header is not None and header.text is not None else "null"
            rest = [c for c in el.children if c.tag != "card_header"]
            return f"MCNCard(title: {title if title == 'null' else f'mcnStr({title})'}, children: [\n{self._children(rest, in_form)}\n        ])"
        if tag == "card_header":
            return f"Text(mcnStr({text or _dstr('')}), style: Theme.of(context).textTheme.titleMedium)"
        if tag in ("h1", "h2", "h3"):
            style = {"h1": "headlineSmall", "h2": "titleLarge", "h3": "titleMedium"}[tag]
            return f"Text(mcnStr({text or _dstr('')}), style: Theme.of(context).textTheme.{style})"
        if tag in ("text", "p", "span", "label"):
            value = text
            if value is None:
                flag = next((a.key for a in el.attrs if a.value is None), None)
                value = _ident(flag) if flag else _dstr("")
            return f"Text(mcnStr({value}))"
        if tag == "separator":
            return "const Divider()"
        if tag in ("badge",):
            return f"Align(alignment: Alignment.centerLeft, child: MCNBadge({text or _dstr('')}))"
        if tag == "alert":
            return f"Card(color: Theme.of(context).colorScheme.secondaryContainer, child: Padding(padding: const EdgeInsets.all(12), child: Text(mcnStr({text or self._lit(el, 'message', _dstr(''))}))))"
        if tag in ("stat_card", "stat"):
            return (f"MCNStat(label: {self._lit(el, 'label', 'null')}, value: {self._lit(el, 'value', 'null')}, "
                    f"icon: {self._lit(el, 'icon', 'null')}, color: {self._lit(el, 'color', 'null')}, unit: {self._lit(el, 'unit', 'null')})")
        if tag == "empty_state":
            return f"MCNEmpty(title: {text or self._lit(el, 'title', _dstr(''))}, description: {self._lit(el, 'description', 'null')}, icon: {self._lit(el, 'icon', 'null')})"
        if tag in ("bar_chart", "line_chart", "area_chart", "pie_chart", "donut_chart"):
            kind = tag.split("_")[0]
            if tag in ("pie_chart", "donut_chart"):
                x, y = self._lit(el, "name_key", "'name'"), self._lit(el, "value_key", "'value'")
            else:
                x, y = self._lit(el, "x_key", "'label'"), self._lit(el, "y_key", "'value'")
            y = y if y.startswith("<dynamic>[") else f"[{y}]"
            height = self._lit(el, "height", "220")
            return f"MCNChart(kind: {_dstr(kind)}, data: {self._lit(el, 'data', 'const []')}, x: {x}, y: {y}, height: ({height}).toDouble())"
        if tag in ("data_table", "table", "data_grid"):
            columns = self._lit(el, "columns", "const []")
            if tag == "table" and columns == "const []":
                heads = [c.text.value for c in _walk_ui(el) if c.tag == "table_head" and isinstance(c.text, ast.Literal)]
                columns = "<dynamic>[" + ", ".join(_dstr(h) for h in heads) + "]"
            data = self._lit(el, "data", None) or self._first_list_state()
            on_delete = self._action(el, "on_delete", "dynamic row", "<String, dynamic>{'id': mcnGet(row, 'id'), 'row': row}")
            on_row = self._action(el, "on_row", "dynamic row", "<String, dynamic>{'id': mcnGet(row, 'id'), 'row': row}")
            title = self._lit(el, "title", None)
            return (f"MCNDataList(data: {data}, columns: {columns}, filters: {self._lit(el, 'filters', 'const []')}, "
                    f"title: {f'mcnStr({title})' if title else 'null'}, pageSize: {self._lit(el, 'page_size', '20')}"
                    + (f", titleKey: {self._lit(el, 'title_key')}" if self._has(el, "title_key") else "")
                    + (f", onDelete: {on_delete}" if on_delete else "") + (f", onTap: {on_row}" if on_row else "") + ")")
        if tag == "kanban":
            group = self._lit(el, "group_by", "'status'")
            on_move = self._action(el, "on_move", "dynamic item, String to", f"<String, dynamic>{{'id': mcnGet(item, 'id'), {group}: to, 'item': item}}")
            return (f"MCNKanban(data: {self._lit(el, 'data', None) or self._first_list_state()}, groupBy: {group}, "
                    f"columns: {self._lit(el, 'columns', 'const []')}"
                    + (f", titleKey: {self._lit(el, 'title_key')}" if self._has(el, "title_key") else "")
                    + (f", onMove: {on_move}" if on_move else "") + ")")
        if tag in ("chat", "chat_widget"):
            send = self._action(el, "endpoint", "String message, List<Map<String, String>> history",
                                "<String, dynamic>{'message': message, 'history': history}") or \
                self._action(el, "on_send", "String message, List<Map<String, String>> history",
                             "<String, dynamic>{'message': message, 'history': history}") or "(m, h) async => ''"
            title = text or self._lit(el, "title", _dstr("Assistant"))
            return (f"MCNChat(title: mcnStr({title}), welcome: {self._lit(el, 'welcome', 'null')}, "
                    f"suggestions: {self._lit(el, 'suggestions', 'const []')}, onSend: {send})")
        if tag == "form":
            submit = self._attr(el, "on_submit")
            handler = self._handler_name(submit.name) if isinstance(submit, ast.Variable) and submit.name in self.handlers else None
            return f"Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: _spaced([\n{self._children(el.children, handler)}\n        ]))"
        if tag in ("input", "textarea"):
            bind = self._attr(el, "bind")
            label = self._lit(el, "label", None) or self._lit(el, "placeholder", "null")
            if isinstance(bind, ast.Variable):
                name = bind.name
                parse = f"mcnNum(v)" if self.bound.get(name) else "v"
                kb = ", keyboardType: TextInputType.number" if self.bound.get(name) else ""
                lines = ", maxLines: 4" if tag == "textarea" else ""
                return (f"TextField(controller: _{name}Ctl, decoration: InputDecoration(labelText: {label}, border: const OutlineInputBorder())"
                        f"{kb}{lines}, onChanged: (v) => setState(() => {_ident(name)} = {parse}))")
            return f"TextField(decoration: InputDecoration(labelText: {label}))"
        if tag == "select":
            bind = self._attr(el, "bind")
            options = self._lit(el, "options", "const []")
            label = self._lit(el, "label", "null")
            if isinstance(bind, ast.Variable):
                v = _ident(bind.name)
                return (f"DropdownButtonFormField<String>(value: mcnList({options}).map(mcnStr).contains(mcnStr({v})) ? mcnStr({v}) : null, "
                        f"decoration: InputDecoration(labelText: {label}, border: const OutlineInputBorder()), "
                        f"items: [for (final o in mcnList({options})) DropdownMenuItem(value: mcnStr(o), child: Text(mcnStr(o)))], "
                        f"onChanged: (v) => setState(() => {v} = v))")
            return None
        if tag in ("checkbox", "switch"):
            bind = self._attr(el, "bind")
            if isinstance(bind, ast.Variable):
                v = _ident(bind.name)
                return f"SwitchListTile(title: Text(mcnStr({self._lit(el, 'label', _dstr(''))})), value: mcnTruthy({v}), onChanged: (b) => setState(() => {v} = b))"
            return None
        if tag == "button":
            click = self._attr(el, "on_click")
            target = None
            if isinstance(click, ast.Variable) and click.name in self.handlers:
                target = self._handler_name(click.name)
            elif in_form:
                target = in_form
            label = text or _dstr("Button")
            outline = isinstance(self._attr(el, "variant"), ast.Literal) and self._attr(el, "variant").value in ("outline", "ghost", "secondary")
            widget = "OutlinedButton" if outline else "FilledButton"
            return f"{widget}(onPressed: {('() => ' + target + '()') if target else 'null'}, child: Text(mcnStr({label})))"
        if tag in ("tabs", "accordion", "accordion_item", "tab_content", "tabs_list", "tab_trigger"):
            return f"Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [\n{self._children(el.children, in_form)}\n        ])"
        if tag in ("progress",):
            return f"LinearProgressIndicator(value: mcnNum({self._lit(el, 'value', '0')}) / 100)"
        if tag == "img":
            return f"Image.network(mcnStr({self._lit(el, 'src', _dstr(''))}))"
        if el.children:
            return f"Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [\n{self._children(el.children, in_form)}\n        ])"
        if text is not None:
            return f"Text(mcnStr({text}))"
        return None


def _walk(stmts):
    """Every AST node under a list of statements."""
    from dataclasses import fields, is_dataclass
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if not is_dataclass(node):
            continue
        yield node
        for f in fields(node):
            v = getattr(node, f.name)
            items = v if isinstance(v, list) else list(v.values()) if isinstance(v, dict) else [v]
            for item in items:
                if isinstance(item, tuple):
                    stack.extend(item)
                elif is_dataclass(item):
                    stack.append(item)


def _walk_ui(el):
    yield el
    for c in el.children:
        yield from _walk_ui(c)
