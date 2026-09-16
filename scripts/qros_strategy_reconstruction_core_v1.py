#!/usr/bin/env python3
"""QROS Strategy Reconstruction Layer v1.3 core.

Branch-only implementation. This module deliberately keeps scientific state,
reconstruction capability, reconstruction certification, and recovery health
as separate axes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple


class SRLError(Exception):
    pass


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SRLError("NONFINITE_JSON_FORBIDDEN")
        return value
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {_normalize(k): _normalize(v) for k, v in value.items()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def content_root(document: Mapping[str, Any], root_field: str) -> str:
    payload = {k: v for k, v in document.items() if k != root_field}
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _artifact_digest(artifact_id: Any) -> str:
    if not isinstance(artifact_id, str) or not artifact_id.startswith("sha256:") or len(artifact_id) != 71:
        raise SRLError("ARTIFACT_ID_INVALID")
    digest = artifact_id[7:]
    try:
        int(digest, 16)
    except Exception as exc:
        raise SRLError("ARTIFACT_ID_INVALID") from exc
    return digest


def verify_locator_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema") != "QROS_LOCATOR_REGISTRY_1.0":
        raise SRLError("REGISTRY_SCHEMA_INVALID")
    if registry.get("registry_root_sha256") != content_root(registry, "registry_root_sha256"):
        raise SRLError("REGISTRY_ROOT_MISMATCH")
    generation = registry.get("generation")
    if not isinstance(generation, int) or generation < 1:
        raise SRLError("REGISTRY_GENERATION_INVALID")
    resolver_contract_id = registry.get("resolver_contract_id")
    if not isinstance(resolver_contract_id, str) or not resolver_contract_id:
        raise SRLError("REGISTRY_RESOLVER_CONTRACT_INVALID")
    mappings = registry.get("mappings")
    if not isinstance(mappings, dict):
        raise SRLError("REGISTRY_MAPPINGS_INVALID")
    for artifact_id, mapping in mappings.items():
        _artifact_digest(artifact_id)
        if not isinstance(mapping, dict):
            raise SRLError("REGISTRY_MAPPING_INVALID")
        if not isinstance(mapping.get("locators"), list):
            raise SRLError("REGISTRY_LOCATORS_INVALID")


def verify_registry_successor(old: Mapping[str, Any], new: Mapping[str, Any]) -> None:
    verify_locator_registry(old)
    verify_locator_registry(new)
    if new["generation"] <= old["generation"]:
        raise SRLError("REGISTRY_GENERATION_NOT_MONOTONIC")
    if new.get("resolver_contract_id") != old.get("resolver_contract_id"):
        raise SRLError("REGISTRY_RESOLVER_CONTRACT_CHANGED")
    for artifact_id in old.get("mappings", {}):
        if artifact_id not in new.get("mappings", {}):
            raise SRLError("REGISTRY_MAPPING_DROPPED")


def _safe_local_path(provider_root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith("/"):
        raise SRLError("LOCATOR_PATH_UNSAFE")
    rel_path = Path(relative)
    if ".." in rel_path.parts:
        raise SRLError("LOCATOR_PATH_UNSAFE")
    raw_path = provider_root / rel_path
    if raw_path.is_symlink():
        raise SRLError("LOCATOR_SYMLINK_FORBIDDEN")
    try:
        resolved_root = provider_root.resolve(strict=True)
        resolved_path = raw_path.resolve(strict=True)
        resolved_path.relative_to(resolved_root)
    except SRLError:
        raise
    except Exception as exc:
        raise SRLError("LOCATOR_UNREADABLE") from exc
    if not resolved_path.is_file():
        raise SRLError("LOCATOR_UNREADABLE")
    return resolved_path


def _parse_verified_timestamp(text: Any) -> datetime:
    if not isinstance(text, str):
        raise SRLError("FETCH_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise SRLError("FETCH_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None:
        raise SRLError("FETCH_TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)


def resolve_artifact(
    ref: Mapping[str, Any],
    registry: Mapping[str, Any],
    providers: Mapping[str, Path],
    now: datetime,
    fetch_ttl_hours: int,
    strict_redundancy: bool,
) -> Tuple[Path, str]:
    artifact_id = ref.get("artifact_id")
    digest = _artifact_digest(artifact_id)
    expected_bytes = ref.get("bytes")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise SRLError("ARTIFACT_SIZE_INVALID")
    mapping = registry.get("mappings", {}).get(artifact_id)
    if not isinstance(mapping, dict):
        raise SRLError("ARTIFACT_NOT_IN_REGISTRY")
    verified_at = _parse_verified_timestamp(mapping.get("last_fetch_verified_utc"))
    now_utc = now.astimezone(timezone.utc)
    if verified_at > now_utc + timedelta(minutes=5):
        raise SRLError("FETCH_TIMESTAMP_FUTURE")
    if now_utc - verified_at > timedelta(hours=fetch_ttl_hours):
        raise SRLError("FETCH_VERIFICATION_STALE")

    good_paths = []
    failure_domains = set()
    for locator in mapping.get("locators", []):
        if not isinstance(locator, dict):
            continue
        provider = locator.get("provider")
        failure_domain = locator.get("failure_domain")
        if provider not in providers or not isinstance(failure_domain, str) or not failure_domain:
            continue
        try:
            path = _safe_local_path(providers[provider], locator.get("path"))
        except SRLError:
            continue
        if path.stat().st_size != expected_bytes:
            continue
        if sha256_file(path) != digest:
            continue
        good_paths.append(path)
        failure_domains.add(failure_domain)

    if not good_paths:
        raise SRLError("FETCH_OR_HASH_VERIFY_FAILED")

    rematerialization = ref.get("rematerialization")
    has_closed_rematerialization = (
        isinstance(rematerialization, dict)
        and rematerialization.get("closed") is True
        and rematerialization.get("reconstructable_exact") is True
        and rematerialization.get("acyclic") is True
    )
    recovery_health = "HEALTHY" if len(failure_domains) >= 2 or has_closed_rematerialization else "DEGRADED"
    if strict_redundancy and ref.get("critical", True) and recovery_health != "HEALTHY":
        raise SRLError("CRITICAL_REDUNDANCY_INSUFFICIENT")

    if ref.get("encoding") in {"zip", "gzip", "container"}:
        if not ref.get("payload_sha256") or not ref.get("decoder_sha256"):
            raise SRLError("PAYLOAD_IDENTITY_INCOMPLETE")

    return good_paths[0], recovery_health


def _assert_acyclic(graph: Mapping[str, Iterable[str]]) -> None:
    seen = set()
    active = set()

    def visit(node: str) -> None:
        if node in active:
            raise SRLError("DEPENDENCY_CYCLE")
        if node in seen:
            return
        active.add(node)
        for child in graph.get(node, []):
            visit(child)
        active.remove(node)
        seen.add(node)

    for node in graph:
        visit(node)


def semantic_fingerprint(capsule: Mapping[str, Any]) -> str:
    semantic = {
        "rules_resolved": capsule["rules_resolved"],
        "config_resolved": capsule["config_resolved"],
        "asset": capsule["asset"],
        "side": capsule["side"],
        "timeframes": capsule["timeframes"],
    }
    return sha256_bytes(canonical_json(semantic).encode("utf-8"))


def validate_capsule(capsule: Mapping[str, Any]) -> None:
    required = [
        "schema", "strategy_id", "campaign_id", "scientific_state", "asset", "side", "timeframes",
        "rules_resolved", "config_resolved", "environment", "runner", "oracle_requirement",
        "golden_vectors", "exposure_ledger", "artifacts", "dependency_edges", "semantic_fingerprint",
        "capsule_root_sha256", "resolver_contract_id", "expected",
    ]
    if any(key not in capsule for key in required):
        raise SRLError("CAPSULE_FIELD_MISSING")
    if capsule["schema"] != "QROS_STRATEGY_RECONSTRUCTION_CAPSULE_1.3":
        raise SRLError("CAPSULE_SCHEMA_INVALID")
    if not isinstance(capsule["strategy_id"], str) or not capsule["strategy_id"]:
        raise SRLError("STRATEGY_ID_INVALID")
    if set(capsule["rules_resolved"]) != {"signal", "entry", "exit", "session", "execution"}:
        raise SRLError("RULES_NOT_FULLY_RESOLVED")

    config = capsule["config_resolved"]
    if (
        config.get("defaults_materialized") is not True
        or config.get("additional_properties_allowed") is not False
        or not config.get("resolver_version")
    ):
        raise SRLError("CONFIG_NOT_CLOSED")

    environment = capsule["environment"]
    for key in ("os", "arch", "locale", "timezone", "rng_algorithm", "rng_seed", "threads", "fp_contract", "network_policy"):
        if key not in environment:
            raise SRLError("ENVIRONMENT_INCOMPLETE")
    if environment["network_policy"] != "DECLARED_RESOLVERS_ONLY":
        raise SRLError("NETWORK_POLICY_OPEN")

    runner = capsule["runner"]
    for key in ("entrypoint", "argv", "cwd", "env_allowlist", "runner_sha256"):
        if key not in runner:
            raise SRLError("RUNNER_INCOMPLETE")
    if not isinstance(runner["argv"], list) or any(not isinstance(arg, str) for arg in runner["argv"]):
        raise SRLError("RUNNER_INCOMPLETE")
    if any("*" in arg or "?" in arg for arg in runner["argv"]):
        raise SRLError("RUNNER_NONDETERMINISTIC_GLOB")

    requirement = capsule["oracle_requirement"]
    if requirement == "REQUIRED":
        if not capsule.get("oracle", {}).get("independent"):
            raise SRLError("ORACLE_REQUIRED_MISSING")
    elif requirement == "WAIVED_NOT_APPLICABLE":
        waiver = capsule.get("oracle_waiver")
        if not isinstance(waiver, dict) or not waiver.get("receipt_sha256") or not waiver.get("rationale"):
            raise SRLError("ORACLE_WAIVER_INVALID")
    else:
        raise SRLError("ORACLE_REQUIREMENT_INVALID")

    if capsule["golden_vectors"].get("status") != "PASS":
        raise SRLError("GOLDEN_VECTOR_NOT_PASS")

    artifacts = capsule["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise SRLError("ARTIFACTS_INVALID")
    for ref in artifacts.values():
        _artifact_digest(ref.get("artifact_id"))
        if not isinstance(ref.get("bytes"), int):
            raise SRLError("ARTIFACT_SIZE_INVALID")

    graph = capsule["dependency_edges"]
    if not isinstance(graph, dict):
        raise SRLError("DEPENDENCY_GRAPH_INVALID")
    _assert_acyclic(graph)
    artifact_names = set(artifacts)
    for node, dependencies in graph.items():
        if node not in artifact_names or any(dependency not in artifact_names for dependency in dependencies):
            raise SRLError("DEPENDENCY_GRAPH_OPEN")

    if capsule["semantic_fingerprint"] != semantic_fingerprint(capsule):
        raise SRLError("SEMANTIC_FINGERPRINT_MISMATCH")
    if capsule["capsule_root_sha256"] != content_root(capsule, "capsule_root_sha256"):
        raise SRLError("CAPSULE_ROOT_MISMATCH")


def _verify_exposure_monotonicity(capsule: Mapping[str, Any], predecessor: Optional[Mapping[str, Any]]) -> None:
    if predecessor is None:
        return
    old = set(predecessor.get("exposure_ledger", []))
    new = set(capsule.get("exposure_ledger", []))
    if not old.issubset(new):
        raise SRLError("EXPOSURE_REGRESSION")


def clean_room_reconstruct(
    capsule: Mapping[str, Any],
    registry: Mapping[str, Any],
    providers: Mapping[str, Path],
    now: datetime,
    fetch_ttl_hours: int,
    strict_redundancy: bool = False,
    predecessor: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    validate_capsule(capsule)
    verify_locator_registry(registry)
    if capsule["resolver_contract_id"] != registry.get("resolver_contract_id"):
        raise SRLError("RESOLVER_CONTRACT_MISMATCH")
    _verify_exposure_monotonicity(capsule, predecessor)

    recovery_health = "HEALTHY"
    paths: Dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="qros_srl_") as temp_dir:
        workspace = Path(temp_dir)
        for name, ref in capsule["artifacts"].items():
            source, artifact_health = resolve_artifact(
                ref, registry, providers, now, fetch_ttl_hours, strict_redundancy
            )
            if artifact_health == "DEGRADED":
                recovery_health = "DEGRADED"
            destination = workspace / f"{name}.blob"
            shutil.copyfile(source, destination)
            if sha256_file(destination) != ref["artifact_id"][7:]:
                raise SRLError("CLEANROOM_COPY_HASH_MISMATCH")
            paths[name] = destination

        # The branch implementation intentionally uses a deterministic toy runner
        # for CI/adversarial certification. Real strategy adapters must implement
        # the same comparison contract before merge to main.
        if "data" not in paths:
            raise SRLError("CLEANROOM_DATA_ARTIFACT_MISSING")
        values = list(map(int, paths["data"].read_text(encoding="utf-8").split()))
        primary = []
        oracle = []
        for i in range(2, len(values) - 1):
            if values[i - 2] > values[i - 1] > values[i]:
                primary.append({"i": i, "side": "BUY", "entry": values[i], "exit": values[i + 1], "pnl_u": values[i + 1] - values[i]})
        for j, (a, b, x, y) in enumerate(zip(values, values[1:], values[2:], values[3:])):
            if a > b > x:
                oracle.append({"i": j + 2, "side": "BUY", "entry": x, "exit": y, "pnl_u": y - x})
        if primary != oracle:
            raise SRLError("PRIMARY_ORACLE_DIVERGENCE")

        ledger_bytes = (canonical_json(primary) + "\n").encode("utf-8")
        if sha256_bytes(ledger_bytes) != capsule["expected"]["ledger_sha256"]:
            raise SRLError("LEDGER_MISMATCH")
        metrics = {
            "n": len(primary),
            "net_u": sum(row["pnl_u"] for row in primary),
            "wins": sum(row["pnl_u"] > 0 for row in primary),
        }
        metrics_bytes = (canonical_json(metrics) + "\n").encode("utf-8")
        if sha256_bytes(metrics_bytes) != capsule["expected"]["metrics_sha256"]:
            raise SRLError("METRICS_MISMATCH")
        decision = {"gate": "TOY", "pass": metrics["n"] >= 1 and metrics["net_u"] > 0}
        decision_bytes = (canonical_json(decision) + "\n").encode("utf-8")
        if sha256_bytes(decision_bytes) != capsule["expected"]["decision_sha256"]:
            raise SRLError("DECISION_MISMATCH")

    return {
        "status": "PASS",
        "reconstruction_capability": "EXACT_NOW",
        "recovery_health": recovery_health,
        "registry_root_sha256": registry["registry_root_sha256"],
        "capsule_root_sha256": capsule["capsule_root_sha256"],
        "scientific_state": capsule["scientific_state"],
    }


def certify_reconstruction(
    capsule: Mapping[str, Any],
    registry: Mapping[str, Any],
    providers: Mapping[str, Path],
    now: datetime,
    fetch_ttl_hours: int,
    predecessor: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    result = clean_room_reconstruct(
        capsule, registry, providers, now, fetch_ttl_hours, strict_redundancy=True, predecessor=predecessor
    )
    result["reconstruction_certification"] = "CERTIFIED_EXACT_AT_TIME"
    result["certified_at_utc"] = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return result


def retention_delete_allowed(
    artifact_id: str,
    reverse_dependency_index: Mapping[str, Iterable[str]],
    plan_generation: int,
    current_generation: int,
) -> None:
    _artifact_digest(artifact_id)
    if plan_generation != current_generation:
        raise SRLError("RETENTION_GENERATION_CHANGED")
    if list(reverse_dependency_index.get(artifact_id, [])):
        raise SRLError("RETENTION_REFERENCED_BLOB")


def terminal_transition_allowed(requested_scientific_state: str, certificate: Mapping[str, Any]) -> None:
    protected = {
        "FROZEN_CANDIDATE", "REJECTED", "OBSERVATIONAL_RESERVE", "BRANCH_EXHAUSTED",
        "APPROVED_RESEARCH", "APPROVED_FINAL",
    }
    if requested_scientific_state not in protected:
        return
    if certificate.get("reconstruction_certification") != "CERTIFIED_EXACT_AT_TIME":
        raise SRLError("RECONSTRUCTABILITY_CERTIFICATE_REQUIRED")
    if certificate.get("recovery_health") != "HEALTHY":
        raise SRLError("RECONSTRUCTABILITY_HEALTH_NOT_HEALTHY")
    if certificate.get("scientific_state") != requested_scientific_state:
        raise SRLError("RECONSTRUCTABILITY_CERTIFICATE_STATE_MISMATCH")


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_provider(spec: str) -> Tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError("provider must be NAME=/absolute/path")
    name, raw = spec.split("=", 1)
    if not name or not raw:
        raise argparse.ArgumentTypeError("provider must be NAME=/absolute/path")
    return name, Path(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_capsule = sub.add_parser("validate-capsule")
    p_capsule.add_argument("--capsule", required=True)

    p_registry = sub.add_parser("validate-registry")
    p_registry.add_argument("--registry", required=True)

    p_cert = sub.add_parser("certify")
    p_cert.add_argument("--capsule", required=True)
    p_cert.add_argument("--registry", required=True)
    p_cert.add_argument("--provider", action="append", default=[], type=_parse_provider)
    p_cert.add_argument("--fetch-ttl-hours", type=int, default=24)
    p_cert.add_argument("--now-utc")

    p_transition = sub.add_parser("transition-check")
    p_transition.add_argument("--state", required=True)
    p_transition.add_argument("--certificate", required=True)

    args = parser.parse_args()
    try:
        if args.command == "validate-capsule":
            capsule = _load_json(args.capsule)
            validate_capsule(capsule)
            output = {"status": "PASS", "capsule_root_sha256": capsule["capsule_root_sha256"]}
        elif args.command == "validate-registry":
            registry = _load_json(args.registry)
            verify_locator_registry(registry)
            output = {"status": "PASS", "registry_root_sha256": registry["registry_root_sha256"], "generation": registry["generation"]}
        elif args.command == "certify":
            capsule = _load_json(args.capsule)
            registry = _load_json(args.registry)
            providers = dict(args.provider)
            if not providers:
                raise SRLError("PROVIDER_MAP_REQUIRED")
            now = datetime.now(timezone.utc) if not args.now_utc else _parse_verified_timestamp(args.now_utc)
            output = certify_reconstruction(capsule, registry, providers, now, args.fetch_ttl_hours)
        else:
            certificate = _load_json(args.certificate)
            terminal_transition_allowed(args.state, certificate)
            output = {"status": "PASS", "state": args.state}
        print(canonical_json(output))
        return 0
    except SRLError as exc:
        print(canonical_json({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    except Exception as exc:
        print(canonical_json({"status": "FAIL_CLOSED", "error": "UNEXPECTED_ERROR", "detail": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
