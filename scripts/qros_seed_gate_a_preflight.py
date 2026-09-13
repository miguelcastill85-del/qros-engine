#!/usr/bin/env python3
import argparse, hashlib, json, re, sys

HEX64=re.compile(r"^[0-9a-f]{64}$")

REQUIRED_TRUE=[
    "causal_scope_frozen",
    "all_applicable_dimensions_audited",
    "finite_domains_frozen",
    "constraint_graph_frozen",
    "universe_enumeration_complete",
    "semantic_dedupe_complete",
    "post_expansion_rise_fixed_point",
    "config_hash_freeze",
    "independent_enumerator_parity_pass",
    "execution_semantics_frozen",
    "execution_unit_binding_pass",
    "cost_model_frozen",
    "data_execution_ready"
]
REQUIRED_ROOTS=[
    "signal_universe_root_sha256",
    "management_universe_root_sha256",
    "execution_universe_root_sha256",
    "stress_universe_root_sha256",
    "full_freeze_descriptor_root_sha256"
]

def evaluate(p):
    errors=[]
    if p.get("compiler_policy") != "governance/QROS_SEED_UNIVERSE_COMPILER_POLICY_v1.1.json":
        errors.append("COMPILER_POLICY_NOT_CANONICAL_V1_1")
    for k in REQUIRED_TRUE:
        if p.get(k) is not True: errors.append("REQUIRED_TRUE_MISSING:"+k)
    for k in REQUIRED_ROOTS:
        v=p.get(k)
        if not isinstance(v,str) or not HEX64.fullmatch(v): errors.append("INVALID_OR_MISSING_SHA256:"+k)
    for k in ("raw_signal_config_count","semantic_signal_config_count","management_profile_count"):
        v=p.get(k)
        if not isinstance(v,int) or v <= 0: errors.append("INVALID_COUNT:"+k)
    if p.get("raw_signal_config_count") != p.get("semantic_signal_config_count") + p.get("semantic_alias_count",0):
        errors.append("SEMANTIC_ACCOUNTING_MISMATCH")
    if p.get("enumerator_symmetric_difference_count") != 0:
        errors.append("ENUMERATOR_SET_PARITY_FAIL")
    if p.get("rise_zero_delta_round_count",0) < 2:
        errors.append("RISE_FIXED_POINT_INSUFFICIENT_ZERO_ROUNDS")
    if p.get("development_pnl_already_observed") is True:
        errors.append("PRE_FREEZE_DEVELOPMENT_EXPOSURE")
    if p.get("holdout_open") is True:
        errors.append("HOLDOUT_MUST_REMAIN_CLOSED_AT_GATE_A_PREFLIGHT")
    decision="GATE_A_AUTHORIZED" if not errors else "GATE_A_FORBIDDEN"
    return {"schema":"QROS_SEED_GATE_A_PREFLIGHT_RECEIPT_1.0","status":"PASS" if not errors else "FAIL","decision":decision,"seed":p.get("seed"),"errors":errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out",required=True); ns=ap.parse_args()
    p=json.load(open(ns.input,encoding="utf-8")); r=evaluate(p)
    payload=json.dumps(r,sort_keys=True,separators=(",",":"))
    r["receipt_sha256"]=hashlib.sha256(payload.encode()).hexdigest()
    open(ns.out,"w",encoding="utf-8").write(json.dumps(r,sort_keys=True,separators=(",",":")))
    print(r["decision"])
    return 0 if r["decision"]=="GATE_A_AUTHORIZED" else 2

if __name__=="__main__": sys.exit(main())
