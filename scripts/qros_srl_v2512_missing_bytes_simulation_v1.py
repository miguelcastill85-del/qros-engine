#!/usr/bin/env python3
"""Reproduce the v2512 failure mode: durable hash/report survives, generator bytes do not.
The expected result is FAIL_CLOSED, never reconstructability PASS.
"""
from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qros_strategy_reconstruction_adversarial_v1 import make_fixture, _seal_registry
from qros_strategy_reconstruction_core_v1 import SRLError, canonical_json, certify_reconstruction

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="qros_srl_v2512_") as temp:
        capsule, registry, providers = make_fixture(Path(temp))
        capsule = copy.deepcopy(capsule)
        capsule["strategy_id"] = "XAU_BUY_MULTIWEEK_PULLBACK_v2512_SIMULATION"
        capsule["scientific_state"] = "OBSERVATIONAL_RESERVE"

        # Simulate exactly the historical pathology: the capsule still knows the
        # generator/content identity, but every locator for that indispensable
        # generator has disappeared.
        primary_id = capsule["artifacts"]["primary"]["artifact_id"]
        registry = copy.deepcopy(registry)
        registry["mappings"][primary_id]["locators"] = [
            {"provider": "A", "failure_domain": "fdA", "path": "missing-generator.bin"}
        ]
        _seal_registry(registry)

        try:
            certify_reconstruction(capsule, registry, providers, NOW, 24)
        except SRLError as exc:
            if str(exc) != "FETCH_OR_HASH_VERIFY_FAILED":
                print(canonical_json({"status": "FAIL", "error": str(exc)}))
                return 2
            print(canonical_json({
                "status": "PASS",
                "schema": "QROS_SRL_V2512_MISSING_BYTES_SIMULATION_RECEIPT_1.0",
                "scientific_state_preserved": "OBSERVATIONAL_RESERVE",
                "generator_hash_identity_preserved": True,
                "generator_bytes_available": False,
                "reconstruction_certification": "FAIL_CLOSED",
                "expected_error": "FETCH_OR_HASH_VERIFY_FAILED",
                "main_merge_authorized": False
            }))
            return 0

        print(canonical_json({"status": "FAIL", "error": "MISSING_GENERATOR_FALSE_PASS"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
