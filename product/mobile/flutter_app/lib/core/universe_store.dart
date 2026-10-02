import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'local_vault.dart';
import 'universe_ir.dart';

class UniverseSessionStore extends ChangeNotifier {
  UniverseSessionStore({LocalVault? vault})
      : _vault = vault ?? MemoryLocalVault();

  static const storageKey = 'qros.universe.latest.v1';
  static const storageSchema = 'QROS_LOCAL_UNIVERSE_STORE_V1';

  final LocalVault _vault;
  UniverseSessionDraft? _latest;
  String? _storageWarning;
  bool _initialized = false;

  UniverseSessionDraft? get latest => _latest;
  String? get storageWarning => _storageWarning;
  bool get initialized => _initialized;
  bool get persistentStorageHealthy => _initialized && _storageWarning == null;

  Future<void> initialize() async {
    if (_initialized) return;
    try {
      final raw = await _vault.read(storageKey);
      if (raw != null && raw.isNotEmpty) {
        _latest = await _decode(raw);
      }
      _storageWarning = null;
    } on LocalPersistenceException catch (e) {
      _storageWarning = e.code;
      _latest = null;
    } catch (_) {
      _storageWarning = 'UNIVERSE_SECURE_STORAGE_UNAVAILABLE';
      _latest = null;
    } finally {
      _initialized = true;
      notifyListeners();
    }
  }

  Future<UniverseSessionDraft> save({
    required String title,
    required String thesis,
    required UniverseBlueprint blueprint,
  }) async {
    final cleanTitle = title.trim();
    final cleanThesis = thesis.trim();
    if (cleanTitle.length < 3 || cleanTitle.length > 72) {
      throw const UniverseValidationError('TITLE_LENGTH');
    }
    if (cleanThesis.length < 10 || cleanThesis.length > 500) {
      throw const UniverseValidationError('THESIS_LENGTH');
    }
    blueprint.validate();
    final draft = UniverseSessionDraft(
      title: cleanTitle,
      thesis: cleanThesis,
      blueprint: blueprint,
      searchSpaceSha256: await blueprint.canonicalSha256(),
      toyEnumerationSha256: await blueprint.toyEnumerationSha256(),
    );
    final json = jsonEncode(_record(draft));
    try {
      await _vault.write(storageKey, json);
    } catch (_) {
      _storageWarning = 'UNIVERSE_SECURE_STORAGE_WRITE_FAILED';
      throw const LocalPersistenceException(
          'UNIVERSE_SECURE_STORAGE_WRITE_FAILED');
    }
    _latest = draft;
    _storageWarning = null;
    notifyListeners();
    return draft;
  }

  Future<void> clear() async {
    try {
      await _vault.delete(storageKey);
    } catch (_) {
      _storageWarning = 'UNIVERSE_SECURE_STORAGE_DELETE_FAILED';
      throw const LocalPersistenceException(
          'UNIVERSE_SECURE_STORAGE_DELETE_FAILED');
    }
    _latest = null;
    _storageWarning = null;
    notifyListeners();
  }

  Map<String, Object?> _record(UniverseSessionDraft draft) => {
        'schema': storageSchema,
        'title': draft.title,
        'thesis': draft.thesis,
        'blueprint': {
          'symbol': draft.blueprint.symbol,
          'sides': draft.blueprint.sides,
          'timeframes': draft.blueprint.timeframes,
          'lookback_bars': draft.blueprint.lookbackBars,
          'confirmation_bars': draft.blueprint.confirmationBars,
          'stop_ratios': draft.blueprint.stopRatios,
          'maximum_holding_bars': draft.blueprint.maximumHoldingBars,
          'observability': draft.blueprint.observability,
          'max_entries_per_day': draft.blueprint.maxEntriesPerDay,
          'overnight_allowed': draft.blueprint.overnightAllowed,
        },
        'search_space_sha256': draft.searchSpaceSha256,
        'toy_enumeration_sha256': draft.toyEnumerationSha256,
        'scientific_authority': false,
        'holdout_open': false,
      };

  Future<UniverseSessionDraft> _decode(String raw) async {
    final Object? decoded;
    try {
      decoded = jsonDecode(raw);
    } catch (_) {
      throw const LocalPersistenceException('UNIVERSE_STORE_CORRUPT_JSON');
    }
    if (decoded is! Map<String, dynamic> ||
        decoded.length != 8 ||
        decoded['schema'] != storageSchema ||
        decoded['title'] is! String ||
        decoded['thesis'] is! String ||
        decoded['blueprint'] is! Map<String, dynamic> ||
        decoded['search_space_sha256'] is! String ||
        decoded['toy_enumeration_sha256'] is! String ||
        decoded['scientific_authority'] != false ||
        decoded['holdout_open'] != false) {
      throw const LocalPersistenceException('UNIVERSE_STORE_INVALID_ROOT');
    }
    final b = decoded['blueprint'] as Map<String, dynamic>;
    const expected = {
      'symbol',
      'sides',
      'timeframes',
      'lookback_bars',
      'confirmation_bars',
      'stop_ratios',
      'maximum_holding_bars',
      'observability',
      'max_entries_per_day',
      'overnight_allowed',
    };
    if (b.length != expected.length || !b.keys.every(expected.contains)) {
      throw const LocalPersistenceException('UNIVERSE_STORE_INVALID_BLUEPRINT');
    }
    try {
      final blueprint = UniverseBlueprint(
        symbol: b['symbol'] as String,
        sides: List<String>.from(b['sides'] as List),
        timeframes: List<String>.from(b['timeframes'] as List),
        lookbackBars: List<int>.from(b['lookback_bars'] as List),
        confirmationBars: List<int>.from(b['confirmation_bars'] as List),
        stopRatios: List<String>.from(b['stop_ratios'] as List),
        maximumHoldingBars: List<int>.from(b['maximum_holding_bars'] as List),
        observability: b['observability'] as String,
        maxEntriesPerDay: b['max_entries_per_day'] as int,
        overnightAllowed: b['overnight_allowed'] as bool,
      );
      blueprint.validate();
      final title = decoded['title'] as String;
      final thesis = decoded['thesis'] as String;
      if (title.trim() != title ||
          title.length < 3 ||
          title.length > 72 ||
          thesis.trim() != thesis ||
          thesis.length < 10 ||
          thesis.length > 500) {
        throw const FormatException();
      }
      final search = await blueprint.canonicalSha256();
      final toy = await blueprint.toyEnumerationSha256();
      if (search != decoded['search_space_sha256'] ||
          toy != decoded['toy_enumeration_sha256']) {
        throw const LocalPersistenceException('UNIVERSE_STORE_HASH_MISMATCH');
      }
      return UniverseSessionDraft(
        title: title,
        thesis: thesis,
        blueprint: blueprint,
        searchSpaceSha256: search,
        toyEnumerationSha256: toy,
      );
    } on LocalPersistenceException {
      rethrow;
    } catch (_) {
      throw const LocalPersistenceException('UNIVERSE_STORE_INVALID_RECORD');
    }
  }
}
