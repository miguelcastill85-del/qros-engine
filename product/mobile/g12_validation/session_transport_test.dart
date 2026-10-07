import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/local_vault.dart';
import 'package:qros_mobile_studio/core/session_client.dart';

// Ephemeral synthetic credentials. No provider credential or real network.
final device = 'device_' + 'D' * 43;
final session = ClientSession(
  origin: HttpsSessionGateway.trustedOrigin,
  deviceId: device,
  clientId: 'client-synthetic',
  accessToken: 'A' * 43,
  accessExpiresAt: 2000,
  refreshToken: 'R' * 43,
  refreshExpiresAt: 10000,
);
const gateway = HttpsSessionGateway();

class TestHeaders extends Fake implements HttpHeaders {
  @override
  ContentType? contentType;
  final values = <String, Object>{};
  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {
    values[name.toLowerCase()] = value;
  }
}

class TestResponse extends Stream<List<int>> implements HttpClientResponse {
  TestResponse(this.statusCode, this.data, {String mime = 'application/json'})
      : headers = TestHeaders()..contentType = ContentType.parse(mime);
  @override
  final int statusCode;
  @override
  final TestHeaders headers;
  final List<int> data;
  int emitted = 0;
  @override
  StreamSubscription<List<int>> listen(void Function(List<int>)? onData,
      {Function? onError, void Function()? onDone, bool? cancelOnError}) =>
      Stream<List<int>>.fromIterable([data]).map((part) {
        emitted += part.length;
        return part;
      }).listen(onData, onError: onError, onDone: onDone,
          cancelOnError: cancelOnError);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class TestRequest extends Fake implements HttpClientRequest {
  TestRequest(this.reply);
  final TestResponse reply;
  @override
  final TestHeaders headers = TestHeaders();
  @override
  bool followRedirects = true;
  final body = StringBuffer();
  @override
  void write(Object? value) => body.write(value);
  @override
  Future<HttpClientResponse> close() async => reply;
}

class TestClient extends Fake implements HttpClient {
  TestClient(this.reply);
  final TestResponse reply;
  final requests = <TestRequest>[];
  final urls = <Uri>[];
  bool closed = false;
  bool forced = false;
  @override
  Duration? connectionTimeout;
  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async {
    urls.add(url);
    final request = TestRequest(reply);
    requests.add(request);
    return request;
  }
  @override
  void close({bool force = false}) {
    closed = true;
    forced = force;
  }
}

Future<T> withResponse<T>(TestClient client, Future<T> Function() action) =>
    HttpOverrides.runZoned(action, createHttpClient: (_) => client);

Map<String, Object> sessionReply() => {
  'schema': 'QROS_G12_SESSION_V1',
  'client_id': 'client-synthetic',
  'access_token': 'A' * 43,
  'access_expires_at': 2000,
  'refresh_token': 'R' * 43,
  'refresh_expires_at': 10000,
  'scope': 'synthetic:jobs',
  'scientific_authority': 'NONE',
};

TestClient jsonReply(Object value, {int status = 200}) =>
    TestClient(TestResponse(status, utf8.encode(jsonEncode(value))));

class ProxyOverride extends HttpOverrides {
  ProxyOverride(this.port);
  final int port;
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      super.createHttpClient(context)
        ..findProxy = (_) => 'PROXY 127.0.0.1:' + port.toString();
}

// An opaque loopback tunnel preserves the production hostname and default TLS
// verifier. It routes only this test's sockets to a local synthetic TLS server.
class LoopbackTunnel {
  LoopbackTunnel(this.listener, this.upstreamPort, this.drop);
  final ServerSocket listener;
  final int? upstreamPort;
  final bool drop;
  final sockets = <Socket>[];
  final failures = <Object>[];
  int connections = 0;
  final authorities = <String>[];
  static Future<LoopbackTunnel> start({int? upstreamPort, bool drop = false}) async {
    final listener = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final tunnel = LoopbackTunnel(listener, upstreamPort, drop);
    listener.listen(tunnel.accept);
    return tunnel;
  }
  void accept(Socket socket) {
    connections++;
    sockets.add(socket);
    if (drop) {
      socket.destroy();
      return;
    }
    var pending = <int>[];
    Socket? upstream;
    late StreamSubscription<Uint8List> subscription;
    subscription = socket.listen((part) async {
      if (upstream != null) {
        upstream!.add(part);
        return;
      }
      pending.addAll(part);
      final text = latin1.decode(pending);
      final end = text.indexOf('\r\n\r\n');
      if (end < 0) return;
      subscription.pause();
      try {
        final first = text.substring(0, text.indexOf('\r\n'));
        authorities.add(first);
        final expected = 'CONNECT ' +
            Uri.parse(HttpsSessionGateway.trustedOrigin).host + ':443 HTTP/1.1';
        if (first != expected || end > 8192) {
          throw StateError('UNEXPECTED_PROXY_CONNECT');
        }
        upstream = await Socket.connect(InternetAddress.loopbackIPv4,
            upstreamPort!, timeout: const Duration(seconds: 3));
        sockets.add(upstream!);
        upstream!.listen(socket.add,
            onError: (Object _) => socket.destroy(),
            onDone: socket.destroy);
        socket.add(latin1.encode('HTTP/1.1 200 Connection Established\r\n\r\n'));
        if (pending.length > end + 4) upstream!.add(pending.sublist(end + 4));
        pending = [];
        subscription.resume();
      } catch (e) {
        failures.add(e);
        socket.destroy();
        upstream?.destroy();
      }
    }, onError: (Object _) => upstream?.destroy(),
        onDone: () => upstream?.destroy());
  }
  Future<void> close() async {
    for (final socket in sockets) { socket.destroy(); }
    await listener.close();
  }
}

void main() {
  test('valid synthetic session is accepted and transport closes', () async {
    final client = jsonReply(sessionReply());
    final result = await withResponse(client, () => gateway.bootstrap(
        HttpsSessionGateway.trustedOrigin, 'B' * 48, device));
    expect(result.clientId, 'client-synthetic');
    expect(client.urls.single.origin, HttpsSessionGateway.trustedOrigin);
    expect(client.requests.single.followRedirects, false);
    expect(client.closed && client.forced, true);
  });

  test('redirect and denial responses never become sessions or follow locations', () async {
    for (final status in [301, 302, 303, 307, 308, 401, 403, 429, 503]) {
      final client = jsonReply(sessionReply(), status: status);
      client.reply.headers.set(HttpHeaders.locationHeader, 'https://attacker.invalid');
      await withResponse(client, () => expectLater(gateway.bootstrap(
          HttpsSessionGateway.trustedOrigin, 'B' * 48, device),
          throwsFormatException));
      expect(client.urls.length, 1);
      expect(client.requests.single.followRedirects, false);
      expect(client.closed && client.forced, true);
      expect(client.reply.emitted, 0);
    }
  });

  test('wrong MIME, malformed bytes, oversized and non-object replies fail closed', () async {
    final replies = [
      TestResponse(200, utf8.encode(jsonEncode(sessionReply())), mime: 'text/html'),
      TestResponse(200, [0xff]),
      TestResponse(200, utf8.encode('{"schema":')),
      TestResponse(200, utf8.encode('[]')),
      TestResponse(200, utf8.encode('null')),
      TestResponse(200, List<int>.filled(65537, 32)),
    ];
    for (final reply in replies) {
      final client = TestClient(reply);
      await withResponse(client, () => expectLater(gateway.bootstrap(
          HttpsSessionGateway.trustedOrigin, 'B' * 48, device),
          throwsFormatException));
      expect(client.closed && client.forced, true);
    }
  });

  test('session substitution and additional authority fields are rejected', () async {
    final changes = <void Function(Map<String, Object>)>[
      (d) => d['scope'] = 'scientific:write',
      (d) => d['scientific_authority'] = 'APPROVED',
      (d) => d['schema'] = 'UNTRUSTED_SESSION',
      (d) => d['server_public_key'] = 'supplied-by-server',
      (d) => d['access_token'] = 'invalid',
      (d) => d['refresh_expires_at'] = '10000',
    ];
    for (final change in changes) {
      final data = sessionReply();
      change(data);
      final client = jsonReply(data);
      await withResponse(client, () => expectLater(gateway.bootstrap(
          HttpsSessionGateway.trustedOrigin, 'B' * 48, device),
          throwsFormatException));
      expect(client.closed && client.forced, true);
    }
    final changedClient = jsonReply(sessionReply()..['client_id'] = 'other-client');
    await withResponse(changedClient, () =>
        expectLater(gateway.refresh(session), throwsFormatException));
  });

  test('valid revocation acknowledgement is accepted', () async {
    final client = jsonReply({'status': 'revoked'});
    await withResponse(client, () => gateway.revoke(session));
    expect(client.requests.single.headers.values['authorization'],
        'Bearer ' + session.refreshToken);
    expect(client.requests.single.headers.values['x-qros-device'], device);
    expect(client.closed && client.forced, true);
  });

  test('invalid revoke acknowledgements remain unconfirmed and local logout clears secrets', () async {
    for (final body in [
      <String, Object>{},
      {'status': 'active'},
      {'status': 'revoked', 'scientific_authority': 'APPROVED'},
    ]) {
      final client = jsonReply(body);
      await withResponse(client, () =>
          expectLater(gateway.revoke(session), throwsFormatException));
      expect(client.closed && client.forced, true);

      final vault = MemoryLocalVault();
      await vault.write(SessionStore.deviceKey, device);
      await vault.write(SessionStore.sessionKey, jsonEncode(session.toLocalRecord()));
      final store = SessionStore(vault: vault, gateway: gateway,
          clock: () => DateTime.fromMillisecondsSinceEpoch(100000, isUtc: true));
      try {
        await store.initialize();
        await withResponse(jsonReply(body), store.signOut);
        expect(store.session, isNull);
        expect(vault.snapshot.containsKey(SessionStore.sessionKey), false);
        expect(store.warning, 'REMOTE_REVOKE_UNCONFIRMED');
      } finally { store.dispose(); }
    }
  });

  test('disconnected pinned G12 transport cannot produce a session', () async {
    final tunnel = await LoopbackTunnel.start(drop: true);
    try {
      await HttpOverrides.runWithHttpOverrides(() async {
        await expectLater(gateway.bootstrap(HttpsSessionGateway.trustedOrigin,
            'B' * 48, device), throwsA(anyOf(
              isA<SocketException>(), isA<HttpException>(),
              isA<HandshakeException>())));
      }, ProxyOverride(tunnel.listener.port));
      expect(tunnel.connections, greaterThan(0));
    } finally { await tunnel.close(); }
  });

  test('same-host untrusted TLS certificate is rejected before credentials reach server', () async {
    final dir = await Directory.systemTemp.createTemp('qros-g12-tls-');
    HttpServer? server;
    LoopbackTunnel? tunnel;
    var applicationRequests = 0;
    try {
      final host = Uri.parse(HttpsSessionGateway.trustedOrigin).host;
      final cert = dir.path + '/cert.pem';
      final key = dir.path + '/key.pem';
      final created = await Process.run('openssl', [
        'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=' + host, '-addext', 'subjectAltName=DNS:' + host,
        '-keyout', key, '-out', cert,
      ]);
      expect(created.exitCode, 0);
      final context = SecurityContext()..useCertificateChain(cert)..usePrivateKey(key);
      server = await HttpServer.bindSecure(InternetAddress.loopbackIPv4, 0, context);
      server.listen((request) {
        applicationRequests++;
        request.response.statusCode = 200;
        request.response.close();
      }, onError: (Object _) {});
      tunnel = await LoopbackTunnel.start(upstreamPort: server.port);
      await HttpOverrides.runWithHttpOverrides(() async {
        await expectLater(gateway.bootstrap(HttpsSessionGateway.trustedOrigin,
            'B' * 48, device), throwsA(isA<HandshakeException>()));
      }, ProxyOverride(tunnel.listener.port));
      expect(tunnel.authorities, isNotEmpty);
      expect(tunnel.failures, isEmpty);
      expect(applicationRequests, 0);
    } finally {
      await tunnel?.close();
      await server?.close(force: true);
      await dir.delete(recursive: true);
    }
  });
}
