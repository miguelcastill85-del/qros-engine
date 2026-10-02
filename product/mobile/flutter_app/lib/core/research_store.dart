import 'dart:collection';
import 'dart:convert';
import 'package:flutter/foundation.dart';

import 'local_vault.dart';

@immutable
class ResearchProject {
  const ResearchProject({
    required this.id,
    required this.title,
    required this.thesis,
    required this.symbol,
    required this.side,
    required this.timeframe,
    required this.state,
    required this.isSample,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String thesis;
  final String symbol;
  final String side;
  final String timeframe;
  final String state;
  final bool isSample;
  final DateTime createdAt;

  String get readableState =>
      isSample ? 'PREREGISTRADO · SIMULADO' : 'BORRADOR LOCAL';

  ResearchProject copyWith({
    String? title,
    String? thesis,
    String? symbol,
    String? side,
    String? timeframe,
  }) =>
      ResearchProject(
        id: id,
        title: title ?? this.title,
        thesis: thesis ?? this.thesis,
        symbol: symbol ?? this.symbol,
        side: side ?? this.side,
        timeframe: timeframe ?? this.timeframe,
        state: state,
        isSample: isSample,
        createdAt: createdAt,
      );

  Map<String, Object?> toEvidenceRecord() => {
        'project_id': id,
        'title': title,
        'thesis': thesis,
        'symbol': symbol,
        'side': side,
        'timeframe': timeframe,
        'display_state': readableState,
        'scientific_state': isSample ? 'SIMULATED_SAMPLE' : 'NONE',
        'is_sample': isSample,
        'created_at': createdAt.toUtc().toIso8601String(),
        'strategy_contract_frozen': false,
        'economic_backtest_executed': false,
        'holdout_accessed': false,
        'mt5_parity_executed': false,
        'scientific_approval': false,
        'external_authority_verified': false,
        'receipt_sha256': null,
      };
}

class ResearchStore extends ChangeNotifier {
  ResearchStore({
    DateTime Function()? clock,
    LocalVault? vault,
  })  : _clock = clock ?? DateTime.now,
        _vault = vault ?? MemoryLocalVault() {
    _projects.add(_sample);
  }

  static final ResearchProject _sample = ResearchProject(
    id: 'DEMO-001',
    title: 'Ruptura y recuperación',
    thesis:
        'Hipótesis ilustrativa de recuperación de nivel. Sin operaciones ni PnL.',
    symbol: 'XAUUSD',
    side: 'BUY',
    timeframe: 'M15',
    state: 'SIMULATED_SAMPLE',
    isSample: true,
    createdAt: DateTime.utc(2026, 1, 1),
  );

  static const symbols = ['XAUUSD', 'NQX'];
  static const sides = ['BUY', 'SELL'];
  static const timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4'];

  static const backupSchema = 'QROS_LOCAL_DRAFT_BACKUP_V1';
  static const storageSchemaV1 = 'QROS_LOCAL_DRAFT_STORE_V1';
  static const storageSchemaV2 = 'QROS_LOCAL_DRAFT_STORE_V2';
  static const storageKey = 'qros.research.drafts.v2';
  static const maxDrafts = 1000;
  static const maxBackupCharacters = 2000000;

  final DateTime Function() _clock;
  final LocalVault _vault;
  final List<ResearchProject> _projects = [];
  int _draftSequence = 0;
  String? _storageWarning;
  bool _initialized = false;

  UnmodifiableListView<ResearchProject> get projects =>
      UnmodifiableListView(_projects);
  int get localDraftCount => _projects.where((p) => !p.isSample).length;
  int get actualBacktests => 0;
  bool get engineConnected => false;
  String? get storageWarning => _storageWarning;
  bool get initialized => _initialized;
  bool get persistentStorageHealthy => _initialized && _storageWarning == null;

  Future<void> initialize() async {
    if (_initialized) return;
    try {
      final raw = await _vault.read(storageKey);
      if (raw != null && raw.isNotEmpty) {
        final restored = _decodePersistent(raw);
        _projects
          ..clear()
          ..addAll(restored.projects)
          ..add(_sample);
        _draftSequence = restored.sequence;
        if (restored.migrated) {
          await _writeSnapshot(_projects, _draftSequence);
        }
      }
      _storageWarning = null;
    } on LocalPersistenceException catch (e) {
      _storageWarning = e.code;
    } catch (_) {
      _storageWarning = 'SECURE_STORAGE_UNAVAILABLE';
    } finally {
      _initialized = true;
      notifyListeners();
    }
  }

  void _validateFields({
    required String title,
    required String thesis,
    required String symbol,
    required String side,
    required String timeframe,
  }) {
    if (title.length < 3 || title.length > 72) {
      throw ArgumentError('El título debe tener entre 3 y 72 caracteres.');
    }
    if (thesis.length < 10 || thesis.length > 500) {
      throw ArgumentError('La hipótesis debe tener entre 10 y 500 caracteres.');
    }
    if (!symbols.contains(symbol) ||
        !sides.contains(side) ||
        !timeframes.contains(timeframe)) {
      throw ArgumentError('Activo, dirección o timeframe no permitido.');
    }
  }

  Future<ResearchProject> createLocalDraft({
    required String title,
    required String thesis,
    required String symbol,
    required String side,
    required String timeframe,
  }) async {
    final cleanedTitle = title.trim();
    final cleanedThesis = thesis.trim();
    _validateFields(
      title: cleanedTitle,
      thesis: cleanedThesis,
      symbol: symbol,
      side: side,
      timeframe: timeframe,
    );
    if (localDraftCount >= maxDrafts) {
      throw ArgumentError('Límite de 1000 borradores alcanzado.');
    }
    final next = _draftSequence + 1;
    final project = ResearchProject(
      id: 'LOCAL-${next.toString().padLeft(4, '0')}',
      title: cleanedTitle,
      thesis: cleanedThesis,
      symbol: symbol,
      side: side,
      timeframe: timeframe,
      state: 'LOCAL_DRAFT_NOT_FROZEN',
      isSample: false,
      createdAt: _clock(),
    );
    final candidate = <ResearchProject>[project, ..._projects];
    await _writeSnapshot(candidate, next);
    _draftSequence = next;
    _projects
      ..clear()
      ..addAll(candidate);
    _storageWarning = null;
    notifyListeners();
    return project;
  }

  Future<ResearchProject> updateLocalDraft({
    required String id,
    required String title,
    required String thesis,
    required String symbol,
    required String side,
    required String timeframe,
  }) async {
    final index = _projects.indexWhere((p) => p.id == id && !p.isSample);
    if (index < 0) {
      throw ArgumentError('Borrador local no encontrado.');
    }
    final cleanedTitle = title.trim();
    final cleanedThesis = thesis.trim();
    _validateFields(
      title: cleanedTitle,
      thesis: cleanedThesis,
      symbol: symbol,
      side: side,
      timeframe: timeframe,
    );
    final updated = _projects[index].copyWith(
      title: cleanedTitle,
      thesis: cleanedThesis,
      symbol: symbol,
      side: side,
      timeframe: timeframe,
    );
    final candidate = List<ResearchProject>.of(_projects);
    candidate[index] = updated;
    await _writeSnapshot(candidate, _draftSequence);
    _projects
      ..clear()
      ..addAll(candidate);
    _storageWarning = null;
    notifyListeners();
    return updated;
  }

  Future<void> deleteLocalDraft(String id) async {
    final index = _projects.indexWhere((p) => p.id == id && !p.isSample);
    if (index < 0) {
      throw ArgumentError('Borrador local no encontrado.');
    }
    final candidate = List<ResearchProject>.of(_projects)..removeAt(index);
    await _writeSnapshot(candidate, _draftSequence);
    _projects
      ..clear()
      ..addAll(candidate);
    _storageWarning = null;
    notifyListeners();
  }

  Map<String, Object?> _backupRecord(ResearchProject p) => {
        'title': p.title,
        'thesis': p.thesis,
        'symbol': p.symbol,
        'side': p.side,
        'timeframe': p.timeframe,
        'created_at': p.createdAt.toUtc().toIso8601String(),
      };

  Map<String, Object?> _persistentRecord(ResearchProject p) => {
        'id': p.id,
        ..._backupRecord(p),
      };

  String exportDraftBackup() => const JsonEncoder.withIndent(' ').convert({
        'schema': backupSchema,
        'drafts': [
          for (final p in _projects)
            if (!p.isSample) _backupRecord(p),
        ],
      });

  Future<int> restoreDraftBackup(String source) async {
    if (source.length > maxBackupCharacters) {
      throw const FormatException('El respaldo supera el tamaño permitido.');
    }
    final Object? decoded;
    try {
      decoded = jsonDecode(source);
    } on FormatException {
      throw const FormatException('El respaldo no es JSON válido.');
    }
    if (decoded is! Map<String, dynamic> ||
        decoded.length != 2 ||
        decoded['schema'] != backupSchema ||
        decoded['drafts'] is! List) {
      throw const FormatException('Formato de respaldo no compatible.');
    }
    final rows = decoded['drafts'] as List;
    if (rows.length > maxDrafts) {
      throw const FormatException('El respaldo supera los 1000 borradores.');
    }
    final pending = <ResearchProject>[];
    final known = {
      for (final p in _projects)
        if (!p.isSample) jsonEncode(_backupRecord(p)),
    };
    for (final row in rows) {
      final parsed = _parseBackupRow(row);
      final candidate = ResearchProject(
        id:
            'LOCAL-${(_draftSequence + pending.length + 1).toString().padLeft(4, '0')}',
        title: parsed.title,
        thesis: parsed.thesis,
        symbol: parsed.symbol,
        side: parsed.side,
        timeframe: parsed.timeframe,
        state: 'LOCAL_DRAFT_NOT_FROZEN',
        isSample: false,
        createdAt: parsed.createdAt,
      );
      if (known.add(jsonEncode(_backupRecord(candidate)))) {
        pending.add(candidate);
      }
    }
    if (localDraftCount + pending.length > maxDrafts) {
      throw const FormatException('No hay espacio para más de 1000 borradores.');
    }
    if (pending.isEmpty) return 0;
    final sequence = _draftSequence + pending.length;
    final candidate = <ResearchProject>[...pending, ..._projects];
    await _writeSnapshot(candidate, sequence);
    _projects
      ..clear()
      ..addAll(candidate);
    _draftSequence = sequence;
    _storageWarning = null;
    notifyListeners();
    return pending.length;
  }

  _ParsedDraft _parseBackupRow(Object? row) {
    const keys = {
      'title',
      'thesis',
      'symbol',
      'side',
      'timeframe',
      'created_at',
    };
    if (row is! Map<String, dynamic> ||
        row.length != keys.length ||
        !row.keys.every(keys.contains) ||
        !row.values.every((v) => v is String)) {
      throw const FormatException(
          'Registro no compatible; no se admite autoridad científica.');
    }
    return _validateParsed(
      title: row['title'] as String,
      thesis: row['thesis'] as String,
      symbol: row['symbol'] as String,
      side: row['side'] as String,
      timeframe: row['timeframe'] as String,
      dateText: row['created_at'] as String,
    );
  }

  _ParsedDraft _validateParsed({
    required String title,
    required String thesis,
    required String symbol,
    required String side,
    required String timeframe,
    required String dateText,
  }) {
    final date = DateTime.tryParse(dateText);
    if (title.trim() != title ||
        title.length < 3 ||
        title.length > 72 ||
        thesis.trim() != thesis ||
        thesis.length < 10 ||
        thesis.length > 500 ||
        !symbols.contains(symbol) ||
        !sides.contains(side) ||
        !timeframes.contains(timeframe) ||
        date == null ||
        !dateText.endsWith('Z') ||
        date.toUtc().toIso8601String() != dateText) {
      throw const FormatException('El respaldo contiene un borrador inválido.');
    }
    return _ParsedDraft(title, thesis, symbol, side, timeframe, date);
  }

  _PersistentDrafts _decodePersistent(String source) {
    if (source.length > maxBackupCharacters) {
      throw const LocalPersistenceException('LOCAL_STORE_OVERSIZED');
    }
    final Object? decoded;
    try {
      decoded = jsonDecode(source);
    } catch (_) {
      throw const LocalPersistenceException('LOCAL_STORE_CORRUPT_JSON');
    }
    if (decoded is! Map<String, dynamic>) {
      throw const LocalPersistenceException('LOCAL_STORE_INVALID_ROOT');
    }
    final schema = decoded['schema'];
    if (schema == storageSchemaV1) {
      final rows = decoded['drafts'];
      if (decoded.length != 2 || rows is! List || rows.length > maxDrafts) {
        throw const LocalPersistenceException('LOCAL_STORE_V1_INVALID');
      }
      final drafts = <ResearchProject>[];
      var sequence = 0;
      try {
        for (final row in rows) {
          final parsed = _parseBackupRow(row);
          sequence++;
          drafts.add(ResearchProject(
            id: 'LOCAL-${sequence.toString().padLeft(4, '0')}',
            title: parsed.title,
            thesis: parsed.thesis,
            symbol: parsed.symbol,
            side: parsed.side,
            timeframe: parsed.timeframe,
            state: 'LOCAL_DRAFT_NOT_FROZEN',
            isSample: false,
            createdAt: parsed.createdAt,
          ));
        }
      } catch (_) {
        throw const LocalPersistenceException('LOCAL_STORE_V1_INVALID');
      }
      return _PersistentDrafts(drafts, sequence, true);
    }
    if (schema != storageSchemaV2 ||
        decoded.length != 3 ||
        decoded['draft_sequence'] is! int ||
        decoded['drafts'] is! List) {
      throw const LocalPersistenceException('LOCAL_STORE_SCHEMA_UNSUPPORTED');
    }
    final sequence = decoded['draft_sequence'] as int;
    final rows = decoded['drafts'] as List;
    if (sequence < 0 || rows.length > maxDrafts || sequence < rows.length) {
      throw const LocalPersistenceException('LOCAL_STORE_SEQUENCE_INVALID');
    }
    const keys = {
      'id',
      'title',
      'thesis',
      'symbol',
      'side',
      'timeframe',
      'created_at',
    };
    final drafts = <ResearchProject>[];
    final ids = <String>{};
    try {
      for (final row in rows) {
        if (row is! Map<String, dynamic> ||
            row.length != keys.length ||
            !row.keys.every(keys.contains) ||
            !row.values.every((v) => v is String)) {
          throw const FormatException();
        }
        final id = row['id'] as String;
        if (!RegExp(r'^LOCAL-[0-9]{4,}$').hasMatch(id) || !ids.add(id)) {
          throw const FormatException();
        }
        final parsed = _validateParsed(
          title: row['title'] as String,
          thesis: row['thesis'] as String,
          symbol: row['symbol'] as String,
          side: row['side'] as String,
          timeframe: row['timeframe'] as String,
          dateText: row['created_at'] as String,
        );
        drafts.add(ResearchProject(
          id: id,
          title: parsed.title,
          thesis: parsed.thesis,
          symbol: parsed.symbol,
          side: parsed.side,
          timeframe: parsed.timeframe,
          state: 'LOCAL_DRAFT_NOT_FROZEN',
          isSample: false,
          createdAt: parsed.createdAt,
        ));
      }
    } catch (_) {
      throw const LocalPersistenceException('LOCAL_STORE_RECORD_INVALID');
    }
    return _PersistentDrafts(drafts, sequence, false);
  }

  Future<void> _writeSnapshot(
      List<ResearchProject> candidate, int sequence) async {
    final json = jsonEncode({
      'schema': storageSchemaV2,
      'draft_sequence': sequence,
      'drafts': [
        for (final p in candidate)
          if (!p.isSample) _persistentRecord(p),
      ],
    });
    try {
      await _vault.write(storageKey, json);
    } catch (_) {
      _storageWarning = 'SECURE_STORAGE_WRITE_FAILED';
      throw const LocalPersistenceException('SECURE_STORAGE_WRITE_FAILED');
    }
  }

  Map<String, Object?> exportSyntheticEvidence() => {
        'schema': 'QROS_MOBILE_ANDROID_G11_TEST_ONLY_V1',
        'created_at_utc': _clock().toUtc().toIso8601String(),
        'classification': 'TEST_ONLY_SYNTHETIC_AND_LOCAL_DRAFTS',
        'is_authentic_research_attestation': false,
        'engine_connected': false,
        'real_trades': 0,
        'scientific_authority': 'NONE',
        'broker_data_included': false,
        'holdout_open': false,
        'ga2_open': false,
        'mt5_executed': false,
        'build_signature': null,
        'external_head_anchor': null,
        'local_persistence_initialized': _initialized,
        'local_persistence_warning': _storageWarning,
        'projects': [for (final item in _projects) item.toEvidenceRecord()],
      };
}

class _ParsedDraft {
  const _ParsedDraft(
      this.title, this.thesis, this.symbol, this.side, this.timeframe, this.createdAt);
  final String title;
  final String thesis;
  final String symbol;
  final String side;
  final String timeframe;
  final DateTime createdAt;
}

class _PersistentDrafts {
  const _PersistentDrafts(this.projects, this.sequence, this.migrated);
  final List<ResearchProject> projects;
  final int sequence;
  final bool migrated;
}
