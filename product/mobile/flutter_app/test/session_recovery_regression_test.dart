import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/session_client.dart';
import 'package:qros_mobile_studio/core/universe_ir.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';
import 'session_job_store_test.dart' show FakeGateway, rep;

class PausedGateway extends FakeGateway {
  final entered = Completer<void>();
  final release = Completer<void>();
  String? revokedAccess;
  @override
  Future<ClientSession> refresh(ClientSession current) async {
    if (!entered.isCompleted) entered.complete();
    await release.future;
    return super.refresh(current);
  }
  @override
  Future<void> revoke(ClientSession current) async {
    revokedAccess = current.accessToken;
    await super.revoke(current);
  }
}

class LostResponseGateway extends FakeGateway {
  final requests = <String>[];
  bool loseFirst = true;
  @override
  Future<SyntheticJob> createJob(
      ClientSession current, UniverseSessionDraft draft, String requestId) async {
    requests.add(requestId);
    final job = await super.createJob(current, draft, requestId);
    if (loseFirst) {
      loseFirst = false;
      throw StateError('SIMULATED_RESPONSE_LOST_AFTER_ACCEPTANCE');
    }
    return job;
  }
}

Future<SessionStore> enrolled(LocalVault vault, FakeGateway gateway,
    {int now = 950}) async {
  final s = SessionStore(vault: vault, gateway: gateway,
    clock: () => DateTime.fromMillisecondsSinceEpoch(now * 1000, isUtc: true),
    deviceIdFactory: () => 'device_' + rep('D', 43));
  await s.initialize();
  await s.enroll('https://g12.example', rep('B', 48));
  return s;
}

void main() {
  test('concurrent access renewal consumes rotating token once', () async {
    final gateway = PausedGateway();
    final s = await enrolled(MemoryLocalVault(), gateway);
    final first = s.ensureAccess();
    await gateway.entered.future;
    final second = s.ensureAccess();
    gateway.release.complete();
    final results = await Future.wait([first, second]);
    expect(gateway.refreshCount, 1);
    expect(results[0].accessToken, results[1].accessToken);
    s.dispose();
  });

  test('sign out queued during renewal cannot resurrect a session', () async {
    final vault = MemoryLocalVault();
    final gateway = PausedGateway();
    final s = await enrolled(vault, gateway);
    final renew = s.renew();
    await gateway.entered.future;
    final close = s.signOut();
    await Future<void>.delayed(Duration.zero);
    gateway.release.complete();
    await Future.wait([renew, close]);
    expect(s.session, isNull);
    expect(vault.snapshot.containsKey(SessionStore.sessionKey), false);
    expect(gateway.revokedAccess, rep('C', 43));
    s.dispose();
  });

  test('request id survives lost response and local restart', () async {
    final vault = MemoryLocalVault();
    final gateway = LostResponseGateway();
    final s = await enrolled(vault, gateway, now: 100);
    final universe = UniverseSessionStore(vault: MemoryLocalVault());
    final draft = await universe.save(title: 'Test recovery',
      thesis: 'Synthetic infrastructure recovery only.',
      blueprint: UniverseBlueprint.sample());
    final first = SyntheticJobStore(vault: vault, sessionStore: s,
      gateway: gateway, requestIdFactory: () => 'req_' + rep('A', 22));
    await expectLater(first.start(draft), throwsStateError);
    final restored = SyntheticJobStore(vault: vault, sessionStore: s,
      gateway: gateway, requestIdFactory: () => 'req_' + rep('B', 22));
    await restored.initialize();
    await restored.start(draft);
    expect(gateway.requests.length, 2);
    expect(gateway.requests.toSet().length, 1);
    first.dispose(); restored.dispose(); universe.dispose(); s.dispose();
  });

  test('opening an old job cannot discard a different pending request', () async {
    final vault = MemoryLocalVault();
    final gateway = LostResponseGateway()..loseFirst = false;
    final s = await enrolled(vault, gateway, now: 100);
    final universe = UniverseSessionStore(vault: MemoryLocalVault());
    final a = await universe.save(title: 'First universe',
      thesis: 'First synthetic universe for retry isolation.',
      blueprint: UniverseBlueprint.sample());
    var counter = 0;
    final jobs = SyntheticJobStore(vault: vault, sessionStore: s,
      gateway: gateway, requestIdFactory: () => 'req_' + rep('${++counter}', 22));
    await jobs.start(a);
    final b = UniverseSessionDraft(title: a.title, thesis: a.thesis,
      blueprint: a.blueprint, searchSpaceSha256: rep('3', 64),
      toyEnumerationSha256: a.toyEnumerationSha256);
    gateway.loseFirst = true;
    await expectLater(jobs.start(b), throwsStateError);
    await expectLater(jobs.start(a), throwsFormatException);
    await jobs.start(b);
    expect(gateway.requests[1], gateway.requests[2]);
    jobs.dispose(); universe.dispose(); s.dispose();
  });
}
