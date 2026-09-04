#!/usr/bin/env python3
"""Fail-closed state transitions for QROS persistent chat execution.

The controller validates authority, selects dependency-ready work, and produces
deterministic lease/checkpoint state.  Durable promotion is performed by the
companion qros_persistent_git_cas.py transaction or an equivalent Git Data API
compare-and-swap sequence.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
QUEUE_GUARDS = {
    "holdout_open_authorized": False,
    "mt5_authorized": False,
    "live_trading_authorized": False,
    "paid_infrastructure_authorized": False,
    "single_winner_selection": False,
    "all_gate_passers_advance": True,
    "branch_exhaustion_authorized": False,
}
ITEM_STATUSES = {
    "READY", "WAITING_PREREQUISITE", "IN_PROGRESS", "COMPLETED", "BLOCKED", "INVALID"
}
LEASE_FIELDS = {
    "lease_id", "worker_id", "fence_token", "parent_main_sha", "claimed_at",
    "heartbeat_at", "expires_at", "entrypoint_sha256",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("time must include timezone")
    return parsed.astimezone(dt.timezone.utc)


def utc_text(value: dt.datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("time must include timezone")
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def require_git_sha(value: str, name: str) -> None:
    if not SHA_RE.fullmatch(value or ""):
        raise ValueError(f"{name} must be a lowercase 40-character git SHA")


def require_sha256(value: str, name: str) -> None:
    if not SHA256_RE.fullmatch(value or ""):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def validate_lease(lease: dict[str, Any]) -> None:
    missing = LEASE_FIELDS - set(lease)
    if missing:
        raise ValueError(f"lease missing {sorted(missing)}")
    require_git_sha(lease["parent_main_sha"], "lease parent_main_sha")
    require_sha256(lease["entrypoint_sha256"], "lease entrypoint_sha256")
    if not isinstance(lease["fence_token"], int) or lease["fence_token"] < 1:
        raise ValueError("lease fence_token must be a positive integer")
    claimed = parse_time(lease["claimed_at"])
    heartbeat = parse_time(lease["heartbeat_at"])
    expires = parse_time(lease["expires_at"])
    if not claimed <= heartbeat < expires:
        raise ValueError("lease timestamps are inconsistent")


def validate(
    protocol: dict[str, Any],
    queue: dict[str, Any],
    state: dict[str, Any],
    head: dict[str, Any],
    *,
    head_blob_sha: str | None = None,
) -> None:
    if protocol.get("schema") != "QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_V1":
        raise ValueError("unexpected protocol schema")
    if protocol.get("status") != "ADOPTED_MANDATORY_OPERATIONAL_LAYER":
        raise ValueError("protocol is not active")
    if queue.get("schema") != "QROS_PERSISTENT_RUN_QUEUE_V1":
        raise ValueError("unexpected queue schema")
    if state.get("schema") != "QROS_PERSISTENT_EXECUTION_STATE_V1":
        raise ValueError("unexpected state schema")
    if not state.get("enabled"):
        raise ValueError("persistent execution is disabled")
    if state.get("holdout_opened") is not False:
        raise ValueError("state does not preserve sealed holdout")
    automation = state.get("automation", {})
    if automation.get("status") != "ACTIVE" or automation.get("automation_created") is not True:
        raise ValueError("automation is not active")
    if automation.get("paid_infrastructure") is not False:
        raise ValueError("automation permits paid infrastructure")
    if state.get("protocol_ref") != "governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.json":
        raise ValueError("state protocol reference drift")
    if state.get("queue_ref") != "control/persistent_execution/RUN_QUEUE.json":
        raise ValueError("state queue reference drift")

    guards = queue.get("guards", {})
    for key, expected in QUEUE_GUARDS.items():
        if guards.get(key) is not expected:
            raise ValueError(f"unsafe queue guard {key}: expected {expected!r}")

    head_schema = str(head.get("schema", ""))
    if not head_schema.startswith("QROS_PERSISTENT_CONTROL_HEAD_V"):
        raise ValueError("invalid QROS HEAD schema")
    if queue.get("source_head_schema") != head_schema:
        raise ValueError("queue/HEAD schema mismatch; reconcile before dispatch")
    if head_blob_sha is not None:
        require_git_sha(head_blob_sha, "head_blob_sha")
        if queue.get("last_reconciled_head_blob_sha") != head_blob_sha:
            raise ValueError("queue/HEAD blob mismatch; reconcile before dispatch")
    if head.get("g30", {}).get("holdout_open_authorized") is not False:
        raise ValueError("HEAD does not forbid holdout opening")
    head_governance = head.get("governance", {})
    if head_governance.get("mt5_authorized") is not False:
        raise ValueError("HEAD authorizes MT5")
    if head_governance.get("branch_exhaustion_authorized") is not False:
        raise ValueError("HEAD authorizes branch exhaustion")
    if head_governance.get("all_gate_passers_advance") is not True:
        raise ValueError("HEAD does not preserve all passers")

    lease = state.get("lease")
    if lease is not None:
        if not isinstance(lease, dict):
            raise ValueError("lease must be an object or null")
        validate_lease(lease)

    required = set(protocol["queue_contract"]["item_required_fields"])
    ids: set[str] = set()
    for item in queue.get("queue", []):
        missing = required - set(item)
        if missing:
            raise ValueError(f"{item.get('item_id', '<unknown>')}: missing {sorted(missing)}")
        if item["status"] not in ITEM_STATUSES:
            raise ValueError(f"{item['item_id']}: invalid status {item['status']}")
        if item["source_head_schema"] != head_schema:
            raise ValueError(f"{item['item_id']}: source HEAD drift")
        item_id = item["item_id"]
        if item_id in ids:
            raise ValueError(f"duplicate item_id {item_id}")
        ids.add(item_id)
    for item in queue.get("queue", []):
        unknown = {x for x in item["prerequisites"] if x.startswith("G30-") and x not in ids}
        if unknown:
            raise ValueError(f"{item['item_id']}: unknown queue dependencies {sorted(unknown)}")


def lease_status(state: dict[str, Any], now: dt.datetime) -> str:
    lease = state.get("lease")
    if lease is None:
        return "FREE"
    validate_lease(lease)
    expires = parse_time(lease["expires_at"])
    return "EXPIRED" if expires <= now.astimezone(dt.timezone.utc) else "ACTIVE"


def next_item(queue: dict[str, Any]) -> dict[str, Any] | None:
    completed = {item["item_id"] for item in queue["queue"] if item["status"] == "COMPLETED"}
    for item in queue["queue"]:
        deps = {value for value in item["prerequisites"] if value.startswith("G30-")}
        if item["status"] == "READY" and deps <= completed:
            return item
    return None


def claim_lease(
    state: dict[str, Any], *, worker_id: str, observed_main_sha: str,
    entrypoint_sha256: str, now: dt.datetime, ttl_minutes: int,
    expired_recovery_ref: str | None = None,
) -> dict[str, Any]:
    require_git_sha(observed_main_sha, "observed_main_sha")
    require_sha256(entrypoint_sha256, "entrypoint_sha256")
    status = lease_status(state, now)
    if status == "ACTIVE":
        raise ValueError("unexpired lease exists")
    if status == "EXPIRED" and not expired_recovery_ref:
        raise ValueError("expired lease requires recovery/quarantine evidence")
    if not 1 <= ttl_minutes <= 95:
        raise ValueError("lease ttl must be between 1 and 95 minutes")
    epoch = int(state.get("lease_epoch", 0)) + 1
    claimed = utc_text(now)
    material = f"{worker_id}\0{observed_main_sha}\0{claimed}\0{epoch}".encode()
    lease_id = hashlib.sha256(material).hexdigest()
    updated = copy.deepcopy(state)
    updated["lease_epoch"] = epoch
    updated["lease"] = {
        "lease_id": lease_id,
        "worker_id": worker_id,
        "fence_token": epoch,
        "parent_main_sha": observed_main_sha,
        "claimed_at": claimed,
        "heartbeat_at": claimed,
        "expires_at": utc_text(now + dt.timedelta(minutes=ttl_minutes)),
        "entrypoint_sha256": entrypoint_sha256,
        "expired_recovery_ref": expired_recovery_ref,
    }
    updated["pending_cas"] = {
        "operation": "LEASE_CLAIM", "expected_main_sha": observed_main_sha, "force": False
    }
    return updated


def _owned_lease(state: dict[str, Any], lease_id: str, fence_token: int) -> dict[str, Any]:
    lease = state.get("lease")
    if not isinstance(lease, dict):
        raise ValueError("no lease exists")
    validate_lease(lease)
    if lease["lease_id"] != lease_id or lease["fence_token"] != fence_token:
        raise ValueError("stale or foreign lease token")
    return lease


def heartbeat_lease(
    state: dict[str, Any], *, lease_id: str, fence_token: int,
    observed_main_sha: str, now: dt.datetime, ttl_minutes: int,
) -> dict[str, Any]:
    require_git_sha(observed_main_sha, "observed_main_sha")
    lease = _owned_lease(state, lease_id, fence_token)
    if parse_time(lease["expires_at"]) <= now.astimezone(dt.timezone.utc):
        raise ValueError("cannot heartbeat an expired lease")
    if not 1 <= ttl_minutes <= 95:
        raise ValueError("lease ttl must be between 1 and 95 minutes")
    updated = copy.deepcopy(state)
    updated["lease"]["heartbeat_at"] = utc_text(now)
    updated["lease"]["expires_at"] = utc_text(now + dt.timedelta(minutes=ttl_minutes))
    updated["pending_cas"] = {
        "operation": "LEASE_HEARTBEAT", "expected_main_sha": observed_main_sha, "force": False
    }
    return updated


def release_lease(
    state: dict[str, Any], *, lease_id: str, fence_token: int,
    observed_main_sha: str, now: dt.datetime, outcome: str,
) -> dict[str, Any]:
    require_git_sha(observed_main_sha, "observed_main_sha")
    lease = _owned_lease(state, lease_id, fence_token)
    updated = copy.deepcopy(state)
    updated["last_released_lease"] = {
        **lease, "released_at": utc_text(now), "outcome": outcome,
    }
    updated["lease"] = None
    updated["pending_cas"] = {
        "operation": "LEASE_RELEASE", "expected_main_sha": observed_main_sha, "force": False
    }
    return updated


def validate_checkpoint(checkpoint: dict[str, Any], protocol: dict[str, Any]) -> None:
    required = set(protocol["checkpoint_policy"]["minimum_fields"])
    missing = required - set(checkpoint)
    if missing:
        raise ValueError(f"checkpoint missing {sorted(missing)}")
    if checkpoint.get("holdout_exposure") != "SEALED_NO_ACCESS":
        raise ValueError("checkpoint does not preserve sealed holdout")
    require_git_sha(checkpoint["parent_commit"], "checkpoint parent_commit")
    if checkpoint.get("execution_state") not in {"COMPLETED", "PENDING_RESUMABLE", "CONTROL_CANARY"}:
        raise ValueError("invalid checkpoint execution_state")
    if not isinstance(checkpoint.get("input_and_source_sha256"), dict):
        raise ValueError("checkpoint input_and_source_sha256 must be an object")
    for name, value in checkpoint["input_and_source_sha256"].items():
        require_sha256(value, f"checkpoint hash {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "next", "lease-check", "checkpoint-validate"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--head-blob-sha")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--now", default=None)
    args = parser.parse_args()
    protocol, queue, state, head = map(load, (args.protocol, args.queue, args.state, args.head))
    validate(protocol, queue, state, head, head_blob_sha=args.head_blob_sha)
    now = parse_time(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    result: dict[str, Any] = {
        "schema": "QROS_PERSISTENT_CHAT_CONTROLLER_RESULT_V2",
        "command": args.command,
        "protocol_sha256": digest(args.protocol),
        "queue_sha256": digest(args.queue),
        "state_sha256": digest(args.state),
        "head_sha256": digest(args.head),
        "lease_status": lease_status(state, now),
        "holdout_opened": False,
    }
    if args.command == "next":
        result["next_item"] = next_item(queue)
        result["decision"] = "DISPATCH_READY" if result["next_item"] else "NO_READY_ITEM_RECONCILE_REQUIRED"
    elif args.command == "lease-check":
        result["decision"] = "CLAIM_ALLOWED" if result["lease_status"] in {"FREE", "EXPIRED"} else "NO_OP_UNEXPIRED_LEASE"
    elif args.command == "checkpoint-validate":
        if args.checkpoint is None:
            raise ValueError("--checkpoint is required")
        validate_checkpoint(load(args.checkpoint), protocol)
        result["decision"] = "CHECKPOINT_VALID"
    else:
        result["decision"] = "CONTROL_DOCUMENTS_VALID"
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
