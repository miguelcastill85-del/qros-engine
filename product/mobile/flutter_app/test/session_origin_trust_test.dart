import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/session_client.dart';

String repeated(String c, int n) => List.filled(n, c).join();

Future<void> withoutTransport(Future<void> Function() test) =>
    HttpOverrides.runZoned(test, createHttpClient: (_) {
      throw StateError('UNTRUSTED_ORIGIN_ATTEMPTED_TRANSPORT');
    });

void main() {
  const gateway = HttpsSessionGateway();

  test('bootstrap rejects fake HTTPS origins before creating any transport', () async {
    final trusted = Uri.parse(HttpsSessionGateway.trustedOrigin);
    final invalid = [
      'https://attacker.example',
      'https://qros-mobile-g12-test-only.attacker.workers.dev',
      'http://${trusted.host}',
      'https://${trusted.host}:444',
      'https://user:password@${trusted.host}',
      'https://${trusted.host}/v1/session/bootstrap',
      'https://${trusted.host}?redirect=attacker',
      'https://${trusted.host}#attacker',
    ];
    for (final origin in invalid) {
      await withoutTransport(() async {
        await expectLater(gateway.bootstrap(origin, repeated('B', 48),
            'device_${repeated('D', 43)}'), throwsFormatException);
      });
    }
  });

  test('stored sessions cannot send access or refresh credentials to another origin', () async {
    final session = ClientSession(
      origin: 'https://attacker.example',
      deviceId: 'device_${repeated('D', 43)}',
      clientId: 'test-only-client',
      accessToken: repeated('A', 43),
      accessExpiresAt: 1000,
      refreshToken: repeated('R', 43),
      refreshExpiresAt: 10000,
    );
    await withoutTransport(() async {
      await expectLater(gateway.refresh(session), throwsFormatException);
      await expectLater(gateway.revoke(session), throwsFormatException);
      await expectLater(gateway.getJob(session, 'synthetic-test-job'), throwsFormatException);
      await expectLater(gateway.resumeJob(session, 'synthetic-test-job'), throwsFormatException);
    });
  });
}
