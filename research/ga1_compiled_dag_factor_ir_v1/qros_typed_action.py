from __future__ import annotations
import hashlib, json, platform, sys
from pathlib import Path
from typing import Any
import numpy as np
from qros_factor_ir_store import immutable_publish_bytes

SCHEMA = "QROS_TYPED_ACTION_KEY_1.0"


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def environment_manifest(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import numba
        numba_version = numba.__version__
    except Exception:
        numba_version = None
    out = {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "numba": numba_version,
        "byteorder": sys.byteorder,
    }
    if extra:
        out["extra"] = extra
    return out


def build_action_payload(*, operation: str, operation_version: str,
                         code_hashes: dict[str, str], domain: dict[str, Any],
                         parameters: dict[str, Any], input_artifacts: dict[str, str],
                         environment: dict[str, Any]) -> dict[str, Any]:
    if not operation or not operation_version:
        raise ValueError("OPERATION_ID_REQUIRED")
    for label, mapping in (("code_hashes", code_hashes), ("input_artifacts", input_artifacts)):
        if not mapping:
            raise ValueError(f"{label.upper()}_REQUIRED")
        for k, v in mapping.items():
            if not isinstance(k, str) or not k or not isinstance(v, str) or len(v) != 64:
                raise ValueError(f"INVALID_{label.upper()}:{k}")
            int(v, 16)
    return {
        "schema": SCHEMA,
        "operation": operation,
        "operation_version": operation_version,
        "code_hashes": dict(sorted(code_hashes.items())),
        "domain": domain,
        "parameters": parameters,
        "input_artifacts": dict(sorted(input_artifacts.items())),
        "environment": environment,
    }


def action_key(**kwargs: Any) -> tuple[str, dict[str, Any]]:
    payload = build_action_payload(**kwargs)
    return sha256_bytes(canonical_bytes(payload)), payload


def receipt_self_hash(receipt: dict[str, Any]) -> str:
    clean = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    return sha256_bytes(canonical_bytes(clean))


def validate_receipt(receipt: dict[str, Any], *, expected_action_key: str | None = None) -> None:
    got = receipt.get("receipt_sha256")
    if not isinstance(got, str) or got != receipt_self_hash(receipt):
        raise ValueError("RECEIPT_SELF_HASH_MISMATCH")
    if expected_action_key is not None and receipt.get("action_key") != expected_action_key:
        raise ValueError("ACTION_KEY_MISMATCH")


def atomic_publish_bytes(path: str | Path, data: bytes, *, crash_before_rename: bool = False) -> str:
    result = immutable_publish_bytes(path, data, crash_before_publish=crash_before_rename)
    return result["sha256"]
