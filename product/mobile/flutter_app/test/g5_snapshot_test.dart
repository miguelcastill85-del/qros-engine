import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g5_snapshot.dart';

Map<String,dynamic> fixture() {
  final raw = File('../g6/tests/fixtures/g5_signed_snapshot_fixture.json').readAsStringSync();
  return jsonDecode(raw) as Map<String,dynamic>;
}

void main() {
  test('Dart independently verifies frozen Python Ed25519 G5 fixture', () async {
    final f=fixture();
    expect(f['public_key_b64'], G6SyntheticTrust.profile.witnessPublicKeyB64);
    final result=await const G5SnapshotVerifier(G6SyntheticTrust.profile)
        .verify(f['payload'] as Map<String,dynamic>);
    expect(result.sequence,1);
    expect(result.rows,2);
    expect(result.headSha256,'c3855bb53e8dddd4120f26ee0a294f069c97be58a4a7275779d016fb4cb22b13');
  });

  test('tampered audit is rejected even with original signature', () async {
    final f=fixture();
    final p=jsonDecode(jsonEncode(f['payload'])) as Map<String,dynamic>;
    (p['audit_receipt'] as Map<String,dynamic>)['rows']=3;
    await expectLater(const G5SnapshotVerifier(G6SyntheticTrust.profile).verify(p),
      throwsA(isA<G5SnapshotReject>()));
  });

  test('cross tenant, scientific escalation and head fork fail closed', () async {
    for (final mutate in <void Function(Map<String,dynamic>)>[
      (p)=>p['tenant']='tenant_B',
      (p)=>p['scientific_approval']=true,
      (p)=>(p['head'] as Map<String,dynamic>)['sha256']=List.filled(64,'f').join(),
    ]) {
      final p=jsonDecode(jsonEncode(fixture()['payload'])) as Map<String,dynamic>;
      mutate(p);
      await expectLater(const G5SnapshotVerifier(G6SyntheticTrust.profile).verify(p), throwsA(isA<G5SnapshotReject>()));
    }
  });

  test('wrong pinned public key rejects a valid signature', () async {
    final f=fixture();
    final bad=G5SnapshotTrust(witnessPublicKeyB64:'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=', witnessId:'witness_fixture',
      tenant:'tenant_A',project:'project_A',campaign:'campaign_A',knownSequence:0,knownHeadSha256:List.filled(64,'0').join());
    await expectLater(G5SnapshotVerifier(bad).verify(f['payload'] as Map<String,dynamic>), throwsA(isA<G5SnapshotReject>()));
  });
}
