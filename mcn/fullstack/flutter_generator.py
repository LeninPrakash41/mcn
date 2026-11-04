"""
Flutter Project Generator for MCN UI Integration
Generates complete Flutter projects from MCN UI definitions
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple


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
  sdk: '>=3.6.2 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0
  google_fonts: ^6.2.1
  fl_chart: ^1.3.0
  lucide_icons_flutter: ^3.1.25

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

  // Set with --dart-define=MCN_API_URL=... (Android emulator: http://10.0.2.2:8080)
  String baseUrl = const String.fromEnvironment('MCN_API_URL', defaultValue: 'http://localhost:8080');

  // Bearer token for services declared with `auth`: --dart-define=MCN_API_TOKEN=...
  // or set it after login.
  String token = const String.fromEnvironment('MCN_API_TOKEN');

  // MCN services expose each endpoint as POST /<endpoint_name> with a JSON body
  Future<Map<String, dynamic>> call(String action, Map<String, dynamic> payload) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/$action'),
        headers: {
          'Content-Type': 'application/json',
          if (token.isNotEmpty) 'Authorization': 'Bearer $token',
        },
        body: json.encode(payload),
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
        widgets_code = """import 'dart:math' as math;
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

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
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: FilledButton(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        onPressed: onPressed,
        child: Text(text, style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
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
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: TextField(
        decoration: InputDecoration(
          hintText: placeholder,
          filled: true,
          fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.6)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.primary, width: 1.5),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        style: GoogleFonts.inter(),
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
    TextStyle style = GoogleFonts.inter(fontSize: 15, height: 1.4);
    if (tag == 'h1') {
      style = GoogleFonts.inter(fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: -0.5);
    } else if (tag == 'h2') {
      style = GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.w600, letterSpacing: -0.3);
    } else if (tag == 'h3') {
      style = GoogleFonts.inter(fontSize: 17, fontWeight: FontWeight.w600);
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
    final bool isRow = className.contains('row') || className.contains('header');
    if (isRow) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: children,
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
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
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: const Padding(
          padding: EdgeInsets.all(24.0),
          child: Center(
            child: Text('No data available', style: TextStyle(color: Colors.grey)),
          ),
        ),
      );
    }
    
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            columns: columns.map((col) => DataColumn(
              label: Text(col, style: GoogleFonts.inter(fontWeight: FontWeight.w700)),
            )).toList(),
            rows: data.map((row) {
              return DataRow(
                cells: columns.map((col) {
                  final cellValue = row is Map ? (row[col.toLowerCase()] ?? row[col] ?? '-') : '-';
                  return DataCell(Text(cellValue.toString(), style: GoogleFonts.inter()));
                }).toList(),
              );
            }).toList(),
          ),
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
    final scheme = Theme.of(context).colorScheme;
    const palette = [Color(0xFF4F46E5), Color(0xFF06B6D4), Color(0xFF10B981), Color(0xFFF59E0B)];
    final isBar = type == 'bar';
    final isPie = type == 'pie' || type == 'donut';

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${type.toUpperCase()} CHART',
              style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700, color: scheme.primary, letterSpacing: 0.5),
            ),
            const SizedBox(height: 14),
            SizedBox(
              height: 220,
              child: data.isEmpty
                  ? Center(child: Text('No data points', style: GoogleFonts.inter(color: scheme.onSurfaceVariant)))
                  : (isPie
                      ? PieChart(PieChartData(
                          sectionsSpace: 3,
                          sections: [
                            for (var i = 0; i < data.length; i++)
                              PieChartSectionData(
                                value: _toNum(data[i]),
                                color: palette[i % palette.length],
                                radius: 50,
                                title: '${_toNum(data[i]).round()}',
                                titleStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
                              ),
                          ],
                        ))
                      : isBar
                          ? BarChart(BarChartData(
                              titlesData: const FlTitlesData(
                                topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                                rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                              ),
                              borderData: FlBorderData(show: false),
                              barGroups: [
                                for (var i = 0; i < data.length; i++)
                                  BarChartGroupData(x: i, barRods: [
                                    BarChartRodData(
                                      toY: _toNum(data[i]),
                                      color: palette[i % palette.length],
                                      width: 14,
                                      borderRadius: const BorderRadius.vertical(top: Radius.circular(5)),
                                    ),
                                  ]),
                              ],
                            ))
                          : LineChart(LineChartData(
                              titlesData: const FlTitlesData(
                                topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                                rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                              ),
                              borderData: FlBorderData(show: false),
                              lineBarsData: [
                                LineChartBarData(
                                  spots: [
                                    for (var i = 0; i < data.length; i++)
                                      FlSpot(i.toDouble(), _toNum(data[i])),
                                  ],
                                  isCurved: true,
                                  color: palette[0],
                                  barWidth: 3,
                                  belowBarData: BarAreaData(
                                    show: true,
                                    color: palette[0].withValues(alpha: 0.15),
                                  ),
                                ),
                              ],
                            ))),
            ),
          ],
        ),
      ),
    );
  }

  double _toNum(dynamic v) {
    if (v is num) return v.toDouble();
    if (v is Map) {
      for (final key in ['value', 'amount', 'count', 'y']) {
        if (v[key] is num) return (v[key] as num).toDouble();
      }
    }
    return 10.0;
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
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Chat with $agentName', style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 18)),
            const SizedBox(height: 12),
            Container(
              height: 200,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(child: Text('Messages appear here', style: GoogleFonts.inter(color: Colors.grey))),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: 'Type your message...',
                      filled: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    style: GoogleFonts.inter(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () {},
                  child: const Text('Send'),
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
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Search $datasourceName', style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 18)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: 'Search enterprise data...',
                      filled: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    style: GoogleFonts.inter(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () {},
                  child: const Text('Search'),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Container(
              height: 120,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text('Enter a query to search across connected data sources.',
                    style: GoogleFonts.inter(color: Colors.grey, fontStyle: FontStyle.italic)),
              ),
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
            
    def _sanitize_names(self, name: str) -> Tuple[str, str]:
        import re
        words = re.sub(r'[^a-zA-Z0-9_]', ' ', name).split()
        if not words:
            words = ['Home']
        class_name = "".join(w.capitalize() for w in words) + "Page"
        file_name = "_".join(w.lower() for w in words) + "_page.dart"
        return class_name, file_name

    def _generate_page_widget(self, output_path: Path, page_name: str, page_data: Dict):
        """Generate individual Page Widget as a StatefulWidget to handle page state"""
        class_name, file_name = self._sanitize_names(page_name)
        content_code = self._generate_page_content_dart(page_data)
        
        page_code = f"""import 'package:flutter/material.dart';
import '../services/mcn_client.dart';
import '../widgets/ui_components.dart';

class {class_name} extends StatefulWidget {{
  const {class_name}({{super.key}});

  @override
  State<{class_name}> createState() => _{class_name}State();
}}

class _{class_name}State extends State<{class_name}> {{
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
        with open(output_path / "lib" / "pages" / file_name, 'w') as f:
            f.write(page_code)
            
    def _generate_page_content_dart(self, page_data: Dict) -> str:
        """Translate MCN components in page layout to Dart code"""
        components = page_data.get('components', [])
        
        widgets = []
        for component in components:
            widgets.append(self._component_to_dart(component))
            
        return ",\n            ".join(widgets)
        
    @staticmethod
    def _dart_escape(value: Any) -> str:
        """Escape a value for use inside a double-quoted Dart string literal"""
        return (str(value).replace('\\', '\\\\').replace('"', '\\"')
                .replace('$', '\\$').replace('\n', '\\n').replace('\r', '\\r'))

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
              text: "{self._dart_escape(props.get('text', 'Button'))}",
              className: "{self._dart_escape(props.get('className', 'btn'))}",
              {onclick_fn}
            )"""
            
        elif comp_type == 'input':
            onchange_fn = ""
            if 'onChange' in events:
                onchange_fn = f"""onChanged: (val) async {{
                  await _mcn.call('{events['onChange']}', {{'value': val}});
                }},"""
            return f"""UIInput(
              placeholder: "{self._dart_escape(props.get('placeholder', ''))}",
              className: "{self._dart_escape(props.get('className', 'input'))}",
              {onchange_fn}
            )"""
            
        elif comp_type == 'text':
            return f"""UIText(
              content: "{self._dart_escape(props.get('content', ''))}",
              tag: "{self._dart_escape(props.get('tag', 'p'))}",
              className: "{self._dart_escape(props.get('className', 'text'))}",
            )"""
            
        elif comp_type == 'container':
            children_dart = []
            for child in component.get('children', []):
                children_dart.append(self._component_to_dart(child))
            
            children_str = ",\n".join(children_dart)
            return f"""UIContainer(
              className: "{self._dart_escape(props.get('className', 'container'))}",
              children: [
                {children_str}
              ],
            )"""
            
        elif comp_type == 'table':
            columns = props.get('columns', [])
            cols_str = ", ".join([f'"{self._dart_escape(col)}"' for col in columns])
            data_source = props.get('dataSource', 'tableData')
            return f"""UITable(
              columns: [{cols_str}],
              data: _data['{data_source}'] ?? [],
              className: "{self._dart_escape(props.get('className', 'table'))}",
            )"""
            
        elif comp_type == 'chart':
            data_source = props.get('data', 'chartData')
            return f"""UIChart(
              type: "{self._dart_escape(props.get('chartType', 'line'))}",
              data: _data['{data_source}'] ?? [],
              className: "{self._dart_escape(props.get('className', 'chart'))}",
            )"""
            
        elif comp_type == 'agent_chat':
            return f"""UIAgentChat(
              agentName: "{self._dart_escape(props.get('agentName', 'Agent'))}",
              className: "{self._dart_escape(props.get('className', 'agent-chat'))}",
            )"""
            
        elif comp_type == 'enterprise_search':
            return f"""UIEnterpriseSearch(
              datasourceName: "{self._dart_escape(props.get('datasourceName', 'Knowledge Base'))}",
              className: "{self._dart_escape(props.get('className', 'enterprise-search'))}",
            )"""
            
        return "const SizedBox.shrink()"
        
    def _generate_main_dart(self, output_path: Path, manifest: Dict):
        """Generate MaterialApp, router, and initialize routing configurations"""
        pages = manifest.get('pages', {})
        
        imports = []
        routes = []
        first_page_class = None
        
        for name, page in pages.items():
            class_name, file_name = self._sanitize_names(name)
            imports.append(f"import 'pages/{file_name}';")
            routes.append(f"'/': (context) => const {class_name}()," if first_page_class is None else f"'{page.get('path', '/' + file_name.replace('_page.dart', ''))}': (context) => const {class_name}(),")
            if first_page_class is None:
                first_page_class = class_name
                
        main_code = f"""import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
{chr(10).join(imports)}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    final baseTheme = ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2563EB)),
      useMaterial3: true,
    );
    return MaterialApp(
      title: 'MCN Mobile App',
      debugShowCheckedModeBanner: false,
      theme: baseTheme.copyWith(
        textTheme: GoogleFonts.interTextTheme(baseTheme.textTheme),
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
