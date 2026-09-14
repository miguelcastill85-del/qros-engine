#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
TERMINAL = {"PASS_FIRST_GATE", "REJECTED_FIRST_GATE", "INVALID_FIRST_GATE", "BLOCKED_BY_INFRASTRUCTURE"}
SUPPORTED_GUARDS = {
    "P01_PRE_ECONOMIC_SCORER_NOT_BUILT",
    "P02_PRE_ECONOMIC_SCORER_PRIMARY_BUILT",
    "P03_PRE_ECONOMIC_SCORER_PARITY_PASS",
    "P04_ECONOMIC_EXECUTION_COMPLETE_UNVALIDATED",
    "P05_ECONOMIC_RESULT_ORACLE_PASS",
    "P06_TERMINAL_PERSISTED",
    "P07_FIFO_PENDING_SCORER_REUSABLE",
    "P08_BACKLOG_DRAINED_NEXT_GA1_FROZEN",
    "P09_GA1_AUTHORIZED_NO_PENDING_FIRST_GATE",
    "P10_GA1_COMPLETE_UNPROMOTED",
    "P11_ALL_GA1_AND_FIRST_GATE_TERMINAL",
    "P12_EXPLICIT_POLICY_REQUIRED_BLOCK",
    "P13_INTEGRITY_INCIDENT_ONLY",
}
SUPPORTED_SUBJECTS = {
    "OLDEST_PENDING_FIRST_GATE",
    "LAST_TERMINAL_FIRST_GATE",
    "NEXT_PREREGISTERED_GA1",
    "CURRENT_GA1",
    "CAMPAIGN",
}
SUPPORTED_SUCCESS_SELECTORS = {"SEL01_LEDGER_AFTER_TERMINAL"}
KERNEL_PIN_KEYS = (
    "governance", "execution_map", "decision_ledger", "master_workgraph", "gap_register",
    "compiler", "oracle", "adversarial_suite", "external_workflow"
)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def h256(x): return hashlib.sha256(canonical(x)).hexdigest()


def git_blob(path: Path):
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode("ascii") + b"\0" + b).hexdigest()


def req(cond, code, detail=None):
    if not cond:
        raise RuntimeError(code if detail is None else f"{code}:{detail}")


def safe_rel(rel):
    return isinstance(rel, str) and rel and not rel.startswith("/") and ".." not in Path(rel).parts


def load(root: Path, rel: str):
    req(safe_rel(rel), "INVALID_PATH", rel)
    p = root / rel
    req(p.is_file(), "MISSING", rel)
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: raise RuntimeError(f"INVALID_JSON:{rel}:{e}") from e


def pin(root: Path, rel: str, want: str, label: str):
    req(safe_rel(rel) and isinstance(want, str) and want, "PIN_MISSING", label)
    p = root / rel
    req(p.is_file(), "PIN_FILE_MISSING", label)
    got = git_blob(p)
    req(got == want, "PIN_MISMATCH", f"{label}:{got}!={want}")
    return got


def dom(x): return (x.get("asset"), x.get("side"), x.get("timeframe"))


def firewalls(target, expected_economic=None, expected_ga2=None):
    req(target.get("holdout_open") is False, "HOLDOUT_MUST_BE_CLOSED")
    if expected_economic is not None: req(target.get("economic_pnl_read") is expected_economic, "ECONOMIC_FLAG_MISMATCH")
    if expected_ga2 is not None: req(target.get("ga2_open") is expected_ga2, "GA2_FLAG_MISMATCH")


def pinned_optional(root: Path, node: dict, label: str):
    req(isinstance(node, dict), "STRUCTURED_RECEIPT_MISSING", label)
    rel, want = node.get("path"), node.get("git_blob_sha1")
    return pin(root, rel, want, label)


def ledger_facts(ledger: dict):
    rows = ledger.get("completed_and_promoted_shards")
    req(isinstance(rows, list), "LEDGER_ROWS_NOT_LIST")
    orders = [r.get("first_gate_order") for r in rows]
    req(all(isinstance(x, int) and x > 0 for x in orders), "LEDGER_ORDER_INVALID")
    req(orders == sorted(orders), "LEDGER_ORDER_NOT_SORTED")
    req(len(orders) == len(set(orders)), "LEDGER_ORDER_DUPLICATE")
    pending = [r for r in rows if r.get("first_gate_status") == "PENDING"]
    terminal = [r for r in rows if r.get("first_gate_status") in TERMINAL]
    req(len(pending) == ledger.get("first_gate_pending_count"), "LEDGER_PENDING_COUNT_MISMATCH")
    req(len(terminal) == ledger.get("first_gate_terminal_count"), "LEDGER_TERMINAL_COUNT_MISMATCH")
    oldest = min(pending, key=lambda r: r["first_gate_order"]) if pending else None
    return rows, pending, terminal, oldest


def verify_map_coverage(emap: dict):
    states = emap.get("states", {})
    req(isinstance(states, dict) and states, "MAP_STATES_EMPTY")
    declared_guards = {v.get("guard_profile") for v in states.values()}
    declared_subjects = {v.get("subject_selector") for v in states.values()}
    declared_success = {v.get("success_state_selector") for v in states.values() if v.get("success_state_selector")}
    req(None not in declared_guards, "MAP_STATE_WITHOUT_GUARD")
    req(None not in declared_subjects, "MAP_STATE_WITHOUT_SUBJECT")
    req(declared_guards == SUPPORTED_GUARDS, "GUARD_COVERAGE_NOT_TOTAL", f"declared={sorted(declared_guards)} supported={sorted(SUPPORTED_GUARDS)}")
    req(declared_subjects <= SUPPORTED_SUBJECTS, "SUBJECT_SELECTOR_UNSUPPORTED", sorted(declared_subjects - SUPPORTED_SUBJECTS))
    req(declared_success == SUPPORTED_SUCCESS_SELECTORS, "SUCCESS_SELECTOR_COVERAGE_NOT_TOTAL")
    for sid, spec in states.items():
        req(isinstance(spec.get("authorized_action"), str) and spec["authorized_action"], "STATE_ACTION_MISSING", sid)
        req(spec.get("failure_state") in states, "STATE_FAILURE_EDGE_UNKNOWN", sid)
        if spec.get("success_state") is not None:
            req(spec.get("success_state") in states, "STATE_SUCCESS_EDGE_UNKNOWN", sid)
        else:
            req(spec.get("success_state_selector") in SUPPORTED_SUCCESS_SELECTORS, "STATE_SUCCESS_SELECTOR_UNKNOWN", sid)
            for dst in spec.get("allowed_success_states", []): req(dst in states, "STATE_DYNAMIC_EDGE_UNKNOWN", f"{sid}->{dst}")
    return states


def resolve_subject(selector, target, ledger, facts):
    rows, pending, terminal, oldest = facts
    if selector == "OLDEST_PENDING_FIRST_GATE":
        req(oldest is not None, "SUBJECT_NO_PENDING_FIRST_GATE")
        return {k: oldest.get(k) for k in ("asset","side","timeframe","shard_id","first_gate_order","distinct_mask_classes")}
    if selector == "LAST_TERMINAL_FIRST_GATE":
        ctx = target.get("transition_context", {}).get("last_terminal_first_gate")
        req(isinstance(ctx, dict), "LAST_TERMINAL_CONTEXT_MISSING")
        match = [r for r in terminal if r.get("shard_id") == ctx.get("shard_id") and r.get("first_gate_order") == ctx.get("first_gate_order")]
        req(len(match) == 1, "LAST_TERMINAL_CONTEXT_NOT_UNIQUE")
        r = match[0]
        return {k: r.get(k) for k in ("asset","side","timeframe","shard_id","first_gate_order","distinct_mask_classes")}
    if selector == "NEXT_PREREGISTERED_GA1":
        n = target.get("next_preregistered_ga1") or ledger.get("next_preregistered_ga1")
        req(isinstance(n, dict) and n.get("shard_id"), "NEXT_GA1_MISSING")
        return {k: n.get(k) for k in ("asset","side","timeframe","shard_id","config_root_sha256","status")}
    if selector == "CURRENT_GA1":
        g = target.get("current_ga1")
        req(isinstance(g, dict) and g.get("shard_id"), "CURRENT_GA1_MISSING")
        return {k: g.get(k) for k in ("asset","side","timeframe","shard_id","config_root_sha256","status")}
    if selector == "CAMPAIGN":
        return {"campaign": CAMPAIGN}
    raise RuntimeError(f"UNKNOWN_SUBJECT_SELECTOR:{selector}")


def resolve_success(spec, target, ledger, facts):
    static = spec.get("success_state")
    if static is not None: return static
    sel = spec.get("success_state_selector")
    if sel != "SEL01_LEDGER_AFTER_TERMINAL": raise RuntimeError(f"UNKNOWN_SUCCESS_SELECTOR:{sel}")
    rows, pending, terminal, oldest = facts
    if pending: return "FG_NEXT_PENDING_READY"
    counts = target.get("verified_counts", {})
    if counts.get("ga1_formally_completed_shards") == 60 and len(terminal) == 60: return "GA1_ALL_60_COMPLETE"
    n = target.get("next_preregistered_ga1") or ledger.get("next_preregistered_ga1")
    if isinstance(n, dict) and n.get("shard_id"): return "FIRST_GATE_BACKLOG_DRAINED"
    raise RuntimeError("SUCCESS_SELECTOR_NO_RULE_MATCH")


def validate_current_subject(target, subject, selector):
    if selector == "OLDEST_PENDING_FIRST_GATE":
        cf = target.get("current_first_gate", {})
        req(cf.get("shard_id") == subject.get("shard_id"), "TARGET_CURRENT_SHARD_MISMATCH")
        req(cf.get("first_gate_order") == subject.get("first_gate_order"), "TARGET_CURRENT_ORDER_MISMATCH")
        req(dom(cf) == (subject.get("asset"),subject.get("side"),subject.get("timeframe")), "TARGET_CURRENT_DOMAIN_MISMATCH")


def apply_guard(profile, root, target, ledger, facts, binding):
    rows, pending, terminal, oldest = facts
    scorer = target.get("first_gate_scorer", {})
    counts = target.get("verified_counts", {})
    if profile == "P01_PRE_ECONOMIC_SCORER_NOT_BUILT":
        req(oldest is not None and target.get("first_gate_data_ready") is True, "P01_DATA_OR_FIFO_NOT_READY")
        req(scorer.get("status") == "NOT_BUILT", "P01_SCORER_STATUS")
        firewalls(target, False, False)
        req(binding.get("full_history_completion_required_for_first_gate") is False, "P01_FULL_HISTORY_AMBIGUITY")
        req(binding.get("xau",{}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "P01_XAU_PREFIX")
        req(binding.get("nqx",{}).get("verification") == "PASS_BYTE_EXACT_PREFIX", "P01_NQX_PREFIX")
    elif profile == "P02_PRE_ECONOMIC_SCORER_PRIMARY_BUILT":
        req(oldest is not None and scorer.get("status") == "PRIMARY_BUILT", "P02_SCORER_STATUS")
        pin(root, scorer.get("primary_source_path"), scorer.get("primary_source_git_blob_sha1"), "first_gate_scorer_primary")
        firewalls(target, False, False)
    elif profile == "P03_PRE_ECONOMIC_SCORER_PARITY_PASS":
        req(oldest is not None and scorer.get("status") == "PARITY_PASS" and scorer.get("independent_oracle_pass") is True, "P03_PARITY")
        pin(root, scorer.get("primary_source_path"), scorer.get("primary_source_git_blob_sha1"), "first_gate_scorer_primary")
        pin(root, scorer.get("oracle_source_path"), scorer.get("oracle_source_git_blob_sha1"), "first_gate_scorer_oracle")
        pinned_optional(root, scorer.get("parity_receipt", {}), "first_gate_scorer_parity_receipt")
        firewalls(target, False, False)
    elif profile == "P04_ECONOMIC_EXECUTION_COMPLETE_UNVALIDATED":
        req(oldest is not None and scorer.get("status") == "PARITY_PASS", "P04_SCORER_OR_FIFO")
        ex = target.get("first_gate_execution", {})
        req(ex.get("status") == "COMPLETE_UNVALIDATED", "P04_EXEC_STATUS")
        pinned_optional(root, ex.get("execution_receipt", {}), "first_gate_execution_receipt")
        firewalls(target, True, True)
    elif profile == "P05_ECONOMIC_RESULT_ORACLE_PASS":
        req(oldest is not None, "P05_FIFO")
        o = target.get("first_gate_result_oracle", {})
        req(o.get("status") == "PASS" and o.get("independent_implementation") is True, "P05_ORACLE")
        pinned_optional(root, o.get("receipt", {}), "first_gate_result_oracle_receipt")
        firewalls(target, True, True)
    elif profile == "P06_TERMINAL_PERSISTED":
        req(len(terminal) >= 1, "P06_NO_TERMINAL")
        ctx = target.get("transition_context", {}).get("last_terminal_first_gate", {})
        req(ctx.get("shard_id") and ctx.get("first_gate_order"), "P06_CONTEXT")
        match = [r for r in terminal if r.get("shard_id")==ctx.get("shard_id") and r.get("first_gate_order")==ctx.get("first_gate_order")]
        req(len(match)==1, "P06_TERMINAL_NOT_UNIQUE")
        req(match[0].get("first_gate_result_receipt") is not None, "P06_RESULT_RECEIPT_MISSING")
        firewalls(target, True, True)
    elif profile == "P07_FIFO_PENDING_SCORER_REUSABLE":
        req(oldest is not None and scorer.get("status") == "PARITY_PASS" and scorer.get("independent_oracle_pass") is True, "P07_SCORER_OR_FIFO")
        firewalls(target, True, True)
    elif profile == "P08_BACKLOG_DRAINED_NEXT_GA1_FROZEN":
        req(not pending, "P08_PENDING_REMAINS")
        req(len(terminal) == len(rows) and len(rows) < 60, "P08_TERMINAL_OR_COUNT")
        n = target.get("next_preregistered_ga1") or ledger.get("next_preregistered_ga1")
        req(isinstance(n, dict) and n.get("shard_id") and n.get("status") in ("BLOCKED_BY_FIRST_GATE_BACKLOG","PREREGISTERED_PENDING_AUTHORIZATION"), "P08_NEXT_GA1")
        req(target.get("new_ga1_authorized") is False, "P08_GA1_ALREADY_AUTHORIZED")
        firewalls(target, True, True)
    elif profile == "P09_GA1_AUTHORIZED_NO_PENDING_FIRST_GATE":
        req(not pending, "P09_PENDING_FIRST_GATE")
        g = target.get("current_ga1", {})
        req(g.get("status") == "AUTHORIZED" and target.get("new_ga1_authorized") is True, "P09_GA1_NOT_AUTHORIZED")
        firewalls(target, True, True)
    elif profile == "P10_GA1_COMPLETE_UNPROMOTED":
        req(not pending, "P10_PENDING_FIRST_GATE")
        g = target.get("current_ga1", {})
        req(g.get("status") == "COMPLETE_UNPROMOTED", "P10_GA1_STATUS")
        pinned_optional(root, g.get("completion_receipt", {}), "current_ga1_completion")
        firewalls(target, True, True)
    elif profile == "P11_ALL_GA1_AND_FIRST_GATE_TERMINAL":
        req(not pending and len(rows) == 60 and len(terminal) == 60, "P11_COUNTS")
        req(counts.get("ga1_formally_completed_shards") == 60 and counts.get("first_gate_terminal") == 60, "P11_TARGET_COUNTS")
        firewalls(target, True, True)
    elif profile == "P12_EXPLICIT_POLICY_REQUIRED_BLOCK":
        req(target.get("policy_required") is True, "P12_POLICY_REQUIRED_FLAG")
        req(target.get("scientific_execution_authorized") is False, "P12_EXECUTION_MUST_BE_BLOCKED")
        firewalls(target, target.get("economic_pnl_read"), target.get("ga2_open"))
    elif profile == "P13_INTEGRITY_INCIDENT_ONLY":
        inc = target.get("integrity_incident", {})
        req(inc.get("status") == "OPEN" and inc.get("scientific_execution_authorized") is False, "P13_INCIDENT")
        req(target.get("holdout_open") is False, "P13_HOLDOUT")
    else:
        raise RuntimeError(f"UNSUPPORTED_GUARD_PROFILE:{profile}")


def derive(root: Path, target: dict, target_path: str):
    req(target.get("campaign") == CAMPAIGN, "CAMPAIGN_MISMATCH")
    k = target.get("execution_kernel", {})
    req(k.get("status") == "ACTIVE" and k.get("single_authoritative_action") is True, "KERNEL_NOT_ACTIVE_SINGLE")
    req(k.get("free_text_next_action_authoritative") is False, "FREE_TEXT_AUTHORITY_FORBIDDEN")

    kpins = {}
    for key in KERNEL_PIN_KEYS:
        node = k.get(key, {})
        kpins[key] = pin(root, node.get("path"), node.get("git_blob_sha1"), key)
    gov = load(root, k["governance"]["path"])
    emap = load(root, k["execution_map"]["path"])
    dled = load(root, k["decision_ledger"]["path"])
    workgraph = load(root, k["master_workgraph"]["path"])
    gaps = load(root, k["gap_register"]["path"])
    req(gov.get("status") == "FROZEN_ACTIVE" and gov.get("chat_runtime_role") == "EPHEMERAL_EXECUTOR_ONLY" and gov.get("no_memory_as_authority") is True, "GOVERNANCE_INVALID")
    req(emap.get("status") == "FROZEN_ACTIVE" and emap.get("campaign") == CAMPAIGN, "MAP_INVALID")
    req(dled.get("status") == "FROZEN_ACTIVE" and dled.get("campaign") == CAMPAIGN, "DECISION_LEDGER_INVALID")
    req(workgraph.get("status") == "FROZEN_ARCHITECTURE_MAP" and workgraph.get("campaign") == CAMPAIGN, "WORKGRAPH_INVALID")
    req(gaps.get("status") == "FROZEN_ACTIVE" and gaps.get("campaign") == CAMPAIGN, "GAP_REGISTER_INVALID")
    states = verify_map_coverage(emap)

    auth, ap = target.get("authority", {}), target.get("authority_pins", {})
    pair = {
        "primary_policy":"primary_policy_git_blob_sha1",
        "first_gate_multiplicity_contract":"multiplicity_contract_git_blob_sha1",
        "gate_a_plan":"gate_a_plan_git_blob_sha1",
        "minimal_dev_carrier_binding":"minimal_dev_carrier_binding_git_blob_sha1",
        "xau_m1_completion":"xau_m1_completion_git_blob_sha1",
        "promotion_ledger":"promotion_ledger_git_blob_sha1",
    }
    spins = {}
    for akey,pkey in pair.items(): spins[akey] = pin(root,auth.get(akey),ap.get(pkey),akey)
    policy=load(root,auth["primary_policy"]); contract=load(root,auth["first_gate_multiplicity_contract"]); gate=load(root,auth["gate_a_plan"]); binding=load(root,auth["minimal_dev_carrier_binding"]); completion=load(root,auth["xau_m1_completion"]); ledger=load(root,auth["promotion_ledger"])
    req(policy.get("status")=="ACTIVE_PRIMARY","POLICY_INVALID")
    req(contract.get("status")=="FROZEN_PRE_PNL","CONTRACT_INVALID")
    req(gate.get("state")=="FROZEN_PRE_PNL","GATE_PLAN_INVALID")
    req(binding.get("status")=="PASS","DEV_BINDING_INVALID")
    req(completion.get("status")=="PASS_DOUBLE_ORACLE","XAU_COMPLETION_INVALID")
    req(ledger.get("campaign")==CAMPAIGN,"PROMOTION_LEDGER_CAMPAIGN")
    facts=ledger_facts(ledger)

    sid=k.get("current_state"); req(sid in states,"UNKNOWN_CURRENT_STATE",sid)
    spec=states[sid]
    subject=resolve_subject(spec["subject_selector"],target,ledger,facts)
    validate_current_subject(target,subject,spec["subject_selector"])
    apply_guard(spec["guard_profile"],root,target,ledger,facts,binding)
    success=resolve_success(spec,target,ledger,facts)
    req(success in states,"RESOLVED_SUCCESS_UNKNOWN",success)

    ticket={
        "schema":"QROS_DETERMINISTIC_ACTION_TICKET_2.0",
        "campaign":CAMPAIGN,
        "frontier_version":target.get("version"),
        "frontier_target_path":target_path,
        "kernel_epoch":k.get("kernel_epoch"),
        "action_sequence":k.get("action_sequence"),
        "state_id":sid,
        "guard_profile":spec["guard_profile"],
        "subject_selector":spec["subject_selector"],
        "action_type":spec["authorized_action"],
        "subject":subject,
        "resolved_success_state":success,
        "failure_state":spec["failure_state"],
        "required_outputs":spec.get("required_outputs",[]),
        "forbidden_actions":spec.get("forbidden_actions",[]),
        "authority_pins":{**kpins,**spins},
        "map_coverage":{
            "guard_profiles_total":len(SUPPORTED_GUARDS),
            "guard_profiles_exact_match":True,
            "subject_selectors_supported":sorted(SUPPORTED_SUBJECTS),
            "success_state_selectors_exact_match":True,
        },
        "invariants":{
            "exactly_one_authoritative_action":True,
            "chat_memory_authoritative":False,
            "free_text_next_action_authoritative":False,
            "holdout_open":target.get("holdout_open"),
            "economic_pnl_read":target.get("economic_pnl_read"),
            "ga2_open":target.get("ga2_open"),
        }
    }
    ticket["ticket_id"]=h256(ticket)
    return ticket


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--out",required=True); ap.add_argument("--target",default=None); a=ap.parse_args()
    root=Path(a.repo_root).resolve(); stable_rel="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"; stable=load(root,stable_rel)
    if a.target:
        target_rel=a.target; target=load(root,target_rel)
        req(target.get("supersedes_frontier_version")==stable.get("current_version"),"CANDIDATE_PARENT_VERSION_MISMATCH")
        req(target.get("superseded_stable_pointer_blob_sha1")==git_blob(root/stable_rel),"CANDIDATE_PARENT_BLOB_MISMATCH")
    else:
        target_rel=stable.get("target_path"); target=load(root,target_rel)
        req(target.get("version")==stable.get("current_version"),"ACTIVE_VERSION_MISMATCH")
    t=derive(root,target,target_rel); out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(t,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","ticket_id":t["ticket_id"],"state_id":t["state_id"],"action_type":t["action_type"],"resolved_success_state":t["resolved_success_state"],"guard_profiles":t["map_coverage"]["guard_profiles_total"]},sort_keys=True)); return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
