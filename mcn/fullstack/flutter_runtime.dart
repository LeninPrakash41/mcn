// MCN runtime for Flutter apps compiled from MCN components (do not edit:
// regenerated on every build). Value helpers give MCN semantics (null-safe
// property access, + for text and numbers, truthiness). The widgets are native
// Material 3, adapting to the platform: a bottom navigation bar on phones, a
// navigation rail on tablets, a page history per tab with back navigation,
// large collapsing titles, pull to refresh, swipe actions and haptics. Icons
// are the web kit's (Lucide) and charts use fl_chart.
import 'dart:math' as math;
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

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
  if (v is String) {
    final cleaned = v.replaceAll(RegExp(r'[\$,€,£,¥,\s,%]'), '').replaceAll(',', '');
    return num.tryParse(cleaned) ?? num.tryParse(v) ?? 0;
  }
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

/// A list to keep in a screen's state: the value if it's a list, else a new empty one.
List<dynamic> mcnListOf(dynamic v) => v is List ? v : <dynamic>[];

/// A map to keep in a screen's state: the value if it's an object, else a new empty one.
Map<String, dynamic> mcnMapOf(dynamic v) {
  if (v is Map<String, dynamic>) return v;
  if (v is Map) return v.map((k, value) => MapEntry('$k', value));
  return <String, dynamic>{};
}

/// A readable message from anything thrown while calling the backend.
String mcnErrorText(Object err) {
  final text = '$err';
  return text.startsWith('Exception: ') ? text.substring(11) : text;
}

// ── Theme, icons and colors ──────────────────────────────────────────────────

const Color _seed = Color(0xFF2563EB); // Vibrant modern primary blue

ThemeData mcnTheme(Brightness brightness, [Color? brand]) {
  final isDark = brightness == Brightness.dark;
  // A brand color is used as it is (Material would soften a seed color)
  final hsl = brand == null ? null : HSLColor.fromColor(brand);
  final brandPrimary = hsl == null ? null
      : isDark ? hsl.withLightness(hsl.lightness.clamp(0.6, 0.72)).toColor() : brand;
  final scheme = ColorScheme.fromSeed(
    seedColor: brand ?? _seed,
    primary: brandPrimary,
    onPrimary: brandPrimary == null ? null
        : (brandPrimary.computeLuminance() > 0.45 ? const Color(0xFF0F172A) : Colors.white),
    brightness: brightness,
    surface: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
  );
  final radius = BorderRadius.circular(18);

  final baseTheme = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    brightness: brightness,
    scaffoldBackgroundColor: isDark ? const Color(0xFF0B0F19) : const Color(0xFFF8FAFC),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: PredictiveBackPageTransitionsBuilder(),
      TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
    }),
    cardTheme: CardThemeData(
      elevation: 0,
      margin: EdgeInsets.zero,
      color: isDark ? const Color(0xFF131D31) : Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: BorderSide(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
          width: 1,
        ),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(
          color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
          width: 1,
        ),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(
          color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
          width: 1,
        ),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: scheme.primary, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      labelStyle: TextStyle(color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
    ),
    listTileTheme: const ListTileThemeData(
      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 2),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      showCloseIcon: true,
    ),
    appBarTheme: AppBarTheme(
      elevation: 0,
      scrolledUnderElevation: 1,
      backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: GoogleFonts.inter(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.3,
        color: isDark ? Colors.white : const Color(0xFF0F172A),
      ),
      iconTheme: IconThemeData(
        color: isDark ? Colors.white : const Color(0xFF0F172A),
        size: 20,
      ),
      actionsIconTheme: IconThemeData(
        color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
        size: 20,
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 60,
      elevation: 0,
      backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
      surfaceTintColor: Colors.transparent,
      indicatorShape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      indicatorColor: scheme.primary.withValues(alpha: isDark ? 0.22 : 0.14),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(
          fontSize: 10.5,
          fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
          letterSpacing: -0.2,
          overflow: TextOverflow.ellipsis,
          color: selected ? scheme.primary : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
        );
      }),
      iconTheme: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return IconThemeData(
          size: 20,
          color: selected ? scheme.primary : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
        );
      }),
    ),
    navigationRailTheme: NavigationRailThemeData(
      backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
      indicatorColor: scheme.primary.withValues(alpha: isDark ? 0.22 : 0.12),
    ),
  );

  final textTheme = GoogleFonts.interTextTheme(baseTheme.textTheme);
  return baseTheme.copyWith(
    textTheme: textTheme.copyWith(
      headlineLarge: textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5),
      headlineMedium: textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5),
      headlineSmall: textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.3),
      titleLarge: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600, letterSpacing: -0.2),
      titleMedium: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
      titleSmall: textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
      bodyLarge: textTheme.bodyLarge?.copyWith(fontSize: 15, height: 1.4),
      bodyMedium: textTheme.bodyMedium?.copyWith(fontSize: 14, height: 1.4),
      bodySmall: textTheme.bodySmall?.copyWith(fontSize: 12, height: 1.3),
      labelLarge: textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
    ),
  );
}

const Map<String, IconData> _icons = {
  'activity': LucideIcons.activity, 'alertcircle': LucideIcons.alertCircle,
  'alerttriangle': LucideIcons.alertTriangle, 'archive': LucideIcons.archive, 'arrowdown': LucideIcons.arrowDown,
  'arrowdownright': LucideIcons.arrowDownRight, 'arrowleft': LucideIcons.arrowLeft,
  'arrowright': LucideIcons.arrowRight, 'arrowup': LucideIcons.arrowUp, 'arrowupright': LucideIcons.arrowUpRight,
  'atsign': LucideIcons.atSign, 'award': LucideIcons.award, 'banknote': LucideIcons.banknote,
  'barchart3': LucideIcons.barChart3, 'battery': LucideIcons.battery, 'batterycharging': LucideIcons.batteryCharging,
  'bell': LucideIcons.bell, 'bellring': LucideIcons.bellRing, 'blinds': LucideIcons.blinds,
  'bluetooth': LucideIcons.bluetooth, 'bookmark': LucideIcons.bookmark, 'bookopen': LucideIcons.bookOpen,
  'bot': LucideIcons.bot, 'box': LucideIcons.box, 'brain': LucideIcons.brain, 'briefcase': LucideIcons.briefcase,
  'building': LucideIcons.building, 'building2': LucideIcons.building2, 'calendar': LucideIcons.calendar,
  'calendardays': LucideIcons.calendarDays, 'camera': LucideIcons.camera, 'cctv': LucideIcons.cctv,
  'check': LucideIcons.check, 'checkcircle': LucideIcons.checkCircle, 'checksquare': LucideIcons.checkSquare,
  'chevrondown': LucideIcons.chevronDown, 'chevronleft': LucideIcons.chevronLeft,
  'chevronright': LucideIcons.chevronRight, 'chevronsleft': LucideIcons.chevronsLeft,
  'chevronsright': LucideIcons.chevronsRight, 'chevronup': LucideIcons.chevronUp, 'circle': LucideIcons.circle,
  'circledot': LucideIcons.circleDot, 'clipboard': LucideIcons.clipboard,
  'clipboardcheck': LucideIcons.clipboardCheck, 'clipboardlist': LucideIcons.clipboardList,
  'clock': LucideIcons.clock, 'cloud': LucideIcons.cloud, 'cloudrain': LucideIcons.cloudRain,
  'code': LucideIcons.code, 'cog': LucideIcons.cog, 'coins': LucideIcons.coins, 'columns3': LucideIcons.columns3,
  'command': LucideIcons.command, 'copy': LucideIcons.copy, 'cpu': LucideIcons.cpu,
  'creditcard': LucideIcons.creditCard, 'database': LucideIcons.database, 'dices': LucideIcons.dices,
  'dollarsign': LucideIcons.dollarSign, 'doorclosed': LucideIcons.doorClosed, 'dooropen': LucideIcons.doorOpen,
  'download': LucideIcons.download, 'droplets': LucideIcons.droplets, 'edit': LucideIcons.edit,
  'euro': LucideIcons.euro, 'eye': LucideIcons.eye, 'eyeoff': LucideIcons.eyeOff, 'fan': LucideIcons.fan,
  'file': LucideIcons.file, 'filetext': LucideIcons.fileText, 'filter': LucideIcons.filter, 'flag': LucideIcons.flag,
  'flame': LucideIcons.flame, 'flaskconical': LucideIcons.flaskConical, 'folder': LucideIcons.folder,
  'folderopen': LucideIcons.folderOpen, 'gauge': LucideIcons.gauge, 'gitbranch': LucideIcons.gitBranch,
  'globe': LucideIcons.globe, 'graduationcap': LucideIcons.graduationCap, 'grid3x3': LucideIcons.grid3x3,
  'gripvertical': LucideIcons.gripVertical, 'hammer': LucideIcons.hammer, 'hash': LucideIcons.hash,
  'heart': LucideIcons.heart, 'helpcircle': LucideIcons.helpCircle, 'highlighter': LucideIcons.highlighter,
  'history': LucideIcons.history, 'home': LucideIcons.home, 'house': LucideIcons.house, 'image': LucideIcons.image,
  'inbox': LucideIcons.inbox, 'info': LucideIcons.info, 'kanban': LucideIcons.kanban, 'key': LucideIcons.key,
  'lamp': LucideIcons.lamp, 'laptop': LucideIcons.laptop, 'layers': LucideIcons.layers, 'layout': LucideIcons.layout,
  'layoutdashboard': LucideIcons.layoutDashboard, 'layoutgrid': LucideIcons.layoutGrid,
  'layoutlist': LucideIcons.layoutList, 'leaf': LucideIcons.leaf, 'lifebuoy': LucideIcons.lifeBuoy,
  'lightbulb': LucideIcons.lightbulb, 'linechart': LucideIcons.lineChart, 'link': LucideIcons.link,
  'list': LucideIcons.list, 'listchecks': LucideIcons.listChecks, 'listtodo': LucideIcons.listTodo,
  'loader2': LucideIcons.loader2, 'lock': LucideIcons.lock, 'logout': LucideIcons.logOut, 'mail': LucideIcons.mail,
  'map': LucideIcons.map, 'mappin': LucideIcons.mapPin, 'maximize2': LucideIcons.maximize2,
  'megaphone': LucideIcons.megaphone, 'menu': LucideIcons.menu, 'messagecircle': LucideIcons.messageCircle,
  'messagesquare': LucideIcons.messageSquare, 'mic': LucideIcons.mic, 'microchip': LucideIcons.microchip,
  'minus': LucideIcons.minus, 'monitor': LucideIcons.monitor, 'moon': LucideIcons.moon,
  'morehorizontal': LucideIcons.moreHorizontal, 'morevertical': LucideIcons.moreVertical,
  'package': LucideIcons.package, 'panelleft': LucideIcons.panelLeft, 'panelleftclose': LucideIcons.panelLeftClose,
  'panelleftopen': LucideIcons.panelLeftOpen, 'paperclip': LucideIcons.paperclip, 'pause': LucideIcons.pause,
  'pencil': LucideIcons.pencil, 'percent': LucideIcons.percent, 'phone': LucideIcons.phone,
  'piechart': LucideIcons.pieChart, 'play': LucideIcons.play, 'plug': LucideIcons.plug, 'plus': LucideIcons.plus,
  'pluscircle': LucideIcons.plusCircle, 'power': LucideIcons.power, 'printer': LucideIcons.printer,
  'radio': LucideIcons.radio, 'receipt': LucideIcons.receipt, 'refreshcw': LucideIcons.refreshCw,
  'repeat': LucideIcons.repeat, 'rocket': LucideIcons.rocket, 'router': LucideIcons.router, 'save': LucideIcons.save,
  'scantext': LucideIcons.scanText, 'search': LucideIcons.search, 'send': LucideIcons.send,
  'server': LucideIcons.server, 'settings': LucideIcons.settings, 'share2': LucideIcons.share2,
  'shield': LucideIcons.shield, 'shieldalert': LucideIcons.shieldAlert, 'shieldcheck': LucideIcons.shieldCheck,
  'shoppingbag': LucideIcons.shoppingBag, 'shoppingcart': LucideIcons.shoppingCart, 'sigma': LucideIcons.sigma,
  'signal': LucideIcons.signal, 'siren': LucideIcons.siren, 'sliders': LucideIcons.sliders,
  'smartphone': LucideIcons.smartphone, 'sparkles': LucideIcons.sparkles, 'sprout': LucideIcons.sprout,
  'square': LucideIcons.square, 'star': LucideIcons.star, 'sun': LucideIcons.sun, 'table': LucideIcons.table,
  'tag': LucideIcons.tag, 'tags': LucideIcons.tags, 'target': LucideIcons.target, 'terminal': LucideIcons.terminal,
  'thermometer': LucideIcons.thermometer, 'thumbsup': LucideIcons.thumbsUp, 'timer': LucideIcons.timer,
  'toggleleft': LucideIcons.toggleLeft, 'trash2': LucideIcons.trash2, 'trendingdown': LucideIcons.trendingDown,
  'trendingup': LucideIcons.trendingUp, 'trophy': LucideIcons.trophy, 'truck': LucideIcons.truck,
  'type': LucideIcons.type, 'upload': LucideIcons.upload, 'user': LucideIcons.user,
  'usercheck': LucideIcons.userCheck, 'userplus': LucideIcons.userPlus, 'users': LucideIcons.users,
  'users2': LucideIcons.users2, 'vibrate': LucideIcons.vibrate, 'video': LucideIcons.video,
  'wallet': LucideIcons.wallet, 'warehouse': LucideIcons.warehouse, 'waves': LucideIcons.waves,
  'webhook': LucideIcons.webhook, 'wifi': LucideIcons.wifi, 'wind': LucideIcons.wind,
  'workflow': LucideIcons.workflow, 'wrench': LucideIcons.wrench, 'x': LucideIcons.x, 'xcircle': LucideIcons.xCircle,
  'zap': LucideIcons.zap,
  'footprints': LucideIcons.footprints, 'heartpulse': LucideIcons.heartPulse, 'dumbbell': LucideIcons.dumbbell,
  'salad': LucideIcons.salad, 'apple': LucideIcons.apple, 'bike': LucideIcons.bike, 'watch': LucideIcons.watch,
  'quote': LucideIcons.quote, 'medal': LucideIcons.medal, 'gift': LucideIcons.gift, 'crown': LucideIcons.crown,
  'calendarcheck': LucideIcons.calendarCheck,
};

IconData mcnIcon(dynamic name) => _icons[mcnStr(name).toLowerCase().replaceAll(RegExp(r'[-_ ]'), '')] ?? LucideIcons.circle;

/// Modern, accessible, vibrant Flutter chart palette.
const List<Color> mcnPalette = [
  Color(0xFF4F46E5), // Indigo
  Color(0xFF06B6D4), // Cyan
  Color(0xFF10B981), // Emerald
  Color(0xFFF59E0B), // Amber
  Color(0xFFEC4899), // Pink
  Color(0xFF8B5CF6), // Purple
  Color(0xFF2563EB), // Blue
  Color(0xFFF97316), // Orange
];

Color mcnTone(dynamic name) => const {
      'green': Color(0xFF10B981), 'emerald': Color(0xFF10B981), 'red': Color(0xFFEF4444), 'blue': Color(0xFF2563EB),
      'sky': Color(0xFF0EA5E9), 'amber': Color(0xFFF59E0B), 'orange': Color(0xFFF97316), 'purple': Color(0xFF8B5CF6),
      'violet': Color(0xFF8B5CF6), 'pink': Color(0xFFEC4899), 'slate': Color(0xFF64748B),
    }[mcnStr(name).toLowerCase()] ?? const Color(0xFF6366F1);

String mcnCompact(num v) {
  final a = v.abs();
  String trim(String s) => s.endsWith('.0') ? s.substring(0, s.length - 2) : s;
  if (a >= 1e9) return '${trim((v / 1e9).toStringAsFixed(1))}B';
  if (a >= 1e6) return '${trim((v / 1e6).toStringAsFixed(1))}M';
  if (a >= 1e3) return '${trim((v / 1e3).toStringAsFixed(a >= 1e4 ? 0 : 1))}k';
  return a >= 10 || v == v.roundToDouble() ? mcnFormat(v.round()) : v.toStringAsFixed(1);
}

/// A round axis step (1, 2 or 5 × 10ⁿ) that splits 0..max into about four parts.
double mcnNiceStep(double max) {
  if (max <= 0) return 1;
  final raw = max / 4;
  final mag = math.pow(10, (math.log(raw) / math.ln10).floor()).toDouble();
  final f = raw / mag;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
}

// ── Notifications ────────────────────────────────────────────────────────────

final GlobalKey<ScaffoldMessengerState> _messenger = GlobalKey<ScaffoldMessengerState>();

void mcnNotify(BuildContext context, dynamic message, [dynamic kind = 'info']) {
  final scheme = Theme.of(context).colorScheme;
  final error = mcnStr(kind) == 'error';
  if (error) HapticFeedback.mediumImpact();
  (_messenger.currentState ?? ScaffoldMessenger.maybeOf(context))?.showSnackBar(SnackBar(
    content: Text(mcnStr(message)),
    backgroundColor: error ? scheme.error : null,
  ));
}

Future<bool> mcnConfirm(BuildContext context, String title, {String action = 'Delete'}) async {
  final ok = await showAdaptiveDialog<bool>(
    context: context,
    builder: (context) => AlertDialog.adaptive(
      title: Text(title),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        TextButton(onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Theme.of(context).colorScheme.error), child: Text(action)),
      ],
    ),
  );
  return ok ?? false;
}

// ── App shell ────────────────────────────────────────────────────────────────

class MCNSection {
  final String label;
  final String icon;
  final Widget Function() build;
  const MCNSection(this.label, this.icon, this.build);
}

/// What a screen needs from the shell: its title, and a way to open the drawer.
class MCNScope extends InheritedWidget {
  final String title;
  final VoidCallback? openDrawer;
  /// A `page` layout: the screen has no app bar (its own navbar, if any, is part of the page)
  final bool bare;
  const MCNScope({super.key, required this.title, this.openDrawer, this.bare = false, required super.child});
  static MCNScope? of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<MCNScope>();
  @override
  bool updateShouldNotify(MCNScope old) => old.title != title || old.openDrawer != openDrawer || old.bare != bare;
}

/// Phones: a bottom navigation bar (up to five sections) or a drawer (more).
/// Tablets and desktop: a navigation rail. Every section keeps its own page
/// history, so detail pages slide in and the back button or swipe-back returns.
class MCNApp extends StatefulWidget {
  final String title;
  final String? logo;
  final List<MCNSection> sections;
  /// Brand color ("#7c3aed"): buttons, links, rings and accents follow it
  final String? brand;
  /// A `page` layout (landing pages): one screen without the app bar
  final bool page;
  const MCNApp({super.key, required this.title, required this.sections, this.logo, this.brand, this.page = false});
  @override
  State<MCNApp> createState() => _MCNAppState();
}

class _MCNAppState extends State<MCNApp> {
  int _index = 0;
  Color? get _brandColor {
    final b = widget.brand ?? '';
    return RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(b) ? Color(int.parse('FF${b.substring(1)}', radix: 16)) : null;
  }
  late final List<GlobalKey<NavigatorState>> _tabs = [for (final _ in widget.sections) GlobalKey<NavigatorState>()];
  final GlobalKey<ScaffoldState> _scaffold = GlobalKey<ScaffoldState>();

  void _select(int i) {
    HapticFeedback.selectionClick();
    if (i == _index) {
      _tabs[i].currentState?.popUntil((r) => r.isFirst);   // tapping the current tab goes back to its start
    } else {
      setState(() => _index = i);
    }
  }

  void _back() {
    final nav = _tabs[_index].currentState;
    if (nav != null && nav.canPop()) {
      nav.pop();
    } else if (_index != 0) {
      setState(() => _index = 0);
    } else {
      SystemNavigator.pop();
    }
  }

  Widget _tab(int i, VoidCallback? openDrawer) {
    final s = widget.sections[i];
    return Navigator(
      key: _tabs[i],
      onGenerateRoute: (settings) => MaterialPageRoute(settings: settings,
          builder: (_) => MCNScope(title: s.label, openDrawer: openDrawer, bare: widget.page, child: s.build())),
    );
  }

  Widget _brand(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(children: [
      Container(width: 36, height: 36, decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(10)),
          child: Icon(mcnIcon(widget.logo ?? 'layoutdashboard'), size: 18, color: scheme.onPrimary)),
      const SizedBox(width: 12),
      Flexible(child: Text(widget.title, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium)),
    ]);
  }

  Widget _shell(BuildContext context) {
    final sections = widget.sections;
    if (sections.isEmpty) return const Scaffold();
    return LayoutBuilder(builder: (context, size) {
      final rail = size.maxWidth >= 640 && sections.length > 1;
      final drawer = !rail && sections.length > 5;
      final pages = IndexedStack(index: _index, children: [
        for (var i = 0; i < sections.length; i++) _tab(i, drawer ? () => _scaffold.currentState?.openDrawer() : null),
      ]);
      return PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, _) { if (!didPop) _back(); },
        child: Scaffold(
          key: _scaffold,
          drawer: drawer ? NavigationDrawer(
            selectedIndex: _index,
            onDestinationSelected: (i) { Navigator.pop(context); _select(i); },
            children: [
              Padding(padding: const EdgeInsets.fromLTRB(28, 20, 16, 12), child: _brand(context)),
              for (final s in sections) NavigationDrawerDestination(icon: Icon(mcnIcon(s.icon)), label: Text(s.label)),
            ],
          ) : null,
          body: rail ? Row(children: [
            SafeArea(child: NavigationRail(
              extended: size.maxWidth >= 1100,
              selectedIndex: _index,
              onDestinationSelected: _select,
              labelType: size.maxWidth >= 1100 ? NavigationRailLabelType.none : NavigationRailLabelType.all,
              leading: Padding(padding: const EdgeInsets.symmetric(vertical: 12),
                  child: size.maxWidth >= 1100 ? SizedBox(width: 200, child: _brand(context))
                      : Container(width: 40, height: 40, decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary,
                          borderRadius: BorderRadius.circular(12)),
                          child: Icon(mcnIcon(widget.logo ?? 'layoutdashboard'), size: 20, color: Theme.of(context).colorScheme.onPrimary))),
              destinations: [for (final s in sections) NavigationRailDestination(icon: Icon(mcnIcon(s.icon)), label: Text(s.label))],
            )),
            const VerticalDivider(width: 1),
            Expanded(child: pages),
          ]) : pages,
          bottomNavigationBar: !rail && !drawer && sections.length > 1
              ? Container(
                  decoration: BoxDecoration(
                    color: Theme.of(context).brightness == Brightness.dark
                        ? const Color(0xFF0F172A)
                        : Colors.white,
                    border: Border(
                      top: BorderSide(
                        color: Theme.of(context).brightness == Brightness.dark
                            ? const Color(0xFF1E293B)
                            : const Color(0xFFE2E8F0),
                        width: 1,
                      ),
                    ),
                  ),
                  child: NavigationBar(
                    height: 60,
                    elevation: 0,
                    selectedIndex: _index,
                    onDestinationSelected: _select,
                    backgroundColor: Colors.transparent,
                    indicatorColor: Theme.of(context).colorScheme.primary.withValues(alpha: 0.14),
                    labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
                    destinations: [
                      for (final s in sections)
                        NavigationDestination(
                          icon: Icon(mcnIcon(s.icon), size: 20),
                          selectedIcon: Icon(mcnIcon(s.icon), size: 20, color: Theme.of(context).colorScheme.primary),
                          label: s.label,
                        )
                    ],
                  ),
                )
              : null,
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: widget.title,
        debugShowCheckedModeBanner: false,
        scaffoldMessengerKey: _messenger,
        theme: mcnTheme(Brightness.light, _brandColor),
        darkTheme: mcnTheme(Brightness.dark, _brandColor),
        themeMode: ThemeMode.system,
        home: Builder(builder: _shell),
      );
}

/// A native mobile screen: a clean Material 3 app bar with left-aligned title,
/// back navigation or drawer toggle, refresh action, and scrollable body.
class MCNPage extends StatelessWidget {
  final List<Widget> children;
  final Future<dynamic> Function()? onRefresh;
  final String? title;

  /// True while the screen's data loads: shows a progress bar under the app bar.
  final bool loading;

  /// Why loading failed: shown above the content with a Retry button.
  final String? error;
  final VoidCallback? onRetry;
  const MCNPage({
    super.key,
    required this.children,
    this.onRefresh,
    this.title,
    this.loading = false,
    this.error,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final scope = MCNScope.of(context);
    final canPop = Navigator.of(context).canPop();
    final pageTitle = title ?? scope?.title ?? '';
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final borderColor = isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0);

    final bare = scope?.bare == true && !canPop;
    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0B0F19) : const Color(0xFFF8FAFC),
      appBar: bare ? null : AppBar(
        title: Text(
          pageTitle,
          style: GoogleFonts.inter(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.3,
          ),
        ),
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
        leading: canPop
            ? IconButton(
                icon: const Icon(LucideIcons.arrowLeft, size: 20),
                tooltip: 'Back',
                onPressed: () => Navigator.of(context).pop(),
              )
            : (scope?.openDrawer != null
                ? IconButton(
                    icon: const Icon(LucideIcons.menu, size: 20),
                    tooltip: 'Menu',
                    onPressed: scope!.openDrawer,
                  )
                : null),
        actions: [
          if (onRefresh != null)
            IconButton(
              icon: const Icon(LucideIcons.rotateCw, size: 18),
              tooltip: 'Refresh',
              onPressed: () async {
                HapticFeedback.lightImpact();
                await onRefresh!();
              },
            ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: loading
              ? const LinearProgressIndicator(minHeight: 1)
              : Container(color: borderColor, height: 1),
        ),
      ),
      body: LayoutBuilder(builder: (context, size) {
        final side = math.max(16.0, (size.maxWidth - 1100) / 2);
        final top = bare ? MediaQuery.of(context).padding.top + 12 : 16.0;
        final items = [
          if (error != null) _MCNLoadError(message: error!, onRetry: onRetry),
          ...children,
        ];
        // A page builds every section up front, so "#pricing" links can scroll to any of them
        final Widget list = bare
            ? SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(side, top, side, 28),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  for (var i = 0; i < items.length; i++) ...[if (i > 0) const SizedBox(height: 24), items[i]],
                ]),
              )
            : ListView.separated(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(side, top, side, 28),
                itemCount: items.length,
                itemBuilder: (_, i) => items[i],
                separatorBuilder: (_, __) => const SizedBox(height: 16),
              );
        return onRefresh == null
            ? list
            : RefreshIndicator.adaptive(
                onRefresh: () async {
                  HapticFeedback.lightImpact();
                  await onRefresh!();
                },
                child: list,
              );
      }),
    );
  }
}

class _MCNLoadError extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const _MCNLoadError({required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: Material(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
          child: Row(children: [
            Icon(LucideIcons.alertCircle, size: 20, color: scheme.onErrorContainer),
            const SizedBox(width: 12),
            Expanded(child: Text(message, style: TextStyle(color: scheme.onErrorContainer))),
            if (onRetry != null)
              TextButton(
                onPressed: onRetry,
                style: TextButton.styleFrom(foregroundColor: scheme.onErrorContainer),
                child: const Text('Retry'),
              ),
          ]),
        ),
      ),
    );
  }
}

// ── Layout ───────────────────────────────────────────────────────────────────

/// grid_cols=N: responsive Flutter grid adapting to phone, tablet and desktop.
/// On phones (<600px width), cards, charts and forms expand to 1 column, while
/// stat cards arrange neatly into 2 columns.
class MCNGrid extends StatelessWidget {
  final int columns;
  final List<Widget> children;
  const MCNGrid({super.key, required this.columns, required this.children});

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
    final allStats = children.every((w) => w is MCNStat);
    // Rings and avatars are small: they sit side by side even on phones
    final allSmall = children.isNotEmpty && children.every((w) => w is MCNProgressRing || w is MCNAvatar);
    final int n;
    if (c.maxWidth > 900) {
      n = columns;
    } else if (c.maxWidth > 600) {
      n = math.min(2, columns);
    } else {
      // Mobile screen (< 600px width)
      if (allSmall) {
        n = math.max(1, math.min(columns, (c.maxWidth / 86).floor()));
      } else if (allStats && columns >= 2 && c.maxWidth >= 260) {
        n = 2; // 2x2 grid for stats
      } else {
        n = 1; // Full width for cards, charts, forms, tables
      }
    }
    const gap = 12.0;
    final w = (c.maxWidth - gap * (n - 1)) / n;
    return Wrap(
      spacing: gap,
      runSpacing: gap,
      children: [for (final child in children) SizedBox(width: w, child: allSmall ? Center(child: child) : child)],
    );
  });
}

/// Vertical stack with even spacing (forms, card bodies).
class MCNStack extends StatelessWidget {
  final List<Widget> children;
  final double gap;
  const MCNStack({super.key, required this.children, this.gap = 12});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < children.length; i++) ...[if (i > 0) SizedBox(height: gap), children[i]],
      ]);
}

class MCNCard extends StatelessWidget {
  final String? title;
  final String? description;
  final List<Widget> children;
  const MCNCard({super.key, this.title, this.description, required this.children});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (title != null) ...[
              Text(
                title!,
                style: t.titleMedium?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.2),
              ),
              if (description != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    description!,
                    style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
                  ),
                ),
              const SizedBox(height: 14),
            ] else if (description != null) ...[
              Text(
                description!,
                style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
              ),
              const SizedBox(height: 12),
            ],
            MCNStack(children: children),
          ],
        ),
      ),
    );
  }
}

class MCNStat extends StatelessWidget {
  final dynamic label, value, icon, color, unit, change;
  const MCNStat({super.key, this.label, this.value, this.icon, this.color, this.unit, this.change});

  @override
  Widget build(BuildContext context) {
    final tone = mcnTone(color);
    final t = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final changeNum = change != null ? mcnNum(change) : null;
    final hasChange = changeNum != null && changeNum != 0;
    final isPos = hasChange && changeNum >= 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: tone.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(mcnIcon(icon), color: tone, size: 18),
                ),
                if (hasChange)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                    decoration: BoxDecoration(
                      color: (isPos ? const Color(0xFF10B981) : const Color(0xFFEF4444)).withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(99),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          isPos ? LucideIcons.trendingUp : LucideIcons.trendingDown,
                          size: 11,
                          color: isPos ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                        ),
                        const SizedBox(width: 3),
                        Text(
                          '${isPos ? '+' : ''}${changeNum.toStringAsFixed(1)}%',
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w700,
                            color: isPos ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text.rich(
                TextSpan(text: mcnFormat(value), children: [
                  // The unit sits after the number, smaller and muted, as on the web
                  if (mcnStr(unit).isNotEmpty)
                    TextSpan(
                      text: ' ${mcnStr(unit)}',
                      style: t.bodyMedium?.copyWith(fontWeight: FontWeight.w400, color: t.bodySmall?.color, letterSpacing: 0),
                    ),
                ]),
                maxLines: 1,
                style: t.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  fontSize: 22,
                  letterSpacing: -0.5,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              mcnHumanize(mcnStr(label)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: t.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class MCNText extends StatelessWidget {
  final dynamic text;
  final String style; // h1 | h2 | h3 | p | muted | small
  const MCNText(this.text, {super.key, this.style = 'p'});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final muted = t.bodyMedium?.copyWith(color: scheme.onSurfaceVariant);
    final s = {
      'h1': t.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
      'h2': t.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      'h3': t.titleMedium?.copyWith(fontWeight: FontWeight.w600),
      'muted': muted,
      'small': t.labelLarge?.copyWith(color: scheme.onSurfaceVariant),
    }[style] ?? t.bodyLarge;
    return Text(mcnStr(text), style: s);
  }
}

class MCNEmpty extends StatelessWidget {
  final dynamic title, description, icon;
  const MCNEmpty({super.key, this.title, this.description, this.icon});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 16),
      child: Column(children: [
        Icon(mcnIcon(icon ?? 'inbox'), size: 36, color: scheme.outline),
        const SizedBox(height: 12),
        Text(mcnStr(title), textAlign: TextAlign.center, style: t.titleSmall),
        if (description != null) Padding(padding: const EdgeInsets.only(top: 4),
            child: Text(mcnStr(description), textAlign: TextAlign.center, style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant))),
      ]),
    );
  }
}

/// A screen that only exists in the web app (agent and workflow builders).
class MCNWebOnly extends StatelessWidget {
  final String name;
  const MCNWebOnly(this.name, {super.key});
  @override
  Widget build(BuildContext context) => Card(child: MCNEmpty(title: '$name is available in the web app', icon: 'monitor',
      description: 'Open this app in a browser to use the $name.'));
}

const Map<String, String> _badgeTones = {
  'active': 'emerald', 'done': 'emerald', 'completed': 'emerald', 'won': 'emerald', 'paid': 'emerald', 'approved': 'emerald',
  'success': 'emerald', 'open': 'sky', 'pending': 'amber', 'review': 'amber', 'draft': 'slate', 'in progress': 'sky',
  'in_progress': 'sky', 'new': 'sky', 'proposal': 'violet', 'qualification': 'violet', 'lost': 'red', 'failed': 'red',
  'rejected': 'red', 'overdue': 'red', 'cancelled': 'red', 'high': 'red', 'urgent': 'red', 'medium': 'amber', 'low': 'slate',
};

/// Modern status badge pill with subtle border and optional dot.
class MCNBadge extends StatelessWidget {
  final dynamic value;
  const MCNBadge(this.value, {super.key});

  @override
  Widget build(BuildContext context) {
    final text = mcnStr(value);
    const tones = ['emerald', 'sky', 'amber', 'red', 'violet', 'slate'];
    final tone = mcnTone(_badgeTones[text.toLowerCase()] ?? tones[text.codeUnits.fold<int>(0, (a, b) => a + b) % tones.length]);
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: dark ? 0.2 : 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: tone.withValues(alpha: dark ? 0.35 : 0.25), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(right: 6),
            decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
          ),
          Text(
            text.isEmpty ? '—' : text,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: dark ? Color.lerp(tone, Colors.white, 0.35) : Color.lerp(tone, Colors.black, 0.3),
            ),
          ),
        ],
      ),
    );
  }
}

class MCNAlert extends StatelessWidget {
  final dynamic text;
  final dynamic title;
  const MCNAlert(this.text, {super.key, this.title});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: scheme.secondaryContainer,
      child: ListTile(
        leading: Icon(LucideIcons.info, color: scheme.onSecondaryContainer),
        title: title == null ? Text(mcnStr(text)) : Text(mcnStr(title)),
        subtitle: title == null ? null : Text(mcnStr(text)),
        textColor: scheme.onSecondaryContainer,
      ),
    );
  }
}

class MCNSeparator extends StatelessWidget {
  const MCNSeparator({super.key});
  @override
  Widget build(BuildContext context) => const Divider(height: 8);
}

class MCNProgress extends StatelessWidget {
  final dynamic value;
  const MCNProgress(this.value, {super.key});
  @override
  Widget build(BuildContext context) => ClipRRect(borderRadius: BorderRadius.circular(99),
      child: LinearProgressIndicator(value: (mcnNum(value) / 100).clamp(0, 1).toDouble(), minHeight: 8));
}

// ── Forms ────────────────────────────────────────────────────────────────────

class MCNButton extends StatelessWidget {
  final dynamic label;
  final String variant; // default | outline | secondary | ghost | destructive
  final VoidCallback? onPressed;
  final dynamic icon;
  const MCNButton(this.label, {super.key, this.variant = 'default', this.onPressed, this.icon});

  @override
  Widget build(BuildContext context) {
    final child = Text(mcnStr(label), style: const TextStyle(fontWeight: FontWeight.w600));
    final i = icon == null ? null : Icon(mcnIcon(icon), size: 18);
    final tap = onPressed == null ? null : () { HapticFeedback.lightImpact(); onPressed!(); };
    final error = Theme.of(context).colorScheme.error;
    final inCardOrForm = context.findAncestorWidgetOfExactType<MCNCard>() != null;
    final btnStyle = ButtonStyle(
      padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 20, vertical: 12)),
      shape: WidgetStatePropertyAll(RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
    );
    final Widget button = switch (variant) {
      'outline' => i == null
          ? OutlinedButton(onPressed: tap, style: btnStyle, child: child)
          : OutlinedButton.icon(onPressed: tap, style: btnStyle, icon: i, label: child),
      'secondary' => i == null
          ? FilledButton.tonal(onPressed: tap, style: btnStyle, child: child)
          : FilledButton.tonalIcon(onPressed: tap, style: btnStyle, icon: i, label: child),
      'ghost' => i == null
          ? TextButton(onPressed: tap, style: btnStyle, child: child)
          : TextButton.icon(onPressed: tap, style: btnStyle, icon: i, label: child),
      'destructive' => FilledButton(
          onPressed: tap,
          style: btnStyle.copyWith(backgroundColor: WidgetStatePropertyAll(error)),
          child: child,
        ),
      _ => i == null
          ? FilledButton(onPressed: tap, style: btnStyle, child: child)
          : FilledButton.icon(onPressed: tap, style: btnStyle, icon: i, label: child),
    };
    return SizedBox(
      width: inCardOrForm ? double.infinity : null,
      height: 44,
      child: button,
    );
  }
}

class MCNInput extends StatelessWidget {
  final dynamic label, placeholder;
  final TextEditingController? controller;
  final bool number, multiline;
  final ValueChanged<String>? onChanged;
  const MCNInput({super.key, this.label, this.placeholder, this.controller, this.number = false, this.multiline = false, this.onChanged});
  @override
  Widget build(BuildContext context) => TextField(
        controller: controller,
        onChanged: onChanged,
        minLines: multiline ? 3 : 1,
        maxLines: multiline ? 6 : 1,
        textInputAction: multiline ? TextInputAction.newline : TextInputAction.next,
        keyboardType: number ? const TextInputType.numberWithOptions(decimal: true, signed: true)
            : (multiline ? TextInputType.multiline : TextInputType.text),
        decoration: InputDecoration(
          labelText: label == null ? null : mcnStr(label),
          hintText: placeholder == null ? null : mcnStr(placeholder),
        ),
      );
}

class MCNSelect extends StatelessWidget {
  final dynamic label;
  final dynamic options;
  final dynamic value;
  final ValueChanged<String> onChanged;
  const MCNSelect({super.key, this.label, this.options, this.value, required this.onChanged});
  @override
  Widget build(BuildContext context) {
    final items = mcnList(options).map(mcnStr).toList();
    final current = items.contains(mcnStr(value)) ? mcnStr(value) : null;
    return DropdownMenu<String>(
      key: ValueKey('$current${items.join('|')}'),
      initialSelection: current,
      expandedInsets: EdgeInsets.zero,
      label: label == null ? null : Text(mcnStr(label)),
      dropdownMenuEntries: [for (final o in items) DropdownMenuEntry(value: o, label: o)],
      onSelected: (v) { if (v != null) { HapticFeedback.selectionClick(); onChanged(v); } },
    );
  }
}

class MCNSwitch extends StatelessWidget {
  final dynamic label;
  final dynamic value;
  final ValueChanged<bool> onChanged;
  const MCNSwitch({super.key, this.label, this.value, required this.onChanged});
  @override
  Widget build(BuildContext context) => SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: Text(mcnStr(label)),
        value: mcnTruthy(value),
        onChanged: (b) { HapticFeedback.selectionClick(); onChanged(b); },
      );
}

// ── Data ─────────────────────────────────────────────────────────────────────

final _badgeColumn = RegExp(r'^(status|stage|priority|state|type|split|label|source)$');

/// Mobile data_table: a search bar, filter chips and a native list. Tap a row
/// to open it (its own page, with back navigation); swipe left to delete.
class MCNDataList extends StatefulWidget {
  final dynamic data;
  final List<dynamic> columns;
  final List<dynamic> filters;
  final String? title;
  final String? description;
  final String? titleKey;
  final int pageSize;
  final Future<void> Function(dynamic row)? onDelete;
  final void Function(dynamic row)? onTap;
  final String? empty;
  const MCNDataList({super.key, this.data, this.columns = const [], this.filters = const [], this.title, this.description,
      this.titleKey, this.pageSize = 20, this.onDelete, this.onTap, this.empty});
  @override
  State<MCNDataList> createState() => _MCNDataListState();
}

class _MCNDataListState extends State<MCNDataList> {
  String _query = '';
  final Map<String, String?> _filter = {};
  int _shown = 0;

  List<String> _cols(List<dynamic> rows) => widget.columns.isNotEmpty ? widget.columns.map(mcnStr).toList()
      : (rows.isNotEmpty && rows.first is Map ? (rows.first as Map).keys.map(mcnStr).where((k) => k != 'id').take(5).toList() : <String>[]);

  void _open(BuildContext context, dynamic row, List<String> cols, String titleKey) {
    if (widget.onTap != null) { widget.onTap!(row); return; }
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => MCNDetailPage(
      row: row, titleKey: titleKey, columns: cols,
      onDelete: widget.onDelete == null ? null : () async { await widget.onDelete!(row); },
    )));
  }

  @override
  Widget build(BuildContext context) {
    final parentCard = context.findAncestorWidgetOfExactType<MCNCard>();
    final inCard = parentCard != null;
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final rows = mcnList(widget.data);
    final cols = _cols(rows);
    final titleKey = widget.titleKey ?? cols.firstWhere((k) => k != 'id', orElse: () => cols.isNotEmpty ? cols.first : 'title');
    final q = _query.toLowerCase();
    final filtered = rows.where((r) =>
        (q.isEmpty || cols.any((col) => mcnStr(mcnGet(r, col)).toLowerCase().contains(q))) &&
        _filter.entries.every((f) => f.value == null || mcnStr(mcnGet(r, f.key)) == f.value)).toList();
    final limit = _shown == 0 ? (inCard ? 5 : widget.pageSize) : _shown;
    final shown = filtered.take(limit).toList();
    final badgeCols = cols.where((c) => c != titleKey && _badgeColumn.hasMatch(c)).toList();
    final otherCols = cols.where((c) => c != titleKey && !_badgeColumn.hasMatch(c)).toList();

    // A table titled like its screen ("Orders" on Orders) doesn't repeat the heading
    final title = widget.title != null && widget.title != MCNScope.of(context)?.title && (!inCard || parentCard.title != widget.title) ? widget.title : null;
    final showSearch = !inCard && (widget.filters.isNotEmpty || rows.length > 6);

    final listContent = Column(children: [
      if (shown.isEmpty)
        MCNEmpty(title: rows.isEmpty ? (widget.empty ?? 'Nothing here yet') : 'No matches', icon: rows.isEmpty ? 'inbox' : 'search'),
      for (var i = 0; i < shown.length; i++) ...[
        if (i > 0) Divider(height: 1, indent: 72, color: scheme.outlineVariant.withValues(alpha: 0.5)),
        _row(context, shown[i], titleKey, badgeCols, otherCols, cols),
      ],
      if (filtered.length > limit)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: TextButton(
            onPressed: () => setState(() => _shown = limit + widget.pageSize),
            child: Text('Show more (${filtered.length - limit} left)'),
          ),
        ),
    ]);

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (title != null) Text(title, style: t.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
      if (widget.description != null) Text(widget.description!, style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
      if (title != null || widget.description != null) const SizedBox(height: 10),
      if (showSearch) ...[
        SearchBar(
          hintText: 'Search',
          leading: const Padding(padding: EdgeInsets.only(left: 4), child: Icon(LucideIcons.search, size: 20)),
          elevation: const WidgetStatePropertyAll(0),
          backgroundColor: WidgetStatePropertyAll(scheme.surfaceContainerHigh),
          onChanged: (v) => setState(() => _query = v),
        ),
        const SizedBox(height: 8),
      ],
      for (final key in widget.filters.map(mcnStr))
        SizedBox(
          height: 48,
          child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.only(top: 8), children: [
            for (final v in rows.map((r) => mcnStr(mcnGet(r, key))).where((v) => v.isNotEmpty).toSet())
              Padding(padding: const EdgeInsets.only(right: 8), child: FilterChip(
                label: Text(v),
                selected: _filter[key] == v,
                onSelected: (on) { HapticFeedback.selectionClick(); setState(() => _filter[key] = on ? v : null); },
              )),
          ]),
        ),
      if (inCard)
        listContent
      else
        Card(
          clipBehavior: Clip.antiAlias,
          child: listContent,
        ),
      if (!inCard && rows.length > 5)
        Padding(padding: const EdgeInsets.only(top: 8, left: 4),
            child: Text('${filtered.length} of ${rows.length}', style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant))),
    ]);
  }

  Widget _row(BuildContext context, dynamic r, String titleKey, List<String> badgeCols, List<String> otherCols, List<String> cols) {
    final scheme = Theme.of(context).colorScheme;
    final title = mcnFormat(mcnGet(r, titleKey));
    final tile = ListTile(
      leading: CircleAvatar(
        backgroundColor: mcnPalette[title.codeUnits.fold<int>(0, (a, b) => a + b) % mcnPalette.length].withValues(alpha: 0.16),
        child: Text(title.isEmpty ? '?' : title.characters.first.toUpperCase(),
            style: TextStyle(fontWeight: FontWeight.w600, color: scheme.onSurface)),
      ),
      title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: otherCols.isEmpty ? null : Text(
        otherCols.take(3).map((c) => mcnFormat(mcnGet(r, c))).where((v) => v != '—').join(' · '),
        maxLines: 1, overflow: TextOverflow.ellipsis),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        for (final c in badgeCols.take(1)) MCNBadge(mcnGet(r, c)),
        const SizedBox(width: 4),
        Icon(LucideIcons.chevronRight, size: 18, color: scheme.onSurfaceVariant),
      ]),
      onTap: () => _open(context, r, cols, titleKey),
    );
    if (widget.onDelete == null) return tile;
    return Dismissible(
      key: ValueKey(mcnGet(r, 'id') ?? r.hashCode),
      direction: DismissDirection.endToStart,
      background: Container(color: scheme.error, alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 24),
          child: Icon(LucideIcons.trash2, color: scheme.onError)),
      confirmDismiss: (_) => mcnConfirm(context, 'Delete $title?'),
      onDismissed: (_) { HapticFeedback.mediumImpact(); widget.onDelete!(r); },
      child: tile,
    );
  }
}

/// One record on its own page, opened from a list (back button / swipe back to return).
class MCNDetailPage extends StatelessWidget {
  final dynamic row;
  final String titleKey;
  final List<String> columns;
  final Future<void> Function()? onDelete;
  const MCNDetailPage({super.key, required this.row, required this.titleKey, required this.columns, this.onDelete});
  @override
  Widget build(BuildContext context) {
    final keys = row is Map ? (row as Map).keys.map(mcnStr).toList() : columns;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: CustomScrollView(slivers: [
        SliverAppBar.large(
          title: Text(mcnFormat(mcnGet(row, titleKey))),
          actions: [
            if (onDelete != null) IconButton(
              icon: const Icon(LucideIcons.trash2), tooltip: 'Delete',
              onPressed: () async {
                if (!await mcnConfirm(context, 'Delete ${mcnFormat(mcnGet(row, titleKey))}?')) return;
                await onDelete!();
                if (context.mounted) Navigator.of(context).pop();
              },
            ),
          ],
        ),
        SliverPadding(
          padding: const EdgeInsets.all(16),
          sliver: SliverToBoxAdapter(child: Card(child: Column(children: [
            for (var i = 0; i < keys.length; i++) ...[
              if (i > 0) Divider(height: 1, indent: 16, color: scheme.outlineVariant.withValues(alpha: 0.5)),
              ListTile(
                title: Text(mcnHumanize(keys[i]), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
                subtitle: _badgeColumn.hasMatch(keys[i])
                    ? Align(alignment: Alignment.centerLeft, child: Padding(padding: const EdgeInsets.only(top: 4), child: MCNBadge(mcnGet(row, keys[i]))))
                    : Text(mcnFormat(mcnGet(row, keys[i])), style: Theme.of(context).textTheme.bodyLarge),
              ),
            ],
          ]))),
        ),
      ]),
    );
  }
}

/// Board with a column per value of groupBy. Phones swipe between columns;
/// long-press a card to drag it, or tap it to pick its new column.
class MCNKanban extends StatefulWidget {
  final dynamic data;
  final String groupBy;
  final List<dynamic> columns;
  final String? titleKey;
  final List<dynamic> fields;
  final Future<dynamic> Function(dynamic item, String to)? onMove;
  const MCNKanban({super.key, this.data, this.groupBy = 'status', this.columns = const [], this.titleKey, this.fields = const [], this.onMove});
  @override
  State<MCNKanban> createState() => _MCNKanbanState();
}

class _MCNKanbanState extends State<MCNKanban> {
  List<dynamic> _items = [];
  final _pages = PageController(viewportFraction: 0.86);
  @override
  void initState() { super.initState(); _items = List.of(mcnList(widget.data)); }
  @override
  void didUpdateWidget(MCNKanban old) {
    super.didUpdateWidget(old);
    // Only new data replaces the board; a rebuild (rotation, resize) keeps the moves made here
    if (!identical(old.data, widget.data)) _items = List.of(mcnList(widget.data));
  }
  @override
  void dispose() { _pages.dispose(); super.dispose(); }

  Future<void> _move(int i, String col) async {
    if (mcnStr(mcnGet(_items[i], widget.groupBy)) == col) return;
    HapticFeedback.mediumImpact();
    final item = Map<String, dynamic>.from(_items[i] as Map)..[widget.groupBy] = col;
    setState(() => _items[i] = item);
    await widget.onMove?.call(item, col);
  }

  Future<void> _pick(BuildContext context, int i, List<String> cols) async {
    final to = await showModalBottomSheet<String>(
      context: context,
      useRootNavigator: true,      // above the bottom navigation bar
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Padding(padding: const EdgeInsets.only(bottom: 8), child: Text('Move to', style: Theme.of(context).textTheme.titleMedium)),
        for (final c in cols)
          ListTile(
            title: Text(c),
            trailing: mcnStr(mcnGet(_items[i], widget.groupBy)) == c ? const Icon(LucideIcons.check) : null,
            onTap: () => Navigator.pop(context, c),
          ),
      ])),
    );
    if (to != null) await _move(i, to);
  }

  Widget _card(BuildContext context, int i, String titleKey, List<String> cols) {
    final t = Theme.of(context).textTheme;
    final item = _items[i];
    final body = Card(
      color: Theme.of(context).colorScheme.surface,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _pick(context, i, cols),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(mcnFormat(mcnGet(item, titleKey)), style: t.titleSmall),
            for (final f in widget.fields.map(mcnStr))
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(children: [
                  Expanded(child: Text(mcnHumanize(f), style: t.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant))),
                  RegExp(r'^(status|priority|type)$').hasMatch(f) ? MCNBadge(mcnGet(item, f)) : Text(mcnFormat(mcnGet(item, f)), style: t.bodySmall),
                ]),
              ),
          ]),
        ),
      ),
    );
    return LongPressDraggable<int>(
      data: i,
      onDragStarted: HapticFeedback.selectionClick,
      feedback: Material(color: Colors.transparent, child: SizedBox(width: 260, child: Transform.rotate(angle: 0.03, child: body))),
      childWhenDragging: Opacity(opacity: 0.35, child: body),
      child: body,
    );
  }

  Widget _column(BuildContext context, String col, String titleKey, List<String> cols) {
    final scheme = Theme.of(context).colorScheme;
    final count = _items.where((r) => mcnStr(mcnGet(r, widget.groupBy)) == col).length;
    return DragTarget<int>(
      onAcceptWithDetails: (d) => _move(d.data, col),
      builder: (context, candidate, _) => AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.symmetric(horizontal: 6),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: candidate.isNotEmpty ? scheme.primaryContainer : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
            child: Row(children: [
              Expanded(child: Text(col, style: Theme.of(context).textTheme.titleSmall)),
              Badge(label: Text('$count'), backgroundColor: scheme.secondary),
            ]),
          ),
          Expanded(child: ListView(children: [
            for (var i = 0; i < _items.length; i++)
              if (mcnStr(mcnGet(_items[i], widget.groupBy)) == col)
                Padding(padding: const EdgeInsets.only(bottom: 8), child: _card(context, i, titleKey, cols)),
            if (count == 0) Padding(padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text('Drop cards here', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall)),
          ])),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cols = widget.columns.isNotEmpty ? widget.columns.map(mcnStr).toList()
        : _items.map((r) => mcnStr(mcnGet(r, widget.groupBy))).toSet().toList();
    final titleKey = widget.titleKey ?? 'title';
    final height = (MediaQuery.sizeOf(context).height * 0.62).clamp(360.0, 720.0);
    return LayoutBuilder(builder: (context, size) {
      final phone = size.maxWidth < 640;
      return SizedBox(
        height: height,
        child: phone
            ? PageView(controller: _pages, padEnds: false, children: [for (final c in cols) _column(context, c, titleKey, cols)])
            : ListView(scrollDirection: Axis.horizontal, children: [
                for (final c in cols) SizedBox(width: 290, child: _column(context, c, titleKey, cols)),
              ]),
      );
    });
  }
}

// ── Charts ───────────────────────────────────────────────────────────────────

class MCNChart extends StatelessWidget {
  final String kind; // bar | line | area | pie | donut
  final dynamic data;
  final String x;
  final List<dynamic> y;
  final double height;
  final String? title;
  const MCNChart({super.key, required this.kind, this.data, this.x = 'label', this.y = const ['value'], this.height = 240, this.title});

  @override
  Widget build(BuildContext context) {
    final parentCard = context.findAncestorWidgetOfExactType<MCNCard>();
    final inCard = parentCard != null;
    final rows = mcnList(data);
    final t = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    if (rows.isEmpty) {
      final empty = SizedBox(
        height: height,
        child: const MCNEmpty(title: 'No chart data yet', icon: 'barchart3'),
      );
      return inCard ? empty : Card(child: empty);
    }
    final keys = y.map(mcnStr).toList();
    final round = kind == 'pie' || kind == 'donut';
    final legend = round ? [for (final r in rows) mcnStr(mcnGet(r, x))] : (keys.length > 1 ? keys.map(mcnHumanize).toList() : <String>[]);
    final showTitle = title != null && title!.isNotEmpty && (!inCard || parentCard.title != title);

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showTitle)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Text(title!, style: t.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
          ),
        SizedBox(height: height, child: round ? _pie(context, rows, keys.first) : _xy(context, rows, keys)),
        if (legend.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 14),
            child: Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                for (var i = 0; i < legend.length; i++)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: mcnPalette[i % mcnPalette.length].withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: mcnPalette[i % mcnPalette.length].withValues(alpha: 0.25),
                        width: 1,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: mcnPalette[i % mcnPalette.length],
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          legend[i],
                          style: t.bodySmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: scheme.onSurface,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
      ],
    );

    if (inCard) {
      return content;
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: content,
      ),
    );
  }

  Widget _pie(BuildContext context, List<dynamic> rows, String key) {
    final values = rows.map((r) => mcnNum(mcnGet(r, key)).toDouble()).toList();
    final total = values.fold<double>(0, (a, b) => a + b);
    if (total <= 0) return const MCNEmpty(title: 'No data yet', icon: 'piechart');
    final donut = kind == 'donut';
    return LayoutBuilder(builder: (context, size) {
      final r = math.min(size.maxWidth, size.maxHeight) / 2;
      return Stack(alignment: Alignment.center, children: [
        PieChart(PieChartData(
          sectionsSpace: 3,
          centerSpaceRadius: donut ? r * 0.58 : 0,
          sections: [
            for (var i = 0; i < values.length; i++)
              PieChartSectionData(
                value: values[i],
                color: mcnPalette[i % mcnPalette.length],
                radius: donut ? r * 0.35 : r * 0.90,
                title: donut ? '' : '${(values[i] / total * 100).round()}%',
                titleStyle: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                  shadows: [Shadow(color: Colors.black45, blurRadius: 4)],
                ),
              ),
          ],
        )),
        if (donut)
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                mcnCompact(total),
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.5,
                ),
              ),
              Text(
                'Total',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
      ]);
    });
  }

  Widget _xy(BuildContext context, List<dynamic> rows, List<String> keys) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final muted = Theme.of(context).textTheme.labelSmall?.copyWith(
      color: scheme.onSurfaceVariant,
      fontWeight: FontWeight.w500,
    );
    final maxV = rows.expand((r) => keys.map((k) => mcnNum(mcnGet(r, k)).toDouble())).fold<double>(0, math.max);
    final yStep = mcnNiceStep(maxV);
    final top = maxV <= 0 ? yStep * 4 : (maxV / yStep).ceil() * yStep;
    final step = (rows.length / 5).ceil().clamp(1, 1 << 30);
    final grid = FlGridData(
      show: true,
      drawVerticalLine: false,
      horizontalInterval: yStep,
      getDrawingHorizontalLine: (_) => FlLine(
        color: scheme.outlineVariant.withValues(alpha: isDark ? 0.3 : 0.4),
        strokeWidth: 1,
        dashArray: [5, 5],
      ),
    );

    Widget bottom(double v, TitleMeta meta) {
      final i = v.round();
      if (i < 0 || i >= rows.length || i % step != 0 || (v - i).abs() > 0.01) return const SizedBox.shrink();
      final label = mcnStr(mcnGet(rows[i], x));
      final display = label.length > 8 ? '${label.substring(0, 7)}…' : label;
      return SideTitleWidget(meta: meta, space: 6, child: Text(display, style: muted));
    }

    final titles = FlTitlesData(
      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      leftTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 42,
          interval: yStep,
          getTitlesWidget: (v, meta) => SideTitleWidget(
            meta: meta,
            space: 6,
            child: Text(mcnCompact(v), style: muted),
          ),
        ),
      ),
      bottomTitles: AxisTitles(
        sideTitles: SideTitles(showTitles: true, reservedSize: 26, interval: 1, getTitlesWidget: bottom),
      ),
    );

    if (kind == 'bar') {
      return LayoutBuilder(builder: (context, size) {
        final totalBars = rows.length * keys.length;
        final barWidth = math.max(8.0, math.min(22.0, (size.maxWidth - 50) / (totalBars * 1.7)));
        return BarChart(BarChartData(
          maxY: top,
          gridData: grid,
          titlesData: titles,
          borderData: FlBorderData(show: false),
          barTouchData: BarTouchData(
            touchTooltipData: BarTouchTooltipData(
              getTooltipColor: (_) => scheme.inverseSurface,
              getTooltipItem: (g, gi, rod, ri) {
                final rowLabel = mcnStr(mcnGet(rows[g.x], x));
                return BarTooltipItem(
                  '$rowLabel\n${mcnFormat(rod.toY)}',
                  TextStyle(color: scheme.onInverseSurface, fontSize: 12, fontWeight: FontWeight.w600),
                );
              },
            ),
          ),
          barGroups: [
            for (var i = 0; i < rows.length; i++)
              BarChartGroupData(
                x: i,
                barsSpace: 4,
                barRods: [
                  for (var k = 0; k < keys.length; k++)
                    BarChartRodData(
                      toY: mcnNum(mcnGet(rows[i], keys[k])).toDouble(),
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          mcnPalette[k % mcnPalette.length],
                          mcnPalette[k % mcnPalette.length].withValues(alpha: 0.72),
                        ],
                      ),
                      width: barWidth,
                      borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                      backDrawRodData: BackgroundBarChartRodData(
                        show: true,
                        toY: top,
                        color: scheme.surfaceContainerHighest.withValues(alpha: isDark ? 0.25 : 0.35),
                      ),
                    ),
                ],
              ),
          ],
        ));
      });
    }

    return LineChart(LineChartData(
      minY: 0,
      maxY: top,
      minX: 0,
      maxX: (rows.length - 1).toDouble().clamp(1, double.infinity),
      gridData: grid,
      titlesData: titles,
      borderData: FlBorderData(show: false),
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (_) => scheme.inverseSurface,
          getTooltipItems: (spots) => [
            for (final s in spots)
              LineTooltipItem(
                mcnFormat(s.y),
                TextStyle(color: scheme.onInverseSurface, fontSize: 12, fontWeight: FontWeight.w600),
              )
          ],
        ),
      ),
      lineBarsData: [
        for (var k = 0; k < keys.length; k++)
          LineChartBarData(
            spots: [
              for (var i = 0; i < rows.length; i++)
                FlSpot(i.toDouble(), mcnNum(mcnGet(rows[i], keys[k])).toDouble())
            ],
            isCurved: rows.length <= 20,
            preventCurveOverShooting: true,
            barWidth: 3.0,
            color: mcnPalette[k % mcnPalette.length],
            dotData: FlDotData(
              show: rows.length <= 16,
              getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                radius: 4,
                color: isDark ? const Color(0xFF0F172A) : Colors.white,
                strokeWidth: 2.5,
                strokeColor: mcnPalette[k % mcnPalette.length],
              ),
            ),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  mcnPalette[k % mcnPalette.length].withValues(alpha: kind == 'area' ? 0.28 : 0.08),
                  mcnPalette[k % mcnPalette.length].withValues(alpha: 0.0),
                ],
              ),
            ),
          ),
      ],
    ));
  }
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
  final _scroll = ScrollController();
  bool _busy = false;

  @override
  void dispose() { _input.dispose(); _scroll.dispose(); super.dispose(); }

  String _replyText(dynamic r) {
    if (r is String) return r;
    for (final k in ['reply', 'answer', 'message', 'response', 'text', 'data']) {
      final v = mcnGet(r, k);
      if (v != null) return _replyText(v);
    }
    return mcnStr(mcnGet(r, 'error') ?? r);
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  Future<void> _send(String text) async {
    final message = text.trim();
    if (message.isEmpty || _busy) return;
    HapticFeedback.lightImpact();
    final history = List<Map<String, String>>.of(_messages);
    setState(() { _messages.add({'role': 'user', 'content': message}); _busy = true; _input.clear(); });
    _toEnd();
    String reply;
    try { reply = _replyText(await widget.onSend(message, history)); } catch (e) { reply = 'Something went wrong: $e'; }
    if (!mounted) return;
    setState(() { _messages.add({'role': 'assistant', 'content': reply}); _busy = false; });
    _toEnd();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final shown = [if (widget.welcome != null) {'role': 'assistant', 'content': widget.welcome!}, ..._messages];
    final height = (MediaQuery.sizeOf(context).height * 0.55).clamp(320.0, 640.0);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        ListTile(
          leading: CircleAvatar(backgroundColor: scheme.primaryContainer, child: Icon(LucideIcons.bot, size: 18, color: scheme.onPrimaryContainer)),
          title: Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(_busy ? 'Typing…' : 'Online'),
        ),
        const Divider(height: 1),
        SizedBox(
          height: height,
          child: ListView(controller: _scroll, padding: const EdgeInsets.all(12), children: [
            for (final m in shown)
              Align(
                alignment: m['role'] == 'user' ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.75),
                  decoration: BoxDecoration(
                    color: m['role'] == 'user' ? scheme.primary : scheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18), topRight: const Radius.circular(18),
                      bottomLeft: Radius.circular(m['role'] == 'user' ? 18 : 4), bottomRight: Radius.circular(m['role'] == 'user' ? 4 : 18)),
                  ),
                  child: Text(m['content'] ?? '', style: t.bodyMedium?.copyWith(color: m['role'] == 'user' ? scheme.onPrimary : scheme.onSurface)),
                ),
              ),
            if (_busy) const Align(alignment: Alignment.centerLeft, child: Padding(padding: EdgeInsets.all(8),
                child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator.adaptive(strokeWidth: 2)))),
          ]),
        ),
        if (_messages.isEmpty && widget.suggestions.isNotEmpty)
          SizedBox(height: 48, child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12), children: [
            for (final s in widget.suggestions)
              Padding(padding: const EdgeInsets.only(right: 8), child: ActionChip(label: Text(mcnStr(s)), onPressed: () => _send(mcnStr(s)))),
          ])),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 8, 12),
          child: Row(children: [
            Expanded(child: TextField(
              controller: _input,
              textInputAction: TextInputAction.send,
              onSubmitted: _send,
              decoration: InputDecoration(hintText: 'Message', border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none)),
            )),
            const SizedBox(width: 6),
            IconButton.filled(icon: const Icon(LucideIcons.send, size: 18), onPressed: _busy ? null : () => _send(_input.text)),
          ]),
        ),
      ]),
    );
  }
}

// ── Landing pages and app design ─────────────────────────────────────────────
// navbar, hero, feature_grid/feature, pricing/plan, testimonials/testimonial,
// logo_cloud, faq/question, cta_band, site_footer, avatar, list_item,
// progress_ring and carousel: the same elements as the web kit, as native widgets.

/// Sections with an `id` register here, so "#pricing" links scroll to them.
final Map<String, GlobalKey> _anchors = {};
GlobalKey mcnAnchor(String id) => _anchors.putIfAbsent(id, () => GlobalKey(debugLabel: id));

String _slug(dynamic s) => mcnStr(s).toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '-').replaceAll(RegExp(r'^-|-$'), '');

/// Follow a link: "#pricing" scrolls to that section (other links open on the web).
void mcnFollow(dynamic link) {
  final l = mcnStr(link);
  if (!l.startsWith('#')) return;
  final ctx = _anchors[l.substring(1)]?.currentContext;
  if (ctx != null) Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 450), curve: Curves.easeOutCubic);
}

VoidCallback? _act(VoidCallback? handler, dynamic link) =>
    handler ?? (mcnStr(link).isEmpty ? null : () => mcnFollow(link));

Color mcnTint(BuildContext context, dynamic color) {
  final c = mcnStr(color).trim();
  if (c.isEmpty || c == 'primary') return Theme.of(context).colorScheme.primary;
  if (RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(c)) return Color(int.parse('FF${c.substring(1)}', radix: 16));
  const extra = {'rose': Color(0xFFF43F5E), 'teal': Color(0xFF14B8A6), 'cyan': Color(0xFF06B6D4), 'indigo': Color(0xFF6366F1)};
  return extra[c.toLowerCase()] ?? mcnTone(c);
}

String mcnInitials(dynamic name) {
  final words = mcnStr(name).split(RegExp(r'\s+')).where((w) => w.isNotEmpty).take(2);
  final s = words.map((w) => w[0].toUpperCase()).join();
  return s.isEmpty ? '?' : s;
}

Widget _anchored(dynamic id, Widget child) => mcnStr(id).isEmpty ? child : KeyedSubtree(key: mcnAnchor(mcnStr(id)), child: child);

class _MCNCta extends StatelessWidget {
  final dynamic label;
  final VoidCallback? onPressed;
  final String variant; // primary | outline | light
  final bool expand;
  const _MCNCta(this.label, {this.onPressed, this.variant = 'primary', this.expand = false});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final tap = onPressed == null ? null : () { HapticFeedback.lightImpact(); onPressed!(); };
    final shape = WidgetStatePropertyAll(RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)));
    const pad = WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 22, vertical: 14));
    final text = Text(mcnStr(label), style: const TextStyle(fontWeight: FontWeight.w700));
    final Widget b = switch (variant) {
      'outline' => OutlinedButton(onPressed: tap ?? () {}, style: ButtonStyle(shape: shape, padding: pad), child: text),
      'light' => FilledButton(onPressed: tap ?? () {}, style: ButtonStyle(shape: shape, padding: pad,
          backgroundColor: const WidgetStatePropertyAll(Colors.white), foregroundColor: WidgetStatePropertyAll(scheme.primary)), child: text),
      _ => FilledButton(onPressed: tap ?? () {}, style: ButtonStyle(shape: shape, padding: pad), child: text),
    };
    return expand ? SizedBox(width: double.infinity, child: b) : b;
  }
}

class _MCNSectionHead extends StatelessWidget {
  final dynamic eyebrow, title, subtitle;
  const _MCNSectionHead({this.eyebrow, this.title, this.subtitle});
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    if (title == null && subtitle == null && eyebrow == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 18, top: 8),
      child: Column(children: [
        if (eyebrow != null) Text(mcnStr(eyebrow).toUpperCase(),
            style: t.labelMedium?.copyWith(color: scheme.primary, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
        if (title != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(mcnStr(title), textAlign: TextAlign.center,
            style: t.headlineSmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.6))),
        if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(mcnStr(subtitle), textAlign: TextAlign.center,
            style: t.bodyLarge?.copyWith(color: scheme.onSurfaceVariant, height: 1.45))),
      ]),
    );
  }
}

class MCNNavbar extends StatelessWidget {
  final dynamic title, logo, links, cta, ctaLink;
  final VoidCallback? onCta;
  const MCNNavbar({super.key, this.title, this.logo, this.links, this.cta, this.ctaLink, this.onCta});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final items = mcnList(links);
    return Row(children: [
      Container(width: 34, height: 34, decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(10)),
          child: Icon(mcnIcon(logo ?? 'sparkles'), size: 18, color: scheme.onPrimary)),
      const SizedBox(width: 10),
      Expanded(child: Text(mcnStr(title), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800))),
      if (items.isNotEmpty) PopupMenuButton<String>(
        icon: const Icon(LucideIcons.menu, size: 22),
        onSelected: (l) => mcnFollow(l.startsWith('#') ? l : '#${_slug(l)}'),
        itemBuilder: (_) => [for (final l in items) PopupMenuItem(value: mcnStr(l), child: Text(mcnStr(l).replaceFirst('#', '')))],
      ),
      if (cta != null) _MCNCta(cta, onPressed: _act(onCta, ctaLink)),
    ]);
  }
}

class MCNHero extends StatelessWidget {
  final dynamic id, title, eyebrow, subtitle, primary, secondary, primaryLink, secondaryLink, image, note, variant;
  final VoidCallback? onPrimary, onSecondary;
  final List<Widget> children;
  const MCNHero({super.key, this.id, this.title, this.eyebrow, this.subtitle, this.primary, this.secondary, this.primaryLink,
      this.secondaryLink, this.image, this.note, this.variant, this.onPrimary, this.onSecondary, this.children = const []});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final dark = mcnStr(variant) == 'dark';
    final fg = dark ? Colors.white : scheme.onSurface;
    return _anchored(id, Container(
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: mcnStr(variant) == 'plain' ? null : LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: dark
              ? [Color.lerp(const Color(0xFF020617), scheme.primary, 0.45)!, const Color(0xFF020617)]
              : [scheme.primary.withValues(alpha: 0.16), scheme.primary.withValues(alpha: 0.03)],
        ),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (eyebrow != null) Container(
          margin: const EdgeInsets.only(bottom: 14),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(color: (dark ? Colors.white : scheme.primary).withValues(alpha: 0.12), borderRadius: BorderRadius.circular(99)),
          child: Text(mcnStr(eyebrow), style: t.labelMedium?.copyWith(color: dark ? Colors.white : scheme.primary, fontWeight: FontWeight.w600)),
        ),
        Text(mcnStr(title), style: t.headlineMedium?.copyWith(color: fg, fontWeight: FontWeight.w800, letterSpacing: -1, height: 1.08)),
        if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 12),
            child: Text(mcnStr(subtitle), style: t.bodyLarge?.copyWith(color: dark ? Colors.white70 : scheme.onSurfaceVariant, height: 1.45))),
        if (primary != null || secondary != null) Padding(padding: const EdgeInsets.only(top: 20), child: Wrap(spacing: 10, runSpacing: 10, children: [
          if (primary != null) _MCNCta(primary, onPressed: _act(onPrimary, primaryLink), variant: dark ? 'light' : 'primary'),
          if (secondary != null) _MCNCta(secondary, onPressed: _act(onSecondary, secondaryLink), variant: 'outline'),
        ])),
        if (note != null) Padding(padding: const EdgeInsets.only(top: 12),
            child: Text(mcnStr(note), style: t.bodySmall?.copyWith(color: dark ? Colors.white60 : scheme.onSurfaceVariant))),
        if (mcnStr(image).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20),
            child: ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.network(mcnStr(image), fit: BoxFit.cover))),
        if (children.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: dark
            // On the dark hero, text inside (ring labels, list rows) is light
            ? Theme(
                data: Theme.of(context).copyWith(colorScheme: scheme.copyWith(onSurface: Colors.white, onSurfaceVariant: Colors.white70)),
                child: DefaultTextStyle.merge(style: const TextStyle(color: Colors.white), child: MCNStack(children: children)))
            : MCNStack(children: children)),
      ]),
    ));
  }
}

class MCNFeatureGrid extends StatelessWidget {
  final dynamic id, title, subtitle, eyebrow, columns;
  final List<Widget> children;
  const MCNFeatureGrid({super.key, this.id, this.title, this.subtitle, this.eyebrow, this.columns, this.children = const []});
  @override
  Widget build(BuildContext context) => _anchored(id, Column(children: [
        _MCNSectionHead(eyebrow: eyebrow, title: title, subtitle: subtitle),
        MCNGrid(columns: columns == null ? 3 : mcnNum(columns).toInt(), children: children),
      ]));
}

class MCNFeature extends StatelessWidget {
  final dynamic title, description, icon;
  const MCNFeature({super.key, this.title, this.description, this.icon});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    return Card(child: Padding(padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(width: 42, height: 42, decoration: BoxDecoration(color: scheme.primary.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
          child: Icon(mcnIcon(icon ?? 'sparkles'), size: 20, color: scheme.primary)),
      const SizedBox(height: 14),
      Text(mcnStr(title), style: t.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
      if (description != null) Padding(padding: const EdgeInsets.only(top: 6),
          child: Text(mcnStr(description), style: t.bodyMedium?.copyWith(color: scheme.onSurfaceVariant, height: 1.45))),
    ])));
  }
}

class MCNPricing extends StatelessWidget {
  final dynamic id, title, subtitle, eyebrow;
  final List<Widget> children;
  const MCNPricing({super.key, this.id, this.title, this.subtitle, this.eyebrow, this.children = const []});
  @override
  Widget build(BuildContext context) => _anchored(id, Column(children: [
        _MCNSectionHead(eyebrow: eyebrow, title: title, subtitle: subtitle),
        MCNGrid(columns: 3, children: children),
      ]));
}

class MCNPlan extends StatelessWidget {
  final dynamic title, price, period, description, features, cta, link, highlight, badge;
  final VoidCallback? onClick;
  const MCNPlan({super.key, this.title, this.price, this.period, this.description, this.features, this.cta, this.link,
      this.highlight, this.badge, this.onClick});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final hi = mcnTruthy(highlight);
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: hi ? scheme.primary : scheme.outlineVariant, width: hi ? 2 : 1)),
      child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(mcnStr(title), style: t.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
          if (hi) Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(99)),
              child: Text(mcnStr(badge ?? 'Most popular'), style: t.labelSmall?.copyWith(color: scheme.onPrimary, fontWeight: FontWeight.w700))),
        ]),
        if (description != null) Text(mcnStr(description), style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
        const SizedBox(height: 14),
        Text.rich(TextSpan(text: mcnStr(price), style: t.headlineMedium?.copyWith(fontWeight: FontWeight.w800), children: [
          if (period != null) TextSpan(text: ' ${mcnStr(period)}', style: t.bodyMedium?.copyWith(color: scheme.onSurfaceVariant)),
        ])),
        const SizedBox(height: 14),
        for (final f in mcnList(features)) Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(LucideIcons.check, size: 18, color: scheme.primary),
          const SizedBox(width: 10),
          Expanded(child: Text(mcnStr(f))),
        ])),
        const SizedBox(height: 10),
        _MCNCta(cta ?? 'Get started', onPressed: _act(onClick, link), variant: hi ? 'primary' : 'outline', expand: true),
      ])),
    );
  }
}

class MCNTestimonials extends StatelessWidget {
  final dynamic id, title, subtitle, eyebrow;
  final List<Widget> children;
  const MCNTestimonials({super.key, this.id, this.title, this.subtitle, this.eyebrow, this.children = const []});
  @override
  Widget build(BuildContext context) => _anchored(id, Column(children: [
        _MCNSectionHead(eyebrow: eyebrow, title: title, subtitle: subtitle),
        MCNGrid(columns: 3, children: children),
      ]));
}

class MCNTestimonial extends StatelessWidget {
  final dynamic title, author, role, avatar, rating;
  const MCNTestimonial({super.key, this.title, this.author, this.role, this.avatar, this.rating});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final stars = (rating == null ? 5 : mcnNum(rating).toInt()).clamp(0, 5);
    return Card(child: Padding(padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [for (var i = 0; i < stars; i++) const Icon(Icons.star_rounded, size: 18, color: Color(0xFFFBBF24))]),
      const SizedBox(height: 10),
      Text('“${mcnStr(title)}”', style: t.bodyLarge?.copyWith(height: 1.45)),
      const SizedBox(height: 14),
      Row(children: [
        MCNAvatar(name: author, src: avatar, size: 38),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(mcnStr(author), style: t.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          if (role != null) Text(mcnStr(role), style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
        ])),
      ]),
    ])));
  }
}

class MCNLogoCloud extends StatelessWidget {
  final dynamic title, names;
  const MCNLogoCloud({super.key, this.title, this.names});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    return Column(children: [
      if (title != null) Text(mcnStr(title), style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
      const SizedBox(height: 10),
      Wrap(alignment: WrapAlignment.center, spacing: 22, runSpacing: 8, children: [
        for (final n in mcnList(names)) Text(mcnStr(n), style: t.titleMedium?.copyWith(fontWeight: FontWeight.w800,
            color: scheme.onSurfaceVariant.withValues(alpha: 0.7))),
      ]),
    ]);
  }
}

class MCNFaq extends StatelessWidget {
  final dynamic id, title, subtitle, eyebrow;
  final List<Widget> children;
  const MCNFaq({super.key, this.id, this.title, this.subtitle, this.eyebrow, this.children = const []});
  @override
  Widget build(BuildContext context) => _anchored(id, Column(children: [
        _MCNSectionHead(eyebrow: eyebrow, title: title, subtitle: subtitle),
        Card(clipBehavior: Clip.antiAlias, child: Column(children: [
          for (var i = 0; i < children.length; i++) ...[if (i > 0) const Divider(height: 1), children[i]],
        ])),
      ]));
}

class MCNQuestion extends StatelessWidget {
  final dynamic title, answer;
  final List<Widget> children;
  const MCNQuestion({super.key, this.title, this.answer, this.children = const []});
  @override
  Widget build(BuildContext context) => Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          title: Text(mcnStr(title), style: const TextStyle(fontWeight: FontWeight.w600)),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (answer != null) Text(mcnStr(answer), style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, height: 1.45)),
            ...children,
          ],
        ),
      );
}

class MCNCtaBand extends StatelessWidget {
  final dynamic id, title, subtitle, cta, link, secondary, secondaryLink;
  final VoidCallback? onClick, onSecondary;
  final List<Widget> children;
  const MCNCtaBand({super.key, this.id, this.title, this.subtitle, this.cta, this.link, this.secondary, this.secondaryLink,
      this.onClick, this.onSecondary, this.children = const []});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    return _anchored(id, Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [scheme.primary, Color.lerp(scheme.primary, Colors.white, 0.25)!]),
      ),
      child: Column(children: [
        Text(mcnStr(title), textAlign: TextAlign.center, style: t.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w800, letterSpacing: -0.5)),
        if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 10),
            child: Text(mcnStr(subtitle), textAlign: TextAlign.center, style: t.bodyLarge?.copyWith(color: Colors.white.withValues(alpha: 0.88)))),
        if (cta != null || secondary != null) Padding(padding: const EdgeInsets.only(top: 18), child: Wrap(spacing: 10, runSpacing: 10, alignment: WrapAlignment.center, children: [
          if (cta != null) _MCNCta(cta, onPressed: _act(onClick, link), variant: 'light'),
          if (secondary != null) _MCNCta(secondary, onPressed: _act(onSecondary, secondaryLink), variant: 'outline'),
        ])),
        if (children.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 18),
            child: Card(child: Padding(padding: const EdgeInsets.all(16), child: MCNStack(children: children)))),
      ]),
    ));
  }
}

class MCNSiteFooter extends StatelessWidget {
  final dynamic title, logo, text, links;
  const MCNSiteFooter({super.key, this.title, this.logo, this.text, this.links});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    return Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Column(children: [
      Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 28, height: 28, decoration: BoxDecoration(color: scheme.primary, borderRadius: BorderRadius.circular(8)),
            child: Icon(mcnIcon(logo ?? 'sparkles'), size: 15, color: scheme.onPrimary)),
        const SizedBox(width: 8),
        Text(mcnStr(title), style: t.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
      ]),
      if (mcnList(links).isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Wrap(spacing: 4, alignment: WrapAlignment.center, children: [
        for (final l in mcnList(links)) TextButton(onPressed: () => mcnFollow(mcnStr(l).startsWith('#') ? l : '#${_slug(l)}'),
            child: Text(mcnStr(l).replaceFirst('#', ''))),
      ])),
      if (text != null) Text(mcnStr(text), style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
    ]));
  }
}

class MCNAvatar extends StatelessWidget {
  final dynamic name, src, size, color, online;
  const MCNAvatar({super.key, this.name, this.src, this.size, this.color, this.online});
  @override
  Widget build(BuildContext context) {
    final px = size == null ? 40.0 : mcnNum(size).toDouble();
    final tint = mcnTint(context, color);
    final photo = mcnStr(src);
    return SizedBox(width: px, height: px, child: Stack(children: [
      Positioned.fill(child: CircleAvatar(
        backgroundColor: tint.withValues(alpha: 0.16),
        foregroundImage: photo.isEmpty ? null : NetworkImage(photo),
        child: Text(mcnInitials(name), style: TextStyle(color: tint, fontWeight: FontWeight.w700, fontSize: math.max(11, px * 0.36))),
      )),
      if (mcnTruthy(online)) Positioned(right: 0, bottom: 0, child: Container(width: px * 0.28, height: px * 0.28,
          decoration: BoxDecoration(color: const Color(0xFF10B981), shape: BoxShape.circle,
              border: Border.all(color: Theme.of(context).colorScheme.surface, width: 2)))),
    ]));
  }
}

class MCNListItem extends StatelessWidget {
  final dynamic title, subtitle, icon, color, avatar, person, trailing, badge, link;
  final VoidCallback? onClick;
  const MCNListItem({super.key, this.title, this.subtitle, this.icon, this.color, this.avatar, this.person, this.trailing,
      this.badge, this.link, this.onClick});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = Theme.of(context).textTheme;
    final tint = mcnTint(context, color);
    final tap = _act(onClick, link);
    final Widget? lead = (avatar != null || person != null)
        ? MCNAvatar(name: person ?? title, src: avatar, size: 42, color: color)
        : icon != null
            ? Container(width: 42, height: 42, decoration: BoxDecoration(color: tint.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(12)),
                child: Icon(mcnIcon(icon), size: 20, color: tint))
            : null;
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: tap == null ? null : () { HapticFeedback.selectionClick(); tap(); },
        child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12), child: Row(children: [
          if (lead != null) ...[lead, const SizedBox(width: 12)],
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(mcnStr(title), maxLines: 1, overflow: TextOverflow.ellipsis, style: t.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            if (subtitle != null) Text(mcnStr(subtitle), maxLines: 1, overflow: TextOverflow.ellipsis,
                style: t.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
          ])),
          if (badge != null) Padding(padding: const EdgeInsets.only(left: 8), child: MCNBadge(badge)),
          if (mcnStr(trailing).isNotEmpty) Padding(padding: const EdgeInsets.only(left: 8),
              child: Text(mcnFormat(trailing), style: t.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
          if (tap != null) Padding(padding: const EdgeInsets.only(left: 4), child: Icon(LucideIcons.chevronRight, size: 18, color: scheme.onSurfaceVariant)),
        ])),
      ),
    );
  }
}

class MCNProgressRing extends StatelessWidget {
  final dynamic value, label, center, color, size, thickness;
  const MCNProgressRing({super.key, this.value, this.label, this.center, this.color, this.size, this.thickness});
  @override
  Widget build(BuildContext context) {
    final px = size == null ? 96.0 : mcnNum(size).toDouble();
    final stroke = thickness == null ? math.max(6.0, px / 10) : mcnNum(thickness).toDouble();
    final pct = (mcnNum(value) / 100).clamp(0, 1).toDouble();
    final tint = mcnTint(context, color);
    final t = Theme.of(context).textTheme;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      SizedBox(width: px, height: px, child: Stack(alignment: Alignment.center, children: [
        SizedBox.expand(child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: pct),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (_, v, __) => CircularProgressIndicator(value: v, strokeWidth: stroke, strokeCap: StrokeCap.round,
              color: tint, backgroundColor: tint.withValues(alpha: 0.16)),
        )),
        Text(center != null ? mcnStr(center) : '${(pct * 100).round()}%',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: math.max(12, px * 0.22))),
      ])),
      if (label != null) Padding(padding: const EdgeInsets.only(top: 8),
          child: Text(mcnStr(label), style: t.bodySmall?.copyWith(fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.onSurfaceVariant))),
    ]);
  }
}

class MCNCarousel extends StatelessWidget {
  final dynamic title, width;
  final List<Widget> children;
  const MCNCarousel({super.key, this.title, this.width, this.children = const []});
  @override
  Widget build(BuildContext context) {
    final w = width == null ? 260.0 : mcnNum(width).toDouble();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (title != null) Padding(padding: const EdgeInsets.only(bottom: 10),
          child: Text(mcnStr(title), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        clipBehavior: Clip.none,
        physics: const BouncingScrollPhysics(),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          for (var i = 0; i < children.length; i++) Padding(
            padding: EdgeInsets.only(right: i == children.length - 1 ? 0 : 12),
            child: SizedBox(width: w, child: children[i]),
          ),
        ]),
      ),
    ]);
  }
}
