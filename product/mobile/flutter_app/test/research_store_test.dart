import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/research_store.dart';

void main() {
  test('fixture is explicitly simulated, not approved and without real metrics',
      () {
    final store = ResearchStore(clock: () => DateTime.utc(2026, 9, 25));
    expect(store.projects.length, 1);
    expect(store.projects.first.isSample, true);
    expect(store.projects.first.state, 'SIMULATED_SAMPLE');
    final evidence = store.exportSyntheticEvidence();
    expect(evidence['scientific_authority'], 'NONE');
    expect(evidence['real_trades'], 0);
    expect(evidence['engine_connected'], false);
    expect(evidence['external_head_anchor'], null);
    store.dispose();
  });

  test('new user idea is persisted but cannot become scientific approval',
      () async {
    final vault = MemoryLocalVault();
    final store = ResearchStore(
      clock: () => DateTime.utc(2026, 9, 25),
      vault: vault,
    );
    final draft = await store.createLocalDraft(
      title: ' Recuperación de nivel ',
      thesis:
          'Entrada hipotética posterior a la recuperación observable de nivel.',
      symbol: 'XAUUSD',
      side: 'BUY',
      timeframe: 'M15',
    );
    expect(draft.id, 'LOCAL-0001');
    expect(draft.title, 'Recuperación de nivel');
    expect(draft.state, 'LOCAL_DRAFT_NOT_FROZEN');
    expect(draft.toEvidenceRecord()['scientific_approval'], false);
    expect(draft.toEvidenceRecord()['receipt_sha256'], null);
    expect(store.actualBacktests, 0);
    expect(vault.snapshot[ResearchStore.storageKey], isNotNull);
    expect(vault.snapshot[ResearchStore.storageKey],
        isNot(contains('scientific_approval')));
    store.dispose();
  });

  test('invalid assets, directions and incomplete hypotheses are rejected',
      () async {
    final store = ResearchStore();
    await expectLater(
      store.createLocalDraft(
        title: 'Test',
        thesis: 'Una hipótesis de prueba.',
        symbol: 'EURUSD',
        side: 'BUY',
        timeframe: 'M15',
      ),
      throwsArgumentError,
    );
    await expectLater(
      store.createLocalDraft(
        title: 'Test',
        thesis: 'corta',
        symbol: 'XAUUSD',
        side: 'BUY',
        timeframe: 'M15',
      ),
      throwsArgumentError,
    );
    expect(store.projects.length, 1);
    store.dispose();
  });
}
