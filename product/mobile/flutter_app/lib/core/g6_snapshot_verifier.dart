part of 'g6_signed_snapshot.dart';

class G6SnapshotVerifier {
  G6SnapshotVerifier({required this.trustPin, this.expectedWireSha256});
  final G6TrustPin trustPin;
  /// Only pinned by an independently distributed fixture, never HTTP response.
  final String? expectedWireSha256;
  G6WitnessHead _known = G6WitnessHead.genesis;
  G6WitnessHead get lastVerifiedHead => _known;

  Future<G6VerifiedSnapshot> verify(List<int> wire) async {
    final raw = g6StrictWireJson(wire);
    if (expectedWireSha256 != null && await _sha(_canonical(raw)) != expectedWireSha256) {
      _fail('FIXTURE_WIRE_HASH_DRIFT');
    }
    if ([_id(trustPin.tenant),_id(trustPin.project),_id(trustPin.campaign),
         _id(trustPin.witnessId)].contains(false)) _fail('INVALID_PIN_IDENTITY');
    final root = _exact(raw, {'schema','source_class','scientific_approval','tenant',
      'project','campaign','audit_receipt','witness_event','head',
      'external_independent_custody','economic_backtests','holdout_open','ga2_open'},'SNAPSHOT_SCHEMA');
    if (root['schema']!='QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1' ||
        root['source_class']!='SYNTHETIC_ONLY' ||
        root['external_independent_custody']!='NOT_DEPLOYED' ||
        root['scientific_approval'] != false || root['economic_backtests'] is! int ||
        root['economic_backtests'] != 0 || root['holdout_open']!=false || root['ga2_open']!=false) {
      _fail('UNAUTHORIZED_SCIENTIFIC_CLAIM');
    }
    if (root['tenant'] != trustPin.tenant || root['project'] != trustPin.project ||
        root['campaign'] != trustPin.campaign) _fail('WRONG_CLIENT_IDENTITY');
    final audit = _exact(root['audit_receipt'], {'schema','classification','tenant',
      'source_class','source_id','license_id','source_sha256','audit_spec_sha256',
      'broker_timezone','diagnostics','rows','imputation','execution_eligible',
      'economic_tests','holdout_open','ga2_open'},'AUDIT_SCHEMA');
    if (audit['schema']!='QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1' ||
        audit['classification']!='TEST_ONLY_NO_SCIENTIFIC_AUTHORITY' ||
        audit['tenant']!=trustPin.tenant || audit['source_class']!='SYNTHETIC_ONLY' ||
        audit['execution_eligible']!=true || audit['economic_tests']!=0 ||
        audit['holdout_open']!=false || audit['ga2_open']!=false ||
        audit['imputation']!='NONE' || audit['rows'] is! int || (audit['rows'] as int)<1 ||
        !_hex(audit['source_sha256']) || !_hex(audit['audit_spec_sha256'])) {
      _fail('INELIGIBLE_SYNTHETIC_AUDIT');
    }
    final diag=_exact(audit['diagnostics'], {'large_gaps','session_transitions',
      'zero_spread_preserved','crossed_spread_preserved','invalid_execution_quotes'},'DIAGNOSTICS_SCHEMA');
    if (diag.values.any((x)=>x is! int || x<0)) _fail('INVALID_DIAGNOSTICS');
    final auditHash=await _sha(_canonical(audit));
    if (trustPin.expectedAuditSha256 != null &&
        trustPin.expectedAuditSha256!=auditHash) _fail('OUT_OF_BAND_AUDIT_DRIFT');
    final event=_exact(root['witness_event'],{'body','signature_b64'},'ENVELOPE_SCHEMA');
    final body=_exact(event['body'],{'schema','witness_id','sequence','previous_sha256',
      'tenant','campaign','subject_sha256','created_utc','classification'},'WITNESS_SCHEMA');
    if (body['schema']!='QROS_G4_WITNESS_TEST_V1' ||
        body['classification']!='TEST_ONLY_SYNTHETIC' ||
        body['witness_id']!=trustPin.witnessId || body['tenant']!=trustPin.tenant ||
        body['campaign']!=trustPin.campaign || body['subject_sha256']!=auditHash ||
        body['sequence'] is! int || (body['sequence'] as int)<1 ||
        !_hex(body['previous_sha256'])) _fail('WITNESS_BODY_MISMATCH');
    final timestamp=body['created_utc'];
    if (timestamp is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$').hasMatch(timestamp)) {
      _fail('WITNESS_TIME_FORMAT');
    }
    final parsed=DateTime.tryParse(timestamp);
    if (parsed==null || parsed.toUtc().toIso8601String().substring(0,19)+'Z'!=timestamp) {
      _fail('WITNESS_TIME_INVALID');
    }
    final newHash=await _sha(_canonical(body));
    final declared=_exact(root['head'],{'sequence','sha256'},'HEAD_SCHEMA');
    if (declared['sequence']!=body['sequence'] || declared['sha256']!=newHash ||
        (trustPin.expectedHeadSha256!=null && trustPin.expectedHeadSha256!=newHash)) {
      _fail('HEAD_FORGED_OR_FORKED');
    }
    final seq=body['sequence'] as int;
    if (seq==_known.sequence) {
      if (newHash!=_known.sha256) _fail('SAME_SEQUENCE_FORK');
    } else if (seq==_known.sequence+1) {
      if (body['previous_sha256']!=_known.sha256 ||
          (_known.createdUtc!=null && timestamp.compareTo(_known.createdUtc!)<0)) {
        _fail('PREVIOUS_HEAD_OR_TIME_ROLLBACK');
      }
    } else { _fail('REPLAY_OR_MISSING_PROOF'); }
    if (trustPin.publicKeyB64.isEmpty) _fail('NO_INDEPENDENT_PUBLIC_KEY');
    late final List<int> key,sig;
    try {
      key=base64.decode(trustPin.publicKeyB64);
      final str=event['signature_b64'];
      if (str is! String) _fail('SIGNATURE_SCHEMA');
      sig=base64.decode(str as String);
      if (base64.encode(sig)!=str) _fail('SIGNATURE_BASE64_NONCANONICAL');
    } on FormatException { _fail('SIGNATURE_BASE64'); }
    if (key.length!=32 || sig.length!=64) _fail('SIGNATURE_LENGTH_OR_KEY');
    final success=await Ed25519().verify(_canonical(body),signature:Signature(sig,
      publicKey:SimplePublicKey(key,type:KeyPairType.ed25519)));
    if (!success) _fail('SIGNATURE_INVALID');
    // State mutation happens only after verifying all claims and the signature.
    _known=G6WitnessHead(seq,newHash,createdUtc:timestamp);
    return G6VerifiedSnapshot(tenant:trustPin.tenant,project:trustPin.project,
      campaign:trustPin.campaign,head:_known,auditSha256:auditHash);
  }
}
