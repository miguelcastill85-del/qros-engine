#!/usr/bin/env python3
"""Finite, fail-closed GitHub publication state machine for QROS durability.

This module is intentionally GitHub-client agnostic. The orchestration layer performs
remote actions and feeds authenticated observations back as events. The FSM prevents
unbounded re-entry and only reaches CLOSED after exact remote readback.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "QROS_GITHUB_DURABILITY_CLOSURE_FSM_V1"
EVENT_SCHEMA = "QROS_GITHUB_DURABILITY_EVENT_V1"
TERMINAL = {"CLOSED", "CONFLICT", "BLOCKED"}
PHASE_ORDER = {
    "PREPARED": 0,
    "COMMIT_CREATED": 1,
    "REF_PROMOTED": 2,
    "READBACK_VERIFIED": 3,
    "CLOSED": 4,
    "CONFLICT": 99,
    "BLOCKED": 99,
}
DEFAULT_MAX_RETRIES = 3


class TransitionError(ValueError):
    pass


def canonical(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _is_sha40(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _is_sha64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def new_journal(
    operation_id: str,
    expected_parent_sha: str,
    payload_sha256: str,
    required_paths: dict[str, str],
    scientific_authority: dict[str, Any],
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    if not operation_id:
        raise TransitionError("OPERATION_ID_REQUIRED")
    if not _is_sha40(expected_parent_sha):
        raise TransitionError("EXPECTED_PARENT_SHA_INVALID")
    if not _is_sha64(payload_sha256):
        raise TransitionError("PAYLOAD_SHA256_INVALID")
    if not required_paths:
        raise TransitionError("REQUIRED_PATHS_EMPTY")
    for path, blob_sha in required_paths.items():
        if not path or path.startswith("/") or ".." in Path(path).parts:
            raise TransitionError(f"INVALID_REQUIRED_PATH:{path}")
        if not _is_sha40(blob_sha):
            raise TransitionError(f"INVALID_REQUIRED_BLOB_SHA:{path}")
    if max_retries < 0:
        raise TransitionError("MAX_RETRIES_INVALID")
    if not isinstance(scientific_authority, dict) or not scientific_authority:
        raise TransitionError("SCIENTIFIC_AUTHORITY_REQUIRED")

    identity = {
        "operation_id": operation_id,
        "expected_parent_sha": expected_parent_sha,
        "payload_sha256": payload_sha256,
        "required_paths": dict(sorted(required_paths.items())),
        "scientific_authority": copy.deepcopy(scientific_authority),
    }
    return {
        "schema": SCHEMA,
        "identity": identity,
        "identity_sha256": sha256_json(identity),
        "phase": "PREPARED",
        "terminal": False,
        "decision": "CONTINUE",
        "commit_sha": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "last_error": None,
        "history": [],
    }


def _validate_journal(j: dict[str, Any]) -> None:
    if j.get("schema") != SCHEMA:
        raise TransitionError("JOURNAL_SCHEMA_MISMATCH")
    identity = j.get("identity")
    if not isinstance(identity, dict):
        raise TransitionError("IDENTITY_MISSING")
    if j.get("identity_sha256") != sha256_json(identity):
        raise TransitionError("IDENTITY_TAMPERED")
    if j.get("phase") not in PHASE_ORDER:
        raise TransitionError("UNKNOWN_PHASE")
    if bool(j.get("terminal")) != (j.get("phase") in TERMINAL):
        raise TransitionError("TERMINAL_FLAG_INCONSISTENT")


def _event_guard(j: dict[str, Any], event: dict[str, Any]) -> None:
    if event.get("schema") != EVENT_SCHEMA:
        raise TransitionError("EVENT_SCHEMA_MISMATCH")
    if event.get("operation_id") != j["identity"]["operation_id"]:
        raise TransitionError("OPERATION_ID_MISMATCH")
    if event.get("identity_sha256") != j["identity_sha256"]:
        raise TransitionError("IDENTITY_SHA256_MISMATCH")


def _append_history(j: dict[str, Any], event: dict[str, Any], outcome: str) -> None:
    e = copy.deepcopy(event)
    e["outcome"] = outcome
    j["history"].append(e)


def _terminal(j: dict[str, Any], phase: str, decision: str, error: str | None) -> dict[str, Any]:
    j["phase"] = phase
    j["terminal"] = True
    j["decision"] = decision
    j["last_error"] = error
    return j


def advance(journal: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Apply one authenticated observation. Never mutates the input journal."""
    j = copy.deepcopy(journal)
    _validate_journal(j)
    _event_guard(j, event)

    # Terminal states are true fixed points: retries or duplicate delivery cannot reopen them.
    if j["terminal"]:
        _append_history(j, event, "IGNORED_TERMINAL_FIXED_POINT")
        return j

    et = event.get("type")
    phase = j["phase"]

    if et == "RETRYABLE_ERROR":
        j["retry_count"] += 1
        j["last_error"] = str(event.get("error") or "RETRYABLE_ERROR")
        if j["retry_count"] > j["max_retries"]:
            _append_history(j, event, "RETRY_BUDGET_EXHAUSTED")
            return _terminal(j, "BLOCKED", "BLOCKED_RETRY_BUDGET_EXHAUSTED", j["last_error"])
        _append_history(j, event, "RETRY_RECORDED")
        return j

    if et == "PARENT_OBSERVED":
        observed = event.get("observed_head_sha")
        expected = j["identity"]["expected_parent_sha"]
        if observed != expected:
            _append_history(j, event, "STALE_PARENT_CONFLICT")
            return _terminal(j, "CONFLICT", "FAIL_CLOSED_STALE_PARENT", "EXPECTED_PARENT_MISMATCH")
        _append_history(j, event, "PARENT_MATCH")
        return j

    if et == "COMMIT_CREATED":
        if phase != "PREPARED":
            raise TransitionError(f"OUT_OF_ORDER:COMMIT_CREATED:{phase}")
        commit_sha = event.get("commit_sha")
        parent_sha = event.get("parent_sha")
        if not _is_sha40(commit_sha):
            raise TransitionError("COMMIT_SHA_INVALID")
        if parent_sha != j["identity"]["expected_parent_sha"]:
            _append_history(j, event, "COMMIT_PARENT_CONFLICT")
            return _terminal(j, "CONFLICT", "FAIL_CLOSED_COMMIT_PARENT", "COMMIT_PARENT_MISMATCH")
        j["commit_sha"] = commit_sha
        j["phase"] = "COMMIT_CREATED"
        j["decision"] = "CONTINUE"
        j["last_error"] = None
        _append_history(j, event, "ADVANCED")
        return j

    if et == "REF_PROMOTED":
        if phase != "COMMIT_CREATED":
            raise TransitionError(f"OUT_OF_ORDER:REF_PROMOTED:{phase}")
        if event.get("observed_head_sha") != j["commit_sha"]:
            _append_history(j, event, "REF_PROMOTION_CONFLICT")
            return _terminal(j, "CONFLICT", "FAIL_CLOSED_REF_PROMOTION", "HEAD_NOT_COMMIT")
        j["phase"] = "REF_PROMOTED"
        j["decision"] = "CONTINUE"
        _append_history(j, event, "ADVANCED")
        return j

    if et == "READBACK_VERIFIED":
        if phase != "REF_PROMOTED":
            raise TransitionError(f"OUT_OF_ORDER:READBACK_VERIFIED:{phase}")
        if event.get("observed_head_sha") != j["commit_sha"]:
            _append_history(j, event, "READBACK_HEAD_CONFLICT")
            return _terminal(j, "CONFLICT", "FAIL_CLOSED_READBACK_HEAD", "READBACK_HEAD_MISMATCH")
        observed_paths = event.get("observed_paths") or {}
        expected_paths = j["identity"]["required_paths"]
        if observed_paths != expected_paths:
            _append_history(j, event, "READBACK_BYTES_CONFLICT")
            return _terminal(j, "CONFLICT", "FAIL_CLOSED_READBACK_BYTES", "READBACK_PATH_BLOB_MISMATCH")
        j["phase"] = "READBACK_VERIFIED"
        _append_history(j, event, "ADVANCED")
        # Closure is part of the same deterministic transition: no dangling state that can loop.
        j["phase"] = "CLOSED"
        j["terminal"] = True
        j["decision"] = "GITHUB_PUBLICATION_CLOSED"
        j["last_error"] = None
        return j

    raise TransitionError(f"UNKNOWN_EVENT:{et}")


def atomic_write(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = __import__("tempfile").mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(obj))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> None:
    ap = argparse.ArgumentParser(description="QROS finite GitHub durability closure FSM")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init")
    p.add_argument("--operation-id", required=True)
    p.add_argument("--expected-parent-sha", required=True)
    p.add_argument("--payload-sha256", required=True)
    p.add_argument("--required-paths-json", required=True)
    p.add_argument("--scientific-authority-json", required=True)
    p.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    p.add_argument("--out", required=True)

    p = sp.add_parser("advance")
    p.add_argument("--journal", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--out", required=True)

    ns = ap.parse_args()
    if ns.cmd == "init":
        j = new_journal(
            ns.operation_id,
            ns.expected_parent_sha,
            ns.payload_sha256,
            json.loads(ns.required_paths_json),
            json.loads(ns.scientific_authority_json),
            ns.max_retries,
        )
        atomic_write(Path(ns.out), j)
        return

    journal = json.loads(Path(ns.journal).read_text(encoding="utf-8"))
    event = json.loads(Path(ns.event).read_text(encoding="utf-8"))
    out = advance(journal, event)
    atomic_write(Path(ns.out), out)
    raise SystemExit(0 if out["phase"] == "CLOSED" else (2 if out["terminal"] else 3))


if __name__ == "__main__":
    main()
