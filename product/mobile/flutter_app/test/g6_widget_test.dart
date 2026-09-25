import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/main.dart';

void main(){
  testWidgets('G6 shield shortcut and signed synthetic offline verification', (tester) async {
    await tester.pumpWidget(const QrosApp());
    // G1 five-tab shell is retained; opt-in G6 is an independent shield FAB.
    expect(find.text('Hipótesis'),findsWidgets);
    await tester.tap(find.byKey(const Key('open-g6-proof')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('g6-screen')),findsOneWidget);
    await tester.tap(find.byKey(const Key('g6-offline')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('g6-verified')),findsOneWidget);
    expect(find.byKey(const Key('g6-denied')),findsNothing);
    expect(find.textContaining('CUSTODIA EXTERNA: NO DESPLEGADA'),findsOneWidget);
    expect(find.text('APPROVED_FINAL'),findsNothing);
  });
}
