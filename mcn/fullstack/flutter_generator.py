"""
Flutter Project Generator for MCN UI Integration
Generates complete Flutter projects from MCN UI definitions
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any


class FlutterProjectGenerator:
    """Generate Flutter projects from MCN UI definitions"""
    
    def __init__(self):
        pass
    
    def generate_project(self, ui_manifest_path: str, output_dir: str, project_name: str):
        """Generate complete Flutter project from UI manifest"""
        
        # Load UI manifest
        with open(ui_manifest_path, 'r') as f:
            manifest = json.load(f)
            
        self.manifest = manifest
        self.components = manifest.get('components', {})
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate project structure
        self._create_project_structure(output_path)
        
        # Generate pubspec.yaml
        self._generate_pubspec_yaml(output_path, project_name)
        
        # Generate Flutter widgets (custom wrappers)
        self._generate_ui_components(output_path)
        
        # Generate MCN Client
        self._generate_mcn_client(output_path)
        
        # Generate page widgets
        self._generate_pages(output_path, manifest)
        
        # Generate main.dart
        self._generate_main_dart(output_path, manifest)
        
        return f"Flutter project generated at {output_path}"
    
    def _create_project_structure(self, output_path: Path):
        """Create Flutter project directory structure"""
        directories = [
            output_path / "lib",
            output_path / "lib" / "pages", 
            output_path / "lib" / "services",
            output_path / "lib" / "widgets",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def _generate_pubspec_yaml(self, output_path: Path, project_name: str):
        """Generate pubspec.yaml"""
        formatted_name = project_name.lower().replace(" ", "_").replace("-", "_")
        pubspec = f"""name: {formatted_name}
description: MCN generated Flutter mobile application.
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
"""
        with open(output_path / "pubspec.yaml", 'w') as f:
            f.write(pubspec)
            
    def _generate_mcn_client(self, output_path: Path):
        """Generate Dart MCN API client"""
        client_code = """import 'dart:convert';
import 'package:http/http.dart' as http;

class MCNClient {
  static final MCNClient _instance = MCNClient._internal();
  factory MCNClient() => _instance;
  MCNClient._internal();

  String baseUrl = 'http://localhost:8000';

  Future<Map<String, dynamic>> call(String action, Map<String, dynamic> payload) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/main'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'action': action,
          ...payload,
        }),
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = json.decode(response.body);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
        return {'success': true, 'data': decoded};
      }
      return {'success': false, 'error': 'Server returned code: ${response.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
"""
        with open(output_path / "lib" / "services" / "mcn_client.dart", 'w') as f:
            f.write(client_code)
            
    def _generate_ui_components(self, output_path: Path):
        """Generate custom styled widgets representing MCN design tokens"""
        widgets_code = """import 'package:flutter/material.dart';

class UIButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final String className;

  const UIButton({
    super.key,
    required this.text,
    this.onPressed,
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.blue.shade600,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          elevation: 2,
        ),
        onPressed: onPressed,
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }
}

class UIInput extends StatelessWidget {
  final String placeholder;
  final ValueChanged<String>? onChanged;
  final String className;

  const UIInput({
    super.key,
    this.placeholder = '',
    this.onChanged,
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: TextField(
        decoration: InputDecoration(
          hintText: placeholder,
          filled: true,
          fillColor: Colors.grey.shade100,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: BorderSide(color: Colors.grey.shade300),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: BorderSide(color: Colors.grey.shade200),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        onChanged: onChanged,
      ),
    );
  }
}

class UIText extends StatelessWidget {
  final String content;
  final String tag;
  final String className;

  const UIText({
    super.key,
    required this.content,
    this.tag = 'p',
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    TextStyle style = const TextStyle(fontSize: 16, color: Colors.black87);
    if (tag == 'h1') {
      style = const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.black);
    } else if (tag == 'h2') {
      style = const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.black87);
    } else if (tag == 'h3') {
      style = const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.blueGrey);
    }
    
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Text(content, style: style),
    );
  }
}

class UIContainer extends StatelessWidget {
  final List<Widget> children;
  final String className;

  const UIContainer({
    super.key,
    required this.children,
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    bool isRow = className.contains('row') || className.contains('header');
    
    if (isRow) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: children,
      );
    }
    
    return Padding(
      padding: const EdgeInsets.all(12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    );
  }
}

class UITable extends StatelessWidget {
  final List<String> columns;
  final List<dynamic> data;
  final String className;

  const UITable({
    super.key,
    required this.columns,
    required this.data,
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    if (data.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16.0),
          child: Text('No data available', style: TextStyle(color: Colors.grey)),
        ),
      );
    }
    
    return Card(
      elevation: 1,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          columns: columns.map((col) => DataColumn(
            label: Text(col, style: const TextStyle(fontWeight: FontWeight.bold)),
          )).toList(),
          rows: data.map((row) {
            return DataRow(
              cells: columns.map((col) {
                final cellValue = row[col.toLowerCase()] ?? row[col] ?? '-';
                return DataCell(Text(cellValue.toString()));
              }).toList(),
            );
          }).toList(),
        ),
      ),
    );
  }
}

class UIChart extends StatelessWidget {
  final String type;
  final List<dynamic> data;
  final String className;

  const UIChart({
    super.key,
    required this.type,
    required this.data,
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 12.0),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Chart: ${type.toUpperCase()}', style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Container(
              height: 200,
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Center(
                child: Text('Dynamic Data Points: ${data.length}', style: const TextStyle(color: Colors.blueAccent)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class UIAgentChat extends StatelessWidget {
  final String agentName;
  final String className;
  
  const UIAgentChat({
    super.key,
    this.agentName = 'Agent',
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: const Color(0xFF1E293B),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Chat with $agentName', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20, color: Colors.blueAccent)),
            const SizedBox(height: 12),
            Container(
              height: 250,
              decoration: BoxDecoration(
                color: const Color(0xFF0F172A),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: 'Type your message...',
                      hintStyle: const TextStyle(color: Colors.white54),
                      filled: true,
                      fillColor: const Color(0xFF1E293B),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.blueAccent, padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20)),
                  child: const Text('Send', style: TextStyle(color: Colors.white)),
                ),
              ],
            )
          ],
        ),
      ),
    );
  }
}

class UIEnterpriseSearch extends StatelessWidget {
  final String datasourceName;
  final String className;

  const UIEnterpriseSearch({
    super.key,
    this.datasourceName = 'Knowledge Base',
    this.className = '',
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: const Color(0xFF1E293B),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Search $datasourceName', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20, color: Colors.indigoAccent)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: 'Search enterprise data...',
                      hintStyle: const TextStyle(color: Colors.white54),
                      filled: true,
                      fillColor: const Color(0xFF1E293B),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.indigoAccent, padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20)),
                  child: const Text('Search', style: TextStyle(color: Colors.white)),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              height: 150,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF0F172A),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text('Enter a query to search across connected data sources.', style: TextStyle(color: Colors.white54, fontStyle: FontStyle.italic)),
            ),
          ],
        ),
      ),
    );
  }
}
"""
        with open(output_path / "lib" / "widgets" / "ui_components.dart", 'w') as f:
            f.write(widgets_code)
            
    def _generate_pages(self, output_path: Path, manifest: Dict):
        """Generate Flutter Page widgets"""
        for page_name, page_data in manifest.get('pages', {}).items():
            self._generate_page_widget(output_path, page_name, page_data)
            
    def _generate_page_widget(self, output_path: Path, page_name: str, page_data: Dict):
        """Generate individual Page Widget as a StatefulWidget to handle page state"""
        
        content_code = self._generate_page_content_dart(page_data)
        
        page_code = f"""import 'package:flutter/material.dart';
import '../services/mcn_client.dart';
import '../widgets/ui_components.dart';

class {page_name}Page extends StatefulWidget {{
  const {page_name}Page({{super.key}});

  @override
  State<{page_name}Page> createState() => _{page_name}PageState();
}}

class _{page_name}PageState extends State<{page_name}Page> {{
  final MCNClient _mcn = MCNClient();
  Map<String, dynamic> _data = {{}};
  bool _loading = true;
  String? _error;

  @override
  void initState() {{
    super.initState();
    _loadPageData();
  }}

  Future<void> _loadPageData() async {{
    setState(() {{
      _loading = true;
      _error = null;
    }});
    
    try {{
      final result = await _mcn.call('load_page_data', {{'page': '{page_name}'}});
      if (result['success'] == true && result['data'] != null) {{
        setState(() {{
          _data = Map<String, dynamic>.from(result['data']);
          _loading = false;
        }});
      }} else {{
        setState(() {{
          _error = result['error'] ?? 'Failed to load page data';
          _loading = false;
        }});
      }}
    }} catch (e) {{
      setState(() {{
        _error = e.toString();
        _loading = false;
      }});
    }}
  }}

  @override
  Widget build(BuildContext context) {{
    if (_loading) {{
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }}

    if (_error != null) {{
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: Colors.red, size: 60),
                const SizedBox(height: 16),
                Text('Error: $_error', textAlign: TextAlign.center),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _loadPageData,
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }}

    return Scaffold(
      appBar: AppBar(
        title: const Text('{page_name}'),
        elevation: 1,
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            {content_code}
          ],
        ),
      ),
    );
  }}
}}
"""
        with open(output_path / "lib" / "pages" / f"{page_name}Page.dart", 'w') as f:
            f.write(page_code)
            
    def _generate_page_content_dart(self, page_data: Dict) -> str:
        """Translate MCN components in page layout to Dart code"""
        components = page_data.get('components', [])
        
        widgets = []
        for component in components:
            widgets.append(self._component_to_dart(component))
            
        return ",\n            ".join(widgets)
        
    def _component_to_dart(self, component: Any) -> str:
        """Recursively build Dart widget representation from component JSON"""
        if isinstance(component, str):
            if component in self.components:
                component = self.components[component]
            else:
                return "const SizedBox.shrink()"
                
        comp_type = component.get('type', 'container')
        props = component.get('props', {})
        events = component.get('events', {})
        
        if comp_type == 'button':
            onclick_fn = ""
            if 'onClick' in events:
                onclick_fn = f"""onPressed: () async {{
                  await _mcn.call('{events['onClick']}', {{}});
                  _loadPageData();
                }},"""
            else:
                onclick_fn = "onPressed: () {},"
                
            return f"""UIButton(
              text: "{props.get('text', 'Button')}",
              className: "{props.get('className', 'btn')}",
              {onclick_fn}
            )"""
            
        elif comp_type == 'input':
            onchange_fn = ""
            if 'onChange' in events:
                onchange_fn = f"""onChanged: (val) async {{
                  await _mcn.call('{events['onChange']}', {{'value': val}});
                }},"""
            return f"""UIInput(
              placeholder: "{props.get('placeholder', '')}",
              className: "{props.get('className', 'input')}",
              {onchange_fn}
            )"""
            
        elif comp_type == 'text':
            return f"""UIText(
              content: "{props.get('content', '')}",
              tag: "{props.get('tag', 'p')}",
              className: "{props.get('className', 'text')}",
            )"""
            
        elif comp_type == 'container':
            children_dart = []
            for child in component.get('children', []):
                children_dart.append(self._component_to_dart(child))
            
            children_str = ",\n".join(children_dart)
            return f"""UIContainer(
              className: "{props.get('className', 'container')}",
              children: [
                {children_str}
              ],
            )"""
            
        elif comp_type == 'table':
            columns = props.get('columns', [])
            cols_str = ", ".join([f'"{col}"' for col in columns])
            data_source = props.get('dataSource', 'tableData')
            return f"""UITable(
              columns: [{cols_str}],
              data: _data['{data_source}'] ?? [],
              className: "{props.get('className', 'table')}",
            )"""
            
        elif comp_type == 'chart':
            data_source = props.get('data', 'chartData')
            return f"""UIChart(
              type: "{props.get('chartType', 'line')}",
              data: _data['{data_source}'] ?? [],
              className: "{props.get('className', 'chart')}",
            )"""
            
        elif comp_type == 'agent_chat':
            return f"""UIAgentChat(
              agentName: "{props.get('agentName', 'Agent')}",
              className: "{props.get('className', 'agent-chat')}",
            )"""
            
        elif comp_type == 'enterprise_search':
            return f"""UIEnterpriseSearch(
              datasourceName: "{props.get('datasourceName', 'Knowledge Base')}",
              className: "{props.get('className', 'enterprise-search')}",
            )"""
            
        return "const SizedBox.shrink()"
        
    def _generate_main_dart(self, output_path: Path, manifest: Dict):
        """Generate MaterialApp, router, and initialize routing configurations"""
        pages = manifest.get('pages', {})
        
        imports = []
        routes = []
        first_page = None
        
        for name, page in pages.items():
            imports.append(f"import 'pages/{name}Page.dart';")
            routes.append(f"'/': (context) => const {name}Page()," if first_page is None else f"'{page.get('path', '/')}': (context) => const {name}Page(),")
            if first_page is None:
                first_page = name
                
        main_code = f"""import 'package:flutter/material.dart';
{chr(10).join(imports)}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: 'MCN Mobile App',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      initialRoute: '/',
      routes: {{
        {chr(10).join(routes)}
      }},
    );
  }}
}}
"""
        with open(output_path / "lib" / "main.dart", 'w') as f:
            f.write(main_code)
