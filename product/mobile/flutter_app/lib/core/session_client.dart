import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:cryptography/cryptography.dart';

import 'local_vault.dart';
import 'universe_ir.dart';

class ClientSession {
  const ClientSession({
    required this.origin,
    required this.deviceId,
    required this.clientId,
    required this.accessToken,
    required this.accessExpiresAt,
    required this.refreshToken,
    required this.refreshExpiresAt,
  });

  final String origin;
  final String deviceId;
  final String clientId;
  final String accessToken;
  final int accessExpiresAt;
  final String refreshToken;
  final int refreshExpiresAt;

  Map<String, Object?> toLocalRecord() => {
        'schema': 'QROS_G12_LOCAL_SESSION_V1',
        'origin': origin,
        'device_id': deviceId,
        'client_id': clientId,
        'access_token': accessToken,
        'access_expires_at': accessExpiresAt,
        'refresh_token': refreshToken,
        'refresh_expires_at': refreshExpiresAt,
      };

  static ClientSession fromLocalRecord(Map<String, dynamic> data) {
    const keys = {
      'schema',
      'origin',
      'device_id',
      'client_id',
      'access_token',
      'access_expires_at',
      'refresh_token',
      'refresh_expires_at',
    };
    if (data.length != keys.length ||
        !data.keys.every(keys.contains) ||
        data['schema'] != 'QROS_G12_LOCAL_SESSION_V1' ||
        data['origin'] is! String ||
        data['device_id'] is! String ||
        data['client_id'] is! String ||
        data['access_token'] is! String ||
        data['access_expires_at'] is! int ||
        data['refresh_token'] is! String ||
        data['refresh_expires_at'] is! int) {
      throw const FormatException('LOCAL_SESSION_SCHEMA_INVALID');
    }
    return ClientSession(
      origin: data['origin'] as String,
      deviceId: data['device_id'] as String,
      clientId: data['client_id'] as String,
      accessToken: data['access_token'] as String,
      accessExpiresAt: data['access_expires_at'] as int,
      refreshToken: data['refresh_token'] as String,
      refreshExpiresAt: data['refresh_expires_at'] as int,
    );
  }
}

class SyntheticJob {
  const SyntheticJob({
    required this.jobId,
    required this.clientId,
    required this.requestId,
    required this.state,
    required this.phase,
    required this.progress,
    required this.searchSpaceSha256,
    required this.toyEnumerationSha256,
    required this.rawBirths,
    required this.resultSha256,
  });

  final String jobId;
  final String clientId;
  final String requestId;
  final String state;
  final int phase;
  final int progress;
  final String searchSpaceSha256;
  final String toyEnumerationSha256;
  final int rawBirths;
  final String? resultSha256;

  bool get complete => state == 'COMPLETE';

  Map<String, Object?> toLocalRecord() => {
        'schema': 'QROS_G12_LOCAL_JOB_V1',
        'job_id': jobId,
        'client_id': clientId,
        'request_id': requestId,
        'state': state,
        'phase': phase,
        'progress': progress,
        'search_space_sha256': searchSpaceSha256,
        'toy_enumeration_sha256': toyEnumerationSha256,
        'raw_births': rawBirths,
        'result_sha256': resultSha256,
      };

  static SyntheticJob fromServer(Map<String, dynamic> data) {
    const states = {'PREPARED', 'VALIDATED', 'CHECKPOINTED', 'COMPLETE'};
    if (data['schema'] != 'QROS_G12_SYNTHETIC_JOB_V1' ||
        data['job_id'] is! String ||
        data['client_id'] is! String ||
        data['request_id'] is! String ||
        data['state'] is! String ||
        !states.contains(data['state']) ||
        data['phase'] is! int ||
        data['progress'] is! int ||
        data['input'] is! Map<String, dynamic> ||
        data['economic_tests'] != 0 ||
        data['scientific_approval'] != false ||
        data['holdout_open'] != false ||
        data['ga2_open'] != false ||
        data['mt5_executed'] != false) {
      throw const FormatException('UNSAFE_JOB_RESPONSE');
    }
    final input = data['input'] as Map<String, dynamic>;
    if (input['search_space_sha256'] is! String ||
        input['toy_enumeration_sha256'] is! String ||
        input['raw_births'] is! int) {
      throw const FormatException('INVALID_JOB_INPUT_ECHO');
    }
    String? resultSha;
    if (data['state'] == 'COMPLETE') {
      final result = data['result'];
      if (result is! Map<String, dynamic> ||
          result['schema'] != 'QROS_G12_SYNTHETIC_JOB_RESULT_V1' ||
          result['classification'] != 'TEST_ONLY_SYNTHETIC_INFRASTRUCTURE' ||
          result['economic_tests'] != 0 ||
          result['scientific_approval'] != false ||
          result['holdout_open'] != false ||
          result['ga2_open'] != false ||
          result['mt5_executed'] != false ||
          result['result_sha256'] is! String) {
        throw const FormatException('UNSAFE_JOB_RESULT');
      }
      resultSha = result['result_sha256'] as String;
    }
    return SyntheticJob(
      jobId: data['job_id'] as String,
      clientId: data['client_id'] as String,
      requestId: data['request_id'] as String,
      state: data['state'] as String,
      phase: data['phase'] as int,
      progress: data['progress'] as int,
      searchSpaceSha256: input['search_space_sha256'] as String,
      toyEnumerationSha256: input['toy_enumeration_sha256'] as String,
      rawBirths: input['raw_births'] as int,
      resultSha256: resultSha,
    );
  }

  /// Checks result integrity and job binding, not independent authenticity.
  static Future<SyntheticJob> verifyServer(Map<String, dynamic> data) async {
    final job = fromServer(data);
    const stages = ['PREPARED', 'VALIDATED', 'CHECKPOINTED', 'COMPLETE'];
    const percentages = [0, 34, 67, 100];
    if (job.phase < 0 || job.phase > 3 ||
        stages[job.phase] != job.state || percentages[job.phase] != job.progress ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(job.searchSpaceSha256) ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(job.toyEnumerationSha256) ||
        job.rawBirths < 1 || job.rawBirths > 10000) {
      throw const FormatException('JOB_STATE_INVALID');
    }
    if (!job.complete) {
      if (data['result'] != null) {
        throw const FormatException('PREMATURE_JOB_RESULT');
      }
      return job;
    }
    final result = Map<String, dynamic>.from(data['result'] as Map);
    const keys = {
      'schema', 'classification', 'job_id', 'search_space_sha256',
      'toy_enumeration_sha256', 'raw_births', 'work_units_completed',
      'economic_tests', 'scientific_approval', 'holdout_open', 'ga2_open',
      'mt5_executed', 'result_sha256',
    };
    if (result.length != keys.length || !result.keys.every(keys.contains) ||
        result['job_id'] != job.jobId ||
        result['search_space_sha256'] != job.searchSpaceSha256 ||
        result['toy_enumeration_sha256'] != job.toyEnumerationSha256 ||
        result['raw_births'] != job.rawBirths ||
        result['work_units_completed'] != 3) {
      throw const FormatException('JOB_RESULT_BINDING_MISMATCH');
    }
    final claimed = result.remove('result_sha256');
    final ordered = <String, dynamic>{
      for (final key in result.keys.toList()..sort()) key: result[key],
    };
    final digest = await Sha256().hash(utf8.encode(jsonEncode(ordered)));
    final actual = digest.bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    if (claimed != actual) throw const FormatException('JOB_RESULT_HASH_MISMATCH');
    return job;
  }

  static SyntheticJob fromLocalRecord(Map<String, dynamic> data) {
    if (data['schema'] != 'QROS_G12_LOCAL_JOB_V1' ||
        data['job_id'] is! String ||
        data['client_id'] is! String ||
        data['request_id'] is! String ||
        data['state'] is! String ||
        data['phase'] is! int ||
        data['progress'] is! int ||
        data['search_space_sha256'] is! String ||
        data['toy_enumeration_sha256'] is! String ||
        data['raw_births'] is! int ||
        (data['result_sha256'] != null && data['result_sha256'] is! String)) {
      throw const FormatException('LOCAL_JOB_SCHEMA_INVALID');
    }
    return SyntheticJob(
      jobId: data['job_id'] as String,
      clientId: data['client_id'] as String,
      requestId: data['request_id'] as String,
      state: data['state'] as String,
      phase: data['phase'] as int,
      progress: data['progress'] as int,
      searchSpaceSha256: data['search_space_sha256'] as String,
      toyEnumerationSha256: data['toy_enumeration_sha256'] as String,
      rawBirths: data['raw_births'] as int,
      resultSha256: data['result_sha256'] as String?,
    );
  }
}

abstract interface class SessionGateway {
  Future<ClientSession> bootstrap(
      String origin, String bootstrapToken, String deviceId);
  Future<ClientSession> refresh(ClientSession current);
  Future<void> revoke(ClientSession current);
  Future<SyntheticJob> createJob(
      ClientSession current, UniverseSessionDraft draft, String requestId);
  Future<SyntheticJob> getJob(ClientSession current, String jobId);
  Future<SyntheticJob> resumeJob(ClientSession current, String jobId);
}

class HttpsSessionGateway implements SessionGateway {
  const HttpsSessionGateway();

  Uri _origin(String value) {
    final input = Uri.tryParse(value.trim());
    if (input == null ||
        input.scheme != 'https' ||
        input.host.isEmpty ||
        input.userInfo.isNotEmpty ||
        (input.path.isNotEmpty && input.path != '/') ||
        input.query.isNotEmpty ||
        input.fragment.isNotEmpty) {
      throw const FormatException('HTTPS_ORIGIN_REQUIRED');
    }
    return input.replace(path: '');
  }

  Future<Map<String, dynamic>> _jsonRequest({
    required String origin,
    required String path,
    required String method,
    required String bearer,
    String? deviceId,
    Map<String, Object?>? body,
    Set<int> accepted = const {200},
  }) async {
    final base = _origin(origin);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final request = await client
          .openUrl(method, base.replace(path: path))
          .timeout(const Duration(seconds: 8));
      request.followRedirects = false;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $bearer');
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (deviceId != null) request.headers.set('X-QROS-Device', deviceId);
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response =
          await request.close().timeout(const Duration(seconds: 8));
      if (!accepted.contains(response.statusCode) ||
          response.headers.contentType?.mimeType != 'application/json') {
        throw const FormatException('REMOTE_REQUEST_REJECTED');
      }
      final bytes = <int>[];
      await for (final part
          in response.timeout(const Duration(seconds: 8))) {
        bytes.addAll(part);
        if (bytes.length > 65536) {
          throw const FormatException('REMOTE_RESPONSE_TOO_LARGE');
        }
      }
      final parsed = jsonDecode(utf8.decode(bytes, allowMalformed: false));
      if (parsed is! Map<String, dynamic>) {
        throw const FormatException('REMOTE_RESPONSE_NOT_OBJECT');
      }
      return parsed;
    } finally {
      client.close(force: true);
    }
  }

  ClientSession _session(
      Map<String, dynamic> data, String origin, String deviceId) {
    const keys = {
      'schema',
      'client_id',
      'access_token',
      'access_expires_at',
      'refresh_token',
      'refresh_expires_at',
      'scope',
      'scientific_authority',
    };
    if (data.length != keys.length ||
        !data.keys.every(keys.contains) ||
        data['schema'] != 'QROS_G12_SESSION_V1' ||
        data['client_id'] is! String ||
        data['access_token'] is! String ||
        data['refresh_token'] is! String ||
        data['access_expires_at'] is! int ||
        data['refresh_expires_at'] is! int ||
        data['scope'] != 'synthetic:jobs' ||
        data['scientific_authority'] != 'NONE') {
      throw const FormatException('UNSAFE_SESSION_RESPONSE');
    }
    final access = data['access_token'] as String;
    final refresh = data['refresh_token'] as String;
    if (!RegExp(r'^[A-Za-z0-9_-]{43}$').hasMatch(access) ||
        !RegExp(r'^[A-Za-z0-9_-]{43}$').hasMatch(refresh)) {
      throw const FormatException('SESSION_TOKEN_FORMAT');
    }
    return ClientSession(
      origin: origin.trim(),
      deviceId: deviceId,
      clientId: data['client_id'] as String,
      accessToken: access,
      accessExpiresAt: data['access_expires_at'] as int,
      refreshToken: refresh,
      refreshExpiresAt: data['refresh_expires_at'] as int,
    );
  }

  @override
  Future<ClientSession> bootstrap(
      String origin, String bootstrapToken, String deviceId) async {
    if (!RegExp(r'^[A-Za-z0-9_-]{48}$').hasMatch(bootstrapToken)) {
      throw const FormatException('BOOTSTRAP_TOKEN_FORMAT');
    }
    final data = await _jsonRequest(
      origin: origin,
      path: '/v1/session/bootstrap',
      method: 'POST',
      bearer: bootstrapToken,
      body: {'device_id': deviceId},
    );
    return _session(data, origin, deviceId);
  }

  @override
  Future<ClientSession> refresh(ClientSession current) async {
    final data = await _jsonRequest(
      origin: current.origin,
      path: '/v1/session/refresh',
      method: 'POST',
      bearer: current.refreshToken,
      deviceId: current.deviceId,
      body: const {},
    );
    final next = _session(data, current.origin, current.deviceId);
    if (next.clientId != current.clientId) {
      throw const FormatException('CLIENT_ID_DRIFT');
    }
    return next;
  }

  @override
  Future<void> revoke(ClientSession current) async {
    await _jsonRequest(
      origin: current.origin,
      path: '/v1/session/revoke',
      method: 'POST',
      bearer: current.refreshToken,
      deviceId: current.deviceId,
      body: const {},
    );
  }

  @override
  Future<SyntheticJob> createJob(
      ClientSession current, UniverseSessionDraft draft, String requestId) async {
    final data = await _jsonRequest(
      origin: current.origin,
      path: '/v1/jobs/synthetic',
      method: 'POST',
      bearer: current.accessToken,
      deviceId: current.deviceId,
      body: {
        'request_id': requestId,
        'search_space_sha256': draft.searchSpaceSha256,
        'toy_enumeration_sha256': draft.toyEnumerationSha256,
        'raw_births': draft.blueprint.rawBirths,
      },
      accepted: const {200, 201},
    );
    final job = await SyntheticJob.verifyServer(data);
    if (job.clientId != current.clientId ||
        job.requestId != requestId ||
        job.searchSpaceSha256 != draft.searchSpaceSha256 ||
        job.toyEnumerationSha256 != draft.toyEnumerationSha256 ||
        job.rawBirths != draft.blueprint.rawBirths) {
      throw const FormatException('JOB_BINDING_MISMATCH');
    }
    return job;
  }

  @override
  Future<SyntheticJob> getJob(
      ClientSession current, String jobId) async {
    final data = await _jsonRequest(
      origin: current.origin,
      path: '/v1/jobs/synthetic/$jobId',
      method: 'GET',
      bearer: current.accessToken,
      deviceId: current.deviceId,
    );
    final job = await SyntheticJob.verifyServer(data);
    if (job.clientId != current.clientId || job.jobId != jobId) {
      throw const FormatException('JOB_IDENTITY_MISMATCH');
    }
    return job;
  }

  @override
  Future<SyntheticJob> resumeJob(
      ClientSession current, String jobId) async {
    final data = await _jsonRequest(
      origin: current.origin,
      path: '/v1/jobs/synthetic/$jobId/resume',
      method: 'POST',
      bearer: current.accessToken,
      deviceId: current.deviceId,
      body: const {},
    );
    final job = await SyntheticJob.verifyServer(data);
    if (job.clientId != current.clientId || job.jobId != jobId) {
      throw const FormatException('JOB_IDENTITY_MISMATCH');
    }
    return job;
  }
}

class SessionStore extends ChangeNotifier {
  SessionStore({
    required LocalVault vault,
    required SessionGateway gateway,
    DateTime Function()? clock,
    String Function()? deviceIdFactory,
  })  : _vault = vault,
        _gateway = gateway,
        _clock = clock ?? DateTime.now,
        _deviceIdFactory = deviceIdFactory ?? _newDeviceId;

  static const sessionKey = 'qros.g12.session.v1';
  static const deviceKey = 'qros.g12.device.v1';

  final LocalVault _vault;
  final SessionGateway _gateway;
  final DateTime Function() _clock;
  final String Function() _deviceIdFactory;

  final LocalMutationQueue _queue = LocalMutationQueue();

  String? _deviceId;
  ClientSession? _session;
  String? _warning;

  String? get deviceId => _deviceId;
  ClientSession? get session => _session;
  bool get enrolled => _session != null;
  String? get warning => _warning;

  static String _newDeviceId() {
    final r = Random.secure();
    final bytes = List<int>.generate(32, (_) => r.nextInt(256));
    return 'device_${base64Url.encode(bytes).replaceAll('=', '')}';
  }

  int get _nowSeconds => _clock().toUtc().millisecondsSinceEpoch ~/ 1000;

  Future<void> initialize() => _queue.run(() async {
    try {
      var id = await _vault.read(deviceKey);
      if (id == null || !RegExp(r'^device_[A-Za-z0-9_-]{43}$').hasMatch(id)) {
        id = _deviceIdFactory();
        await _vault.write(deviceKey, id);
      }
      _deviceId = id;
      final raw = await _vault.read(sessionKey);
      if (raw != null && raw.isNotEmpty) {
        final decoded = jsonDecode(raw);
        if (decoded is! Map<String, dynamic>) {
          throw const FormatException('LOCAL_SESSION_INVALID');
        }
        final restored = ClientSession.fromLocalRecord(decoded);
        if (restored.deviceId != id || restored.refreshExpiresAt <= _nowSeconds) {
          await _vault.delete(sessionKey);
        } else {
          _session = restored;
        }
      }
      _warning = null;
    } catch (_) {
      _session = null;
      _warning = 'SESSION_LOCAL_RECOVERY_FAILED';
    }
    notifyListeners();
    });

  Future<void> _persist(ClientSession value) async {
    await _vault.write(sessionKey, jsonEncode(value.toLocalRecord()));
    _session = value;
    _warning = null;
    notifyListeners();
  }

  Future<ClientSession> enroll(String origin, String bootstrapToken) => _queue.run(() async {
    final id = _deviceId ?? _deviceIdFactory();
    if (_deviceId == null) {
      await _vault.write(deviceKey, id);
      _deviceId = id;
    }
    final next = await _gateway.bootstrap(origin, bootstrapToken, id);
    await _persist(next);
    return next;
    });

  Future<ClientSession> renew() => _queue.run(_renew);

  Future<ClientSession> _renew() async {
    final current = _session;
    if (current == null || current.refreshExpiresAt <= _nowSeconds) {
      throw const FormatException('SESSION_NOT_RENEWABLE');
    }
    final next = await _gateway.refresh(current);
    await _persist(next);
    return next;
  }

  Future<ClientSession> ensureAccess() => _queue.run(() async {
    final current = _session;
    if (current == null) throw const FormatException('SESSION_REQUIRED');
    if (current.refreshExpiresAt <= _nowSeconds) {
      await _vault.delete(sessionKey);
      _session = null;
      notifyListeners();
      throw const FormatException('SESSION_EXPIRED');
    }
    if (current.accessExpiresAt - _nowSeconds <= 60) return _renew();
    return current;
    });

  Future<void> signOut() => _queue.run(() async {
    final current = _session;
    if (current != null && current.refreshExpiresAt > _nowSeconds) {
      try {
        await _gateway.revoke(current);
      } catch (_) {
        _warning = 'REMOTE_REVOKE_UNCONFIRMED';
      }
    }
    await _vault.delete(sessionKey);
    _session = null;
    notifyListeners();
    });
}

class SyntheticJobStore extends ChangeNotifier {
  SyntheticJobStore({
    required LocalVault vault,
    required SessionStore sessionStore,
    required SessionGateway gateway,
    String Function()? requestIdFactory,
  })  : _vault = vault,
        _sessionStore = sessionStore,
        _gateway = gateway,
        _requestIdFactory = requestIdFactory ?? _newRequestId;

  static const jobKey = 'qros.g12.job.v1';
  static const pendingKey = 'qros.g12.pending.v1';

  final LocalVault _vault;
  final SessionStore _sessionStore;
  final SessionGateway _gateway;
  final String Function() _requestIdFactory;

  final LocalMutationQueue _queue = LocalMutationQueue();
  bool _initialized = false;
  bool _loadBlocked = true;

  SyntheticJob? _job;
  String? _warning;

  SyntheticJob? get job => _job;
  String? get warning => _warning;

  static String _newRequestId() {
    final r = Random.secure();
    final bytes = List<int>.generate(16, (_) => r.nextInt(256));
    return 'req_${base64Url.encode(bytes).replaceAll('=', '')}';
  }

  Future<void> initialize() => _queue.run(_load);

  Future<void> _load() async {
    if (_initialized) return;
    _initialized = true;
    try {
      final raw = await _vault.read(jobKey);
      if (raw != null && raw.isNotEmpty) {
        final decoded = jsonDecode(raw);
        if (decoded is! Map<String, dynamic>) {
          throw const FormatException('LOCAL_JOB_INVALID');
        }
        _job = SyntheticJob.fromLocalRecord(decoded);
      }
      _loadBlocked = false;
      _warning = null;
    } catch (_) {
      _job = null;
      _warning = 'JOB_LOCAL_RECOVERY_FAILED';
    }
    notifyListeners();
  }

  Future<void> _ensureLoaded() async {
    await _load();
    if (_loadBlocked) throw const FormatException('JOB_LOCAL_RECOVERY_REQUIRED');
  }

  void _checkContinuity(SyntheticJob old, SyntheticJob next) {
    if (old.clientId != next.clientId || old.jobId != next.jobId ||
        old.requestId != next.requestId ||
        old.searchSpaceSha256 != next.searchSpaceSha256 ||
        old.toyEnumerationSha256 != next.toyEnumerationSha256 ||
        old.rawBirths != next.rawBirths || next.phase < old.phase) {
      throw const FormatException('JOB_CONTINUITY_MISMATCH');
    }
  }

  Future<void> _persist(SyntheticJob value) async {
    await _vault.write(jobKey, jsonEncode(value.toLocalRecord()));
    _job = value;
    _warning = null;
    notifyListeners();
  }

  Future<SyntheticJob> start(UniverseSessionDraft draft) => _queue.run(() async {
    await _ensureLoaded();
    final session = await _sessionStore.ensureAccess();
    final current = _job;
    if (current != null &&
        current.clientId == session.clientId &&
        current.searchSpaceSha256 == draft.searchSpaceSha256 &&
        current.toyEnumerationSha256 == draft.toyEnumerationSha256 &&
        current.rawBirths == draft.blueprint.rawBirths) {
      await _vault.delete(pendingKey);
      return _sync();
    }
    final binding = <String, Object?>{
      'schema': 'QROS_G12_PENDING_REQUEST_V1',
      'client_id': session.clientId,
      'origin': session.origin,
      'search_space_sha256': draft.searchSpaceSha256,
      'toy_enumeration_sha256': draft.toyEnumerationSha256,
      'raw_births': draft.blueprint.rawBirths,
    };
    final raw = await _vault.read(pendingKey);
    String requestId;
    if (raw != null) {
      final pending = jsonDecode(raw);
      if (pending is! Map<String, dynamic> ||
          pending.length != binding.length + 1 ||
          pending['request_id'] is! String ||
          binding.entries.any((e) => pending[e.key] != e.value)) {
        throw const FormatException('PENDING_JOB_REQUIRES_RECOVERY');
      }
      requestId = pending['request_id'] as String;
    } else {
      requestId = _requestIdFactory();
      await _vault.write(pendingKey, jsonEncode({...binding, 'request_id': requestId}));
    }
    final next = await _gateway.createJob(session, draft, requestId);
    if (next.clientId != session.clientId || next.requestId != requestId ||
        next.searchSpaceSha256 != draft.searchSpaceSha256 ||
        next.toyEnumerationSha256 != draft.toyEnumerationSha256 ||
        next.rawBirths != draft.blueprint.rawBirths) {
      throw const FormatException('JOB_BINDING_MISMATCH');
    }
    await _persist(next);
    await _vault.delete(pendingKey);
    return next;
    });

  Future<SyntheticJob> sync() => _queue.run(_sync);

  Future<SyntheticJob> _sync() async {
    await _ensureLoaded();
    final current = _job;
    if (current == null) throw const FormatException('JOB_REQUIRED');
    final session = await _sessionStore.ensureAccess();
    final next = await _gateway.getJob(session, current.jobId);
    _checkContinuity(current, next);
    await _persist(next);
    return next;
  }

  Future<SyntheticJob> resume() => _queue.run(() async {
    await _ensureLoaded();
    final current = _job;
    if (current == null) throw const FormatException('JOB_REQUIRED');
    if (current.complete) return current;
    final session = await _sessionStore.ensureAccess();
    final next = await _gateway.resumeJob(session, current.jobId);
    _checkContinuity(current, next);
    await _persist(next);
    return next;
    });

  Future<void> clear() => _queue.run(() async {
    await _ensureLoaded();
    await _vault.delete(pendingKey);
    await _vault.delete(jobKey);
    _job = null;
    _warning = null;
    notifyListeners();
    });
}
