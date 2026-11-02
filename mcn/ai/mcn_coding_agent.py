from __future__ import annotations

import os
import re
import anthropic
from pathlib import Path
from typing import Optional

# ── System prompts ─────────────────────────────────────────────────────────────

MCN_UI_SYSTEM_PROMPT = """
You are an expert AI Coding Agent for the MCN (Macincode Scripting Language) platform.
Your job is to read and enhance MCN user interface scripts or compiled React TSX components to make them look beautiful, elegant, modern, responsive, and interactive.
You must focus on design standards equivalent to modern platforms like Lovable, v0, and shadcn/ui.

Key Design Elements to Inject:
1. Glassmorphism: Add properties like className="glass-card hover-scale hover:shadow-lg transition-all duration-300"
2. Grid Layouts: Add class names like className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" to create responsive layouts.
3. Micro-Animations: Hover transitions, scale-ups, text gradients, neon glow outlines.
4. Professional Colors: Deep slates, clean whites, vibrant purples/indigos, or matching luxury dark modes.

IMPORTANT: Return ONLY the raw code block containing the fully enhanced file contents. Do not add explanations, do not wrap in markdown code fences.
"""

MCN_BACKEND_SYSTEM_PROMPT = """
You are an expert AI Backend Coding Agent for the MCN (Macincode Scripting Language) platform.

MCN is a domain-specific scripting language. Here are the backend primitives you MUST use:

  service <Name> {
    port: <number>
    endpoint <method> "<path>" { ... }      # HTTP endpoints
    schedule "<cron>" { ... }               # Cron jobs
    on_event "<name>" { ... }               # Event listeners
    workflow <Name> { step <label> { ... } } # Multi-step workflows
  }

  database <Name> {
    table <TableName> { <field>: <type>, ... }
    query <name>(<params>) { sql "..." }
  }

  auth { provider: "<value>" }              # Auth primitive
  contract <Name> { field: <type> }        # Data contracts / DTOs
  log(<message>)
  http.<method>("<url>", body=...) → returns dict
  db.<TableName>.insert(...)
  db.<TableName>.find(where={...})
  db.<TableName>.update(where={...}, set={...})
  db.<TableName>.delete(where={...})

Best Practices:
- Add proper error handling using if/else blocks around data operations.
- Add input validation before inserting or querying data.
- Group related endpoints logically inside a single service block.
- Add informative log() statements to track important events.
- Use contracts to define request/response shapes for consistency.
- For auth endpoints, always include token verification using auth.verify_token().

IMPORTANT: Return ONLY the raw MCN backend code. Do not add explanations, do not wrap in markdown code fences.
"""


class MCNCodingAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-6"):
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
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        content = "".join(block.text for block in response.content)
        # Strip markdown fences if the model returned them
        if "```" in content:
            m = re.search(r"```[a-zA-Z]*\n(.*?)\n```", content, re.DOTALL)
            if m:
                content = m.group(1)
        return content.strip()
