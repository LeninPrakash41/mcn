"""Default files seeded into a new playground workspace."""
import json
import os
from pathlib import Path
from .core import (
    _request_workspace,
)

# ── Workspace endpoints ───────────────────────────────────────────────────────

_DEFAULT_BACKEND = '''\
// MCN Backend Service — click ▶ Run Backend [Ctrl+Enter] to test
service api
    port 8080

    endpoint get_dashboard()
        return {
            title: "Sales Intelligence Hub",
            active_deals: 14,
            pipeline_value: "$420,000",
            status: "online"
        }

    endpoint list_leads()
        return [
            {id: "L1", name: "Sarah Jenkins", company: "Acme Health", value: 75000, status: "Qualified"},
            {id: "L2", name: "David Lin", company: "Vertex AI", value: 140000, status: "Proposal"},
            {id: "L3", name: "Elena Rostova", company: "FinTech Cloud", value: 185000, status: "Closing"}
        ]

// Live startup script
var welcome = "MCN Studio Ready"
log("⚡ " + welcome)
var leads = list_leads()
log("✓ Loaded " + str(len(leads)) + " active sales pipeline leads")
for lead in leads
    log("  • " + lead.name + " (" + lead.company + ") - $" + str(lead.value))
'''

_DEFAULT_UI = '''\
// MCN UI — click ⚡ Build & Preview to compile to React & Flutter
component Dashboard
    state leads = []
    state total = "$420,000"

    on load
        leads = list_leads()

    render
        card
            card_header "Sales Intelligence & Pipeline"
            stat label="Active Pipeline" value=total change=14.2
            table data=leads
                table_header
                    table_row
                        table_head "id"
                        table_head "name"
                        table_head "company"
                        table_head "value"
                        table_head "status"
                table_body

app MainApp
    title "Sales Intelligence Hub"
    layout
        main
            Dashboard
'''

_ITEM_MANAGER_BACKEND = '''\
// MCN Backend — edit me and click ⚡ Build
contract Item
    name: str
    price: float

query("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, created_at TEXT DEFAULT (datetime('now')))")

service items_api
    port 8080

    endpoint list_items()
        var items = query("SELECT * FROM items ORDER BY created_at DESC")
        return {success: true, data: items}

    endpoint create_item(name, price)
        query("INSERT INTO items (name, price) VALUES (?, ?)", (name, price))
        var id = query("SELECT last_insert_rowid() as id")[0].id
        return {success: true, id: id}

    endpoint delete_item(id)
        query("DELETE FROM items WHERE id=?", (id,))
        return {success: true}
'''

_ITEM_MANAGER_UI = '''\
component ItemForm
    state name    = ""
    state price   = 0
    state message = ""

    on submit
        var result = create_item(name, price)
        if result.success
            message = "Created item!"

    render
        card
            card_header "Add Item"
            form on_submit=submit
                input bind=name label="Name"
                input bind=price label="Price" type="number"
                button "Add Item" variant="default"
                div
                    text message

component ItemTable
    state items = []

    on load
        var resp = list_items()
        items = resp.data

    render
        card
            card_header "All Items"
            table
                table_header
                    table_row
                        table_head "name"
                        table_head "price"
                        table_head "created_at"
                table_body

app ItemManager
    title  "Item Manager"
    layout
        tabs
            tab "Add Item"  ItemForm
            tab "All Items" ItemTable
'''


_DEFAULT_MOBILE_DART = '''\
import 'package:flutter/material.dart';
import 'screens/dashboard.dart';

void main() {
  runApp(const MCNMobileApp());
}

class MCNMobileApp extends StatelessWidget {
  const MCNMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sales Intelligence Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0F1D),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          secondary: Color(0xFFFF6B6B),
          surface: Color(0xFF111C33),
        ),
        useMaterial3: true,
      ),
      home: const DashboardScreen(),
    );
  }
}
'''

_DEFAULT_MOBILE_SCREEN = '''\
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../widgets/mcn_widgets.dart';

// MCN backend URL. Pass --dart-define=MCN_API_URL=... (Android emulator: http://10.0.2.2:8080)
const String kApiUrl = String.fromEnvironment('MCN_API_URL', defaultValue: 'http://localhost:8080');

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  // Demo data shown until the backend responds (or if it is not running)
  static const List<Map<String, dynamic>> _demoLeads = [
    {"name": "Sarah Jenkins", "company": "Acme Health", "value": 75000, "status": "Qualified"},
    {"name": "David Lin", "company": "Vertex AI", "value": 140000, "status": "Proposal"},
    {"name": "Elena Rostova", "company": "FinTech Cloud", "value": 185000, "status": "Closing"},
  ];

  String _title = "Sales Intelligence";
  int _activeDeals = 14;
  String _pipelineValue = "\\$420,000";
  List<Map<String, dynamic>> _leads = _demoLeads;
  bool _loading = true;
  bool _live = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  // MCN services expose each endpoint as POST /<endpoint_name> with a JSON body
  Future<dynamic> _call(String endpoint) async {
    final res = await http
        .post(Uri.parse('$kApiUrl/$endpoint'),
            headers: {'Content-Type': 'application/json'}, body: '{}')
        .timeout(const Duration(seconds: 5));
    if (res.statusCode != 200) throw Exception('HTTP ${res.statusCode}');
    return jsonDecode(res.body);
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final dashboard = await _call('get_dashboard') as Map<String, dynamic>;
      final leads = (await _call('list_leads') as List).cast<Map<String, dynamic>>();
      setState(() {
        _title = dashboard['title']?.toString() ?? _title;
        _activeDeals = (dashboard['active_deals'] as num?)?.toInt() ?? leads.length;
        _pipelineValue = dashboard['pipeline_value']?.toString() ?? _pipelineValue;
        _leads = leads;
        _live = true;
      });
    } catch (_) {
      setState(() => _live = false);
    } finally {
      setState(() => _loading = false);
    }
  }

  String _money(dynamic v) {
    if (v is! num) return v?.toString() ?? '';
    final digits = v.round().toString();
    final out = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) out.write(',');
      out.write(digits[i]);
    }
    return '\\$$out';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: const Color(0xFF111C33),
        elevation: 0,
        actions: [
          IconButton(
            icon: _loading
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.refresh, color: Color(0xFF38BDF8)),
            tooltip: 'Reload from MCN backend',
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (!_loading && !_live)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0x33F59E0B),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0x66F59E0B)),
                  ),
                  child: const Text(
                    "Showing demo data. Start the MCN backend (Run in MCN Studio) at $kApiUrl, then pull to refresh.",
                    style: TextStyle(color: Color(0xFFFCD34D), fontSize: 12),
                  ),
                ),
              // KPI Stat Row
              Row(
                children: [
                  Expanded(
                    child: MCNStatCard(
                      label: "Active Deals",
                      value: "$_activeDeals",
                      change: _live ? "Live" : "Demo",
                      isPositive: true,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: MCNStatCard(
                      label: "Pipeline Value",
                      value: _pipelineValue,
                      change: _live ? "Live" : "Demo",
                      isPositive: true,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Section Header
              const Text(
                "Recent High-Value Leads",
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 12),

              // Leads List
              ..._leads.map((lead) => MCNLeadTile(
                name: lead["name"]?.toString() ?? '',
                company: lead["company"]?.toString() ?? '',
                value: _money(lead["value"]),
                status: lead["status"]?.toString() ?? '',
              )),

              const SizedBox(height: 20),
              // Primary Action Button
              MCNButton(
                text: "+ Create New Deal Opportunity",
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Add a create_deal endpoint to backend/main.mcn to save deals.")),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
'''

_DEFAULT_MOBILE_WIDGETS = '''\
import 'package:flutter/material.dart';

class MCNStatCard extends StatelessWidget {
  final String label;
  final String value;
  final String change;
  final bool isPositive;

  const MCNStatCard({
    super.key,
    required this.label,
    required this.value,
    required this.change,
    this.isPositive = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14.0),
      decoration: BoxDecoration(
        color: const Color(0xFF111C33),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E2D4A)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 4),
          Text(
            change,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: isPositive ? const Color(0xFF10B981) : const Color(0xFFFF6B6B)),
          ),
        ],
      ),
    );
  }
}

class MCNLeadTile extends StatelessWidget {
  final String name;
  final String company;
  final String value;
  final String status;

  const MCNLeadTile({
    super.key,
    required this.name,
    required this.company,
    required this.value,
    required this.status,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF182442),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E2D4A)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.white)),
              const SizedBox(height: 2),
              Text(company, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(value, style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF38BDF8), fontSize: 13)),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0x2038BDF8),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0x4038BDF8)),
                ),
                child: Text(status, style: const TextStyle(fontSize: 10, color: Color(0xFF38BDF8), fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class MCNButton extends StatelessWidget {
  final String text;
  final VoidCallback onPressed;

  const MCNButton({
    super.key,
    required this.text,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF0284C7),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: onPressed,
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
      ),
    );
  }
}
'''

_DEFAULT_MOBILE_MCN = '''\
// MCN Mobile UI (Flutter Target)
// Click ⚡ Build Flutter Simulator to compile to mobile package

component MobileDashboard
    state active_deals = 14
    state pipeline_value = "$420,000"

    render
        card
            card_header "Sales Intelligence Mobile"
            stat label="Active Deals" value="14" change=12.5
            stat label="Pipeline Value" value="$420,000" change=18.2
            button "+ Create New Deal Opportunity"

app MobileSalesApp
    title "Sales Intelligence Mobile"
    target "flutter"
    layout
        main
            MobileDashboard
'''

_DEFAULT_PUBSPEC = '''\
name: mcn_mobile_app
description: MCN Model Context Native Mobile Application
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0

flutter:
  uses-material-design: true
'''

_DEFAULT_MOBILE_MANIFEST = {
    "name": "SalesMobileApp",
    "components": {
        "Dashboard": {
            "type": "container",
            "props": {"className": "column"},
            "children": [
                {"type": "text", "props": {"tag": "h1", "content": "Sales Intelligence Mobile"}},
                {"type": "card", "props": {"title": "Active Pipeline", "value": "$420,000"}},
                {"type": "button", "props": {"text": "⚡ Refresh Deals"}},
                {"type": "input", "props": {"placeholder": "Search leads..."}}
            ]
        }
    },
    "pages": {
        "Sales Intelligence": {
            "components": ["Dashboard"]
        }
    }
}

_DEFAULT_REPL_SCRIPT = '''\
// MCN REPL Script — Press Ctrl+Enter to execute expressions

var title = "MCN REPL Environment"
log("⚡ " + title)

function calculate_roi(revenue, cost)
    return ((revenue - cost) / cost) * 100

var revenue = 150000
var cost = 95000
var roi = calculate_roi(revenue, cost)

log("Revenue: $" + str(revenue))
log("Cost:    $" + str(cost))
log("ROI:     " + str(roi) + "%")

// Working with lists
var deals = [45000, 120000, 85000, 30000, 210000]
log("Total Pipeline: $" + str(sum(deals)))
log("Average Deal:   $" + str(avg(deals)))
log("Max Deal:       $" + str(max(deals)))
'''


def _seed_workspace(ws: Path | None = None):
    """Write default starter files if workspace is empty or missing MCN files."""
    ws = ws or _request_workspace()
    
    # 1. Web Workspace
    backend_dir = ws / "backend"
    ui_dir      = ws / "ui"
    backend_dir.mkdir(parents=True, exist_ok=True)
    ui_dir.mkdir(parents=True, exist_ok=True)
    backend_file = backend_dir / "main.mcn"
    ui_file      = ui_dir / "app.mcn"
    if not backend_file.exists():
        backend_file.write_text(_DEFAULT_BACKEND, encoding="utf-8")
    if not ui_file.exists():
        ui_file.write_text(_DEFAULT_UI, encoding="utf-8")

    # 2. Mobile (Flutter) Workspace
    mobile_dir = ws / "mobile"
    mobile_lib = mobile_dir / "lib"
    mobile_screens = mobile_lib / "screens"
    mobile_widgets = mobile_lib / "widgets"
    mobile_screens.mkdir(parents=True, exist_ok=True)
    mobile_widgets.mkdir(parents=True, exist_ok=True)

    dart_main = mobile_lib / "main.dart"
    dart_screen = mobile_screens / "dashboard.dart"
    dart_widgets = mobile_widgets / "mcn_widgets.dart"
    mobile_mcn = mobile_dir / "ui.mcn"
    pubspec_file = mobile_dir / "pubspec.yaml"
    mobile_manifest = mobile_dir / "ui-manifest.json"

    if not dart_main.exists():
        dart_main.write_text(_DEFAULT_MOBILE_DART, encoding="utf-8")
    if not dart_screen.exists():
        dart_screen.write_text(_DEFAULT_MOBILE_SCREEN, encoding="utf-8")
    if not dart_widgets.exists():
        dart_widgets.write_text(_DEFAULT_MOBILE_WIDGETS, encoding="utf-8")
    if not mobile_mcn.exists():
        mobile_mcn.write_text(_DEFAULT_MOBILE_MCN, encoding="utf-8")
    if not pubspec_file.exists():
        pubspec_file.write_text(_DEFAULT_PUBSPEC, encoding="utf-8")
    if not mobile_manifest.exists():
        mobile_manifest.write_text(json.dumps(_DEFAULT_MOBILE_MANIFEST, indent=2), encoding="utf-8")

    # Clean up the legacy generated flutter folder — only in Studio's own
    # workspace, never in a developer's project opened with `mcn studio <dir>`
    legacy_flutter = ws / "flutter"
    if legacy_flutter.exists() and not os.environ.get("MCN_WORKSPACE"):
        import shutil
        shutil.rmtree(legacy_flutter, ignore_errors=True)

    # 3. REPL Scripts Workspace
    scripts_dir = ws / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    repl_file = scripts_dir / "sandbox.mcn"
    if not repl_file.exists():
        repl_file.write_text(_DEFAULT_REPL_SCRIPT, encoding="utf-8")
