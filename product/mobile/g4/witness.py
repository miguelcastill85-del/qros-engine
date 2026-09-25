"""G4 independently testable *local* external-witness prototype.

Writer is a separate process/trust store from the research worker in CI. No production
immutable cloud custody, hard hardware key, TLS or tenant auth is claimed here.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from data_audit import exact, strict_json, ident, hex64, canonical, digest, deny, _instant, AuditReject

ZERO = "0" * 64
ENVELOPE = {"body", "signature_b64"}
BODY = {"schema", "witness_id", "sequence", "previous_sha256", "tenant", "campaign",
        "subject_sha256", "created_utc", "classification"}

@dataclass(frozen=True)
class Head:
    sequence: int
    sha256: str

GENESIS = Head(0, ZERO)

class WitnessVerifier:
    def __init__(self, public_key: bytes, witness_id: str):
        if type(public_key) is not bytes or len(public_key) != 32:
            deny("WITNESS_TRUST_ROOT_NOT_PINNED")
        self.key = Ed25519PublicKey.from_public_bytes(public_key)
        self.public_key = public_key
        self.witness_id = ident(witness_id, "WITNESS")

    def verify_step(self, envelope: Any, *, prior: Head,
                    tenant: str, campaign: str, minimum_time: str | None = None) -> Head:
        exact(envelope, ENVELOPE, "WITNESS_ENVELOPE")
        body = exact(envelope["body"], BODY, "WITNESS_BODY")
        if body["schema"] != "QROS_G4_WITNESS_TEST_V1" or body["classification"] != "TEST_ONLY_SYNTHETIC":
            deny("UNTRUSTED_WITNESS_SCHEMA")
        if body["witness_id"] != self.witness_id:
            deny("WITNESS_ID_MISMATCH")
        if body["tenant"] != ident(tenant, "EXPECTED_TENANT") or body["campaign"] != ident(campaign, "EXPECTED_CAMPAIGN"):
            deny("CROSS_TENANT_OR_CAMPAIGN")
        if type(body["sequence"]) is not int or body["sequence"] != prior.sequence + 1:
            deny("SEQUENCE_REPLAY_OR_FORK")
        if body["previous_sha256"] != hex64(prior.sha256, "PRIOR"):
            deny("PREVIOUS_HEAD_MISMATCH")
        hex64(body["subject_sha256"], "SUBJECT")
        stamp = _instant(body["created_utc"])
        if minimum_time is not None and stamp < _instant(minimum_time):
            deny("WITNESS_TIMESTAMP_ROLLBACK")
        try:
            sig = base64.b64decode(envelope["signature_b64"], validate=True)
            if len(sig) != 64:
                deny("WITNESS_SIGNATURE_LENGTH")
            self.key.verify(sig, canonical(body))
        except (ValueError, InvalidSignature, TypeError):
            deny("WITNESS_SIGNATURE_INVALID")
        return Head(body["sequence"], digest(canonical(body)))

    def verify_known_head(self, envelope: Any, *, known: Head, tenant: str, campaign: str) -> Head:
        """Refuse stale snapshots; require consecutive proof from an externally pinned prior head."""
        return self.verify_step(envelope, prior=known, tenant=tenant, campaign=campaign)

class LocalTestWitnessStore:
    """Separate local process proof of concept; **not** independent commercial custody.

    Global chain enforces strict monotonicity. Expose only scoped proof events, never this
    private multi-tenant log, to customer clients. Do not store the signing key here.
    """
    def __init__(self, directory: Path, signing_key: Ed25519PrivateKey, witness_id: str):
        if directory.is_symlink():
            deny("SYMLINK_WITNESS_DIRECTORY")
        self.root = directory
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.id = ident(witness_id, "WITNESS")
        self.key = signing_key
        self.public_key = signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        self.verifier = WitnessVerifier(self.public_key, witness_id)
        self.log = directory / "witness.jsonl"
        self.lock = directory / "writer.lock"

    def _fd(self, path: Path, *, write: bool) -> int:
        flags = os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        if write:
            flags |= os.O_RDWR | os.O_CREAT
        else:
            flags |= os.O_RDONLY
        try:
            fd = os.open(path, flags, 0o600)
            if not os.path.isfile(path) or os.fstat(fd).st_nlink != 1:
                os.close(fd)
                deny("LINKED_OR_NONREGULAR_WITNESS_FILE")
            return fd
        except (OSError, ValueError):
            deny("WITNESS_FILE_ACCESS_FAIL_CLOSED")

    def _inspect_unlocked(self) -> tuple[Head, list[dict[str, Any]]]:
        if not self.log.exists() and not self.log.is_symlink():
            return GENESIS, []
        fd = self._fd(self.log, write=False)
        try:
            size = os.fstat(fd).st_size
            if size > 4_000_000:
                deny("WITNESS_LOG_SIZE")
            with os.fdopen(fd, "rb", closefd=False) as f:
                contents = f.read()
        finally:
            os.close(fd)
        if contents and not contents.endswith(b"\n"):
            deny("TRUNCATED_WITNESS_LOG")
        result: list[dict[str, Any]] = []
        head = GENESIS
        min_date: str | None = None
        for line in contents.splitlines():
            event = strict_json(line, max_size=8192)
            body = event.get("body") if type(event) is dict else None
            if type(body) is not dict:
                deny("CORRUPT_WITNESS_LOG")
            head = self.verifier.verify_step(event, prior=head,
                                             tenant=body.get("tenant"), campaign=body.get("campaign"),
                                             minimum_time=min_date)
            min_date = body["created_utc"]
            result.append(event)
        return head, result

    def inspect(self) -> Head:
        fd = self._fd(self.lock, write=True)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            return self._inspect_unlocked()[0]
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def append(self, *, prior: Head, tenant: str, campaign: str,
               subject_sha256: str, created_utc: str,
               audit_receipt: dict[str, Any] | None = None) -> tuple[Head, dict[str, Any]]:
        ident(tenant, "TENANT")
        ident(campaign, "CAMPAIGN")
        hex64(subject_sha256, "SUBJECT")
        _instant(created_utc)
        if audit_receipt is not None:
            if audit_receipt.get("schema") != "QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1" or \
               audit_receipt.get("tenant") != tenant or \
               audit_receipt.get("execution_eligible") is not True or \
               digest(canonical(audit_receipt)) != subject_sha256:
                deny("UNVERIFIED_OR_QUARANTINED_AUDIT_ANCHOR")
        fd = self._fd(self.lock, write=True)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            current, records = self._inspect_unlocked()
            if current != prior:
                deny("EXTERNAL_WITNESS_CAS_CONFLICT")
            if records and _instant(created_utc) < _instant(records[-1]["body"]["created_utc"]):
                deny("WITNESS_TIMESTAMP_ROLLBACK")
            body = {"schema": "QROS_G4_WITNESS_TEST_V1", "witness_id": self.id,
                    "sequence": current.sequence + 1, "previous_sha256": current.sha256,
                    "tenant": tenant, "campaign": campaign, "subject_sha256": subject_sha256,
                    "created_utc": created_utc, "classification": "TEST_ONLY_SYNTHETIC"}
            sig = self.key.sign(canonical(body))
            event = {"body": body, "signature_b64": base64.b64encode(sig).decode("ascii")}
            payload = canonical(event) + b"\n"
            logfd = self._fd(self.log, write=True)
            try:
                os.lseek(logfd, 0, os.SEEK_END)
                written = 0
                while written < len(payload):
                    n = os.write(logfd, payload[written:])
                    if n <= 0:
                        deny("WITNESS_SHORT_WRITE")
                    written += n
                os.fsync(logfd)
            finally:
                os.close(logfd)
            if os.environ.get("QROS_G4_TEST_KILL_AFTER_FSYNC") == "1":
                os._exit(83)  # Real process crash canary; never use in production.
            dirfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
            result = self.verifier.verify_step(event, prior=current, tenant=tenant, campaign=campaign)
            if result != self._inspect_unlocked()[0]:
                deny("WITNESS_POST_WRITE_READBACK")
            return result, event
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
