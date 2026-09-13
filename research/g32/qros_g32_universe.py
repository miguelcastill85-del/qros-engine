#!/usr/bin/env python3
"""Deterministic G32 predevelopment-universe enumerator.

This program reads no market data and computes no economic result.  It builds
the finite QROS-owned configuration identities frozen in the G32 ontology,
using two enumeration algorithms that share only the canonical specification.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Iterator


SIGNAL_SCHEMA = "QROS_G32_SIGNAL_CONFIG_V1"
MANAGEMENT_SCHEMA = "QROS_G32_MANAGEMENT_PROFILE_V1"
EXECUTION_SCHEMA = "QROS_G32_EXECUTION_PROFILE_V1"
STRESS_SCHEMA = "QROS_G32_STRESS_PROFILE_V1"
ROOT_DOMAIN = b"QROS_G32_SORTED_ID_ROOT_V1\n"
SHARD_DOMAIN = b"QROS_G32_ID_SHARD_ROOT_V1\n"


def canonical_bytes(value: object) -> bytes:
    """Canonical UTF-8/NFC JSON used by every G32 identity."""
    normalized = unicodedata.normalize("NFC", json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ))
    return normalized.encode("utf-8")


def object_id(prefix: str, value: object) -> str:
    return prefix + hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_ontology(path: Path) -> dict:
    ontology = json.loads(path.read_text(encoding="utf-8"))
    if ontology.get("schema") != "QROS_G32_UNIVERSE_ONTOLOGY_V2":
        raise ValueError("unexpected ontology schema")
    return ontology


def valid_alpha_pairs(ontology: dict) -> list[tuple[int, int]]:
    axes = ontology["base_axes"]
    return [
        (fast, slow)
        for fast in axes["fast_limit_ppm"]
        for slow in axes["slow_limit_ppm"]
        if 0 < slow < fast <= 1_000_000
    ]


def _generic_parameter_product(parameters: dict) -> Iterator[dict]:
    keys = sorted(parameters)
    if not keys:
        yield {}
        return
    for values in itertools.product(*(parameters[k] for k in keys)):
        yield dict(zip(keys, values))


def family_variants_a(ontology: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for family_id, spec in ontology["family_variants"].items():
        if "variants" in spec:
            for params in spec["variants"]:
                out.append((family_id, dict(params)))
        else:
            for params in _generic_parameter_product(spec["parameters"]):
                out.append((family_id, params))
    return out


def _signal_config(
    asset: str,
    side: str,
    timeframe_seconds: int,
    feature_quote_side: str,
    price_transform: str,
    phase_estimator: str,
    fast_limit_ppm: int,
    slow_limit_ppm: int,
    gap_state_policy: str,
    family_id: str,
    family_parameters: dict,
) -> dict:
    return {
        "schema": SIGNAL_SCHEMA,
        "asset": asset,
        "side": side,
        "timeframe_seconds": timeframe_seconds,
        "feature_quote_side": feature_quote_side,
        "price_transform": price_transform,
        "phase_estimator": phase_estimator,
        "fast_limit_ppm": fast_limit_ppm,
        "slow_limit_ppm": slow_limit_ppm,
        "gap_state_policy": gap_state_policy,
        "family_id": family_id,
        "family_parameters": family_parameters,
    }


def enumerate_signal_a(ontology: dict) -> Iterator[tuple[str, str]]:
    """Enumerator A: direct Cartesian traversal and generic family expansion."""
    axes = ontology["base_axes"]
    base = itertools.product(
        axes["asset"],
        axes["side"],
        axes["timeframe_seconds"],
        axes["feature_quote_side"],
        axes["price_transform"],
        axes["phase_estimator"],
        valid_alpha_pairs(ontology),
        axes["gap_state_policy"],
    )
    variants = family_variants_a(ontology)
    for asset, side, tf, quote, transform, phase, pair, gap_policy in base:
        fast, slow = pair
        for family_id, params in variants:
            config = _signal_config(asset, side, tf, quote, transform, phase, fast, slow, gap_policy, family_id, params)
            yield object_id("g32s_", config), family_id


def family_variants_b(ontology: dict) -> list[tuple[str, dict]]:
    """Independent explicit expansion, deliberately not using product()."""
    specs = ontology["family_variants"]
    out: list[tuple[str, dict]] = [("F01_ROOT_FRESH_CROSS", {})]
    for k in specs["F02_ORDER_PERSISTENCE"]["parameters"]["additional_completed_bars"]:
        out.append(("F02_ORDER_PERSISTENCE", {"additional_completed_bars": k}))
    f3 = specs["F03_NORMALIZED_SEPARATION"]["parameters"]
    for atr in f3["atr_period"]:
        for threshold in f3["minimum_abs_separation_atr_ppm"]:
            out.append(("F03_NORMALIZED_SEPARATION", {
                "atr_period": atr,
                "minimum_abs_separation_atr_ppm": threshold,
            }))
    f4 = specs["F04_SLOPE_ALIGNMENT"]["parameters"]
    for target in f4["slope_target"]:
        for lag in f4["slope_lag_bars"]:
            out.append(("F04_SLOPE_ALIGNMENT", {"slope_lag_bars": lag, "slope_target": target}))
    for regime in specs["F05_ALPHA_REGIME"]["parameters"]["alpha_regime"]:
        out.append(("F05_ALPHA_REGIME", {"alpha_regime": regime}))
    f6 = specs["F06_VOLATILITY_CONTEXT"]["parameters"]
    for mode in f6["volatility_mode"]:
        for lookback in f6["context_lookback_bars"]:
            out.append(("F06_VOLATILITY_CONTEXT", {
                "context_lookback_bars": lookback,
                "volatility_mode": mode,
            }))
    f7 = specs["F07_SPREAD_CONTEXT"]["parameters"]
    for percentile in f7["max_prior_spread_percentile_ppm"]:
        for lookback in f7["context_lookback_bars"]:
            out.append(("F07_SPREAD_CONTEXT", {
                "context_lookback_bars": lookback,
                "max_prior_spread_percentile_ppm": percentile,
            }))
    f8 = specs["F08_TICK_INTENSITY_CONTEXT"]["parameters"]
    for percentile in f8["min_prior_intensity_percentile_ppm"]:
        for lookback in f8["context_lookback_bars"]:
            out.append(("F08_TICK_INTENSITY_CONTEXT", {
                "context_lookback_bars": lookback,
                "min_prior_intensity_percentile_ppm": percentile,
            }))
    for bars in specs["F09_REFRACTORY"]["parameters"]["refractory_completed_bars"]:
        out.append(("F09_REFRACTORY", {"refractory_completed_bars": bars}))
    return out


def _decode_mixed_radix(index: int, dimensions: list[list]) -> list:
    selected = []
    for values in reversed(dimensions):
        index, position = divmod(index, len(values))
        selected.append(values[position])
    if index:
        raise ValueError("mixed-radix overflow")
    return list(reversed(selected))


def enumerate_signal_b(ontology: dict) -> Iterator[tuple[str, str]]:
    """Enumerator B: family-major mixed-radix index decoding."""
    axes = ontology["base_axes"]
    pairs = []
    for slow in axes["slow_limit_ppm"]:
        for fast in axes["fast_limit_ppm"]:
            if slow > 0 and fast > slow and fast <= 1_000_000:
                pairs.append((fast, slow))
    dimensions = [
        list(reversed(axes["asset"])),
        list(reversed(axes["side"])),
        list(reversed(axes["timeframe_seconds"])),
        list(reversed(axes["feature_quote_side"])),
        list(reversed(axes["price_transform"])),
        list(reversed(axes["phase_estimator"])),
        list(reversed(pairs)),
        list(reversed(axes["gap_state_policy"])),
    ]
    base_count = math.prod(len(x) for x in dimensions)
    for family_id, params in reversed(family_variants_b(ontology)):
        for ordinal in range(base_count - 1, -1, -1):
            asset, side, tf, quote, transform, phase, pair, gap_policy = _decode_mixed_radix(ordinal, dimensions)
            fast, slow = pair
            config = _signal_config(asset, side, tf, quote, transform, phase, fast, slow, gap_policy, family_id, params)
            yield object_id("g32s_", config), family_id


def sorted_root(ids: Iterable[str]) -> str:
    h = hashlib.sha256(ROOT_DOMAIN)
    for identifier in sorted(ids):
        h.update(identifier.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def shard_manifest(ids: Iterable[str]) -> dict:
    shards: dict[str, list[str]] = defaultdict(list)
    for identifier in ids:
        digest = identifier.split("_", 1)[1]
        shards[digest[:2]].append(identifier)
    records = []
    for prefix in (f"{i:02x}" for i in range(256)):
        h = hashlib.sha256(SHARD_DOMAIN + prefix.encode("ascii") + b"\n")
        members = sorted(shards.get(prefix, []))
        for identifier in members:
            h.update(identifier.encode("ascii"))
            h.update(b"\n")
        records.append({"prefix": prefix, "count": len(members), "root_sha256": h.hexdigest()})
    return {
        "schema": "QROS_G32_SIGNAL_ID_SHARD_ROOTS_V1",
        "partition": "first_two_hex_characters_of_signal_config_digest",
        "shards": records,
    }


def enumerate_management(ontology: dict, reverse: bool = False) -> list[str]:
    profiles = ontology["management_overlay_universe"]["profiles"]
    configs = [{"schema": MANAGEMENT_SCHEMA, "family": "OPPOSITE_CROSS_OR_DAY_END", "parameters": {}}]
    atr = profiles["ATR_BRACKET"]
    for period in atr["atr_period"]:
        for stop in atr["stop_atr_ppm"]:
            for target in atr["target_r_ppm"]:
                configs.append({"schema": MANAGEMENT_SCHEMA, "family": "ATR_BRACKET", "parameters": {
                    "atr_period": period, "stop_atr_ppm": stop, "target_r_ppm": target,
                }})
    for target in profiles["SIGNAL_BAR_EXTREME_TARGET_R"]["target_r_ppm"]:
        configs.append({"schema": MANAGEMENT_SCHEMA, "family": "SIGNAL_BAR_EXTREME_TARGET_R", "parameters": {"target_r_ppm": target}})
    for bars in profiles["TIME_STOP_OR_OPPOSITE_CROSS"]["time_stop_bars"]:
        configs.append({"schema": MANAGEMENT_SCHEMA, "family": "TIME_STOP_OR_OPPOSITE_CROSS", "parameters": {"time_stop_bars": bars}})
    if reverse:
        configs = list(reversed(configs))
    return [object_id("g32m_", x) for x in configs]


def enumerate_execution(ontology: dict) -> list[str]:
    return [object_id("g32e_", {
        "schema": EXECUTION_SCHEMA,
        "profile": ontology["execution_profile_universe"]["profiles"][0],
    })]


def enumerate_stress(ontology: dict, reverse: bool = False) -> list[str]:
    spec = ontology["stress_profile_universe"]
    configs = []
    outer = spec["cost_regime"] if not reverse else list(reversed(spec["latency"]))
    inner = spec["latency"] if not reverse else list(reversed(spec["cost_regime"]))
    for a in outer:
        for b in inner:
            cost, latency = (a, b) if not reverse else (b, a)
            configs.append({"schema": STRESS_SCHEMA, "cost_regime": cost, "latency": latency})
    return [object_id("g32x_", x) for x in configs]


def build_receipts(ontology_path: Path) -> tuple[dict, dict, dict]:
    ontology = read_ontology(ontology_path)
    a_rows = list(enumerate_signal_a(ontology))
    b_rows = list(enumerate_signal_b(ontology))
    a_ids = {identifier for identifier, _ in a_rows}
    b_ids = {identifier for identifier, _ in b_rows}
    a_family = Counter(family for _, family in a_rows)
    b_family = Counter(family for _, family in b_rows)
    symmetric_difference = a_ids.symmetric_difference(b_ids)

    management_a = set(enumerate_management(ontology))
    management_b = set(enumerate_management(ontology, reverse=True))
    execution_ids = set(enumerate_execution(ontology))
    stress_a = set(enumerate_stress(ontology))
    stress_b = set(enumerate_stress(ontology, reverse=True))

    expected = ontology["finite_universe_cardinality"]
    if len(a_ids) != expected["logically_valid_signal_configs"]:
        raise AssertionError((len(a_ids), expected))
    if symmetric_difference:
        raise AssertionError(f"signal enumerator disagreement: {len(symmetric_difference)}")
    if a_family != b_family:
        raise AssertionError("family counts disagree")
    if management_a != management_b or len(management_a) != ontology["management_overlay_universe"]["expected_profiles"]:
        raise AssertionError("management enumeration disagreement")
    if stress_a != stress_b or len(stress_a) != ontology["stress_profile_universe"]["expected_profiles"]:
        raise AssertionError("stress enumeration disagreement")

    sorted_ids = sorted(a_ids)
    shards = shard_manifest(a_ids)
    shard_bytes = canonical_bytes(shards) + b"\n"
    enumeration = {
        "schema": "QROS_G32_EXACT_ENUMERATION_PARITY_RECEIPT_V1",
        "campaign": ontology["campaign"],
        "status": "PASS_NO_RESULTS",
        "ontology_sha256": hashlib.sha256(ontology_path.read_bytes()).hexdigest(),
        "enumerator_a": "CARTESIAN_BASE_GENERIC_SORTED_PARAMETER_EXPANSION",
        "enumerator_b": "FAMILY_MAJOR_EXPLICIT_EXPANSION_MIXED_RADIX_BASE_DECODER",
        "signal_universe": {
            "raw_count": len(a_rows),
            "valid_unique_count_a": len(a_ids),
            "valid_unique_count_b": len(b_ids),
            "symmetric_difference_count": len(symmetric_difference),
            "duplicate_config_id_count_a": len(a_rows) - len(a_ids),
            "duplicate_config_id_count_b": len(b_rows) - len(b_ids),
            "root_sha256_a": sorted_root(a_ids),
            "root_sha256_b": sorted_root(b_ids),
            "first_config_id": sorted_ids[0],
            "last_config_id": sorted_ids[-1],
            "family_counts": dict(sorted(a_family.items())),
        },
        "management_universe": {
            "count_a": len(management_a),
            "count_b": len(management_b),
            "symmetric_difference_count": len(management_a.symmetric_difference(management_b)),
            "root_sha256": sorted_root(management_a),
        },
        "execution_universe": {"count": len(execution_ids), "root_sha256": sorted_root(execution_ids)},
        "stress_universe": {
            "count_a": len(stress_a),
            "count_b": len(stress_b),
            "symmetric_difference_count": len(stress_a.symmetric_difference(stress_b)),
            "root_sha256": sorted_root(stress_a),
        },
        "signal_shard_manifest": {
            "path": "control/G32_SIGNAL_ID_SHARD_ROOTS_V1.json",
            "shards": 256,
            "sha256": hashlib.sha256(shard_bytes).hexdigest(),
        },
        "semantic_config_canonicalization": {
            "config_id_collisions": 0,
            "pre_result_economic_alias_claims": 0,
            "signal_mask_aliases": "PENDING_REAL_SIGNAL_MASK_PARITY_AND_MUST_BE_DEDUPED_BEFORE_N_TESTS",
        },
        "market_data_read": False,
        "pnl_read": False,
        "holdout_opened": False,
        "decision": "EXACT_CONFIG_SET_PARITY_PASS_SIGNAL_EXECUTION_NOT_YET_AUTHORIZED",
    }
    coverage = {
        "schema": "QROS_G32_PREDEVELOPMENT_UNIVERSE_COVERAGE_RECEIPT_V1",
        "campaign": ontology["campaign"],
        "status": "PASS_FOR_FROZEN_PREDEVELOPMENT_ONTOLOGY_SCOPE",
        "scope": ontology["causal_scope_contract"]["in_scope"],
        "eligible_family_count": len(a_family),
        "family_counts": dict(sorted(a_family.items())),
        "unexamined_family_count": 0,
        "closed_exclusions": [
            {"dimension": "NAMED_SESSION_AND_DAY_OF_WEEK", "code": "UNIT_OR_CLOCK_UNRESOLVED", "evidence": "control/G32_DATA_AUTHORITY_BINDING_V1.json"},
            {"dimension": "MULTI_FAMILY_STACKING", "code": "OUT_OF_SCOPE_FROZEN_REASON", "evidence": "max_interaction_depth=1"},
            {"dimension": "EXTERNAL_OR_CROSS_ASSET_FEATURES", "code": "OUT_OF_SCOPE_FROZEN_REASON", "evidence": "price-tick-only root"},
        ],
        "coverage_basis": "Every allowed mutation operator in the frozen causal scope projects onto an explicit base axis or exactly one of F01-F09.",
        "branch_exhausted": False,
        "market_data_read": False,
        "pnl_read": False,
        "holdout_opened": False,
    }
    return enumeration, shards, coverage


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    enumeration, shards, coverage = build_receipts(args.ontology)
    write_json(args.out_dir / "G32_EXACT_ENUMERATION_PARITY_RECEIPT_V1.json", enumeration)
    write_json(args.out_dir / "G32_SIGNAL_ID_SHARD_ROOTS_V1.json", shards)
    write_json(args.out_dir / "G32_PREDEVELOPMENT_UNIVERSE_COVERAGE_RECEIPT_V1.json", coverage)
    print(json.dumps(enumeration, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
