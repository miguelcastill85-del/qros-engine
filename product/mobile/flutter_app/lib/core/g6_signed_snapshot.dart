import 'dart:convert';
import 'package:cryptography/cryptography.dart';
part 'g6_snapshot_verifier.dart';

/// Independently verified G5 wire format. Every result is SYNTHETIC TEST_ONLY.
/// Pin MUST originate outside the network snapshot. No signing keys shipped.
class G6Reject implements Exception {
  const G6Reject(this.code);
  final String code;
  @override
  String toString() => 'QROS_G6_REJECT:$code';
}

class G6WitnessHead {
  const G6WitnessHead(this.sequence, this.sha256, {this.createdUtc});
  final int sequence;
  final String sha256;
  final String? createdUtc;
  static const genesis = G6WitnessHead(0,
      '0000000000000000000000000000000000000000000000000000000000000000');
}

class G6TrustPin {
  const G6TrustPin({required this.tenant, required this.project,
    required this.campaign, required this.witnessId,
    required this.publicKeyB64, this.expectedAuditSha256, this.expectedHeadSha256});
  final String tenant, project, campaign, witnessId, publicKeyB64;
  final String? expectedAuditSha256, expectedHeadSha256;
  factory G6TrustPin.fromOfflineFixture(Map<String, dynamic> data) {
    _exact(data, {'schema','classification','tenant','project','campaign',
        'witness_id','witness_public_b64','expected_audit_sha256',
        'expected_head_sha256','sequence','snapshot_wire_sha256',
        'production_trust_root','economic_backtests'},'PIN_SCHEMA');
    if (data['schema'] != 'QROS_G6_OFFLINE_TRUST_FIXTURE_V1' ||
        data['classification'] != 'SYNTHETIC_ONLY' ||
        data['production_trust_root'] != false || data['economic_backtests'] != 0 ||
        data['sequence'] != 1 || !_hex(data['snapshot_wire_sha256'])) {
      throw const G6Reject('UNTRUSTED_FIXTURE_PIN');
    }
    return G6TrustPin(tenant: data['tenant'] as String,
      project: data['project'] as String, campaign: data['campaign'] as String,
      witnessId: data['witness_id'] as String,
      publicKeyB64: data['witness_public_b64'] as String,
      expectedAuditSha256: data['expected_audit_sha256'] as String,
      expectedHeadSha256: data['expected_head_sha256'] as String);
  }
}

class G6VerifiedSnapshot {
  const G6VerifiedSnapshot({required this.tenant, required this.project,
    required this.campaign, required this.head, required this.auditSha256});
  final String tenant, project, campaign, auditSha256;
  final G6WitnessHead head;
  String get status => 'TEST_ONLY_SYNTHETIC_VERIFIED';
}

Never _fail(String code) => throw G6Reject(code);

Map<String,dynamic> _exact(Object? value, Set<String> keys, String label) {
  if (value is! Map<String,dynamic> || value.keys.toSet().difference(keys).isNotEmpty ||
      keys.difference(value.keys.toSet()).isNotEmpty) _fail(label);
  return value;
}
bool _hex(Object? x) => x is String && RegExp(r'^[0-9a-f]{64}$').hasMatch(x);
bool _id(Object? x) => x is String && RegExp(r'^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,95}$').hasMatch(x);
String _hash(List<int> digest) => digest.map((b)=>b.toRadixString(16).padLeft(2,'0')).join();

Object? _sortTree(Object? raw) {
  if (raw is Map<String,dynamic>) {
    final keys = raw.keys.toList()..sort();
    return {for(final key in keys) key:_sortTree(raw[key])};
  }
  if (raw is List) return raw.map(_sortTree).toList();
  if (raw == null || raw is String || raw is bool || raw is int) return raw;
  _fail('UNSUPPORTED_JSON_TYPE');
}
List<int> _canonical(Object? body) => utf8.encode(jsonEncode(_sortTree(body)));
Future<String> _sha(List<int> bytes) async => _hash((await Sha256().hash(bytes)).bytes);

/// Defense against duplicate JSON keys: G5 emits canonical wire JSON. Reject
/// any input whose exact bytes differ from the decoded, reserialized structure.
/// This also rejects non-canonical numbers, NaN, unbounded nesting, whitespace,
/// alternate escapes and duplicate-key substitution (even when jsonDecode keeps
/// only the last duplicate). A single optional terminal LF is fixture-only.
Map<String,dynamic> g6StrictWireJson(List<int> bytes) {
  if (bytes.isEmpty || bytes.length > 65536) _fail('WIRE_SIZE');
  late final String decoded;
  try { decoded = utf8.decode(bytes,allowMalformed:false); }
  on FormatException { _fail('WIRE_UTF8'); }
  final stripped = decoded.endsWith('\n') ? decoded.substring(0,decoded.length-1) : decoded;
  Object? parsed;
  try { parsed = jsonDecode(stripped); }
  on FormatException { _fail('WIRE_JSON'); }
  if (parsed is! Map<String,dynamic> || jsonEncode(_sortTree(parsed))!=stripped) {
    _fail('NONCANONICAL_OR_DUPLICATE_JSON');
  }
  return parsed;
}

