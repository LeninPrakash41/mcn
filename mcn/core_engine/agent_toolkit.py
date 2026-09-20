"""
MCN Agent Toolkit — Dedicated LLM & Autonomous Coding Agent Infrastructure

Provides programmatic syntax, lexer, AST, and type validation designed
specifically for AI coding agents (Google Antigravity, Claude, GPT-4o, Cursor).

Key capabilities:
  1. verify_agent_code(code) -> Multi-stage verification with line/col diagnostics and suggested fixes.
  2. generate_repair_prompt(code, result) -> 1-shot self-healing prompt for LLMs.
  3. get_agent_scaffold(template) -> Verified reference boilerplate.
  4. explain_syntax(query) -> Precise grammar rules & signatures for LLM context injection.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .lexer import Lexer, LexError, TT
from .parser import Parser, ParseError
from .type_checker import TypeChecker, Severity
from . import ast_nodes as ast


# ── Canonical Scaffolds Repository ────────────────────────────────────────────

SCAFFOLDS: Dict[str, str] = {
    "sales_calendar": """// Sales Intelligence & Calendar Hub
use "db"
use "ui"

query("CREATE TABLE IF NOT EXISTS sales_events (id INTEGER PRIMARY KEY, company TEXT, prospect_name TEXT, deal_size INTEGER, stage TEXT, scheduled_time TEXT, notes TEXT)")

var existing = query("SELECT COUNT(*) as count FROM sales_events")
if existing[0].count == 0:
    query("INSERT INTO sales_events (company, prospect_name, deal_size, stage, scheduled_time, notes) VALUES (?, ?, ?, ?, ?, ?)", ("Acme Health", "Sarah Jenkins", 75000, "Discovery", "10:30 AM", "Legacy migration evaluation."))
    query("INSERT INTO sales_events (company, prospect_name, deal_size, stage, scheduled_time, notes) VALUES (?, ?, ?, ?, ?, ?)", ("Vertex AI", "David Lin", 140000, "Proposal", "02:00 PM", "Security review & SOC2."))

function get_metrics()
    var events = query("SELECT deal_size, stage FROM sales_events")
    var total = 0
    for ev in events:
        total += ev.deal_size
    return {"pipeline": total, "count": events.length}

var m = get_metrics()
var events_list = query("SELECT id, company, prospect_name, deal_size, stage, scheduled_time FROM sales_events")

var header = ui("container", [
    ui("stat", {"label": "Active Pipeline", "value": "$" + m.pipeline}),
    ui("stat", {"label": "Calls Scheduled", "value": m.count})
])

var queue = ui("card", {"title": "Today's Schedule"}, [
    ui("table", {"data": events_list, "columns": ["scheduled_time", "company", "prospect_name", "deal_size", "stage"], "actions": ["AI Briefing"]}),
    ui("ai_prompt", {"placeholder": "Ask AI Copilot: Generate briefing for Vertex AI call..."})
])

var app = ui("page", "SalesHub", "/", [header, queue])
""",

    "crm": """// Single-File CRM & Lead Intelligence Hub
use "db"
use "ui"

query("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, name TEXT, company TEXT, deal_size INTEGER, status TEXT, score INTEGER)")

function triage_lead(notes: str): dict
    var score_str = ai("Rate lead quality 1-100 given notes: " + notes)
    var score = 85
    return {"score": score, "status": "Qualified"}

var leads_data = query("SELECT * FROM leads ORDER BY id DESC")

var stats = ui("container", [
    ui("stat", {"label": "Active Leads", "value": leads_data.length}),
    ui("stat", {"label": "Conversion Rate", "value": "24.8%", "change": 4.2})
])

var table_card = ui("card", {"title": "Lead Management"}, [
    ui("table", {"data": leads_data, "columns": ["name", "company", "deal_size", "status", "score"]}),
    ui("button", {"label": "+ Add New Lead", "variant": "primary", "action": "open_lead_modal"})
])

var crm_page = ui("page", "CRM", "/", [stats, table_card])
""",

    "ai_triage": """// AI Support Dispatch & Urgency Classifier
use "auth"
use "ui"

function triage_ticket(ticket_body: str): str
    var tier = classify(ticket_body, ["low", "medium", "critical"])
    if tier == "critical":
        log("DISPATCH ALERT: PagerDuty triggered for ticket: " + ticket_body)
    return tier

var header = ui("stat", {"label": "Auto-Triage Accuracy", "value": "99.1%"})
var prompt_panel = ui("card", {"title": "AI Support Dispatcher"}, [
    ui("ai_prompt", {"placeholder": "Paste customer ticket message to triage..."})
])

var triage_app = ui("page", "SupportTriage", "/", [header, prompt_panel])
""",

    "rest_service": """// High-Performance Microservice
service LeadScoringAPI
    port 8080

    endpoint "GET /health"()
        return {"status": "ok", "timestamp": now()}

    endpoint "POST /score"(req)
        var lead = req.body
        var score = ai("Score deal probability 1-100 for: " + to_json(lead))
        return {"lead_id": lead.id, "score": score, "tier": "A"}
"""
}

# ── Syntax Explanations Repository ────────────────────────────────────────────

SYNTAX_RULES: Dict[str, Dict[str, Any]] = {
    "var": {
        "syntax": "var name [: type] = value",
        "description": "Declares a variable. Type annotation is optional.",
        "examples": ["var count = 10", "var user_name: str = 'Alice'", "var rates: list = [0.1, 0.2]"]
    },
    "function": {
        "syntax": "function name(param: type = default): return_type\n    body",
        "description": "Defines a named function with optional type hints and default values.",
        "examples": ["function add(a: int, b: int = 0): int\n    return a + b"]
    },
    "db": {
        "syntax": "use 'db'\nquery('SQL', (params,))",
        "description": "Native SQLite persistence. Always use parameterized queries with tuple args.",
        "examples": ["query('SELECT * FROM users WHERE age >= ?', (21,))", "query('INSERT INTO items (name) VALUES (?)', ('Widget',))"]
    },
    "ai": {
        "syntax": "ai('prompt string with {interpolation}')",
        "description": "Direct LLM inference expression returning a string response.",
        "examples": ["var summary = ai('Summarize customer feedback: ' + feedback)", "var score = ai('Rate urgency 1-10 for: {ticket.body}')"]
    },
    "ui": {
        "syntax": "ui('type', props, [children])",
        "description": "Declarative UI component directive. Types: page, container, card, stat, table, ai_prompt, button.",
        "examples": ["ui('stat', {'label': 'Revenue', 'value': '$100k'})", "ui('card', {'title': 'Queue'}, [table, button])"]
    },
    "service": {
        "syntax": "service ServiceName\n    port 8080\n    endpoint 'METHOD /path'(req)\n        return data",
        "description": "Declares an instant HTTP REST service with auto-routed endpoints.",
        "examples": ["service API\n    port 3000\n    endpoint 'GET /users'()\n        return query('SELECT * FROM users')"]
    }
}


# ── Code Verifier ─────────────────────────────────────────────────────────────

def verify_agent_code(code: str) -> Dict[str, Any]:
    """
    Comprehensive multi-stage verification for AI coding agents.
    
    Returns structured JSON with:
      - valid: bool
      - syntax_valid: bool
      - type_valid: bool
      - issues: list of {stage, severity, line, col, message, code_context, fix_suggestion}
      - ast_summary: summary of variables, functions, and packages used
    """
    if not code or not code.strip():
        return {
            "valid": False,
            "syntax_valid": False,
            "type_valid": False,
            "issues_count": 1,
            "issues": [{
                "stage": "lexer",
                "severity": "error",
                "line": 1,
                "col": 1,
                "message": "Source code is empty.",
                "code_context": "",
                "fix_suggestion": "Provide non-empty MCN source code."
            }],
            "ast_summary": {}
        }

    lines = code.splitlines()
    issues: List[Dict[str, Any]] = []
    tokens = []
    program = None

    def get_context(line_num: int) -> str:
        if 1 <= line_num <= len(lines):
            return lines[line_num - 1]
        return ""

    # ── STAGE 1: Lexer Verification ───────────────────────────────────────────
    try:
        tokens = Lexer(code).tokenize()
    except LexError as le:
        issues.append({
            "stage": "lexer",
            "severity": "error",
            "line": getattr(le, "line", 1),
            "col": getattr(le, "col", 1),
            "message": str(le),
            "code_context": get_context(getattr(le, "line", 1)),
            "fix_suggestion": _suggest_lexer_fix(str(le), get_context(getattr(le, "line", 1)))
        })
        return {
            "valid": False,
            "syntax_valid": False,
            "type_valid": False,
            "issues_count": len(issues),
            "issues": issues,
            "ast_summary": {}
        }
    except Exception as exc:
        issues.append({
            "stage": "lexer",
            "severity": "error",
            "line": 1,
            "col": 1,
            "message": f"Lexer error: {exc}",
            "code_context": get_context(1),
            "fix_suggestion": "Check token formatting and unclosed string quotes."
        })
        return {
            "valid": False,
            "syntax_valid": False,
            "type_valid": False,
            "issues_count": len(issues),
            "issues": issues,
            "ast_summary": {}
        }

    # ── STAGE 2: Parser Verification ──────────────────────────────────────────
    parser = Parser(tokens)
    try:
        program = parser.parse()
        if parser.errors:
            for err in parser.errors:
                m = re.search(r"\[(\d+):(\d+)\]", err)
                if m:
                    line_no, col_no = int(m.group(1)), int(m.group(2))
                else:
                    line_no, col_no = 1, 1
                issues.append({
                    "stage": "parser",
                    "severity": "error",
                    "line": line_no,
                    "col": col_no,
                    "message": err,
                    "code_context": get_context(line_no),
                    "fix_suggestion": _suggest_parser_fix(err, get_context(line_no))
                })
            return {
                "valid": False,
                "syntax_valid": False,
                "type_valid": False,
                "issues_count": len(issues),
                "issues": issues,
                "ast_summary": {}
            }
    except ParseError as pe:
        line_no = getattr(pe, "line", 1)
        col_no = getattr(pe, "col", 1)
        issues.append({
            "stage": "parser",
            "severity": "error",
            "line": line_no,
            "col": col_no,
            "message": str(pe),
            "code_context": get_context(line_no),
            "fix_suggestion": _suggest_parser_fix(str(pe), get_context(line_no))
        })
        return {
            "valid": False,
            "syntax_valid": False,
            "type_valid": False,
            "issues_count": len(issues),
            "issues": issues,
            "ast_summary": {}
        }
    except Exception as exc:
        issues.append({
            "stage": "parser",
            "severity": "error",
            "line": 1,
            "col": 1,
            "message": f"Parser failure: {exc}",
            "code_context": get_context(1),
            "fix_suggestion": "Check syntax structure and block indentations."
        })
        return {
            "valid": False,
            "syntax_valid": False,
            "type_valid": False,
            "issues_count": len(issues),
            "issues": issues,
            "ast_summary": {}
        }

    syntax_valid = len(issues) == 0

    # ── STAGE 3: Static Type Checker ──────────────────────────────────────────
    type_checker = TypeChecker()
    type_issues = type_checker.check(program)
    for ti in type_issues:
        sev = "error" if ti.severity == Severity.ERROR else "warning"
        issues.append({
            "stage": "type_checker",
            "severity": sev,
            "line": ti.line,
            "col": ti.col,
            "message": ti.message,
            "code_context": get_context(ti.line),
            "fix_suggestion": _suggest_type_fix(ti.message, get_context(ti.line))
        })

    # ── STAGE 4: Agent Linter & Best Practice Heuristics ──────────────────────
    lint_issues, ast_summary = _lint_ast(program, code)
    issues.extend(lint_issues)

    error_count = sum(1 for i in issues if i["severity"] == "error")
    is_valid = error_count == 0

    return {
        "valid": is_valid,
        "syntax_valid": syntax_valid,
        "type_valid": error_count == 0,
        "issues_count": len(issues),
        "issues": issues,
        "ast_summary": ast_summary
    }


# ── Fix Suggestions Logic ─────────────────────────────────────────────────────

def _suggest_lexer_fix(message: str, line_str: str) -> str:
    if "Inconsistent dedent" in message:
        return "Align indentation with previous block using standard 4 spaces."
    if "Unterminated string" in message:
        return 'Close the unclosed quotation mark (" or \').'
    return "Check for unrecognized characters or unclosed brackets."

def _suggest_parser_fix(message: str, line_str: str) -> str:
    if "Expected ':'" in message:
        return "Add ':' after expression or type hint."
    if "Expected '='" in message:
        return "Ensure variable assignment uses '='."
    if "Expected ')'" in message:
        return "Add closing ')' to match opening parenthesis."
    if "Expected ']'" in message:
        return "Add closing ']' to match opening square bracket."
    if "Expected '}'" in message:
        return "Add closing '}' to match opening brace."
    return "Review MCN syntax grammar rules for statement."

def _suggest_type_fix(message: str, line_str: str) -> str:
    if "Cannot assign" in message:
        return "Cast expression or adjust declared variable type."
    if "incompatible with declared return type" in message:
        return "Ensure returned value matches the function's declared return type."
    if "is not callable" in message:
        return "Verify that the variable being called is a valid function or built-in."
    return "Ensure operand types are compatible with operation."

def _lint_ast(program: ast.Program, code: str) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    vars_declared = set()
    funcs_declared = set()
    packages_used = set()
    ui_called = False
    db_called = False
    ai_called = False

    for stmt in program.body:
        if isinstance(stmt, ast.VarDecl):
            vars_declared.add(stmt.name)
        elif isinstance(stmt, ast.FunctionDecl):
            funcs_declared.add(stmt.name)
        elif isinstance(stmt, ast.UseStmt):
            if isinstance(stmt.package, ast.Literal):
                packages_used.add(str(stmt.package.value))

    # Check for missing package imports
    if "query(" in code and "db" not in packages_used:
        issues.append({
            "stage": "linter",
            "severity": "warning",
            "line": 1,
            "col": 1,
            "message": "Function 'query()' used but 'use \"db\"' was not declared.",
            "code_context": "query(...)",
            "fix_suggestion": 'Add \'use "db"\' at the top of your script.'
        })

    if "ui(" in code and "ui" not in packages_used:
        issues.append({
            "stage": "linter",
            "severity": "warning",
            "line": 1,
            "col": 1,
            "message": "Function 'ui()' used but 'use \"ui\"' was not declared.",
            "code_context": "ui(...)",
            "fix_suggestion": 'Add \'use "ui"\' at the top of your script.'
        })

    ast_summary = {
        "variables": sorted(list(vars_declared)),
        "functions": sorted(list(funcs_declared)),
        "packages": sorted(list(packages_used)),
        "has_ui": "ui" in packages_used or "ui(" in code,
        "has_db": "db" in packages_used or "query(" in code,
        "has_ai": "ai(" in code or "classify(" in code or "rag(" in code
    }

    return issues, ast_summary


# ── Repair Prompt Generator ───────────────────────────────────────────────────

def generate_repair_prompt(code: str, verification_result: Optional[Dict[str, Any]] = None) -> str:
    """
    Constructs an optimal, high-signal prompt for LLMs to repair broken MCN code in 1 pass.
    """
    if verification_result is None:
        verification_result = verify_agent_code(code)

    if verification_result.get("valid", False):
        return "The provided MCN code is 100% valid. No repairs needed."

    issue_lines = []
    for idx, iss in enumerate(verification_result.get("issues", []), 1):
        line = iss.get("line", 1)
        col = iss.get("col", 1)
        msg = iss.get("message", "Error")
        ctx = iss.get("code_context", "").strip()
        fix = iss.get("fix_suggestion", "")
        issue_lines.append(
            f"Issue #{idx} [Line {line}:{col}]: {msg}\n"
            f"  Faulty Code: {ctx}\n"
            f"  Suggested Fix: {fix}"
        )

    formatted_issues = "\n\n".join(issue_lines)

    prompt = (
        "Please fix the following syntax / type issues in the MCN script:\n\n"
        f"--- DIAGNOSTIC REPORT ---\n"
        f"{formatted_issues}\n\n"
        f"--- ORIGINAL CODE ---\n"
        f"{code}\n\n"
        f"Return ONLY the corrected, self-contained MCN code block."
    )
    return prompt


# ── Scaffolds & Explanations ──────────────────────────────────────────────────

def get_agent_scaffold(template: str) -> str:
    """Returns a verified MCN scaffold by template name."""
    t_clean = template.lower().strip()
    return SCAFFOLDS.get(t_clean, SCAFFOLDS["sales_calendar"])

def explain_syntax(query: str) -> Dict[str, Any]:
    """Returns syntax rules and signature for a query."""
    q_clean = query.lower().strip()
    return SYNTAX_RULES.get(q_clean, {
        "syntax": f"{query} ...",
        "description": f"Documentation for '{query}'.",
        "examples": []
    })
