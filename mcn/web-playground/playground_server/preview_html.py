"""Renders the interactive in-browser preview of a compiled MCN app."""
import json
import re
from pathlib import Path

def _generate_interactive_preview_html(ws: Path, app_code: str, components_code: dict) -> str:
    # ── 1. Extract App Title & Layout Type from ui/app.mcn and App.tsx ────────
    app_title = "MCN Application"
    layout_type = "single"
    nav_items = []

    ui_src = ""
    if (ws / "ui" / "app.mcn").exists():
        try:
            ui_src = (ws / "ui" / "app.mcn").read_text(encoding="utf-8")
        except Exception:
            ui_src = ""

    # App title
    atm = re.search(r'title\s+["\']([^"\']+)["\']', ui_src)
    if atm:
        app_title = atm.group(1).strip()
    else:
        tm = re.search(r'<h1[^>]*>([^<]+)</h1>', app_code)
        if tm:
            app_title = tm.group(1).strip()
        elif "app " in ui_src:
            m = re.search(r'app\s+([A-Za-z0-9_]+)', ui_src)
            if m:
                app_title = m.group(1).strip()

    # Detect Layout & Navigation
    if "sidebar" in ui_src.lower() or "<aside" in app_code:
        layout_type = "sidebar"
    elif "tabs" in ui_src.lower() or "<Tabs" in app_code:
        layout_type = "tabs"

    # Extract Nav Items from ui/app.mcn
    for match in re.finditer(r'(?:nav|tab)\s+["\']([^"\']+)["\']\s+([A-Za-z0-9_]+)', ui_src):
        nav_items.append({"label": match.group(1).strip(), "comp": match.group(2).strip()})

    # If no nav items from mcn, try extracting from App.tsx
    if not nav_items:
        for match in re.finditer(r'setActive\(["\']([^"\']+)["\']\)', app_code):
            lbl = match.group(1).strip()
            if not any(n["label"] == lbl for n in nav_items):
                comp_match = re.search(rf'active\s*===\s*["\']{re.escape(lbl)}["\']\s*&&\s*<([A-Za-z0-9_]+)', app_code)
                comp_name = comp_match.group(1) if comp_match else lbl
                nav_items.append({"label": lbl, "comp": comp_name})

        for match in re.finditer(r'<TabsTrigger\s+value=["\']([^"\']+)["\']', app_code):
            lbl = match.group(1).strip()
            if not any(n["label"] == lbl for n in nav_items):
                nav_items.append({"label": lbl, "comp": lbl})

    # If still no nav items, but we have components, create nav from components
    if not nav_items and components_code:
        comp_keys = list(components_code.keys())
        if "Dashboard" in comp_keys:
            comp_keys.remove("Dashboard")
            comp_keys.insert(0, "Dashboard")
        for ck in comp_keys:
            nav_items.append({"label": ck.replace("Table", "").replace("Form", " Form").strip() or ck, "comp": ck})
        if len(nav_items) > 1:
            layout_type = "sidebar" if len(nav_items) >= 3 else "tabs"

    tabs = [n["label"] for n in nav_items]

    # ── 2. Parse Component Metadata ───────────────────────────────────────────
    parsed_comps = {}
    for comp_name, comp_code in components_code.items():
        card_title = ""
        m = re.search(r'<CardTitle[^>]*>([^<]+)</CardTitle>', comp_code)
        if m:
            card_title = m.group(1).strip()
        if not card_title:
            m = re.search(r'<h[1-3][^>]*>\{?["\']?([^"\'<]+)["\']?\}?</h[1-3]>', comp_code)
            if m:
                card_title = m.group(1).strip()

        cols = []
        for match in re.finditer(r'<TableHead[^>]*>\{?["\']?([^"\'<]+)["\']?\}?</TableHead>', comp_code):
            c = match.group(1).strip()
            if c.lower() != "actions" and c not in cols:
                cols.append(c)

        fields = []
        for match in re.finditer(r'<label[^>]*>([^<]+)</label>', comp_code):
            lbl = match.group(1).strip()
            if lbl and lbl.lower() not in ["actions", "status"] and lbl not in fields:
                fields.append(lbl)

        stats = []
        for match in re.finditer(r'label=["\']([^"\']+)["\'][^>]*value=\{?([^\s">]+)\}?', comp_code):
            stats.append({"label": match.group(1), "value": match.group(2)})

        form_titles = []
        for match in re.finditer(r'card_header\s+["\'](Add[^"\']+|Create[^"\']+|Log[^"\']+|New[^"\']+|Publish[^"\']+)["\']', comp_code, re.IGNORECASE):
            form_titles.append(match.group(1).strip())

        parsed_comps[comp_name] = {
            "name": comp_name,
            "title": card_title or comp_name,
            "columns": cols,
            "fields": fields,
            "stats": stats,
            "form_titles": form_titles,
            "has_table": bool(cols),
            "has_form": bool(fields) or "form" in comp_code.lower() or "button" in comp_code.lower(),
        }

    # ── 3. Multi-Entity Seed Data Engine ───────────────────────────────────────
    datasets = {}

    for comp_name, comp_info in parsed_comps.items():
        cn_lower = comp_name.lower()
        cols = comp_info["columns"]

        # Prompt Marketplace Catalog
        if "market" in cn_lower or "catalog" in cn_lower or "promptitem" in cn_lower or "prompts" in cn_lower:
            datasets[comp_name] = [
                {
                    "id": "1",
                    "title": "Ultra-Realistic Cinematic Photography",
                    "category": "Image & Art",
                    "ai_tool": "Midjourney v6",
                    "prompt_template": "Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0",
                    "description": "Studio-quality portrait and landscape generator with cinematic depth-of-field, volumetric light rays, and hyper-realistic skin textures.",
                    "sample_output": "A hyper-detailed 35mm portrait with golden-hour edge lighting, photorealistic depth, and organic textures.",
                    "price": "$4.99",
                    "author": "AlexRivera",
                    "forks_count": 1420,
                    "avg_rating": 4.95,
                    "tags": "photography, cinematic, midjourney, lighting"
                },
                {
                    "id": "2",
                    "title": "Full-Stack Architecture & TypeScript Refactor",
                    "category": "Coding & Tech",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "Act as a Principal Software Architect. Review the following {{language}} component for {{framework}}. Apply clean architecture, strict typing, error boundaries, and return production-ready code with unit tests:\\n\\n{{code_snippet}}",
                    "description": "Enterprise-grade code reviewer and refactoring engine tailored for TypeScript, React, and microservices architecture.",
                    "sample_output": "Provides clean module interfaces, Zod schema validations, and 100% test coverage patterns.",
                    "price": "$9.99",
                    "author": "ElenaDev",
                    "forks_count": 3840,
                    "avg_rating": 4.99,
                    "tags": "typescript, react, architecture, clean-code"
                },
                {
                    "id": "3",
                    "title": "Viral LinkedIn & Twitter Thread Engine",
                    "category": "Marketing & SEO",
                    "ai_tool": "ChatGPT 4o",
                    "prompt_template": "Write a viral 7-part hook thread about {{topic}} targeting {{audience}}. Use punchy short sentences, contrarian insights, data-backed frameworks, and finish with a high-converting CTA.",
                    "description": "Transforms complex business lessons, tech breakthroughs, and founder stories into viral social engagement threads.",
                    "sample_output": "Hook: 90% of SaaS founders make this pricing mistake... (7-tweet breakdown with actionable takeaways)",
                    "price": "Free",
                    "author": "MarcusGrowth",
                    "forks_count": 6120,
                    "avg_rating": 4.88,
                    "tags": "social, marketing, growth, threads, free"
                },
                {
                    "id": "4",
                    "title": "Autonomous Research Agent System Prompt",
                    "category": "AI Agents",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "You are an Autonomous Research Analyst Agent. Given the research inquiry: {{inquiry}}, perform a 3-step synthesis: 1. Core thesis, 2. Key counter-arguments, 3. Strategic executive recommendations with citations.",
                    "description": "Complete system prompt definition for deploying autonomous market analysis and multi-source research agents.",
                    "sample_output": "Comprehensive executive brief structured with methodology, market sizing, risk matrix, and strategic bets.",
                    "price": "$14.99",
                    "author": "ElenaDev",
                    "forks_count": 890,
                    "avg_rating": 4.92,
                    "tags": "agent, research, system-prompt, langchain"
                },
                {
                    "id": "5",
                    "title": "Cyberpunk Isometric Game Asset Generator",
                    "category": "Image & Art",
                    "ai_tool": "Stable Diffusion XL",
                    "prompt_template": "Isometric 3D render of {{asset_name}}, cyberpunk futuristic aesthetic, neon glow, octane render, game-ready sprite asset on dark clean background",
                    "description": "Generate game-ready 3D isometric sprites, cyber-buildings, props, and UI items with clean alpha transparencies.",
                    "sample_output": "Isometric neon-lit cyber-cafe asset with transparent background alpha ready for Unity/Unreal.",
                    "price": "$2.99",
                    "author": "AlexRivera",
                    "forks_count": 740,
                    "avg_rating": 4.85,
                    "tags": "game-dev, isometric, sdxl, 3d, cyberpunk"
                }
            ]
        # Workflows Studio
        elif "workflow" in cn_lower or "pipeline" in cn_lower:
            datasets[comp_name] = [
                {
                    "id": "1",
                    "title": "End-to-End SEO Content Pipeline",
                    "category": "Marketing & SEO",
                    "description": "Multi-step pipeline that researches search intent, generates SEO outlines, writes 2,000-word authoritative drafts, and optimizes meta tags.",
                    "ai_tools_used": "Claude 3.5 + Perplexity",
                    "step_count": 3,
                    "author": "MarcusGrowth",
                    "price": "$19.99",
                    "forks_count": 1280,
                    "stages": [
                        {"stage": 1, "title": "Search Intent & Topic Cluster Research", "output": "1. Core Intent: High-intent B2B engineering decision makers.\n2. Subtopics: Total cost of ownership, edge latency, API reliability.\n3. Recommended Angle: Enterprise deployment checklist & comparison matrix."},
                        {"stage": 2, "title": "Long-form Structural Outline", "output": "• Section 1: The Modern AI Stack Paradigm Shift\n• Section 2: Security & Architecture Tradeoffs (SOC2, HIPAA)\n• Section 3: Real-World Case Study (40% cost reduction)\n• Section 4: Implementation Blueprint & Code Sandbox\n• Section 5: Executive FAQ"},
                        {"stage": 3, "title": "Production Draft & Meta Tag Optimization", "output": "Article Title: 'The 2026 Guide to Autonomous AI Deployment'\nMeta Description: Learn how leading engineering teams cut latency by 60% with edge pipelines.\nGenerated 2,140 words. Readability: 82.4 | SEO Score: 98.6/100"}
                    ]
                },
                {
                    "id": "2",
                    "title": "API Contract to Frontend Component Suite",
                    "category": "Coding & Tech",
                    "description": "Automated pipeline that transforms OpenAPI YAML specs into TypeScript types, Mock Service Worker handlers, and shadcn/ui components.",
                    "ai_tools_used": "Claude 3.5 + GPT-4o",
                    "step_count": 3,
                    "author": "ElenaDev",
                    "price": "$24.99",
                    "forks_count": 2150,
                    "stages": [
                        {"stage": 1, "title": "OpenAPI Specification Ingestion & Validation", "output": "Validated 14 endpoints and 8 schemas. Extracted User, Prompt, Workflow, Review contracts with 0 syntax errors."},
                        {"stage": 2, "title": "TypeScript Types & MSW Handlers Generation", "output": "Generated 12 TypeScript strict interface types and 6 MSW mock request interceptors with realistic test data."},
                        {"stage": 3, "title": "shadcn/ui Component Transpilation", "output": "Compiled 5 React views with table grids, dialog modals, responsive sidebar layout, and KPI stats cards."}
                    ]
                }
            ]
        # CRM Deals
        elif "deal" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Acme Corp Cloud Migration", "value": "$85,000", "stage": "Proposal", "contact": "Sarah Connor"},
                {"id": "2", "title": "Global Logistics Fleet IoT", "value": "$142,000", "stage": "Negotiation", "contact": "Alex Rivera"},
                {"id": "3", "title": "Apex FinTech Core Engine", "value": "$64,000", "stage": "Won", "contact": "Michael Scott"},
                {"id": "4", "title": "Starlight Retail POS Sync", "value": "$129,000", "stage": "Prospecting", "contact": "Elena Vance"},
                {"id": "5", "title": "Nexus BioTech R&D", "value": "$95,000", "stage": "Qualification", "contact": "David Kim"},
            ]
        # CRM Contacts
        elif "contact" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Sarah Connor", "email": "sarah@acme.com", "company": "Acme Corp", "phone": "+1 (555) 019-2834"},
                {"id": "2", "name": "Alex Rivera", "email": "alex@globallogistics.com", "company": "Global Logistics", "phone": "+1 (555) 028-4921"},
                {"id": "3", "name": "Michael Scott", "email": "mscott@apexfin.com", "company": "Apex FinTech", "phone": "+1 (555) 037-1829"},
                {"id": "4", "name": "Elena Vance", "email": "elena@starlight.io", "company": "Starlight Retail", "phone": "+1 (555) 046-5912"},
                {"id": "5", "name": "David Kim", "email": "dkim@nexusbio.org", "company": "Nexus BioTech", "phone": "+1 (555) 055-7381"},
            ]
        # CRM Companies
        elif "compan" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Acme Corp", "industry": "Cloud Infrastructure", "size": "500+"},
                {"id": "2", "name": "Global Logistics", "industry": "Transportation", "size": "201-500"},
                {"id": "3", "name": "Apex FinTech", "industry": "Financial Services", "size": "51-200"},
                {"id": "4", "name": "Starlight Retail", "industry": "E-Commerce", "size": "51-200"},
                {"id": "5", "name": "Nexus BioTech", "industry": "Biotechnology", "size": "11-50"},
            ]
        # CRM Activities
        elif "activit" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Q3 Deal Review Call", "type": "Call", "contact": "Sarah Connor", "due_date": "2026-09-15"},
                {"id": "2", "title": "Send Contract Draft", "type": "Email", "contact": "Alex Rivera", "due_date": "2026-09-16"},
                {"id": "3", "title": "Architecture Sync Meeting", "type": "Meeting", "contact": "Michael Scott", "due_date": "2026-09-18"},
                {"id": "4", "title": "Follow up on POC feedback", "type": "Task", "contact": "Elena Vance", "due_date": "2026-09-20"},
                {"id": "5", "title": "NDA signed by Legal", "type": "Note", "contact": "David Kim", "due_date": "2026-09-14"},
            ]
        # Construction Projects
        elif "project" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Downtown Metro Station Phase 2", "budget": "$4,200,000", "status": "In Progress", "site": "Site Alpha", "start_date": "2026-01-15", "end_date": "2026-11-30"},
                {"id": "2", "name": "Harbor Bridge Retrofit", "budget": "$1,850,000", "status": "Engineering Review", "site": "East Pier", "start_date": "2026-03-01", "end_date": "2026-08-15"},
                {"id": "3", "name": "Solar Array Substation", "budget": "$920,000", "status": "Completed", "site": "North Field", "start_date": "2025-09-10", "end_date": "2026-02-28"},
                {"id": "4", "name": "Logistics Hub Warehouse B", "budget": "$2,600,000", "status": "Permit Approved", "site": "Sector 4", "start_date": "2026-06-01", "end_date": "2027-01-20"},
            ]
        # Construction Jobs
        elif "job" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "title": "Foundation Concrete Pouring", "assigned_to": "Apex Structural", "status": "Completed"},
                {"id": "2", "title": "HVAC Ventilation Ducting", "assigned_to": "Breeze Mechanical", "status": "In Progress"},
                {"id": "3", "title": "High-Voltage Relay Wiring", "assigned_to": "VoltPower Inc", "status": "Pending"},
                {"id": "4", "title": "Fire Suppression Sprinkler Testing", "assigned_to": "SafetyFirst Co", "status": "Scheduled"},
            ]
        # Construction Compliance
        elif "compliance" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "requirement": "OSHA High-Elevation Fall Arrest", "authority": "OSHA", "status": "Certified", "inspected_at": "2026-08-10"},
                {"id": "2", "requirement": "EPA Runoff Containment", "authority": "EPA", "status": "Passed", "inspected_at": "2026-07-22"},
                {"id": "3", "requirement": "Municipal Seismic Reinforcement", "authority": "City Planning", "status": "Approved", "inspected_at": "2026-09-01"},
            ]
        # Materials
        elif "material" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "High-Tensile Grade 60 Rebar", "quantity": "500", "unit": "Tons", "status": "In Stock"},
                {"id": "2", "name": "Ready-Mix Portland Concrete", "quantity": "350", "unit": "m³", "status": "Delivered"},
                {"id": "3", "name": "Structural I-Beams (W14x90)", "quantity": "120", "unit": "Units", "status": "In Transit"},
                {"id": "4", "name": "Copper Electrical Conduit", "quantity": "80", "unit": "Rolls", "status": "Low Stock"},
            ]
        # Analytics Hub / Transactions
        elif "analytic" in cn_lower or "transaction" in cn_lower or "performance" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "customer": "Acme Corp", "region": "North America", "category": "Enterprise Software", "amount": "$48,000", "status": "closed", "created_at": "2026-01-15"},
                {"id": "2", "customer": "Globex Inc", "region": "Europe", "category": "Cloud Infrastructure", "amount": "$72,000", "status": "closed", "created_at": "2026-02-10"},
                {"id": "3", "customer": "Soylent Corp", "region": "Asia Pacific", "category": "Enterprise Software", "amount": "$31,500", "status": "closed", "created_at": "2026-02-28"},
                {"id": "4", "customer": "Initech", "region": "North America", "category": "Security & Compliance", "amount": "$19,000", "status": "pending", "created_at": "2026-03-05"},
                {"id": "5", "customer": "Umbrella Corp", "region": "Europe", "category": "Cloud Infrastructure", "amount": "$64,000", "status": "closed", "created_at": "2026-03-12"},
                {"id": "6", "customer": "Hooli", "region": "North America", "category": "AI Analytics", "amount": "$89,000", "status": "closed", "created_at": "2026-04-02"},
                {"id": "7", "customer": "Massive Dynamic", "region": "Asia Pacific", "category": "AI Analytics", "amount": "$55,000", "status": "pending", "created_at": "2026-04-18"},
                {"id": "8", "customer": "Stark Industries", "region": "North America", "category": "Cloud Infrastructure", "amount": "$98,000", "status": "closed", "created_at": "2026-05-01"},
            ]
        # Item / Inventory
        elif "item" in cn_lower or "product" in cn_lower or "inventory" in cn_lower:
            datasets[comp_name] = [
                {"id": "1", "name": "Industrial Sensor Node", "price": "$120.00", "stock": "45", "category": "Sensors"},
                {"id": "2", "name": "Edge AI Gateway Controller", "price": "$450.00", "stock": "18", "category": "Controllers"},
                {"id": "3", "name": "Smart Power Relay Switch", "price": "$38.50", "stock": "92", "category": "Switches"},
                {"id": "4", "name": "High-Precision Temperature Probe", "price": "$75.00", "stock": "34", "category": "Sensors"},
                {"id": "5", "name": "Wireless Mesh Beacon", "price": "$29.99", "stock": "150", "category": "Network"},
            ]
        elif cols:
            datasets[comp_name] = [
                {"id": str(i), **{col: f"{col.replace('_', ' ').title()} #{i}" if col != "id" else str(i) for col in cols}}
                for i in range(1, 6)
            ]
        else:
            datasets[comp_name] = [
                {"id": "1", "name": f"{comp_name} Item Alpha", "value": "Operational", "status": "Active"},
                {"id": "2", "name": f"{comp_name} Item Beta", "value": "High Velocity", "status": "Active"},
                {"id": "3", "name": f"{comp_name} Item Gamma", "value": "Pending Review", "status": "In Review"},
            ]

    # Ensure default prompt datasets exist if this is PromptMarketplace
    if any("prompt" in n["label"].lower() or "market" in n["label"].lower() or "workflow" in n["label"].lower() for n in nav_items):
        if "MarketplaceCatalog" not in datasets:
            catalog_key = next((n["comp"] for n in nav_items if "market" in n["label"].lower() or "catalog" in n["label"].lower()), "MarketplaceCatalog")
            datasets[catalog_key] = [
                {
                    "id": "1",
                    "title": "Ultra-Realistic Cinematic Photography",
                    "category": "Image & Art",
                    "ai_tool": "Midjourney v6",
                    "prompt_template": "Cinematic shot of {{subject}}, volumetric rim lighting, 8k resolution, shot on 35mm lens, f/1.8, photorealistic textures, muted color grading --ar 16:9 --v 6.0",
                    "description": "Studio-quality portrait and landscape generator with cinematic depth-of-field, volumetric light rays, and hyper-realistic skin textures.",
                    "sample_output": "A hyper-detailed 35mm portrait with golden-hour edge lighting, photorealistic depth, and organic textures.",
                    "price": "$4.99",
                    "author": "AlexRivera",
                    "forks_count": 1420,
                    "avg_rating": 4.95,
                    "tags": "photography, cinematic, midjourney, lighting"
                },
                {
                    "id": "2",
                    "title": "Full-Stack Architecture & TypeScript Refactor",
                    "category": "Coding & Tech",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "Act as a Principal Software Architect. Review the following {{language}} component for {{framework}}. Apply clean architecture, strict typing, error boundaries, and return production-ready code with unit tests:\\n\\n{{code_snippet}}",
                    "description": "Enterprise-grade code reviewer and refactoring engine tailored for TypeScript, React, and microservices architecture.",
                    "sample_output": "Provides clean module interfaces, Zod schema validations, and 100% test coverage patterns.",
                    "price": "$9.99",
                    "author": "ElenaDev",
                    "forks_count": 3840,
                    "avg_rating": 4.99,
                    "tags": "typescript, react, architecture, clean-code"
                },
                {
                    "id": "3",
                    "title": "Viral LinkedIn & Twitter Thread Engine",
                    "category": "Marketing & SEO",
                    "ai_tool": "ChatGPT 4o",
                    "prompt_template": "Write a viral 7-part hook thread about {{topic}} targeting {{audience}}. Use punchy short sentences, contrarian insights, data-backed frameworks, and finish with a high-converting CTA.",
                    "description": "Transforms complex business lessons, tech breakthroughs, and founder stories into viral social engagement threads.",
                    "sample_output": "Hook: 90% of SaaS founders make this pricing mistake... (7-tweet breakdown with actionable takeaways)",
                    "price": "Free",
                    "author": "MarcusGrowth",
                    "forks_count": 6120,
                    "avg_rating": 4.88,
                    "tags": "social, marketing, growth, threads, free"
                },
                {
                    "id": "4",
                    "title": "Autonomous Research Agent System Prompt",
                    "category": "AI Agents",
                    "ai_tool": "Claude 3.5 Sonnet",
                    "prompt_template": "You are an Autonomous Research Analyst Agent. Given the research inquiry: {{inquiry}}, perform a 3-step synthesis: 1. Core thesis, 2. Key counter-arguments, 3. Strategic executive recommendations with citations.",
                    "description": "Complete system prompt definition for deploying autonomous market analysis and multi-source research agents.",
                    "sample_output": "Comprehensive executive brief structured with methodology, market sizing, risk matrix, and strategic bets.",
                    "price": "$14.99",
                    "author": "ElenaDev",
                    "forks_count": 890,
                    "avg_rating": 4.92,
                    "tags": "agent, research, system-prompt, langchain"
                },
                {
                    "id": "5",
                    "title": "Cyberpunk Isometric Game Asset Generator",
                    "category": "Image & Art",
                    "ai_tool": "Stable Diffusion XL",
                    "prompt_template": "Isometric 3D render of {{asset_name}}, cyberpunk futuristic aesthetic, neon glow, octane render, game-ready sprite asset on dark clean background",
                    "description": "Generate game-ready 3D isometric sprites, cyber-buildings, props, and UI items with clean alpha transparencies.",
                    "sample_output": "Isometric neon-lit cyber-cafe asset with transparent background alpha ready for Unity/Unreal.",
                    "price": "$2.99",
                    "author": "AlexRivera",
                    "forks_count": 740,
                    "avg_rating": 4.85,
                    "tags": "game-dev, isometric, sdxl, 3d, cyberpunk"
                }
            ]

    project_payload = {
        "title": app_title,
        "layout": layout_type,
        "nav_items": nav_items,
        "tabs": tabs,
        "components": parsed_comps,
        "datasets": datasets,
    }

    project_json = json.dumps(project_payload)

    return _fill_template({
        'app_title': app_title,
        'project_json': project_json,
    })


_TEMPLATE_PATH = Path(__file__).with_name("preview_template.html")


def _fill_template(values: dict) -> str:
    """Substitute @@name@@ placeholders in preview_template.html."""
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return re.sub(r"@@(\w+)@@", lambda m: str(values[m.group(1)]), html)
