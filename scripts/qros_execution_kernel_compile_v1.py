#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def load_json(root: Path, rel: str):
    if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise RuntimeError(f"INVALID_REPO_PATH:{rel!r}")
    p = root / rel
    if not p.is_file():
        raise RuntimeError(f"MISSING:{rel}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"INVALID_JSON:{rel}:{e}") from e


def require(cond, code, detail=None):
    if not cond:
        raise RuntimeError(code if detail is None else f"{code}:{detail}")


def dom(x):
    return (x.get("asset"), x.get("side"), x.get("timeframe"))


def verify_pin(root: Path, rel: str, expected: str, label: str):
    require(bool(rel) and bool(expected), f"PIN_MISSING:{label}")
    actual = git_blob_sha1(root / rel)
    require(actual == expected, f"PIN_MISMATCH:{label}", f"{actual}!={expected}")
    return actual


def derive_action(root: Path, target: dict, target_path: str):
    require(target.get("campaign") == CAMPAIGN, "CAMPAIGN_MISMATCH")
    kernel = target.get("execution_kernel")
    require(isinstance(kernel, dict), "KERNEL_MISSING")
    require(kernel.get("status") == "ACTIVE", "KERNEL_NOT_ACTIVE")
    require(kernel.get("single_authoritative_action") is True, "KERNEL_SINGLE_ACTION_DISABLED")
    require(kernel.get("free_text_next_action_authoritative") is False, "FREE_TEXT_AUTHORITY_FORBIDDEN")

    pins = {}
    for key in ("governance", "execution_map", "decision_ledger", "compiler", "oracle", "adversarial_suite", "external_workflow"):
        node = kernel.get(key, {})
        rel, exp = node.get("path"), node.get("git_blob_sha1")
        pins[key] = verify_pin(root, rel, exp, key)

    gov = load_json(root, kernel["governance"]["path"])
    emap = load_json(root, kernel["execution_map"]["path"])
    dledger = load_json(root, kernel["decision_ledger"]["path"])
    require(gov.get("status") == "FROZEN_ACTIVE", "GOVERNANCE_NOT_FROZEN")
    require(gov.get("chat_runtime_role") == "EPHEMERAL_EXECUTOR_ONLY", "CHAT_ROLE_AMBIGUOUS")
    require(gov.get("no_memory_as_authority") is True, "MEMORY_AUTHORITY_FORBIDDEN")
    require(emap.get("status") == "FROZEN_ACTIVE", "MAP_NOT_FROZEN")
    require(emap.get("campaign") == CAMPAIGN, "MAP_CAMPAIGN_MISMATCH")
    require(dledger.get("status") == "FROZEN_ACTIVE", "DECISION_LEDGER_NOT_FROZEN")

    auth = target.get("authority", {})
    auth_pins = target.get("authority_pins", {})
    pin_map = {
        "primary_policy": "primary_policy_git_blob_sha1",
        "first_gate_multiplicity_contract": "multiplicity_contract_git_blob_sha1",
        "gate_a_plan": "gate_a_plan_git_blob_sha1",
        "minimal_dev_carrier_binding": "minimal_dev_carrier_binding_git_blob_sha1",
        "xau_m1_completion": "xau_m1_completion_git_blob_sha1",
        "promotion_ledger": "promotion_ledger_git_blob_sha1",
    }
    verified_scientific_pins = {}
    for akey, pkey in pin_map.items():
        rel = auth.get(akey)
        exp = auth_pins.get(pkey)
        verified_scientific_pins[akey] = verify_pin(root, rel, exp, akey)

    policy = load_json(root, auth["primary_policy"])
    contract = load_json(root, auth["first_gate_multiplicity_contract"])
    gate = load_json(root, auth["gate_a_plan"])
    binding = load_json(root, auth["minimal_dev_carrier_binding"])
    completion = load_json(root, auth["xau_m1_completion"])
    ledger = load_json(root, auth["promotion_ledger"])

    require(policy.get("status") == "ACTIVE_PRIMARY", "PRIMARY_POLICY_NOT_ACTIVE")
    require(contract.get("status") == "FROZEN_PRE_PNL", "MULTIPLICITY_NOT_FROZEN")
    require(gate.get("state") == "FROZEN_PRE_PNL", "GATE_PLAN_NOT_FROZEN")
    require(binding.get("status") == "PASS", "MINIMAL_DEV_BINDING_NOT_PASS")
    require(completion.get("status") == "PASS_DOUBLE_ORACLE", "XAU_M1_GA1_NOT_DOUBLE_ORACLE")
    require(ledger.get("campaign") == CAMPAIGN, "LEDGER_CAMPAIGN_MISMATCH")

    rows = ledger.get("completed_and_promoted_shards")
    require(isinstance(rows, list) and rows, "LEDGER_ROWS_EMPTY")
    orders = [r.get("first_gate_order") for r in rows]
    require(all(isinstance(o, int) and o > 0 for o in orders), "LEDGER_ORDER_INVALID")
    require(len(set(orders)) == len(orders), "LEDGER_ORDER_DUPLICATE")
    require(orders == sorted(orders), "LEDGER_ORDER_NOT_SORTED")
    pending = [r for r in rows if r.get("first_gate_status") == "PENDING"]
    terminal = [r for r in rows if r.get("first_gate_status") in ("PASS_FIRST_GATE", "REJECTED_FIRST_GATE", "INVALID_FIRST_GATE", "BLOCKED_BY_INFRASTRUCTURE")]
    require(len(pending) == ledger.get("first_gate_pending_count"), "LEDGER_PENDING_COUNT_MISMATCH")
    require(len(terminal) == ledger.get("first_gate_terminal_count"), "LEDGER_TERMINAL_COUNT_MISMATCH")
    require(len(pending) > 0, "NO_PENDING_FIRST_GATE")
    oldest = min(pending, key=lambda r: r["first_gate_order"])
    require(oldest.get("first_gate_order") == ledger.get("current_first_gate_order"), "FIFO_CURRENT_ORDER_MISMATCH")
    require(oldest.get("shard_id") == ledger.get("current_first_gate_shard_id"), "FIFO_CURRENT_SHARD_MISMATCH")
    require(dom(oldest) == dom(ledger.get("current_first_gate_domain", {})), "FIFO_CURRENT_DOMAIN_MISMATCH")

    cf = target.get("current_first_gate", {})
    require(dom(cf) == dom(oldest), "TARGET_LEDGER_DOMAIN_MISMATCH")
    require(cf.get("shard_id") == oldest.get("shard_id"), "TARGET_LEDGER_SHARD_MISMATCH")
    require(cf.get("first_gate_order") == oldest.get("first_gate_order"), "TARGET_LEDGER_ORDER_MISMATCH")

    state_id = kernel.get("current_state")
    states = emap.get("states", {})
    require(state_id in states, "UNKNOWN_KERNEL_STATE", state_id)
    state_spec = states[state_id]
    action_type = state_spec.get("authorized_action")
    require(isinstance(action_type, str) and action_type, "ACTION_UNDEFINED", state_id)

    scorer = target.get("first_gate_scorer", {})
    if state_id == "FG_SCORER_NOT_BUILT":
        require(target.get("first_gate_data_ready") is True, "FIRST_GATE_DATA_NOT_READY")
        require(scorer.get("status") == "NOT_BUILT", "SCORER_STATUS_CONTRADICTION")
        require(all(target.get(k) is False for k in ("economic_pnl_read", "holdout_open", "ga2_open")), "PRE_ECONOMIC_FIREWALL_BROKEN")
        require(binding.get("full_history_completion_required_for_first_gate") is False, "FULL_HISTORY_FALSE_REQUIREMENT")
        require(binding.get("xau", {}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "XAU_DEV_PREFIX_NOT_PASS")
        require(binding.get("nqx", {}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "NQX_DEV_PREFIX_NOT_PASS")
    elif state_id == "FG_SCORER_PRIMARY_BUILT":
        require(scorer.get("status") == "PRIMARY_BUILT", "SCORER_PRIMARY_STATUS_MISMATCH")
        verify_pin(root, scorer.get("primary_source_path"), scorer.get("primary_source_git_blob_sha1"), "scorer_primary")
        require(all(target.get(k) is False for k in ("economic_pnl_read", "holdout_open", "ga2_open")), "PRE_ECONOMIC_FIREWALL_BROKEN")
    elif state_id == "FG_SCORER_PARITY_PASS":
        require(scorer.get("status") == "PARITY_PASS", "SCORER_PARITY_STATUS_MISMATCH")
        require(scorer.get("independent_oracle_pass") is True, "SCORER_ORACLE_NOT_PASS")
        require(target.get("holdout_open") is False, "HOLDOUT_MUST_REMAIN_CLOSED")
    elif state_id in ("FG_EXECUTION_COMPLETE_UNVALIDATED", "FG_RESULT_ORACLE_PASS", "FG_TERMINAL_PERSISTED"):
        require(target.get("holdout_open") is False, "HOLDOUT_MUST_REMAIN_CLOSED")
    else:
        require(state_spec.get("future_state_explicit") is True, "STATE_NOT_IMPLEMENTED_EXPLICITLY", state_id)

    require(state_spec.get("deterministic") is True, "STATE_NOT_DETERMINISTIC", state_id)
    require(state_spec.get("success_state") is not None, "SUCCESS_STATE_UNDEFINED", state_id)
    require(state_spec.get("failure_state") is not None, "FAILURE_STATE_UNDEFINED", state_id)

    subject = {
        "asset": oldest.get("asset"),
        "side": oldest.get("side"),
        "timeframe": oldest.get("timeframe"),
        "shard_id": oldest.get("shard_id"),
        "first_gate_order": oldest.get("first_gate_order"),
        "distinct_mask_classes": oldest.get("distinct_mask_classes"),
    }

    ticket = {
        "schema": "QROS_DETERMINISTIC_ACTION_TICKET_1.0",
        "campaign": CAMPAIGN,
        "frontier_version": target.get("version"),
        "frontier_target_path": target_path,
        "kernel_epoch": kernel.get("kernel_epoch"),
        "action_sequence": kernel.get("action_sequence"),
        "state_id": state_id,
        "action_type": action_type,
        "subject": subject,
        "success_state": state_spec.get("success_state"),
        "failure_state": state_spec.get("failure_state"),
        "required_outputs": state_spec.get("required_outputs", []),
        "forbidden_actions": state_spec.get("forbidden_actions", []),
        "authority_pins": {**pins, **verified_scientific_pins},
        "invariants": {
            "exactly_one_authoritative_action": True,
            "fifo_oldest_pending_only": True,
            "chat_memory_authoritative": False,
            "free_text_next_action_authoritative": False,
            "holdout_open": target.get("holdout_open"),
            "economic_pnl_read": target.get("economic_pnl_read"),
            "ga2_open": target.get("ga2_open"),
        },
    }
    ticket["ticket_id"] = sha256_obj(ticket)
    return ticket


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", default=None, help="Optional unpromoted immutable frontier target for candidate validation.")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    stable_path = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
    stable = load_json(root, stable_path)

    if args.target:
        target_path = args.target
        target = load_json(root, target_path)
        require(target.get("supersedes_frontier_version") == stable.get("current_version"), "CANDIDATE_PARENT_VERSION_MISMATCH")
        expected_parent_blob = target.get("superseded_stable_pointer_blob_sha1")
        if expected_parent_blob:
            require(git_blob_sha1(root / stable_path) == expected_parent_blob, "CANDIDATE_PARENT_BLOB_MISMATCH")
    else:
        target_path = stable.get("target_path")
        require(isinstance(target_path, str) and target_path, "STABLE_TARGET_MISSING")
        target = load_json(root, target_path)
        require(target.get("version") == stable.get("current_version"), "ACTIVE_VERSION_MISMATCH")

    ticket = derive_action(root, target, target_path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ticket, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "state_id": ticket["state_id"], "action_type": ticket["action_type"], "ticket_id": ticket["ticket_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(e)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
