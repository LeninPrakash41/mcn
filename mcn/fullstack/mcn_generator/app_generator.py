#!/usr/bin/env python3
"""
MCN Full-Stack App Generator — v2.1

Generates a complete runnable application:
  backend/   — MCN service files (contract + service + tests)
  frontend/  — React + TypeScript UI
  config/    — docker-compose, env template
  README.md  — project README

Usage:
  python app_generator.py new insurance-claims --template claims
  python app_generator.py new my-app --template business
  python app_generator.py generate-model Claim --fields "claimant:str,amount:float,status:str"
"""

import os
import json
import textwrap
import argparse
from typing import Dict, List
from pathlib import Path


# ── Built-in templates ────────────────────────────────────────────────────────

TEMPLATES: Dict[str, dict] = {

    "claims": {
        "title":       "Insurance Claims Management",
        "description": "AI-powered insurance claim submission, triage, and processing",
        "contract": {
            "name": "Claim",
            "fields": {
                "claimant":      "str",
                "policy_number": "str",
                "incident_date": "str",
                "description":   "str",
                "amount":        "float",
                "category":      "str",   # AI-classified
                "urgency":       "str",   # AI-classified
                "status":        "str",   # pending / approved / rejected
            },
        },
        "service_name": "claims_api",
        "port": 8080,
        "endpoints": ["submit", "get", "list", "process", "delete", "update"],
        "ai_features": ["classify_urgency", "extract_details", "generate_summary"],
        "table": "claims",
    },

    "business": {
        "title":       "Business Operations",
        "description": "Customer and order management with AI analytics",
        "contract": {
            "name": "Order",
            "fields": {
                "customer_name":  "str",
                "product":        "str",
                "quantity":       "int",
                "amount":         "float",
                "status":         "str",
            },
        },
        "service_name": "orders_api",
        "port": 8080,
        "endpoints": ["create", "get", "list", "update", "delete"],
        "ai_features": ["analyze_trend"],
        "table": "orders",
    },

    "dashboard": {
        "title":       "Business Dashboard",
        "description": "Analytics dashboard with charts, KPIs, and CRUD management",
        "contract": {
            "name": "Record",
            "fields": {
                "name":     "str",
                "category": "str",
                "value":    "float",
                "status":   "str",
            },
        },
        "service_name": "dashboard_api",
        "port": 8080,
        "endpoints": ["submit", "get", "list", "delete", "update"],
        "ai_features": ["analyze_trend"],
        "table": "records",
        "dashboard": True,
    },

    "feedback": {
        "title":       "Customer Feedback",
        "description": "Collect, classify, and respond to customer feedback with AI",
        "contract": {
            "name": "Feedback",
            "fields": {
                "customer":  "str",
                "message":   "str",
                "sentiment": "str",
                "score":     "int",
                "category":  "str",
            },
        },
        "service_name": "feedback_api",
        "port": 8080,
        "endpoints": ["submit", "get", "list", "delete", "update"],
        "ai_features": ["classify_sentiment", "generate_reply"],
        "table": "feedback",
    },
}


# ── Generator ─────────────────────────────────────────────────────────────────

class MCNAppGenerator:

    def create_app(self, app_name: str, template_name: str = "business",
                   features: List[str] = None) -> int:  # noqa: ARG002 (features reserved for future use)

        tpl = TEMPLATES.get(template_name)
        if not tpl:
            available = ", ".join(TEMPLATES.keys())
            print(f"Unknown template '{template_name}'. Available: {available}")
            return 1

        app_dir = Path(app_name)
        if app_dir.exists():
            print(f"Directory '{app_name}' already exists.")
            return 1

        print(f"\nGenerating: {tpl['title']}")
        print(f"Template:   {template_name}")
        print(f"Directory:  {app_name}/\n")

        self._make_dirs(app_dir)
        self._write_backend(app_dir, tpl)
        self._write_ui_mcn(app_dir, tpl)
        self._write_frontend(app_dir, tpl, app_name)
        self._write_config(app_dir, tpl)

        print(f"\n✓  {app_name}/ created")
        print(f"\nNext steps:")
        print(f"  cd {app_name}")
        print(f"  mcn test backend/main.mcn               # run tests")
        print(f"  mcn serve --file backend/main.mcn       # start API on :{tpl['port']}")
        print(f"  mcn build ui/app.mcn --out frontend     # compile UI to React + shadcn")
        print(f"  cd frontend && npm install && npm run dev")
        return 0

    # ── Directory scaffold ────────────────────────────────────────────────────

    def _make_dirs(self, app_dir: Path):
        for d in [
            app_dir / "backend",
            app_dir / "ui",
            app_dir / "frontend" / "src" / "components",
            app_dir / "frontend" / "src" / "services",
            app_dir / "frontend" / "src" / "pages",
            app_dir / "frontend" / "public",
            app_dir / "config",
        ]:
            d.mkdir(parents=True, exist_ok=True)
            print(f"  mkdir {d}")

    # ── Backend ───────────────────────────────────────────────────────────────

    def _write_backend(self, app_dir: Path, tpl: dict):
        contract   = tpl["contract"]
        cname      = contract["name"]
        fields     = contract["fields"]
        table      = tpl["table"]
        svc_name   = tpl["service_name"]
        port       = tpl["port"]
        ai_feats   = set(tpl.get("ai_features", []))
        title      = tpl["title"]

        # ── contract field lines ──────────────────────────────────────────────
        field_lines = "\n".join(
            f"    {fname}: {ftype}" for fname, ftype in fields.items()
        )

        # ── CREATE TABLE sql ─────────────────────────────────────────────────
        sql_type_map = {"str": "TEXT", "int": "INTEGER", "float": "REAL",
                        "bool": "INTEGER"}
        col_defs = ", ".join(
            f"{fname} {sql_type_map.get(ftype, 'TEXT')}"
            for fname, ftype in fields.items()
            if fname != "id"
        )
        create_sql = (
            f"CREATE TABLE IF NOT EXISTS {table} "
            f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs}, "
            f"created_at TEXT DEFAULT (datetime('now')))"
        )

        # ── endpoint bodies ───────────────────────────────────────────────────
        param_names   = [f for f in fields if f not in ("id", "status", "category",
                                                          "urgency", "sentiment",
                                                          "score", "created_at")]
        submit_params = ", ".join(param_names)
        insert_cols   = ", ".join(param_names)
        insert_qmarks = ", ".join("?" for _ in param_names)
        insert_vals   = "(" + ", ".join(param_names) + ")"


        # ── classify / extract blocks ─────────────────────────────────────────
        ai_classify_block = ""
        if "classify_urgency" in ai_feats:
            ai_classify_block = """
        // AI triage
        var category = classify(description, ["property", "medical", "vehicle", "liability", "other"])
        var urgency  = classify(description, ["low", "medium", "high", "critical"])"""
        elif "classify_sentiment" in ai_feats:
            ai_classify_block = """
        // AI sentiment analysis
        var sentiment = classify(message, ["positive", "neutral", "negative"])
        var score_str = ai("Rate the urgency of this feedback 1-10 (number only): " + message)
        var score     = score_str"""
        elif "analyze_trend" in ai_feats:
            ai_classify_block = ""

        # ── AI extract call ───────────────────────────────────────────────────
        if "extract_details" in ai_feats:
            extract_block = f"""
        // Extract structured details from description
        var extracted = extract(description, {cname})"""
        else:
            extract_block = ""

        # ── INSERT statement and args ─────────────────────────────────────────
        if "classify_urgency" in ai_feats:
            all_insert_cols  = insert_cols + ", category, urgency, status"
            all_insert_q     = insert_qmarks + ", ?, ?, ?"
            all_insert_vals  = insert_vals[:-1] + ", category, urgency, \"pending\")"
        elif "classify_sentiment" in ai_feats:
            non_ai = [f for f in param_names if f not in ("sentiment", "score", "category")]
            non_ai_cols = ", ".join(non_ai)
            non_ai_q    = ", ".join("?" for _ in non_ai)
            non_ai_vals = "(" + ", ".join(non_ai) + ", sentiment, score, \"pending\")"
            all_insert_cols  = non_ai_cols + ", sentiment, score, status"
            all_insert_q     = non_ai_q    + ", ?, ?, ?"
            all_insert_vals  = non_ai_vals
        else:
            all_insert_cols = insert_cols
            all_insert_q    = insert_qmarks
            all_insert_vals = insert_vals

        # ── process / update endpoint ─────────────────────────────────────────
        process_endpoint = ""
        if "process" in tpl.get("endpoints", []):
            process_endpoint = f"""
    endpoint process_claim(id, decision, notes = "")
        var existing = query("SELECT * FROM {table} WHERE id = ?", (id,))
        if not existing
            throw "Claim not found: {{id}}"
        var summary = ai("Summarize this claim decision in one sentence. Decision: {{decision}}. Notes: {{notes}}")
        query("UPDATE {table} SET status = ? WHERE id = ?", (decision, id))
        return {{success: true, id: id, status: decision, summary: summary}}"""
        elif "update" in tpl.get("endpoints", []):
            process_endpoint = f"""
    endpoint update_item(id, status)
        query("UPDATE {table} SET status = ? WHERE id = ?", (status, id))
        return {{success: true, id: id, status: status}}"""

        # ── AI summary on list ────────────────────────────────────────────────
        list_ai_block = ""
        if "generate_summary" in ai_feats or "analyze_trend" in ai_feats:
            list_ai_block = f"""
        var summary = ai("Give a one-sentence insight on these {{items}} records")
        return {{success: true, data: items, total: items, insight: summary}}"""
        else:
            list_ai_block = "\n        return {success: true, data: items}"

        # ── delete endpoint ───────────────────────────────────────────────────
        delete_endpoint = ""
        if "delete" in tpl.get("endpoints", []):
            entity_name = table[:-1] if table.endswith('s') else table
            delete_endpoint = f"""
    endpoint delete_{entity_name}(id)
        query("DELETE FROM {table} WHERE id = ?", (id,))
        return {{success: true}}"""

        # ── update endpoint ───────────────────────────────────────────────────
        update_endpoint = ""
        if "update" in tpl.get("endpoints", []):
            entity_name  = table[:-1] if table.endswith('s') else table
            upd_fields   = [f for f in param_names]
            set_clause   = ", ".join(f"{f} = ?" for f in upd_fields)
            upd_vals     = "(" + ", ".join(upd_fields) + ", id)"
            update_endpoint = f"""
    endpoint update_{entity_name}(id, {", ".join(upd_fields)})
        query("UPDATE {table} SET {set_clause} WHERE id = ?", {upd_vals})
        return {{success: true}}"""

        # ── assemble main.mcn ─────────────────────────────────────────────────
        main_mcn = f"""\
// {title}
// Generated by MCN App Generator v2.1

// ── Schema ────────────────────────────────────────────────────────────────────

contract {cname}
{field_lines}

// ── Database init ─────────────────────────────────────────────────────────────

query("{create_sql}")

// ── Service ───────────────────────────────────────────────────────────────────

service {svc_name}
    port {port}

    endpoint submit_{table[:-1] if table.endswith('s') else table}({submit_params}){ai_classify_block}{extract_block}
        query("INSERT INTO {table} ({all_insert_cols}) VALUES ({all_insert_q})", {all_insert_vals})
        var new_id = query("SELECT last_insert_rowid() as id")[0].id
        return {{success: true, id: new_id, status: "pending"}}

    endpoint get_{table[:-1] if table.endswith('s') else table}(id)
        var rows = query("SELECT * FROM {table} WHERE id = ?", (id,))
        if not rows
            throw "{cname} not found: {{id}}"
        return rows[0]

    endpoint list_{table}(limit = 50, offset = 0)
        var items = query("SELECT * FROM {table} ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)){list_ai_block}
{process_endpoint}
{delete_endpoint}
{update_endpoint}

// ── Tests ─────────────────────────────────────────────────────────────────────

test "database initialises"
    var rows = query("SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    assert rows, "Table '{table}' should exist"

test "submit returns an id"
    {self._gen_test_submit(param_names, table)}

test "get returns submitted record"
    {self._gen_test_get(param_names, table)}
"""

        self._write(app_dir / "backend" / "main.mcn", main_mcn)

    def _gen_test_submit(self, param_names: List[str], table: str) -> str:
        sample_vals = self._sample_values(param_names)
        call_args   = ", ".join(f'"{v}"' for v in sample_vals)
        fn_name     = f"submit_{table[:-1] if table.endswith('s') else table}"
        return f"""var r = {fn_name}({call_args})
    assert r.success == true
    assert r.id > 0"""

    def _gen_test_get(self, param_names: List[str], table: str) -> str:
        sample_vals = self._sample_values(param_names)
        call_args   = ", ".join(f'"{v}"' for v in sample_vals)
        fn_name_sub = f"submit_{table[:-1] if table.endswith('s') else table}"
        fn_name_get = f"get_{table[:-1] if table.endswith('s') else table}"
        return f"""var created = {fn_name_sub}({call_args})
    var fetched  = {fn_name_get}(created.id)
    assert fetched.id == created.id"""

    def _sample_values(self, param_names: List[str]) -> List[str]:
        samples = {
            "claimant":      "John Doe",
            "policy_number": "POL-2025-001",
            "incident_date": "2025-03-01",
            "description":   "Vehicle damaged in parking lot",
            "amount":        "2500",
            "customer_name": "Alice",
            "product":       "Widget Pro",
            "quantity":      "3",
            "customer":      "Bob",
            "message":       "Great service!",
            "name":          "Test User",
            "email":         "test@example.com",
        }
        return [samples.get(p, f"test_{p}") for p in param_names]

    # ── MCN UI declarations (component / app syntax) ──────────────────────────

    def _write_ui_mcn(self, app_dir: Path, tpl: dict):
        """
        Write ui/app.mcn — the unified MCN UI file.
        Build it with:  mcn build ui/app.mcn --out frontend
        """
        cname       = tpl["contract"]["name"]
        fields      = tpl["contract"]["fields"]
        table       = tpl["table"]
        title       = tpl["title"]
        theme       = tpl.get("theme", "professional")
        entity      = table[:-1] if table.endswith("s") else table   # "claim"
        entity_cap  = entity.capitalize()                             # "Claim"
        submit_fn   = f"submit_{entity}"
        list_fn     = f"list_{table}"

        # User-facing form fields (exclude auto-generated ones)
        _skip = {"id", "status", "category", "urgency", "sentiment",
                 "score", "created_at"}
        input_fields = {k: v for k, v in fields.items() if k not in _skip}

        # Build state declarations
        state_lines = "\n".join(
            f"    state {fname} = {self._default_state(ftype)}"
            for fname, ftype in input_fields.items()
        )
        state_lines += "\n    state submitting = false\n    state message    = \"\""

        # Build input elements inside the form
        input_elements = "\n".join(
            self._mcn_input_element(fname, ftype)
            for fname, ftype in input_fields.items()
        )

        # Table headers from all fields
        all_cols = ["id", *fields.keys(), "created_at"]
        table_heads = "\n".join(
            f"                        table_head \"{c}\""
            for c in all_cols
        )

        # Edit state declarations (one per editable field)
        edit_state_lines = "\n".join(
            f"    state edit_{fname} = {self._default_state(ftype)}"
            for fname, ftype in input_fields.items()
        )
        edit_state_lines += "\n    state edit_item = null\n    state show_edit_modal = false"

        # Edit form inputs
        edit_input_elements = "\n".join(
            self._mcn_input_element(fname, ftype, prefix="edit_")
            for fname, ftype in input_fields.items()
        )

        # Collect submit params
        submit_args = ", ".join(input_fields.keys())

        ui_mcn = f"""\
// {title} — UI declarations
// Generated by MCN App Generator v2.1
//
// This file defines the full frontend in MCN syntax.
// Compile to React + shadcn with:
//   mcn build ui/app.mcn --out frontend

// ── Form component ─────────────────────────────────────────────────────────────

component {entity_cap}Form
{state_lines}

    on submit
        submitting = true
        var result = {submit_fn}({submit_args})
        if result.success
            message = "Submitted successfully! ID: " + result.id
        submitting = false

    render
        card
            card_header "Submit a {entity_cap}"
            form on_submit=submit
{input_elements}
                button "Submit {entity_cap}" variant="default" disabled=submitting
                div
                    text message

// ── Table component ────────────────────────────────────────────────────────────

component {entity_cap}Table
    state items   = []
    state insight = ""
{edit_state_lines}

    on load
        var response = {list_fn}()
        items   = response.data
        insight = response.insight

    render
        card
            card_header "All {entity_cap}s"
            div
                text insight
            table
                table_header
                    table_row
{table_heads}
                table_body
        modal show=show_edit_modal
            card_header "Edit {entity_cap}"
            form on_submit=handleSave
{edit_input_elements}
                button "Save Changes" variant="default"

// ── App layout ─────────────────────────────────────────────────────────────────

app {cname}Manager
    title  "{title}"
    theme  "{theme}"
    layout
        tabs
{self._gen_app_tabs(tpl, entity_cap)}
"""
        if tpl.get("dashboard"):
            ui_mcn += self._gen_dashboard_component(entity_cap, list_fn)
        self._write(app_dir / "ui" / "app.mcn", ui_mcn)

    def _gen_app_tabs(self, tpl: dict, entity_cap: str) -> str:
        """Return the tab lines for the app layout block."""
        lines = [
            f'            tab "Submit {entity_cap}"  {entity_cap}Form',
            f'            tab "All {entity_cap}s"    {entity_cap}Table',
        ]
        if tpl.get("dashboard"):
            lines.append(f'            tab "Dashboard"           {entity_cap}Dashboard')
        return "\n".join(lines)

    def _gen_dashboard_component(self, entity_cap: str, list_fn: str) -> str:
        """Return MCN source for a DashboardStats component (charts + KPI cards)."""
        return f"""\
// ── Dashboard component ────────────────────────────────────────────────────────

component {entity_cap}Dashboard
    state chart_data = []
    state total      = 0
    state insight    = ""

    on load
        var response = {list_fn}()
        chart_data = response.data
        total      = response.total
        insight    = response.insight

    render
        card
            card_header "Dashboard Overview"
            div grid_cols=3
                stat_card label="Total {entity_cap}s" value=total unit=""
                stat_card label="AI Insight" value=insight unit=""
            bar_chart data=chart_data x_key="status" y_key="id" height=300
"""

    def _default_state(self, ftype: str) -> str:
        """Return a sensible default for a state variable based on field type."""
        return {"int": "0", "float": "0", "bool": "false"}.get(ftype, '""')

    def _mcn_input_element(self, fname: str, ftype: str, prefix: str = "") -> str:
        """Return a MCN input element line for a form field.

        prefix: if "edit_", binds to edit_{fname} instead of {fname}.
        """
        label    = fname.replace("_", " ").title()
        bind_var = f"{prefix}{fname}"
        if ftype in ("int", "float"):
            return f'                input bind={bind_var} label="{label}" type="number"'
        if fname in ("description", "notes", "message", "details"):
            return f'                textarea bind={bind_var} label="{label}"'
        if fname == "incident_date" or "date" in fname:
            return f'                input bind={bind_var} label="{label}" type="date"'
        return f'                input bind={bind_var} label="{label}"'

    # ── Frontend ──────────────────────────────────────────────────────────────

    def _write_frontend(self, app_dir: Path, tpl: dict, app_name: str):
        cname  = tpl["contract"]["name"]
        fields = tpl["contract"]["fields"]
        table  = tpl["table"]
        port   = tpl["port"]
        title  = tpl["title"]

        # Only the user-facing input fields
        input_fields = {
            k: v for k, v in fields.items()
            if k not in ("id", "status", "category", "urgency", "sentiment",
                         "score", "created_at")
        }

        # package.json
        self._write(app_dir / "frontend" / "package.json", json.dumps({
            "name":    f"{app_name}-frontend",
            "version": "1.0.0",
            "private": True,
            "dependencies": {
                "react":           "^18.2.0",
                "react-dom":       "^18.2.0",
                "typescript":      "^5.3.0",
                "@types/react":    "^18.0.28",
                "@types/react-dom":"^18.0.11",
                "vite":            "^5.0.0",
                "@vitejs/plugin-react": "^4.0.0",
            },
            "scripts": {
                "dev":   "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
        }, indent=2))

        # vite.config.ts
        self._write(app_dir / "frontend" / "vite.config.ts", f"""\
import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],
  server: {{
    proxy: {{
      '/api': 'http://localhost:{port}'
    }}
  }}
}})
""")

        # API client
        submit_fn  = f"submit_{table[:-1] if table.endswith('s') else table}"
        get_fn     = f"get_{table[:-1] if table.endswith('s') else table}"
        list_fn    = f"list_{table}"
        process_fn = "process_claim" if "process" in tpl.get("endpoints", []) else "update_item"

        self._write(app_dir / "frontend" / "src" / "services" / "api.ts", f"""\
const BASE = '/api';

async function call(endpoint: string, body: Record<string, unknown>) {{
  const res = await fetch(`${{BASE}}/${{endpoint}}`, {{
    method:  'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body:    JSON.stringify(body),
  }});
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}}

export const api = {{
  submit:  (data: Record<string, unknown>) => call('{submit_fn}', data),
  get:     (id: number)                    => call('{get_fn}', {{ id }}),
  list:    (limit = 50)                    => call('{list_fn}', {{ limit }}),
  process: (id: number, decision: string, notes = '') =>
    call('{process_fn}', {{ id, decision, notes }}),
}};
""")

        # Form fields JSX
        form_fields_jsx = "\n".join(
            self._input_jsx(fname, ftype)
            for fname, ftype in input_fields.items()
        )

        # Table header cells
        all_col_names = ["id", *fields.keys(), "created_at"]
        th_cells = "".join(f"<th>{c}</th>" for c in all_col_names)
        td_cells = "".join(
            f"{{(row as any)['{c}']}} " for c in all_col_names
        )

        # Process button (claims template)
        process_section = ""
        if "process" in tpl.get("endpoints", []):
            process_section = """\

  async function processRow(id: number, decision: string) {
    await api.process(id, decision);
    loadRows();
  }
"""
            process_td = """<td>
            <button onClick={() => processRow((row as any).id, 'approved')}>✓ Approve</button>
            {' '}
            <button onClick={() => processRow((row as any).id, 'rejected')}>✗ Reject</button>
          </td>"""
        else:
            process_td = ""

        # Main App.tsx
        self._write(app_dir / "frontend" / "src" / "App.tsx", f"""\
import React from 'react';
import {{ api }} from './services/api';
import './App.css';

const FIELDS = {json.dumps(list(input_fields.keys()))};

export default function App() {{
  const [rows, setRows]       = React.useState<unknown[]>([]);
  const [form, setForm]       = React.useState<Record<string,string>>(
    Object.fromEntries(FIELDS.map(f => [f, '']))
  );
  const [status, setStatus]   = React.useState('');
  const [loading, setLoading] = React.useState(false);

  async function loadRows() {{
    const data = await api.list();
    setRows(data.data ?? []);
  }}

  React.useEffect(() => {{ loadRows(); }}, []);

  async function handleSubmit(e: React.FormEvent) {{
    e.preventDefault();
    setLoading(true);
    setStatus('');
    try {{
      const result = await api.submit(form);
      setStatus(`Submitted — ID: ${{result.id}}, Status: ${{result.status}}`);
      setForm(Object.fromEntries(FIELDS.map(f => [f, ''])));
      loadRows();
    }} catch (err: any) {{
      setStatus(`Error: ${{err.message}}`);
    }} finally {{
      setLoading(false);
    }}
  }}
  {process_section}
  return (
    <div className="app">
      <header>
        <h1>{title}</h1>
        <p>Powered by MCN</p>
      </header>

      <section className="form-section">
        <h2>New Submission</h2>
        <form onSubmit={{handleSubmit}}>
{form_fields_jsx}
          <button type="submit" disabled={{loading}}>
            {{loading ? 'Submitting…' : 'Submit'}}
          </button>
          {{status && <p className="status">{{status}}</p>}}
        </form>
      </section>

      <section className="list-section">
        <h2>Records</h2>
        <table>
          <thead><tr>{th_cells}{'<th>Actions</th>' if process_section else ''}</tr></thead>
          <tbody>
            {{rows.map((row: unknown, i) => (
              <tr key={{i}}>
                {td_cells}
                {process_td}
              </tr>
            ))}}
          </tbody>
        </table>
      </section>
    </div>
  );
}}
""")

        # CSS
        self._write(app_dir / "frontend" / "src" / "App.css", """\
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body  { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; }
.app  { max-width: 1100px; margin: 0 auto; padding: 20px; }
header { background: #1a5f99; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 24px; }
header p { opacity: .7; font-size: 13px; margin-top: 4px; }
section { background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 24px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); }
h2 { font-size: 16px; margin-bottom: 16px; }
form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field.full { grid-column: 1 / -1; }
label { font-size: 12px; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: .5px; }
input, textarea { padding: 8px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
input:focus, textarea:focus { outline: none; border-color: #1a5f99; }
textarea { resize: vertical; min-height: 80px; }
button { grid-column: 1 / -1; padding: 10px; background: #1a5f99; color: #fff;
         border: none; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: 600; }
button:hover { background: #154d80; }
button:disabled { opacity: .6; cursor: default; }
.status { grid-column: 1/-1; padding: 8px 12px; background: #e8f4e8;
          border: 1px solid #a3d5a3; border-radius: 4px; font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f8f8; font-weight: 600; font-size: 11px; text-transform: uppercase;
     letter-spacing: .5px; color: #666; }
tr:hover { background: #fafafa; }
td button { padding: 4px 8px; font-size: 11px; grid-column: unset; margin-right: 4px; }
""")

        # index.html
        self._write(app_dir / "frontend" / "index.html", f"""\
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
""")

        # main.tsx
        self._write(app_dir / "frontend" / "src" / "main.tsx", """\
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
""")

    def _input_jsx(self, fname: str, ftype: str) -> str:
        label   = fname.replace("_", " ").title()
        is_long = fname in ("description", "message", "notes", "summary")
        is_num  = ftype in ("int", "float")
        is_date = "date" in fname
        kind    = "full" if is_long else ""

        if is_long:
            return f"""\
          <div className="field full">
            <label>{label}</label>
            <textarea name="{fname}" value={{form['{fname}'] ?? ''}}
              onChange={{e => setForm(p => ({{...p, {fname}: e.target.value}}))}}>
            </textarea>
          </div>"""
        else:
            itype = "date" if is_date else ("number" if is_num else "text")
            return f"""\
          <div className="field {kind}">
            <label>{label}</label>
            <input type="{itype}" name="{fname}" value={{form['{fname}'] ?? ''}}
              onChange={{e => setForm(p => ({{...p, {fname}: e.target.value}}))}} />
          </div>"""

    # ── Config files ──────────────────────────────────────────────────────────

    def _write_config(self, app_dir: Path, tpl: dict):
        port  = tpl["port"]
        title = tpl["title"]

        self._write(app_dir / ".env.example", f"""\
ANTHROPIC_API_KEY=sk-ant-...
MCN_AI_PROVIDER=anthropic
DATABASE_URL=sqlite:///./data.db
""")

        self._write(app_dir / "docker-compose.yml", f"""\
version: '3.9'
services:
  backend:
    image: python:3.12-slim
    working_dir: /app
    volumes:
      - ./backend:/app
      - ./data:/data
    ports:
      - "{port}:{port}"
    environment:
      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
      - MCN_AI_PROVIDER=anthropic
    command: mcn serve --file main.mcn --port {port}

  frontend:
    image: node:20-alpine
    working_dir: /app
    volumes:
      - ./frontend:/app
    ports:
      - "3000:3000"
    command: sh -c "npm install && npm run dev -- --host"
    depends_on:
      - backend
""")

        self._write(app_dir / "README.md", f"""\
# {title}

Generated by MCN App Generator v2.1.

## Stack

- **Backend** — MCN service (`backend/main.mcn`)
- **Frontend** — React + TypeScript + Vite (`frontend/`)
- **AI** — Anthropic Claude via `ai()`, `classify()`, `extract()`
- **Database** — SQLite (zero-config)

## Quick Start

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Backend
mcn test backend/main.mcn          # run tests first
mcn serve --file backend/main.mcn  # API on :{port}

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

## Docker

```bash
docker-compose up
# API  → http://localhost:{port}
# UI   → http://localhost:3000
```

## Backend endpoints

| Endpoint | Method | Description |
|---|---|---|
{self._endpoint_table(tpl)}
""")

    def _endpoint_table(self, tpl: dict) -> str:
        table = tpl["table"]
        cname = tpl["contract"]["name"].lower()
        rows  = []
        for ep in tpl.get("endpoints", []):
            if ep == "submit":
                rows.append(f"| `submit_{cname}` | POST | Submit a new {cname} (AI triage) |")
            elif ep == "get":
                rows.append(f"| `get_{cname}` | POST | Fetch a single {cname} by id |")
            elif ep == "list":
                rows.append(f"| `list_{table}` | POST | List all {table} |")
            elif ep == "process":
                rows.append(f"| `process_claim` | POST | Approve or reject a claim |")
            elif ep == "create":
                rows.append(f"| `create_{cname}` | POST | Create a {cname} |")
            elif ep == "update":
                rows.append(f"| `update_item` | POST | Update status |")
        return "\n".join(rows)

    # ── Standalone generators ─────────────────────────────────────────────────

    def generate_model(self, model_name: str, fields: Dict[str, str]) -> int:
        sql_map  = {"str": "TEXT", "int": "INTEGER", "float": "REAL", "bool": "INTEGER"}
        col_defs = ", ".join(
            f"{k} {sql_map.get(v, 'TEXT')}" for k, v in fields.items()
        )
        field_lines = "\n".join(f"    {k}: {v}" for k, v in fields.items())
        param_list  = ", ".join(fields.keys())
        q_marks     = ", ".join("?" for _ in fields)
        vals_tuple  = "(" + ", ".join(fields.keys()) + ")"

        code = f"""\
contract {model_name}
{field_lines}

query("CREATE TABLE IF NOT EXISTS {model_name.lower()}s (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs})")

service {model_name.lower()}_api
    port 8080

    endpoint create({param_list})
        query("INSERT INTO {model_name.lower()}s ({param_list}) VALUES ({q_marks})", {vals_tuple})
        var id = query("SELECT last_insert_rowid() as id")[0].id
        return {{success: true, id: id}}

    endpoint get(id)
        var rows = query("SELECT * FROM {model_name.lower()}s WHERE id = ?", (id,))
        if not rows
            throw "{model_name} not found: {{id}}"
        return rows[0]

    endpoint list()
        var rows = query("SELECT * FROM {model_name.lower()}s ORDER BY id DESC")
        return {{success: true, data: rows}}

test "create and retrieve {model_name.lower()}"
    var r = create({", ".join(f'"{k}"' for k in fields)})
    assert r.success == true
    var row = get(r.id)
    assert row.id == r.id
"""
        path = Path(f"{model_name.lower()}.mcn")
        self._write(path, code)
        print(f"✓  {path}")
        return 0

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _write(path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  write  {path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MCN Full-Stack App Generator v2.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python app_generator.py new my-claims --template claims
          python app_generator.py new my-shop   --template business
          python app_generator.py generate-model Invoice --fields "customer:str,amount:float,paid:bool"
        """)
    )
    sub = parser.add_subparsers(dest="command")

    # new
    p_new = sub.add_parser("new", help="Scaffold a full-stack app")
    p_new.add_argument("name", help="App directory name")
    p_new.add_argument("--template", default="business",
                       choices=list(TEMPLATES.keys()),
                       help="App template (default: business)")

    # generate-model
    p_model = sub.add_parser("generate-model", help="Generate a standalone MCN model + service")
    p_model.add_argument("name", help="Model name (e.g. Invoice)")
    p_model.add_argument("--fields", required=True,
                         help="Comma-separated name:type pairs, e.g. customer:str,amount:float")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    gen = MCNAppGenerator()

    if args.command == "new":
        return gen.create_app(args.name, args.template)

    if args.command == "generate-model":
        fields = {}
        for pair in args.fields.split(","):
            k, v = pair.strip().split(":")
            fields[k.strip()] = v.strip()
        return gen.generate_model(args.name, fields)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
