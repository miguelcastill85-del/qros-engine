from __future__ import annotations
import copy, hashlib, json
from typing import Any

SCHEMA = "QROS_SCIENTIFIC_CONTEXT_1.0"
BINDING_INPUT = "__scientific_context__"
REQUIRED_FIELDS = (
    "schema","campaign_id","seed_id","genealogy_id","phase","asset","side","timeframe",
    "development_period","scientific_state","holdout_state","exposure_state",
    "multiplicity_scope","cost_model_id","gate_policy_id","selection_policy_id",
    "thesis_fingerprint","data_context_fingerprint","extensions",
)
HEX64_FIELDS = ("thesis_fingerprint","data_context_fingerprint")

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _nonempty_string(v: Any, label: str) -> str:
    if not isinstance(v, str) or not v:
        raise ValueError(label + "_REQUIRED")
    return v

def _hex64(v: Any, label: str) -> str:
    v = _nonempty_string(v, label)
    if len(v) != 64:
        raise ValueError(label + "_INVALID")
    try:
        int(v, 16)
    except Exception as e:
        raise ValueError(label + "_INVALID") from e
    return v

def validate_scientific_context(context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise ValueError("SCIENTIFIC_CONTEXT_OBJECT_REQUIRED")
    if set(context) != set(REQUIRED_FIELDS):
        missing = sorted(set(REQUIRED_FIELDS) - set(context))
        extra = sorted(set(context) - set(REQUIRED_FIELDS))
        raise ValueError("SCIENTIFIC_CONTEXT_FIELDS_INVALID:missing=" + ",".join(missing) + ";extra=" + ",".join(extra))
    if context.get("schema") != SCHEMA:
        raise ValueError("SCIENTIFIC_CONTEXT_SCHEMA_INVALID")
    for field in (
        "campaign_id","seed_id","genealogy_id","phase","asset","side","timeframe",
        "scientific_state","holdout_state","exposure_state","multiplicity_scope",
        "cost_model_id","gate_policy_id","selection_policy_id",
    ):
        _nonempty_string(context[field], field.upper())
    for field in HEX64_FIELDS:
        _hex64(context[field], field.upper())
    period = context["development_period"]
    if not isinstance(period, dict) or set(period) != {"start","end","timezone"}:
        raise ValueError("DEVELOPMENT_PERIOD_INVALID")
    for field in ("start","end","timezone"):
        _nonempty_string(period[field], "DEVELOPMENT_PERIOD_" + field.upper())
    if not isinstance(context["extensions"], dict):
        raise ValueError("SCIENTIFIC_CONTEXT_EXTENSIONS_INVALID")
    canonical_bytes(context)
    return copy.deepcopy(context)

def scientific_context_artifact(context: dict[str, Any]) -> tuple[bytes, str]:
    normalized = validate_scientific_context(context)
    raw = canonical_bytes(normalized)
    return raw, sha256_bytes(raw)

def bind_scientific_context(manifest: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("MANIFEST_OBJECT_REQUIRED")
    nodes = manifest.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("MANIFEST_NODES_REQUIRED")
    _, context_hash = scientific_context_artifact(context)
    compiled = copy.deepcopy(manifest)
    for node in compiled["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("MANIFEST_NODE_INVALID")
        static = node.get("static_inputs")
        if not isinstance(static, dict):
            raise ValueError("STATIC_INPUTS_INVALID")
        if BINDING_INPUT in static:
            raise ValueError("RESERVED_SCIENTIFIC_CONTEXT_INPUT_PRESENT")
        static[BINDING_INPUT] = context_hash
    return {
        "manifest": compiled,
        "scientific_context": validate_scientific_context(context),
        "scientific_context_sha256": context_hash,
        "binding_input": BINDING_INPUT,
    }
