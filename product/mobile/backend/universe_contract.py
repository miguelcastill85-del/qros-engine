"""Independent G1 Python typed-universe oracle. SYNTHETIC_ONLY; no PnL."""
from __future__ import annotations
import hashlib
import itertools
import json
from typing import Any

ALLOWED = {
    'symbol': ('SIM_NQX', 'SIM_XAUUSD'),
    'sides': ('BUY', 'SELL'),
    'timeframes': ('M5', 'M15'),
    'lookback_bars': (5, 10, 15),
    'confirmation_bars': (1, 2),
    'stop_ratios': ('1/1', '2/1', '3/2'),
    'maximum_holding_bars': (8, 12),
}

class UniverseReject(ValueError):
    pass


def _axis(name: str, values: Any) -> list:
    if not isinstance(values, list) or not values:
        raise UniverseReject('EMPTY_' + name.upper())
    # No coercion: bool is a subclass of int and must be rejected.
    for v in values:
        if type(v) not in (int, str) or v not in ALLOWED[name]:
            raise UniverseReject('INVALID_' + name.upper())
    if len(values) != len(set(values)):
        raise UniverseReject('DUPLICATE_' + name.upper())
    return sorted(values)


def make_blueprint(raw: dict[str, Any]) -> dict[str, Any]:
    expected = {'symbol', 'sides', 'timeframes', 'lookback_bars',
                'confirmation_bars', 'stop_ratios', 'maximum_holding_bars',
                'observability', 'max_entries_per_day', 'overnight_allowed'}
    if type(raw) is not dict or set(raw) != expected:
        raise UniverseReject('BLUEPRINT_SCHEMA')
    symbol = raw['symbol']
    if type(symbol) is not str or symbol not in ALLOWED['symbol']:
        raise UniverseReject('SYMBOL_NOT_SYNTHETIC')
    sides = _axis('sides', raw['sides'])
    tfs = _axis('timeframes', raw['timeframes'])
    lb = _axis('lookback_bars', raw['lookback_bars'])
    conf = _axis('confirmation_bars', raw['confirmation_bars'])
    stops = _axis('stop_ratios', raw['stop_ratios'])
    holding = _axis('maximum_holding_bars', raw['maximum_holding_bars'])
    if raw['observability'] != 'CLOSED_BAR_ONLY':
        raise UniverseReject('FUTURE_OR_UNFINALIZED_BAR')
    if type(raw['max_entries_per_day']) is not int or raw['max_entries_per_day'] != 3 or raw['overnight_allowed'] is not False:
        raise UniverseReject('EXECUTION_POLICY_DRIFT')
    n = len(sides)*len(tfs)*len(lb)*len(conf)*len(stops)*len(holding)
    if n > 1000000:
        raise UniverseReject('BIRTH_BUDGET_EXCEEDED')
    return {
        'classification': 'SYNTHETIC_ONLY',
        'constraints': {
            'ambiguous_sl_tp': 'STOP_FIRST', 'buy_entry': 'ASK',
            'buy_exit': 'BID', 'gap_fill': 'FIRST_EXECUTABLE',
            'max_entries_per_day': 3, 'overnight_allowed': False,
            'sell_entry': 'BID', 'sell_exit': 'ASK',
        },
        'grammar': {
            'confirmation_bars': conf, 'lookback_bars': lb,
            'maximum_holding_bars': holding, 'stop_ratios': stops,
        },
        'holdout_open': False, 'observability': 'CLOSED_BAR_ONLY',
        'raw_births': n, 'schema': 'QROS_TYPED_UNIVERSE_DRAFT_V1',
        'scientific_authority': False, 'sides': sides,
        'status': 'LOCAL_DRAFT_NOT_FROZEN', 'symbol': symbol, 'timeframes': tfs,
    }


def canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def enumerate_toy_ids(obj: dict[str, Any]) -> list[str]:
    if obj['raw_births'] > 10000:
        raise UniverseReject('ENUMERATION_PREVIEW_BUDGET_EXCEEDED')
    g = obj['grammar']
    ids = [f"{obj['symbol']}|{side}|{tf}|{lb}|{conf}|{stop}|{exit_}"
           for side, tf, lb, conf, stop, exit_ in itertools.product(
               obj['sides'], obj['timeframes'], g['lookback_bars'],
               g['confirmation_bars'], g['stop_ratios'],
               g['maximum_holding_bars'])]
    if len(ids) != obj['raw_births'] or len(ids) != len(set(ids)):
        raise UniverseReject('TOY_CENSUS_INTEGRITY_FAILURE')
    return ids


def derive_oracle(raw: dict[str, Any]) -> dict[str, Any]:
    obj = make_blueprint(raw)
    ids = enumerate_toy_ids(obj)
    return {
        'canonical_json': canonical_json(obj),
        'canonical_sha256': sha256(canonical_json(obj)),
        'toy_enumeration_sha256': sha256('\n'.join(ids)+'\n'),
        'raw_births': obj['raw_births'],
    }
