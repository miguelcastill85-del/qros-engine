import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/session_client.dart';
import 'package:qros_mobile_studio/core/universe_ir.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';

class FakeGateway implements SessionGateway {
  int refreshCount = 0;
  int revokeCount = 0;
  int resumeCount = 0;
  final Map<String, SyntheticJob> jobs = {};

  @override
  Future<ClientSession> bootstrap(
      String origin, String bootstrapToken, String deviceId) async {
    expect(bootstrapToken, 'B' * 48);
    return ClientSession(
      origin: origin,
      deviceId: deviceId,
      clientId: 'client-1',
      accessToken: 'A' * 43,
      accessExpiresAt: 1000,
      refreshToken: 'R' * 43,
      refreshExpiresAt: 10000,
    );
  }

  @override
  Future<ClientSession> refresh(ClientSession current) async {
    refreshCount++;
    return ClientSession(
      origin: current.origin,
      deviceId: current.deviceId,
      clientId: current.clientId,
      accessToken: 'C' * 43,
      accessExpiresAt: 2000,
      refreshToken: 'S' * 43,
      refreshExpiresAt: 11000,
    );
  }

  @override
  Future<void> revoke(ClientSession current) async {
    revokeCount++;
  }

  @override
  Future<SyntheticJob> createJob(
      ClientSession current, UniverseSessionDraft draft, String requestId) async {
    const id = '12345678-1234-1234-1234-123456789012';
    final job = SyntheticJob(
      jobId: id,
      clientId: current.clientId,
      requestId: requestId,
      state: 'PREPARED',
      phase: 0,
      progress: 0,
      searchSpaceSha256: draft.searchSpaceSha256,
      toyEnumerationSha256: draft.toyEnumerationSha256,
      rawBirths: draft.blueprint.rawBirths,
      resultSha256: null,
    );
    jobs[id] = job;
    return job;
  }

  @override
  Future<SyntheticJob> getJob(ClientSession current, String jobId) async =>
      jobs[jobId]!;

  @override
  Future<SyntheticJob> resumeJob(
      ClientSession current, String jobId) async {
    resumeCount++;
    final old = jobs[jobId]!;
    final phase = old.phase + 1;
    final state = phase == 1
        ? 'VALIDATED'
        : phase == 2
            ? 'CHECKPOINTED'
            : 'COMPLETE';
    final progress = phase == 1
        ? 34
        : phase == 2
            ? 67
            : 100;
    final job = SyntheticJob(
      jobId: old.jobId,
      clientId: old.clientId,
      requestId: old.requestId,
      state: state,
      phase: phase > 3 ? 3 : phase,
      progress: progress,
      searchSpaceSha256: old.searchSpaceSha256,
      toyEnumerationSha256: old.toyEnumerationSha256,
      rawBirths: old.rawBirths,
      resultSha256: state == 'COMPLETE' ? 'f' * 64 : null,
    );
    jobs[jobId] = job;
    return job;
  }
}

void main() {
  test('session survives restart, bootstrap is not persisted and refresh rotates',
      () async {
    final vault = MemoryLocalVault();
    final gateway = FakeGateway();
    var now = DateTime.fromMillisecondsSinceEpoch(100 * 1000, isUtc: true);
    final store = SessionStore(
      vault: vault,
      gateway: gateway,
      clock: () => now,
      deviceIdFactory: () => 'device_NaN',
    );
    await store.initialize();
    expect(store.deviceId, 'device_NaN');
    await store.enroll('https://g12.example', 'B' * 48);
    expect(store.enrolled, true);
    expect(vault.snapshot[SessionStore.sessionKey], isNot(contains('B' * 48)));

    final restored = SessionStore(
      vault: vault,
      gateway: gateway,
      clock: () => now,
      deviceIdFactory: () => 'device_NaN',
    );
    await restored.initialize();
    expect(restored.session!.clientId, 'client-1');
    expect(restored.deviceId, 'device_NaN');

    now = DateTime.fromMillisecondsSinceEpoch(950 * 1000, isUtc: true);
    final renewed = await restored.ensureAccess();
    expect(gateway.refreshCount, 1);
    expect(renewed.accessToken, 'C' * 43);
    expect(renewed.refreshToken, 'S' * 43);
    expect(vault.snapshot[SessionStore.sessionKey], isNot(contains('R' * 43)));

    await restored.signOut();
    expect(gateway.revokeCount, 1);
    expect(restored.session, isNull);
    expect(vault.snapshot.containsKey(SessionStore.sessionKey), false);
    store.dispose();
    restored.dispose();
  });

  test('synthetic job survives local restart and resumes without a new job',
      () async {
    final vault = MemoryLocalVault();
    final gateway = FakeGateway();
    final session = SessionStore(
      vault: vault,
      gateway: gateway,
      clock: () => DateTime.fromMillisecondsSinceEpoch(100 * 1000, isUtc: true),
      deviceIdFactory: () => 'device_NaN',
    );
    await session.initialize();
    await session.enroll('https://g12.example', 'B' * 48);

    final universe = UniverseSessionStore(vault: MemoryLocalVault());
    final draft = await universe.save(
      title: 'Universo G12',
      thesis: 'Hipótesis sintética para probar un trabajo durable.',
      blueprint: UniverseBlueprint.sample(),
    );

    final first = SyntheticJobStore(
      vault: vault,
      sessionStore: session,
      gateway: gateway,
      requestIdFactory: () => 'req_NaN',
    );
    final created = await first.start(draft);
    expect(created.state, 'PREPARED');
    expect(created.rawBirths, 144);

    final restored = SyntheticJobStore(
      vault: vault,
      sessionStore: session,
      gateway: gateway,
      requestIdFactory: () => 'req_NaN',
    );
    await restored.initialize();
    expect(restored.job!.jobId, created.jobId);
    expect((await restored.resume()).state, 'VALIDATED');
    expect((await restored.resume()).state, 'CHECKPOINTED');
    final completed = await restored.resume();
    expect(completed.state, 'COMPLETE');
    expect(completed.resultSha256, 'f' * 64);
    expect(gateway.resumeCount, 3);
    expect(completed.searchSpaceSha256, draft.searchSpaceSha256);
    expect(completed.rawBirths, draft.blueprint.rawBirths);

    first.dispose();
    restored.dispose();
    universe.dispose();
    session.dispose();
  });
}
