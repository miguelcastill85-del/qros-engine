import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';

class G5SnapshotReject implements Exception {
  const G5SnapshotReject(this.code);
  final String code;
  @override
  String toString() => 'QROS_G6_FAIL_CLOSED:$code';
}

class G5SnapshotTrust {
  const G5SnapshotTrust({
    required this.witnessPublicKeyB64,
    required this.witnessId,
    required this.tenant,
    required this.project,
    required this.campaign,
    required this.knownSequence,
    required this.knownHeadSha256,
  });
  final String witnessPublicKeyB64;
  final String witnessId;
  final String tenant;
  final String project;
  final String campaign;
  final int knownSequence;
  final String knownHeadSha256;
}

class G9LiveTrust {
  static const origin = 'https://qros-mobile-g9-test-only.miguelcastill85.workers.dev';
  static const profile = G5SnapshotTrust(
    witnessPublicKeyB64: 'NMKrBtWIcaMe1blwTUUS0CvZbxXCM0Z3yTOMBnYA+58=',
    witnessId: 'g9_backend_test_only', tenant: 'tenant_A', project: 'project_A', campaign: 'campaign_A',
    knownSequence: 0, knownHeadSha256: '0000000000000000000000000000000000000000000000000000000000000000',
  );
}

class G6SyntheticTrust {
  static const profile = G5SnapshotTrust(
    witnessPublicKeyB64: 'QwRr/kCSs+lJlOraFdzCDYqqB7ZY/TlU644O+4vcpd4=',
    witnessId: 'witness_fixture',
    tenant: 'tenant_A',
    project: 'project_A',
    campaign: 'campaign_A',
    knownSequence: 0,
    knownHeadSha256: '0000000000000000000000000000000000000000000000000000000000000000',
  );
}

class VerifiedG5Snapshot {
  const VerifiedG5Snapshot({
    required this.tenant,
    required this.project,
    required this.campaign,
    required this.sequence,
    required this.headSha256,
    required this.auditSha256,
    required this.rows,
    required this.brokerTimezone,
  });
  final String tenant;
  final String project;
  final String campaign;
  final int sequence;
  final String headSha256;
  final String auditSha256;
  final int rows;
  final String brokerTimezone;
}

class G5SnapshotVerifier {
  const G5SnapshotVerifier(this.trust);
  final G5SnapshotTrust trust;

  Never _reject(String code) => throw G5SnapshotReject(code);

  Map<String, dynamic> _object(Object? value, Set<String> keys, String code) {
    if (value is! Map<String, dynamic> || value.keys.toSet().difference(keys).isNotEmpty ||
        keys.difference(value.keys.toSet()).isNotEmpty) {
      _reject(code);
    }
    return value;
  }

  static Object? _sortTree(Object? value) {
    if (value is Map) {
      final keys = value.keys.map((e) => e.toString()).toList()..sort();
      return {for (final k in keys) k: _sortTree(value[k])};
    }
    if (value is List) return value.map(_sortTree).toList();
    return value;
  }

  static List<int> canonicalBytes(Object? value) => utf8.encode(jsonEncode(_sortTree(value)));

  static String _hex(List<int> bytes) =>
      bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();

  Future<String> _digest(Object? value) async =>
      _hex((await Sha256().hash(canonicalBytes(value))).bytes);

  void _hex64(Object? value, String code) {
    if (value is! String || !RegExp(r'^[0-9a-f]{64}$').hasMatch(value)) _reject(code);
  }

  Future<VerifiedG5Snapshot> verify(Map<String, dynamic> payload) async {
    _object(payload, {
      'schema','source_class','scientific_approval','tenant','project','campaign',
      'audit_receipt','witness_event','head','external_independent_custody',
      'economic_backtests','holdout_open','ga2_open'
    }, 'SNAPSHOT_SCHEMA');
    if (payload['schema'] != 'QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1' ||
        payload['source_class'] != 'SYNTHETIC_ONLY' ||
        payload['scientific_approval'] != false ||
        payload['external_independent_custody'] != 'NOT_DEPLOYED' ||
        payload['economic_backtests'] != 0 || payload['holdout_open'] != false ||
        payload['ga2_open'] != false) {
      _reject('UNAUTHORIZED_SCIENTIFIC_CLAIM');
    }
    if (payload['tenant'] != trust.tenant || payload['project'] != trust.project ||
        payload['campaign'] != trust.campaign) {
      _reject('WRONG_CLIENT_IDENTITY');
    }

    final audit = _object(payload['audit_receipt'], {
      'schema','classification','tenant','source_id','source_sha256','license_id',
      'source_class','broker_timezone','rows','diagnostics','execution_eligible',
      'imputation','economic_tests','holdout_open','ga2_open','audit_spec_sha256'
    }, 'AUDIT_SCHEMA');
    final diagnostics = _object(audit['diagnostics'], {
      'zero_spread_preserved','crossed_spread_preserved','large_gaps',
      'session_transitions','invalid_execution_quotes'
    }, 'DIAGNOSTIC_SCHEMA');
    if (audit['schema'] != 'QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1' ||
        audit['classification'] != 'TEST_ONLY_NO_SCIENTIFIC_AUTHORITY' ||
        audit['tenant'] != trust.tenant || audit['source_class'] != 'SYNTHETIC_ONLY' ||
        audit['execution_eligible'] != true || audit['imputation'] != 'NONE' ||
        audit['economic_tests'] != 0 || audit['holdout_open'] != false ||
        audit['ga2_open'] != false || audit['rows'] is! int || (audit['rows'] as int) < 1 ||
        diagnostics.values.any((v) => v is! int || v < 0) ||
        diagnostics['invalid_execution_quotes'] != 0) {
      _reject('INELIGIBLE_SYNTHETIC_AUDIT');
    }
    _hex64(audit['source_sha256'], 'AUDIT_SOURCE_HASH');
    _hex64(audit['audit_spec_sha256'], 'AUDIT_SPEC_HASH');
    final auditSha = await _digest(audit);

    final envelope = _object(payload['witness_event'], {'body','signature_b64'}, 'WITNESS_ENVELOPE');
    final body = _object(envelope['body'], {
      'schema','witness_id','sequence','previous_sha256','tenant','campaign',
      'subject_sha256','created_utc','classification'
    }, 'WITNESS_BODY');
    if (body['schema'] != 'QROS_G4_WITNESS_TEST_V1' ||
        body['classification'] != 'TEST_ONLY_SYNTHETIC' ||
        body['witness_id'] != trust.witnessId || body['tenant'] != trust.tenant ||
        body['campaign'] != trust.campaign || body['sequence'] != trust.knownSequence + 1 ||
        body['previous_sha256'] != trust.knownHeadSha256 || body['subject_sha256'] != auditSha) {
      _reject('WITNESS_CHAIN_MISMATCH');
    }
    _hex64(body['previous_sha256'], 'PREVIOUS_HASH');
    _hex64(body['subject_sha256'], 'SUBJECT_HASH');
    if (body['created_utc'] is! String ||
        !RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$').hasMatch(body['created_utc'] as String)) {
      _reject('WITNESS_TIME_FORMAT');
    }
    final sigB64 = envelope['signature_b64'];
    if (sigB64 is! String) _reject('SIGNATURE_FORMAT');
    late List<int> sig;
    late List<int> pub;
    try {
      sig = base64.decode(sigB64);
      pub = base64.decode(trust.witnessPublicKeyB64);
    } on FormatException {
      _reject('SIGNATURE_ENCODING');
    }
    if (sig.length != 64 || pub.length != 32) _reject('TRUST_OR_SIGNATURE_LENGTH');
    final key = SimplePublicKey(pub, type: KeyPairType.ed25519);
    if (!await Ed25519().verify(canonicalBytes(body), signature: Signature(sig, publicKey: key))) {
      _reject('WITNESS_SIGNATURE_INVALID');
    }
    final headSha = await _digest(body);
    final head = _object(payload['head'], {'sequence','sha256'}, 'HEAD_SCHEMA');
    if (head['sequence'] != body['sequence'] || head['sha256'] != headSha) _reject('HEAD_MISMATCH');
    _hex64(headSha, 'HEAD_HASH');

    return VerifiedG5Snapshot(
      tenant: trust.tenant, project: trust.project, campaign: trust.campaign,
      sequence: body['sequence'] as int, headSha256: headSha, auditSha256: auditSha,
      rows: audit['rows'] as int, brokerTimezone: audit['broker_timezone'] as String,
    );
  }
}

abstract class G5SnapshotGateway {
  Future<VerifiedG5Snapshot> fetch(String origin, String token);
}

class HttpsG5SnapshotGateway implements G5SnapshotGateway {
  const HttpsG5SnapshotGateway(this.verifier);
  final G5SnapshotVerifier verifier;

  @override
  Future<VerifiedG5Snapshot> fetch(String origin, String token) async {
    if (token.length < 32 || token.length > 128 || !RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(token)) {
      throw const G5SnapshotReject('TOKEN_FORMAT');
    }
    final input = Uri.tryParse(origin.trim());
    if (input == null || input.scheme != 'https' || input.host.isEmpty || input.userInfo.isNotEmpty ||
        (input.path.isNotEmpty && input.path != '/') || input.query.isNotEmpty || input.fragment.isNotEmpty) {
      throw const G5SnapshotReject('HTTPS_ORIGIN_ONLY');
    }
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final req = await client.getUrl(input.replace(path: '/v1/demo-snapshot')).timeout(const Duration(seconds: 8));
      req.followRedirects = false;
      req.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      req.headers.set('X-QROS-Project', verifier.trust.project);
      req.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final resp = await req.close().timeout(const Duration(seconds: 8));
      if (resp.isRedirect) throw const G5SnapshotReject('REDIRECT_DENIED');
      if (resp.statusCode != 200 || resp.headers.contentType?.mimeType != 'application/json') {
        throw G5SnapshotReject('HTTP_${resp.statusCode}');
      }
      final cache = resp.headers.value(HttpHeaders.cacheControlHeader) ?? '';
      if (!cache.contains('no-store')) throw const G5SnapshotReject('CACHE_POLICY');
      final bytes = <int>[];
      await for (final chunk in resp.timeout(const Duration(seconds: 8))) {
        bytes.addAll(chunk);
        if (bytes.length > 65536) throw const G5SnapshotReject('RESPONSE_TOO_LARGE');
      }
      final decoded = jsonDecode(utf8.decode(bytes, allowMalformed: false));
      if (decoded is! Map<String, dynamic>) throw const G5SnapshotReject('JSON_OBJECT_REQUIRED');
      // G5 emits canonical JSON. Requiring exact canonical bytes prevents duplicate-key
      // ambiguity and parser-dependent representations in this transport.
      if (!const ListEqualityInt().equals(bytes, G5SnapshotVerifier.canonicalBytes(decoded))) {
        throw const G5SnapshotReject('NON_CANONICAL_JSON');
      }
      return verifier.verify(decoded);
    } finally {
      client.close(force: true);
    }
  }
}

class ListEqualityInt {
  const ListEqualityInt();
  bool equals(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

