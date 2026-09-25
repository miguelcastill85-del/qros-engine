import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'g6_signed_snapshot.dart';

/// G5 local TEST_ONLY integration seam. No production endpoint or credentials
/// embedded in the app. No certificate bypass, insecure fallback or redirects.
abstract class G6SyntheticTransport {
  Future<List<int>> getSnapshot({required String origin,required String token,
    required String project, String? testCaPem});
}

class G6LocalTlsTransport implements G6SyntheticTransport {
  const G6LocalTlsTransport();
  @override
  Future<List<int>> getSnapshot({required String origin,required String token,
      required String project,String? testCaPem}) async {
    final u=Uri.tryParse(origin.trim());
    if(u==null || u.scheme!='https' || !['127.0.0.1','localhost'].contains(u.host) ||
        u.userInfo.isNotEmpty || (u.path.isNotEmpty && u.path!='/') ||
        u.hasQuery || u.hasFragment || u.port==0) {
      throw const G6Reject('LOOPBACK_HTTPS_ORIGIN_ONLY');
    }
    if(!RegExp(r'^[A-Za-z0-9_-]{43,128}$').hasMatch(token)) {
      throw const G6Reject('TOKEN_FORMAT');
    }
    if(!RegExp(r'^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,95}$').hasMatch(project)) {
      throw const G6Reject('PROJECT_FORMAT');
    }
    // Trust the system root store and any explicitly supplied local test CA.
    // The CA must be acquired independently of this network response.
    final ssl=SecurityContext(withTrustedRoots:true);
    if(testCaPem!=null && testCaPem.trim().isNotEmpty) {
      if(testCaPem.length>8192 || !testCaPem.contains('BEGIN CERTIFICATE')) {
        throw const G6Reject('TEST_CA_CERTIFICATE_INVALID');
      }
      ssl.setTrustedCertificatesBytes(utf8.encode(testCaPem));
    }
    final client=HttpClient(context:ssl)..connectionTimeout=const Duration(seconds:6);
    try {
      final request=await client.getUrl(u.replace(path:'/v1/demo-snapshot')).timeout(const Duration(seconds:8));
      request.headers.set(HttpHeaders.authorizationHeader,'Bearer $token');
      request.headers.set('X-QROS-Project',project);
      request.headers.set(HttpHeaders.acceptHeader,'application/json');
      request.followRedirects=false;
      final response=await request.close().timeout(const Duration(seconds:8));
      if(response.isRedirect || response.statusCode!=200 ||
          response.headers.contentType?.mimeType!='application/json') {
        throw const G6Reject('GATEWAY_NON_200_OR_REDIRECT');
      }
      final bytes=<int>[];
      await for(final chunk in response.timeout(const Duration(seconds:8))) {
        bytes.addAll(chunk);
        if(bytes.length>65536) throw const G6Reject('OVERSIZE_SIGNED_SNAPSHOT');
      }
      return bytes;
    } finally {client.close(force:true);}
  }
}

class G6SnapshotGateway {
  G6SnapshotGateway({G6SyntheticTransport? transport}):transport=transport??const G6LocalTlsTransport();
  final G6SyntheticTransport transport;
  G6TrustPin? _sessionPin;
  G6SnapshotVerifier? _sessionVerifier;
  Future<G6VerifiedSnapshot> fetch({required String origin,required String token,
      required G6TrustPin outOfBandPin,String? testCaPem}) async {
    final previous=_sessionPin;
    if (previous!=null && (previous.tenant!=outOfBandPin.tenant ||
        previous.project!=outOfBandPin.project || previous.campaign!=outOfBandPin.campaign ||
        previous.witnessId!=outOfBandPin.witnessId ||
        previous.publicKeyB64!=outOfBandPin.publicKeyB64)) {
      throw const G6Reject('PIN_CHANGED_DURING_SESSION');
    }
    final verifier=_sessionVerifier??G6SnapshotVerifier(trustPin:outOfBandPin);
    final bytes=await transport.getSnapshot(origin:origin,token:token,
       project:outOfBandPin.project,testCaPem:testCaPem);
    final checked=await verifier.verify(bytes);
    _sessionPin??=outOfBandPin;
    _sessionVerifier??=verifier;
    return checked;
  }
}
