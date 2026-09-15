#!/usr/bin/env python3
"""Fail-closed validator for the V252 FIRST_GATE scorer build capsule.

Non-economic by construction: verifies exact repository bytes and structured
state only. It never reads PnL, mask economic outputs, holdout, or GA2 data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class CapsuleValidationError(RuntimeError):
    pass


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def read_bytes(root: Path, rel: str) -> bytes:
    p = root / rel
    if not p.is_file():
        raise CapsuleValidationError(f"MISSING_FILE:{rel}")
    return p.read_bytes()


def read_json(root: Path, rel: str) -> dict[str, Any]:
    try:
        return json.loads(read_bytes(root, rel).decode("utf-8"))
    except CapsuleValidationError:
        raise
    except Exception as exc:
        raise CapsuleValidationError(f"INVALID_JSON:{rel}:{type(exc).__name__}") from exc


def verify_blob(root: Path, rel: str, expected: str) -> str:
    actual = git_blob_sha1(read_bytes(root, rel))
    if actual != expected:
        raise CapsuleValidationError(f"BLOB_MISMATCH:{rel}:{expected}:{actual}")
    return actual


def eq(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise CapsuleValidationError(f"VALUE_MISMATCH:{label}:{expected!r}:{actual!r}")


def validate(root: Path, capsule_rel: str) -> dict[str, Any]:
    cap_bytes = read_bytes(root, capsule_rel)
    try:
        cap = json.loads(cap_bytes.decode("utf-8"))
    except Exception as exc:
        raise CapsuleValidationError(f"INVALID_CAPSULE_JSON:{type(exc).__name__}") from exc

    eq("schema", cap.get("schema"), "QROS_PUBLIC1000_EXECUTION_CAPSULE_1.0")
    eq("campaign", cap.get("campaign"), "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA")

    deps = cap.get("direct_dependencies")
    if not isinstance(deps, list) or len(deps) != 24:
        raise CapsuleValidationError("DEPENDENCY_COUNT_NOT_24")
    roles = [d.get("role") for d in deps]
    paths = [d.get("path") for d in deps]
    if len(set(roles)) != 24 or len(set(paths)) != 24:
        raise CapsuleValidationError("DEPENDENCY_DUPLICATE_ROLE_OR_PATH")
    dep_by_role: dict[str, dict[str, str]] = {}
    for d in deps:
        role, path, sha = d.get("role"), d.get("path"), d.get("git_blob_sha1")
        if not all(isinstance(x, str) and x for x in (role, path, sha)):
            raise CapsuleValidationError("INVALID_DEPENDENCY_ROW")
        verify_blob(root, path, sha)
        dep_by_role[role] = d

    auth = cap["authority"]
    chat_bind = auth["current_chat_handoff_pointer"]
    handoff_bind = auth["handoff"]
    stable_bind = auth["stable_scientific_pointer"]
    target_bind = auth["stable_target"]
    for b in (chat_bind, handoff_bind, stable_bind, target_bind):
        verify_blob(root, b["path"], b["git_blob_sha1"])

    chat = read_json(root, chat_bind["path"])
    eq("chat.status", chat.get("status"), "ACTIVE_AUDITED")
    eq("chat.handoff_path", chat.get("handoff_path"), handoff_bind["path"])
    eq("chat.handoff_sha", chat.get("handoff_git_blob_sha1"), handoff_bind["git_blob_sha1"])
    eq("chat.audit", chat.get("active_external_audit_status"), "PASS")
    eq("chat.stable_path", chat["stable_scientific_pointer"].get("path"), stable_bind["path"])
    eq("chat.stable_sha", chat["stable_scientific_pointer"].get("expected_git_blob_sha1"), stable_bind["git_blob_sha1"])
    eq("chat.stable_version", chat["stable_scientific_pointer"].get("expected_version"), stable_bind["version"])

    stable = read_json(root, stable_bind["path"])
    eq("stable.version", stable.get("current_version"), "V252")
    eq("stable.target_path", stable.get("target_path"), target_bind["path"])
    eq("stable.target_sha", stable.get("target_git_blob_sha1"), target_bind["git_blob_sha1"])
    eq("stable.state", stable.get("state"), "DEVELOPMENT_RUNNING")
    eq("stable.scientific_state", stable.get("scientific_state"), "PREREGISTERED_NO_RESULTS")

    ticket = cap["machine_ticket"]
    eq("ticket.id", stable.get("machine_action_ticket_id"), ticket["ticket_id"])
    eq("ticket.action", stable.get("machine_action_type"), ticket["action"])
    eq("ticket.state", stable.get("machine_state_id"), ticket["state_id"])
    eq("ticket.guard", stable.get("machine_guard_profile"), ticket["guard_profile"])
    eq("ticket.subject", stable.get("machine_subject"), ticket["subject"])
    eq("stable.scope", stable.get("authorized_action_scope"), "MACHINE_ACTION_TICKET_ONLY")
    eq("stable.execution_latch", stable.get("scientific_execution_authorized"), True)
    eq("stable.first_gate_execution_authorized", stable.get("first_gate_execution_authorized"), False)
    eq("stable.first_gate_scorer_status", stable.get("first_gate_scorer_status"), "NOT_BUILT")
    for k in ("economic_pnl_read", "holdout_open", "ga2_open", "new_ga1_authorized"):
        eq(f"stable.{k}", stable.get(k), False)

    ledger = read_json(root, dep_by_role["promotion_ledger"]["path"])
    for k in ("economic_pnl_read", "holdout_open", "ga2_open", "new_ga1_authorized"):
        eq(f"ledger.{k}", ledger.get(k), False)
    eq("ledger.order", ledger.get("current_first_gate_order"), 1)
    eq("ledger.shard", ledger.get("current_first_gate_shard_id"), ticket["subject"]["shard_id"])
    eq("ledger.domain", ledger.get("current_first_gate_domain"), {
        "asset": ticket["subject"]["asset"], "side": ticket["subject"]["side"], "timeframe": ticket["subject"]["timeframe"]
    })
    fifo = [r for r in ledger.get("completed_and_promoted_shards", []) if r.get("first_gate_order") == 1]
    if len(fifo) != 1:
        raise CapsuleValidationError("FIFO1_CARDINALITY_NOT_1")
    eq("fifo.status", fifo[0].get("first_gate_status"), "PENDING")
    eq("fifo.executed", fifo[0].get("economic_scoring_executed"), False)

    success = cap["success_transition"]
    eq("transition.from", success.get("from_state"), "FG_SCORER_NOT_BUILT")
    eq("transition.to", success.get("to_state"), "FG_SCORER_PRIMARY_BUILT")
    eq("transition.next", success.get("next_action"), "VERIFY_FIRST_GATE_SCORER_WITH_INDEPENDENT_ORACLE")
    for k in ("economic_pnl_read", "ga2_open", "holdout_open", "new_ga1_authorized"):
        eq(f"transition.{k}", success.get(k), False)

    expected_forbidden = {
        "READ_ECONOMIC_PNL", "OPEN_GA2", "OPEN_HOLDOUT", "EXECUTE_FIRST_GATE",
        "START_NEW_GA1", "RECOMPUTE_COMPLETED_GA1", "CHANGE_FIFO", "CHANGE_MULTIPLICITY",
        "CHANGE_FROZEN_UNIVERSE", "REPOSITORY_WIDE_EXPLORATORY_DEPENDENCY_SEARCH",
    }
    if set(cap.get("forbidden_actions", [])) != expected_forbidden:
        raise CapsuleValidationError("FORBIDDEN_ACTION_SET_MISMATCH")

    return {
        "schema": "QROS_EXECUTION_CAPSULE_VALIDATION_RESULT_1.0",
        "status": "PASS",
        "capsule_path": capsule_rel,
        "capsule_git_blob_sha1": git_blob_sha1(cap_bytes),
        "verified_dependency_count": 24,
        "ticket_id": ticket["ticket_id"],
        "machine_action": ticket["action"],
        "subject": ticket["subject"],
        "economic_pnl_read": False,
        "ga2_open": False,
        "holdout_open": False,
        "new_ga1_authorized": False,
        "next_state": success["to_state"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capsule", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    try:
        out = validate(Path(a.root).resolve(), a.capsule)
    except CapsuleValidationError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
