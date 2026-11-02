"""
MCN Agent — Claude-powered code generator.
Converts a natural-language description into a complete MCN application.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import anthropic

from .mcn_spec import MCN_SYSTEM_PROMPT, MCN_FIX_PROMPT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_RE = re.compile(r"<backend>(.*?)</backend>", re.DOTALL)
_UI_RE       = re.compile(r"<ui>(.*?)</ui>",          re.DOTALL)


def _extract_blocks(text: str) -> tuple[str, str]:
    """Return (backend_mcn, ui_mcn) from a Claude response, or ('', '') on failure."""
    backend_m = _BACKEND_RE.search(text)
    ui_m      = _UI_RE.search(text)
    backend   = backend_m.group(1).strip() if backend_m else ""
    ui        = ui_m.group(1).strip()      if ui_m      else ""
    return backend, ui


def _validate_mcn(code: str, label: str) -> Optional[str]:
    """
    Try to lex + parse `code`.  Returns an error string on failure, None on success.
    Imports done lazily to avoid circular-import issues at module load time.
    """
    try:
        from mcn.core_engine.lexer  import Lexer
        from mcn.core_engine.parser import Parser

        tokens = Lexer(code).tokenize()
        Parser(tokens).parse()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"[{label}] {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class MCNAgent:
    """
    Generates a full MCN application from a natural-language description.

    Usage
    -----
    agent = MCNAgent()                          # reads ANTHROPIC_API_KEY from env
    result = agent.generate("A todo-list app", output_dir="./todo_app")
    print(result["backend_path"], result["ui_path"])
    """

    MAX_RETRIES = 3

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model  = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        description: str,
        attachments: Optional[list[dict]] = None,
        output_dir: str = ".",
        port: int = 8080,
        verbose: bool = True,
    ) -> dict:
        """
        Generate + validate + write MCN files for `description` and optional `attachments`.

        Parameters
        ----------
        description : natural-language app description
        attachments : list of dicts with keys {name, type, data, size}
        output_dir  : root folder where backend/ and ui/ will be written
        port        : backend server port (injected into the prompt)
        verbose     : print streaming progress to stdout

        Returns
        -------
        dict with keys:
            backend_path, ui_path       — Path objects of written files
            backend_mcn, ui_mcn         — raw MCN source strings
            attempts                    — number of generation attempts used
            build_cmd                   — suggested mcn build command string
        """
        prompt = self._build_prompt(description, port, attachments=attachments)

        backend_mcn = ""
        ui_mcn      = ""
        last_error  = ""
        attempts    = 0

        # ── Generation + self-correction loop ──────────────────────────
        for attempt in range(1, self.MAX_RETRIES + 1):
            attempts = attempt

            if attempt == 1:
                att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
                if verbose:
                    print(f"\n[MCN Agent] Generating MCN for: {description!r}{att_info}\n")
                raw = self._call_claude(prompt, system=MCN_SYSTEM_PROMPT, verbose=verbose)
            else:
                if verbose:
                    print(f"\n[MCN Agent] Self-correcting (attempt {attempt}) …\n")
                raw = self._fix_mcn(
                    backend_mcn=backend_mcn,
                    ui_mcn=ui_mcn,
                    error=last_error,
                    verbose=verbose,
                )

            backend_mcn, ui_mcn = _extract_blocks(raw)

            if not backend_mcn or not ui_mcn:
                last_error = "Could not extract <backend> and/or <ui> blocks from response."
                if verbose:
                    print(f"  ✗ {last_error}")
                continue

            # Validate both files
            be_err = _validate_mcn(backend_mcn, "backend")
            ui_err = _validate_mcn(ui_mcn,      "ui")

            if be_err or ui_err:
                last_error = "\n".join(filter(None, [be_err, ui_err]))
                if verbose:
                    print(f"  ✗ Parse error:\n{last_error}")
                continue

            # All good
            if verbose:
                print(f"  ✓ MCN validated on attempt {attempt}")
            break
        else:
            # Exhausted retries — write whatever we have and warn
            if verbose:
                print(f"\n[MCN Agent] Warning: max retries reached. Writing last output anyway.")

        # ── Write files ────────────────────────────────────────────────
        out = Path(output_dir)
        backend_path = self._write(out / "backend" / "main.mcn", backend_mcn)
        ui_path      = self._write(out / "ui"      / "app.mcn",  ui_mcn)

        if verbose:
            print(f"\n[MCN Agent] Written:")
            print(f"  backend → {backend_path}")
            print(f"  ui      → {ui_path}")

        build_cmd = f"mcn build {ui_path} --out {out / 'frontend'}"
        if verbose:
            print(f"\n[MCN Agent] Next step:\n  {build_cmd}\n")

        return {
            "backend_path": backend_path,
            "ui_path":      ui_path,
            "backend_mcn":  backend_mcn,
            "ui_mcn":       ui_mcn,
            "attempts":     attempts,
            "build_cmd":    build_cmd,
        }

    def generate_and_build(
        self,
        description: str,
        attachments: Optional[list[dict]] = None,
        output_dir: str = ".",
        port: int = 8080,
        verbose: bool = True,
    ) -> dict:
        """
        Like `generate`, but also runs `mcn build` after writing files.
        Returns the same dict with an extra `build_result` key.
        """
        result = self.generate(
            description,
            attachments=attachments,
            output_dir=output_dir,
            port=port,
            verbose=verbose,
        )

        ui_path  = result["ui_path"]
        out_dir  = Path(output_dir) / "frontend"

        if verbose:
            print(f"[MCN Agent] Running: mcn build {ui_path} --out {out_dir}")

        proc = subprocess.run(
            [sys.executable, "-m", "mcn", "build", str(ui_path), "--out", str(out_dir)],
            capture_output=not verbose,
            text=True,
        )
        result["build_result"] = {
            "returncode": proc.returncode,
            "stdout":     proc.stdout if not verbose else "",
            "stderr":     proc.stderr if not verbose else "",
        }
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        description: str,
        port: int,
        attachments: Optional[list[dict]] = None,
    ) -> str | list[dict]:
        if not attachments:
            return (
                f"Build a complete MCN application for the following:\n\n"
                f"{description}\n\n"
                f"Use port {port} for the backend service.\n"
                f"Remember to output BOTH <backend> and <ui> blocks."
            )

        content_blocks: list[dict] = []
        file_summaries: list[str] = []

        for att in attachments:
            name = att.get("name", "attachment")
            mime = (att.get("type") or "").lower()
            raw_data = att.get("data", "")
            if "," in raw_data and raw_data.startswith("data:"):
                raw_data = raw_data.split(",", 1)[1]

            if mime == "application/pdf" or name.lower().endswith(".pdf"):
                file_summaries.append(f"- [PDF / Requirements / BRD] {name}")
                content_blocks.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": raw_data,
                    },
                })
            elif mime in ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif") or any(
                name.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")
            ):
                img_media = (
                    "image/png" if name.lower().endswith(".png")
                    else "image/jpeg" if name.lower().endswith((".jpg", ".jpeg"))
                    else "image/webp" if name.lower().endswith(".webp")
                    else "image/gif" if name.lower().endswith(".gif")
                    else (mime or "image/png")
                )
                file_summaries.append(f"- [Image / Figma / Flowchart UI] {name}")
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_media,
                        "data": raw_data,
                    },
                })
            else:
                # Text, Markdown, JSON, SVG, CSV, etc.
                file_summaries.append(f"- [Specification File] {name}")
                try:
                    import base64
                    decoded_text = base64.b64decode(raw_data).decode("utf-8", errors="replace")
                except Exception:
                    decoded_text = str(raw_data)
                content_blocks.append({
                    "type": "text",
                    "text": f"--- Attached Document: {name} ---\n{decoded_text}\n--- End Attached Document ---",
                })

        instruction_text = (
            f"Build a complete, production-ready MCN application based on the user's requirements "
            f"and the {len(attachments)} attached specification documents / flowchart diagrams / Figma UI mockups.\n\n"
            f"USER SPECIFICATION / APP GOAL:\n"
            f"{description}\n\n"
            f"ATTACHED ARTIFACTS:\n"
            + "\n".join(file_summaries)
            + f"\n\n"
            f"REQUIREMENTS ANALYSIS & DECOMPOSITION WORKFLOW:\n"
            f"1. BRD / PRD Analysis: Extract all core entity models, fields, types, business rules, and CRUD workflows from the documents.\n"
            f"2. Flowcharts & State Logic: Replicate all decision paths, status progressions, and lifecycle transitions in the backend endpoints and frontend state.\n"
            f"3. Figma UI & Layouts: Match the visual cards, navigation tabs, metrics/KPI cards, tables, and form inputs faithfully in the MCN UI code.\n"
            f"4. Database & Backend: Define table schemas with query() and backend service endpoints on port {port}.\n"
            f"5. Output Format: Output BOTH <backend> and <ui> blocks containing complete MCN code with no placeholders or stubs."
        )

        content_blocks.append({"type": "text", "text": instruction_text})
        return content_blocks

    def _call_claude(self, prompt: str | list[dict], system: str, verbose: bool) -> str:
        """Stream a Claude response and return the full text."""
        chunks: list[str] = []

        with self.client.messages.stream(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                chunks.append(text)
                if verbose:
                    print(text, end="", flush=True)

        if verbose:
            print()  # newline after stream ends

        return "".join(chunks)

    def _fix_mcn(
        self,
        backend_mcn: str,
        ui_mcn: str,
        error: str,
        verbose: bool,
    ) -> str:
        """Ask Claude to fix broken MCN, returning corrected backend + ui in XML tags."""
        fix_prompt = (
            f"The following MCN code has errors. Fix them and return BOTH corrected files "
            f"wrapped in <backend>...</backend> and <ui>...</ui> XML tags.\n\n"
            f"ERROR:\n{error}\n\n"
            f"BACKEND (backend/main.mcn):\n{backend_mcn}\n\n"
            f"UI (ui/app.mcn):\n{ui_mcn}"
        )

        # Use full spec as system so the fix knows all the rules
        return self._call_claude(fix_prompt, system=MCN_SYSTEM_PROMPT + "\n\n" + MCN_FIX_PROMPT, verbose=verbose)

    @staticmethod
    def _write(path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
