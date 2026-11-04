// MCN runtime for Flutter apps compiled from MCN components (do not edit:
// regenerated on every build). Value helpers give MCN semantics (null-safe
// property access, + for text and numbers, truthiness); the widgets are the
// mobile counterparts of the MCN UI kit.
import 'dart:math' as math;
import 'package:flutter/material.dart';

// ── Values ───────────────────────────────────────────────────────────────────

dynamic mcnGet(dynamic obj, String key) {
  if (obj is Map) return obj[key];
  if (key == 'length' && (obj is List || obj is String)) return obj.length;
  return null;
}

dynamic mcnIndex(dynamic obj, dynamic i) {
  if (obj is List && i is int) return (i >= 0 && i < obj.length) ? obj[i] : null;
  if (obj is Map) return obj[i is String ? i : '$i'];
  return null;
}

bool mcnTruthy(dynamic v) => !(v == null || v == false || v == 0 || v == '');

num mcnNum(dynamic v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v) ?? 0;
  if (v is bool) return v ? 1 : 0;
  return 0;
}

String mcnStr(dynamic v) {
  if (v == null) return '';
  if (v is double && v == v.roundToDouble() && v.abs() < 1e15) return v.toInt().toString();
  return v.toString();
}

dynamic mcnAdd(dynamic a, dynamic b) {
  if (a is String || b is String) return mcnStr(a) + mcnStr(b);
  if (a is List && b is List) return [...a, ...b];
  return mcnNum(a) + mcnNum(b);
}

int mcnLen(dynamic v) => (v is List || v is String || v is Map) ? v.length : 0;

bool mcnContains(dynamic hay, dynamic needle) {
  if (hay is String) return hay.contains(mcnStr(needle));
  if (hay is List) return hay.contains(needle);
  if (hay is Map) return hay.containsKey(needle);
  return false;
}

dynamic mcnRound(dynamic v, [dynamic digits = 0]) {
  final d = mcnNum(digits).toInt();
  final f = math.pow(10, d);
  final r = (mcnNum(v) * f).round() / f;
  return d == 0 ? r.toInt() : r;
}

/// Display text for a value: 35136 → "35,136", true → "Yes".
String mcnFormat(dynamic v) {
  if (v == null || v == '') return '—';
  if (v is bool) return v ? 'Yes' : 'No';
  if (v is num) {
    final whole = v is int || v == v.roundToDouble();
    final s = whole ? v.toInt().abs().toString() : v.abs().toStringAsFixed(2);
    final parts = s.split('.');
    final digits = parts[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    return '${v < 0 ? '-' : ''}$digits${parts.length > 1 ? '.${parts[1]}' : ''}';
  }
  return v.toString();
}

String mcnHumanize(String key) {
  final s = key.replaceAll(RegExp(r'[_-]+'), ' ').trim();
  return s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}

List<dynamic> mcnList(dynamic v) => v is List ? v : const [];

// ── Notifications ────────────────────────────────────────────────────────────

void mcnNotify(BuildContext context, dynamic message, [dynamic kind = 'info']) {
  final colors = {'success': Colors.green.shade700, 'error': Colors.red.shade700, 'warning': Colors.orange.shade800};
  ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(
    content: Text(mcnStr(message)),
    backgroundColor: colors[mcnStr(kind)],
    behavior: SnackBarBehavior.floating,
  ));
}

// ── Icons ────────────────────────────────────────────────────────────────────

const Map<String, IconData> _icons = {
  'layoutdashboard': Icons.dashboard_outlined, 'home': Icons.home_outlined, 'users': Icons.people_outline,
  'user': Icons.person_outline, 'trendingup': Icons.trending_up, 'dollarsign': Icons.attach_money,
  'shoppingcart': Icons.shopping_cart_outlined, 'alerttriangle': Icons.warning_amber_outlined, 'bot': Icons.smart_toy_outlined,
  'messagesquare': Icons.chat_bubble_outline, 'messagecircle': Icons.chat_bubble_outline, 'history': Icons.history,
  'mail': Icons.mail_outline, 'workflow': Icons.account_tree_outlined, 'kanban': Icons.view_kanban_outlined,
  'calendar': Icons.calendar_today_outlined, 'building2': Icons.business_outlined, 'building': Icons.business_outlined,
  'settings': Icons.settings_outlined, 'checkcircle': Icons.check_circle_outline, 'play': Icons.play_arrow_outlined,
  'listtodo': Icons.checklist, 'checksquare': Icons.check_box_outlined, 'target': Icons.track_changes, 'package': Icons.inventory_2_outlined,
  'filetext': Icons.description_outlined, 'receipt': Icons.receipt_long_outlined, 'barchart3': Icons.bar_chart, 'linechart': Icons.show_chart,
  'piechart': Icons.pie_chart_outline, 'gauge': Icons.speed, 'sparkles': Icons.auto_awesome, 'plug': Icons.power_outlined,
  'wrench': Icons.build_outlined, 'bell': Icons.notifications_none, 'search': Icons.search, 'inbox': Icons.inbox_outlined,
  'folderopen': Icons.folder_open_outlined, 'rocket': Icons.rocket_launch_outlined, 'database': Icons.storage, 'globe': Icons.public,
  'clock': Icons.schedule, 'star': Icons.star_border, 'heart': Icons.favorite_border, 'thermometer': Icons.thermostat, 'lightbulb': Icons.lightbulb_outline,
  'droplets': Icons.water_drop_outlined, 'dooropen': Icons.door_front_door_outlined, 'doorclosed': Icons.door_front_door_outlined,
  'house': Icons.home_outlined, 'cpu': Icons.memory, 'microchip': Icons.memory, 'fan': Icons.mode_fan_off_outlined,
  'activity': Icons.monitor_heart_outlined, 'radio': Icons.sensors, 'signal': Icons.signal_cellular_alt, 'wifi': Icons.wifi,
  'power': Icons.power_settings_new, 'zap': Icons.bolt, 'battery': Icons.battery_std, 'batterycharging': Icons.battery_charging_full,
  'bluetooth': Icons.bluetooth, 'cloudrain': Icons.water, 'wind': Icons.air, 'flame': Icons.local_fire_department_outlined,
  'leaf': Icons.eco_outlined, 'sprout': Icons.grass, 'waves': Icons.waves, 'lamp': Icons.light_outlined, 'blinds': Icons.blinds,
  'cctv': Icons.videocam_outlined, 'router': Icons.router_outlined, 'siren': Icons.campaign_outlined, 'vibrate': Icons.vibration,
  'flaskconical': Icons.science_outlined, 'brain': Icons.psychology_outlined, 'tags': Icons.sell_outlined, 'tag': Icons.label_outline,
  'clipboardcheck': Icons.assignment_turned_in_outlined, 'highlighter': Icons.highlight, 'scantext': Icons.document_scanner_outlined,
  'sigma': Icons.functions, 'dices': Icons.casino_outlined, 'trendingdown': Icons.trending_down,
};

IconData mcnIcon(dynamic name) => _icons[mcnStr(name).toLowerCase().replaceAll(RegExp(r'[-_ ]'), '')] ?? Icons.circle_outlined;

const List<Color> mcnPalette = [Color(0xFF6366F1), Color(0xFF06B6D4), Color(0xFFF59E0B), Color(0xFF10B981), Color(0xFFEC4899), Color(0xFF8B5CF6)];

Color mcnTone(dynamic name) => const {
      'green': Color(0xFF16A34A), 'red': Color(0xFFDC2626), 'blue': Color(0xFF2563EB),
      'amber': Color(0xFFD97706), 'purple': Color(0xFF9333EA),
    }[mcnStr(name)] ?? const Color(0xFF6366F1);

// ── App shell ────────────────────────────────────────────────────────────────

class MCNSection {
  final String label;
  final String icon;
  final Widget Function() build;
  const MCNSection(this.label, this.icon, this.build);
}

/// Bottom navigation for up to five sections, a drawer for more.
class MCNApp extends StatefulWidget {
  final String title;
  final List<MCNSection> sections;
  const MCNApp({super.key, required this.title, required this.sections});
  @override
  State<MCNApp> createState() => _MCNAppState();
}

class _MCNAppState extends State<MCNApp> {
  int _index = 0;
  @override
  Widget build(BuildContext context) {
    final sections = widget.sections;
    final useBar = sections.length > 1 && sections.length <= 5;
    return MaterialApp(
      title: widget.title,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: const Color(0xFF4F46E5), useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: const Color(0xFF4F46E5), useMaterial3: true, brightness: Brightness.dark),
      home: Builder(builder: (context) => Scaffold(
        appBar: AppBar(title: Text(sections.length > 1 ? sections[_index].label : widget.title)),
        drawer: useBar || sections.length < 2 ? null : Drawer(
          child: ListView(children: [
            DrawerHeader(child: Align(alignment: Alignment.bottomLeft,
                child: Text(widget.title, style: Theme.of(context).textTheme.titleLarge))),
            for (var i = 0; i < sections.length; i++)
              ListTile(
                leading: Icon(mcnIcon(sections[i].icon)), title: Text(sections[i].label), selected: i == _index,
                onTap: () { setState(() => _index = i); Navigator.pop(context); },
              ),
          ]),
        ),
        body: sections.isEmpty ? const SizedBox.shrink() : KeyedSubtree(key: ValueKey(_index), child: sections[_index].build()),
        bottomNavigationBar: useBar ? NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (i) => setState(() => _index = i),
          destinations: [for (final s in sections) NavigationDestination(icon: Icon(mcnIcon(s.icon)), label: s.label)],
        ) : null,
      )),
    );
  }
}

// ── Layout ───────────────────────────────────────────────────────────────────

/// grid_cols=N: N columns on wide screens, two on tablets, one on phones.
class MCNGrid extends StatelessWidget {
  final int columns;
  final List<Widget> children;
  const MCNGrid({super.key, required this.columns, required this.children});
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        final n = c.maxWidth > 900 ? columns : (c.maxWidth > 560 ? math.min(2, columns) : (columns >= 4 ? 2 : 1));
        final w = (c.maxWidth - 12 * (n - 1)) / n;
        return Wrap(spacing: 12, runSpacing: 12, children: [for (final child in children) SizedBox(width: w, child: child)]);
      });
}

class MCNCard extends StatelessWidget {
  final String? title;
  final List<Widget> children;
  const MCNCard({super.key, this.title, required this.children});
  @override
  Widget build(BuildContext context) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (title != null) Padding(padding: const EdgeInsets.only(bottom: 12),
                child: Text(title!, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600))),
            ...children,
          ]),
        ),
      );
}

class MCNStat extends StatelessWidget {
  final dynamic label, value, icon, color, unit;
  const MCNStat({super.key, this.label, this.value, this.icon, this.color, this.unit});
  @override
  Widget build(BuildContext context) {
    final tone = mcnTone(color);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(mcnStr(label), style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            Text('${mcnFormat(value)}${mcnStr(unit)}', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          ])),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: tone.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
            child: Icon(mcnIcon(icon), color: tone, size: 20),
          ),
        ]),
      ),
    );
  }
}

class MCNEmpty extends StatelessWidget {
  final dynamic title, description, icon;
  const MCNEmpty({super.key, this.title, this.description, this.icon});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Column(children: [
          Icon(mcnIcon(icon ?? 'inbox'), size: 36, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 8),
          Text(mcnStr(title), style: Theme.of(context).textTheme.titleSmall),
          if (description != null) Text(mcnStr(description), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
        ]),
      );
}

/// A screen that only exists in the web app (agent and workflow builders).
class MCNWebOnly extends StatelessWidget {
  final String name;
  const MCNWebOnly(this.name, {super.key});
  @override
  Widget build(BuildContext context) => MCNEmpty(title: '$name is available in the web app', icon: 'monitor',
      description: 'Open this app in a browser to use the $name.');
}

class MCNBadge extends StatelessWidget {
  final dynamic value;
  const MCNBadge(this.value, {super.key});
  @override
  Widget build(BuildContext context) {
    final text = mcnStr(value);
    final good = {'paid', 'active', 'done', 'won', 'success', 'completed', 'approved'}.contains(text.toLowerCase());
    final bad = {'overdue', 'failed', 'lost', 'cancelled', 'rejected', 'high', 'urgent'}.contains(text.toLowerCase());
    final color = good ? Colors.green : bad ? Colors.red : Colors.indigo;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(text, style: TextStyle(fontSize: 12, color: color.shade700, fontWeight: FontWeight.w500)),
    );
  }
}

// ── Data ─────────────────────────────────────────────────────────────────────

/// Mobile data_table: search, filter chips and a card per record.
class MCNDataList extends StatefulWidget {
  final dynamic data;
  final List<dynamic> columns;
  final List<dynamic> filters;
  final String? title;
  final String? titleKey;
  final int pageSize;
  final Future<void> Function(dynamic row)? onDelete;
  final void Function(dynamic row)? onTap;
  final String? empty;
  const MCNDataList({super.key, this.data, this.columns = const [], this.filters = const [], this.title, this.titleKey,
      this.pageSize = 20, this.onDelete, this.onTap, this.empty});
  @override
  State<MCNDataList> createState() => _MCNDataListState();
}

class _MCNDataListState extends State<MCNDataList> {
  String _query = '';
  final Map<String, String?> _filter = {};
  int _shown = 0;

  @override
  Widget build(BuildContext context) {
    final rows = mcnList(widget.data);
    final cols = widget.columns.isNotEmpty ? widget.columns.map(mcnStr).toList()
        : (rows.isNotEmpty && rows.first is Map ? (rows.first as Map).keys.map(mcnStr).where((k) => k != 'id').take(5).toList() : <String>[]);
    final titleKey = widget.titleKey ?? (cols.isNotEmpty ? cols.first : 'title');
    final q = _query.toLowerCase();
    final filtered = rows.where((r) =>
        (q.isEmpty || cols.any((c) => mcnStr(mcnGet(r, c)).toLowerCase().contains(q))) &&
        _filter.entries.every((f) => f.value == null || mcnStr(mcnGet(r, f.key)) == f.value)).toList();
    final limit = _shown == 0 ? widget.pageSize : _shown;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (widget.title != null) Padding(padding: const EdgeInsets.only(bottom: 8),
          child: Text(widget.title!, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600))),
      TextField(
        decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search…', border: OutlineInputBorder(), isDense: true),
        onChanged: (v) => setState(() => _query = v),
      ),
      for (final key in widget.filters.map(mcnStr))
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.only(top: 8),
          child: Row(children: [
            Padding(padding: const EdgeInsets.only(right: 6), child: ChoiceChip(label: Text('All ${mcnHumanize(key).toLowerCase()}'),
                selected: _filter[key] == null, onSelected: (_) => setState(() => _filter[key] = null))),
            for (final v in rows.map((r) => mcnStr(mcnGet(r, key))).where((v) => v.isNotEmpty).toSet())
              Padding(padding: const EdgeInsets.only(right: 6), child: ChoiceChip(label: Text(v), selected: _filter[key] == v,
                  onSelected: (_) => setState(() => _filter[key] = v))),
          ]),
        ),
      const SizedBox(height: 8),
      if (filtered.isEmpty) MCNEmpty(title: rows.isEmpty ? (widget.empty ?? 'Nothing here yet') : 'No matches', icon: rows.isEmpty ? 'inbox' : 'search'),
      for (final r in filtered.take(limit))
        Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            onTap: widget.onTap == null ? null : () => widget.onTap!(r),
            title: Text(mcnFormat(mcnGet(r, titleKey)), style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
              for (final c in cols.where((c) => c != titleKey))
                RegExp(r'^(status|stage|priority|state|type)$').hasMatch(c)
                    ? MCNBadge(mcnGet(r, c))
                    : Text('${mcnHumanize(c)}: ${mcnFormat(mcnGet(r, c))}', style: Theme.of(context).textTheme.bodySmall),
            ]),
            trailing: widget.onDelete == null ? null : IconButton(
              icon: const Icon(Icons.delete_outline), tooltip: 'Delete',
              onPressed: () => widget.onDelete!(r),
            ),
          ),
        ),
      if (filtered.length > limit)
        Center(child: TextButton(onPressed: () => setState(() => _shown = limit + widget.pageSize),
            child: Text('Show more (${filtered.length - limit} left)'))),
    ]);
  }
}

/// Board with a column per value of groupBy; long-press a card to move it.
class MCNKanban extends StatefulWidget {
  final dynamic data;
  final String groupBy;
  final List<dynamic> columns;
  final String? titleKey;
  final Future<dynamic> Function(dynamic item, String to)? onMove;
  const MCNKanban({super.key, this.data, this.groupBy = 'status', this.columns = const [], this.titleKey, this.onMove});
  @override
  State<MCNKanban> createState() => _MCNKanbanState();
}

class _MCNKanbanState extends State<MCNKanban> {
  List<dynamic> _items = [];
  @override
  void initState() { super.initState(); _items = List.of(mcnList(widget.data)); }
  @override
  void didUpdateWidget(MCNKanban old) { super.didUpdateWidget(old); _items = List.of(mcnList(widget.data)); }

  @override
  Widget build(BuildContext context) {
    final cols = widget.columns.isNotEmpty ? widget.columns.map(mcnStr).toList()
        : _items.map((r) => mcnStr(mcnGet(r, widget.groupBy))).toSet().toList();
    final titleKey = widget.titleKey ?? 'title';
    return SizedBox(
      height: 420,
      child: ListView(scrollDirection: Axis.horizontal, children: [
        for (final col in cols)
          DragTarget<int>(
            onAcceptWithDetails: (d) async {
              final item = Map<String, dynamic>.from(_items[d.data] as Map)..[widget.groupBy] = col;
              setState(() => _items[d.data] = item);
              await widget.onMove?.call(item, col);
            },
            builder: (context, candidate, _) => Container(
              width: 260,
              margin: const EdgeInsets.only(right: 12),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: candidate.isNotEmpty ? Theme.of(context).colorScheme.primaryContainer : Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(col, style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Expanded(child: ListView(children: [
                  for (var i = 0; i < _items.length; i++)
                    if (mcnStr(mcnGet(_items[i], widget.groupBy)) == col)
                      LongPressDraggable<int>(
                        data: i,
                        feedback: SizedBox(width: 240, child: Card(child: ListTile(title: Text(mcnFormat(mcnGet(_items[i], titleKey)))))),
                        childWhenDragging: Opacity(opacity: 0.4, child: Card(child: ListTile(title: Text(mcnFormat(mcnGet(_items[i], titleKey)))))),
                        child: Card(child: ListTile(title: Text(mcnFormat(mcnGet(_items[i], titleKey))), trailing: const Icon(Icons.drag_indicator))),
                      ),
                ])),
              ]),
            ),
          ),
      ]),
    );
  }
}

// ── Charts ───────────────────────────────────────────────────────────────────

class MCNChart extends StatelessWidget {
  final String kind; // bar | line | area | pie | donut
  final dynamic data;
  final String x;
  final List<dynamic> y;
  final double height;
  const MCNChart({super.key, required this.kind, this.data, this.x = 'label', this.y = const ['value'], this.height = 220});
  @override
  Widget build(BuildContext context) {
    final rows = mcnList(data);
    if (rows.isEmpty) return SizedBox(height: height, child: const MCNEmpty(title: 'No data yet', icon: 'barchart3'));
    final keys = y.map(mcnStr).toList();
    return Column(children: [
      SizedBox(height: height, width: double.infinity,
          child: CustomPaint(painter: _ChartPainter(kind, rows, x, keys, Theme.of(context).colorScheme.outlineVariant))),
      if (kind == 'pie' || kind == 'donut' || keys.length > 1)
        Padding(padding: const EdgeInsets.only(top: 8), child: Wrap(spacing: 12, runSpacing: 4, children: [
          for (var i = 0; i < (kind == 'pie' || kind == 'donut' ? rows.length : keys.length); i++)
            Row(mainAxisSize: MainAxisSize.min, children: [
              Container(width: 10, height: 10, decoration: BoxDecoration(color: mcnPalette[i % mcnPalette.length], borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 4),
              Text(kind == 'pie' || kind == 'donut' ? mcnStr(mcnGet(rows[i], x)) : mcnHumanize(keys[i]), style: Theme.of(context).textTheme.bodySmall),
            ]),
        ])),
    ]);
  }
}

class _ChartPainter extends CustomPainter {
  final String kind;
  final List<dynamic> rows;
  final String x;
  final List<String> keys;
  final Color grid;
  _ChartPainter(this.kind, this.rows, this.x, this.keys, this.grid);

  @override
  void paint(Canvas canvas, Size size) {
    if (kind == 'pie' || kind == 'donut') {
      final values = rows.map((r) => mcnNum(mcnGet(r, keys.first)).toDouble()).toList();
      final total = values.fold<double>(0, (a, b) => a + b);
      if (total <= 0) return;
      final r = math.min(size.width, size.height) / 2 - 4;
      final rect = Rect.fromCircle(center: size.center(Offset.zero), radius: r);
      var start = -math.pi / 2;
      for (var i = 0; i < values.length; i++) {
        final sweep = values[i] / total * math.pi * 2;
        canvas.drawArc(rect, start, sweep, kind == 'pie',
            Paint()..color = mcnPalette[i % mcnPalette.length]..style = kind == 'pie' ? PaintingStyle.fill : PaintingStyle.stroke
              ..strokeWidth = r * 0.38);
        start += sweep;
      }
      return;
    }
    final maxV = rows.expand((r) => keys.map((k) => mcnNum(mcnGet(r, k)).toDouble())).fold<double>(0, math.max);
    if (maxV <= 0) return;
    final gridPaint = Paint()..color = grid..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final gy = size.height - size.height * i / 4;
      canvas.drawLine(Offset(0, gy), Offset(size.width, gy), gridPaint);
    }
    final band = size.width / rows.length;
    for (var k = 0; k < keys.length; k++) {
      final color = mcnPalette[k % mcnPalette.length];
      if (kind == 'bar') {
        final w = band * 0.7 / keys.length;
        for (var i = 0; i < rows.length; i++) {
          final h = mcnNum(mcnGet(rows[i], keys[k])) / maxV * size.height;
          canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(band * i + band * 0.15 + w * k, size.height - h, w - 2, h), const Radius.circular(3)),
              Paint()..color = color);
        }
      } else {
        final path = Path();
        for (var i = 0; i < rows.length; i++) {
          final px = band * i + band / 2;
          final py = size.height - mcnNum(mcnGet(rows[i], keys[k])) / maxV * size.height;
          i == 0 ? path.moveTo(px, py) : path.lineTo(px, py);
        }
        if (kind == 'area') {
          final fill = Path.from(path)..lineTo(band * (rows.length - 1) + band / 2, size.height)..lineTo(band / 2, size.height)..close();
          canvas.drawPath(fill, Paint()..color = color.withValues(alpha: 0.15));
        }
        canvas.drawPath(path, Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 2.5);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) => old.rows != rows;
}

// ── Chat ─────────────────────────────────────────────────────────────────────

class MCNChat extends StatefulWidget {
  final String title;
  final String? welcome;
  final List<dynamic> suggestions;
  final Future<dynamic> Function(String message, List<Map<String, String>> history) onSend;
  const MCNChat({super.key, this.title = 'Assistant', this.welcome, this.suggestions = const [], required this.onSend});
  @override
  State<MCNChat> createState() => _MCNChatState();
}

class _MCNChatState extends State<MCNChat> {
  final List<Map<String, String>> _messages = [];
  final _input = TextEditingController();
  bool _busy = false;

  String _replyText(dynamic r) {
    if (r is String) return r;
    for (final k in ['reply', 'answer', 'message', 'response', 'text', 'data']) {
      final v = mcnGet(r, k);
      if (v != null) return _replyText(v);
    }
    return mcnStr(mcnGet(r, 'error') ?? r);
  }

  Future<void> _send(String text) async {
    final message = text.trim();
    if (message.isEmpty || _busy) return;
    final history = List<Map<String, String>>.of(_messages);
    setState(() { _messages.add({'role': 'user', 'content': message}); _busy = true; _input.clear(); });
    String reply;
    try { reply = _replyText(await widget.onSend(message, history)); } catch (e) { reply = 'Something went wrong: $e'; }
    if (!mounted) return;
    setState(() { _messages.add({'role': 'assistant', 'content': reply}); _busy = false; });
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final shown = [if (widget.welcome != null) {'role': 'assistant', 'content': widget.welcome!}, ..._messages];
    return MCNCard(title: widget.title, children: [
      SizedBox(
        height: 380,
        child: ListView(children: [
          for (final m in shown)
            Align(
              alignment: m['role'] == 'user' ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 4),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                constraints: const BoxConstraints(maxWidth: 300),
                decoration: BoxDecoration(color: m['role'] == 'user' ? scheme.primary : scheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(14)),
                child: Text(m['content'] ?? '', style: TextStyle(color: m['role'] == 'user' ? scheme.onPrimary : scheme.onSurface)),
              ),
            ),
          if (_busy) const Padding(padding: EdgeInsets.all(8), child: Text('Thinking…')),
        ]),
      ),
      if (_messages.isEmpty && widget.suggestions.isNotEmpty)
        Wrap(spacing: 6, children: [for (final s in widget.suggestions) ActionChip(label: Text(mcnStr(s)), onPressed: () => _send(mcnStr(s)))]),
      Row(children: [
        Expanded(child: TextField(controller: _input, decoration: const InputDecoration(hintText: 'Type a message…'), onSubmitted: _send)),
        IconButton(icon: const Icon(Icons.send), onPressed: _busy ? null : () => _send(_input.text)),
      ]),
    ]);
  }
}
