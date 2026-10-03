import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/session_client.dart';

Map<String, dynamic> fixture() => jsonDecode(
  File('test/fixtures/g12_result_python.json').readAsStringSync()) as Map<String, dynamic>;

void main() {
  test('G12 result SHA agrees with independently generated Python fixture', () async {
    final job = await SyntheticJob.verifyServer(fixture());
    expect(job.complete, true);
    expect(job.resultSha256, '582e593602593454d76ac3a5a911ac6c69deecbbefb0e279dcd6325f2dfa2b18');
  });
  test('rejects tampered digest, result substitution and unsafe states', () async {
    final modifications = <void Function(Map<String, dynamic>)>[
      (d) => (d['result'] as Map)['result_sha256'] = '0' * 64,
      (d) => (d['result'] as Map)['job_id'] = 'different-job',
      (d) => (d['result'] as Map)['raw_births'] = 145,
      (d) => (d['result'] as Map)['search_space_sha256'] = '3' * 64,
      (d) => (d['result'] as Map)['work_units_completed'] = 4,
      (d) => (d['result'] as Map)['scientific_approval'] = true,
      (d) => (d['result'] as Map)['extra'] = 'unrecognized',
      (d) => d['phase'] = 2,
      (d) => d['progress'] = 99,
      (d) => d['state'] = 'VALIDATED',
    ];
    for (final change in modifications) {
      final data = fixture();
      change(data);
      await expectLater(SyntheticJob.verifyServer(data), throwsFormatException);
    }
  });
  test('rejects result attached before completion', () async {
    final data = fixture()..['state'] = 'PREPARED'..['phase'] = 0..['progress'] = 0;
    await expectLater(SyntheticJob.verifyServer(data), throwsFormatException);
  });
}
