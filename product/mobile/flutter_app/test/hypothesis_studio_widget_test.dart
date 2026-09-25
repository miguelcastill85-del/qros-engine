import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/main.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';

Future<void> _scrollTo(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  final scrollable = find.descendant(
    of: find.byKey(const Key('hypothesis-studio-screen')),
    matching: find.byType(Scrollable),
  ).first;
  await tester.scrollUntilVisible(target, 320.0, scrollable: scrollable);
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  // Verify actual hit-testable position, not merely a lazily materialized item.
  for (var i = 0; i < 6; i++) {
    final center = tester.getCenter(target);
    final rootHeight = tester.view.physicalSize.height / tester.view.devicePixelRatio;
    if (center.dy > 0 && center.dy < rootHeight - 96) break;
    await tester.drag(scrollable, const Offset(0, -150));
    await tester.pumpAndSettle();
  }
  final finalCenter = tester.getCenter(target);
  final rootHeight = tester.view.physicalSize.height / tester.view.devicePixelRatio;
  expect(finalCenter.dy, greaterThan(0));
  expect(finalCenter.dy, lessThan(rootHeight - 80));
}

void main() {
  testWidgets('new mobile hypothesis/factory flow computes 144 without economic results', (tester) async {
    final store = UniverseSessionStore();
    await tester.pumpWidget(QrosApp(universeStore: store));
    await tester.tap(find.text('Hipótesis').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('hypothesis-studio-screen')), findsOneWidget);
    await _scrollTo(tester, 'g1-raw-count');
    expect(tester.widget<Text>(find.byKey(const Key('g1-raw-count'))).data, '144');
    await _scrollTo(tester, 'g1-analyze');
    await tester.tap(find.byKey(const Key('g1-analyze')));
    await tester.pumpAndSettle();
    expect(store.latest, isNotNull);
    expect(store.latest!.blueprint.rawBirths, 144);
    await _scrollTo(tester, 'g1-open-factory');
    expect(find.byKey(const Key('g1-saved-hash')), findsOneWidget);
    await tester.tap(find.byKey(const Key('g1-open-factory')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('factory-screen')), findsOneWidget);
    expect(find.byKey(const Key('factory-verified-hash')), findsOneWidget);
    expect(store.latest!.blueprint.canonicalObject()['scientific_authority'], false);
    expect(store.latest!.blueprint.canonicalObject()['holdout_open'], false);
    store.dispose();
  });

  testWidgets('invalid empty side fails closed without saving an approved strategy', (tester) async {
    final store=UniverseSessionStore();
    await tester.pumpWidget(QrosApp(universeStore:store));
    await tester.tap(find.text('Hipótesis').last);
    await tester.pumpAndSettle();
    await _scrollTo(tester,'g1-side-SELL');
    await tester.tap(find.byKey(const Key('g1-side-SELL')));
    await tester.pumpAndSettle();
    await _scrollTo(tester,'g1-side-BUY');
    await tester.tap(find.byKey(const Key('g1-side-BUY')));
    await tester.pumpAndSettle();
    await _scrollTo(tester,'g1-analyze');
    await tester.tap(find.byKey(const Key('g1-analyze')));
    await tester.pumpAndSettle();
    expect(store.latest, isNull);
    expect(find.byKey(const Key('g1-error')), findsOneWidget);
    store.dispose();
  });
}
