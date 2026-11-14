"""
MCN UI Compiler — converts ComponentDecl / AppDecl AST nodes into
React + shadcn/ui TypeScript files.

Pipeline:
  1.  Parse .mcn file  →  AST (Program)
  2.  Run evaluator    →  evaluator.components, evaluator.app_decl populated
  3.  UICompiler       →  writes frontend/src/** TSX files
  4.  shadcn installer →  runs `npx shadcn@latest add <components>`
  5.  tailwind config  →  written from app.theme

Entry point:
    from mcn.core_engine.ui_compiler import UICompiler
    compiler = UICompiler(output_dir="my_app/frontend")
    compiler.compile(evaluator)
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import ast_nodes as ast

# The MCN UI kit: components every compiled app is built from
_KIT_DIR = Path(__file__).resolve().parent.parent / "ui-kit" / "react" / "src"

# Backend endpoint name → parameter names, when the backend is known. Calls from
# UI code then send each argument under the parameter it belongs to.
_ENDPOINT_PARAMS: Dict[str, List[str]] = {}

# Handler names that are reserved words in JavaScript get an `on` prefix
_JS_RESERVED = {"break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete",
                "do", "else", "enum", "export", "extends", "finally", "for", "function", "if", "import",
                "in", "instanceof", "new", "return", "super", "switch", "this", "throw", "try", "typeof",
                "var", "void", "while", "with", "yield", "let", "static", "await"}


def _handler_name(event: str) -> str:
    """`on submit` → submit, `on delete` → onDelete (delete is reserved in JavaScript)."""
    name = _camel(event)
    return "on" + _pascal(event) if name in _JS_RESERVED else name


# Elements rendered by a single kit component, with their attributes passed as props
_KIT_TAGS = {"bar_chart", "line_chart", "area_chart", "pie_chart", "donut_chart", "sparkline",
             "data_table", "kanban", "breadcrumb", "empty_state",
             "chat", "chat_widget", "agent_builder", "workflow_builder"}

# Attributes that name an endpoint or handler: attr → (prop, TS parameters, endpoint payload)
_KIT_ACTIONS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "chat":        {"endpoint": ("onSend", "message: string, history: { role: string; content: string }[]", "{ message, history }"),
                    "on_send":  ("onSend", "message: string, history: { role: string; content: string }[]", "{ message, history }")},
    "agent_builder": {"on_save":   ("onSave",   "agent: Row", "{ agent }"),
                      "on_test":   ("onTest",   "agent: Row, message: string, history: { role: string; content: string }[]", "{ agent, message, history }"),
                      "on_delete": ("onDelete", "agent: Row", "{ id: agent.id, agent }")},
    "workflow_builder": {"on_save": ("onSave", "workflow: Row", "{ workflow }"),
                         "on_run":  ("onRun",  "workflow: Row", "{ workflow }")},
    "data_table":  {"on_add":    ("onAdd",      "", "{}"),
                    "on_edit":   ("onEdit",     "row: Row", "{ id: row.id, row }"),
                    "on_delete": ("onDelete",   "row: Row", "{ id: row.id, row }"),
                    "on_row":    ("onRowClick", "row: Row", "{ id: row.id, row }")},
    "kanban":      {"on_move":   ("onMove",      "item: Row, to: string", "{ id: item.id, GROUP: to, item }"),
                    "on_click":  ("onCardClick", "item: Row", "{ id: item.id, item }")},
}
_KIT_ACTIONS["chat_widget"] = _KIT_ACTIONS["chat"]


# ── shadcn component map ───────────────────────────────────────────────────────
# MCN tag → (shadcn component name(s), shadcn package name, JSX tag(s))

_SHADCN: Dict[str, Tuple[List[str], str, str]] = {
    # tag: ([imports from package], shadcn package slug, primary JSX tag)
    "card":         (["Card", "CardContent"],          "card",     "Card"),
    "card_header":  (["CardHeader"],                   "card",     "CardHeader"),
    "card_content": (["CardContent"],                  "card",     "CardContent"),
    "card_footer":  (["CardFooter"],                   "card",     "CardFooter"),
    "input":        (["Input"],                        "input",    "Input"),
    "textarea":     (["Textarea"],                     "textarea", "Textarea"),
    "button":       (["Button"],                       "button",   "Button"),
    "label":        (["Label"],                        "label",    "Label"),
    "badge":        (["Badge"],                        "badge",    "Badge"),
    "alert":        (["Alert", "AlertDescription"],    "alert",    "Alert"),
    "separator":    (["Separator"],                    "separator","Separator"),
    "table":        (["Table","TableHeader","TableBody","TableRow","TableHead","TableCell"],
                     "table",   "Table"),
    "table_header": (["TableHeader"],                  "table",    "TableHeader"),
    "table_body":   (["TableBody"],                    "table",    "TableBody"),
    "table_row":    (["TableRow"],                     "table",    "TableRow"),
    "table_head":   (["TableHead"],                    "table",    "TableHead"),
    "table_cell":   (["TableCell"],                    "table",    "TableCell"),
    "tabs":         (["Tabs","TabsList","TabsTrigger","TabsContent"],
                     "tabs",    "Tabs"),
    "tabs_list":    (["TabsList"],                     "tabs",     "TabsList"),
    "tab_trigger":  (["TabsTrigger"],                  "tabs",     "TabsTrigger"),
    "tab_content":  (["TabsContent"],                  "tabs",     "TabsContent"),
    "select":       (["Select","SelectContent","SelectItem","SelectTrigger","SelectValue"],
                     "select",  "Select"),
    "dialog":       (["Dialog","DialogContent","DialogHeader","DialogTitle"],
                     "dialog",  "Dialog"),
    "modal":        (["Dialog","DialogContent","DialogHeader","DialogTitle"],
                     "dialog",  "Dialog"),
    "scroll_area":  (["ScrollArea"],                   "scroll-area", "ScrollArea"),
    "avatar":       (["Avatar","AvatarImage","AvatarFallback"],
                     "avatar",  "Avatar"),
    "progress":     (["Progress"],                     "progress", "Progress"),
    "skeleton":     (["Skeleton"],                     "skeleton", "Skeleton"),
    "toast":        ([],                               "toast",    "toast"),
    # Charts — the kit's SVG charts
    "bar_chart":    (["BarChart"],                     "chart",    "BarChart"),
    "line_chart":   (["LineChart"],                    "chart",    "LineChart"),
    "area_chart":   (["AreaChart"],                    "chart",    "AreaChart"),
    "pie_chart":    (["PieChart"],                     "chart",    "PieChart"),
    "donut_chart":  (["DonutChart"],                   "chart",    "DonutChart"),
    "sparkline":    (["Sparkline"],                    "chart",    "Sparkline"),
    # Rich components
    "data_table":   (["DataTable"],                    "data-table",       "DataTable"),
    "kanban":       (["Kanban"],                       "kanban",           "Kanban"),
    "breadcrumb":   (["Breadcrumb"],                   "breadcrumb",       "Breadcrumb"),
    "empty_state":  (["EmptyState"],                   "empty-state",      "EmptyState"),
    "chat":         (["ChatBot"],                      "chat",             "ChatBot"),
    "chat_widget":  (["ChatWidget"],                   "chat",             "ChatWidget"),
    "agent_builder":    (["AgentBuilder"],             "agent-builder",    "AgentBuilder"),
    "workflow_builder": (["WorkflowBuilder"],          "workflow-builder", "WorkflowBuilder"),
    # New components
    "checkbox":      (["Checkbox"],                     "checkbox",      "Checkbox"),
    "switch":        (["Switch"],                       "switch",        "Switch"),
    "radio_group":   (["RadioGroup", "RadioGroupItem"], "radio-group",   "RadioGroup"),
    "tooltip":       (["Tooltip", "TooltipContent", "TooltipProvider", "TooltipTrigger"],
                      "tooltip",       "TooltipProvider"),
    "accordion":     (["Accordion", "AccordionContent", "AccordionItem", "AccordionTrigger"],
                      "accordion",     "Accordion"),
    "dropdown_menu": (["DropdownMenu", "DropdownMenuContent", "DropdownMenuItem",
                       "DropdownMenuTrigger", "DropdownMenuSeparator"],
                      "dropdown-menu", "DropdownMenu"),
    "sheet":         (["Sheet", "SheetContent", "SheetHeader", "SheetTitle", "SheetTrigger"],
                      "sheet",         "Sheet"),
}

# Tags that map to plain HTML elements (no shadcn import needed)
_HTML_TAGS = {"div", "span", "p", "h1", "h2", "h3", "h4", "form",
              "section", "article", "header", "footer", "main", "nav",
              "ul", "li", "ol", "a", "img", "text",
              "accordion_item"}  # handled inside accordion renderer

# Tailwind theme presets applied to globals.css CSS variables
_THEMES: Dict[str, Dict[str, str]] = {
    "professional": {
        "--radius":     "0.5rem",
        "--background": "0 0% 100%",
        "--foreground": "222.2 84% 4.9%",
        "--primary":    "222.2 47.4% 11.2%",
        "--accent":     "210 40% 96.1%",
    },
    "modern": {
        "--radius":     "0.75rem",
        "--background": "0 0% 100%",
        "--foreground": "240 10% 3.9%",
        "--primary":    "240 5.9% 10%",
        "--accent":     "240 4.8% 95.9%",
    },
    "minimal": {
        "--radius":     "0.25rem",
        "--background": "0 0% 100%",
        "--foreground": "0 0% 3.9%",
        "--primary":    "0 0% 9%",
        "--accent":     "0 0% 96.1%",
    },
    "glassmorphism": {
        "--radius":     "1rem",
        "--background": "220 33% 98%",
        "--foreground": "224 71% 4%",
        "--primary":    "262.1 83.3% 57.8%",
        "--accent":     "262.1 83.3% 95%",
        "--border":     "220 13% 91%",
    },
    "luxury_dark": {
        "--radius":     "0.75rem",
        "--background": "224 71% 4%",
        "--foreground": "210 40% 98%",
        "--primary":    "263.4 70% 50.4%",
        "--accent":     "217.2 32.6% 17.5%",
        "--border":     "217.2 32.6% 17.5%",
    },
    "default": {
        "--radius":     "0.5rem",
        "--background": "0 0% 100%",
        "--foreground": "222.2 84% 4.9%",
        "--primary":    "221.2 83.2% 53.3%",
        "--accent":     "210 40% 96.1%",
    },
}


# ── helpers ────────────────────────────────────────────────────────────────────

def endpoints_from_backend(path) -> Dict[str, List[str]]:
    """Endpoint name → parameter names, read (not run) from a backend .mcn file.
    Returns {} when the file is missing or doesn't parse."""
    from .lexer import Lexer
    from .parser import Parser
    try:
        program = Parser(Lexer(Path(path).read_text(encoding="utf-8")).tokenize()).parse()
    except Exception:
        return {}
    found: Dict[str, List[str]] = {}
    for stmt in program.body:
        if isinstance(stmt, ast.ServiceDecl):
            for ep in stmt.endpoints:
                found[ep.name] = list(ep.params)
    return found


def _pascal(name: str) -> str:
    """snake_case / kebab-case → PascalCase."""
    return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def _camel(name: str) -> str:
    """snake_case → camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


def prettier_json(data, indent: int = 0, width: int = 120) -> str:
    """JSON laid out like Prettier: objects one key per line, short arrays on one line."""
    pad = " " * indent
    if isinstance(data, dict):
        if not data:
            return "{}"
        items = [f'{pad}  {json.dumps(k)}: {prettier_json(v, indent + 2, width)}' for k, v in data.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(data, list):
        inline = "[" + ", ".join(prettier_json(v, indent, width) for v in data) + "]"
        if "\n" not in inline and len(pad) + len(inline) + 20 <= width:
            return inline
        return "[\n" + ",\n".join(f"{pad}  {prettier_json(v, indent + 2, width)}" for v in data) + f"\n{pad}]"
    return json.dumps(data)


def _ts_object(pairs: List[str]) -> str:
    """{ a, b: 1 }: a key with a same-named value uses the shorthand."""
    tidy = [p.split(": ", 1)[0] if re.match(r"^(\w+): \1$", p) else p for p in pairs]
    return "{ " + ", ".join(tidy) + " }" if tidy else "{}"


def _unwrap_parens(ts: str) -> str:
    """((a > 0)) → a > 0 when the parentheses wrap the whole expression."""
    while ts.startswith("(") and _balanced_end(ts, 0) == len(ts):
        ts = ts[1:-1]
    return ts


_JSX_TIDY = [
    (re.compile(r"<(\w+(?:\.\w+)?) >"), r"<\1>"),                                   # <Card > → <Card>
    (re.compile(r'(\s\w+)=\{"([^"\\{}<>]*)"\}'), r'\1="\2"'),                       # x={"a"} → x="a"
    (re.compile(r'>\{"([^"\\{}<>]*[^"\\{}<>\s])"\}<'), r">\1<"),                    # >{"Text"}< → >Text<
]


def tidy_jsx(line: str) -> str:
    for pattern, repl in _JSX_TIDY:
        line = pattern.sub(repl, line)
    return line


def endpoint_tables_from_backend(path) -> Dict[str, str]:
    """Endpoint name → table, for endpoints that return a table's rows unchanged
    (SELECT * FROM table, no joins or JSON parsing), so their rows can be typed."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return {}
    found: Dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)endpoint\s+(\w+)\s*\(", line)
        if not m:
            continue
        indent, body = len(m.group(1)), []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        code = "\n".join(body)
        tables = set(re.findall(r"SELECT\s+\*\s+FROM\s+(\w+)", code, re.I))
        if len(tables) == 1 and not re.search(r"\bJOIN\b|json_parse|\bmap\(|\bfor\b", code, re.I):
            found[m.group(2)] = tables.pop()
    return found


def _split_props(text: str) -> List[str]:
    """JSX props split at top-level spaces (not inside {}, (), [] or quotes)."""
    props, cur, depth, quote = [], "", 0, ""
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'`":
            quote = ch
        elif ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                props.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        props.append(cur)
    return props


def wrap_jsx(line: str, width: int = 120) -> List[str]:
    """A tag too long for one line, with one prop per line (as Prettier writes it)."""
    if len(line) <= width:
        return [line]
    m = re.match(r"^(\s*)<([A-Za-z][\w.]*) (.+?)\s*(/?>)$", line)
    if not m or "<" in m.group(3).replace("=>", ""):
        return [line]
    pad, tag, rest, close = m.groups()
    props = _split_props(rest)
    if len(props) < 2 or not all(re.match(r"^[\w-]+(=|$)", p) for p in props):
        return [line]
    out = [f"{pad}<{tag}"]
    for prop in props:
        line = f"{pad}  {prop}"
        arrow = re.match(r"^([\w-]+=\{(?:async )?\([^()]*\) =>) (.+)\}$", prop)
        if len(line) > width and arrow:
            # A long callback breaks after the arrow, as Prettier writes it
            out += [f"{pad}  {arrow.group(1)}", f"{pad}    {arrow.group(2)}", f"{pad}  }}"]
        else:
            out.append(line)
    return out + [f"{pad}{close}"]


def _reassigned(stmts, name: str) -> bool:
    """Whether a later statement (in nested blocks too) assigns to name again."""
    for st in stmts or []:
        if isinstance(st, (ast.AssignStmt, getattr(ast, "CompoundAssignStmt", ast.AssignStmt))) and st.name == name:
            return True
        if any(_reassigned(getattr(st, a, None), name) for a in ("then_body", "else_body", "body")):
            return True
    return False


def code_only(code: str, jsx: bool = False) -> str:
    """Code with the text of string literals removed; ${...} parts of template literals are kept.
    For JSX only double-quoted strings are removed: text between tags isn't quoted."""
    out, i, n = [], 0, len(code)
    quotes = '"' if jsx else "\"'`"
    while i < n:
        ch = code[i]
        if ch not in quotes:
            out.append(ch)
            i += 1
            continue
        quote, i = ch, i + 1
        out.append(quote)
        while i < n and code[i] != quote:
            if code[i] == "\\":
                i += 2
                continue
            if quote == "`" and code.startswith("${", i):
                # Keep the expression, up to its matching brace
                depth, j = 1, i + 2
                while j < n and depth:
                    depth += (code[j] == "{") - (code[j] == "}")
                    j += 1
                out.append(" " + code_only(code[i + 2:j - 1]) + " ")
                i = j
                continue
            if quote != "`" and code[i] == "\n":
                break                   # unterminated: stop at the line end
            i += 1
        out.append(quote)
        i += 1
    return "".join(out)


def _uses(code: str, name: str, stripped: bool = False) -> bool:
    """Whether code reads name (outside string text). stripped: code_only() was already applied."""
    # Not an object key (`name: 1`) or a JSX prop name (`name={...}`)
    pattern = rf"(?<![\w$.]){re.escape(name)}(?![\w$]|:|=[{{\"])"
    return re.search(pattern, code if stripped else code_only(code)) is not None


def _prune_component(imports: List[str], icon_binding: List[str], hooks: List[str],
                     handlers: List[str], jsx_lines: List[str], type_defs: List[str]):
    """Drop what the component never uses (lint-clean output): unused state, setters,
    hook dependencies, imports and icons."""
    # Hook dependencies the callback doesn't read
    def prune_deps(handler: str) -> str:
        m = re.search(r"\}, \[([^\]]*)\]\)\s*$", handler)
        if not m:
            return handler
        body = handler[:m.start()]
        deps = [d.strip() for d in m.group(1).split(",") if d.strip() and _uses(body, d.strip())]
        return handler[:m.start()] + "}, [" + ", ".join(deps) + "])" + handler[m.end():]
    handlers = [prune_deps(h) for h in handlers]

    # State whose value or setter is never used
    jsx_code = code_only("\n".join(jsx_lines), jsx=True)
    handlers_code = code_only("\n".join(handlers))
    kept = []
    for i, line in enumerate(hooks):
        m = re.match(r"^(\s*)const \[(\w+), (\w+)\] = (useState.*)$", line)
        if not m:
            kept.append(line)
            continue
        others = "\n".join([code_only("\n".join(hooks[:i] + hooks[i + 1:])), handlers_code, jsx_code])
        pad, name, setter, rest = m.groups()
        used_value, used_setter = _uses(others, name, True), _uses(others, setter, True)
        if not used_value and not used_setter:
            continue
        if not used_setter:
            kept.append(f"{pad}const [{name}] = {rest}")
        elif not used_value:
            kept.append(f"{pad}const [, {setter}] = {rest}")
        else:
            kept.append(line)
    hooks = kept

    body = "\n".join([code_only("\n".join(hooks + handlers + type_defs)), jsx_code])
    # Icons the render never shows
    if icon_binding:
        m = re.match(r"const \{ (.*) \} = icons", icon_binding[0])
        names = [n for n in m.group(1).split(", ") if _uses(body, n, True)] if m else []
        icon_binding = [f"const {{ {', '.join(names)} }} = icons", ""] if names else []
    body_with_icons = body + "\n".join(icon_binding)
    # Imports nothing uses
    out = []
    for line in imports:
        m = re.match(r'^import (type )?\{\s*([^}]+)\s*\} from (.+)$', line)
        if not m or line.startswith('import React'):
            out.append(line)
            continue
        names = [n.strip() for n in m.group(2).split(",") if n.strip()]
        keep = [n for n in names if _uses(body_with_icons, n.split(" as ")[-1].replace("type ", "").strip(), True)]
        if keep:
            out.append(f"import {m.group(1) or ''}{{ {', '.join(keep)} }} from {m.group(3)}")
    react = re.match(r'^import (React, )?\{ ([^}]+) \} from "react"$', out[0]) if out else None
    if react:
        hooks_used = [h for h in react.group(2).split(", ") if _uses(body, h, True)]
        default = "React, " if react.group(1) else ""
        out[0] = f'import {default}{{ {", ".join(hooks_used)} }} from "react"' if hooks_used else \
            ('import React from "react"' if default else "")
        out = [ln for ln in out if ln]
    return out, icon_binding, hooks, handlers


def _jsx_prop(name: str, ts: str) -> str:
    """name="text" for a plain string literal, name={expr} otherwise."""
    if len(ts) >= 2 and ts[0] == ts[-1] == '"' and "\\" not in ts and '"' not in ts[1:-1] \
            and "{" not in ts and "<" not in ts:
        return f"{name}={ts}"
    return f"{name}={{{ts}}}"


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def _balanced_end(text: str, open_idx: int) -> int:
    """Index just past the ")" matching the "(" at open_idx (quotes respected); -1 if unbalanced."""
    depth, quote, i = 0, "", open_idx
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in "\"'`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def split_await(text: str, marker: str) -> Optional[Tuple[str, str, str]]:
    """For text holding exactly one "(await <marker>...)", return (before, call, after).
    Used to run independent backend calls together."""
    if text.count("await ") != 1:
        return None
    start = text.find("(await " + marker)
    if start < 0:
        return None
    end = _balanced_end(text, start)
    if end < 0:
        return None
    return text[:start], text[start + len("(await "):end - 1], text[end:]


def names_in(node) -> Set[str]:
    """Every variable name an expression reads."""
    found: Set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Variable):
            found.add(n.name)
        if isinstance(n, (list, tuple)):
            stack.extend(n)
        elif hasattr(n, "__dict__"):
            stack.extend(v for v in vars(n).values() if isinstance(v, (list, tuple)) or hasattr(v, "__dict__"))
    return found


_SQL_NUMBER = ("INT", "REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")


def tables_from_backend(path) -> Dict[str, Dict[str, str]]:
    """Table name → {column: TypeScript type}, read from CREATE TABLE statements in a backend file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError):
        return {}
    tables: Dict[str, Dict[str, str]] = {}
    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)[\"`]?\s*\(", text, re.I):
        end = _balanced_end(text, m.end() - 1)
        if end < 0:
            continue
        body, depth, parts, cur = text[m.end():end - 1], 0, [], ""
        for ch in body:
            depth += (ch == "(") - (ch == ")")
            if ch == "," and depth == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        parts.append(cur)
        cols: Dict[str, str] = {}
        for part in parts:
            words = part.strip().split()
            if len(words) < 1 or words[0].upper() in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"):
                continue
            name = words[0].strip('"`')
            sql_type = words[1].upper() if len(words) > 1 else ""
            if not re.match(r"^[A-Za-z_]\w*$", name):
                continue
            cols[name] = ("number" if any(t in sql_type for t in _SQL_NUMBER)
                          else "boolean" if "BOOL" in sql_type else "string")
        if cols:
            tables[m.group(1)] = cols
    return tables


# MCN built-ins that run in the browser instead of becoming backend API calls
_TS_BUILTINS = {
    "str":   lambda a: f"String({a[0] if a else ''})",
    "len":   lambda a: f"({a[0]}).length",
    "int":   lambda a: f"Math.trunc(Number({a[0]}))",
    "float": lambda a: f"Number({a[0]})",
    "round": lambda a: (f"Number(Number({a[0]}).toFixed({a[1]}))" if len(a) > 1
                        else f"Math.round({a[0]})"),
    "abs":   lambda a: f"Math.abs({a[0]})",
    "min":   lambda a: f"Math.min({', '.join(a)})",
    "max":   lambda a: f"Math.max({', '.join(a)})",
    "upper": lambda a: f"String({a[0]}).toUpperCase()",
    "lower": lambda a: f"String({a[0]}).toLowerCase()",
    "join":  lambda a: f"({a[0]}).join({a[1] if len(a) > 1 else repr(',')})",
}


def _expr_to_ts(expr: Optional[ast.Expr],
                local_vars: Optional[Dict[str, str]] = None) -> str:
    """Convert a simple MCN expression to a TypeScript expression string.

    local_vars: mapping of MCN variable name → local TS identifier (e.g. temp
    vars captured with ``const _items = await ...``).
    """
    lv = local_vars or {}
    if expr is None:
        return '""'
    if isinstance(expr, ast.Literal):
        if expr.value is None:
            return "null"
        if isinstance(expr.value, str):
            return json.dumps(expr.value)
        if isinstance(expr.value, bool):
            return "true" if expr.value else "false"
        return str(expr.value)
    if isinstance(expr, ast.Variable):
        if expr.name in _JS_RESERVED:
            return _handler_name(expr.name)
        return lv.get(expr.name, expr.name)
    if isinstance(expr, ast.Property):
        obj = _expr_to_ts(expr.object, lv)
        return f"{obj}{'?.' if getattr(expr, 'safe', False) else '.'}{expr.name}"
    if isinstance(expr, ast.Index):
        return f"{_expr_to_ts(expr.object, lv)}[{_expr_to_ts(expr.index, lv)}]"
    if isinstance(expr, ast.Unary):
        operand = _expr_to_ts(expr.operand, lv)
        return f"!({operand})" if expr.operator in ("not", "!") else f"{expr.operator}{operand}"
    if isinstance(expr, ast.TernaryExpr):
        return (f"({_expr_to_ts(expr.condition, lv)} ? {_expr_to_ts(expr.then_expr, lv)}"
                f" : {_expr_to_ts(expr.else_expr, lv)})")
    if isinstance(expr, ast.Binary):
        left  = _expr_to_ts(expr.left, lv)
        right = _expr_to_ts(expr.right, lv)
        op    = expr.operator
        if op == "+" and (isinstance(expr.left, ast.Array) or isinstance(expr.right, ast.Array)):
            # list + [x]  →  array concatenation, not string concatenation
            return f"[...({left}), ...({right})]"
        if op == "+" and not any(isinstance(e, ast.Literal) and isinstance(e.value, str)
                                 for e in (expr.left, expr.right)):
            # Numbers add, strings concatenate: same as MCN
            return f"({left} + {right})"
        if op == "+":
            # Produce a template literal: `${left}${right}`
            # Strip surrounding quotes from string literals so they merge cleanly
            def _unwrap(ts: str) -> str:
                if ts.startswith('"') and ts.endswith('"'):
                    return ts[1:-1].replace("`", "\\`").replace("${", "\\${")
                if ts.startswith("`") and ts.endswith("`") and ts.count("`") == 2:
                    return ts[1:-1]
                return f"${{{ts}}}"
            return f"`{_unwrap(left)}{_unwrap(right)}`"
        op = {"and": "&&", "or": "||", "==": "===", "!=": "!=="}.get(op, op)
        return f"({left} {op} {right})"
    if isinstance(expr, ast.Call):
        args_ts = [_expr_to_ts(a, lv) for a in expr.arguments]
        if isinstance(expr.callee, ast.Property):
            # obj.method(args) → same call in TypeScript
            return f"{_expr_to_ts(expr.callee, lv)}({', '.join(args_ts)})"
        if isinstance(expr.callee, ast.Variable) and expr.callee.name in _TS_BUILTINS:
            return _TS_BUILTINS[expr.callee.name](args_ts)
        if isinstance(expr.callee, ast.Variable):
            fn = expr.callee.name
            if fn == "notify":
                return f"notify({', '.join(_expr_to_ts(a, lv) for a in expr.arguments)})"
            if fn in ("toast", "log", "confirm", "alert"):
                args = ", ".join(_expr_to_ts(a, lv) for a in expr.arguments)
                if fn == "log":
                    return f"console.log({args})"
                if fn == "confirm":
                    return f"window.confirm({args})"
                if fn == "alert":
                    return f"window.alert({args})"
                return f"toast({args})"

            # Build the payload: the endpoint's parameter names when the backend is
            # known, otherwise the argument variable names
            pairs = []
            params = _ENDPOINT_PARAMS.get(fn)
            if params is not None:
                for name, a in zip(params, expr.arguments):
                    pairs.append(f"{name}: {_expr_to_ts(a, lv)}")
                return f"(await api.post(\"/{fn}\", {_ts_object(pairs)}))"
            for i, a in enumerate(expr.arguments):
                if isinstance(a, ast.Variable):
                    key = a.name[5:] if a.name.startswith("edit_") else a.name
                    pairs.append(f"{key}: {a.name}")
                elif isinstance(a, ast.Property):
                    key = a.name
                    pairs.append(f"{key}: {_expr_to_ts(a, lv)}")
                else:
                    # Fallback: if it's a literal or complex expr, use a generic key
                    pairs.append(f"arg{i}: {_expr_to_ts(a, lv)}")
            return f"(await api.post(\"/{fn}\", {_ts_object(pairs)}))"
        return '""'
    if isinstance(expr, ast.Array):
        return "[" + ", ".join(_expr_to_ts(e, lv) for e in expr.elements) + "]"
    if hasattr(ast, 'MCNObject') and isinstance(expr, getattr(ast, 'MCNObject')):
        props = []
        for k, v in expr.properties:
            if isinstance(k, getattr(ast, 'Literal')) and isinstance(k.value, str):
                key_str = json.dumps(k.value)
            elif isinstance(k, getattr(ast, 'Variable')):
                key_str = k.name
            else:
                key_str = f"[{_expr_to_ts(k, lv)}]"
            props.append(f"{key_str}: {_expr_to_ts(v, lv)}")
        return _ts_object(props)
    return '""'


def _get_entity_names(comp_name: str, known=None) -> Tuple[str, str]:
    """Given a component name like DealsTable, return (singular, plural) entity names (e.g. ('deal', 'deals'))."""
    name = comp_name.replace("Table", "")
    lower = name.lower()

    mappings = {
        "deals": ("deal", "deals"),
        "contacts": ("contact", "contacts"),
        "companies": ("company", "companies"),
        "activities": ("activity", "activities"),
        "item": ("item", "items"),
        "items": ("item", "items"),
    }

    if lower in mappings:
        return mappings[lower]

    if lower.endswith("ies"):
        candidates = [lower[:-3] + "y"]
    elif lower.endswith(("sses", "xes", "ches", "shes", "zes")):
        candidates = [lower[:-2], lower[:-1]]            # boxes → box, branches → branch
    elif lower.endswith("s") and not lower.endswith("ss"):
        candidates = [lower[:-1], lower[:-2]]            # resources → resource
    else:
        return lower, lower + "s"

    # Prefer the spelling the backend's endpoints actually use
    for singular in candidates:
        if any(f"{verb}_{singular}" in (_ENDPOINT_PARAMS if known is None else known)
               for verb in ("create", "update", "delete", "get")):
            return singular, lower
    return candidates[0], lower



def crud_endpoint_fits(name: str, columns: List[str], endpoints: Dict[str, List[str]]) -> bool:
    """Whether a table screen can call this endpoint correctly: it exists, and the table's columns
    (plus the row's id) supply every parameter. Without backend information, assume it does."""
    if not endpoints:
        return True
    if name not in endpoints:
        return False
    return set(endpoints[name] or []) <= set(columns) | {"id"}


# ── main compiler class ────────────────────────────────────────────────────────

class UICompiler:
    """
    Compile MCN component/app AST → React + shadcn/ui TypeScript source files.

    Usage:
        compiler = UICompiler(output_dir=Path("my_app/frontend"))
        compiler.compile(evaluator)   # evaluator has .components and .app_decl
    """

    def __init__(self, output_dir: Path, endpoints: Optional[Dict[str, List[str]]] = None,
                 tables: Optional[Dict[str, Dict[str, str]]] = None):
        """endpoints: backend endpoint name → parameter names, if known.
        tables: table name → column types (default: read from ../backend/main.mcn)."""
        self.out              = Path(output_dir)
        backend = self.out.parent / "backend" / "main.mcn"
        self.tables = tables if tables is not None else tables_from_backend(backend)
        self.endpoint_tables = endpoint_tables_from_backend(backend) if tables is None else {}
        _ENDPOINT_PARAMS.clear()
        _ENDPOINT_PARAMS.update(endpoints or {})
        self._shadcn_needed: Set[str] = set()   # shadcn package slugs to install
        self._current_comp: Optional[ast.ComponentDecl] = None
        self._extra_imports: Set[str] = set()   # per-component extra import lines

    # ── Public API ─────────────────────────────────────────────────────────────

    def compile(self, evaluator) -> List[Path]:
        """
        Main entry point. Returns list of written files.
        evaluator must be an Evaluator instance after execute_program() was called.
        """
        written: List[Path] = []

        src = self.out / "src"
        (src / "components" / "ui").mkdir(parents=True, exist_ok=True)
        (src / "pages").mkdir(parents=True, exist_ok=True)
        (src / "services").mkdir(parents=True, exist_ok=True)
        (src / "hooks").mkdir(parents=True, exist_ok=True)
        (src / "lib").mkdir(parents=True, exist_ok=True)

        # The MCN UI kit: src/components/ui/* and src/lib/utils.ts
        ui_written = self._write_ui_components(src)
        written.extend(ui_written)

        app_decl: Optional[ast.AppDecl] = evaluator.app_decl
        components: Dict[str, ast.ComponentDecl] = evaluator.components

        theme = app_decl.theme if app_decl else "default"

        # 1. Compile each component
        for name, comp in components.items():
            path = src / "components" / f"{name}.tsx"
            path.write_text(self._compile_component(comp))
            written.append(path)
            print(f"  write  {path.relative_to(self.out.parent)}")

        # Types, lint, format and test setup
        (src / "test").mkdir(parents=True, exist_ok=True)
        support = {
            src / "types.ts": self._gen_types_ts(),
            src / "vite-env.d.ts": self._gen_vite_env(),
            src / "test" / "setup.ts": self._TEST_SETUP,
            self.out / "eslint.config.js": self._ESLINT_CONFIG,
            self.out / ".prettierrc": self._PRETTIER_CONFIG,
            # Machine-generated files are left as they are
            self.out / ".prettierignore": "dist\nnode_modules\nsrc/preview.css\nsrc/components/ui/icons-data.ts\n",
        }
        for path, text in support.items():
            path.write_text(text)
            written.append(path)
        if components:
            test_path = src / "test" / "screens.test.tsx"
            test_path.write_text(self._gen_screens_test(components))
            written.append(test_path)

        # 2. Generate API service layer
        api_path = src / "services" / "api.ts"
        api_path.write_text(self._gen_api_service(app_decl))
        written.append(api_path)
        print(f"  write  {api_path.relative_to(self.out.parent)}")

        # 3. Generate App.tsx
        app_tsx = src / "App.tsx"
        app_tsx.write_text(self._gen_app_tsx(app_decl, components))
        written.append(app_tsx)
        print(f"  write  {app_tsx.relative_to(self.out.parent)}")

        # 4. Generate main.tsx
        main_tsx = src / "main.tsx"
        main_tsx.write_text(self._gen_main_tsx())
        written.append(main_tsx)
        print(f"  write  {main_tsx.relative_to(self.out.parent)}")

        # 5. globals.css with theme variables
        css_path = src / "globals.css"
        css_path.write_text(self._gen_globals_css(theme))
        written.append(css_path)
        print(f"  write  {css_path.relative_to(self.out.parent)}")

        # 6. package.json
        pkg_path = self.out / "package.json"
        pkg_path.write_text(self._gen_package_json(app_decl))
        written.append(pkg_path)
        print(f"  write  {pkg_path.relative_to(self.out.parent)}")

        # 7. tailwind.config.ts
        tw_path = self.out / "tailwind.config.ts"
        tw_path.write_text(self._gen_tailwind_config())
        written.append(tw_path)
        print(f"  write  {tw_path.relative_to(self.out.parent)}")

        # 8. vite.config.ts
        vite_path = self.out / "vite.config.ts"
        vite_path.write_text(self._gen_vite_config())
        written.append(vite_path)
        print(f"  write  {vite_path.relative_to(self.out.parent)}")

        # 9. postcss.config.js
        postcss_path = self.out / "postcss.config.js"
        postcss_path.write_text(self._gen_postcss_config())
        written.append(postcss_path)
        print(f"  write  {postcss_path.relative_to(self.out.parent)}")

        # 10. components.json (shadcn config)
        shadcn_cfg = self.out / "components.json"
        shadcn_cfg.write_text(self._gen_shadcn_config())
        written.append(shadcn_cfg)
        print(f"  write  {shadcn_cfg.relative_to(self.out.parent)}")

        # 10. tsconfig.json
        tsconfig = self.out / "tsconfig.json"
        tsconfig.write_text(self._gen_tsconfig())
        written.append(tsconfig)
        print(f"  write  {tsconfig.relative_to(self.out.parent)}")

        # 11. tsconfig.node.json
        tsconfig_node = self.out / "tsconfig.node.json"
        tsconfig_node.write_text(prettier_json({
            "compilerOptions": {
                "composite":        True,
                "skipLibCheck":     True,
                "module":           "ESNext",
                "moduleResolution": "bundler",
                "allowSyntheticDefaultImports": True,
            },
            "include": ["vite.config.ts", "tailwind.config.ts"],
        }) + "\n")
        written.append(tsconfig_node)
        print(f"  write  {tsconfig_node.relative_to(self.out.parent)}")

        # 12. index.html
        index_html = self.out / "index.html"
        title = app_decl.title if app_decl else "MCN App"
        index_html.write_text(self._gen_index_html(title))
        written.append(index_html)
        print(f"  write  {index_html.relative_to(self.out.parent)}")

        # Once the project's dependencies are installed, Prettier formats the output exactly
        prettier = self.out / "node_modules" / ".bin" / "prettier"
        if prettier.exists():
            import subprocess
            try:
                subprocess.run([str(prettier), "--write", "--log-level", "warn", "src", "index.html", "*.json", "*.ts"],
                               cwd=self.out, capture_output=True, timeout=120)
            except (OSError, subprocess.SubprocessError):
                pass

        return written

    # ── Component compiler ─────────────────────────────────────────────────────

    # ── Types ──────────────────────────────────────────────────────────────────

    def _assigned_from(self, stmts, state_name: str) -> Set[str]:
        """Names read by every assignment to state_name in these statements (nested blocks too)."""
        found: Set[str] = set()
        for st in stmts or []:
            if isinstance(st, ast.AssignStmt) and st.name == state_name:
                found |= names_in(st.value)
            for attr in ("then_body", "else_body", "body"):
                found |= self._assigned_from(getattr(st, attr, None), state_name)
        return found

    def _table_type(self, state_name: str) -> Optional[str]:
        """The row interface for a list state that's only ever filled from endpoints
        returning one table's rows unchanged (list_orders → SELECT * FROM orders → Order)."""
        comp = self._current_comp
        sources: Set[str] = set()
        for h in (comp.handlers if comp else []):
            sources |= self._assigned_from(h.body, state_name)
        tables = {self.endpoint_tables[src] for src in sources if src in self.endpoint_tables}
        called = {src for src in sources if src in _ENDPOINT_PARAMS}
        if len(tables) == 1 and called <= set(self.endpoint_tables):
            table = tables.pop()
            if table in self.tables:
                return _pascal(_singular(table))
        return None

    def _row_states(self, elements) -> Set[str]:
        """States the render tree uses as rows (data tables, charts, kanban, lists)."""
        found: Set[str] = set()
        for el in elements or []:
            if el.tag in ("data_table", "kanban", "table") and not any(
                    a.key in ("data", "rows", "items", "cards") for a in el.attrs):
                comp = self._current_comp
                first = next((st.name for st in (comp.states if comp else []) if isinstance(st.value, ast.Array)), None)
                if first:
                    found.add(first)
            for a in el.attrs:
                if a.key in ("data", "rows", "items", "cards", "agents", "workflows", "messages") \
                        and isinstance(a.value, ast.Variable):
                    found.add(a.value.name)
            found |= self._row_states(el.children)
        return found

    def _literal_ts_type(self, value) -> str:
        if isinstance(value, ast.Variable) and value.name in ("true", "false"):
            return "boolean"
        if isinstance(value, ast.Literal):
            v = value.value
            if isinstance(v, bool):
                return "boolean"
            if isinstance(v, (int, float)):
                return "number"
            if isinstance(v, str):
                return "string"
            return "BackendValue"
        if isinstance(value, ast.MCNObject):
            return "Row"
        if isinstance(value, ast.Array):
            return self._array_type(value, None)
        return "BackendValue"

    def _array_type(self, value: ast.Array, state_name: Optional[str], rows: bool = False) -> str:
        kinds = {self._literal_ts_type(e) for e in value.elements}
        if len(kinds) == 1 and kinds != {"BackendValue"}:
            return f"{kinds.pop()}[]"
        if not value.elements and state_name:
            table = self._table_type(state_name)
            if table:
                self._type_imports.add(table)
                return f"{table}[]"
            if rows:
                return "Row[]"
        return "BackendValue[]"

    def _state_generic(self, comp: ast.ComponentDecl, st, rows: Set[str]) -> str:
        """The useState type parameter for a state, from its starting value."""
        v = st.value
        if isinstance(v, ast.Array):
            return f"<{self._array_type(v, st.name, st.name in rows)}>"
        if isinstance(v, ast.MCNObject):
            name = _pascal(comp.name) + _pascal(st.name)
            fields = []
            for k, val in v.properties:
                key = k.name if isinstance(k, ast.Variable) else (k.value if isinstance(k, ast.Literal) else None)
                if isinstance(key, str):
                    prop = key if re.match(r"^[A-Za-z_$][\w$]*$", key) else json.dumps(key)
                    fields.append(f"  {prop}: {self._literal_ts_type(val)}")
            self._type_defs.append(f"interface {name} extends Row {{\n" + "\n".join(fields) + "\n}" if fields
                                   else f"type {name} = Row")
            return f"<{name}>"
        if (isinstance(v, ast.Literal) and v.value is None) or (isinstance(v, ast.Variable) and v.name == "null"):
            return "<Row | null>" if st.name.endswith(("_item", "selected", "current")) or st.name == "selected" else "<BackendValue>"
        return ""

    def _gen_types_ts(self) -> str:
        lines = [
            "/**",
            " * Types for data from the backend.",
            " *",
            " * Tables come from the CREATE TABLE statements in backend/main.mcn. MCN code is",
            " * dynamically typed, so values MCN can't know the type of are BackendValue.",
            " */",
            "",
            "// eslint-disable-next-line @typescript-eslint/no-explicit-any",
            "export type BackendValue = any",
            "",
            "/** A record from the backend: known fields are typed, others are BackendValue. */",
            "export type Row = Record<string, BackendValue>",
        ]
        for table, cols in self.tables.items():
            lines += ["", f"/** A row of the `{table}` table. */",
                      f"export interface {_pascal(_singular(table))} extends Row {{",
                      *[f"  {c}: {t}" for c, t in cols.items()], "}"]
        return "\n".join(lines) + "\n"

    def _compile_component(self, comp: ast.ComponentDecl) -> str:
        """Compile a single ComponentDecl → .tsx file content."""
        self._current_comp = comp
        self._extra_imports = set()
        self._type_defs: List[str] = []
        self._type_imports: Set[str] = set()
        self._tmp_count = 0

        shadcn_imports: Dict[str, List[str]] = {}

        # Collect shadcn imports needed by this component's render tree
        if comp.render:
            self._collect_imports(comp.render.elements, shadcn_imports)

        def _extract_table_columns(elements: List[ast.UIElement]) -> List[str]:
            cols = []
            for el in elements:
                if el.tag == "table_head" and el.text and hasattr(el.text, "value"):
                    val = str(el.text.value)
                    clean_text = val.strip('"').strip("'")
                    if clean_text:
                        cols.append(clean_text)
                else:
                    cols.extend(_extract_table_columns(el.children))
            return cols

        # Detect CRUD mode
        table_columns = list(dict.fromkeys(_extract_table_columns(comp.render.elements))) if comp.render else []
        has_crud_from_table = bool(table_columns)
        has_crud_from_states = any(s.name == "edit_item" for s in comp.states)
        has_crud = has_crud_from_table or has_crud_from_states
        # Only offer the create, edit and delete actions whose endpoints exist.
        # Without backend information (compiling a UI on its own), offer all three.
        _crud_one = _get_entity_names(comp.name)[0]
        self._crud_ops = {
            verb: has_crud and crud_endpoint_fits(
                f"{verb}_{_crud_one}",
                table_columns + ([st.name[5:] for st in comp.states if st.name.startswith("edit_")] if verb == "update" else []),
                _ENDPOINT_PARAMS)
            for verb in ("create", "update", "delete")
        }
        crud = self._crud_ops

        # Determine which React hooks are needed
        has_load_handler   = any(h.event == "load" for h in comp.handlers)
        has_other_handlers = any(h.event != "load" for h in comp.handlers)
        react_hooks: List[str] = ["useState"]
        if has_load_handler:
            react_hooks.append("useEffect")
        if has_other_handlers or has_crud or has_load_handler:
            react_hooks.append("useCallback")

        imports: List[str] = [
            f'import React, {{ {", ".join(react_hooks)} }} from "react"',
            'import { api } from "../services/api"',
        ]
        row_states = self._row_states(comp.render.elements if comp.render else [])
        for pkg_path, names in sorted(shadcn_imports.items()):
            imports.append(f'import {{ {", ".join(sorted(set(names)))} }} from "{pkg_path}"')

        # useState hooks from state declarations
        hooks: List[str] = []
        defined_states = set()
        for s in comp.states:
            var_name   = s.name
            defined_states.add(var_name)
            setter     = "set" + _pascal(var_name)
            default_ts = _expr_to_ts(s.value)
            generic = self._state_generic(comp, s, row_states)
            hooks.append(f"  const [{var_name}, {setter}] = useState{generic}({default_ts})")

        # Automatically inject CRUD states if they aren't explicitly defined
        synthetic_edit_fields = []
        synthetic_create_fields = []
        if has_crud:
            if "edit_item" not in defined_states:
                hooks.append(f"  const [edit_item, setEditItem] = useState<Row | null>(null)")
            for col in table_columns:
                edit_var = f"edit_{col}"
                if edit_var not in defined_states:
                    hooks.append(f"  const [{edit_var}, set{_pascal(edit_var)}] = useState('')")
                    synthetic_edit_fields.append(edit_var)
                create_var = f"create_{col}"
                if create_var not in defined_states:
                    hooks.append(f"  const [{create_var}, set{_pascal(create_var)}] = useState('')")
                    synthetic_create_fields.append(create_var)
            
            # Global Search and Pagination
            hooks.append(f"  const [searchQuery, setSearchQuery] = useState('')")
            hooks.append(f"  const [currentPage, setCurrentPage] = useState(1)")
            hooks.append(f"  const [pageSize, setPageSize] = useState(10)")
            arr_state = next((s.name for s in comp.states if isinstance(s.value, ast.Array)), "items")
            hooks.append(f"  const filteredItems = React.useMemo(() => {{\n    const rows = Array.isArray({arr_state}) ? {arr_state} : []\n    if (!searchQuery) return rows\n    const q = searchQuery.toLowerCase()\n    return rows.filter((item: Row) => Object.values(item).some((v) => String(v).toLowerCase().includes(q)))\n  }}, [{arr_state}, searchQuery])")

        if has_crud:
            entity_singular, entity_plural = _get_entity_names(comp.name)
            entity = entity_singular
            
            # Fields with edit_ prefix (both explicitly defined and auto-injected)
            edit_fields_names = [s.name for s in comp.states if s.name.startswith("edit_") and s.name not in ("edit_item", "edit_item_id")]
            edit_fields_names.extend(synthetic_edit_fields)
            
            field_setters = "\n    ".join(
                f"set{_pascal(name)}(row.{name[5:]} ?? '')"
                for name in edit_fields_names
            )
            save_payload_fields = ", ".join(
                f"{name[5:]}: {name}" for name in edit_fields_names
                if name[5:] != "id"   # id is already sent as _mcnEditItemId
            )
            hooks.append(f"  const [_mcnEditItemId, set_mcnEditItemId] = useState<number | null>(null)")
            hooks.append(f"  const [_mcnShowEditModal, set_mcnShowEditModal] = useState(false)")
            hooks.append(f"  const [_mcnShowCreateModal, set_mcnShowCreateModal] = useState(false)")


        # Event handlers from on blocks
        handlers: List[str] = []
        if has_load_handler:
            hooks.append("  const [loadState, setLoadState] = useState<LoadState>({ loading: true, error: null })")
        for h in comp.handlers:
            fn_name = _handler_name(h.event)
            body_ts = self._stmts_to_ts(h.body, indent=6)
            if h.event == "load":
                load_deps = ", ".join(st.name for st in comp.states if _uses(body_ts, st.name))
                # Loads the screen's data; failures show with a Retry button
                handlers.append(
                    f"  const loadScreen = useCallback(async () => {{\n"
                    f"    setLoadState({{ loading: true, error: null }})\n"
                    f"    let failure: string | null = null\n"
                    f"    try {{\n"
                    f"{body_ts}"
                    f"    }} catch (err) {{\n"
                    f"      failure = errorMessage(err)\n"
                    f"    }} finally {{\n"
                    f"      setLoadState({{ loading: false, error: failure }})\n"
                    f"    }}\n"
                    f"  }}, [{load_deps}])\n"
                    f"\n"
                    + (f"  useEffect(() => {{\n"
                       f"    void loadScreen()\n"
                       f"  }}, [loadScreen])" if not load_deps else
                       f"  // Runs once when the screen opens, like MCN's `on load`; Retry uses the latest values\n"
                       f"  useEffect(() => {{\n"
                       f"    void loadScreen()\n"
                       f"    // eslint-disable-next-line react-hooks/exhaustive-deps\n"
                       f"  }}, [])")
                )
            else:
                dep_names = ", ".join(s.name for s in comp.states if _uses(body_ts, s.name))
                # A handler wired to a kit component receives the row, item,
                # agent, workflow or message as its argument
                # ...unless the component has state of that name, which the handler means instead
                state_names = {st.name for st in comp.states}
                implicit = [n for n in ("row", "item", "agent", "workflow", "message")
                            if n not in state_names and _uses(body_ts, n)]
                bind_args = "".join(f"    const {n} = e as Row\n" for n in implicit)
                handlers.append(
                    f"  const {fn_name} = useCallback(async (e?: unknown) => {{\n"
                    f"    preventDefault(e)\n"
                    f"{bind_args}"
                    f"    try {{\n"
                    f"{body_ts}"
                    f"    }} catch (err) {{\n"
                    f"      notify(errorMessage(err), \"error\")\n"
                    f"    }}\n"
                    f"  }}, [{dep_names}])"
                )

        # Inject CRUD helper functions for components with edit_item state
        if has_crud:
            entity_singular, entity_plural = _get_entity_names(comp.name)
        if has_crud and crud["update"]:
            handlers.append(
                f"  const handleEdit = useCallback((row: Row) => {{\n"
                f"    set_mcnEditItemId(row.id)\n"
                f"    {field_setters}\n"
                f"    setEditItem(row)\n"
                f"    set_mcnShowEditModal(true)\n"
                f"  }}, [])\n"
            )
        if has_crud and crud["delete"]:
            handlers.append(
                f"  const handleDelete = useCallback(async (id: number) => {{\n"
                f'    if (!window.confirm("Delete this {entity_singular}?")) return\n'
                f"    try {{\n"
                f"      await api.post(\"/delete_{entity_singular}\", {{ id }})\n"
                f"      const _resp = await api.post(\"/list_{entity_plural}\", {{}})\n"
                f"      set{_pascal(arr_state or 'items')}(_resp.data ?? _resp)\n"
                f"    }} catch (err) {{\n"
                f"      notify(errorMessage(err), \"error\")\n"
                f"    }}\n"
                f"  }}, [])\n"
            )
        if has_crud and crud["update"]:
            handlers.append(
                f"  const handleSave = useCallback(async () => {{\n"
                f"    try {{\n"
                f"      await api.post(\"/update_{entity_singular}\", {{ id: _mcnEditItemId, {save_payload_fields} }})\n"
                f"      set_mcnShowEditModal(false)\n"
                f"      const _resp = await api.post(\"/list_{entity_plural}\", {{}})\n"
                f"      set{_pascal(arr_state or 'items')}(_resp.data ?? _resp)\n"
                f"    }} catch (err) {{\n"
                f"      notify(errorMessage(err), \"error\")\n"
                f"    }}\n"
                f"  }}, [_mcnEditItemId, {', '.join(name for name in edit_fields_names)}])\n"
            )

        if has_crud:
            entity_singular, entity_plural = _get_entity_names(comp.name)
            
            # Create handler
            create_payload_fields = ", ".join(f"{name[7:]}: {name}" for name in synthetic_create_fields)
            create_reset_fields = "\n    ".join(f"set{_pascal(name)}('')" for name in synthetic_create_fields)
        if has_crud and crud["create"]:
            handlers.append(
                f"  const handleCreate = useCallback(async () => {{\n"
                f"    try {{\n"
                f"      await api.post(\"/create_{entity_singular}\", {{ {create_payload_fields} }})\n"
                f"      set_mcnShowCreateModal(false)\n"
                f"      {create_reset_fields.replace(chr(10) + '    ', chr(10) + '      ')}\n"
                f"      const _resp = await api.post(\"/list_{entity_plural}\", {{}})\n"
                f"      set{_pascal(arr_state or 'items')}(_resp.data ?? _resp)\n"
                f"    }} catch (err) {{\n"
                f"      notify(errorMessage(err), \"error\")\n"
                f"    }}\n"
                f"  }}, [{', '.join(synthetic_create_fields)}])\n"
            )
        if has_crud:
            
            # Filtering and Pagination
            handlers.append(
                f"  const paginatedItems = React.useMemo(() => {{\n"
                f"    const start = (currentPage - 1) * pageSize\n"
                f"    return filteredItems.slice(start, start + pageSize)\n"
                f"  }}, [filteredItems, currentPage, pageSize])\n"
            )
            handlers.append(
                f"  const totalPages = Math.ceil(filteredItems.length / pageSize)\n"
            )

        # Render JSX (must happen before final import assembly so _extra_imports is populated)
        jsx_lines: List[str] = []
        if comp.render:
            for el in comp.render.elements:
                jsx_lines.extend(self._element_to_jsx(el, indent=4))
        else:
            jsx_lines.append("    <div>Empty component</div>")

        # Inject Edit modal JSX for CRUD components
        if has_crud:
            entity_singular, _ = _get_entity_names(comp.name)
            # Collect edit_ fields for the modal form inputs
            # States the user declared as numbers must be set with numbers
            numeric_states = {
                st.name for st in comp.states
                if isinstance(st.value, ast.Literal) and isinstance(st.value.value, (int, float))
                and not isinstance(st.value.value, bool)
            }

            def _input_value(name: str) -> str:
                return "Number(e.target.value)" if name in numeric_states else "e.target.value"

            edit_field_inputs: List[str] = []
            for name in edit_fields_names:
                field_name = name[5:]
                edit_field_inputs.extend([
                    f'          <div className="space-y-1">',
                    f'            <label className="text-sm font-medium capitalize">{field_name}</label>',
                    f'            <input className="w-full border rounded px-3 py-2 text-sm" value={{{name}}} onChange={{(e) => set{_pascal(name)}({_input_value(name)})}} />',
                    f'          </div>',
                ])
            
            create_field_inputs: List[str] = []
            for name in synthetic_create_fields:
                field_name = name[7:]
                create_field_inputs.extend([
                    f'          <div className="space-y-1">',
                    f'            <label className="text-sm font-medium capitalize">{field_name}</label>',
                    f'            <input className="w-full border rounded px-3 py-2 text-sm" value={{{name}}} onChange={{(e) => set{_pascal(name)}({_input_value(name)})}} />',
                    f'          </div>',
                ])

            edit_sheet = [
                f'      <Sheet open={{_mcnShowEditModal}} onOpenChange={{set_mcnShowEditModal}}>',
                f'        <SheetContent className="sm:max-w-md overflow-y-auto">',
                f'          <SheetHeader>',
                f'            <SheetTitle>Edit {entity_singular}</SheetTitle>',
                f'            <SheetDescription>Update the details below.</SheetDescription>',
                f'          </SheetHeader>',
                f'          <div className="space-y-4 py-4">',
                *(edit_field_inputs if edit_field_inputs else [
                    f'              <p className="text-sm text-muted-foreground">No editable fields defined.</p>',
                ]),
                f'          </div>',
                f'          <SheetFooter>',
                f'            <button className="px-4 py-2 text-sm rounded border hover:bg-slate-50" onClick={{() => set_mcnShowEditModal(false)}}>Cancel</button>',
                f'            <button className="px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={{handleSave}}>Save Changes</button>',
                f'          </SheetFooter>',
                f'        </SheetContent>',
                f'      </Sheet>',
            ]
            create_sheet = [
                f'      <Sheet open={{_mcnShowCreateModal}} onOpenChange={{set_mcnShowCreateModal}}>',
                f'        <SheetContent className="sm:max-w-md overflow-y-auto">',
                f'          <SheetHeader>',
                f'            <SheetTitle>Create {entity_singular}</SheetTitle>',
                f'            <SheetDescription>Enter the details below.</SheetDescription>',
                f'          </SheetHeader>',
                f'          <div className="space-y-4 py-4">',
                *(create_field_inputs if create_field_inputs else [
                    f'              <p className="text-sm text-muted-foreground">No fields defined.</p>',
                ]),
                f'          </div>',
                f'          <SheetFooter>',
                f'            <button className="px-4 py-2 text-sm rounded border hover:bg-slate-50" onClick={{() => set_mcnShowCreateModal(false)}}>Cancel</button>',
                f'            <button className="px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={{handleCreate}}>Create</button>',
                f'          </SheetFooter>',
                f'        </SheetContent>',
                f'      </Sheet>'
            ]
            modal_jsx = (edit_sheet if crud["update"] else []) + (create_sheet if crud["create"] else [])
            if modal_jsx:
                self._shadcn_needed.add("sheet")
                self._extra_imports.add('import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from "@/components/ui/sheet"')
            jsx_lines.extend(modal_jsx)

        jsx_lines = [wrapped for ln in jsx_lines for wrapped in wrap_jsx(tidy_jsx(ln))]
        if has_load_handler:
            jsx_lines.insert(0, "    <LoadStatus loading={loadState.loading} error={loadState.error} onRetry={loadScreen} />")
            self._extra_imports.add('import { LoadStatus, type LoadState } from "@/components/ui/load-status"')

        # Wrap in Fragment when multiple root elements (e.g. main card + edit modal)
        needs_fragment = len(comp.render.elements if comp.render else []) > 1 or has_crud or has_load_handler
        if needs_fragment:
            jsx_lines = ['    <div className="space-y-6">', *["  " + ln for ln in jsx_lines], "    </div>"]

        # toast() / notify() come from the kit's notification system
        all_compiled_code = "\n".join(handlers) + "\n" + "\n".join(jsx_lines)
        if "toast(" in all_compiled_code or "toast." in all_compiled_code:
            self._extra_imports.add('import { toast } from "@/components/ui/toast"')
        if "notify(" in all_compiled_code:
            self._extra_imports.add('import { notify } from "@/components/ui/toast"')
        helpers = [h for h in ("errorMessage", "preventDefault") if h + "(" in all_compiled_code]
        if helpers:
            self._extra_imports.add(f'import {{ {", ".join(helpers)} }} from "@/lib/utils"')
        hook_code = "\n".join(hooks) + all_compiled_code
        type_names = sorted(self._type_imports | {t for t in ("BackendValue", "Row") if re.search(rf"\b{t}\b", hook_code + "\n".join(self._type_defs))})
        if type_names:
            self._extra_imports.add(f'import type {{ {", ".join(type_names)} }} from "../types"')

        # Icons come from the kit: `const { Users, Plus } = icons`
        icon_names: list = []
        other_extras: list = []
        for line in self._extra_imports:
            m = re.match(r'import \{\s*([^}]+)\s*\} from "lucide-react"', line)
            if m:
                icon_names.extend(n.strip() for n in m.group(1).split(","))
            else:
                other_extras.append(line)
        icon_binding = []
        if icon_names:
            other_extras.append('import { icons } from "@/components/ui/icon"')
            icon_binding = [f"const {{ {', '.join(sorted(set(icon_names)))} }} = icons", ""]
        for extra in sorted(other_extras):
            if extra not in imports:
                imports.append(extra)

        # A component named like something it imports (`component Label` vs the kit's
        # Label) gets a local name and is exported under its own name
        imported = set(icon_names)
        for line in imports:
            m = re.match(r'import \{\s*([^}]+)\s*\}', line)
            if m:
                imported.update(n.split(" as ")[-1].strip() for n in m.group(1).split(","))
        local = f"{comp.name}Screen" if comp.name in imported else comp.name

        body_code = "\n".join(hooks + handlers + jsx_lines)
        if "React." not in body_code:
            imports[0] = imports[0].replace("import React, { ", "import { ")
        imports, icon_binding, hooks, handlers = _prune_component(
            imports, icon_binding, hooks, handlers, jsx_lines, self._type_defs)

        # Assemble
        lines = [
            *imports,
            "",
            *icon_binding,
            *[d + "\n" for d in self._type_defs],
            f"export function {local}() {{" if local == comp.name else f"function {local}() {{",
            *hooks,
            *([""] if hooks else []),
            *[ln for h in handlers for ln in (h.rstrip("\n"), "")],
            "  return (",
            *jsx_lines,
            "  )",
            "}",
            "",
            *([] if local == comp.name else [f"export {{ {local} as {comp.name} }}"]),
            f"export default {local}",
            "",
        ]
        return "\n".join(lines)

    def _collect_imports(self, elements: List[ast.UIElement],
                         acc: Dict[str, List[str]]) -> None:
        """Walk render tree and accumulate required shadcn imports."""
        for el in elements:
            tag = el.tag
            if tag in _SHADCN:
                names, slug, _ = _SHADCN[tag]
                pkg_path = f"@/components/ui/{slug}"
                if pkg_path not in acc:
                    acc[pkg_path] = []
                acc[pkg_path].extend(names)

            # form fields with a label attr render <Label> → need its import
            if tag in ("input", "textarea", "select", "file_upload"):
                has_label = any(a.key == "label" for a in el.attrs)
                if has_label:
                    self._shadcn_needed.add("label")
                    pkg = "@/components/ui/label"
                    acc.setdefault(pkg, []).append("Label")

            self._collect_imports(el.children, acc)

    def _element_to_jsx(self, el: ast.UIElement, indent: int) -> List[str]:
        """Convert a UIElement to JSX lines."""
        pad   = " " * indent
        tag   = el.tag
        lines: List[str] = []

        # ── for x in items loop rendering ───────────────────────────────────────
        if tag == "for" and el.for_var and el.for_iterable is not None:
            iterable_ts = _expr_to_ts(el.for_iterable)
            var_name = el.for_var
            child_lines: List[str] = []
            for child in el.children:
                child_lines.extend(self._element_to_jsx(child, indent + 4))
            lines.append(f"{pad}{{{iterable_ts}.map(({var_name}: BackendValue, _i: number) => (")
            lines.append(f"{pad}  <React.Fragment key={{_i}}>")
            lines.extend(child_lines)
            lines.append(f"{pad}  </React.Fragment>")
            lines.append(f"{pad}))}}")
            return lines

        # ── show=expr conditional rendering ────────────────────────────────────
        # modal/dialog handle show= via their open= prop, not the generic wrapper
        show_attr = next((a for a in el.attrs if a.key == "show"), None)
        if show_attr and tag not in ("modal", "dialog"):
            cond = _expr_to_ts(show_attr.value)
            inner_attrs = [a for a in el.attrs if a.key != "show"]
            inner_el = ast.UIElement(tag=el.tag, attrs=inner_attrs,
                                     text=el.text, children=el.children)
            inner = self._element_to_jsx(inner_el, indent + 2)
            return [f"{pad}{{({cond}) && ("] + inner + [f"{pad})}}"]

        if tag in _KIT_TAGS:
            return self._kit_element(el, indent)

        # Determine JSX tag name
        if tag in _SHADCN:
            _, _, jsx_tag = _SHADCN[tag]
        elif tag in _HTML_TAGS:
            jsx_tag = tag if tag != "text" else "span"
        else:
            jsx_tag = _pascal(tag)  # custom component reference

        # Build props string
        props = self._attrs_to_props(el.attrs, tag)

        has_children = bool(el.children)
        has_text     = el.text is not None

        # Special handling for input (self-closing with label wrapper)
        if tag == "input":
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            bind_attr  = next((a for a in el.attrs if a.key == "bind"), None)
            if label_attr:
                label_text = _expr_to_ts(label_attr.value)
                lines.append(f'{pad}<div className="space-y-1">')
                lines.append(f'{pad}  <Label htmlFor="{_expr_to_ts(bind_attr.value) if bind_attr else tag}">'
                             f'{{{label_text}}}</Label>')
                lines.append(f'{pad}  <Input {props} />')
                lines.append(f'{pad}</div>')
                return lines
            else:
                lines.append(f'{pad}<Input {props} />')
                return lines

        # file_upload
        if tag == "file_upload":
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            if label_attr:
                label_text = _expr_to_ts(label_attr.value)
                lines.append(f'{pad}<div className="space-y-1">')
                lines.append(f'{pad}  <Label>{{{label_text}}}</Label>')
                lines.append(f'{pad}  <Input type="file" {props} />')
                lines.append(f'{pad}</div>')
                return lines
            lines.append(f'{pad}<Input type="file" {props} />')
            return lines

        # data_grid
        if tag == "data_grid":
            data_attr = next((a for a in el.attrs if a.key == "data"), None)
            if data_attr:
                data_expr = _expr_to_ts(data_attr.value)
                lines.append(f'{pad}<div className="border rounded-md overflow-x-auto">')
                lines.append(f'{pad}  <Table>')
                lines.append(f'{pad}    <TableHeader>')
                lines.append(f'{pad}      <TableRow>')
                lines.append(f'{pad}        {{({data_expr} && {data_expr}.length > 0) ? Object.keys({data_expr}[0]).map(k => <TableHead key={{k}}>{{k}}</TableHead>) : null}}')
                lines.append(f'{pad}      </TableRow>')
                lines.append(f'{pad}    </TableHeader>')
                lines.append(f'{pad}    <TableBody>')
                lines.append(f'{pad}      {{({data_expr} || []).map((row, i) => (')
                lines.append(f'{pad}        <TableRow key={{i}}>')
                lines.append(f'{pad}          {{Object.keys(row).map(k => (')
                lines.append(f'{pad}            <TableCell key={{k}}><Input defaultValue={{row[k]}} className="border-transparent hover:border-gray-300 focus:border-blue-500 bg-transparent shadow-none" /></TableCell>')
                lines.append(f'{pad}          ))}}')
                lines.append(f'{pad}        </TableRow>')
                lines.append(f'{pad}      ))}}')
                lines.append(f'{pad}    </TableBody>')
                lines.append(f'{pad}  </Table>')
                lines.append(f'{pad}</div>')
                return lines

        # textarea with label
        if tag == "textarea":
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            bind_attr  = next((a for a in el.attrs if a.key == "bind"), None)
            if label_attr:
                label_text = _expr_to_ts(label_attr.value)
                lines.append(f'{pad}<div className="space-y-1">')
                lines.append(f'{pad}  <Label>{{{label_text}}}</Label>')
                lines.append(f'{pad}  <Textarea {props} />')
                lines.append(f'{pad}</div>')
                return lines
            lines.append(f'{pad}<Textarea {props} />')
            return lines

        # button with text
        if tag == "button":
            btn_text = _expr_to_ts(el.text) if el.text else '"Click"'
            lines.append(f'{pad}<Button {props}>{{{btn_text}}}</Button>')
            return lines

        # text — renders a variable or literal as inline text
        if tag == "text":
            # `text message` → bare attr whose key IS the variable name
            if el.attrs and el.attrs[0].value is None:
                var_name = el.attrs[0].key
                lines.append(f'{pad}<span>{{{var_name}}}</span>')
            elif el.text:
                lines.append(f'{pad}<span>{{{_expr_to_ts(el.text)}}}</span>')
            return lines

        # badge, separator — simple self-closing or text
        if tag in ("badge", "separator"):
            if has_text:
                txt = _expr_to_ts(el.text)
                lines.append(f'{pad}<{jsx_tag} {props}>{{{txt}}}</{jsx_tag}>')
            else:
                lines.append(f'{pad}<{jsx_tag} {props} />')
            return lines

        # form — wraps children
        if tag == "form":
            lines.append(f'{pad}<form {props} className="space-y-4">')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</form>')
            return lines

        # card_header — renders text content
        if tag == "card_header":
            txt = _expr_to_ts(el.text) if el.text else '""'
            lines.append(f'{pad}<CardHeader>')
            lines.append(f'{pad}  <h2 className="text-xl font-semibold">{{{txt}}}</h2>')
            lines.append(f'{pad}</CardHeader>')
            return lines

        # card — correctly separates CardHeader/Footer and wraps content in CardContent
        if tag == "card":
            lines.append(f'{pad}<Card {props}>')
            in_content = False
            for child in el.children:
                if child.tag in {"card_header", "card_content", "card_footer"}:
                    if in_content:
                        lines.append(f'{pad}  </CardContent>')
                        in_content = False
                    lines.extend(self._element_to_jsx(child, indent + 2))
                else:
                    if not in_content:
                        lines.append(f'{pad}  <CardContent className="pt-6">')
                        in_content = True
                    lines.extend(self._element_to_jsx(child, indent + 4))
            if in_content:
                lines.append(f'{pad}  </CardContent>')
            lines.append(f'{pad}</Card>')
            return lines

        # table — generate full table structure with data rows if table_body is empty
        if tag == "table":
            # Extract column names from table_header for data row generation
            col_names: List[str] = []
            for child in el.children:
                if child.tag == "table_header":
                    for row_el in child.children:
                        if row_el.tag == "table_row":
                            for th in row_el.children:
                                if th.tag == "table_head" and th.text:
                                    if isinstance(th.text, ast.Literal):
                                        col_names.append(str(th.text.value).strip('"').strip("'"))

            # Detect CRUD mode: component has edit_item state OR table has columns
            has_actions = False
            if self._current_comp is not None:
                has_actions = any(s.name == "edit_item" for s in self._current_comp.states)
            if not has_actions:
                has_actions = bool(col_names)
            
            if has_actions:
                self._extra_imports.add('import { Search, Plus } from "lucide-react"')
                self._extra_imports.add('import { Label } from "@/components/ui/label"')
                self._shadcn_needed.add("label")
                entity_singular = _get_entity_names(self._current_comp.name)[0] if self._current_comp else "item"
                ops = getattr(self, "_crud_ops", {}) or {}
                new_button = [
                    f'{pad}  <button className="flex items-center gap-2 px-4 py-2 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90" onClick={{() => set_mcnShowCreateModal(true)}}>',
                    f'{pad}    <Plus className="w-4 h-4" /> New {entity_singular.capitalize()}',
                    f'{pad}  </button>',
                ] if ops.get("create", True) else []
                lines.extend([
                    f'{pad}<div className="flex items-center justify-between pb-4">',
                    f'{pad}  <div className="relative w-64">',
                    f'{pad}    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />',
                    f'{pad}    <input type="text" placeholder="Search..." className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={{searchQuery}} onChange={{(e) => setSearchQuery(e.target.value)}} />',
                    f'{pad}  </div>',
                    *new_button,
                    f'{pad}</div>'
                ])
            lines.append(f'{pad}<Table {props}>')

            for child in el.children:
                ops = getattr(self, "_crud_ops", {}) or {}
                row_actions = has_actions and (ops.get("update", True) or ops.get("delete", True))
                if child.tag == "table_header" and row_actions:
                    # Inject Actions column into header
                    lines.extend(self._element_to_jsx_header_with_actions(child, indent + 2))
                elif child.tag == "table_body" and not child.children:
                    # Check if table or table_body has a "data" attribute
                    data_attr = next((a for a in el.attrs if a.key == "data"), None)
                    if not data_attr:
                        data_attr = next((a for a in child.attrs if a.key == "data"), None)

                    arr_state = None
                    if data_attr:
                        arr_state = _expr_to_ts(data_attr.value)
                    elif self._current_comp:
                        arr_state = next(
                            (s.name for s in self._current_comp.states
                             if isinstance(s.value, ast.Array)),
                            None,
                        )
                    entity_singular = "item"
                    if self._current_comp:
                        entity_singular, _ = _get_entity_names(self._current_comp.name)
                    lines.extend(
                        self._gen_table_body_rows("paginatedItems" if has_actions else (arr_state or "items"), col_names, indent + 2, has_actions, entity_singular)
                    )
                else:
                    lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</Table>')
            if has_actions:
                lines.extend([
                    f'{pad}<div className="flex items-center justify-between px-4 py-3 border-t">',
                    f'{pad}  <div className="text-sm text-muted-foreground">',
                    f'{pad}    Showing {{(currentPage - 1) * pageSize + 1}} to {{Math.min(currentPage * pageSize, filteredItems.length)}} of {{filteredItems.length}} entries',
                    f'{pad}  </div>',
                    f'{pad}  <div className="flex items-center space-x-2">',
                    f'{pad}    <button className="px-3 py-1 text-sm border rounded hover:bg-accent disabled:opacity-50" onClick={{() => setCurrentPage(p => Math.max(1, p - 1))}} disabled={{currentPage === 1}}>Previous</button>',
                    f'{pad}    <button className="px-3 py-1 text-sm border rounded hover:bg-accent disabled:opacity-50" onClick={{() => setCurrentPage(p => Math.min(totalPages, p + 1))}} disabled={{currentPage === totalPages || totalPages === 0}}>Next</button>',
                    f'{pad}  </div>',
                    f'{pad}</div>'
                ])

            return lines

        # tabs
        if tag == "tabs":
            lines.append(f'{pad}<Tabs {props} className="w-full">')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</Tabs>')
            return lines

        # alert with description
        if tag == "alert":
            msg = _expr_to_ts(el.text) if el.text else '""'
            lines.append(f'{pad}<Alert {props}>')
            lines.append(f'{pad}  <AlertDescription>{{{msg}}}</AlertDescription>')
            lines.append(f'{pad}</Alert>')
            return lines

        # modal / dialog → shadcn Dialog
        if tag in ("modal", "dialog"):
            self._shadcn_needed.add("dialog")
            show_expr  = "false"
            on_change  = "() => {}"
            for a in el.attrs:
                if a.key == "show":
                    show_expr = _expr_to_ts(a.value)
                    if isinstance(a.value, ast.Variable):
                        on_change = "set" + _pascal(a.value.name)

            # Extract title from first card_header child (required for accessibility)
            title_text = '""'
            body_children = []
            for child in el.children:
                if child.tag == "card_header" and child.text and not body_children:
                    title_text = _expr_to_ts(child.text)
                else:
                    body_children.append(child)

            lines.append(f'{pad}<Dialog open={{{show_expr}}} onOpenChange={{{on_change}}}>')
            lines.append(f'{pad}  <DialogContent className="sm:max-w-lg">')
            lines.append(f'{pad}    <DialogHeader>')
            lines.append(f'{pad}      <DialogTitle>{{{title_text}}}</DialogTitle>')
            lines.append(f'{pad}    </DialogHeader>')
            for child in body_children:
                lines.extend(self._element_to_jsx(child, indent + 4))
            lines.append(f'{pad}  </DialogContent>')
            lines.append(f'{pad}</Dialog>')
            return lines

        # select → shadcn Select with options
        if tag == "select":
            self._shadcn_needed.add("select")
            bind_attr    = next((a for a in el.attrs if a.key == "bind"),    None)
            options_attr = next((a for a in el.attrs if a.key == "options"), None)
            label_attr   = next((a for a in el.attrs if a.key == "label"),   None)
            ph_attr      = next((a for a in el.attrs if a.key == "placeholder"), None)
            ph_text      = _expr_to_ts(ph_attr.value) if ph_attr else '"Select…"'
            var_name     = _expr_to_ts(bind_attr.value) if bind_attr else "value"
            setter       = "set" + _pascal(var_name) if bind_attr and isinstance(bind_attr.value, ast.Variable) else "setValue"
            opts_expr    = _expr_to_ts(options_attr.value) if options_attr else "[]"
            if label_attr:
                self._shadcn_needed.add("label")
                lbl = _expr_to_ts(label_attr.value)
                lines.append(f'{pad}<div className="space-y-1">')
                lines.append(f'{pad}  <Label>{{{lbl}}}</Label>')
                lines.append(f'{pad}  <Select value={{{var_name}}} onValueChange={{{setter}}}>')
                lines.append(f'{pad}    <SelectTrigger><SelectValue placeholder={{{ph_text}}} /></SelectTrigger>')
                lines.append(f'{pad}    <SelectContent>')
                lines.append(f'{pad}      {{{opts_expr}.map((o: unknown) => <SelectItem key={{String(o)}} value={{String(o)}}>{{String(o)}}</SelectItem>)}}')
                lines.append(f'{pad}    </SelectContent>')
                lines.append(f'{pad}  </Select>')
                lines.append(f'{pad}</div>')
            else:
                lines.append(f'{pad}<Select value={{{var_name}}} onValueChange={{{setter}}}>')
                lines.append(f'{pad}  <SelectTrigger><SelectValue placeholder={{{ph_text}}} /></SelectTrigger>')
                lines.append(f'{pad}  <SelectContent>')
                lines.append(f'{pad}    {{{opts_expr}.map((o: unknown) => <SelectItem key={{String(o)}} value={{String(o)}}>{{String(o)}}</SelectItem>)}}')
                lines.append(f'{pad}  </SelectContent>')
                lines.append(f'{pad}</Select>')
            return lines

        # gantt_chart
        if tag == "gantt_chart":
            data_attr  = next((a for a in el.attrs if a.key == "data"),   None)
            data_expr  = _expr_to_ts(data_attr.value)  if data_attr  else "[]"
            lines += [
                f'{pad}<div className="overflow-x-auto w-full">',
                f'{pad}  <div className="min-w-[500px] flex flex-col gap-3 py-2">',
                f'{pad}    {{{data_expr}.map((task: Row, i: number) => (',
                f'{pad}      <div key={{i}} className="flex items-center gap-4 text-sm">',
                f'{pad}        <div className="w-32 font-medium truncate" title={{task.name || task.title}}>{{task.name || task.title || `Task ${{i+1}}`}}</div>',
                f'{pad}        <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-8 relative overflow-hidden group">',
                f'{pad}          <div className="absolute top-0 bottom-0 bg-blue-500/80 rounded-full transition-all group-hover:bg-blue-400" style={{{{ left: `${{Math.max(0, Math.min(100, task.start || (i*10)))}}%`, right: `${{100 - Math.max(0, Math.min(100, task.end || ((i+3)*10)))}}%` }}}}></div>',
                f'{pad}        </div>',
                f'{pad}        <div className="w-20 text-slate-500 text-xs text-right">{{task.status || "In Progress"}}</div>',
                f'{pad}      </div>',
                f'{pad}    ))}}',
                f'{pad}  </div>',
                f'{pad}</div>',
            ]
            return lines

        # stat / stat_card — a compact KPI card with icon, value, trend
        if tag in ("stat", "stat_card"):
            label_attr = next((a for a in el.attrs if a.key in ("label", "title")), None)
            value_attr = next((a for a in el.attrs if a.key in ("value", "val")), None)
            unit_attr  = next((a for a in el.attrs if a.key == "unit"),  None)
            icon_attr  = next((a for a in el.attrs if a.key == "icon"),  None)
            trend_attr = next((a for a in el.attrs if a.key in ("trend", "change")), None)
            trend_lbl  = next((a for a in el.attrs if a.key in ("trend_label", "change_label")), None)
            color_attr = next((a for a in el.attrs if a.key == "color"), None)
            lbl   = _expr_to_ts(label_attr.value) if label_attr else '""'
            val   = _expr_to_ts(value_attr.value) if value_attr else '""'
            unit  = _expr_to_ts(unit_attr.value)  if unit_attr  else '""'
            icon  = icon_attr.value.value if icon_attr and isinstance(icon_attr.value, ast.Literal) else "TrendingUp"
            trend = _expr_to_ts(trend_attr.value) if trend_attr else None
            tlbl  = _expr_to_ts(trend_lbl.value) if trend_lbl else '"vs last month"'
            color = color_attr.value.value if color_attr and isinstance(color_attr.value, ast.Literal) else "primary"
            self._extra_imports.add(f'import {{ {icon} }} from "lucide-react"')
            self._extra_imports.add('import { Stat } from "@/components/ui/stat"')
            props = [_jsx_prop("label", lbl), f"value={{{val}}}", f"icon={{{icon}}}"]
            if color != "primary":
                props.append(f'tone="{color}"')
            if unit_attr:
                props.append(_jsx_prop("unit", unit))
            if trend:
                props.append(f"change={{{trend}}}")
                if trend_lbl:
                    props.append(_jsx_prop("trendLabel", tlbl))
            lines.append(f"{pad}<Stat {' '.join(props)} />")
            return lines

        # pagination — prev/next button row
        if tag == "pagination":
            page_attr  = next((a for a in el.attrs if a.key == "page"),      None)
            total_attr = next((a for a in el.attrs if a.key == "total"),     None)
            size_attr  = next((a for a in el.attrs if a.key == "page_size"), None)
            page_var   = _expr_to_ts(page_attr.value)  if page_attr  else "page"
            total_expr = _expr_to_ts(total_attr.value) if total_attr else "items.length"
            page_size  = _expr_to_ts(size_attr.value)  if size_attr  else "10"
            page_set   = "set" + _pascal(page_var) if page_attr and isinstance(page_attr.value, ast.Variable) else "setPage"
            lines += [
                f'{pad}<div className="flex items-center justify-between mt-4">',
                f'{pad}  <button',
                f'{pad}    className="px-3 py-1 text-sm border rounded disabled:opacity-40"',
                f'{pad}    disabled={{{{{page_var}}} <= 0}}',
                f'{pad}    onClick={{() => {page_set}((p: number) => Math.max(0, p - 1))}}',
                f'{pad}  >Previous</button>',
                f'{pad}  <span className="text-sm text-muted-foreground">',
                f'{pad}    Page {{{{{page_var}}} + 1}} of {{Math.max(1, Math.ceil({total_expr} / {page_size}))}}',
                f'{pad}  </span>',
                f'{pad}  <button',
                f'{pad}    className="px-3 py-1 text-sm border rounded disabled:opacity-40"',
                f'{pad}    disabled={{({{{page_var}}} + 1) * {page_size} >= {total_expr}}}',
                f'{pad}    onClick={{() => {page_set}((p: number) => p + 1)}}',
                f'{pad}  >Next</button>',
                f'{pad}</div>',
            ]
            return lines

        # checkbox
        if tag == "checkbox":
            bind_attr  = next((a for a in el.attrs if a.key == "bind"),  None)
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            var_name   = _expr_to_ts(bind_attr.value)  if bind_attr  else "checked"
            setter     = ("set" + _pascal(var_name)
                          if bind_attr and isinstance(bind_attr.value, ast.Variable)
                          else "setChecked")
            lbl        = _expr_to_ts(label_attr.value) if label_attr else '""'
            self._shadcn_needed.add("checkbox")
            self._shadcn_needed.add("label")
            lines += [
                f'{pad}<div className="flex items-center space-x-2">',
                f'{pad}  <Checkbox id="{var_name}" checked={{{var_name}}} onCheckedChange={{{setter}}} />',
                f'{pad}  <label htmlFor="{var_name}" className="text-sm font-medium leading-none">{{{lbl}}}</label>',
                f'{pad}</div>',
            ]
            return lines

        # switch
        if tag == "switch":
            bind_attr  = next((a for a in el.attrs if a.key == "bind"),  None)
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            var_name   = _expr_to_ts(bind_attr.value)  if bind_attr  else "enabled"
            setter     = ("set" + _pascal(var_name)
                          if bind_attr and isinstance(bind_attr.value, ast.Variable)
                          else "setEnabled")
            lbl        = _expr_to_ts(label_attr.value) if label_attr else '""'
            self._shadcn_needed.add("switch")
            self._shadcn_needed.add("label")
            lines += [
                f'{pad}<div className="flex items-center space-x-2">',
                f'{pad}  <Switch id="{var_name}" checked={{{var_name}}} onCheckedChange={{{setter}}} />',
                f'{pad}  <label htmlFor="{var_name}" className="text-sm font-medium">{{{lbl}}}</label>',
                f'{pad}</div>',
            ]
            return lines

        # radio_group
        if tag == "radio_group":
            bind_attr    = next((a for a in el.attrs if a.key == "bind"),    None)
            options_attr = next((a for a in el.attrs if a.key == "options"), None)
            label_attr   = next((a for a in el.attrs if a.key == "label"),   None)
            var_name     = _expr_to_ts(bind_attr.value)    if bind_attr    else "selected"
            setter       = ("set" + _pascal(var_name)
                            if bind_attr and isinstance(bind_attr.value, ast.Variable)
                            else "setSelected")
            opts_expr    = _expr_to_ts(options_attr.value) if options_attr else "[]"
            self._shadcn_needed.add("radio-group")
            wrap_lines = []
            if label_attr:
                self._shadcn_needed.add("label")
                lbl = _expr_to_ts(label_attr.value)
                wrap_lines.append(f'{pad}<div className="space-y-2">')
                wrap_lines.append(f'{pad}  <Label>{{{lbl}}}</Label>')
                inner_pad = pad + "  "
            else:
                inner_pad = pad
            wrap_lines += [
                f'{inner_pad}<RadioGroup value={{{var_name}}} onValueChange={{{setter}}} className="space-y-2">',
                f'{inner_pad}  {{{opts_expr}.map((o: unknown) => (',
                f'{inner_pad}    <div key={{String(o)}} className="flex items-center space-x-2">',
                f'{inner_pad}      <RadioGroupItem value={{String(o)}} id={{`rg-${{String(o)}}`}} />',
                f'{inner_pad}      <label htmlFor={{`rg-${{String(o)}}`}} className="text-sm">{{String(o)}}</label>',
                f'{inner_pad}    </div>',
                f'{inner_pad}  ))}}',
                f'{inner_pad}</RadioGroup>',
            ]
            if label_attr:
                wrap_lines.append(f'{pad}</div>')
            lines += wrap_lines
            return lines

        # accordion
        if tag == "accordion":
            self._shadcn_needed.add("accordion")
            lines.append(f'{pad}<Accordion type="single" collapsible className="w-full">')
            for i, child in enumerate(el.children):
                if child.tag == "accordion_item":
                    title_attr = next((a for a in child.attrs if a.key == "title"), None)
                    title      = _expr_to_ts(title_attr.value) if title_attr else f'"Item {i + 1}"'
                    lines.append(f'{pad}  <AccordionItem value="item-{i}">')
                    lines.append(f'{pad}    <AccordionTrigger>{{{title}}}</AccordionTrigger>')
                    lines.append(f'{pad}    <AccordionContent>')
                    for gc in child.children:
                        lines.extend(self._element_to_jsx(gc, indent + 6))
                    lines.append(f'{pad}    </AccordionContent>')
                    lines.append(f'{pad}  </AccordionItem>')
                else:
                    lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</Accordion>')
            return lines

        # tooltip
        if tag == "tooltip":
            content_attr = next((a for a in el.attrs if a.key == "content"), None)
            content      = _expr_to_ts(content_attr.value) if content_attr else '""'
            self._shadcn_needed.add("tooltip")
            lines.append(f'{pad}<TooltipProvider>')
            lines.append(f'{pad}  <Tooltip>')
            lines.append(f'{pad}    <TooltipTrigger asChild>')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 6))
            lines.append(f'{pad}    </TooltipTrigger>')
            lines.append(f'{pad}    <TooltipContent><p>{{{content}}}</p></TooltipContent>')
            lines.append(f'{pad}  </Tooltip>')
            lines.append(f'{pad}</TooltipProvider>')
            return lines

        # dropdown_menu
        if tag == "dropdown_menu":
            trigger_attr = next((a for a in el.attrs if a.key == "trigger"), None)
            items_attr   = next((a for a in el.attrs if a.key == "items"),   None)
            trigger_text = _expr_to_ts(trigger_attr.value) if trigger_attr else '"Menu"'
            items_expr   = _expr_to_ts(items_attr.value)   if items_attr   else "[]"
            self._shadcn_needed.add("dropdown-menu")
            self._shadcn_needed.add("button")
            lines += [
                f'{pad}<DropdownMenu>',
                f'{pad}  <DropdownMenuTrigger asChild>',
                f'{pad}    <Button variant="outline">{{{trigger_text}}}</Button>',
                f'{pad}  </DropdownMenuTrigger>',
                f'{pad}  <DropdownMenuContent>',
                f'{pad}    {{{items_expr}.map((item: Row, i: number) => (',
                f'{pad}      <DropdownMenuItem key={{i}}>{{String(item)}}</DropdownMenuItem>',
                f'{pad}    ))}}',
                f'{pad}  </DropdownMenuContent>',
                f'{pad}</DropdownMenu>',
            ]
            return lines

        # sheet
        if tag == "sheet":
            side_attr  = next((a for a in el.attrs if a.key == "side"),  None)
            title_attr = next((a for a in el.attrs if a.key == "title"), None)
            show_attr2 = next((a for a in el.attrs if a.key == "show"),  None)
            show_expr  = _expr_to_ts(show_attr2.value) if show_attr2 else "false"
            on_change  = ("set" + _pascal(show_attr2.value.name)
                          if show_attr2 and isinstance(show_attr2.value, ast.Variable)
                          else "() => {}")
            side       = _expr_to_ts(side_attr.value)  if side_attr  else '"right"'
            title_text = _expr_to_ts(title_attr.value) if title_attr else '""'
            self._shadcn_needed.add("sheet")
            lines.append(f'{pad}<Sheet open={{{show_expr}}} onOpenChange={{{on_change}}}>')
            lines.append(f'{pad}  <SheetContent side={{{side}}}>')
            lines.append(f'{pad}    <SheetHeader><SheetTitle>{{{title_text}}}</SheetTitle></SheetHeader>')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 4))
            lines.append(f'{pad}  </SheetContent>')
            lines.append(f'{pad}</Sheet>')
            return lines

        # Auto-class for headings when no className provided
        _heading_cls = {
            "h1": "text-3xl font-bold mb-4",
            "h2": "text-xl font-semibold mb-4",
            "h3": "text-base font-semibold mb-2",
            "h4": "text-sm font-semibold mb-1",
        }
        if tag in _heading_cls and 'className' not in props:
            props = f'className="{_heading_cls[tag]}" {props}'.strip()

        # generic element with possible children or text
        if has_children or has_text:
            lines.append(f'{pad}<{jsx_tag} {props}>')
            if has_text:
                lines.append(f'{pad}  {{{_expr_to_ts(el.text)}}}')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</{jsx_tag}>')
        else:
            lines.append(f'{pad}<{jsx_tag} {props} />')

        return lines

    def _element_to_jsx_header_with_actions(self, header_el: ast.UIElement,
                                             indent: int) -> List[str]:
        """Render a table_header, appending an Actions <TableHead> at the end."""
        pad = " " * indent
        lines: List[str] = [f"{pad}<TableHeader>"]
        for child in header_el.children:
            if child.tag == "table_row":
                lines.append(f"{pad}  <TableRow>")
                for th in child.children:
                    lines.extend(self._element_to_jsx(th, indent + 4))
                lines.append(f'{pad}    <TableHead>Actions</TableHead>')
                lines.append(f"{pad}  </TableRow>")
            else:
                lines.extend(self._element_to_jsx(child, indent + 2))
        lines.append(f"{pad}</TableHeader>")
        return lines

    def _gen_table_body_rows(self, state_name: str, cols: List[str], indent: int,
                              has_actions: bool = False, entity: str = "item") -> List[str]:
        """Generate a <TableBody> with a .map() over state_name using col names."""
        pad = " " * indent
        p2  = pad + "  "
        p4  = pad + "    "
        p6  = pad + "      "

        actions_cell = ""
        ops = getattr(self, "_crud_ops", {}) or {}
        can_edit, can_delete = ops.get("update", True), ops.get("delete", True)
        if has_actions and (can_edit or can_delete):
            edit_btn = (
                f"\n{p6}<button"
                f'\n{p6}  className="mr-2 text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded hover:bg-blue-200"'
                f"\n{p6}  onClick={{() => handleEdit(row)}}"
                f"\n{p6}>Edit</button>"
            ) if can_edit else ""
            delete_btn = (
                f"\n{p6}<button"
                f'\n{p6}  className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200"'
                f"\n{p6}  onClick={{() => handleDelete(row.id)}}"
                f"\n{p6}>Delete</button>"
            ) if can_delete else ""
            actions_cell = f"\n{p4}<TableCell>{edit_btn}{delete_btn}\n{p4}</TableCell>"


        if not cols:
            # No column info — use Object.entries as fallback
            return [
                f"{pad}<TableBody>",
                f"{p2}{{{state_name}.map((row: Row, i: number) => (",
                f"{p4}<TableRow key={{i}}>",
                f"{p6}{{Object.entries(row).map(([k, v]) => (",
                f"{p6}  <TableCell key={{k}}>{{String(v)}}</TableCell>",
                f"{p6}))}}",
                *(([f"{actions_cell}"] if actions_cell else [])),
                f"{p4}</TableRow>",
                f"{p2}))}}",
                f"{pad}</TableBody>",
            ]

        cells = "\n".join(f"{p4}<TableCell>{{row.{c}}}</TableCell>" for c in cols)
        return [
            f"{pad}<TableBody>",
            f"{p2}{{{state_name}.map((row: Row, i: number) => (",
            f"{p4}<TableRow key={{i}}>",
            cells,
            *(([actions_cell] if actions_cell else [])),
            f"{p4}</TableRow>",
            f"{p2}))}}",
            f"{pad}</TableBody>",
        ]

    def _kit_element(self, el: ast.UIElement, indent: int) -> List[str]:
        """A kit component: attributes become props, and attributes that name an
        endpoint or an `on` handler become callbacks."""
        pad = " " * indent
        tag = el.tag
        _, _, jsx_tag = _SHADCN[tag]
        handlers = {h.event for h in self._current_comp.handlers} if self._current_comp else set()
        actions = _KIT_ACTIONS.get(tag, {})
        group = next((a.value.value for a in el.attrs if a.key == "group_by" and isinstance(a.value, ast.Literal)), "status")
        props: List[str] = []
        for attr in el.attrs:
            key, val = attr.key, attr.value
            if key in actions and isinstance(val, ast.Variable):
                prop, params, payload = actions[key]
                first = params.split(":")[0].strip() if params else ""
                if val.name in handlers:      # a component `on` handler
                    props.append(f"{prop}={{({params}) => {_handler_name(val.name)}({first})}}")
                else:                         # a backend endpoint
                    props.append(f"{prop}={{async ({params}) => api.post(\"/{val.name}\", {payload.replace('GROUP', group)})}}")
                continue
            if val is None:
                props.append(key)
            elif isinstance(val, ast.Literal) and isinstance(val.value, str):
                props.append(f"{key}={{{json.dumps(val.value)}}}")
            else:
                props.append(f"{key}={{{_expr_to_ts(val)}}}")
        # The element's text is its title (`chat "Support bot"`, `empty_state "No deals"`)
        if el.text is not None and not any(a.key == "title" for a in el.attrs):
            props.insert(0, f"title={{{_expr_to_ts(el.text)}}}")
        # A data component without data= shows the component's first list state
        if tag in ("data_table", "kanban") and not any(a.key == "data" for a in el.attrs) and self._current_comp:
            lists = [st.name for st in self._current_comp.states if isinstance(st.value, ast.Array)]
            if lists:
                props.insert(0, f"data={{{lists[0]}}}")
        return [f"{pad}<{jsx_tag} {' '.join(props)} />".replace("  />", " />")]

    def _attrs_to_props(self, attrs: List[ast.UIAttr], tag: str) -> str:
        """Convert UIAttr list → JSX props string."""
        props: List[str] = []
        for attr in attrs:
            key = attr.key
            val = attr.value

            # Skip label, show, options — handled separately
            if key in ("label", "show", "options", "x_key", "y_key", "name_key",
                       "value_key", "data", "height", "page", "total", "page_size"):
                continue

            # grid_cols=N → Tailwind grid className
            if key == "grid_cols" and tag == "div":
                n = _expr_to_ts(val) if val else "3"
                # strip quotes if it's a string literal
                n = n.strip('"\'')
                # One column on phones, two on tablets, N on wide screens
                cols = {"1": "grid-cols-1", "2": "grid-cols-1 sm:grid-cols-2"}.get(n, f"grid-cols-1 sm:grid-cols-2 lg:grid-cols-{n}")
                # [&>*]:min-w-0 lets cells shrink below their content (charts, tables)
                props.append(f'className="grid {cols} gap-4 [&>*]:min-w-0"')
                continue

            # bind=name  →  value={name} onChange={e => setName(...)}
            if key == "bind":
                var_name = _expr_to_ts(val)
                setter   = "set" + _pascal(var_name)
                numeric  = self._current_comp is not None and any(
                    st.name == var_name and isinstance(st.value, ast.Literal)
                    and isinstance(st.value.value, (int, float)) and not isinstance(st.value.value, bool)
                    for st in self._current_comp.states)
                value_ts = "Number(e.target.value)" if numeric else "e.target.value"
                if tag == "textarea":
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(e: {{ target: {{ value: string }} }}) => {setter}(e.target.value)}}')
                elif tag == "input":
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(e: {{ target: {{ value: string }} }}) => {setter}({value_ts})}}')
                else:
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(v) => {setter}(v)}}')
                continue

            # on_submit / on_click → onSubmit / onClick
            if key.startswith("on_"):
                react_evt = "on" + _pascal(key[3:])
                # on_click=close_blinds names the `on close_blinds` handler, generated as closeBlinds
                handler   = _handler_name(val.name) if isinstance(val, ast.Variable) else _expr_to_ts(val)
                props.append(f'{react_evt}={{{handler}}}')
                continue

            # type="..." placeholder="..." variant="..."
            if val is None:
                props.append(key)  # boolean flag
            elif isinstance(val, ast.Literal) and isinstance(val.value, str):
                props.append(f'{_camel(key)}={{{json.dumps(val.value)}}}')
            else:
                props.append(f'{_camel(key)}={{{_expr_to_ts(val)}}}')

        return " ".join(props)

    def _stmts_to_ts(self, stmts: List[ast.Stmt], indent: int = 4,
                     _lv: Optional[Dict[str, str]] = None,
                     _locals: Optional[set] = None) -> str:
        """Convert simple MCN statements to TypeScript (for event handlers).

        _lv: internal local-var substitution dict; don't pass externally.
        _locals: names declared with `var` (assigned directly, not via setters).
        """
        pad    = " " * indent
        lv     = dict(_lv or {})   # copy so sibling branches don't share mutations
        locals_ = set(_locals or ())
        lines: List[str] = []

        def block(body, extra_locals=()):
            return self._stmts_to_ts(body, indent + 2, lv, locals_ | set(extra_locals)).rstrip("\n")

        def parallel_call(stmt, taken: Set[str]):
            """(setter, before, call, after) for `state = endpoint(...)` that can run alongside others."""
            if not isinstance(stmt, ast.AssignStmt) or stmt.name in locals_ or stmt.name in taken \
                    or isinstance(stmt.value, ast.Literal) or names_in(stmt.value) & taken:
                return None
            parts = split_await(_expr_to_ts(stmt.value, lv), "api.post(")
            return parts

        skip = 0
        for i, stmt in enumerate(stmts):
            if skip:
                skip -= 1
                continue
            # Independent backend calls in a row run together
            group, taken = [], set()
            for nxt in stmts[i:]:
                parts = parallel_call(nxt, taken)
                if not parts:
                    break
                group.append((nxt, parts))
                taken.add(nxt.name)
            if len(group) > 1:
                self._tmp_count = getattr(self, "_tmp_count", 0) + 1
                results = f"_results{self._tmp_count}"
                lines.append(f"{pad}const {results} = await Promise.all([")
                lines.extend(f"{pad}  {call}," for _, (_, call, _) in group)
                lines.append(f"{pad}])")
                for k, (st, (before, _, after)) in enumerate(group):
                    self._tmp_count += 1
                    temp = f"_{st.name}{self._tmp_count}"
                    lines.append(f"{pad}const {temp} = {before}{results}[{k}]{after}")
                    lines.append(f"{pad}set{_pascal(st.name)}({temp})")
                    lv[st.name] = temp
                skip = len(group) - 1
                continue

            if isinstance(stmt, ast.VarDecl):
                val = _expr_to_ts(stmt.value, lv)
                # Explicit types keep strict TypeScript from inferring never[] / null
                ann = ": BackendValue[]" if isinstance(stmt.value, ast.Array) else (
                      ": BackendValue" if isinstance(stmt.value, ast.MCNObject) or
                      (isinstance(stmt.value, ast.Literal) and stmt.value.value is None) else "")
                kw = "let" if _reassigned(stmts[i + 1:], stmt.name) else "const"
                if val.startswith("(await ") and _balanced_end(val, 0) == len(val):
                    lines.append(f"{pad}{kw} {stmt.name}{ann} = {val[1:-1]}")
                elif isinstance(stmt.value, ast.Call):
                    lines.append(f"{pad}{kw} {stmt.name}{ann} = await {val}")
                else:
                    lines.append(f"{pad}{kw} {stmt.name}{ann} = {val}")
                # Named vars are usable directly, no setter needed
                lv[stmt.name] = stmt.name
                locals_.add(stmt.name)

            elif isinstance(stmt, ast.AssignStmt) and stmt.name in locals_:
                val = _expr_to_ts(stmt.value, lv)
                if val.startswith("(await ") and _balanced_end(val, 0) == len(val):
                    val, await_ = val[1:-1], ""
                else:
                    await_ = "await " if isinstance(stmt.value, ast.Call) else ""
                lines.append(f"{pad}{stmt.name} = {await_}{val}")

            elif isinstance(stmt, ast.ForStmt):
                iterable = _expr_to_ts(stmt.iterable, lv)
                loop_vars = [stmt.variable] + ([stmt.index_var] if stmt.index_var else [])
                for v in loop_vars:
                    lv[v] = v
                if stmt.index_var:
                    lines.append(f"{pad}for (const [{stmt.index_var}, {stmt.variable}] of ({iterable} ?? []).entries()) {{")
                else:
                    lines.append(f"{pad}for (const {stmt.variable} of ({iterable} ?? [])) {{")
                body = block(stmt.body, loop_vars)
                if body.strip():
                    lines.append(body)
                lines.append(f"{pad}}}")

            elif isinstance(stmt, ast.WhileStmt):
                lines.append(f"{pad}while ({_unwrap_parens(_expr_to_ts(stmt.condition, lv))}) {{")
                body = block(stmt.body)
                if body.strip():
                    lines.append(body)
                lines.append(f"{pad}}}")

            elif isinstance(stmt, ast.ReturnStmt):
                lines.append(f"{pad}return" + (f" {_expr_to_ts(stmt.value, lv)}" if stmt.value else ""))

            elif isinstance(stmt, ast.BreakStmt):
                lines.append(f"{pad}break")

            elif isinstance(stmt, ast.ContinueStmt):
                lines.append(f"{pad}continue")

            elif isinstance(stmt, ast.PropertyAssignStmt):
                lines.append(f"{pad}{_expr_to_ts(stmt.object, lv)}.{stmt.prop} = {_expr_to_ts(stmt.value, lv)}")

            elif isinstance(stmt, ast.IndexAssignStmt):
                lines.append(f"{pad}{_expr_to_ts(stmt.object, lv)}[{_expr_to_ts(stmt.index, lv)}] = "
                             f"{_expr_to_ts(stmt.value, lv)}")

            elif isinstance(stmt, ast.AssignStmt):
                # Capture the new value in a local, then call the setter: React state
                # updates only show on the next render, so later lines read the local
                setter = "set" + _pascal(stmt.name)
                if isinstance(stmt.value, ast.Literal):
                    val = _expr_to_ts(stmt.value, lv)
                    lines.append(f"{pad}{setter}({val})")
                    lv[stmt.name] = val
                    continue
                self._tmp_count = getattr(self, "_tmp_count", 0) + 1
                temp = f"_{stmt.name}{self._tmp_count}"
                val = _expr_to_ts(stmt.value, lv)
                await_ = "await " if isinstance(stmt.value, ast.Call) and not val.startswith("(await ") else ""
                lines.append(f"{pad}const {temp} = {await_}{val}")
                lines.append(f"{pad}{setter}({temp})")
                lv[stmt.name] = temp

            elif isinstance(stmt, ast.ExprStmt):
                val = _expr_to_ts(stmt.expression, lv)
                if isinstance(stmt.expression, ast.Call):
                    # "(await api.post(...))" → "await api.post(...)": a statement must not
                    # start with "(" or JavaScript joins it to the line above
                    sync = val.startswith(("notify(", "toast(", "console.log(", "window.", "String(", "Math."))
                    lines.append(f"{pad}{val[1:-1]}" if val.startswith("(await ") and val.endswith(")")
                                 else f"{pad}{val}" if sync else f"{pad}await {val}")
                else:
                    lines.append(f"{pad}{val}")

            elif isinstance(stmt, ast.IfStmt):
                cond      = _unwrap_parens(_expr_to_ts(stmt.condition, lv))
                then_body = block(stmt.then_body)
                lines.append(f"{pad}if ({cond}) {{")
                if then_body.strip():
                    lines.append(then_body)
                if stmt.else_body:
                    lines.append(f"{pad}}} else {{")
                    else_body = block(stmt.else_body)
                    if else_body.strip():
                        lines.append(else_body)
                lines.append(f"{pad}}}")

            else:
                lines.append(f"{pad}// {type(stmt).__name__}")

        return "\n".join(lines) + ("\n" if lines else "")

    # ── App.tsx generator ──────────────────────────────────────────────────────

    def _gen_app_tsx(self, app: Optional[ast.AppDecl],
                     components: Dict[str, ast.ComponentDecl]) -> str:
        """App.tsx: every layout renders inside the kit's AppShell (navigation,
        header with breadcrumb/search/notifications/theme, footer, toasts)."""
        title = app.title if app and app.title else (app.name if app else "MCN App")
        layout = app.layout if app else None
        nav: List[Tuple[str, str, str, str]] = []      # (label, icon, component, group)
        shell = "top"
        if layout and layout.sidebar:
            shell = "sidebar"
            nav = [(n.label, n.icon or self._nav_icon(n.label), n.component or n.label.replace(" ", ""), n.group)
                   for n in layout.sidebar]
        elif layout and layout.tabs:
            shell = "tabs"
            nav = [(t.label, self._nav_icon(t.label), t.component or t.label.replace(" ", ""), "") for t in layout.tabs]
        elif layout and layout.routes:
            shell = "sidebar" if len(layout.routes) > 3 else "tabs"
            nav = [((r.path.strip("/").replace("-", " ").title() or "Home"), self._nav_icon(r.path.strip("/") or "home"), r.component, "")
                   for r in layout.routes]
        names = [n for n in ((layout.main if layout else None) or list(components.keys())) if n in components]
        nav = [n for n in nav if n[2] in components]
        used = {n[2] for n in nav}
        imports = "\n".join(f'import {{ {name} }} from "./components/{name}"' for name in components
                            if name in used or (not nav and name in names))

        if nav:
            items = ",\n".join(
                f'  {{ label: {json.dumps(label)}, icon: {json.dumps(icon)}, element: <{comp} />'
                + (f", group: {json.dumps(group)}" if group else "") + " }"
                for label, icon, comp, group in nav)
        else:
            stacked = "\n".join(f"        <{name} />" for name in names)
            items = f'  {{ label: "Home", icon: "Home", element: (\n      <div className="space-y-6">\n{stacked}\n      </div>\n    ) }}'
        extra = ""
        if app and app.footer:
            extra += f" footer={{{json.dumps(app.footer)}}}"
        if app and app.logo:
            extra += f" logo={{{json.dumps(app.logo)}}}"
        return f'''import {{ AppShell, type NavItem }} from "@/components/ui/app-shell"
{imports}
import "./globals.css"

const NAV: NavItem[] = [
{items},
]

export default function App() {{
  return <AppShell title={{{json.dumps(title)}}} layout="{shell}" nav={{NAV}}{extra} />
}}
'''

    # Icons for common navigation labels (any name from the kit's icon set works)
    _ICON_MAP: Dict[str, str] = {
        "deals":       "TrendingUp",
        "contacts":    "Users",
        "companies":   "Building2",
        "activities":  "Calendar",
        "dashboard":   "LayoutDashboard",
        "overview":    "LayoutGrid",
        "reports":     "BarChart3",
        "analytics":   "LineChart",
        "settings":    "Settings",
        "profile":     "User",
        "orders":      "ShoppingCart",
        "products":    "Package",
        "inventory":   "Warehouse",
        "customers":   "UserCheck",
        "invoices":    "FileText",
        "expenses":    "Receipt",
        "tasks":       "CheckSquare",
        "projects":    "FolderOpen",
        "team":        "Users2",
        "home":        "Home",
        "leads":       "Target",
        "pipeline":    "Kanban",
        "messages":    "MessageSquare",
        "notifications": "Bell",
    }

    def _nav_icon(self, label: str) -> str:
        return self._ICON_MAP.get(label.lower(), "Circle")

    def _gen_api_service(self, app: Optional[ast.AppDecl]) -> str:
        return '''\
/**
 * Calls to the MCN backend. Every endpoint answers POST with a JSON body.
 * The address comes from window.MCN_API_URL (set by Studio's preview), then
 * VITE_API_URL, then http://localhost:8080.
 *
 * Services declared with `auth "token"` or `auth "jwt"` need a bearer token.
 * It comes from window.MCN_API_TOKEN, then localStorage "mcn_token" (set it
 * after login), then VITE_API_TOKEN.
 */
import type { BackendValue } from "../types"

declare global {
  interface Window {
    MCN_API_URL?: string
    MCN_API_TOKEN?: string
  }
}

const env = import.meta.env ?? {}

const BASE: string =
  (typeof window !== "undefined" && window.MCN_API_URL) || env.VITE_API_URL || "http://localhost:8080"

function token(): string {
  try {
    return window.MCN_API_TOKEN || localStorage.getItem("mcn_token") || env.VITE_API_TOKEN || ""
  } catch {
    return env.VITE_API_TOKEN || ""
  }
}

export function setToken(value: string | null): void {
  try {
    if (value) localStorage.setItem("mcn_token", value)
    else localStorage.removeItem("mcn_token")
  } catch {
    // Storage is unavailable (private mode); the token lasts for this page only
  }
}

// Single sign-on (`auth "sso"`): after signing in, the backend sends people back with
// #mcn_token=... in the address. Keep the token and tidy the address.
if (typeof window !== "undefined" && window.location.hash.includes("mcn_token=")) {
  const params = new URLSearchParams(window.location.hash.slice(1))
  const signedIn = params.get("mcn_token")
  if (signedIn) {
    setToken(signedIn)
    params.delete("mcn_token")
    const rest = params.toString()
    window.history.replaceState(null, "", window.location.pathname + window.location.search + (rest ? `#${rest}` : ""))
  }
}

/** Sign out of single sign-on: forget the token and return to the sign-in page. */
export function signOut(): void {
  setToken(null)
  window.location.reload()
}

type ErrorBody = { error?: string; detail?: string } | null

async function request<T>(path: string, body?: unknown): Promise<T> {
  let res: Response
  const auth = token()
  try {
    res = await fetch(`${BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    window.dispatchEvent(new CustomEvent("mcn:backend-offline", { detail: BASE }))
    throw new Error(`Can't reach the backend at ${BASE}. Is it running?`)
  }
  const data: unknown = await res.json().catch(() => null)
  const signIn = (data as { sso_login?: string } | null)?.sso_login
  if (res.status === 401 && signIn) {
    // An SSO service: go to the organization's sign-in page and come back here
    setToken(null)
    window.location.assign(`${BASE}${signIn}?return_to=${encodeURIComponent(window.location.href)}`)
  }
  if (!res.ok) {
    const err = data as ErrorBody
    // The app's own errors read as they are; anything else names the call that failed
    throw new Error(err?.error || `${path}: ${err?.detail || res.statusText || "request failed"} (${res.status})`)
  }
  return data as T
}

export const api = {
  get: <T = BackendValue>(path: string) => request<T>(path),
  post: <T = BackendValue>(path: string, body: unknown = {}) => request<T>(path, body),
}
'''

    def _gen_vite_env(self) -> str:
        return '''\
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_API_TOKEN?: string
}
'''

    def _gen_main_tsx(self) -> str:
        return '''\
import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./globals.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'''

    def _gen_globals_css(self, theme: str) -> str:
        # Full shadcn CSS variable set — theme presets only override a subset
        base_vars = {
            "--background":            "0 0% 100%",
            "--foreground":            "222.2 84% 4.9%",
            "--card":                  "0 0% 100%",
            "--card-foreground":       "222.2 84% 4.9%",
            "--popover":               "0 0% 100%",
            "--popover-foreground":    "222.2 84% 4.9%",
            "--primary":               "221.2 83.2% 53.3%",
            "--primary-foreground":    "210 40% 98%",
            "--secondary":             "210 40% 96.1%",
            "--secondary-foreground":  "222.2 47.4% 11.2%",
            "--muted":                 "210 40% 96.1%",
            "--muted-foreground":      "215.4 16.3% 46.9%",
            "--accent":                "210 40% 96.1%",
            "--accent-foreground":     "222.2 47.4% 11.2%",
            "--destructive":           "0 84.2% 60.2%",
            "--destructive-foreground":"210 40% 98%",
            "--border":                "214.3 31.8% 91.4%",
            "--input":                 "214.3 31.8% 91.4%",
            "--ring":                  "221.2 83.2% 53.3%",
            "--radius":                "0.5rem",
        }
        dark_vars = {
            "--background":            "222.2 84% 4.9%",
            "--foreground":            "210 40% 98%",
            "--card":                  "222.2 84% 4.9%",
            "--card-foreground":       "210 40% 98%",
            "--popover":               "222.2 84% 4.9%",
            "--popover-foreground":    "210 40% 98%",
            "--primary":               "217.2 91.2% 59.8%",
            "--primary-foreground":    "222.2 47.4% 11.2%",
            "--secondary":             "217.2 32.6% 17.5%",
            "--secondary-foreground":  "210 40% 98%",
            "--muted":                 "217.2 32.6% 17.5%",
            "--muted-foreground":      "215 20.2% 65.1%",
            "--accent":                "217.2 32.6% 17.5%",
            "--accent-foreground":     "210 40% 98%",
            "--destructive":           "0 62.8% 30.6%",
            "--destructive-foreground":"210 40% 98%",
            "--border":                "217.2 32.6% 17.5%",
            "--input":                 "217.2 32.6% 17.5%",
            "--ring":                  "224.3 76.3% 48%",
        }
        # Apply theme overrides on top of base
        overrides = _THEMES.get(theme, {})
        light = {**base_vars, **overrides}
        light_css = "\n".join(f"    {k}: {v};" for k, v in light.items())
        dark_css  = "\n".join(f"    {k}: {v};" for k, v in dark_vars.items())
        return f'''\
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  :root {{
{light_css}
  }}
  .dark {{
{dark_css}
  }}
  * {{
    @apply border-border;
  }}
  body {{
    @apply bg-background text-foreground;
    font-feature-settings:
      "rlig" 1,
      "calt" 1;
  }}
}}

@layer utilities {{
  .glass-card {{
    background: rgba(255, 255, 255, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.25);
  }}
  .dark .glass-card {{
    background: rgba(15, 23, 42, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }}
  .premium-gradient-bg {{
    background: radial-gradient(circle at top left, var(--accent) 0%, var(--background) 70%);
  }}
  .hover-scale {{
    transition:
      transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
      box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .hover-scale:hover {{
    transform: translateY(-2px) scale(1.01);
    box-shadow:
      0 10px 25px -5px rgba(0, 0, 0, 0.05),
      0 8px 10px -6px rgba(0, 0, 0, 0.05);
  }}
}}
'''

    def _gen_package_json(self, app: Optional[ast.AppDecl]) -> str:
        name = app.name.lower().replace(" ", "-") if app else "mcn-app"
        return prettier_json({
            "name":        name,
            "version":     "0.1.0",
            "private":     True,
            "type":        "module",
            "scripts": {
                "dev":     "vite",
                "build":   "tsc && vite build",
                "preview": "vite preview",
                "typecheck": "tsc --noEmit",
                "lint":    "eslint .",
                "format":  "prettier --write .",
                "test":    "vitest run",
            },
            # Everything else (components, charts, icons, toasts, routing) is the
            # MCN UI kit, copied into src/ — so React is the only dependency
            "dependencies": {
                "react":           "^18.3.1",
                "react-dom":       "^18.3.1",
            },
            "devDependencies": {
                "@eslint/js":          "^9.13.0",
                "@testing-library/jest-dom": "^6.6.2",
                "@testing-library/react": "^16.0.1",
                "@types/react":        "^18.3.0",
                "@types/react-dom":    "^18.3.0",
                "@vitejs/plugin-react": "^4.3.1",
                "autoprefixer":        "^10.4.20",
                "eslint":              "^9.13.0",
                "eslint-plugin-react-hooks": "^5.0.0",
                "globals":             "^15.11.0",
                "jsdom":               "^25.0.1",
                "postcss":             "^8.4.47",
                "prettier":            "^3.3.3",
                "tailwindcss":         "^3.4.13",
                "typescript":          "^5.5.3",
                "typescript-eslint":   "^8.11.0",
                "vite":                "^5.4.8",
                "vitest":              "^2.1.3",
            },
        }) + "\n"

    def _gen_tailwind_config(self) -> str:
        return '''\
import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
}

export default config
'''

    def _gen_vite_config(self) -> str:
        return '''\
/// <reference types="vitest" />
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
})
'''

    # ── Lint, format and test setup ────────────────────────────────────────────

    _ESLINT_CONFIG = '''\
import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import tseslint from "typescript-eslint"

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2020, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
)
'''

    _PRETTIER_CONFIG = json.dumps({"semi": False, "printWidth": 120, "tabWidth": 2}, indent=2) + "\n"

    _TEST_SETUP = '''\
import "@testing-library/jest-dom/vitest"

// Browser APIs jsdom doesn't have, used by charts and layout components
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
})) as typeof window.matchMedia
Element.prototype.scrollIntoView ??= () => {}
'''

    def _gen_screens_test(self, components) -> str:
        names = sorted(components)
        imports = "\n".join(f'import {{ {n} }} from "../components/{n}"' for n in names)
        cases = "\n".join(
            f'  it("{n} renders", () => {{\n'
            f"    const {{ container }} = render(<{n} />)\n"
            f"    expect(container.firstChild).not.toBeNull()\n"
            f"  }})\n" for n in names)
        return f'''\
// Generated by MCN on every build: a smoke test for each screen. Add your own tests in other files.
import {{ render }} from "@testing-library/react"
import {{ describe, expect, it, vi }} from "vitest"
{imports}

// The backend answers every call with an empty list
vi.mock("../services/api", () => ({{
  api: {{ get: vi.fn(async () => ({{ data: [] }})), post: vi.fn(async () => ({{ data: [] }})) }},
  setToken: vi.fn(),
}}))

describe("screens", () => {{
{cases}}})
'''

    def _gen_postcss_config(self) -> str:
        return '''\
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
'''

    def _gen_shadcn_config(self) -> str:
        return prettier_json({
            "$schema":   "https://ui.shadcn.com/schema.json",
            "style":     "default",
            "rsc":       False,
            "tsx":       True,
            "tailwind": {
                "config":        "tailwind.config.ts",
                "css":           "src/globals.css",
                "baseColor":     "slate",
                "cssVariables":  True,
            },
            "aliases": {
                "components": "@/components",
                "utils":      "@/lib/utils",
            },
        }) + "\n"

    def _gen_tsconfig(self) -> str:
        return prettier_json({
            "compilerOptions": {
                "target":            "ES2020",
                "useDefineForClassFields": True,
                "lib":               ["ES2020", "DOM", "DOM.Iterable"],
                "module":            "ESNext",
                "skipLibCheck":      True,
                "moduleResolution":  "bundler",
                "allowImportingTsExtensions": True,
                "resolveJsonModule": True,
                "isolatedModules":   True,
                "noEmit":            True,
                "jsx":               "react-jsx",
                "strict":            True,
                "noUnusedLocals":    False,
                "noUnusedParameters": False,
                "noFallthroughCasesInSwitch": True,
                "baseUrl":           ".",
                "paths": {
                    "@/*": ["./src/*"],
                },
            },
            "include": ["src"],
            "references": [{"path": "./tsconfig.node.json"}],
        }) + "\n"

    def _gen_index_html(self, title: str) -> str:
        return f'''\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''

    def _write_ui_components(self, src: Path) -> List[Path]:
        """Copy the MCN UI kit (mcn/ui-kit/react/src) into the generated project.

        The same source is bundled for Studio's live preview, so an exported app
        and its preview render with identical components."""
        written: List[Path] = []
        for path in sorted(_KIT_DIR.rglob("*")):
            if path.is_dir() or path.name == "index.ts":
                continue
            dest = src / path.relative_to(_KIT_DIR)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest)
        print(f"  write  {len(written)} MCN UI kit files → src/components/ui, src/lib")
        return written
