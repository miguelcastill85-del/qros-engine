import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';

/// Public, frozen TEST_ONLY fixture trust pins. No signing key is bundled.
/// A future production trust root must be distributed independently of the API.
class DemoTrust {
  static const witnessKeyB64 = 'Z4s0XQ5mCA+JbfvM3/q+9XVvckv3W8NuJLL5OFsCAZ0=';
  static const receiptKeyB64 = 'emJQHs4C0RL/Xvg8NzwXHlwInp6ppE3G31hiUaBXQBE=';
  static const anchorSha256 = '13232d1cfef35495692db5447bd1deb825fa5650b9459e3e9694a907f44048ac';
  static const sourceSha256 = '2401952fedf4d1e68e265fe6cbf896f29afaaf223571f9a6a37a05b0f952fa88';
}

class VerifiedDemo {
  const VerifiedDemo({required this.projectTitle, required this.anchorHash,
    required this.anchorSequence, required this.symbol,
    required this.side, required this.timeframe});
  final String projectTitle;
  final String anchorHash;
  final int anchorSequence;
  final String symbol;
  final String side;
  final String timeframe;
  String get state => 'SIMULATED_SAMPLE';
  bool get scientificApproval => false;
}

/// A remote UI may display ONLY a signature-verified, externally anchored,
/// specifically pinned synthetic fixture. It cannot derive scientific PASS.
class DemoReceiptVerifier {
  const DemoReceiptVerifier();

  Never _reject(String reason) => throw FormatException('QROS_DEMO_FAIL_CLOSED:$reason');

  Map<String, dynamic> _object(Object? o, Set<String> keys, String label) {
    if (o is! Map<String, dynamic> ||
        o.keys.toSet().difference(keys).isNotEmpty ||
        keys.difference(o.keys.toSet()).isNotEmpty) {
      _reject(label);
    }
    return o;
  }

  String _hex(List<int> bytes) => bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();

  Object? _sorted(Object? value) {
    if (value is Map) {
      final keys = value.keys.map((e) => e.toString()).toList()..sort();
      return {for (final key in keys) key: _sorted(value[key])};
    }
    if (value is List) return value.map(_sorted).toList();
    return value;
  }

  List<int> _canonical(Map<String, dynamic> body) => utf8.encode(jsonEncode(_sorted(body)));

  Future<String> _digest(Map<String, dynamic> body) async =>
      _hex((await Sha256().hash(_canonical(body))).bytes);

  Future<Map<String, dynamic>> _signed(Object? envelope, String keyB64, String schema) async {
    final signed = _object(envelope, {'body', 'signature_b64'}, 'SIGNED_ENVELOPE_SCHEMA');
    final body = signed['body'];
    if (body is! Map<String, dynamic> || body['schema'] != schema) _reject('BODY_SCHEMA');
    final signatureB64 = signed['signature_b64'];
    if (signatureB64 is! String) _reject('SIGNATURE_FORMAT');
    late final List<int> rawSig;
    try {
      rawSig = base64.decode(signatureB64);
    } on FormatException {
      _reject('SIGNATURE_ENCODING');
    }
    if (rawSig.length != 64) _reject('SIGNATURE_LENGTH');
    final publicKey = SimplePublicKey(base64.decode(keyB64), type: KeyPairType.ed25519);
    if (!await Ed25519().verify(_canonical(body), signature: Signature(rawSig, publicKey: publicKey))) {
      _reject('SIGNATURE_INVALID');
    }
    return body;
  }

  Future<VerifiedDemo> verify(Map<String, dynamic> data) async {
    _object(data, {'schema', 'mode', 'scientific_authority', 'anchor', 'receipt'}, 'SNAPSHOT_SCHEMA');
    if (data['schema'] != 'QROS_MOBILE_SIGNED_TEST_ONLY_V1' ||
        data['mode'] != 'TEST_ONLY_SYNTHETIC' || data['scientific_authority'] != 'NONE') {
      _reject('NOT_A_SYNTHETIC_DEMO');
    }
    final anchor = await _signed(data['anchor'], DemoTrust.witnessKeyB64, 'QROS_M2_WITNESS_ANCHOR_TEST_V1');
    _object(anchor, {'schema','sequence','digest','previous_digest','project_id',
      'source_class','source_pin_sha256'}, 'ANCHOR_SCHEMA');
    if (anchor['project_id'] != 'DEMO-001' || anchor['source_class'] != 'TEST_ONLY_SYNTHETIC' ||
        anchor['source_pin_sha256'] != DemoTrust.sourceSha256 ||
        anchor['sequence'] != 1 || anchor['digest'] is! String ||
        anchor['previous_digest'] != List.filled(64, '0').join()) {
      _reject('ANCHOR_AUTHORITY_MISMATCH');
    }
    final anchorHash = await _digest(anchor);
    if (anchorHash != DemoTrust.anchorSha256) _reject('EXTERNAL_ANCHOR_MISMATCH');

    final receipt = await _signed(data['receipt'], DemoTrust.receiptKeyB64, 'QROS_MOBILE_RECEIPT_TEST_V1');
    _object(receipt, {'schema','project_id','source_class','scientific_state',
      'scientific_approval','holdout_open','ga2_open','mt5_executed',
      'anchor_sha256','anchor_sequence','source_pin_sha256','project'}, 'RECEIPT_SCHEMA');
    if (receipt['project_id'] != 'DEMO-001' || receipt['source_class'] != 'TEST_ONLY_SYNTHETIC' ||
        receipt['scientific_state'] != 'SIMULATED_SAMPLE' ||
        receipt['scientific_approval'] != false || receipt['holdout_open'] != false ||
        receipt['ga2_open'] != false || receipt['mt5_executed'] != false ||
        receipt['anchor_sha256'] != anchorHash || receipt['anchor_sequence'] != 1 ||
        receipt['source_pin_sha256'] != DemoTrust.sourceSha256) {
      _reject('RECEIPT_AUTHORITY_MISMATCH');
    }
    final project = _object(receipt['project'],
        {'id','title','symbol','side','timeframe','classification'}, 'PROJECT_SCHEMA');
    if (project['id'] != 'DEMO-001' || project['title'] != 'Ruptura y recuperacion DEMO' ||
        project['symbol'] != 'XAUUSD' || project['side'] != 'BUY' ||
        project['timeframe'] != 'M15' || project['classification'] != 'TEST_ONLY_SYNTHETIC') {
      _reject('PROJECT_FIXTURE_MISMATCH');
    }
    return VerifiedDemo(projectTitle: project['title'] as String, anchorHash: anchorHash,
      anchorSequence: 1, symbol: project['symbol'] as String,
      side: project['side'] as String, timeframe: project['timeframe'] as String);
  }
}

abstract class DemoGateway {
  Future<VerifiedDemo> fetch(String origin, String token);
}

/// No URL or token is bundled. TLS is mandatory; system certificate checks
/// remain enabled and no redirects or certificate exceptions are allowed.
class HttpsDemoGateway implements DemoGateway {
  const HttpsDemoGateway();

  @override
  Future<VerifiedDemo> fetch(String origin, String token) async {
    if (token.length < 32 || token.length > 128 ||
        !RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(token)) {
      throw const FormatException('TOKEN_FORMAT_INVALID');
    }
    final input = Uri.tryParse(origin.trim());
    if (input == null || input.scheme != 'https' || input.host.isEmpty ||
        input.port == 0 || input.userInfo.isNotEmpty ||
        input.path != '' && input.path != '/' ||
        input.query.isNotEmpty || input.fragment.isNotEmpty) {
      throw const FormatException('HTTPS_ORIGIN_REQUIRED');
    }
    final url = input.replace(path: '/v1/demo-snapshot');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final request = await client.getUrl(url).timeout(const Duration(seconds: 8));
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      request.followRedirects = false;
      final response = await request.close().timeout(const Duration(seconds: 8));
      if (response.statusCode != 200 ||
          response.headers.contentType?.mimeType != 'application/json') {
        throw const FormatException('UNVERIFIED_REMOTE_RESPONSE');
      }
      final bytes = <int>[];
      await for (final part in response.timeout(const Duration(seconds: 8))) {
        bytes.addAll(part);
        if (bytes.length > 65536) throw const FormatException('RESPONSE_TOO_LARGE');
      }
      final raw = jsonDecode(utf8.decode(bytes, allowMalformed: false));
      if (raw is! Map<String, dynamic>) throw const FormatException('SNAPSHOT_NOT_AN_OBJECT');
      return DemoReceiptVerifier().verify(raw);
    } finally {
      client.close(force: true);
    }
  }
}
