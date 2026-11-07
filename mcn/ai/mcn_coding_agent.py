from __future__ import annotations

import os
import re
import anthropic
from pathlib import Path
from typing import Optional

from .mcn_agent import DEFAULT_MODEL, GENERATION_EFFORT, raise_if_refused

# ── System prompts ─────────────────────────────────────────────────────────────

MCN_UI_SYSTEM_PROMPT = """
You are an expert AI Coding Agent for the MCN (Macincode Scripting Language) platform.
Your job is to read and enhance MCN user interface scripts (ui/app.mcn) or compiled React TSX components (frontend/src/App.tsx)
to make them look beautiful, modern, responsive, and production-ready for both Web and Native Flutter Mobile apps.

MCN UI SYNTAX SPECIFICATION (ui/app.mcn):
1. Indentation: Exactly 4 spaces per nesting level. No curly braces, no tabs.
2. Structure:
   component <ComponentName>
       state <name> = <default_val>
       on load
           var resp = <endpoint_name>()
           <state_var> = resp.data
       on submit
           var result = <endpoint_name>(<args>)
           ...
       render
           div
               h2 "Section Title"
               div grid_cols=2 | 3 | 4
                   stat_card label="Total Deals" value=<var> icon="TrendingUp" color="blue"
               card
                   card_header "Title"
                   table data=<array_var>
                       table_header
                           table_row
                               table_head "col1"
                               table_head "col2"
                       table_body
3. Built-in UI Elements:
   - Layout: div, div grid_cols=N, card, card_header "Title", card_content, card_footer
   - Headings & Text: h1 "...", h2 "...", h3 "...", p "...", text <variable>
   - Stat Cards: stat_card label="Label" value=<var> icon="TrendingUp|Users|Building2|Calendar|CheckCircle|DollarSign" color="blue|green|purple|amber"
   - Charts: bar_chart data=<array_var> x_key="title" y_key="value" height=300, line_chart, pie_chart
   - Tables: table or table data=<array_var>, table_header, table_row, table_head "fieldName", table_body
   - Forms & Inputs: form on_submit=<handler>, input bind=<state> label="...", textarea bind=<state> label="...", select bind=<state> options=[...] label="...", button "Label" variant="default|outline|destructive"
   - Modals: modal show=<bool_state>
4. App Root Layout:
   app <AppName>
       title "<Title>"
       theme "professional" | "modern" | "minimal"
       layout
           sidebar
               nav "Dashboard"  DashboardComponent
               nav "Deals"      DealsTableComponent
           // or tabs
           tabs
               tab "Tab Name"   TabComponent

Design Standards:
- Modern Material 3 & Tailwind aesthetics: clear visual hierarchy, stat cards with Lucide icons, responsive grids (grid_cols=2, grid_cols=3, grid_cols=4).
- If enhancing MCN (ui/app.mcn), adhere strictly to valid MCN UI grammar without injecting raw HTML or JSX.
- If enhancing compiled React TSX (frontend/src/App.tsx), use modern React, Tailwind CSS, Lucide icons, and shadcn/ui components.

IMPORTANT: Return ONLY the raw enhanced code without explanations or markdown code fences.
"""

MCN_BACKEND_SYSTEM_PROMPT = """
You are an expert AI Backend Coding Agent for the MCN (Macincode Scripting Language) platform.

MCN Backend Syntax Specification (backend/main.mcn):
1. Indentation: Exactly 4 spaces per nesting level.
2. Contracts (DTO models):
   contract <ModelName>
       <field>: str | int | float | bool

3. Database Initialization (SQLite query on start):
   query("CREATE TABLE IF NOT EXISTS tablename (id INTEGER PRIMARY KEY AUTOINCREMENT, field1 TEXT, field2 REAL, created_at TEXT DEFAULT (datetime('now')))")

4. Services & Endpoints:
   service <service_name>
       port 8080

       endpoint list_items(limit = 50)
           var items = query("SELECT * FROM tablename ORDER BY created_at DESC LIMIT ?", (limit,))
           return {success: true, data: items}

       endpoint create_item(field1, field2)
           query("INSERT INTO tablename (field1, field2) VALUES (?, ?)", (field1, field2))
           var id = query("SELECT last_insert_rowid() as id")[0].id
           return {success: true, id: id}

       endpoint delete_item(id)
           query("DELETE FROM tablename WHERE id = ?", (id,))
           return {success: true}

5. Built-in Primitives:
   - AI generation: var insight = ai("Prompt text {variable}")
   - Classification: var label = classify(text, ["cat1", "cat2"])
   - Analytics (with `use analytics`): kpi_summary("table", metrics=["sum:amount", "count:*"]), trend(...), distribution(...)

IMPORTANT: Return ONLY the raw valid MCN backend code without explanations or markdown fences.
"""


class MCNCodingAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model  = model

    # ── UI Agents ──────────────────────────────────────────────────────────────

    def enhance_mcn_code(self, mcn_code: str, prompt: str) -> str:
        """Enhance pre-compilation MCN UI layout code."""
        full_prompt = (
            f"Please enhance the following MCN UI layout script according to this request: '{prompt}'.\n"
            f"Add elegant class names, responsive layouts, text gradients, hover scales, and clean padding/margins.\n\n"
            f"ORIGINAL MCN CODE:\n{mcn_code}\n\n"
            f"Return ONLY the updated MCN code without any explanations."
        )
        return self._call_llm(full_prompt, system=MCN_UI_SYSTEM_PROMPT)

    def enhance_compiled_code(self, file_content: str, file_path: str, prompt: str) -> str:
        """Enhance post-compilation React/TSX or Flutter code."""
        file_ext = Path(file_path).suffix
        lang = "TypeScript React (TSX)" if file_ext in (".tsx", ".ts") else "Flutter (Dart)"
        full_prompt = (
            f"Please enhance the following compiled {lang} component file according to this request: '{prompt}'.\n"
            f"Add responsive grids, Tailwind styling (glass-card, gradients, transitions), custom badges, or interactive widgets.\n\n"
            f"ORIGINAL COMPILED CODE:\n{file_content}\n\n"
            f"Return ONLY the updated {lang} code without any explanations."
        )
        return self._call_llm(full_prompt, system=MCN_UI_SYSTEM_PROMPT)

    # ── Backend Agent ──────────────────────────────────────────────────────────

    def enhance_backend_code(self, mcn_code: str, prompt: str) -> str:
        """
        Enhance or extend an MCN backend file.

        The agent can:
          - Add new endpoints (GET, POST, PUT, DELETE) to existing services
          - Add new database tables and query blocks
          - Add authentication & role-based access control primitives
          - Add cron-scheduled background jobs
          - Add event listeners and multi-step workflows
          - Refactor logic for cleaner error handling and validation
        """
        full_prompt = (
            f"Please enhance or extend the following MCN backend script according to this request: '{prompt}'.\n"
            f"Keep all existing functionality intact. Add the requested features using proper MCN syntax.\n\n"
            f"CURRENT MCN BACKEND CODE:\n{mcn_code}\n\n"
            f"Return ONLY the complete updated MCN backend code without any explanations."
        )
        return self._call_llm(full_prompt, system=MCN_BACKEND_SYSTEM_PROMPT)

    def generate_backend_code(self, prompt: str) -> str:
        """
        Generate a brand-new MCN backend file from scratch.
        Use this when there is no existing backend code to enhance.
        """
        full_prompt = (
            f"Generate a complete, production-ready MCN backend script for the following: '{prompt}'.\n"
            f"Include a service block with relevant endpoints, a database block with appropriate tables,\n"
            f"auth primitives if needed, contracts for request/response shapes, and cron jobs if applicable.\n\n"
            f"Return ONLY the MCN backend code without any explanations."
        )
        return self._call_llm(full_prompt, system=MCN_BACKEND_SYSTEM_PROMPT)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call_llm(self, prompt: str, system: str = MCN_UI_SYSTEM_PROMPT) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,  # thinking tokens count toward this cap
            output_config={"effort": GENERATION_EFFORT},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        raise_if_refused(response)
        # Opus 5.5 always thinks, so skip thinking blocks and keep only text
        content = "".join(block.text for block in response.content if block.type == "text")
        # Strip markdown fences if the model returned them
        if "```" in content:
            m = re.search(r"```[a-zA-Z]*\n(.*?)\n```", content, re.DOTALL)
            if m:
                content = m.group(1)
        return content.strip()
