import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/main.dart';
import 'package:qros_mobile_studio/core/research_store.dart';
import 'package:qros_mobile_studio/core/verified_demo.dart';

class DemoGatewayStub implements DemoGateway {
  @override
  Future<VerifiedDemo> fetch(String origin, String token) async => const VerifiedDemo(
    projectTitle: 'Ruptura y recuperacion DEMO',
    anchorHash: DemoTrust.anchorSha256, anchorSequence: 1,
    symbol: 'XAUUSD', side: 'BUY', timeframe: 'M15');
}

void main() {
  testWidgets('home and all four mobile destinations render honest offline states', (tester) async {
    final store = ResearchStore();
    await tester.pumpWidget(QrosApp(store: store));
    expect(find.text('QROS'), findsOneWidget);
    expect(find.text('TEST_ONLY'), findsOneWidget);
    expect(find.textContaining('Motor desconectado'), findsOneWidget);
    await tester.tap(find.text('Proyectos').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('projects-screen')), findsOneWidget);
    expect(find.text('DEMO-001'), findsOneWidget);
    await tester.tap(find.text('Historial').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('Evento visual simulado'), findsOneWidget);
    await tester.tap(find.text('Seguridad').last);
    await tester.pumpAndSettle();
    expect(find.text('Permisos científicos'), findsOneWidget);
    store.dispose();
  });

  testWidgets('a hypothesis is a local draft, not an approved research contract', (tester) async {
    final store = ResearchStore();
    await tester.pumpWidget(QrosApp(store: store));
    await tester.tap(find.byKey(const Key('new-project-action')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('draft-title')), 'Hipótesis causal M15');
    await tester.enterText(find.byKey(const Key('draft-thesis')), 'Se observa una ruptura y recuperación antes de la entrada hipotética.');
    await tester.scrollUntilVisible(find.byKey(const Key('new-project-submit')), 260.0, scrollable: find.byType(Scrollable).last);
    await tester.tap(find.byKey(const Key('new-project-submit')));
    await tester.pumpAndSettle();
    expect(store.localDraftCount, 1);
    expect(store.projects.first.state, 'LOCAL_DRAFT_NOT_FROZEN');
    expect(find.text('LOCAL-0001'), findsOneWidget);
    store.dispose();
  });

  testWidgets('mobile remote DEMO is read-only and never marks approval', (tester) async {
    final store = ResearchStore();
    await tester.pumpWidget(QrosApp(store: store, demoGateway: DemoGatewayStub()));
    await tester.tap(find.text('Seguridad').last);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('open-remote-demo')), 220.0,
      scrollable: find.byType(Scrollable).last);
    await tester.tap(find.byKey(const Key('open-remote-demo')));
    await tester.pumpAndSettle();
    expect(find.textContaining('SOLO LECTURA'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('remote-demo-url')), 'https://valid.example.com');
    await tester.enterText(find.byKey(const Key('remote-demo-token')), 'test_example_0123456789_0123456789');
    await tester.tap(find.byKey(const Key('remote-demo-fetch')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('remote-demo-verified')), findsOneWidget);
    expect(find.textContaining('SIMULATED_SAMPLE'), findsOneWidget);
    expect(store.engineConnected, false);
    expect(store.actualBacktests, 0);
    store.dispose();
  });

  testWidgets('security screen copies only synthetic evidence and has no PASS action', (tester) async {
    final store = ResearchStore();
    await tester.pumpWidget(QrosApp(store: store));
    await tester.tap(find.text('Seguridad').last);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('copy-evidence-action')), 260.0, scrollable: find.byType(Scrollable).last);
    expect(find.textContaining('Copiar JSON TEST_ONLY'), findsOneWidget);
    expect(find.text('APPROVED_FINAL'), findsNothing);
    expect(store.engineConnected, false);
    store.dispose();
  });
}
