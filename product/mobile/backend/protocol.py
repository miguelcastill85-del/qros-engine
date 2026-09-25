"""Verify offline signed synthetic demo receipts and independent witness anchor.

TEST_ONLY: no real research states, financial metrics, broker input, or production
credential storage. Two different Ed25519 public keys; neither private key is
stored here. Trust root SHA-256 must be provided out of band by deployer.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_JSON_BYTES = 65536
HEX64 = re.compile(r"^[0-9a-f]{64}$")
B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


class EvidenceRejected(ValueError):
    """Fail-closed invalid, stale, mismatched, or tampered evidence."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceRejected(code)


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise EvidenceRejected("INVALID_CANONICAL_JSON") from exc


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def checked_hex(value: Any) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, "INVALID_HEX_DIGEST")
    return value


def checked_json(raw: bytes) -> Any:
    require(0 < len(raw) <= MAX_JSON_BYTES, "BAD_JSON_SIZE")
    def no_duplicates(pairs):
        o = {}
        for k, v in pairs:
            if k in o:
                raise ValueError("duplicate JSON key")
            o[k] = v
        return o
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nan")))
    except (UnicodeDecodeError, ValueError) as exc:
        raise EvidenceRejected("INVALID_JSON") from exc
    return obj


def exact_keys(value: Any, expected: set[str], code: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == expected, code)
    return value


def valid_base64(value: Any, size: int, code: str) -> bytes:
    require(isinstance(value, str) and B64.fullmatch(value) is not None, code)
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EvidenceRejected(code) from exc
    require(len(result) == size, code)
    return result


@dataclass(frozen=True)
class TrustRoot:
    anchor_sha256: str
    witness_public_key: bytes
    receipt_public_key: bytes
    project_id: str
    source_pin_sha256: str

    @classmethod
    def parse(cls, raw: bytes, out_of_band_sha256: str) -> "TrustRoot":
        require(sha256(raw) == checked_hex(out_of_band_sha256), "UNTRUSTED_TRUST_ROOT_BYTES")
        o = exact_keys(checked_json(raw), {"schema", "anchor_sha256", "witness_public_key_b64",
                                         "receipt_public_key_b64", "project_id", "source_pin_sha256"},
                       "TRUST_ROOT_SCHEMA")
        require(o["schema"] == "QROS_MOBILE_TRUST_ROOT_TEST_V1", "TRUST_ROOT_SCHEMA")
        require(o["project_id"] == "DEMO-001", "UNEXPECTED_DEMO_PROJECT")
        witness = valid_base64(o["witness_public_key_b64"], 32, "BAD_WITNESS_KEY")
        receipt = valid_base64(o["receipt_public_key_b64"], 32, "BAD_RECEIPT_KEY")
        require(witness != receipt, "SIGNING_KEY_SEPARATION_REQUIRED")
        return cls(checked_hex(o["anchor_sha256"]), witness, receipt, o["project_id"],
                   checked_hex(o["source_pin_sha256"]))


def verify_signed(envelope: Any, public_key: bytes, expected_schema: str) -> dict[str, Any]:
    env = exact_keys(envelope, {"body", "signature_b64"}, "SIGNED_ENVELOPE_SCHEMA")
    body = env["body"]
    require(isinstance(body, dict) and body.get("schema") == expected_schema, "SIGNED_BODY_SCHEMA")
    signature = valid_base64(env["signature_b64"], 64, "BAD_SIGNATURE_ENCODING")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical(body))
    except InvalidSignature as exc:
        raise EvidenceRejected("SIGNATURE_INVALID") from exc
    return body


@dataclass(frozen=True)
class VerifiedSnapshot:
    anchor_sha256: str
    anchor_sequence: int
    project: dict[str, str]
    response: dict[str, Any]


def verify_snapshot(bundle: Any, trust: TrustRoot) -> VerifiedSnapshot:
    b = exact_keys(bundle, {"schema", "mode", "anchor", "receipt", "scientific_authority"},
                   "SNAPSHOT_SCHEMA")
    require(b["schema"] == "QROS_MOBILE_SIGNED_TEST_ONLY_V1" and
            b["mode"] == "TEST_ONLY_SYNTHETIC" and b["scientific_authority"] == "NONE",
            "NOT_SYNTHETIC_SAMPLE")
    anchor = verify_signed(b["anchor"], trust.witness_public_key, "QROS_M2_WITNESS_ANCHOR_TEST_V1")
    exact_keys(anchor, {"schema", "sequence", "digest", "previous_digest", "project_id",
                        "source_class", "source_pin_sha256"}, "ANCHOR_SCHEMA")
    require(type(anchor["sequence"]) is int and anchor["sequence"] >= 1, "BAD_ANCHOR_SEQUENCE")
    checked_hex(anchor["digest"])
    checked_hex(anchor["previous_digest"])
    require(anchor["digest"] != anchor["previous_digest"], "BAD_ANCHOR_CHAIN")
    require(anchor["project_id"] == trust.project_id and
            anchor["source_class"] == "TEST_ONLY_SYNTHETIC" and
            anchor["source_pin_sha256"] == trust.source_pin_sha256, "ANCHOR_AUTHORITY_MISMATCH")
    digest = sha256(canonical(anchor))
    require(digest == trust.anchor_sha256, "EXTERNAL_HEAD_ANCHOR_MISMATCH")
    receipt = verify_signed(b["receipt"], trust.receipt_public_key,
                            "QROS_MOBILE_RECEIPT_TEST_V1")
    exact_keys(receipt, {"schema", "project_id", "source_class", "scientific_state",
                         "scientific_approval", "holdout_open", "ga2_open", "mt5_executed",
                         "anchor_sha256", "anchor_sequence", "source_pin_sha256", "project"},
               "RECEIPT_SCHEMA")
    require(receipt["anchor_sha256"] == digest and receipt["anchor_sequence"] == anchor["sequence"] and
            receipt["project_id"] == trust.project_id and
            receipt["source_pin_sha256"] == trust.source_pin_sha256,
            "RECEIPT_ANCHOR_MISMATCH")
    require(receipt["source_class"] == "TEST_ONLY_SYNTHETIC" and
            receipt["scientific_state"] == "SIMULATED_SAMPLE" and
            receipt["scientific_approval"] is False and
            receipt["holdout_open"] is False and receipt["ga2_open"] is False and
            receipt["mt5_executed"] is False, "FORBIDDEN_SCIENTIFIC_PROMOTION")
    project = exact_keys(receipt["project"], {"id", "title", "symbol", "side", "timeframe", "classification"},
                         "PROJECT_SCHEMA")
    require(project == {"id": "DEMO-001", "title": "Ruptura y recuperacion DEMO",
                        "symbol": "XAUUSD", "side": "BUY", "timeframe": "M15",
                        "classification": "TEST_ONLY_SYNTHETIC"}, "NOT_FROZEN_DEMO_FIXTURE")
    return VerifiedSnapshot(anchor_sha256=digest, anchor_sequence=anchor["sequence"],
                            project=project, response=b)


def load_verified_snapshot(trust_path: Path, trust_sha256: str, snapshot_path: Path) -> VerifiedSnapshot:
    # Only read files, never follow symlinks; deployment must mount trust root from
    # an independently controlled read-only path and pin its bytes out of band.
    for p in (trust_path, snapshot_path):
        require(p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_JSON_BYTES,
                "UNSAFE_OR_OVERSIZED_SOURCE_FILE")
    trust = TrustRoot.parse(trust_path.read_bytes(), trust_sha256)
    return verify_snapshot(checked_json(snapshot_path.read_bytes()), trust)
