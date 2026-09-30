import 'dart:collection';
import 'dart:convert';
import 'package:flutter/foundation.dart';

/// In-memory fixture store. No networking, broker connection or research authority.
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

  /// The sample state is illustrative, never a scientific state transition.
  String get readableState =>
      isSample ? 'PREREGISTRADO · SIMULADO' : 'BORRADOR LOCAL';

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

/// Only UI drafts are allowed. The caller cannot request an approved scientific state.
class ResearchStore extends ChangeNotifier {
  ResearchStore({DateTime Function()? clock}) : _clock = clock ?? DateTime.now {
    _projects.add(
      ResearchProject(
        id: 'DEMO-001',
        title: 'Ruptura y recuperación',
        thesis: 'Hipótesis ilustrativa de recuperación de nivel. Sin operaciones ni PnL.',
        symbol: 'XAUUSD',
        side: 'BUY',
        timeframe: 'M15',
        state: 'SIMULATED_SAMPLE',
        isSample: true,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
    );
  }

  static const symbols = ['XAUUSD', 'NQX'];
  static const sides = ['BUY', 'SELL'];
  static const timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4'];

  final DateTime Function() _clock;
  final List<ResearchProject> _projects = [];
  int _draftSequence = 0;

  UnmodifiableListView<ResearchProject> get projects =>
      UnmodifiableListView(_projects);
  int get localDraftCount => _draftSequence;
  int get actualBacktests => 0;
  bool get engineConnected => false;

  ResearchProject createLocalDraft({
    required String title,
    required String thesis,
    required String symbol,
    required String side,
    required String timeframe,
  }) {
    final cleanedTitle = title.trim();
    final cleanedThesis = thesis.trim();
    if (cleanedTitle.length < 3 || cleanedTitle.length > 72) {
      throw ArgumentError('El título debe tener entre 3 y 72 caracteres.');
    }
    if (cleanedThesis.length < 10 || cleanedThesis.length > 500) {
      throw ArgumentError('La hipótesis debe tener entre 10 y 500 caracteres.');
    }
    if (!symbols.contains(symbol) ||
        !sides.contains(side) ||
        !timeframes.contains(timeframe)) {
      throw ArgumentError('Activo, dirección o timeframe no permitido.');
    }
    if (localDraftCount >= maxDrafts) {
      throw StateError('Límite de 1000 borradores alcanzado.');
    }
    _draftSequence++;
    final project = ResearchProject(
      id: 'LOCAL-${_draftSequence.toString().padLeft(4, '0')}',
      title: cleanedTitle,
      thesis: cleanedThesis,
      symbol: symbol,
      side: side,
      timeframe: timeframe,
      state: 'LOCAL_DRAFT_NOT_FROZEN',
      isSample: false,
      createdAt: _clock(),
    );
    _projects.insert(0, project);
    notifyListeners();
    return project;
  }


  static const backupSchema = 'QROS_LOCAL_DRAFT_BACKUP_V1';
  static const maxDrafts = 1000;
  static const maxBackupCharacters = 2000000;

  Map<String, Object?> _draftRecord(ResearchProject p) => {
    'title': p.title, 'thesis': p.thesis, 'symbol': p.symbol,
    'side': p.side, 'timeframe': p.timeframe,
    'created_at': p.createdAt.toUtc().toIso8601String(),
  };

  /// Portable user drafts only: never signed evidence, credentials or authority.
  String exportDraftBackup() => const JsonEncoder.withIndent('  ').convert({
    'schema': backupSchema,
    'drafts': [for (final p in _projects) if (!p.isSample) _draftRecord(p)],
  });

  /// Validate the entire document before mutating. Duplicate imports are no-ops.
  int restoreDraftBackup(String source) {
    if (source.length > maxBackupCharacters) {
      throw const FormatException('El respaldo supera el tamaño permitido.');
    }
    final Object? decoded;
    try { decoded = jsonDecode(source); }
    on FormatException { throw const FormatException('El respaldo no es JSON válido.'); }
    if (decoded is! Map<String, dynamic> ||
        decoded.length != 2 || decoded['schema'] != backupSchema ||
        decoded['drafts'] is! List) {
      throw const FormatException('Formato de respaldo no compatible.');
    }
    final rows = decoded['drafts'] as List;
    if (rows.length > maxDrafts) {
      throw const FormatException('El respaldo supera los 1000 borradores.');
    }
    const keys = {'title', 'thesis', 'symbol', 'side', 'timeframe', 'created_at'};
    final pending = <ResearchProject>[];
    final known = {for (final p in _projects) if (!p.isSample) jsonEncode(_draftRecord(p))};
    for (final row in rows) {
      if (row is! Map<String, dynamic> || row.length != keys.length ||
          !row.keys.every(keys.contains) || !row.values.every((v) => v is String)) {
        throw const FormatException('Registro no compatible; no se admite autoridad científica.');
      }
      final title = row['title'] as String;
      final thesis = row['thesis'] as String;
      final dateText = row['created_at'] as String;
      final date = DateTime.tryParse(dateText);
      if (title.trim() != title || title.length < 3 || title.length > 72 ||
          thesis.trim() != thesis || thesis.length < 10 || thesis.length > 500 ||
          !symbols.contains(row['symbol']) || !sides.contains(row['side']) ||
          !timeframes.contains(row['timeframe']) || date == null ||
          !dateText.endsWith('Z') || date.toUtc().toIso8601String() != dateText) {
        throw const FormatException('El respaldo contiene un borrador inválido.');
      }
      final candidate = ResearchProject(
        id: 'LOCAL-${(_draftSequence + pending.length + 1).toString().padLeft(4, '0')}',
        title: title, thesis: thesis, symbol: row['symbol'] as String,
        side: row['side'] as String, timeframe: row['timeframe'] as String,
        state: 'LOCAL_DRAFT_NOT_FROZEN', isSample: false, createdAt: date,
      );
      if (known.add(jsonEncode(_draftRecord(candidate)))) pending.add(candidate);
    }
    if (localDraftCount + pending.length > maxDrafts) {
      throw const FormatException('No hay espacio para más de 1000 borradores.');
    }
    if (pending.isNotEmpty) {
      _projects.insertAll(0, pending);
      _draftSequence += pending.length;
      notifyListeners();
    }
    return pending.length;
  }

  Map<String, Object?> exportSyntheticEvidence() => {
    'schema': 'QROS_MOBILE_ANDROID_M0_TEST_ONLY_V1',
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
    'projects': [for (final item in _projects) item.toEvidenceRecord()],
  };
}
