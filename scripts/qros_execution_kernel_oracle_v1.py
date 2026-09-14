#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
TERMINAL = {"PASS_FIRST_GATE", "REJECTED_FIRST_GATE", "INVALID_FIRST_GATE", "BLOCKED_BY_INFRASTRUCTURE"}


def load(root: Path, rel: str):
    if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts:
        raise ValueError(f"BAD_PATH:{rel!r}")
    p = root / rel
    if not p.is_file():
        raise ValueError(f"ABSENT:{rel}")
    return json.loads(p.read_text(encoding="utf-8"))


def blob(path: Path):
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def h256(x):
    return hashlib.sha256(canon(x)).hexdigest()


def must(x, code):
    if not x:
        raise ValueError(code)


def domain(row):
    return (row.get("asset"), row.get("side"), row.get("timeframe"))


def expected(root: Path, target: dict, target_path: str):
    must(target.get("campaign") == CAMPAIGN, "ORACLE_CAMPAIGN")
    k = target.get("execution_kernel", {})
    must(k.get("status") == "ACTIVE", "ORACLE_KERNEL_INACTIVE")
    must(k.get("single_authoritative_action") is True, "ORACLE_NOT_SINGLE_ACTION")
    must(k.get("free_text_next_action_authoritative") is False, "ORACLE_TEXT_AUTHORITY")

    kpins = {}
    for name in ("governance", "execution_map", "decision_ledger", "compiler", "oracle", "adversarial_suite", "external_workflow"):
        node = k.get(name, {})
        p, s = node.get("path"), node.get("git_blob_sha1")
        must(p and s, f"ORACLE_PIN_ABSENT:{name}")
        actual = blob(root / p)
        must(actual == s, f"ORACLE_PIN_DIFF:{name}")
        kpins[name] = actual

    gov = load(root, k["governance"]["path"])
    emap = load(root, k["execution_map"]["path"])
    decisions = load(root, k["decision_ledger"]["path"])
    must(gov.get("chat_runtime_role") == "EPHEMERAL_EXECUTOR_ONLY", "ORACLE_CHAT_ROLE")
    must(gov.get("no_memory_as_authority") is True, "ORACLE_MEMORY_RULE")
    must(emap.get("campaign") == CAMPAIGN and emap.get("status") == "FROZEN_ACTIVE", "ORACLE_MAP")
    must(decisions.get("status") == "FROZEN_ACTIVE", "ORACLE_DECISIONS")

    auth = target.get("authority", {})
    ap = target.get("authority_pins", {})
    pairs = [
        ("primary_policy", "primary_policy_git_blob_sha1"),
        ("first_gate_multiplicity_contract", "multiplicity_contract_git_blob_sha1"),
        ("gate_a_plan", "gate_a_plan_git_blob_sha1"),
        ("minimal_dev_carrier_binding", "minimal_dev_carrier_binding_git_blob_sha1"),
        ("xau_m1_completion", "xau_m1_completion_git_blob_sha1"),
        ("promotion_ledger", "promotion_ledger_git_blob_sha1"),
    ]
    spins = {}
    for pkey, skey in pairs:
        rel, want = auth.get(pkey), ap.get(skey)
        must(rel and want, f"ORACLE_SCI_PIN_ABSENT:{pkey}")
        got = blob(root / rel)
        must(got == want, f"ORACLE_SCI_PIN_DIFF:{pkey}")
        spins[pkey] = got

    policy = load(root, auth["primary_policy"])
    contract = load(root, auth["first_gate_multiplicity_contract"])
    gate = load(root, auth["gate_a_plan"])
    binding = load(root, auth["minimal_dev_carrier_binding"])
    comp = load(root, auth["xau_m1_completion"])
    ledger = load(root, auth["promotion_ledger"])
    must(policy.get("status") == "ACTIVE_PRIMARY", "ORACLE_POLICY")
    must(contract.get("status") == "FROZEN_PRE_PNL", "ORACLE_CONTRACT")
    must(gate.get("state") == "FROZEN_PRE_PNL", "ORACLE_GATE")
    must(binding.get("status") == "PASS", "ORACLE_BINDING")
    must(comp.get("status") == "PASS_DOUBLE_ORACLE", "ORACLE_COMP")

    rows = ledger.get("completed_and_promoted_shards", [])
    must(rows, "ORACLE_NO_ROWS")
    order = [r.get("first_gate_order") for r in rows]
    must(order == sorted(order) and len(order) == len(set(order)), "ORACLE_FIFO_ORDER")
    pend = [r for r in rows if r.get("first_gate_status") == "PENDING"]
    term = [r for r in rows if r.get("first_gate_status") in TERMINAL]
    must(len(pend) == ledger.get("first_gate_pending_count"), "ORACLE_PENDING_COUNT")
    must(len(term) == ledger.get("first_gate_terminal_count"), "ORACLE_TERM_COUNT")
    must(pend, "ORACLE_NO_PENDING")
    first = sorted(pend, key=lambda r: r["first_gate_order"])[0]
    must(first.get("first_gate_order") == ledger.get("current_first_gate_order"), "ORACLE_CURRENT_ORDER")
    must(first.get("shard_id") == ledger.get("current_first_gate_shard_id"), "ORACLE_CURRENT_ID")
    must(domain(first) == domain(ledger.get("current_first_gate_domain", {})), "ORACLE_CURRENT_DOMAIN")
    cf = target.get("current_first_gate", {})
    must(cf.get("shard_id") == first.get("shard_id") and cf.get("first_gate_order") == first.get("first_gate_order") and domain(cf) == domain(first), "ORACLE_TARGET_CURRENT")

    sid = k.get("current_state")
    spec = emap.get("states", {}).get(sid)
    must(isinstance(spec, dict), "ORACLE_STATE_UNKNOWN")
    act = spec.get("authorized_action")
    must(spec.get("deterministic") is True and isinstance(act, str) and act, "ORACLE_ACTION_UNDEFINED")
    must(spec.get("success_state") is not None and spec.get("failure_state") is not None, "ORACLE_TRANSITION_UNDEFINED")

    scorer = target.get("first_gate_scorer", {})
    if sid == "FG_SCORER_NOT_BUILT":
        must(target.get("first_gate_data_ready") is True, "ORACLE_DATA_NOT_READY")
        must(scorer.get("status") == "NOT_BUILT", "ORACLE_SCORER_CONTRADICTION")
        must(target.get("economic_pnl_read") is False and target.get("holdout_open") is False and target.get("ga2_open") is False, "ORACLE_FIREWALL")
        must(binding.get("full_history_completion_required_for_first_gate") is False, "ORACLE_FULL_HISTORY_AMBIGUITY")
        must(binding.get("xau",{}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "ORACLE_XAU_PREFIX")
        must(binding.get("nqx",{}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "ORACLE_NQX_PREFIX")
    elif sid == "FG_SCORER_PRIMARY_BUILT":
        must(scorer.get("status") == "PRIMARY_BUILT", "ORACLE_SCORER_PRIMARY")
        must(blob(root / scorer.get("primary_source_path")) == scorer.get("primary_source_git_blob_sha1"), "ORACLE_SCORER_PRIMARY_PIN")
        must(target.get("economic_pnl_read") is False and target.get("holdout_open") is False and target.get("ga2_open") is False, "ORACLE_FIREWALL")
    elif sid == "FG_SCORER_PARITY_PASS":
        must(scorer.get("status") == "PARITY_PASS" and scorer.get("independent_oracle_pass") is True, "ORACLE_SCORER_PARITY")
        must(target.get("holdout_open") is False, "ORACLE_HOLDOUT")
    elif sid in {"FG_EXECUTION_COMPLETE_UNVALIDATED", "FG_RESULT_ORACLE_PASS", "FG_TERMINAL_PERSISTED"}:
        must(target.get("holdout_open") is False, "ORACLE_HOLDOUT")
    else:
        must(spec.get("future_state_explicit") is True, "ORACLE_UNIMPLEMENTED_STATE")

    base = {
        "schema": "QROS_DETERMINISTIC_ACTION_TICKET_1.0",
        "campaign": CAMPAIGN,
        "frontier_version": target.get("version"),
        "frontier_target_path": target_path,
        "kernel_epoch": k.get("kernel_epoch"),
        "action_sequence": k.get("action_sequence"),
        "state_id": sid,
        "action_type": act,
        "subject": {
            "asset": first.get("asset"),
            "side": first.get("side"),
            "timeframe": first.get("timeframe"),
            "shard_id": first.get("shard_id"),
            "first_gate_order": first.get("first_gate_order"),
            "distinct_mask_classes": first.get("distinct_mask_classes"),
        },
        "success_state": spec.get("success_state"),
        "failure_state": spec.get("failure_state"),
        "required_outputs": spec.get("required_outputs", []),
        "forbidden_actions": spec.get("forbidden_actions", []),
        "authority_pins": {**kpins, **spins},
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
    base["ticket_id"] = h256(base)
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--primary-ticket", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", default=None)
    a = ap.parse_args()
    root = Path(a.repo_root).resolve()
    stable_rel = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
    stable = load(root, stable_rel)
    if a.target:
        target_rel = a.target
        target = load(root, target_rel)
        must(target.get("supersedes_frontier_version") == stable.get("current_version"), "ORACLE_PARENT_VERSION")
        parent_blob = target.get("superseded_stable_pointer_blob_sha1")
        if parent_blob:
            must(blob(root / stable_rel) == parent_blob, "ORACLE_PARENT_BLOB")
    else:
        target_rel = stable.get("target_path")
        target = load(root, target_rel)
        must(target.get("version") == stable.get("current_version"), "ORACLE_ACTIVE_VERSION")
    exp = expected(root, target, target_rel)
    got = json.loads(Path(a.primary_ticket).read_text(encoding="utf-8"))
    must(got == exp, "PRIMARY_ORACLE_TICKET_MISMATCH")
    rec = {
        "schema": "QROS_DETERMINISTIC_ACTION_ORACLE_RECEIPT_1.0",
        "status": "PASS",
        "frontier_version": exp["frontier_version"],
        "state_id": exp["state_id"],
        "action_type": exp["action_type"],
        "ticket_id": exp["ticket_id"],
        "independent_implementation": True,
        "imports_primary_compiler": False,
    }
    rec["receipt_sha256"] = h256(rec)
    Path(a.out).write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
