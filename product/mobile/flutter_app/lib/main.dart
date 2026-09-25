import 'package:flutter/material.dart';
import 'core/research_store.dart';
import 'core/verified_demo.dart';
import 'core/universe_store.dart';
import 'ui/app_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const QrosApp());
}

class QrosApp extends StatefulWidget {
  const QrosApp({super.key, this.store, this.demoGateway, this.universeStore});

  final ResearchStore? store;
  final DemoGateway? demoGateway;
  final UniverseSessionStore? universeStore;

  @override
  State<QrosApp> createState() => _QrosAppState();
}

class _QrosAppState extends State<QrosApp> {
  late final ResearchStore _store = widget.store ?? ResearchStore();
  late final UniverseSessionStore _universeStore = widget.universeStore ?? UniverseSessionStore();

  @override
  void dispose() {
    if (widget.store == null) _store.dispose();
    if (widget.universeStore == null) _universeStore.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const teal = Color(0xFF36D7B7);
    return MaterialApp(
      title: 'QROS Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF09111F),
        colorScheme: const ColorScheme.dark(
          primary: teal,
          onPrimary: Color(0xFF071A1B),
          surface: Color(0xFF121E31),
          onSurface: Color(0xFFF3F7FF),
          secondary: Color(0xFFFBD67A),
          error: Color(0xFFF28F94),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF09111F),
          foregroundColor: Color(0xFFF3F7FF),
          centerTitle: false,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF16263A),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFF33485E)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: teal, width: 1.5),
          ),
          errorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFFF28F94)),
          ),
          focusedErrorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Color(0xFFF28F94), width: 1.5),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        navigationBarTheme: const NavigationBarThemeData(
          backgroundColor: Color(0xFF101C2E),
          indicatorColor: Color(0xFF245D57),
          labelTextStyle: WidgetStatePropertyAll(TextStyle(fontSize: 11)),
        ),
      ),
      home: QrosShell(store: _store, universeStore: _universeStore, demoGateway: widget.demoGateway ?? const HttpsDemoGateway()),
    );
  }
}
