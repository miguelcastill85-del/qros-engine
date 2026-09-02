#!/usr/bin/env python3
"""QROS holdout genealogy preflight.

Fail-closed authorization check for any request to open/read a clean holdout.
This tool does not evaluate strategy economics. It validates only governance state.

Usage:
  python3 scripts/qros_holdout_genealogy_preflight.py --input packet.json --out receipt.json

The caller MUST require status=PASS and decision=HOLDOUT_OPEN_AUTHORIZED.
Anything else forbids economic holdout access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "QROS_HOLDOUT_GENEALOGY_PREFLIGHT_RECEIPT_1.0"
POLICY_REF = "governance/QROS_HOLDOUT_GENEALOGY_FIREWALL_v1.0.json"

REQUIRED_TRUE = (
    "root_genealogy_id_verified",
    "universe_ontology_frozen",
    "rise_fixed_point",
    "ontology_sufficiency_audit_receipt_pass",
    "predevelopment_universe_coverage_receipt_pass",
    "all_eligible_frontiers_development_complete_or_causally_excluded",
    "root_genealogy_pre_holdout_coverage_receipt_pass",
    "all_gate_a_selection_complete",
    "all_similarity_clustering_complete",
    "final_genealogy_candidate_cohort_frozen",
    "buy_sell_separation_verified",
    "execution_semantics_frozen",
    "independent_parity_pass",
    "cost_model_frozen",
    "clean_holdout_window_verified_unexposed_for_entire_genealogy",
    "holdout_acceptance_gate_frozen_before_economic_read",
)

REQUIRED_FALSE = (
    "any_open_eligible_frontier",
    "holdout_window_already_economically_exposed_for_genealogy",
)


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(packet: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    evidence: list[str] = []

    if packet.get("request") != "OPEN_CLEAN_HOLDOUT":
        failures.append("REQUEST_NOT_OPEN_CLEAN_HOLDOUT")

    root_id = packet.get("root_genealogy_id")
    campaign_id = packet.get("campaign_id")
    if not isinstance(root_id, str) or not root_id.strip():
        failures.append("ROOT_GENEALOGY_ID_MISSING")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        failures.append("CAMPAIGN_ID_MISSING")

    scope = packet.get("coverage_receipt_scope")
    if scope != "ROOT_GENEALOGY_COMPLETE":
        failures.append("COVERAGE_SCOPE_NOT_ROOT_GENEALOGY_COMPLETE")

    state = packet.get("state")
    if not isinstance(state, dict):
        failures.append("STATE_OBJECT_MISSING")
        state = {}

    for key in REQUIRED_TRUE:
        value = state.get(key)
        if value is not True:
            failures.append(f"REQUIRED_TRUE_FAILED:{key}")
        else:
            evidence.append(key)

    for key in REQUIRED_FALSE:
        value = state.get(key)
        if value is not False:
            failures.append(f"REQUIRED_FALSE_FAILED:{key}")
        else:
            evidence.append(key)

    refs = packet.get("authority_refs")
    if not isinstance(refs, dict) or not refs:
        failures.append("AUTHORITY_REFS_MISSING")
    else:
        required_refs = (
            "ontology_ref",
            "rise_ref",
            "ontology_sufficiency_receipt_ref",
            "predevelopment_coverage_receipt_ref",
            "root_pre_holdout_coverage_receipt_ref",
            "final_candidate_cohort_ref",
            "execution_parity_ref",
            "holdout_gate_ref",
            "exposure_ledger_ref",
        )
        for key in required_refs:
            val = refs.get(key)
            if not isinstance(val, str) or not val.strip():
                failures.append(f"AUTHORITY_REF_MISSING:{key}")

    frontier = packet.get("requesting_frontier")
    if frontier and state.get("all_eligible_frontiers_development_complete_or_causally_excluded") is not True:
        failures.append("FRONTIER_CANNOT_SELF_AUTHORIZE_HOLDOUT")

    return sorted(set(failures)), sorted(set(evidence))


def build_receipt(packet: dict[str, Any]) -> dict[str, Any]:
    input_sha = sha256_hex(canonical_bytes(packet))
    failures, evidence = validate(packet)
    passed = not failures
    return {
        "schema": SCHEMA,
        "policy_ref": POLICY_REF,
        "input_sha256": input_sha,
        "root_genealogy_id": packet.get("root_genealogy_id"),
        "campaign_id": packet.get("campaign_id"),
        "requesting_frontier": packet.get("requesting_frontier"),
        "coverage_receipt_scope": packet.get("coverage_receipt_scope"),
        "status": "PASS" if passed else "FAIL",
        "decision": "HOLDOUT_OPEN_AUTHORIZED" if passed else "HOLDOUT_OPEN_FORBIDDEN",
        "fail_closed": True,
        "verified_conditions": evidence,
        "failures": failures,
        "economic_read_authorized": passed,
        "irreversible_warning": "HOLDOUT ABIERTO — ESTE PERIODO YA NO ES DESCONOCIDO PARA TODA LA GENEALOGIA" if passed else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    packet_path = Path(args.input)
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        receipt = {
            "schema": SCHEMA,
            "policy_ref": POLICY_REF,
            "status": "FAIL",
            "decision": "HOLDOUT_OPEN_FORBIDDEN",
            "fail_closed": True,
            "economic_read_authorized": False,
            "failures": [f"INPUT_READ_OR_JSON_ERROR:{type(exc).__name__}"],
        }
        text = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        print(text, end="")
        return 2

    if not isinstance(packet, dict):
        packet = {"_invalid_root": packet}

    receipt = build_receipt(packet)
    text = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
