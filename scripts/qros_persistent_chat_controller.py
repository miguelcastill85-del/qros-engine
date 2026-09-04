#!/usr/bin/env python3
"""Validate and deterministically select work from the QROS persistent chat queue.

This utility does not execute scientific code and does not mutate GitHub. The automation
or operator performs remote compare-and-swap commits; this source validates the control
documents and emits the next dispatch candidate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


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
        raise ValueError("lease time must include timezone")
    return parsed.astimezone(dt.timezone.utc)


def validate(protocol: dict[str, Any], queue: dict[str, Any], state: dict[str, Any], head: dict[str, Any]) -> None:
    if protocol.get("schema") != "QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_V1":
        raise ValueError("unexpected protocol schema")
    if protocol.get("status") != "ADOPTED_MANDATORY_OPERATIONAL_LAYER":
        raise ValueError("protocol is not active")
    if not state.get("enabled"):
        raise ValueError("persistent execution is disabled")
    if state.get("holdout_opened") is not False:
        raise ValueError("state does not preserve sealed holdout")
    guards = queue.get("guards", {})
    if guards.get("holdout_open_authorized") is not False:
        raise ValueError("queue authorizes holdout")
    if guards.get("paid_infrastructure_authorized") is not False:
        raise ValueError("queue authorizes paid infrastructure")
    if guards.get("single_winner_selection") is not False:
        raise ValueError("queue permits single-winner selection")
    if not str(head.get("schema", "")).startswith("QROS_PERSISTENT_CONTROL_HEAD_V"):
        raise ValueError("invalid QROS HEAD schema")
    if head.get("g30", {}).get("holdout_open_authorized") is not False:
        raise ValueError("HEAD does not forbid holdout opening")
    ids: set[str] = set()
    for item in queue.get("queue", []):
        missing = set(protocol["queue_contract"]["item_required_fields"]) - set(item)
        if missing:
            raise ValueError(f"{item.get('item_id', '<unknown>')}: missing {sorted(missing)}")
        item_id = item["item_id"]
        if item_id in ids:
            raise ValueError(f"duplicate item_id {item_id}")
        ids.add(item_id)


def lease_status(state: dict[str, Any], now: dt.datetime) -> str:
    lease = state.get("lease")
    if lease is None:
        return "FREE"
    expires = parse_time(lease["expires_at"])
    return "EXPIRED" if expires <= now else "ACTIVE"


def next_item(queue: dict[str, Any]) -> dict[str, Any] | None:
    completed = {item["item_id"] for item in queue["queue"] if item["status"] == "COMPLETED"}
    for item in queue["queue"]:
        deps = {value for value in item["prerequisites"] if value.startswith("G30-")}
        if item["status"] == "READY" and deps <= completed:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "next", "lease-check"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--now", default=None, help="ISO-8601 UTC timestamp for deterministic lease checks")
    args = parser.parse_args()
    protocol, queue, state, head = map(load, (args.protocol, args.queue, args.state, args.head))
    validate(protocol, queue, state, head)
    now = parse_time(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    result: dict[str, Any] = {
        "schema": "QROS_PERSISTENT_CHAT_CONTROLLER_RESULT_V1",
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
    else:
        result["decision"] = "CONTROL_DOCUMENTS_VALID"
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
