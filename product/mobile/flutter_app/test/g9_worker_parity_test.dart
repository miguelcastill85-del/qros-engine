import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g5_snapshot.dart';

void main() {
  test('G9 actual Worker bytes verify through unchanged G6 verifier with independent test pin', () async {
    final f=jsonDecode(File('../g9/evidence/parity_fixture.json').readAsStringSync()) as Map<String,dynamic>;
    final raw=File('../g9/evidence/worker_snapshot.json').readAsBytesSync();
    final trust=G5SnapshotTrust(witnessPublicKeyB64:f['public_key_b64'] as String,
      witnessId:'g9_backend_test_only',tenant:'tenant_A',project:'project_A',campaign:'campaign_A',
      knownSequence:0,knownHeadSha256:List.filled(64,'0').join());
    final p=jsonDecode(utf8.decode(raw)) as Map<String,dynamic>;
    expect(const ListEqualityInt().equals(raw,G5SnapshotVerifier.canonicalBytes(p)),true);
    final v=await G5SnapshotVerifier(trust).verify(p);
    expect(v.rows,2);expect(v.sequence,1);
    expect(v.headSha256,(p['head'] as Map<String,dynamic>)['sha256']);
    (p['witness_event'] as Map<String,dynamic>)['signature_b64']=base64Encode(List.filled(64,0));
    await expectLater(G5SnapshotVerifier(trust).verify(p),throwsA(isA<G5SnapshotReject>()));
  });
}
