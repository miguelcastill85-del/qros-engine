#!/usr/bin/env python3
"""Fail-closed dimensional/unit preflight before QROS economic scoring.

This validator reads no PnL. It verifies that frozen ATR-fixed management
semantics are dimensionally equivalent to both primary and independent runner
bindings, and optionally verifies the exact SHA-256 of authority files in a
repository checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "QROS_EXECUTION_UNIT_BINDING_PREFLIGHT_RECEIPT_1.0"
POLICY_REF = "governance/QROS_EXECUTION_UNIT_BINDING_FIREWALL_v1.0.json"
REQUEST = "AUTHORIZE_ECONOMIC_SCORING_UNIT_BINDING"
PASS_DECISION = "ECONOMIC_SCORING_UNIT_BINDING_AUTHORIZED"
FAIL_DECISION = "ECONOMIC_SCORING_FORBIDDEN"
TOL = 1e-12

REQUIRED_AUTHORITY_KEYS = (
    "prereg_ref",
    "unit_contract_ref",
    "primary_runner_ref",
    "independent_runner_ref",
)


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_repo_path(repo_root: Path, relative: str) -> Path | None:
    try:
        root = repo_root.resolve(strict=True)
        candidate = (root / relative).resolve(strict=False)
        candidate.relative_to(root)
        return candidate
    except (OSError, ValueError):
        return None


def positive_number(obj: dict[str, Any], key: str, failures: list[str], scope: str) -> float | None:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
        failures.append(f"INVALID_POSITIVE_NUMBER:{scope}.{key}")
        return None
    return float(value)


def validate_runner(
    name: str,
    runner: dict[str, Any],
    atr_storage_scale: float,
    execution_scale: float,
    frozen_stop_mult: float,
    frozen_reward_r: float,
    raw_atr: float,
    failures: list[str],
    evidence: list[str],
) -> dict[str, float] | None:
    m = positive_number(runner, "atr_multiplier", failures, name)
    divisor = positive_number(runner, "atr_divisor", failures, name)
    take_r = positive_number(runner, "take_r_multiple", failures, name)
    if None in (m, divisor, take_r):
        return None

    effective = m * atr_storage_scale / (divisor * execution_scale)
    expected_stop = frozen_stop_mult * raw_atr * execution_scale
    runner_stop = m * (raw_atr * atr_storage_scale) / divisor
    expected_take = frozen_reward_r * expected_stop
    runner_take = take_r * runner_stop

    if not math.isclose(effective, frozen_stop_mult, rel_tol=TOL, abs_tol=TOL):
        failures.append(f"EFFECTIVE_STOP_MULT_MISMATCH:{name}")
    else:
        evidence.append(f"effective_stop_mult:{name}")

    if not math.isclose(take_r, frozen_reward_r, rel_tol=TOL, abs_tol=TOL):
        failures.append(f"REWARD_R_MISMATCH:{name}")
    else:
        evidence.append(f"reward_r:{name}")

    if not math.isclose(runner_stop, expected_stop, rel_tol=TOL, abs_tol=TOL):
        failures.append(f"SYNTHETIC_STOP_DIMENSIONAL_INVARIANT_FAIL:{name}")
    else:
        evidence.append(f"synthetic_stop:{name}")

    if not math.isclose(runner_take, expected_take, rel_tol=TOL, abs_tol=TOL):
        failures.append(f"SYNTHETIC_TAKE_DIMENSIONAL_INVARIANT_FAIL:{name}")
    else:
        evidence.append(f"synthetic_take:{name}")

    return {
        "effective_atr_stop_mult": effective,
        "synthetic_stop_execution_units": runner_stop,
        "synthetic_take_execution_units": runner_take,
    }


def validate(packet: dict[str, Any], repo_root: Path | None = None) -> tuple[list[str], list[str], dict[str, Any]]:
    failures: list[str] = []
    evidence: list[str] = []
    derived: dict[str, Any] = {}

    if packet.get("request") != REQUEST:
        failures.append("REQUEST_MISMATCH")

    for key in ("campaign_id", "root_genealogy_id"):
        value = packet.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"MISSING_ID:{key}")

    frozen = packet.get("frozen_semantics")
    units = packet.get("unit_contract")
    runners = packet.get("runner_bindings")
    if not isinstance(frozen, dict):
        failures.append("FROZEN_SEMANTICS_MISSING")
        frozen = {}
    if not isinstance(units, dict):
        failures.append("UNIT_CONTRACT_MISSING")
        units = {}
    if not isinstance(runners, dict):
        failures.append("RUNNER_BINDINGS_MISSING")
        runners = {}

    if frozen.get("stop_family") != "ATR_FIXED":
        failures.append("UNSUPPORTED_OR_UNBOUND_STOP_FAMILY")

    frozen_stop_mult = positive_number(frozen, "atr_stop_mult", failures, "frozen_semantics")
    frozen_reward_r = positive_number(frozen, "reward_r_multiple", failures, "frozen_semantics")
    atr_storage_scale = positive_number(units, "atr_storage_units_per_raw_quote_unit", failures, "unit_contract")
    execution_scale = positive_number(units, "execution_price_units_per_raw_quote_unit", failures, "unit_contract")

    raw_atr_obj = packet.get("synthetic_raw_atr_quote_units", 100.0)
    if isinstance(raw_atr_obj, bool) or not isinstance(raw_atr_obj, (int, float)) or not math.isfinite(float(raw_atr_obj)) or float(raw_atr_obj) <= 0:
        failures.append("INVALID_SYNTHETIC_RAW_ATR")
        raw_atr = 100.0
    else:
        raw_atr = float(raw_atr_obj)

    runner_results: dict[str, Any] = {}
    if None not in (frozen_stop_mult, frozen_reward_r, atr_storage_scale, execution_scale):
        for name in ("primary", "independent"):
            runner = runners.get(name)
            if not isinstance(runner, dict):
                failures.append(f"RUNNER_BINDING_MISSING:{name}")
                continue
            result = validate_runner(
                name,
                runner,
                atr_storage_scale,
                execution_scale,
                frozen_stop_mult,
                frozen_reward_r,
                raw_atr,
                failures,
                evidence,
            )
            if result is not None:
                runner_results[name] = result

        if "primary" in runner_results and "independent" in runner_results:
            for key in ("effective_atr_stop_mult", "synthetic_stop_execution_units", "synthetic_take_execution_units"):
                if not math.isclose(runner_results["primary"][key], runner_results["independent"][key], rel_tol=TOL, abs_tol=TOL):
                    failures.append(f"PRIMARY_INDEPENDENT_UNIT_SEMANTICS_MISMATCH:{key}")
                else:
                    evidence.append(f"primary_independent:{key}")

        derived = {
            "synthetic_raw_atr_quote_units": raw_atr,
            "expected_atr_stop_mult": frozen_stop_mult,
            "expected_reward_r_multiple": frozen_reward_r,
            "expected_stop_execution_units": frozen_stop_mult * raw_atr * execution_scale,
            "expected_take_execution_units": frozen_reward_r * frozen_stop_mult * raw_atr * execution_scale,
            "runner_results": runner_results,
        }

    refs = packet.get("authority_refs")
    hashes = packet.get("authority_sha256")
    if not isinstance(refs, dict):
        failures.append("AUTHORITY_REFS_MISSING")
        refs = {}
    if not isinstance(hashes, dict):
        failures.append("AUTHORITY_SHA256_MAP_MISSING")
        hashes = {}

    for key in REQUIRED_AUTHORITY_KEYS:
        ref = refs.get(key)
        expected = hashes.get(key)
        if not isinstance(ref, str) or not ref.strip():
            failures.append(f"AUTHORITY_REF_MISSING:{key}")
            continue
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
            failures.append(f"AUTHORITY_SHA256_INVALID:{key}")
            continue
        if repo_root is not None:
            path = safe_repo_path(repo_root, ref)
            if path is None:
                failures.append(f"AUTHORITY_PATH_INVALID:{key}")
            elif not path.is_file():
                failures.append(f"AUTHORITY_FILE_NOT_FOUND:{key}")
            else:
                actual = file_sha256(path)
                if actual.lower() != expected.lower():
                    failures.append(f"AUTHORITY_SHA256_MISMATCH:{key}")
                else:
                    evidence.append(f"authority_sha256:{key}")

    return sorted(set(failures)), sorted(set(evidence)), derived


def build_receipt(packet: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    failures, evidence, derived = validate(packet, repo_root=repo_root)
    passed = not failures
    return {
        "schema": SCHEMA,
        "policy_ref": POLICY_REF,
        "input_sha256": sha256_hex(canonical_bytes(packet)),
        "campaign_id": packet.get("campaign_id"),
        "root_genealogy_id": packet.get("root_genealogy_id"),
        "status": "PASS" if passed else "FAIL",
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "fail_closed": True,
        "economic_scoring_unit_binding_authorized": passed,
        "verified_conditions": evidence,
        "derived": derived,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    try:
        packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("root JSON must be an object")
    except Exception as exc:
        receipt = {
            "schema": SCHEMA,
            "policy_ref": POLICY_REF,
            "status": "FAIL",
            "decision": FAIL_DECISION,
            "fail_closed": True,
            "economic_scoring_unit_binding_authorized": False,
            "failures": [f"INPUT_READ_OR_JSON_ERROR:{type(exc).__name__}"],
        }
        text = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        print(text, end="")
        return 2

    receipt = build_receipt(packet, repo_root=Path(args.repo_root))
    text = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
