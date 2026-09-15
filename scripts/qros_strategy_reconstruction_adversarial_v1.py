#!/usr/bin/env python3
"""Adversarial verification for QROS Strategy Reconstruction Layer v1.3.

No economic PnL is read. All fixtures are synthetic and generated in a
zero-cache temporary workspace.
"""
from __future__ import annotations

import copy
import csv
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qros_strategy_reconstruction_core_v1 import (
    SRLError,
    canonical_json,
    certify_reconstruction,
    clean_room_reconstruct,
    content_root,
    retention_delete_allowed,
    semantic_fingerprint,
    sha256_bytes,
    terminal_transition_allowed,
    validate_capsule,
    verify_locator_registry,
    verify_registry_successor,
)

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
TTL = 24


def _sha_json(value):
    return sha256_bytes((canonical_json(value) + "\n").encode("utf-8"))


def _seal_capsule(capsule):
    capsule["semantic_fingerprint"] = semantic_fingerprint(capsule)
    capsule["capsule_root_sha256"] = content_root(capsule, "capsule_root_sha256")


def _seal_registry(registry):
    registry["registry_root_sha256"] = content_root(registry, "registry_root_sha256")


def make_fixture(root: Path):
    providers = {}
    for name in ("A", "B", "C"):
        path = root / name
        path.mkdir(parents=True)
        providers[name] = path

    data_bytes = b"9 7 5 8 6 4 10 9 3 12\n"
    data_digest = sha256_bytes(data_bytes)
    data_id = "sha256:" + data_digest
    data_name = data_digest + ".blob"
    (providers["A"] / data_name).write_bytes(data_bytes)
    (providers["B"] / data_name).write_bytes(data_bytes)

    primary = []
    values = list(map(int, data_bytes.decode().split()))
    for i in range(2, len(values) - 1):
        if values[i - 2] > values[i - 1] > values[i]:
            primary.append({"i": i, "side": "BUY", "entry": values[i], "exit": values[i + 1], "pnl_u": values[i + 1] - values[i]})
    metrics = {
        "n": len(primary),
        "net_u": sum(x["pnl_u"] for x in primary),
        "wins": sum(x["pnl_u"] > 0 for x in primary),
    }
    decision = {"gate": "TOY", "pass": metrics["n"] >= 1 and metrics["net_u"] > 0}

    artifacts = {}
    for artifact_name, artifact_bytes in {
        "data": data_bytes,
        "primary": b"primary-v1\n",
        "oracle": b"oracle-v1\n",
        "config": b"config-v1\n",
    }.items():
        digest = sha256_bytes(artifact_bytes)
        artifact_id = "sha256:" + digest
        filename = digest + ".blob"
        for provider in ("A", "B"):
            (providers[provider] / filename).write_bytes(artifact_bytes)
        artifacts[artifact_name] = {
            "artifact_id": artifact_id,
            "bytes": len(artifact_bytes),
            "critical": True,
            "encoding": "raw",
        }

    capsule = {
        "schema": "QROS_STRATEGY_RECONSTRUCTION_CAPSULE_1.3",
        "strategy_id": "QROS_SYNTHETIC_REJECTED_STRATEGY_v1",
        "campaign_id": "QROS_SRL_SYNTHETIC_ADVERSARIAL_v1",
        "scientific_state": "REJECTED",
        "asset": "XAUUSD",
        "side": "BUY",
        "timeframes": ["M1"],
        "rules_resolved": {
            "signal": {"type": "synthetic"},
            "entry": {"price": "ASK"},
            "exit": {"price": "BID", "sl_tp_ambiguity": "SL_FIRST"},
            "session": {"overnight": False},
            "execution": {"gap": "FIRST_EXECUTABLE", "zero_spread_fill": False},
        },
        "config_resolved": {
            "defaults_materialized": True,
            "additional_properties_allowed": False,
            "resolver_version": "SRL_CONFIG_RESOLVER_1.0",
        },
        "environment": {
            "os": "linux",
            "arch": "x86_64",
            "locale": "C.UTF-8",
            "timezone": "UTC",
            "rng_algorithm": "PCG64",
            "rng_seed": 20260914,
            "threads": 1,
            "fp_contract": "IEEE754_STRICT_OR_FIXED_POINT",
            "network_policy": "DECLARED_RESOLVERS_ONLY",
        },
        "runner": {
            "entrypoint": "synthetic-runner",
            "argv": ["--exact"],
            "cwd": ".",
            "env_allowlist": ["LANG", "TZ"],
            "runner_sha256": "1" * 64,
        },
        "oracle_requirement": "REQUIRED",
        "oracle": {"independent": True, "oracle_sha256": "2" * 64},
        "golden_vectors": {"status": "PASS", "receipt_sha256": "3" * 64},
        "exposure_ledger": ["DEV:2018-2019", "EXPOSED:2020-2024"],
        "artifacts": artifacts,
        "dependency_edges": {
            "data": [],
            "config": [],
            "primary": ["data", "config"],
            "oracle": ["data", "config"],
        },
        "semantic_fingerprint": "",
        "capsule_root_sha256": "",
        "resolver_contract_id": "QROS_LOCAL_RESOLVER_1.0",
        "expected": {
            "ledger_sha256": _sha_json(primary),
            "metrics_sha256": _sha_json(metrics),
            "decision_sha256": _sha_json(decision),
        },
    }
    _seal_capsule(capsule)

    registry = {
        "schema": "QROS_LOCATOR_REGISTRY_1.0",
        "generation": 1,
        "resolver_contract_id": "QROS_LOCAL_RESOLVER_1.0",
        "mappings": {},
        "registry_root_sha256": "",
    }
    for ref in artifacts.values():
        digest = ref["artifact_id"][7:]
        registry["mappings"][ref["artifact_id"]] = {
            "last_fetch_verified_utc": "2026-09-14T11:30:00Z",
            "locators": [
                {"provider": "A", "failure_domain": "fdA", "path": digest + ".blob"},
                {"provider": "B", "failure_domain": "fdB", "path": digest + ".blob"},
            ],
        }
    _seal_registry(registry)
    return capsule, registry, providers


def main():
    results = []

    def test(name, fn, expected=None):
        try:
            fn()
            got = "PASS"
        except SRLError as exc:
            got = str(exc)
        except Exception as exc:
            got = "UNEXPECTED:" + type(exc).__name__
        status = "PASS" if ((expected is None and got == "PASS") or (expected is not None and got == expected)) else "FAIL"
        results.append({"test": name, "expected": expected or "PASS", "got": got, "status": status})

    with tempfile.TemporaryDirectory(prefix="qros_srl_adv_") as temp:
        root = Path(temp)
        capsule, registry, providers = make_fixture(root)
        original_capsule_bytes = (canonical_json(capsule) + "\n").encode()
        data_id = capsule["artifacts"]["data"]["artifact_id"]
        mapping = registry["mappings"][data_id]
        loc_a, loc_b = mapping["locators"]
        path_a = providers[loc_a["provider"]] / loc_a["path"]
        path_b = providers[loc_b["provider"]] / loc_b["path"]
        bytes_a = path_a.read_bytes()
        bytes_b = path_b.read_bytes()

        test("T00_VALIDATE_CAPSULE", lambda: validate_capsule(capsule))
        test("T01_VALIDATE_REGISTRY", lambda: verify_locator_registry(registry))
        test("T02_CERTIFY_HEALTHY", lambda: certify_reconstruction(capsule, registry, providers, NOW, TTL))

        path_a.write_bytes(bytes_a + b"X")
        def degraded_now():
            r = clean_room_reconstruct(capsule, registry, providers, NOW, TTL)
            if r["recovery_health"] != "DEGRADED":
                raise SRLError("EXPECTED_DEGRADED_HEALTH")
        test("T03_ONE_MIRROR_CORRUPT_RECONSTRUCTS", degraded_now)
        test("T04_ONE_MIRROR_CORRUPT_CERT_FAILS", lambda: certify_reconstruction(capsule, registry, providers, NOW, TTL), "CRITICAL_REDUNDANCY_INSUFFICIENT")
        path_a.write_bytes(bytes_a)

        path_a.write_bytes(bytes_a + b"X")
        path_b.write_bytes(bytes_b + b"Y")
        test("T05_BOTH_MIRRORS_CORRUPT", lambda: clean_room_reconstruct(capsule, registry, providers, NOW, TTL), "FETCH_OR_HASH_VERIFY_FAILED")
        path_a.write_bytes(bytes_a)
        path_b.write_bytes(bytes_b)

        path_a.write_bytes(bytes_a + b"X")
        def repair_and_recertify():
            degraded = clean_room_reconstruct(capsule, registry, providers, NOW, TTL)
            if degraded["recovery_health"] != "DEGRADED":
                raise SRLError("EXPECTED_DEGRADED_HEALTH")
            target = providers["C"] / (data_id[7:] + ".blob")
            shutil.copyfile(path_b, target)
            if sha256_bytes(target.read_bytes()) != data_id[7:]:
                raise SRLError("REPAIR_HASH_FAIL")
            successor = copy.deepcopy(registry)
            successor["generation"] = 2
            successor["mappings"][data_id]["locators"] = [
                successor["mappings"][data_id]["locators"][1],
                {"provider": "C", "failure_domain": "fdC", "path": target.name},
            ]
            _seal_registry(successor)
            verify_registry_successor(registry, successor)
            certified = certify_reconstruction(capsule, successor, providers, NOW, TTL)
            if certified["recovery_health"] != "HEALTHY":
                raise SRLError("REPAIR_NOT_HEALTHY")
        test("T06_REPAIR_AND_RECERTIFY", repair_and_recertify)
        path_a.write_bytes(bytes_a)

        same_domain = copy.deepcopy(registry)
        same_domain["mappings"][data_id]["locators"][0]["failure_domain"] = "same"
        same_domain["mappings"][data_id]["locators"][1]["failure_domain"] = "same"
        _seal_registry(same_domain)
        test("T07_SAME_DOMAIN_RECONSTRUCTS", lambda: clean_room_reconstruct(capsule, same_domain, providers, NOW, TTL))
        test("T08_SAME_DOMAIN_CERT_FAILS", lambda: certify_reconstruction(capsule, same_domain, providers, NOW, TTL), "CRITICAL_REDUNDANCY_INSUFFICIENT")

        for name, timestamp, expected in [
            ("T09_STALE_FETCH", "2026-09-01T00:00:00Z", "FETCH_VERIFICATION_STALE"),
            ("T10_FUTURE_FETCH", "2026-09-14T13:00:00Z", "FETCH_TIMESTAMP_FUTURE"),
        ]:
            mutated = copy.deepcopy(registry)
            mutated["mappings"][data_id]["last_fetch_verified_utc"] = timestamp
            _seal_registry(mutated)
            test(name, lambda m=mutated: clean_room_reconstruct(capsule, m, providers, NOW, TTL), expected)

        missing = copy.deepcopy(registry)
        missing["mappings"][data_id]["locators"] = [{"provider": "A", "failure_domain": "fdA", "path": "missing"}]
        _seal_registry(missing)
        test("T11_MISSING_BYTES", lambda: clean_room_reconstruct(capsule, missing, providers, NOW, TTL), "FETCH_OR_HASH_VERIFY_FAILED")

        bad_root = copy.deepcopy(registry)
        bad_root["generation"] = 2
        test("T12_REGISTRY_ROOT_TAMPER", lambda: verify_locator_registry(bad_root), "REGISTRY_ROOT_MISMATCH")
        equal_generation = copy.deepcopy(registry)
        _seal_registry(equal_generation)
        test("T13_REGISTRY_ROLLBACK_OR_EQUAL", lambda: verify_registry_successor(registry, equal_generation), "REGISTRY_GENERATION_NOT_MONOTONIC")
        dropped = copy.deepcopy(registry)
        dropped["generation"] = 2
        dropped["mappings"].pop(data_id)
        _seal_registry(dropped)
        test("T14_REGISTRY_DROPS_MAPPING", lambda: verify_registry_successor(registry, dropped), "REGISTRY_MAPPING_DROPPED")
        resolver_changed = copy.deepcopy(registry)
        resolver_changed["generation"] = 2
        resolver_changed["resolver_contract_id"] = "OTHER"
        _seal_registry(resolver_changed)
        test("T15_REGISTRY_RESOLVER_CHANGE", lambda: verify_registry_successor(registry, resolver_changed), "REGISTRY_RESOLVER_CONTRACT_CHANGED")

        rotated_name = "rot-" + data_id[7:] + ".blob"
        (providers["C"] / rotated_name).write_bytes(bytes_a)
        rotated = copy.deepcopy(registry)
        rotated["generation"] = 2
        rotated["mappings"][data_id]["locators"] = [
            rotated["mappings"][data_id]["locators"][1],
            {"provider": "C", "failure_domain": "fdC", "path": rotated_name},
        ]
        _seal_registry(rotated)
        def locator_rotation():
            verify_registry_successor(registry, rotated)
            certify_reconstruction(capsule, rotated, providers, NOW, TTL)
            if (canonical_json(capsule) + "\n").encode() != original_capsule_bytes:
                raise SRLError("CAPSULE_MUTATED_BY_LOCATOR_ROTATION")
        test("T16_LOCATOR_ROTATION_CAPSULE_IMMUTABLE", locator_rotation)

        traversal = copy.deepcopy(registry)
        traversal["mappings"][data_id]["locators"] = [{"provider": "A", "failure_domain": "fdA", "path": "../escape"}]
        _seal_registry(traversal)
        test("T17_PATH_TRAVERSAL", lambda: clean_room_reconstruct(capsule, traversal, providers, NOW, TTL), "FETCH_OR_HASH_VERIFY_FAILED")

        symlink = providers["A"] / "link"
        try:
            symlink.symlink_to(path_a)
            symlink_registry = copy.deepcopy(registry)
            symlink_registry["mappings"][data_id]["locators"] = [{"provider": "A", "failure_domain": "fdA", "path": "link"}]
            _seal_registry(symlink_registry)
            test("T18_SYMLINK_FORBIDDEN", lambda: clean_room_reconstruct(capsule, symlink_registry, providers, NOW, TTL), "FETCH_OR_HASH_VERIFY_FAILED")
        finally:
            if symlink.exists() or symlink.is_symlink():
                symlink.unlink()

        mutations = [
            ("T19_RULES_INCOMPLETE", lambda x: x["rules_resolved"].pop("execution"), "RULES_NOT_FULLY_RESOLVED"),
            ("T20_DEFAULTS_UNRESOLVED", lambda x: x["config_resolved"].__setitem__("defaults_materialized", False), "CONFIG_NOT_CLOSED"),
            ("T21_OPEN_CONFIG_KEYS", lambda x: x["config_resolved"].__setitem__("additional_properties_allowed", True), "CONFIG_NOT_CLOSED"),
            ("T22_ORACLE_MISSING", lambda x: x.pop("oracle"), "ORACLE_REQUIRED_MISSING"),
            ("T23_NETWORK_OPEN", lambda x: x["environment"].__setitem__("network_policy", "OPEN"), "NETWORK_POLICY_OPEN"),
            ("T24_FP_CONTRACT_MISSING", lambda x: x["environment"].pop("fp_contract"), "ENVIRONMENT_INCOMPLETE"),
            ("T25_RUNNER_GLOB", lambda x: x["runner"].__setitem__("argv", ["*.json"]), "RUNNER_NONDETERMINISTIC_GLOB"),
            ("T26_DEPENDENCY_CYCLE", lambda x: x["dependency_edges"]["config"].append("primary"), "DEPENDENCY_CYCLE"),
            ("T27_DEPENDENCY_UNKNOWN", lambda x: x["dependency_edges"]["primary"].__setitem__(0, "missing"), "DEPENDENCY_GRAPH_OPEN"),
            ("T28_RULE_TAMPER", lambda x: x["rules_resolved"].__setitem__("entry", "other"), "SEMANTIC_FINGERPRINT_MISMATCH"),
            ("T29_SIDE_TAMPER", lambda x: x.__setitem__("side", "SELL"), "SEMANTIC_FINGERPRINT_MISMATCH"),
        ]
        for name, mutate, expected in mutations:
            changed = copy.deepcopy(capsule)
            mutate(changed)
            changed["capsule_root_sha256"] = content_root(changed, "capsule_root_sha256")
            test(name, lambda x=changed: validate_capsule(x), expected)

        weak_waiver = copy.deepcopy(capsule)
        weak_waiver["oracle_requirement"] = "WAIVED_NOT_APPLICABLE"
        weak_waiver.pop("oracle")
        weak_waiver["oracle_waiver"] = {"rationale": "not enough"}
        _seal_capsule(weak_waiver)
        test("T30_WEAK_ORACLE_WAIVER", lambda: validate_capsule(weak_waiver), "ORACLE_WAIVER_INVALID")

        root_tamper = copy.deepcopy(capsule)
        root_tamper["capsule_root_sha256"] = "0" * 64
        test("T31_CAPSULE_ROOT_TAMPER", lambda: validate_capsule(root_tamper), "CAPSULE_ROOT_MISMATCH")

        predecessor = copy.deepcopy(capsule)
        exposure_regression = copy.deepcopy(capsule)
        exposure_regression["exposure_ledger"] = ["DEV:2018-2019"]
        _seal_capsule(exposure_regression)
        test("T32_EXPOSURE_REGRESSION", lambda: clean_room_reconstruct(exposure_regression, registry, providers, NOW, TTL, predecessor=predecessor), "EXPOSURE_REGRESSION")

        missing_again = copy.deepcopy(registry)
        missing_again["mappings"][data_id]["locators"] = [{"provider": "A", "failure_domain": "fdA", "path": "gone"}]
        _seal_registry(missing_again)
        def scientific_state_preserved():
            try:
                clean_room_reconstruct(capsule, missing_again, providers, NOW, TTL)
            except SRLError as exc:
                if str(exc) != "FETCH_OR_HASH_VERIFY_FAILED":
                    raise
                if capsule["scientific_state"] != "REJECTED":
                    raise SRLError("SCIENTIFIC_STATE_CHANGED")
                return
            raise SRLError("EXPECTED_FAIL")
        test("T33_SCIENTIFIC_STATE_PRESERVED", scientific_state_preserved)

        reverse_index = {data_id: [capsule["strategy_id"]]}
        test("T34_RETENTION_REFERENCED_BLOB", lambda: retention_delete_allowed(data_id, reverse_index, 2, 2), "RETENTION_REFERENCED_BLOB")
        free_id = "sha256:" + "1" * 64
        test("T35_RETENTION_TOCTOU", lambda: retention_delete_allowed(free_id, {}, 2, 3), "RETENTION_GENERATION_CHANGED")
        test("T36_RETENTION_FREE_BLOB", lambda: retention_delete_allowed(free_id, {}, 2, 2))

        for name, key, expected in [
            ("T37_LEDGER_EXPECTED_TAMPER", "ledger_sha256", "LEDGER_MISMATCH"),
            ("T38_METRICS_EXPECTED_TAMPER", "metrics_sha256", "METRICS_MISMATCH"),
            ("T39_DECISION_EXPECTED_TAMPER", "decision_sha256", "DECISION_MISMATCH"),
        ]:
            changed = copy.deepcopy(capsule)
            changed["expected"][key] = "f" * 64
            _seal_capsule(changed)
            test(name, lambda x=changed: clean_room_reconstruct(x, registry, providers, NOW, TTL), expected)

        compressed = copy.deepcopy(capsule)
        compressed["artifacts"]["data"]["encoding"] = "zip"
        _seal_capsule(compressed)
        test("T40_COMPRESSED_IDENTITY_INCOMPLETE", lambda: clean_room_reconstruct(compressed, registry, providers, NOW, TTL), "PAYLOAD_IDENTITY_INCOMPLETE")

        nonfinite = copy.deepcopy(capsule)
        nonfinite["config_resolved"]["bad"] = float("nan")
        test("T41_NONFINITE_JSON", lambda: canonical_json(nonfinite), "NONFINITE_JSON_FORBIDDEN")

        bad_artifact = copy.deepcopy(capsule)
        bad_artifact["artifacts"]["data"]["artifact_id"] = "md5:x"
        _seal_capsule(bad_artifact)
        test("T42_BAD_ARTIFACT_ID", lambda: clean_room_reconstruct(bad_artifact, registry, providers, NOW, TTL), "ARTIFACT_ID_INVALID")

        one_copy = copy.deepcopy(registry)
        one_copy["mappings"][data_id]["locators"] = one_copy["mappings"][data_id]["locators"][:1]
        _seal_registry(one_copy)
        with_remat = copy.deepcopy(capsule)
        with_remat["artifacts"]["data"]["rematerialization"] = {"closed": True, "reconstructable_exact": True, "acyclic": True}
        _seal_capsule(with_remat)
        test("T43_ONE_COPY_PLUS_CLOSED_REMAT", lambda: certify_reconstruction(with_remat, one_copy, providers, NOW, TTL))
        cyclic_remat = copy.deepcopy(capsule)
        cyclic_remat["artifacts"]["data"]["rematerialization"] = {"closed": True, "reconstructable_exact": True, "acyclic": False}
        _seal_capsule(cyclic_remat)
        test("T44_CYCLIC_REMAT_NOT_ENOUGH", lambda: certify_reconstruction(cyclic_remat, one_copy, providers, NOW, TTL), "CRITICAL_REDUNDANCY_INSUFFICIENT")

        generation_two = copy.deepcopy(registry)
        generation_two["generation"] = 2
        _seal_registry(generation_two)
        def exact_registry_root_captured():
            a = clean_room_reconstruct(capsule, registry, providers, NOW, TTL)
            b = clean_room_reconstruct(capsule, generation_two, providers, NOW, TTL)
            if a["registry_root_sha256"] == b["registry_root_sha256"]:
                raise SRLError("REGISTRY_ROOT_NOT_CAPTURED")
        test("T45_EXACT_REGISTRY_ROOT_CAPTURED", exact_registry_root_captured)

        def capsule_has_no_locator():
            text = canonical_json(capsule)
            for forbidden in ("locators", "providerA", "providerB", "failure_domain"):
                if forbidden in text:
                    raise SRLError("LOCATOR_LEAK")
        test("T46_CAPSULE_NO_PROVIDER_LOCATORS", capsule_has_no_locator)

        historical_certificate = certify_reconstruction(capsule, registry, providers, NOW, TTL)
        path_a.write_bytes(bytes_a + b"X")
        def certificate_history_immutable():
            if historical_certificate["reconstruction_certification"] != "CERTIFIED_EXACT_AT_TIME":
                raise SRLError("OLD_CERT_LOST")
            current = clean_room_reconstruct(capsule, registry, providers, NOW, TTL)
            if current["recovery_health"] != "DEGRADED":
                raise SRLError("CURRENT_HEALTH_NOT_DEGRADED")
        test("T47_HISTORIC_CERT_PRESERVED", certificate_history_immutable)
        test("T48_NEW_TERMINAL_CERT_REQUIRES_R17", lambda: certify_reconstruction(capsule, registry, providers, NOW, TTL), "CRITICAL_REDUNDANCY_INSUFFICIENT")
        path_a.write_bytes(bytes_a)

        test("T49_FINAL_BASELINE_RECERTIFY", lambda: certify_reconstruction(capsule, registry, providers, NOW, TTL))

        certificate = certify_reconstruction(capsule, registry, providers, NOW, TTL)
        test("T50_TERMINAL_TRANSITION_CERTIFIED", lambda: terminal_transition_allowed("REJECTED", certificate))
        wrong_state_cert = copy.deepcopy(certificate)
        wrong_state_cert["scientific_state"] = "APPROVED_FINAL"
        test("T51_TERMINAL_TRANSITION_STATE_MISMATCH", lambda: terminal_transition_allowed("REJECTED", wrong_state_cert), "RECONSTRUCTABILITY_CERTIFICATE_STATE_MISMATCH")
        missing_cert = {"scientific_state": "REJECTED", "recovery_health": "HEALTHY"}
        test("T52_TERMINAL_TRANSITION_CERT_MISSING", lambda: terminal_transition_allowed("REJECTED", missing_cert), "RECONSTRUCTABILITY_CERTIFICATE_REQUIRED")
        degraded_cert = copy.deepcopy(certificate)
        degraded_cert["recovery_health"] = "DEGRADED"
        test("T53_TERMINAL_TRANSITION_DEGRADED", lambda: terminal_transition_allowed("REJECTED", degraded_cert), "RECONSTRUCTABILITY_HEALTH_NOT_HEALTHY")

    status = "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL"
    output = {
        "status": status,
        "schema": "QROS_SRL_ADVERSARIAL_RECEIPT_1.3",
        "synthetic_only": True,
        "economic_pnl_read": False,
        "test_count": len(results),
        "passed": sum(row["status"] == "PASS" for row in results),
        "failed": [row for row in results if row["status"] != "PASS"],
        "results": results,
    }
    print(canonical_json(output))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
