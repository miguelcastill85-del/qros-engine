import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g6_signed_snapshot.dart';
import 'package:qros_mobile_studio/core/g6_demo_transport.dart';

class FakeG6Transport implements G6SyntheticTransport {
  FakeG6Transport(this.bytes);
  final List<int> bytes;
  String? projectSeen;
  @override Future<List<int>> getSnapshot({required String origin,required String token,
    required String project,String? testCaPem}) async {projectSeen=project;return bytes;}
}

void main(){
  TestWidgetsFlutterBinding.ensureInitialized();
  late List<int> wire;late Map<String,dynamic> trust;
  setUpAll(() async {
    wire=(await rootBundle.load('assets/g6_signed_snapshot.json')).buffer.asUint8List();
    trust=jsonDecode(await rootBundle.loadString('assets/g6_offline_trust.json')) as Map<String,dynamic>;
  });
  G6SnapshotVerifier verifier() => G6SnapshotVerifier(trustPin:G6TrustPin.fromOfflineFixture(trust),
    expectedWireSha256:trust['snapshot_wire_sha256'] as String);

  test('G5 independent signed fixture exact SHA and tenant matches Python',() async {
    final checked=await verifier().verify(wire);
    expect(checked.tenant,'tenant_G6');
    expect(checked.head.sequence,1);
    expect(checked.head.sha256,trust['expected_head_sha256']);
    expect(checked.auditSha256,trust['expected_audit_sha256']);
    expect(checked.status,'TEST_ONLY_SYNTHETIC_VERIFIED');
  });
  test('second identical signed snapshot is idempotent in RAM only',() async {
    final v=verifier();await v.verify(wire);await v.verify(wire);
    expect(v.lastVerifiedHead.sequence,1);
  });
  test('reject noncanonical duplicate-key substitution',() {
    final s=utf8.decode(wire);
    final poisoned=s.replaceFirst('"ga2_open":false','"ga2_open":false,"ga2_open":true');
    expect(()=>g6StrictWireJson(utf8.encode(poisoned)),throwsA(isA<G6Reject>()));
  });
  test('reject modified audit even with valid old witness signature',() async {
    final s=utf8.decode(wire);
    final poisoned=s.replaceFirst('"rows":1','"rows":2');
    final v=G6SnapshotVerifier(trustPin:G6TrustPin.fromOfflineFixture(trust));
    await expectLater(v.verify(utf8.encode(poisoned)),throwsA(isA<G6Reject>()));
    expect(v.lastVerifiedHead.sequence,0);
  });
  test('reject scientific approval field injection',() async {
    final s=utf8.decode(wire).replaceFirst('"scientific_approval":false','"scientific_approval":true');
    final v=G6SnapshotVerifier(trustPin:G6TrustPin.fromOfflineFixture(trust));
    await expectLater(v.verify(utf8.encode(s)),throwsA(isA<G6Reject>()));
  });
  test('reject forged head with original valid signature',() async {
    final s=utf8.decode(wire).replaceFirst(trust['expected_head_sha256'] as String,List.filled(64,'f').join());
    final v=G6SnapshotVerifier(trustPin:G6TrustPin.fromOfflineFixture(trust));
    await expectLater(v.verify(utf8.encode(s)),throwsA(isA<G6Reject>()));
  });
  test('reject wrong tenant and missing independent root',() async {
    final good=G6TrustPin.fromOfflineFixture(trust);
    final bad=G6TrustPin(tenant:'other',project:good.project,campaign:good.campaign,
        witnessId:good.witnessId,publicKeyB64:good.publicKeyB64);
    await expectLater(G6SnapshotVerifier(trustPin:bad).verify(wire),throwsA(isA<G6Reject>()));
    final none=G6TrustPin(tenant:good.tenant,project:good.project,campaign:good.campaign,
        witnessId:good.witnessId,publicKeyB64:'');
    await expectLater(G6SnapshotVerifier(trustPin:none).verify(wire),throwsA(isA<G6Reject>()));
  });
  test('reject invalid signed Ed25519 message',() async {
    final s=utf8.decode(wire);
    final match=RegExp(r'"signature_b64":"([A-Za-z0-9+/=]+)"').firstMatch(s)!;
    final sig=match.group(1)!;
    final swapped=(sig[0]=='A'?'B':'A')+sig.substring(1);
    final poisoned=s.replaceFirst('"signature_b64":"$sig"','"signature_b64":"$swapped"');
    final v=G6SnapshotVerifier(trustPin:G6TrustPin.fromOfflineFixture(trust));
    await expectLater(v.verify(utf8.encode(poisoned)),throwsA(isA<G6Reject>()));
    expect(v.lastVerifiedHead.sequence,0);
  });
  test('injected read-only gateway retains out-of-band tenant pin',() async {
    final transport=FakeG6Transport(wire);
    final gateway=G6SnapshotGateway(transport:transport);
    final checked=await gateway.fetch(origin:'https://127.0.0.1:4443',
      token:List.filled(43,'T').join(),outOfBandPin:G6TrustPin.fromOfflineFixture(trust));
    expect(transport.projectSeen,'project_G6');expect(checked.head.sequence,1);
    final repeated=await gateway.fetch(origin:'https://127.0.0.1:4443',
      token:List.filled(43,'T').join(),outOfBandPin:G6TrustPin.fromOfflineFixture(trust));
    expect(repeated.head.sequence,1);
    final good=G6TrustPin.fromOfflineFixture(trust);
    final changed=G6TrustPin(tenant:'other',project:good.project,campaign:good.campaign,
      witnessId:good.witnessId,publicKeyB64:good.publicKeyB64);
    await expectLater(gateway.fetch(origin:'https://127.0.0.1:4443',
      token:List.filled(43,'T').join(),outOfBandPin:changed),throwsA(isA<G6Reject>()));
  });
  test('wire bounds and missing keys fail closed',() {
    expect(()=>g6StrictWireJson([]),throwsA(isA<G6Reject>()));
    expect(()=>g6StrictWireJson(List<int>.filled(65537,123)),throwsA(isA<G6Reject>()));
    expect(()=>g6StrictWireJson(utf8.encode('{"schema":"fake"}')),returnsNormally);
  });
}
