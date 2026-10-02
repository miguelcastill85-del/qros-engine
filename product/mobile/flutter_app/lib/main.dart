import 'package:flutter/material.dart';
import 'core/research_store.dart';
import 'core/g5_snapshot.dart';
import 'core/verified_demo.dart';
import 'core/universe_store.dart';
import 'core/local_vault.dart';
import 'core/session_client.dart';
import 'ui/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final vault = SecureLocalVault();
  final researchStore = ResearchStore(vault: vault);
  final universeStore = UniverseSessionStore(vault: vault);
  const sessionGateway = HttpsSessionGateway();
  final sessionStore = SessionStore(vault: vault, gateway: sessionGateway);
  final jobStore = SyntheticJobStore(
    vault: vault,
    sessionStore: sessionStore,
    gateway: sessionGateway,
  );
  await researchStore.initialize();
  await universeStore.initialize();
  await sessionStore.initialize();
  await jobStore.initialize();
  runApp(QrosApp(
    store: researchStore,
    universeStore: universeStore,
    sessionGateway: sessionGateway,
    sessionStore: sessionStore,
    jobStore: jobStore,
  ));
}

class QrosApp extends StatefulWidget {
  const QrosApp({
    super.key,
    this.store,
    this.demoGateway,
    this.universeStore,
    this.g5Gateway,
    this.sessionGateway,
    this.sessionStore,
    this.jobStore,
  });

  final ResearchStore? store;
  final DemoGateway? demoGateway;
  final UniverseSessionStore? universeStore;
  final G5SnapshotGateway? g5Gateway;
  final SessionGateway? sessionGateway;
  final SessionStore? sessionStore;
  final SyntheticJobStore? jobStore;

  @override
  State<QrosApp> createState() => _QrosAppState();
}

class _QrosAppState extends State<QrosApp> {
  late final ResearchStore _store = widget.store ?? ResearchStore();
  late final UniverseSessionStore _universeStore =
      widget.universeStore ?? UniverseSessionStore();
  late final SessionGateway _sessionGateway =
      widget.sessionGateway ?? const HttpsSessionGateway();
  late final MemoryLocalVault _ephemeralVault = MemoryLocalVault();
  late final SessionStore _sessionStore = widget.sessionStore ??
      SessionStore(vault: _ephemeralVault, gateway: _sessionGateway);
  late final SyntheticJobStore _jobStore = widget.jobStore ??
      SyntheticJobStore(
        vault: _ephemeralVault,
        sessionStore: _sessionStore,
        gateway: _sessionGateway,
      );

  @override
  void dispose() {
    if (widget.store == null) _store.dispose();
    if (widget.universeStore == null) _universeStore.dispose();
    if (widget.sessionStore == null) _sessionStore.dispose();
    if (widget.jobStore == null) _jobStore.dispose();
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
            borderSide:
                const BorderSide(color: Color(0xFFF28F94), width: 1.5),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        navigationBarTheme: const NavigationBarThemeData(
          backgroundColor: Color(0xFF101C2E),
          indicatorColor: Color(0xFF245D57),
          labelTextStyle: WidgetStatePropertyAll(TextStyle(fontSize: 11)),
        ),
      ),
      home: QrosShell(
        store: _store,
        universeStore: _universeStore,
        sessionStore: _sessionStore,
        jobStore: _jobStore,
        demoGateway: widget.demoGateway ?? const HttpsDemoGateway(),
        g5Gateway: widget.g5Gateway ??
            const HttpsG5SnapshotGateway(
              G5SnapshotVerifier(G9LiveTrust.profile),
              allowedOrigin: G9LiveTrust.origin,
            ),
      ),
    );
  }
}
