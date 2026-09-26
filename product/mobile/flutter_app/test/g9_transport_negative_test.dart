import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g5_snapshot.dart';

void main() {
  const gateway=HttpsG5SnapshotGateway(G5SnapshotVerifier(G6SyntheticTrust.profile));
  final token=List.filled(43,'A').join();
  test('disconnected endpoint cannot produce verified snapshot',() async {
    final socket=await ServerSocket.bind(InternetAddress.loopbackIPv4,0);
    final port=socket.port;
    await socket.close();
    await expectLater(gateway.fetch('https://127.0.0.1:$port',token),throwsA(isA<SocketException>()));
  });
  test('substituted self-signed TLS server certificate fails before authenticated receipt',() async {
    final temp=await Directory.systemTemp.createTemp('qros-g9-tls-');
    HttpServer? server;
    var authenticatedRequests=0;
    try {
      final cert='${temp.path}/cert.pem';final key='${temp.path}/key.pem';
      final result=await Process.run('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1',
        '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',key,'-out',cert]);
      expect(result.exitCode,0);
      final context=SecurityContext()..useCertificateChain(cert)..usePrivateKey(key);
      server=await HttpServer.bindSecure(InternetAddress.loopbackIPv4,0,context);
      server.listen((r){authenticatedRequests++;r.response.statusCode=200;r.response.close();},onError:(Object _){});
      await expectLater(gateway.fetch('https://127.0.0.1:${server.port}',token),throwsA(isA<HandshakeException>()));
      expect(authenticatedRequests,0);
    } finally {await server?.close(force:true);await temp.delete(recursive:true);}
  });
}
