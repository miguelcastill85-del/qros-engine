import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/main.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';

void main() {
  testWidgets('new mobile hypothesis/factory flow computes 144 without economic results', (tester) async {
    final store = UniverseSessionStore();
    await tester.pumpWidget(QrosApp(universeStore: store));
    await tester.tap(find.text('Hipótesis').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('hypothesis-studio-screen')), findsOneWidget);
    expect(find.text('144'), findsOneWidget);
    await tester.scrollUntilVisible(find.byKey(const Key('g1-analyze')), 220.0,
      scrollable: find.byType(Scrollable).last);
    await tester.tap(find.byKey(const Key('g1-analyze')));
    await tester.pumpAndSettle();
    expect(store.latest, isNotNull);
    expect(store.latest!.blueprint.rawBirths, 144);
    expect(find.byKey(const Key('g1-saved-hash')), findsOneWidget);
    await tester.tap(find.byKey(const Key('g1-open-factory')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('factory-screen')), findsOneWidget);
    expect(find.byKey(const Key('factory-verified-hash')), findsOneWidget);
    expect(find.text('NO EJECUTADO'), findsWidgets);
    expect(find.textContaining('0'), findsWidgets);
    store.dispose();
  });

  testWidgets('invalid empty side fails closed without saving an approved strategy', (tester) async {
    final store=UniverseSessionStore();
    await tester.pumpWidget(QrosApp(universeStore:store));
    await tester.tap(find.text('Hipótesis').last);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('g1-side-SELL')), 180.0,
      scrollable: find.byType(Scrollable).last);
    await tester.tap(find.byKey(const Key('g1-side-SELL')));
    await tester.tap(find.byKey(const Key('g1-side-BUY')));
    await tester.scrollUntilVisible(find.byKey(const Key('g1-analyze')), 220.0,
      scrollable: find.byType(Scrollable).last);
    await tester.tap(find.byKey(const Key('g1-analyze')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('g1-error')), findsOneWidget);
    expect(store.latest, isNull);
    store.dispose();
  });
}
