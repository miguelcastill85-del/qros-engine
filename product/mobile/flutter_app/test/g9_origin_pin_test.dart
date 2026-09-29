import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g5_snapshot.dart';

class NoNetwork extends HttpOverrides {
  int clients = 0;
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    clients++;
    throw StateError('Unexpected network access');
  }
}

void main() {
  test('G9 rejects substituted origins before client creation or bearer transfer', () async {
    final trap = NoNetwork();
    const gateway = HttpsG5SnapshotGateway(G5SnapshotVerifier(G9LiveTrust.profile), allowedOrigin: G9LiveTrust.origin);
    await HttpOverrides.runZoned(() async {
      for (final origin in ['https://attacker.invalid', '${G9LiveTrust.origin}.attacker.invalid',
        '${G9LiveTrust.origin}:444', '${G9LiveTrust.origin}/redirect',
        G9LiveTrust.origin.replaceFirst('https:', 'http:'), ' ${G9LiveTrust.origin}']) {
        await expectLater(gateway.fetch(origin, List.filled(43, 'A').join()),
          throwsA(isA<G5SnapshotReject>().having((e) => e.toString(), 'code', contains('ORIGIN_PIN_MISMATCH'))));
      }
    }, createHttpClient: trap.createHttpClient);
    expect(trap.clients, 0);
  });
}
