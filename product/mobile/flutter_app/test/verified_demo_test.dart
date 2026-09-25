import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/verified_demo.dart';

void main() {
  late Map<String, dynamic> signed;
  setUpAll(() {
    signed = jsonDecode(File('test/signed_snapshot.json').readAsStringSync()) as Map<String, dynamic>;
  });
  test('two independently signed fixture envelopes and pinned external anchor verify', () async {
    final record = await const DemoReceiptVerifier().verify(signed);
    expect(record.anchorHash, DemoTrust.anchorSha256);
    expect(record.projectTitle, 'Ruptura y recuperacion DEMO');
    expect(record.scientificApproval, false);
    expect(record.state, 'SIMULATED_SAMPLE');
  });
  test('mutated receipt promotion cannot forge Ed25519', () async {
    final modified = jsonDecode(jsonEncode(signed)) as Map<String, dynamic>;
    final receipt = modified['receipt'] as Map<String, dynamic>;
    (receipt['body'] as Map<String, dynamic>)['scientific_approval'] = true;
    await expectLater(const DemoReceiptVerifier().verify(modified), throwsA(isA<FormatException>()));
  });
  test('mutated external witness anchor fails', () async {
    final modified = jsonDecode(jsonEncode(signed)) as Map<String, dynamic>;
    final anchor = modified['anchor'] as Map<String, dynamic>;
    (anchor['body'] as Map<String, dynamic>)['digest'] = List.filled(64, 'a').join();
    await expectLater(const DemoReceiptVerifier().verify(modified), throwsA(isA<FormatException>()));
  });
  test('swap separate signatures fails closed', () async {
    final modified = jsonDecode(jsonEncode(signed)) as Map<String, dynamic>;
    (modified['receipt'] as Map<String, dynamic>)['signature_b64'] =
        (modified['anchor'] as Map<String, dynamic>)['signature_b64'];
    await expectLater(const DemoReceiptVerifier().verify(modified), throwsA(isA<FormatException>()));
  });
  test('no privileged unknown schema fields', () async {
    final modified = jsonDecode(jsonEncode(signed)) as Map<String, dynamic>;
    modified['actor'] = 'QROS_CORE';
    await expectLater(const DemoReceiptVerifier().verify(modified), throwsA(isA<FormatException>()));
  });
  test('client rejects HTTP and has no default token', () async {
    await expectLater(const HttpsDemoGateway().fetch('http://127.0.0.1:8765', List.filled(40, 'x').join()),
        throwsA(isA<FormatException>()));
    await expectLater(const HttpsDemoGateway().fetch('https://example.com', 'pass'),
        throwsA(isA<FormatException>()));
  });
}
