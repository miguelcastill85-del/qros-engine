from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
from qros_scientific_context import BINDING_INPUT, bind_scientific_context
from qros_typed_action import validate_environment_manifest
from qros_typed_dag import EXECUTION_CONTRACT as RAW_EXECUTION_CONTRACT
from qros_typed_dag import execute_manifest, manifest_root, normalize_manifest, validate_run_receipt

SCHEMA = "QROS_SCIENTIFIC_DAG_EXECUTION_1.0"
EXECUTION_CONTRACT = "SCIENTIFIC_CONTEXT_BOUND_ONLY"
EXPECTED_RAW_EXECUTION_CONTRACT = "TECHNICAL_ONLY_UNBOUND_MANIFESTS_NOT_SCIENTIFICALLY_ADMISSIBLE"

def compile_scientific_manifest(manifest: dict[str, Any], scientific_context: dict[str, Any]) -> dict[str, Any]:
    if RAW_EXECUTION_CONTRACT != EXPECTED_RAW_EXECUTION_CONTRACT:
        raise RuntimeError("RAW_EXECUTOR_CONTRACT_MISMATCH")
    bound = bind_scientific_context(manifest, scientific_context)
    for node in bound["manifest"]["nodes"]:
        try:
            validate_environment_manifest(node.get("environment"))
        except ValueError as e:
            raise ValueError("SCIENTIFIC_ENVIRONMENT_INVALID:" + str(node.get("id", "<unknown>")) + ":" + str(e)) from e
    normalized = normalize_manifest(bound["manifest"])
    expected = bound["scientific_context_sha256"]
    for node in normalized["nodes"]:
        if node["static_inputs"].get(BINDING_INPUT) != expected:
            raise ValueError("SCIENTIFIC_CONTEXT_BINDING_PROPAGATION_FAILED:" + node["id"])
    return {
        "schema": SCHEMA,
        "execution_contract": EXECUTION_CONTRACT,
        "raw_execution_contract": RAW_EXECUTION_CONTRACT,
        "manifest": normalized,
        "manifest_root_sha256": manifest_root(normalized),
        "scientific_context": bound["scientific_context"],
        "scientific_context_sha256": expected,
        "binding_input": BINDING_INPUT,
    }

def execute_scientific_manifest(manifest: dict[str, Any], scientific_context: dict[str, Any],
                                cas_dir: str | Path,
                                operations: dict[str, Callable[[dict[str, Any], dict[str, bytes]], bytes]],
                                *, crash_after_nodes: int | None = None) -> dict[str, Any]:
    compiled = compile_scientific_manifest(manifest, scientific_context)
    result = execute_manifest(compiled["manifest"], cas_dir, operations, crash_after_nodes=crash_after_nodes)
    if result["manifest_root_sha256"] != compiled["manifest_root_sha256"]:
        raise ValueError("SCIENTIFIC_MANIFEST_ROOT_MISMATCH")
    return {
        **result,
        "scientific_execution_schema": SCHEMA,
        "execution_contract": EXECUTION_CONTRACT,
        "scientific_context_sha256": compiled["scientific_context_sha256"],
        "binding_input": BINDING_INPUT,
    }

def validate_scientific_run(manifest: dict[str, Any], scientific_context: dict[str, Any],
                            cas_dir: str | Path) -> dict[str, Any]:
    compiled = compile_scientific_manifest(manifest, scientific_context)
    receipt = validate_run_receipt(compiled["manifest"], cas_dir)
    return {
        "status": "PASS",
        "manifest_root_sha256": compiled["manifest_root_sha256"],
        "scientific_context_sha256": compiled["scientific_context_sha256"],
        "node_count": receipt["node_count"],
        "receipt": receipt,
    }
