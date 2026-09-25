import 'dart:collection';
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
