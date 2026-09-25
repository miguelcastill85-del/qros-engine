import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/universe_ir.dart';
import 'package:qros_mobile_studio/core/universe_store.dart';

void main() {
  late Map<String, dynamic> oracle;
  setUpAll(() {
    oracle = jsonDecode(File('test/fixtures/universe_oracle.json').readAsStringSync())
        as Map<String, dynamic>;
  });

  UniverseBlueprint fixtureBlueprint() {
    final raw = oracle['raw_input'] as Map<String, dynamic>;
    return UniverseBlueprint(
      symbol: raw['symbol'] as String,
      sides: (raw['sides'] as List).cast<String>(),
      timeframes: (raw['timeframes'] as List).cast<String>(),
      lookbackBars: (raw['lookback_bars'] as List).cast<int>(),
      confirmationBars: (raw['confirmation_bars'] as List).cast<int>(),
      stopRatios: (raw['stop_ratios'] as List).cast<String>(),
      maximumHoldingBars: (raw['maximum_holding_bars'] as List).cast<int>(),
    );
  }

  test('independent Python/Dart canonical contract, SHA-256 and 144 toy enumerations agree', () async {
    final blueprint = fixtureBlueprint();
    final expected = oracle['oracle'] as Map<String, dynamic>;
    expect(blueprint.rawBirths, 144);
    expect(blueprint.canonicalJson(), expected['canonical_json']);
    expect(await blueprint.canonicalSha256(), expected['canonical_sha256']);
    expect(blueprint.enumerateToyIds().length, 144);
    expect(await blueprint.toyEnumerationSha256(), expected['toy_enumeration_sha256']);
    final c = await blueprint.contractPreview();
    expect(c['search_space_sha256'], expected['canonical_sha256']);
    expect(c['multiplicity_n_tests'], 0);
    expect(c['can_freeze'], false);
    expect(c['data_authority_id'], null);
  });

  test('canonicalization ignores order of domain input but never merges different grids', () async {
    final other = UniverseBlueprint(
      symbol: 'SIM_XAUUSD', sides: ['BUY', 'SELL'],
      timeframes: ['M5', 'M15'], lookbackBars: [5, 10, 15],
      confirmationBars: [1, 2], stopRatios: ['1/1', '2/1', '3/2'],
      maximumHoldingBars: [8, 12],
    );
    expect(await other.canonicalSha256(), await fixtureBlueprint().canonicalSha256());
    final reduced = UniverseBlueprint(symbol: 'SIM_XAUUSD', sides: ['BUY'],
      timeframes: ['M5','M15'], lookbackBars: [5,10,15],
      confirmationBars: [1,2], stopRatios: ['1/1','2/1','3/2'],maximumHoldingBars:[8,12]);
    expect(reduced.rawBirths, 72);
    expect(await reduced.canonicalSha256(), isNot(await other.canonicalSha256()));
  });

  test('rejects an empty domain or repeated values instead of inventing zero unique candidates', () {
    expect(() => UniverseBlueprint(symbol: 'SIM_XAUUSD', sides: [], timeframes: ['M5'],
      lookbackBars:[5], confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8]).validate(),
      throwsA(isA<UniverseValidationError>()));
    expect(() => UniverseBlueprint(symbol: 'SIM_XAUUSD', sides: ['BUY','BUY'],timeframes:['M5'],
      lookbackBars:[5],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8]).validate(),
      throwsA(isA<UniverseValidationError>()));
  });

  test('rejects future-bar observability, unknown broker instruments and unbounded grids', () {
    expect(() => UniverseBlueprint(symbol:'SIM_XAUUSD',sides:['BUY'],timeframes:['M5'],
      lookbackBars:[5],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8],
      observability:'BAR_ZERO_CURRENT').validate(),throwsA(isA<UniverseValidationError>()));
    expect(() => UniverseBlueprint(symbol:'XAUUSD_LIVE',sides:['BUY'],timeframes:['M5'],
      lookbackBars:[5],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8]).validate(),
      throwsA(isA<UniverseValidationError>()));
    expect(() => UniverseBlueprint(symbol:'SIM_XAUUSD',sides:['BUY'],timeframes:['M5'],
      lookbackBars:[999999999],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8]).validate(),
      throwsA(isA<UniverseValidationError>()));
  });

  test('execution invariants fail closed on overnight or more than three entries', () {
    expect(() => UniverseBlueprint(symbol:'SIM_XAUUSD',sides:['BUY'],timeframes:['M5'],
      lookbackBars:[5],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8],
      overnightAllowed:true).validate(),throwsA(isA<UniverseValidationError>()));
    expect(() => UniverseBlueprint(symbol:'SIM_XAUUSD',sides:['BUY'],timeframes:['M5'],
      lookbackBars:[5],confirmationBars:[1],stopRatios:['1/1'],maximumHoldingBars:[8],
      maxEntriesPerDay:5).validate(),throwsA(isA<UniverseValidationError>()));
  });

  test('in-memory store never issues a frozen scientific contract', () async {
    final store = UniverseSessionStore();
    final draft = await store.save(title:'Compresion M15',
      thesis:'Hipotesis sintetica de compresion antes de ruptura y confirmacion.',
      blueprint:fixtureBlueprint());
    expect(store.latest, same(draft));
    expect(draft.blueprint.canonicalObject()['holdout_open'], false);
    final preview=await draft.blueprint.contractPreview();
    expect(preview['frozen'], false);
    expect(preview['can_freeze'], false);
    expect(preview['program_sha256'], null);
    store.dispose();
  });
}
