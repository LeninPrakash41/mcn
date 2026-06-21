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
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import ast_nodes as ast


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
    "toast":        ([],                               "sonner",   "toast"),
    # Charts — recharts (not shadcn, imported directly from "recharts")
    "bar_chart":   (["BarChart", "Bar", "XAxis", "YAxis", "CartesianGrid", "Tooltip", "ResponsiveContainer"],
                    "recharts", "BarChart"),
    "line_chart":  (["LineChart", "Line", "XAxis", "YAxis", "CartesianGrid", "Tooltip", "ResponsiveContainer"],
                    "recharts", "LineChart"),
    "pie_chart":   (["PieChart", "Pie", "Cell", "Tooltip", "Legend"],
                    "recharts", "PieChart"),
    # Stat card (plain div-based, no shadcn package)
    "stat_card":   (["Card", "CardContent"],           "card",     "Card"),
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
    "default": {
        "--radius":     "0.5rem",
        "--background": "0 0% 100%",
        "--foreground": "222.2 84% 4.9%",
        "--primary":    "221.2 83.2% 53.3%",
        "--accent":     "210 40% 96.1%",
    },
}


# ── helpers ────────────────────────────────────────────────────────────────────

def _pascal(name: str) -> str:
    """snake_case / kebab-case → PascalCase."""
    return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def _camel(name: str) -> str:
    """snake_case → camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


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
        if isinstance(expr.value, str):
            return json.dumps(expr.value)
        if isinstance(expr.value, bool):
            return "true" if expr.value else "false"
        return str(expr.value)
    if isinstance(expr, ast.Variable):
        return lv.get(expr.name, expr.name)
    if isinstance(expr, ast.Property):
        obj = _expr_to_ts(expr.object, lv)
        return f"{obj}.{expr.name}"
    if isinstance(expr, ast.Binary):
        left  = _expr_to_ts(expr.left, lv)
        right = _expr_to_ts(expr.right, lv)
        op    = expr.operator
        if op == "+":
            # Produce a template literal: `${left}${right}`
            # Strip surrounding quotes from string literals so they merge cleanly
            def _unwrap(ts: str) -> str:
                if ts.startswith('"') and ts.endswith('"'):
                    return ts[1:-1]
                return f"${{{ts}}}"
            return f"`{_unwrap(left)}{_unwrap(right)}`"
        return f"{left} {op} {right}"
    if isinstance(expr, ast.Call):
        if isinstance(expr.callee, ast.Variable):
            fn = expr.callee.name
            # Build the payload object from positional args (use var names as keys)
            pairs = []
            for a in expr.arguments:
                if isinstance(a, ast.Variable):
                    pairs.append(a.name)
                else:
                    pairs.append(_expr_to_ts(a, lv))
            body = "{" + ", ".join(pairs) + "}"
            return f"api.post('/{fn}', {body})"
        return '""'
    if isinstance(expr, ast.Array):
        return "[" + ", ".join(_expr_to_ts(e, lv) for e in expr.elements) + "]"
    return '""'


# ── main compiler class ────────────────────────────────────────────────────────

class UICompiler:
    """
    Compile MCN component/app AST → React + shadcn/ui TypeScript source files.

    Usage:
        compiler = UICompiler(output_dir=Path("my_app/frontend"))
        compiler.compile(evaluator)   # evaluator has .components and .app_decl
    """

    def __init__(self, output_dir: Path):
        self.out              = Path(output_dir)
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

        # Always write lib/utils.ts — required by every shadcn component
        utils_path = src / "lib" / "utils.ts"
        utils_path.write_text(
            'import { type ClassValue, clsx } from "clsx"\n'
            'import { twMerge } from "tailwind-merge"\n'
            "\n"
            "export function cn(...inputs: ClassValue[]) {\n"
            "  return twMerge(clsx(inputs))\n"
            "}\n"
        )
        written.append(utils_path)
        print(f"  write  {utils_path.relative_to(self.out.parent)}")

        app_decl: Optional[ast.AppDecl] = evaluator.app_decl
        components: Dict[str, ast.ComponentDecl] = evaluator.components

        theme = app_decl.theme if app_decl else "default"

        # 1. Compile each component
        for name, comp in components.items():
            path = src / "components" / f"{name}.tsx"
            path.write_text(self._compile_component(comp))
            written.append(path)
            print(f"  write  {path.relative_to(self.out.parent)}")

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
        tsconfig_node.write_text(json.dumps({
            "compilerOptions": {
                "composite":        True,
                "skipLibCheck":     True,
                "module":           "ESNext",
                "moduleResolution": "bundler",
                "allowSyntheticDefaultImports": True,
            },
            "include": ["vite.config.ts", "tailwind.config.ts"],
        }, indent=2))
        written.append(tsconfig_node)
        print(f"  write  {tsconfig_node.relative_to(self.out.parent)}")

        # 12. index.html
        index_html = self.out / "index.html"
        title = app_decl.title if app_decl else "MCN App"
        index_html.write_text(self._gen_index_html(title))
        written.append(index_html)
        print(f"  write  {index_html.relative_to(self.out.parent)}")

        # Print shadcn install command
        if self._shadcn_needed:
            pkgs = " ".join(sorted(self._shadcn_needed))
            print(f"\n  shadcn  npx shadcn@latest add {pkgs}")

        return written

    # ── Component compiler ─────────────────────────────────────────────────────

    def _compile_component(self, comp: ast.ComponentDecl) -> str:
        """Compile a single ComponentDecl → .tsx file content."""
        self._current_comp = comp
        self._extra_imports = set()

        shadcn_imports: Dict[str, List[str]] = {}

        # Collect shadcn imports needed by this component's render tree
        if comp.render:
            self._collect_imports(comp.render.elements, shadcn_imports)

        # Detect CRUD mode (component has edit_item state) — needed before building hooks list
        has_crud = any(s.name == "edit_item" for s in comp.states)

        # Determine which React hooks are needed
        has_load_handler   = any(h.event == "load" for h in comp.handlers)
        has_other_handlers = any(h.event != "load" for h in comp.handlers)
        react_hooks: List[str] = ["useState"]
        if has_load_handler:
            react_hooks.append("useEffect")
        if has_other_handlers or has_crud:
            react_hooks.append("useCallback")

        imports: List[str] = [
            f'import React, {{ {", ".join(react_hooks)} }} from "react"',
            'import { api } from "../services/api"',
        ]
        for pkg_path, names in sorted(shadcn_imports.items()):
            imports.append(f'import {{ {", ".join(sorted(set(names)))} }} from "{pkg_path}"')

        # useState hooks from state declarations
        hooks: List[str] = []
        for s in comp.states:
            var_name   = s.name
            setter     = "set" + _pascal(var_name)
            default_ts = _expr_to_ts(s.value)
            hooks.append(f"  const [{var_name}, {setter}] = useState({default_ts})")

        if has_crud:
            # entity name: ClaimTable → claim, OrderTable → order
            entity = comp.name.replace("Table", "").lower()
            # Fields with edit_ prefix
            edit_fields = [s for s in comp.states if s.name.startswith("edit_")
                           and s.name not in ("edit_item", "edit_item_id")]
            field_setters = "\n    ".join(
                f"set{_pascal(s.name)}((row as any).{s.name[5:]} ?? '')"
                for s in edit_fields
            )
            save_payload_fields = ", ".join(
                f"{s.name[5:]}: {s.name}" for s in edit_fields
            )
            hooks.append(f"  const [editItemId, setEditItemId] = useState<number | null>(null)")

        # Event handlers from on blocks
        handlers: List[str] = []
        for h in comp.handlers:
            fn_name = _camel(h.event)
            body_ts = self._stmts_to_ts(h.body, indent=6 if h.event == "load" else 4)
            if h.event == "load":
                # useEffect with async IIFE
                handlers.append(
                    f"  useEffect(() => {{\n"
                    f"    ;(async () => {{\n"
                    f"{body_ts}"
                    f"    }})()\n"
                    f"  }}, [])"
                )
            else:
                dep_names = ", ".join(s.name for s in comp.states)
                handlers.append(
                    f"  const {fn_name} = useCallback(async (e?: React.FormEvent) => {{\n"
                    f"    if (e) e.preventDefault()\n"
                    f"{body_ts}"
                    f"  }}, [{dep_names}])"
                )

        # Inject CRUD helper functions for components with edit_item state
        if has_crud:
            handlers.append(
                f"  const handleEdit = useCallback((row: any) => {{\n"
                f"    setEditItemId(row.id)\n"
                f"    {field_setters}\n"
                f"    setEditItem(row)\n"
                f"    setShowEditModal(true)\n"
                f"  }}, [])\n"
            )
            handlers.append(
                f"  const handleDelete = useCallback(async (id: number) => {{\n"
                f'    if (!window.confirm("Delete this {entity}?")) return\n'
                f"    await api.post('/delete_{entity}', {{ id }})\n"
                f"    const _resp = await api.post('/list_{entity}s', {{}})\n"
                f"    setItems(_resp.data ?? _resp)\n"
                f"  }}, [])\n"
            )
            handlers.append(
                f"  const handleSave = useCallback(async () => {{\n"
                f"    await api.post('/update_{entity}', {{ id: editItemId, {save_payload_fields} }})\n"
                f"    setShowEditModal(false)\n"
                f"    const _resp = await api.post('/list_{entity}s', {{}})\n"
                f"    setItems(_resp.data ?? _resp)\n"
                f"  }}, [editItemId, {', '.join(s.name for s in edit_fields)}])\n"
            )

        # Render JSX (must happen before final import assembly so _extra_imports is populated)
        jsx_lines: List[str] = []
        if comp.render:
            for el in comp.render.elements:
                jsx_lines.extend(self._element_to_jsx(el, indent=4))
        else:
            jsx_lines.append("    <div>Empty component</div>")

        # Wrap in Fragment when multiple root elements (e.g. main card + edit modal)
        needs_fragment = len(comp.render.elements if comp.render else []) > 1
        if needs_fragment:
            jsx_lines = ["    <>", *["  " + ln for ln in jsx_lines], "    </>"]

        # Merge lucide-react imports and append remaining extras
        lucide_icons: list = []
        other_extras: list = []
        for line in self._extra_imports:
            if '"lucide-react"' in line:
                # Extract icon name from: import { X } from "lucide-react"
                import importlib as _il  # local import to avoid polluting module scope
                import re as _re
                m = _re.search(r'\{\s*([^}]+)\s*\}', line)
                if m:
                    lucide_icons.extend(n.strip() for n in m.group(1).split(','))
            else:
                other_extras.append(line)
        # Merge with any existing lucide-react import in imports list
        existing_lucide_idx = next(
            (i for i, ln in enumerate(imports) if '"lucide-react"' in ln), None)
        if lucide_icons:
            if existing_lucide_idx is not None:
                # Extract existing names and merge
                import re as _re2
                m2 = _re2.search(r'\{\s*([^}]+)\s*\}', imports[existing_lucide_idx])
                existing_names = [n.strip() for n in m2.group(1).split(',')] if m2 else []
                merged = sorted(set(existing_names + lucide_icons))
                imports[existing_lucide_idx] = f'import {{ {", ".join(merged)} }} from "lucide-react"'
            else:
                imports.append(f'import {{ {", ".join(sorted(set(lucide_icons)))} }} from "lucide-react"')
        for extra in sorted(other_extras):
            imports.append(extra)

        # Assemble
        lines = [
            *imports,
            "",
            f"export function {comp.name}() {{",
            *hooks,
            *([""] if hooks else []),
            *handlers,
            *([""] if handlers else []),
            "  return (",
            *jsx_lines,
            "  )",
            "}",
            "",
            f"export default {comp.name}",
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
                self._shadcn_needed.add(slug)
                # recharts and other non-shadcn libs import directly by package name
                if slug in ("recharts",):
                    pkg_path = slug
                else:
                    pkg_path = f"@/components/ui/{slug}"
                if pkg_path not in acc:
                    acc[pkg_path] = []
                acc[pkg_path].extend(names)

            # input/textarea with label attr → needs Label import
            if tag in ("input", "textarea"):
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

        # card — adds CardContent wrapper automatically
        if tag == "card":
            lines.append(f'{pad}<Card {props}>')
            for child in el.children:
                lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</Card>')
            return lines

        # table — generate full table structure with data rows if table_body is empty
        if tag == "table":
            # Detect CRUD mode: component has edit_item state
            has_actions = (self._current_comp is not None and
                           any(s.name == "edit_item" for s in self._current_comp.states))

            # Extract column names from table_header for data row generation
            col_names: List[str] = []
            for child in el.children:
                if child.tag == "table_header":
                    for row_el in child.children:
                        if row_el.tag == "table_row":
                            for th in row_el.children:
                                if th.tag == "table_head" and th.text:
                                    if isinstance(th.text, ast.Literal):
                                        col_names.append(str(th.text.value))

            lines.append(f'{pad}<Table {props}>')
            for child in el.children:
                if child.tag == "table_header" and has_actions:
                    # Inject Actions column into header
                    lines.extend(self._element_to_jsx_header_with_actions(child, indent + 2))
                elif child.tag == "table_body" and not child.children:
                    # Find the array-typed state variable in the current component
                    arr_state = None
                    if self._current_comp:
                        arr_state = next(
                            (s.name for s in self._current_comp.states
                             if isinstance(s.value, ast.Array)),
                            None,
                        )
                    entity = (self._current_comp.name.replace("Table", "").lower()
                              if self._current_comp else "item")
                    lines.extend(
                        self._gen_table_body_rows(arr_state or "items", col_names,
                                                  indent + 2, has_actions, entity)
                    )
                else:
                    lines.extend(self._element_to_jsx(child, indent + 2))
            lines.append(f'{pad}</Table>')
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
                lines.append(f'{pad}      {{{opts_expr}.map((o: any) => <SelectItem key={{String(o)}} value={{String(o)}}>{{String(o)}}</SelectItem>)}}')
                lines.append(f'{pad}    </SelectContent>')
                lines.append(f'{pad}  </Select>')
                lines.append(f'{pad}</div>')
            else:
                lines.append(f'{pad}<Select value={{{var_name}}} onValueChange={{{setter}}}>')
                lines.append(f'{pad}  <SelectTrigger><SelectValue placeholder={{{ph_text}}} /></SelectTrigger>')
                lines.append(f'{pad}  <SelectContent>')
                lines.append(f'{pad}    {{{opts_expr}.map((o: any) => <SelectItem key={{String(o)}} value={{String(o)}}>{{String(o)}}</SelectItem>)}}')
                lines.append(f'{pad}  </SelectContent>')
                lines.append(f'{pad}</Select>')
            return lines

        # bar_chart
        if tag == "bar_chart":
            data_attr  = next((a for a in el.attrs if a.key == "data"),   None)
            x_attr     = next((a for a in el.attrs if a.key == "x_key"),  None)
            y_attr     = next((a for a in el.attrs if a.key == "y_key"),  None)
            h_attr     = next((a for a in el.attrs if a.key == "height"), None)
            data_expr  = _expr_to_ts(data_attr.value)  if data_attr  else "[]"
            x_key      = _expr_to_ts(x_attr.value)     if x_attr     else '"label"'
            y_key      = _expr_to_ts(y_attr.value)      if y_attr     else '"value"'
            height     = _expr_to_ts(h_attr.value)      if h_attr     else "300"
            lines += [
                f'{pad}<ResponsiveContainer width="100%" height={{{height}}}>',
                f'{pad}  <BarChart data={{{data_expr}}}>',
                f'{pad}    <CartesianGrid strokeDasharray="3 3" />',
                f'{pad}    <XAxis dataKey={{{x_key}}} />',
                f'{pad}    <YAxis />',
                f'{pad}    <Tooltip />',
                f'{pad}    <Bar dataKey={{{y_key}}} fill="#6366f1" />',
                f'{pad}  </BarChart>',
                f'{pad}</ResponsiveContainer>',
            ]
            return lines

        # line_chart
        if tag == "line_chart":
            data_attr  = next((a for a in el.attrs if a.key == "data"),   None)
            x_attr     = next((a for a in el.attrs if a.key == "x_key"),  None)
            y_attr     = next((a for a in el.attrs if a.key == "y_key"),  None)
            h_attr     = next((a for a in el.attrs if a.key == "height"), None)
            data_expr  = _expr_to_ts(data_attr.value)  if data_attr  else "[]"
            x_key      = _expr_to_ts(x_attr.value)     if x_attr     else '"label"'
            y_key      = _expr_to_ts(y_attr.value)      if y_attr     else '"value"'
            height     = _expr_to_ts(h_attr.value)      if h_attr     else "300"
            lines += [
                f'{pad}<ResponsiveContainer width="100%" height={{{height}}}>',
                f'{pad}  <LineChart data={{{data_expr}}}>',
                f'{pad}    <CartesianGrid strokeDasharray="3 3" />',
                f'{pad}    <XAxis dataKey={{{x_key}}} />',
                f'{pad}    <YAxis />',
                f'{pad}    <Tooltip />',
                f'{pad}    <Line type="monotone" dataKey={{{y_key}}} stroke="#6366f1" strokeWidth={{2}} />',
                f'{pad}  </LineChart>',
                f'{pad}</ResponsiveContainer>',
            ]
            return lines

        # pie_chart
        if tag == "pie_chart":
            data_attr  = next((a for a in el.attrs if a.key == "data"),       None)
            name_attr  = next((a for a in el.attrs if a.key == "name_key"),   None)
            val_attr   = next((a for a in el.attrs if a.key == "value_key"),  None)
            h_attr     = next((a for a in el.attrs if a.key == "height"),     None)
            data_expr  = _expr_to_ts(data_attr.value) if data_attr else "[]"
            name_key   = _expr_to_ts(name_attr.value) if name_attr else '"name"'
            val_key    = _expr_to_ts(val_attr.value)  if val_attr  else '"value"'
            height     = _expr_to_ts(h_attr.value)    if h_attr    else "300"
            colors     = '["#6366f1","#8b5cf6","#a78bfa","#c4b5fd","#ddd6fe"]'
            lines += [
                f'{pad}<ResponsiveContainer width="100%" height={{{height}}}>',
                f'{pad}  <PieChart>',
                f'{pad}    <Pie data={{{data_expr}}} dataKey={{{val_key}}} nameKey={{{name_key}}} cx="50%" cy="50%" outerRadius={{80}}>',
                f'{pad}      {{{data_expr}.map((_: any, i: number) => <Cell key={{i}} fill={{{colors}[i % {colors}.length]}} />)}}',
                f'{pad}    </Pie>',
                f'{pad}    <Tooltip />',
                f'{pad}    <Legend />',
                f'{pad}  </PieChart>',
                f'{pad}</ResponsiveContainer>',
            ]
            return lines

        # stat_card — a compact KPI card with icon, value, trend
        if tag == "stat_card":
            label_attr = next((a for a in el.attrs if a.key == "label"), None)
            value_attr = next((a for a in el.attrs if a.key == "value"), None)
            unit_attr  = next((a for a in el.attrs if a.key == "unit"),  None)
            icon_attr  = next((a for a in el.attrs if a.key == "icon"),  None)
            trend_attr = next((a for a in el.attrs if a.key == "trend"), None)
            trend_lbl  = next((a for a in el.attrs if a.key == "trend_label"), None)
            color_attr = next((a for a in el.attrs if a.key == "color"), None)
            lbl   = _expr_to_ts(label_attr.value) if label_attr else '""'
            val   = _expr_to_ts(value_attr.value) if value_attr else '""'
            unit  = _expr_to_ts(unit_attr.value)  if unit_attr  else '""'
            icon  = icon_attr.value.value if icon_attr and isinstance(icon_attr.value, ast.Literal) else "TrendingUp"
            trend = _expr_to_ts(trend_attr.value) if trend_attr else None
            tlbl  = _expr_to_ts(trend_lbl.value) if trend_lbl else '"vs last month"'
            color = color_attr.value.value if color_attr and isinstance(color_attr.value, ast.Literal) else "primary"
            icon_cls = {
                "green": "text-green-600 bg-green-100",
                "red":   "text-red-600 bg-red-100",
                "blue":  "text-blue-600 bg-blue-100",
                "amber": "text-amber-600 bg-amber-100",
                "purple":"text-purple-600 bg-purple-100",
            }.get(color, "text-primary bg-primary/10")
            self._extra_imports.add(f'import {{ {icon} }} from "lucide-react"')
            trend_jsx = ""
            if trend:
                trend_jsx = (
                    f'\n{pad}    <p className="text-xs text-muted-foreground mt-1">'
                    f'<span className={{({trend}) >= 0 ? "text-green-600" : "text-red-600"}}>'
                    f'{{({trend}) >= 0 ? "↑" : "↓"}} {{{trend}}}%</span> {{{tlbl}}}</p>'
                )
            lines += [
                f'{pad}<Card>',
                f'{pad}  <CardContent className="p-5">',
                f'{pad}    <div className="flex items-center justify-between">',
                f'{pad}      <div>',
                f'{pad}        <p className="text-sm font-medium text-muted-foreground">{{{lbl}}}</p>',
                f'{pad}        <p className="text-2xl font-bold mt-1">{{{val}}}<span className="text-sm font-normal ml-1 text-muted-foreground">{{{unit}}}</span></p>',
                f'{pad}        {trend_jsx}',
                f'{pad}      </div>',
                f'{pad}      <div className="p-2 rounded-lg {icon_cls}">',
                f'{pad}        <{icon} className="w-5 h-5" />',
                f'{pad}      </div>',
                f'{pad}    </div>',
                f'{pad}  </CardContent>',
                f'{pad}</Card>',
            ]
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
                f'{inner_pad}  {{{opts_expr}.map((o: any) => (',
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
                f'{pad}    {{{items_expr}.map((item: any, i: number) => (',
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
        if has_actions:
            actions_cell = (
                f"\n{p4}<TableCell>"
                f"\n{p6}<button"
                f'\n{p6}  className="mr-2 text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded hover:bg-blue-200"'
                f"\n{p6}  onClick={{() => handleEdit(row)}}"
                f"\n{p6}>Edit</button>"
                f"\n{p6}<button"
                f'\n{p6}  className="text-xs px-2 py-1 bg-red-100 text-red-800 rounded hover:bg-red-200"'
                f"\n{p6}  onClick={{() => handleDelete(row.id)}}"
                f"\n{p6}>Delete</button>"
                f"\n{p4}</TableCell>"
            )

        if not cols:
            # No column info — use Object.entries as fallback
            return [
                f"{pad}<TableBody>",
                f"{p2}{{{state_name}.map((row: any, i: number) => (",
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
            f"{p2}{{{state_name}.map((row: any, i: number) => (",
            f"{p4}<TableRow key={{i}}>",
            cells,
            *(([actions_cell] if actions_cell else [])),
            f"{p4}</TableRow>",
            f"{p2}))}}",
            f"{pad}</TableBody>",
        ]

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
                props.append(f'className="grid grid-cols-{n} gap-4"')
                continue

            # bind=name  →  value={name} onChange={e => setName(...)}
            if key == "bind":
                var_name = _expr_to_ts(val)
                setter   = "set" + _pascal(var_name)
                if tag == "textarea":
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(e) => {setter}(e.target.value)}}')
                elif tag == "input":
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(e) => {setter}(e.target.value)}}')
                else:
                    props.append(f'value={{{var_name}}} '
                                 f'onChange={{(v) => {setter}(v)}}')
                continue

            # on_submit / on_click → onSubmit / onClick
            if key.startswith("on_"):
                react_evt = "on" + _pascal(key[3:])
                handler   = _expr_to_ts(val)
                props.append(f'{react_evt}={{{handler}}}')
                continue

            # type="..." placeholder="..." variant="..."
            if val is None:
                props.append(key)  # boolean flag
            elif isinstance(val, ast.Literal) and isinstance(val.value, str):
                props.append(f'{_camel(key)}={json.dumps(val.value)}')
            else:
                props.append(f'{_camel(key)}={{{_expr_to_ts(val)}}}')

        return " ".join(props)

    def _stmts_to_ts(self, stmts: List[ast.Stmt], indent: int = 4,
                     _lv: Optional[Dict[str, str]] = None) -> str:
        """Convert simple MCN statements to TypeScript (for event handlers).

        _lv: internal local-var substitution dict; don't pass externally.
        """
        pad   = " " * indent
        lv    = dict(_lv or {})   # copy so sibling branches don't share mutations
        lines: List[str] = []

        for stmt in stmts:
            if isinstance(stmt, ast.VarDecl):
                val = _expr_to_ts(stmt.value, lv)
                if isinstance(stmt.value, ast.Call):
                    lines.append(f"{pad}const {stmt.name} = await {val}")
                else:
                    lines.append(f"{pad}const {stmt.name} = {val}")
                # Named vars are usable directly, no setter needed
                lv[stmt.name] = stmt.name

            elif isinstance(stmt, ast.AssignStmt):
                setter = "set" + _pascal(stmt.name)
                val_expr = stmt.value
                if isinstance(val_expr, ast.Call):
                    # Capture to a temp var, then call setter — avoids stale state
                    temp = f"_{stmt.name}"
                    call_ts = _expr_to_ts(val_expr, lv)
                    lines.append(f"{pad}const {temp} = await {call_ts}")
                    lines.append(f"{pad}{setter}({temp})")
                    lv[stmt.name] = temp   # subsequent reads see the fresh value
                else:
                    val = _expr_to_ts(val_expr, lv)
                    lines.append(f"{pad}{setter}({val})")

            elif isinstance(stmt, ast.ExprStmt):
                val = _expr_to_ts(stmt.expression, lv)
                if isinstance(stmt.expression, ast.Call):
                    lines.append(f"{pad}await {val}")
                else:
                    lines.append(f"{pad}{val}")

            elif isinstance(stmt, ast.IfStmt):
                cond      = _expr_to_ts(stmt.condition, lv)
                then_body = self._stmts_to_ts(stmt.then_body, indent + 2, lv)
                lines.append(f"{pad}if ({cond}) {{")
                if then_body.strip():
                    lines.append(then_body.rstrip("\n"))
                lines.append(f"{pad}}}")

            else:
                lines.append(f"{pad}// {type(stmt).__name__}")

        return "\n".join(lines) + ("\n" if lines else "")

    # ── App.tsx generator ──────────────────────────────────────────────────────

    def _gen_app_tsx(self, app: Optional[ast.AppDecl],
                     components: Dict[str, ast.ComponentDecl]) -> str:
        title = app.title if app else "MCN App"

        comp_imports = "\n".join(
            f'import {{ {name} }} from "./components/{name}"'
            for name in components
        )

        if app and app.layout:
            layout = app.layout

            # URL routing layout (react-router-dom)
            if layout.routes:
                return self._gen_router_layout(app, components, comp_imports)

            # Sidebar layout (with or without tabs)
            if layout.sidebar:
                if layout.tabs:
                    self._shadcn_needed.add("tabs")
                return self._gen_sidebar_tabs_layout(app, components, comp_imports)

            # Tabs only
            if layout.tabs:
                self._shadcn_needed.add("tabs")
                tabs_list = "\n".join(
                    f'          <TabsTrigger value="{t.label}">{t.label}</TabsTrigger>'
                    for t in layout.tabs
                )
                tabs_content = "\n".join(
                    f'        <TabsContent value="{t.label}">\n'
                    f'          <{t.component or "div"} />\n'
                    f'        </TabsContent>'
                    for t in layout.tabs
                )
                default_tab = layout.tabs[0].label if layout.tabs else ""
                return f'''\
import React from "react"
import {{ Tabs, TabsList, TabsTrigger, TabsContent }} from "@/components/ui/tabs"
{comp_imports}
import "./globals.css"

export default function App() {{
  return (
    <div className="min-h-screen bg-background p-6">
      <h1 className="text-2xl font-bold mb-6">{title}</h1>
      <Tabs defaultValue="{default_tab}" className="w-full">
        <TabsList>
{tabs_list}
        </TabsList>
{tabs_content}
      </Tabs>
    </div>
  )
}}
'''

            # Main components stacked
            main_jsx = "\n".join(
                f'      <{name} />'
                for name in (layout.main or list(components.keys()))
            )
        else:
            main_jsx = "\n".join(f'      <{name} />' for name in components)

        return f'''\
import React from "react"
{comp_imports}
import "./globals.css"

export default function App() {{
  return (
    <div className="min-h-screen bg-background p-6">
      <h1 className="text-2xl font-bold mb-6">{title}</h1>
      <div className="space-y-6">
{main_jsx}
      </div>
    </div>
  )
}}
'''

    # Map common nav labels to lucide-react icon names
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

    def _gen_sidebar_tabs_layout(self, app: ast.AppDecl,
                                  components: Dict[str, ast.ComponentDecl],
                                  comp_imports: str) -> str:
        layout = app.layout
        title  = app.title

        # Collect icon names used
        icon_names = [self._nav_icon(n.label) for n in layout.sidebar]
        icons_import = ", ".join(sorted(set(icon_names)))

        nav_items = "\n".join(
            f'          <button\n'
            f'            onClick={{() => setActive("{n.label}")}}\n'
            f'            className={{`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm '
            f'font-medium transition-colors ${{active === "{n.label}" '
            f'? "bg-primary text-primary-foreground" '
            f': "text-muted-foreground hover:bg-accent hover:text-foreground"}}`}}\n'
            f'          >\n'
            f'            <{self._nav_icon(n.label)} className="w-4 h-4 shrink-0" />\n'
            f'            {n.label}\n'
            f'          </button>'
            for n in layout.sidebar
        )

        pages = "\n".join(
            f'      {{active === "{n.label}" && <{n.component or _pascal(n.label)} />}}'
            for n in layout.sidebar
        )

        default_page = layout.sidebar[0].label if layout.sidebar else ""

        app_icon = self._nav_icon(title.split()[0].lower()) if title else "Circle"
        all_icons = sorted(set(icon_names) | {app_icon, "LogOut", "ChevronRight"})
        icons_import_full = ", ".join(all_icons)

        return f'''\
import React, {{ useState }} from "react"
import {{ {icons_import_full} }} from "lucide-react"
{comp_imports}
import "./globals.css"

export default function App() {{
  const [active, setActive] = useState("{default_page}")

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="w-64 border-r bg-card flex flex-col shadow-sm">
        {{/* Header */}}
        <div className="flex items-center gap-3 px-4 py-4 border-b">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <{app_icon} className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-sm font-bold leading-tight">{title}</h2>
            <p className="text-xs text-muted-foreground">Workspace</p>
          </div>
        </div>

        {{/* Nav */}}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2 mt-1">Navigation</p>
{nav_items}
        </nav>

        {{/* User footer */}}
        <div className="border-t p-3">
          <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-accent cursor-pointer group">
            <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">User</p>
              <p className="text-xs text-muted-foreground truncate">user@example.com</p>
            </div>
            <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="p-6">
{pages}
        </div>
      </main>
    </div>
  )
}}
'''

    def _gen_router_layout(self, app: ast.AppDecl,
                            components: Dict[str, ast.ComponentDecl],
                            comp_imports: str) -> str:
        layout = app.layout
        title  = app.title
        routes = layout.routes

        route_elements = "\n".join(
            f'        <Route path="{r.path}" element={{<{r.component or "div"} />}} />'
            for r in routes
        )
        # Nav links for each route
        nav_links = "\n".join(
            f'          <NavLink to="{r.path}" '
            f'className={{({{isActive}}) => isActive ? "font-bold text-primary" : "text-muted-foreground"}}'
            f'>{r.component}</NavLink>'
            for r in routes
        )

        return f'''\
import React from "react"
import {{ BrowserRouter, Routes, Route, NavLink }} from "react-router-dom"
{comp_imports}
import "./globals.css"

export default function App() {{
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-background">
        <aside className="w-56 border-r p-4 flex flex-col gap-2">
          <h2 className="text-lg font-bold mb-4">{title}</h2>
{nav_links}
        </aside>
        <main className="flex-1 p-6">
          <Routes>
{route_elements}
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}}
'''

    # ── Boilerplate file generators ────────────────────────────────────────────

    def _gen_api_service(self, app: Optional[ast.AppDecl]) -> str:
        return '''\
/**
 * MCN API service — auto-generated.
 * All endpoint calls go through this module so components stay clean.
 */

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8080"

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method:  body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body:    body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  get:  <T>(path: string)              => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, body),
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
  </React.StrictMode>
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
    font-feature-settings: "rlig" 1, "calt" 1;
  }}
}}
'''

    def _gen_package_json(self, app: Optional[ast.AppDecl]) -> str:
        name = app.name.lower().replace(" ", "-") if app else "mcn-app"
        return json.dumps({
            "name":        name,
            "version":     "0.1.0",
            "private":     True,
            "type":        "module",
            "scripts": {
                "dev":     "vite",
                "build":   "tsc && vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "react":           "^18.3.1",
                "react-dom":       "^18.3.1",
                "class-variance-authority": "^0.7.1",
                "clsx":            "^2.1.1",
                "lucide-react":    "^0.446.0",
                "tailwind-merge":  "^2.5.2",
                "tailwindcss-animate": "^1.0.7",
                "@radix-ui/react-slot":         "^1.1.0",
                "@radix-ui/react-checkbox":     "^1.1.1",
                "@radix-ui/react-switch":       "^1.1.0",
                "@radix-ui/react-radio-group":  "^1.2.0",
                "@radix-ui/react-tooltip":      "^1.1.2",
                "@radix-ui/react-accordion":    "^1.2.0",
                "@radix-ui/react-dropdown-menu":"^2.1.1",
                "@radix-ui/react-dialog":       "^1.1.1",
                "@radix-ui/react-select":       "^2.1.1",
                "@radix-ui/react-tabs":         "^1.1.0",
                "@radix-ui/react-popover":      "^1.1.1",
                "@radix-ui/react-label":        "^2.1.0",
                "@radix-ui/react-separator":    "^1.1.0",
                "@radix-ui/react-scroll-area":  "^1.1.0",
                "@radix-ui/react-avatar":       "^1.1.0",
                "@radix-ui/react-progress":     "^1.1.0",
                "recharts":        "^2.12.0",
                "react-router-dom": "^6.26.0",
            },
            "devDependencies": {
                "@types/react":        "^18.3.0",
                "@types/react-dom":    "^18.3.0",
                "@vitejs/plugin-react": "^4.3.1",
                "autoprefixer":        "^10.4.20",
                "postcss":             "^8.4.47",
                "tailwindcss":         "^3.4.13",
                "typescript":          "^5.5.3",
                "vite":                "^5.4.8",
            },
        }, indent=2)

    def _gen_tailwind_config(self) -> str:
        return '''\
import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border:     "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT:    "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
'''

    def _gen_vite_config(self) -> str:
        return '''\
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
})
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
        return json.dumps({
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
        }, indent=2)

    def _gen_tsconfig(self) -> str:
        return json.dumps({
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
                "noUnusedLocals":    True,
                "noUnusedParameters": True,
                "noFallthroughCasesInSwitch": True,
                "baseUrl":           ".",
                "paths": {
                    "@/*": ["./src/*"],
                },
            },
            "include": ["src"],
            "references": [{"path": "./tsconfig.node.json"}],
        }, indent=2)

    def _gen_index_html(self, title: str) -> str:
        return f'''\
<!DOCTYPE html>
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
