"""Example scripts, project templates and the component catalog.

Templates live as plain files under ./templates/<id>/ so they can be read and
edited like any MCN project; templates/index.json holds their order and metadata.
"""
import json
from functools import lru_cache
from pathlib import Path

from flask import Blueprint
from .core import jsonify

bp = Blueprint("examples", __name__)

TEMPLATES_DIR = Path(__file__).with_name("templates")


def load_template(template_id: str) -> dict:
    """One template as served to the IDE: metadata plus `code` or `files`."""
    for meta in _index():
        if meta["id"] == template_id:
            return _with_sources(meta)
    raise KeyError(template_id)


@lru_cache(maxsize=1)
def _index() -> tuple:
    return tuple(json.loads((TEMPLATES_DIR / "index.json").read_text(encoding="utf-8")))


def _with_sources(meta: dict) -> dict:
    base = TEMPLATES_DIR / meta["id"]
    template = {k: v for k, v in meta.items() if k != "files"}
    if "files" in meta:
        template["files"] = [
            {"path": rel, "content": (base / rel).read_text(encoding="utf-8")} for rel in meta["files"]
        ]
    else:
        template["code"] = (base / meta["file"]).read_text(encoding="utf-8")
    return template


@bp.route("/api/examples")
def get_examples():
    return jsonify([_with_sources(meta) for meta in _index()])


@bp.route("/api/components")
def get_components():
    return jsonify([
        {
            "name": "Button",
            "category": "primitives",
            "description": "Primary action button with multiple variants and loading states.",
            "mcnSnippet": 'ui("button", {label: "Submit", variant: "primary", action: "submit"})',
            "reactSnippet": '<Button variant="primary" size="md">Submit</Button>',
            "flutterSnippet": 'MCNButton(label: "Submit", variant: MCNButtonVariant.primary, onPressed: () {})',
        },
        {
            "name": "Input",
            "category": "primitives",
            "description": "Text input with optional label, hint, error, and prefix/suffix slots.",
            "mcnSnippet": 'ui("input", {name: "email", label: "Email", placeholder: "user@example.com"})',
            "reactSnippet": '<Input label="Email" placeholder="user@example.com" />',
            "flutterSnippet": 'MCNInput(label: "Email", hint: "user@example.com")',
        },
        {
            "name": "Badge",
            "category": "primitives",
            "description": "Status badge chip with optional dot indicator.",
            "mcnSnippet": 'ui("badge", {label: "Active", variant: "success", dot: true})',
            "reactSnippet": '<Badge variant="success" dot>Active</Badge>',
            "flutterSnippet": 'MCNBadge(label: "Active", variant: MCNBadgeVariant.success, dot: true)',
        },
        {
            "name": "Card",
            "category": "layout",
            "description": "Container card with title, description, and footer.",
            "mcnSnippet": 'ui("card", {title: "Overview", description: "Daily metrics"})',
            "reactSnippet": '<Card title="Overview" description="Daily metrics"><p>Content</p></Card>',
            "flutterSnippet": 'MCNCard(title: "Overview", description: "Daily metrics", child: Text("Content"))',
        },
        {
            "name": "Stat",
            "category": "data",
            "description": "Metric stat block with value, change percentage, and trend indicators.",
            "mcnSnippet": 'ui("stat", {label: "Active Users", value: "1,240", change: 12.5})',
            "reactSnippet": '<Stat label="Active Users" value="1,240" change={12.5} />',
            "flutterSnippet": 'MCNStat(label: "Active Users", value: "1,240", change: 12.5)',
        },
        {
            "name": "AIPrompt",
            "category": "ai",
            "description": "Multi-line AI assistant input with streaming and model controls.",
            "mcnSnippet": 'ui("ai_prompt", {placeholder: "Ask AI to generate..."})',
            "reactSnippet": '<AIPrompt placeholder="Ask AI..." onSubmit={(p) => generate(p)} />',
            "flutterSnippet": 'MCNAIPrompt(placeholder: "Ask AI...", onSubmit: (p) => generate(p))',
        },
        {
            "name": "StreamingText",
            "category": "ai",
            "description": "Animated typewriter text display for live AI response tokens.",
            "mcnSnippet": 'ui("streaming_text", {text: ai_output, streaming: is_loading})',
            "reactSnippet": '<StreamingText text={output} isStreaming={isStreaming} />',
            "flutterSnippet": 'MCNStreamingText(text: output, isStreaming: isStreaming)',
        },
        {
            "name": "OutputLog",
            "category": "ai",
            "description": "Catppuccin Mocha terminal log console with colored levels.",
            "mcnSnippet": 'ui("output_log", {lines: logs})',
            "reactSnippet": '<OutputLog lines={logs} autoScroll />',
            "flutterSnippet": 'MCNOutputLog(entries: logs)',
        }
    ])
