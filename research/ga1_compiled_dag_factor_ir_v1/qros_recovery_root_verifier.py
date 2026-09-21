from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT_SCHEMA = "QROS_GA1_EVIDENCE_NATIVE_RECOVERY_ROOT_1.0"

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def git_blob_sha1(b: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(b)).encode("ascii") + b"\0" + b).hexdigest()

def _safe_path(repo_root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or "\\" in rel:
        raise ValueError("ARTIFACT_PATH_INVALID")
    p = Path(rel)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise ValueError("ARTIFACT_PATH_INVALID")
    base = repo_root.resolve()
    full = (base / p).resolve()
    if full != base and base not in full.parents:
        raise ValueError("ARTIFACT_PATH_TRAVERSAL")
    return full

def _verify_receipt_if_json(path: Path, raw: bytes) -> None:
    if path.suffix != ".json":
        return
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError("JSON_ARTIFACT_INVALID:" + str(path)) from e
    if isinstance(obj, dict) and "receipt_sha256" in obj:
        claimed = obj["receipt_sha256"]
        clean = {k: v for k, v in obj.items() if k != "receipt_sha256"}
        calc = sha256_bytes(canonical_bytes(clean))
        if claimed != calc:
            raise ValueError("RECEIPT_SELF_HASH_MISMATCH:" + str(path))

def _verify_artifact(repo_root: Path, ref: dict[str, Any]) -> None:
    rel = ref.get("path")
    expected = ref.get("git_blob_sha1") or ref.get("artifact_blob_sha1")
    if not isinstance(expected, str) or len(expected) != 40:
        raise ValueError("ARTIFACT_BLOB_SHA1_INVALID")
    path = _safe_path(repo_root, rel)
    if not path.is_file():
        raise ValueError("ARTIFACT_MISSING:" + rel)
    raw = path.read_bytes()
    if git_blob_sha1(raw) != expected:
        raise ValueError("ARTIFACT_BLOB_SHA1_MISMATCH:" + rel)
    _verify_receipt_if_json(path, raw)

def verify_ledger(repo_root: Path, ledger_rel: str, expected_file_sha256: str,
                  expected_head: str, expected_records: int) -> dict[str, Any]:
    path = _safe_path(repo_root, ledger_rel)
    if not path.is_file():
        raise ValueError("LEDGER_MISSING")
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_file_sha256:
        raise ValueError("LEDGER_FILE_SHA256_MISMATCH")
    try:
        text = raw.decode("utf-8")
    except Exception as e:
        raise ValueError("LEDGER_UTF8_INVALID") from e
    lines = text.splitlines()
    if len(lines) != expected_records:
        raise ValueError("LEDGER_RECORD_COUNT_MISMATCH")
    prev = None
    seen_paths = set()
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except Exception as e:
            raise ValueError(f"LEDGER_JSON_INVALID:{i}") from e
        if set(row) != {"payload", "sha256"}:
            raise ValueError(f"LEDGER_ROW_FIELDS_INVALID:{i}")
        payload = row["payload"]
        if payload.get("seq") != i:
            raise ValueError(f"LEDGER_SEQ_INVALID:{i}")
        if payload.get("previous") != prev:
            raise ValueError(f"LEDGER_CHAIN_PREVIOUS_MISMATCH:{i}")
        calc = sha256_bytes(canonical_bytes(payload))
        if row["sha256"] != calc:
            raise ValueError(f"LEDGER_ROW_SHA256_MISMATCH:{i}")
        event = payload.get("event")
        if not isinstance(event, dict):
            raise ValueError(f"LEDGER_EVENT_INVALID:{i}")
        rel = event.get("path")
        if rel in seen_paths:
            raise ValueError(f"LEDGER_DUPLICATE_ARTIFACT_PATH:{i}")
        seen_paths.add(rel)
        _verify_artifact(repo_root, event)
        prev = row["sha256"]
    if prev != expected_head:
        raise ValueError("LEDGER_HEAD_MISMATCH")
    return {"records": len(lines), "head_sha256": prev, "file_sha256": expected_file_sha256}

def verify_recovery_root(repo_root: str | Path, root_rel: str) -> dict[str, Any]:
    repo_root = Path(repo_root)
    root_path = _safe_path(repo_root, root_rel)
    raw = root_path.read_bytes()
    try:
        root = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError("RECOVERY_ROOT_JSON_INVALID") from e
    if root.get("schema") != ROOT_SCHEMA:
        raise ValueError("RECOVERY_ROOT_SCHEMA_MISMATCH")
    if root.get("status") != "VERIFIED_RECOVERY_ROOT":
        raise ValueError("RECOVERY_ROOT_STATUS_INVALID")
    claimed = root.get("recovery_root_sha256")
    clean = {k: v for k, v in root.items() if k != "recovery_root_sha256"}
    calc = sha256_bytes(canonical_bytes(clean))
    if claimed != calc:
        raise ValueError("RECOVERY_ROOT_SELF_HASH_MISMATCH")
    ledger = root.get("event_ledger")
    if not isinstance(ledger, dict):
        raise ValueError("RECOVERY_ROOT_LEDGER_INVALID")
    ledger_result = verify_ledger(
        repo_root,
        ledger["path"],
        ledger["file_sha256"],
        ledger["head_sha256"],
        int(ledger["records"]),
    )
    reusable = root.get("reusable_evidence_set")
    if not isinstance(reusable, list):
        raise ValueError("REUSABLE_EVIDENCE_SET_INVALID")
    for ref in reusable:
        if not isinstance(ref, dict):
            raise ValueError("REUSABLE_EVIDENCE_REF_INVALID")
        _verify_artifact(repo_root, ref)
    return {
        "status": "PASS",
        "recovery_root_sha256": claimed,
        "ledger": ledger_result,
        "reusable_artifacts_verified": len(reusable),
    }
