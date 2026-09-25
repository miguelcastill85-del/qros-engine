import 'dart:convert';

import 'package:cryptography/cryptography.dart';

/// G1 is a bounded, syntactic TEST_ONLY search-space draft, not a strategy,
/// simulator, frozen scientific contract or permission to open a holdout.
class UniverseValidationError implements Exception {
  const UniverseValidationError(this.code);
  final String code;
  @override
  String toString() => 'QROS_UNIVERSE_REJECTED:$code';
}

class UniverseBlueprint {
  UniverseBlueprint({
    required this.symbol,
    required List<String> sides,
    required List<String> timeframes,
    required List<int> lookbackBars,
    required List<int> confirmationBars,
    required List<String> stopRatios,
    required List<int> maximumHoldingBars,
    this.observability = 'CLOSED_BAR_ONLY',
    this.maxEntriesPerDay = 3,
    this.overnightAllowed = false,
  })  : sides = List.unmodifiable(sides),
        timeframes = List.unmodifiable(timeframes),
        lookbackBars = List.unmodifiable(lookbackBars),
        confirmationBars = List.unmodifiable(confirmationBars),
        stopRatios = List.unmodifiable(stopRatios),
        maximumHoldingBars = List.unmodifiable(maximumHoldingBars);

  static const allowedSymbols = {'SIM_XAUUSD', 'SIM_NQX'};
  static const allowedSides = {'BUY', 'SELL'};
  static const allowedTimeframes = {'M5', 'M15'};
  static const allowedLookbacks = {5, 10, 15};
  static const allowedConfirmations = {1, 2};
  static const allowedStops = {'1/1', '3/2', '2/1'};
  static const allowedHoldingBars = {8, 12};
  static const maxAllowedBirths = 1000000;
  static const maxPreviewEnumeration = 10000;

  final String symbol;
  final List<String> sides;
  final List<String> timeframes;
  final List<int> lookbackBars;
  final List<int> confirmationBars;
  final List<String> stopRatios;
  final List<int> maximumHoldingBars;
  final String observability;
  final int maxEntriesPerDay;
  final bool overnightAllowed;

  factory UniverseBlueprint.sample() => UniverseBlueprint(
        symbol: 'SIM_XAUUSD',
        sides: ['BUY', 'SELL'],
        timeframes: ['M5', 'M15'],
        lookbackBars: [5, 10, 15],
        confirmationBars: [1, 2],
        stopRatios: ['1/1', '3/2', '2/1'],
        maximumHoldingBars: [8, 12],
      );

  void _checkAxis<T>(String name, List<T> selected, Set<T> allowed) {
    if (selected.isEmpty) throw UniverseValidationError('EMPTY_$name');
    if (selected.toSet().length != selected.length) {
      throw UniverseValidationError('DUPLICATE_$name');
    }
    if (selected.any((x) => !allowed.contains(x))) {
      throw UniverseValidationError('INVALID_$name');
    }
  }

  void validate() {
    if (!allowedSymbols.contains(symbol)) {
      throw const UniverseValidationError('SYMBOL_NOT_SYNTHETIC');
    }
    _checkAxis('SIDE', sides, allowedSides);
    _checkAxis('TIMEFRAME', timeframes, allowedTimeframes);
    _checkAxis('LOOKBACK', lookbackBars, allowedLookbacks);
    _checkAxis('CONFIRMATION', confirmationBars, allowedConfirmations);
    _checkAxis('STOP', stopRatios, allowedStops);
    _checkAxis('EXIT', maximumHoldingBars, allowedHoldingBars);
    if (observability != 'CLOSED_BAR_ONLY') {
      throw const UniverseValidationError('FUTURE_OR_UNFINALIZED_BAR');
    }
    if (maxEntriesPerDay != 3 || overnightAllowed) {
      throw const UniverseValidationError('EXECUTION_POLICY_DRIFT');
    }
    if (rawBirths > maxAllowedBirths) {
      throw const UniverseValidationError('BIRTH_BUDGET_EXCEEDED');
    }
  }

  int get rawBirths => sides.length * timeframes.length *
      lookbackBars.length * confirmationBars.length *
      stopRatios.length * maximumHoldingBars.length;

  static List<T> _ordered<T extends Comparable>(List<T> values) =>
      List<T>.of(values)..sort();

  Map<String, Object?> canonicalObject() {
    validate();
    return {
      'classification': 'SYNTHETIC_ONLY',
      'constraints': {
        'ambiguous_sl_tp': 'STOP_FIRST',
        'buy_entry': 'ASK',
        'buy_exit': 'BID',
        'gap_fill': 'FIRST_EXECUTABLE',
        'max_entries_per_day': maxEntriesPerDay,
        'overnight_allowed': overnightAllowed,
        'sell_entry': 'BID',
        'sell_exit': 'ASK',
      },
      'grammar': {
        'confirmation_bars': _ordered(confirmationBars),
        'lookback_bars': _ordered(lookbackBars),
        'maximum_holding_bars': _ordered(maximumHoldingBars),
        'stop_ratios': _ordered(stopRatios),
      },
      'holdout_open': false,
      'observability': observability,
      'raw_births': rawBirths,
      'schema': 'QROS_TYPED_UNIVERSE_DRAFT_V1',
      'scientific_authority': false,
      'sides': _ordered(sides),
      'status': 'LOCAL_DRAFT_NOT_FROZEN',
      'symbol': symbol,
      'timeframes': _ordered(timeframes),
    };
  }

  static Object? _sortTree(Object? value) {
    if (value is Map) {
      final keys = value.keys.map((key) => key.toString()).toList()..sort();
      return {for (final key in keys) key: _sortTree(value[key])};
    }
    if (value is List) return value.map(_sortTree).toList();
    return value;
  }

  String canonicalJson() => jsonEncode(_sortTree(canonicalObject()));

  Future<String> canonicalSha256() async {
    final digest = await Sha256().hash(utf8.encode(canonicalJson()));
    return _hex(digest.bytes);
  }

  static String _hex(List<int> bytes) =>
      bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();

  /// Limited toy enumeration for an independent, synthetic Python/Dart oracle.
  /// No market data, indicator calculations, trades or economic scoring occur.
  Iterable<String> enumerateToyIds() sync* {
    validate();
    if (rawBirths > maxPreviewEnumeration) {
      throw const UniverseValidationError('ENUMERATION_PREVIEW_BUDGET_EXCEEDED');
    }
    for (final side in _ordered(sides)) {
      for (final tf in _ordered(timeframes)) {
        for (final lb in _ordered(lookbackBars)) {
          for (final confirmation in _ordered(confirmationBars)) {
            for (final stop in _ordered(stopRatios)) {
              for (final exit in _ordered(maximumHoldingBars)) {
                yield '$symbol|$side|$tf|$lb|$confirmation|$stop|$exit';
              }
            }
          }
        }
      }
    }
  }

  Future<String> toyEnumerationSha256() async {
    final ids = enumerateToyIds().toList();
    if (ids.length != rawBirths || ids.toSet().length != ids.length) {
      throw const UniverseValidationError('TOY_CENSUS_INTEGRITY_FAILURE');
    }
    return _hex((await Sha256().hash(utf8.encode('${ids.join('\n')}\n'))).bytes);
  }

  /// Contract preview reuses exact existing C++ StrategyContract field names.
  /// NULLs mean authority and data identities have NOT been verified.
  Future<Map<String, Object?>> contractPreview() async => {
        'schema': 'QROS_STRATEGY_CONTRACT_PREVIEW_TEST_V1',
        'contract_id': null,
        'genealogy_root_id': null,
        'symbol': symbol,
        'side_policy': _ordered(sides).join(','),
        'program_sha256': null,
        'data_authority_id': null,
        'execution_policy_sha256': null,
        'cost_policy_sha256': null,
        'search_space_sha256': await canonicalSha256(),
        'multiplicity_n_tests': 0,
        'development_partition_id': null,
        'holdout_partition_id': null,
        'holdout_state': 'SEALED_NO_DATA',
        'frozen': false,
        'can_freeze': false,
        'user_thesis_attested': false,
      };
}

class UniverseSessionDraft {
  const UniverseSessionDraft({
    required this.title,
    required this.thesis,
    required this.blueprint,
    required this.searchSpaceSha256,
    required this.toyEnumerationSha256,
  });
  final String title;
  final String thesis;
  final UniverseBlueprint blueprint;
  final String searchSpaceSha256;
  final String toyEnumerationSha256;
}
