from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

SCHEMA = "QROS_EVIDENCE_NATIVE_RECOVERY_VERIFIER_2.0"
ROOT_SCHEMA = "QROS_GA1_EVIDENCE_NATIVE_RECOVERY_ROOT_1.0"

CODE_PATHS = {
    "event_canary": "research/ga1_compiled_dag_factor_ir_v1/qros_independent_event_canary.py",
    "factor_ir": "research/ga1_compiled_dag_factor_ir_v1/qros_factor_ir.py",
    "factor_ir_store": "research/ga1_compiled_dag_factor_ir_v1/qros_factor_ir_store.py",
    "geometry_compiler": "research/ga1_compiled_dag_factor_ir_v1/qros_geometry_compiler.py",
    "maskpack_regression": "research/ga1_compiled_dag_factor_ir_v1/qros_maskpack_regression.py",
    "typed_action": "research/ga1_compiled_dag_factor_ir_v1/qros_typed_action.py",
    "typed_dag": "research/ga1_compiled_dag_factor_ir_v1/qros_typed_dag.py",
    "recovery_verifier": "research/ga1_compiled_dag_factor_ir_v1/qros_recovery_verifier.py",
}
HANDOFF_PATH = "control/QROS_PUBLIC_1000_CURRENT_CHAT_HANDOFF.json"
POINTER_PATH = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

def _resolve_under(root: Path, rel_or_path: str | Path) -> Path:
    base = root.resolve()
    p = Path(rel_or_path)
    if isinstance(rel_or_path, str) and "\\" in rel_or_path:
        raise ValueError("PATH_INVALID")
    if p.is_absolute():
        full = p.resolve()
    else:
        if any(part in ("", ".", "..") for part in p.parts):
            raise ValueError("PATH_INVALID")
        full = (base / p).resolve()
    if full != base and base not in full.parents:
        raise ValueError("PATH_TRAVERSAL")
    return full

def _read(root: Path, rel_or_path: str | Path) -> bytes:
    p = _resolve_under(root, rel_or_path)
    if not p.is_file():
        raise ValueError("MISSING_ARTIFACT:" + str(rel_or_path))
    return p.read_bytes()

def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        obj = json.loads(data.decode("utf-8"))
    except Exception as e:
        raise ValueError(label + "_JSON_INVALID") from e
    if not isinstance(obj, dict):
        raise ValueError(label + "_OBJECT_REQUIRED")
    return obj

def verify_receipt_bytes(data: bytes, label: str) -> bool:
    obj = _json_bytes(data, label)
    if "receipt_sha256" not in obj:
        return False
    got = obj.get("receipt_sha256")
    clean = {k: v for k, v in obj.items() if k != "receipt_sha256"}
    want = sha256_bytes(canonical_bytes(clean))
    if got != want:
        raise ValueError("RECEIPT_SELF_HASH_MISMATCH:" + label)
    return True

def verify_ledger(ledger: bytes, spec: dict[str, Any]) -> dict[str, Any]:
    if sha256_bytes(ledger) != spec["file_sha256"]:
        raise ValueError("LEDGER_FILE_SHA256_MISMATCH")
    try:
        lines = ledger.decode("utf-8").splitlines()
    except Exception as e:
        raise ValueError("LEDGER_UTF8_INVALID") from e
    if len(lines) != spec["records"]:
        raise ValueError("LEDGER_RECORD_COUNT_MISMATCH")
    prev = None
    refs: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except Exception as e:
            raise ValueError(f"LEDGER_JSON_INVALID:{i}") from e
        if set(row) != {"payload", "sha256"}:
            raise ValueError(f"LEDGER_FIELDS_INVALID:{i}")
        payload = row["payload"]
        if payload.get("seq") != i:
            raise ValueError(f"LEDGER_SEQUENCE_INVALID:{i}")
        if payload.get("previous") != prev:
            raise ValueError(f"LEDGER_PREVIOUS_INVALID:{i}")
        want = sha256_bytes(canonical_bytes(payload))
        if row["sha256"] != want:
            raise ValueError(f"LEDGER_RECORD_HASH_MISMATCH:{i}")
        event = payload.get("event")
        if not isinstance(event, dict):
            raise ValueError(f"LEDGER_EVENT_INVALID:{i}")
        path = event.get("path")
        blob = event.get("git_blob_sha1") or event.get("artifact_blob_sha1")
        if path is not None or blob is not None:
            if not isinstance(path, str) or not path or not isinstance(blob, str) or len(blob) != 40:
                raise ValueError(f"LEDGER_REFERENCE_INVALID:{i}")
            if path in seen_paths:
                raise ValueError(f"LEDGER_DUPLICATE_REFERENCE:{i}")
            seen_paths.add(path)
            refs.append((path, blob))
        prev = row["sha256"]
    if prev != spec["head_sha256"]:
        raise ValueError("LEDGER_HEAD_MISMATCH")
    return {"records": len(lines), "head_sha256": prev, "references": refs}

def _verify_blob(root: Path, rel: str, expected: str) -> bytes:
    if not isinstance(expected, str) or len(expected) != 40:
        raise ValueError("GIT_BLOB_EXPECTATION_INVALID:" + rel)
    data = _read(root, rel)
    got = git_blob_sha1(data)
    if got != expected:
        raise ValueError("GIT_BLOB_MISMATCH:" + rel)
    return data

def _add_expected(expected: dict[str, str], rel: str, blob: str, label: str) -> None:
    _resolve_under(Path("."), rel)
    if not isinstance(blob, str) or len(blob) != 40:
        raise ValueError(label + "_BLOB_INVALID:" + rel)
    if rel in expected and expected[rel] != blob:
        raise ValueError("CONFLICTING_BLOB_EXPECTATION:" + rel)
    expected[rel] = blob

def verify_recovery_root(snapshot_root: str | Path, recovery_root_path: str | Path) -> dict[str, Any]:
    snapshot = Path(snapshot_root)
    root_bytes = _read(snapshot, recovery_root_path)
    root = _json_bytes(root_bytes, "RECOVERY_ROOT")
    if root.get("schema") != ROOT_SCHEMA:
        raise ValueError("RECOVERY_ROOT_SCHEMA_INVALID")
    if root.get("status") != "VERIFIED_RECOVERY_ROOT":
        raise ValueError("RECOVERY_ROOT_STATUS_INVALID")
    clean = {k: v for k, v in root.items() if k != "recovery_root_sha256"}
    want_root = sha256_bytes(canonical_bytes(clean))
    if root.get("recovery_root_sha256") != want_root:
        raise ValueError("RECOVERY_ROOT_SELF_HASH_MISMATCH")

    ledger_spec = root.get("event_ledger")
    if not isinstance(ledger_spec, dict):
        raise ValueError("LEDGER_SPEC_MISSING")
    ledger = _read(snapshot, ledger_spec["path"])
    led = verify_ledger(ledger, ledger_spec)

    expected: dict[str, str] = {}
    for row in root.get("reusable_evidence_set", []):
        p, b = row.get("path"), row.get("git_blob_sha1")
        if not isinstance(p, str) or not isinstance(b, str):
            raise ValueError("REUSABLE_EVIDENCE_ROW_INVALID")
        _add_expected(expected, p, b, "REUSABLE_EVIDENCE")
    for p, b in led["references"]:
        _add_expected(expected, p, b, "LEDGER")

    auth = root.get("authority_vector", {})
    code = auth.get("CODE_AUTHORITY", {})
    for name, rel in CODE_PATHS.items():
        if name in code:
            _add_expected(expected, rel, code[name], "CODE_AUTHORITY")
    op = auth.get("OPERATIONAL_AUTHORITY", {})
    if "handoff_git_blob_sha1" in op:
        _add_expected(expected, HANDOFF_PATH, op["handoff_git_blob_sha1"], "HANDOFF")
    if "seed0076_pointer_git_blob_sha1" in op:
        _add_expected(expected, POINTER_PATH, op["seed0076_pointer_git_blob_sha1"], "POINTER")

    verified_receipts = 0
    for rel, blob in sorted(expected.items()):
        data = _verify_blob(snapshot, rel, blob)
        if rel.endswith(".json") and verify_receipt_bytes(data, rel):
            verified_receipts += 1

    pointer = _json_bytes(_read(snapshot, POINTER_PATH), "POINTER")
    handoff = _json_bytes(_read(snapshot, HANDOFF_PATH), "HANDOFF")
    anchor = root["verified_recovery_root"]["scientific_anchor"]
    if pointer.get("current_version") != anchor.get("stable_frontier"):
        raise ValueError("STALE_POINTER_VERSION")
    if pointer.get("target_git_blob_sha1") != anchor.get("target_git_blob_sha1"):
        raise ValueError("STALE_POINTER_TARGET_BLOB")
    target_path = pointer.get("target_path")
    if not isinstance(target_path, str) or not target_path:
        raise ValueError("POINTER_TARGET_PATH_INVALID")
    target_raw = _read(snapshot, target_path)
    if git_blob_sha1(target_raw) != anchor["target_git_blob_sha1"]:
        raise ValueError("POINTER_TARGET_CONTENT_MISMATCH")
    target = _json_bytes(target_raw, "TARGET")

    if handoff.get("stable_frontier_version") != anchor.get("stable_frontier"):
        raise ValueError("HANDOFF_FRONTIER_SPLIT")
    if handoff.get("stable_frontier_target_git_blob_sha1") != anchor.get("target_git_blob_sha1"):
        raise ValueError("HANDOFF_TARGET_SPLIT")

    sci = auth.get("SCIENTIFIC_AUTHORITY", {})
    if root.get("scientific_state") != sci.get("scientific_state"):
        raise ValueError("SCIENTIFIC_STATE_SPLIT")
    if target.get("scientific_state") != sci.get("scientific_state"):
        raise ValueError("TARGET_SCIENTIFIC_STATE_SPLIT")
    flags = ("shard11_open", "economic_pnl_read", "ga2_open", "holdout_open")
    for flag in flags:
        if sci.get(flag) is not False or target.get(flag) is not False:
            raise ValueError("SCIENTIFIC_FIREWALL_NOT_CLOSED:" + flag)
    counts = target.get("verified_counts", {})
    if counts.get("ga1_formally_completed_shards") != sci.get("ga1_completed"):
        raise ValueError("GA1_COMPLETED_COUNT_SPLIT")
    if counts.get("shards_total") != sci.get("ga1_total"):
        raise ValueError("GA1_TOTAL_COUNT_SPLIT")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "recovery_root_sha256": want_root,
        "ledger_records": led["records"],
        "ledger_head_sha256": led["head_sha256"],
        "referenced_artifacts_verified": len(expected),
        "receipt_self_hashes_verified": verified_receipts,
        "stable_frontier": anchor["stable_frontier"],
        "scientific_state": root["scientific_state"],
        "shard11_open": False,
    }
