import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/research_store.dart';
import 'package:qros_mobile_studio/core/universe_ir.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';

void main() {
  test('project create edit delete roundtrip is durable and local-only',
      () async {
    final vault = MemoryLocalVault();
    final a = ResearchStore(
      clock: () => DateTime.utc(2026, 10, 2),
      vault: vault,
    );
    final created = await a.createLocalDraft(
      title: 'Idea durable',
      thesis: 'Hipótesis observable guardada de forma local.',
      symbol: 'XAUUSD',
      side: 'BUY',
      timeframe: 'M15',
    );
    await a.updateLocalDraft(
      id: created.id,
      title: 'Idea durable editada',
      thesis: 'Hipótesis observable editada y guardada localmente.',
      symbol: 'NQX',
      side: 'SELL',
      timeframe: 'H1',
    );

    final b = ResearchStore(vault: vault);
    await b.initialize();
    expect(b.localDraftCount, 1);
    expect(b.projects.first.title, 'Idea durable editada');
    expect(b.projects.first.symbol, 'NQX');
    expect(b.projects.first.toEvidenceRecord()['scientific_approval'], false);

    await b.deleteLocalDraft(created.id);
    final c = ResearchStore(vault: vault);
    await c.initialize();
    expect(c.localDraftCount, 0);
    expect(c.projects.single.isSample, true);
    a.dispose();
    b.dispose();
    c.dispose();
  });

  test('legacy V1 secure payload migrates deterministically to V2', () async {
    final legacy = jsonEncode({
      'schema': ResearchStore.storageSchemaV1,
      'drafts': [
        {
          'title': 'Migración local',
          'thesis': 'Hipótesis válida recuperada desde un esquema anterior.',
          'symbol': 'XAUUSD',
          'side': 'BUY',
          'timeframe': 'M15',
          'created_at': '2026-10-02T00:00:00.000Z',
        }
      ],
    });
    final vault = MemoryLocalVault({ResearchStore.storageKey: legacy});
    final store = ResearchStore(vault: vault);
    await store.initialize();
    expect(store.storageWarning, isNull);
    expect(store.localDraftCount, 1);
    final upgraded =
        jsonDecode(vault.snapshot[ResearchStore.storageKey]!)
            as Map<String, dynamic>;
    expect(upgraded['schema'], ResearchStore.storageSchemaV2);
    expect(upgraded['draft_sequence'], 1);
    store.dispose();
  });

  test('corrupt secure project state fails closed without injecting drafts',
      () async {
    final vault =
        MemoryLocalVault({ResearchStore.storageKey: '{"schema":'});
    final store = ResearchStore(vault: vault);
    await store.initialize();
    expect(store.localDraftCount, 0);
    expect(store.projects.single.isSample, true);
    expect(store.storageWarning, 'LOCAL_STORE_CORRUPT_JSON');
    store.dispose();
  });

  test('synthetic universe survives restart only when hashes still match',
      () async {
    final vault = MemoryLocalVault();
    final a = UniverseSessionStore(vault: vault);
    final saved = await a.save(
      title: 'Universo durable',
      thesis: 'Hipótesis sintética para validar persistencia sin PnL.',
      blueprint: UniverseBlueprint.sample(),
    );
    final b = UniverseSessionStore(vault: vault);
    await b.initialize();
    expect(b.storageWarning, isNull);
    expect(b.latest, isNotNull);
    expect(b.latest!.searchSpaceSha256, saved.searchSpaceSha256);
    expect(b.latest!.toyEnumerationSha256, saved.toyEnumerationSha256);
    expect(b.latest!.blueprint.canonicalObject()['scientific_authority'],
        false);

    final tampered =
        jsonDecode(vault.snapshot[UniverseSessionStore.storageKey]!)
            as Map<String, dynamic>;
    tampered['search_space_sha256'] = List.filled(64, '0').join();
    final badVault = MemoryLocalVault({
      UniverseSessionStore.storageKey: jsonEncode(tampered),
    });
    final c = UniverseSessionStore(vault: badVault);
    await c.initialize();
    expect(c.latest, isNull);
    expect(c.storageWarning, 'UNIVERSE_STORE_HASH_MISMATCH');
    a.dispose();
    b.dispose();
    c.dispose();
  });
}
