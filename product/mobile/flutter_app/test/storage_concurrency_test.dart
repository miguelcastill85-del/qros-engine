import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/research_store.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';
import 'package:qros_mobile_studio/core/universe_ir.dart';

Future<ResearchProject> create(ResearchStore s, String title) =>
    s.createLocalDraft(title: title, thesis: 'Hipótesis sintética de persistencia.',
      symbol: 'NQX', side: 'BUY', timeframe: 'M15');

class PausedVault extends MemoryLocalVault {
  final entered = Completer<void>();
  final release = Completer<void>();
  bool first = true;
  @override
  Future<void> write(String key, String value) async {
    if (first) {
      first = false;
      entered.complete();
      await release.future;
    }
    await super.write(key, value);
  }
}

class FailOnceVault extends MemoryLocalVault {
  bool fail = true;
  @override
  Future<void> write(String key, String value) async {
    if (fail) { fail = false; throw StateError('synthetic storage error'); }
    await super.write(key, value);
  }
}

void main() {
  test('overlapping draft saves retain both records with unique IDs after restart', () async {
    final vault = PausedVault();
    final s = ResearchStore(vault: vault);
    final first = create(s, 'Primera idea');
    await vault.entered.future;
    final second = create(s, 'Segunda idea');
    vault.release.complete();
    final created = await Future.wait([first, second]);
    expect(created.map((p) => p.id).toSet().length, 2);
    final restored = ResearchStore(vault: vault);
    await restored.initialize();
    expect(restored.localDraftCount, 2);
    expect(restored.projects.where((p) => !p.isSample).map((p) => p.title).toSet(),
      {'Primera idea', 'Segunda idea'});
    s.dispose(); restored.dispose();
  });

  test('mutation hydrates previously saved drafts even without explicit initialize', () async {
    final vault = MemoryLocalVault();
    final first = ResearchStore(vault: vault);
    await create(first, 'Idea anterior');
    first.dispose();
    final next = ResearchStore(vault: vault);
    await create(next, 'Idea nueva');
    expect(next.localDraftCount, 2);
    expect(next.projects.where((p) => !p.isSample).map((p) => p.id).toSet().length, 2);
    next.dispose();
  });

  test('corrupt storage is preserved when a later create is attempted', () async {
    const corrupt = '{"schema":';
    final vault = MemoryLocalVault({ResearchStore.storageKey: corrupt});
    final s = ResearchStore(vault: vault);
    await s.initialize();
    await expectLater(create(s, 'No sobrescribir'), throwsA(isA<LocalPersistenceException>()));
    expect(vault.snapshot[ResearchStore.storageKey], corrupt);
    expect(s.localDraftCount, 0);
    s.dispose();
  });

  test('failed queued write does not poison the next valid operation', () async {
    final vault = FailOnceVault();
    final s = ResearchStore(vault: vault);
    final failed = expectLater(create(s, 'Falla de prueba'),
      throwsA(isA<LocalPersistenceException>()));
    final successful = create(s, 'Idea recuperada');
    await failed;
    expect((await successful).id, 'LOCAL-0001');
    final restarted = ResearchStore(vault: vault);
    await restarted.initialize();
    expect(restarted.projects.first.title, 'Idea recuperada');
    expect(restarted.localDraftCount, 1);
    s.dispose(); restarted.dispose();
  });

  test('saved ID above sequence rejects hydration before IDs can collide', () async {
    final vault = MemoryLocalVault();
    final s = ResearchStore(vault: vault);
    await create(s, 'Idea original');
    final raw = jsonDecode(vault.snapshot[ResearchStore.storageKey]!) as Map<String, dynamic>;
    (raw['drafts'] as List).first['id'] = 'LOCAL-0002';
    final tampered = jsonEncode(raw);
    await vault.write(ResearchStore.storageKey, tampered);
    final restored = ResearchStore(vault: vault);
    await restored.initialize();
    expect(restored.storageWarning, 'LOCAL_STORE_RECORD_INVALID');
    await expectLater(create(restored, 'No colisionar'),
      throwsA(isA<LocalPersistenceException>()));
    expect(vault.snapshot[ResearchStore.storageKey], tampered);
    s.dispose(); restored.dispose();
  });

  test('universe clear follows pending save durably in invocation order', () async {
    final vault = PausedVault();
    final s = UniverseSessionStore(vault: vault);
    final saving = s.save(title: 'Universo de prueba',
      thesis: 'Hipótesis sintética con persistencia ordenada.',
      blueprint: UniverseBlueprint.sample());
    await vault.entered.future;
    final clearing = s.clear();
    vault.release.complete();
    await saving;
    await clearing;
    final restarted = UniverseSessionStore(vault: vault);
    await restarted.initialize();
    expect(s.latest, isNull);
    expect(restarted.latest, isNull);
    expect(vault.snapshot.containsKey(UniverseSessionStore.storageKey), false);
    s.dispose(); restarted.dispose();
  });

  test('corrupt universe is not overwritten by save or clear', () async {
    final vault = MemoryLocalVault({UniverseSessionStore.storageKey: 'broken'});
    final s = UniverseSessionStore(vault: vault);
    await s.initialize();
    await expectLater(s.save(title: 'Universo nuevo',
      thesis: 'Hipótesis sintética sin sobrescritura silenciosa.',
      blueprint: UniverseBlueprint.sample()), throwsA(isA<LocalPersistenceException>()));
    await expectLater(s.clear(), throwsA(isA<LocalPersistenceException>()));
    expect(vault.snapshot[UniverseSessionStore.storageKey], 'broken');
    s.dispose();
  });
}
