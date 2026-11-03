"""OpenAPI spec and Swagger UI for the workspace backend."""
import re
from pathlib import Path
from flask import Blueprint
from .core import (
    Response,
    _request_workspace,
    jsonify,
)

bp = Blueprint("api_docs", __name__)

# ── OpenAPI 3.0 & Swagger Interactive Explorer ────────────────────────────────

def _generate_openapi_spec(ws: Path) -> dict:
    title = "MCN Full-Stack Application"
    description = "Auto-generated OpenAPI 3.0 specification for MCN services, contracts, and endpoints."
    version = "1.0.0"

    mcn_texts = []
    for f in sorted(ws.rglob("*.mcn")):
        if f.is_file() and not any(p in ("node_modules", "frontend", ".git", "__pycache__") for p in f.parts):
            try:
                mcn_texts.append(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    all_code = "\n".join(mcn_texts)

    tm = re.search(r'title\s+["\']([^"\']+)["\']', all_code)
    if tm:
        title = tm.group(1).strip()
    elif "app " in all_code:
        am = re.search(r'app\s+([A-Za-z0-9_]+)', all_code)
        if am:
            title = f"{am.group(1).strip()} API"

    schemas = {}
    for cm in re.finditer(r'contract\s+([A-Za-z0-9_]+)\s*\n((?:\s+[A-Za-z0-9_]+:\s*[A-Za-z0-9_\[\]]+\n*)+)', all_code):
        cname = cm.group(1).strip()
        body = cm.group(2)
        props = {}
        required = []
        for line in body.strip().splitlines():
            line = line.strip()
            if ":" in line:
                fname, ftype = line.split(":", 1)
                fname = fname.strip()
                ftype = ftype.strip().lower()
                required.append(fname)
                if ftype in ("int", "integer"):
                    props[fname] = {"type": "integer", "example": 1}
                elif ftype in ("float", "real", "number"):
                    props[fname] = {"type": "number", "format": "float", "example": 99.99}
                elif ftype in ("bool", "boolean"):
                    props[fname] = {"type": "boolean", "example": True}
                elif ftype.startswith("list") or ftype.startswith("array"):
                    props[fname] = {"type": "array", "items": {"type": "string"}}
                else:
                    props[fname] = {"type": "string", "example": f"Sample {fname}"}
        schemas[cname] = {
            "type": "object",
            "properties": props,
            "required": required
        }

    paths = {}
    ep_pattern = re.compile(r'(?:@guard\(([^)]*)\)\s*)?endpoint\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)', re.MULTILINE)
    for match in ep_pattern.finditer(all_code):
        guard_meta = match.group(1)
        ep_name = match.group(2).strip()
        params_str = match.group(3).strip()

        ep_path = f"/api/{ep_name}"
        params_list = [p.strip() for p in params_str.split(",") if p.strip()]

        method = "post" if any(k in ep_name.lower() for k in ("create", "save", "add", "update", "delete", "post", "run", "submit", "test", "publish")) or params_list else "get"
        
        tags = ["Core Services"]
        if "item" in ep_name.lower(): tags = ["Inventory"]
        elif "deal" in ep_name.lower() or "sales" in ep_name.lower(): tags = ["Sales & CRM"]
        elif "prompt" in ep_name.lower() or "workflow" in ep_name.lower(): tags = ["AI Marketplace"]
        elif "project" in ep_name.lower() or "job" in ep_name.lower(): tags = ["Construction"]
        elif "analytic" in ep_name.lower() or "report" in ep_name.lower() or "kpi" in ep_name.lower(): tags = ["Analytics & BI"]

        summary = ep_name.replace("_", " ").title()
        description = f"Execute MCN service endpoint `{ep_name}`."
        if guard_meta:
            description += f" **Guarded with RBAC**: `{guard_meta}`."

        op = {
            "summary": summary,
            "description": description,
            "tags": tags,
            "responses": {
                "200": {
                    "description": "Successful execution",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean", "example": True},
                                    "data": {"type": "array", "items": {"type": "object"}}
                                }
                            }
                        }
                    }
                }
            }
        }

        if guard_meta:
            op["security"] = [{"bearerAuth": []}]
            op["responses"]["401"] = {"description": "Missing or invalid JWT Bearer token"}
            op["responses"]["403"] = {"description": "Forbidden — Insufficient role permissions"}

        if method == "get" and params_list:
            op["parameters"] = [
                {
                    "name": p.split("=")[0].strip(),
                    "in": "query",
                    "required": "=" not in p,
                    "schema": {"type": "string"}
                }
                for p in params_list
            ]
        elif method == "post" and params_list:
            body_props = {}
            body_req = []
            for p in params_list:
                pname = p.split("=")[0].strip()
                body_props[pname] = {"type": "string", "example": pname}
                if "=" not in p:
                    body_req.append(pname)
            op["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": body_props,
                            "required": body_req
                        }
                    }
                }
            }

        paths[ep_path] = {method: op}

    if "/health" not in paths:
        paths["/health"] = {
            "get": {
                "summary": "Service Health Check",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {"status": {"type": "string", "example": "ok"}}}}}
                    }
                }
            }
        }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": description,
            "version": version
        },
        "servers": [
            {"url": "http://localhost:8080", "description": "Local MCN Backend Server"},
            {"url": "http://localhost:5003", "description": "MCN Web Playground API"}
        ],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Enter JWT token with role claims (Bearer <token>)"
                }
            }
        }
    }


@bp.route("/api/openapi.json")
def get_openapi_spec():
    """Return auto-generated OpenAPI 3.0 specification."""
    return jsonify(_generate_openapi_spec(_request_workspace()))


@bp.route("/docs")
def get_swagger_docs():
    """Render interactive Swagger UI documentation explorer."""
    swagger_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MCN API Documentation — Swagger UI</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin: 0; background: #0b132b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .swagger-ui .topbar { background-color: #080e21; border-bottom: 1px solid #1e293b; }
    .swagger-ui .info .title { color: #f8fafc; font-size: 24px; font-weight: 800; }
    .swagger-ui .info p, .swagger-ui .info li { color: #94a3b8; }
    .swagger-ui { color: #cbd5e1; }
    .swagger-ui .scheme-container { background: #0f172a; box-shadow: none; border-bottom: 1px solid #1e293b; }
    .swagger-ui .opblock { border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); background: #0f172a; }
    .swagger-ui .opblock .opblock-summary-path { color: #f8fafc; font-weight: 700; }
    .swagger-ui .opblock.opblock-post { border-color: rgba(56,189,248,0.4); background: rgba(56,189,248,0.04); }
    .swagger-ui .opblock.opblock-get { border-color: rgba(52,211,153,0.4); background: rgba(52,211,153,0.04); }
    .swagger-ui .btn.authorize { color: #38bdf8; border-color: #38bdf8; }
    .swagger-ui .btn.authorize svg { fill: #38bdf8; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" charset="UTF-8"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
  <script>
  window.onload = function() {
    window.ui = SwaggerUIBundle({
      url: "/api/openapi.json",
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      plugins: [
        SwaggerUIBundle.plugins.DownloadUrl
      ],
      layout: "StandaloneLayout"
    });
  };
  </script>
</body>
</html>"""
    return Response(swagger_html, mimetype="text/html")
