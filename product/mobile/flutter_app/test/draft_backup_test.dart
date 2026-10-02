import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/research_store.dart';
import 'package:qros_mobile_studio/ui/draft_backup_screen.dart';

Future<ResearchStore> seeded() async {
  final s = ResearchStore(
    clock: () => DateTime.utc(2026, 9, 30),
    vault: MemoryLocalVault(),
  );
  await s.createLocalDraft(
    title: 'Idea propia',
    thesis: 'Hipótesis causal de prueba sin resultados.',
    symbol: 'NQX',
    side: 'SELL',
    timeframe: 'H4',
  );
  return s;
}

void main() {
  test('backup survives a fresh store, retains drafts and grants no authority',
      () async {
    final a = await seeded();
    final b = ResearchStore(vault: MemoryLocalVault());
    final payload = a.exportDraftBackup();
    expect(payload, isNot(contains('SIMULATED_SAMPLE')));
    expect(await b.restoreDraftBackup(payload), 1);
    expect(b.projects.first.title, 'Idea propia');
    expect(b.projects.first.side, 'SELL');
    expect(b.projects.first.createdAt, DateTime.utc(2026, 9, 30));
    expect(b.projects.first.toEvidenceRecord()['scientific_approval'], false);
    expect(await b.restoreDraftBackup(payload), 0);
    expect(b.localDraftCount, 1);
    expect(b.projects.where((p) => p.isSample).length, 1);
    a.dispose();
    b.dispose();
  });

  test('invalid second row leaves the whole store unchanged', () async {
    final a = await seeded();
    final b = await seeded();
    final data =
        jsonDecode(a.exportDraftBackup()) as Map<String, dynamic>;
    final first =
        Map<String, dynamic>.from((data['drafts'] as List).first as Map);
    first['title'] = 'Otra idea';
    data['drafts'] = [first, {...first, 'side': 'INVALID'}];
    final before = b.exportDraftBackup();
    await expectLater(
        b.restoreDraftBackup(jsonEncode(data)), throwsFormatException);
    expect(b.exportDraftBackup(), before);
    a.dispose();
    b.dispose();
  });

  test('import rejects injected authority, unsupported version and malformed data',
      () async {
    final a = await seeded();
    final data =
        jsonDecode(a.exportDraftBackup()) as Map<String, dynamic>;
    (data['drafts'] as List).first['scientific_approval'] = true;
    await expectLater(
        a.restoreDraftBackup(jsonEncode(data)), throwsFormatException);
    await expectLater(
        a.restoreDraftBackup('{"schema":"future","drafts":[]}'),
        throwsFormatException);
    await expectLater(a.restoreDraftBackup('not json'), throwsFormatException);
    await expectLater(
        a.restoreDraftBackup(
            '{"schema":"QROS_LOCAL_DRAFT_BACKUP_V1","drafts":{} }'),
        throwsFormatException);
    expect(a.localDraftCount, 1);
    a.dispose();
  });

  test('invalid normalized date and oversized input reject without mutation',
      () async {
    final a = await seeded();
    final data =
        jsonDecode(a.exportDraftBackup()) as Map<String, dynamic>;
    (data['drafts'] as List).first['created_at'] =
        '2026-02-31T00:00:00.000Z';
    await expectLater(
        a.restoreDraftBackup(jsonEncode(data)), throwsFormatException);
    await expectLater(
        a.restoreDraftBackup(
            ' ' * (ResearchStore.maxBackupCharacters + 1)),
        throwsFormatException);
    expect(a.localDraftCount, 1);
    a.dispose();
  });

  test('existing drafts survive merging and imported identifiers stay unique',
      () async {
    final a = await seeded();
    final b = await seeded();
    await b.createLocalDraft(
      title: 'Segunda idea',
      thesis: 'Otra hipótesis observable local.',
      symbol: 'XAUUSD',
      side: 'BUY',
      timeframe: 'M15',
    );
    expect(await a.restoreDraftBackup(b.exportDraftBackup()), 1);
    expect(a.localDraftCount, 2);
    expect(a.projects.map((p) => p.id).toSet().length, a.projects.length);
    a.dispose();
    b.dispose();
  });

  test('draft limit uses the recoverable validation error handled by the form',
      () async {
    final s = ResearchStore(vault: MemoryLocalVault());
    for (var i = 0; i < ResearchStore.maxDrafts; i++) {
      await s.createLocalDraft(
        title: 'Idea $i',
        thesis: 'Hipótesis local para comprobar capacidad.',
        symbol: 'NQX',
        side: 'BUY',
        timeframe: 'M15',
      );
    }
    await expectLater(
      s.createLocalDraft(
        title: 'Idea extra',
        thesis: 'Hipótesis fuera de capacidad.',
        symbol: 'NQX',
        side: 'BUY',
        timeframe: 'M15',
      ),
      throwsArgumentError,
    );
    expect(s.localDraftCount, ResearchStore.maxDrafts);
    s.dispose();
  });

  testWidgets('restore UI rejects malformed input then imports and clears text',
      (tester) async {
    final a = await seeded();
    final b = ResearchStore(vault: MemoryLocalVault());
    await tester.pumpWidget(MaterialApp(home: DraftBackupScreen(store: b)));
    await tester.enterText(
        find.byKey(const Key('backup-input')), 'invalid');
    await tester.ensureVisible(find.byKey(const Key('restore-drafts')));
    await tester.tap(find.byKey(const Key('restore-drafts')));
    await tester.pumpAndSettle();
    expect(find.text('El respaldo no es JSON válido.'), findsOneWidget);
    expect(b.localDraftCount, 0);
    await tester.enterText(
        find.byKey(const Key('backup-input')), a.exportDraftBackup());
    await tester.ensureVisible(find.byKey(const Key('restore-drafts')));
    await tester.tap(find.byKey(const Key('restore-drafts')));
    await tester.pumpAndSettle();
    expect(b.localDraftCount, 1);
    expect(find.textContaining('Borradores recuperados: 1'), findsOneWidget);
    final field =
        tester.widget<TextField>(find.byKey(const Key('backup-input')));
    expect(field.controller!.text, isEmpty);
    await tester.pumpWidget(const SizedBox());
    a.dispose();
    b.dispose();
  });
}
