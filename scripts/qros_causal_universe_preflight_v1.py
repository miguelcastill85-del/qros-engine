#!/usr/bin/env python3
import argparse, json, sys

REQUIRED_BAR_CLOCK = ("timezone_authority","session_calendar","bar_origin","dst_policy","partial_bar_policy")
REQUIRED_PARITY_TRUE = ("independent_enumerator_required","independent_signal_oracle_required","independent_execution_oracle_required")

def fail(code, msg, errors):
    errors.append({"code": code, "message": msg})

def product_count(axes):
    if not isinstance(axes, dict) or not axes:
        return None
    n = 1
    for _, vals in axes.items():
        if not isinstance(vals, list) or len(vals) == 0:
            return None
        n *= len(vals)
    return n

def validate(doc):
    e=[]
    if doc.get("scientific_state") != "PREREGISTERED_NO_RESULTS":
        fail("STATE_NOT_PREREGISTERED_NO_RESULTS","scientific_state must be PREREGISTERED_NO_RESULTS",e)

    fw=doc.get("economic_firewall",{})
    for k in ("economic_pnl_read","holdout_open","ga2_open","economic_scoring_authorized"):
        if fw.get(k) is not False:
            fail("ECONOMIC_FIREWALL_OPEN",f"{k} must be false",e)

    hyp=doc.get("causal_hypothesis",{})
    if hyp.get("observable_before_entry") is not True:
        fail("HYPOTHESIS_NOT_CAUSALLY_OBSERVABLE","causal_hypothesis.observable_before_entry must be true",e)
    for k in ("mechanism_id","genealogy_id","mechanism_fingerprint"):
        if not hyp.get(k):
            fail("HYPOTHESIS_IDENTITY_MISSING",f"{k} missing",e)

    clock=doc.get("bar_clock",{})
    for k in REQUIRED_BAR_CLOCK:
        if not clock.get(k):
            fail("BAR_CLOCK_BINDING_MISSING",f"bar_clock.{k} missing",e)

    feats=doc.get("features",[])
    if not isinstance(feats,list) or not feats:
        fail("FEATURE_BINDING_MISSING","features must be a non-empty list",e)
    else:
        seen=set()
        for i,f in enumerate(feats):
            if not isinstance(f,dict):
                fail("FEATURE_RECORD_INVALID",f"features[{i}] must be an object",e)
                continue
            fid=f.get("feature_id")
            if not fid:
                fail("FEATURE_ID_MISSING",f"features[{i}].feature_id missing",e)
                continue
            if fid in seen:
                fail("FEATURE_ID_DUPLICATE",f"duplicate feature_id {fid}",e)
            seen.add(fid)
            av=f.get("availability")
            if av not in ("CLOSED_BAR","CURRENT_TICK_CAUSAL","STATIC_PREREGISTERED"):
                fail("FEATURE_AVAILABILITY_INVALID",f"{fid}: availability={av}",e)
            off=f.get("closed_bar_offset")
            if av=="CLOSED_BAR" and (type(off) is not int or off < 1):
                fail("LOOKAHEAD_CLOSED_BAR_OFFSET",f"{fid}: CLOSED_BAR requires closed_bar_offset>=1",e)
            if f.get("uses_future_data") is True:
                fail("LOOKAHEAD_EXPLICIT",f"{fid}: uses_future_data=true",e)
            elif f.get("uses_future_data") is not False:
                fail("FUTURE_DEPENDENCY_UNDECLARED",f"{fid}: uses_future_data must be explicitly false",e)
            tf=f.get("source_timeframe")
            if not isinstance(tf,str) or not tf.strip():
                fail("FEATURE_TIMEFRAME_MISSING",f"{fid}: source_timeframe missing or empty",e)
            deps=f.get("depends_on")
            if not isinstance(deps,list) or not all(isinstance(x,str) and x.strip() for x in deps):
                fail("FEATURE_DEPENDENCY_INVALID",f"{fid}: depends_on must be a list of nonempty IDs",e)

    uni=doc.get("universe",{})
    axes=uni.get("parameter_axes")
    raw=product_count(axes)
    if raw is None:
        fail("UNIVERSE_AXES_INVALID","parameter_axes must be non-empty lists",e)
    declared=uni.get("expected_raw_count")
    if raw is not None and declared != raw:
        fail("UNIVERSE_COUNT_MISMATCH",f"expected_raw_count={declared}, computed={raw}",e)
    depth=uni.get("interaction_depth")
    if type(depth) is not int or depth < 0:
        fail("INTERACTION_DEPTH_INVALID","interaction_depth must be integer >=0",e)
    if not uni.get("interaction_depth_rationale"):
        fail("INTERACTION_DEPTH_RATIONALE_MISSING","interaction_depth_rationale missing",e)
    if uni.get("parameter_neighborhood_preregistered") is not True:
        fail("PARAMETER_NEIGHBORHOOD_NOT_FROZEN","parameter neighborhoods/boundaries must be preregistered",e)
    if uni.get("semantic_normalization_exact_only") is not True:
        fail("SEMANTIC_DEDUPE_NOT_EXACT","semantic normalization/dedupe must be exact-only pre-PnL",e)
    if uni.get("near_duplicate_reduces_n_tests") is not False:
        fail("NEAR_DUPLICATE_NTESTS_LEAK","near duplicates may not reduce N_TESTS without exact proof",e)

    gen=doc.get("genealogy_collision",{})
    if gen.get("mechanism_fingerprint_required") is not True:
        fail("GENEALOGY_FINGERPRINT_MISSING","mechanism fingerprint gate must be enabled",e)
    if gen.get("exact_event_mask_collision_check_pre_pnl") is not True:
        fail("CROSS_GENEALOGY_COLLISION_UNCHECKED","exact event-mask collision check must run before PnL",e)
    if gen.get("collision_changes_genealogy_without_new_preregistration") is not False:
        fail("GENEALOGY_REWRITE_RISK","collision cannot silently rewrite genealogy",e)

    par=doc.get("parity",{})
    for k in REQUIRED_PARITY_TRUE:
        if par.get(k) is not True:
            fail("PARITY_REQUIREMENT_MISSING",f"parity.{k} must be true",e)
    if par.get("primary_and_oracle_source_must_differ") is not True:
        fail("PARITY_NOT_INDEPENDENT","primary_and_oracle_source_must_differ must be true",e)

    mult=doc.get("multiplicity",{})
    if not mult.get("n_tests_authority"):
        fail("N_TESTS_AUTHORITY_MISSING","multiplicity.n_tests_authority missing",e)
    if mult.get("campaign_level_null_calibration_required") is not True:
        fail("GLOBAL_NULL_CALIBRATION_MISSING","campaign-level null calibration must be required",e)
    if mult.get("cross_shard_duplicate_policy") not in ("GLOBAL_EXACT_MASK_ALIAS","COUNT_EACH_IF_NOT_EXACT_PROVEN"):
        fail("CROSS_SHARD_DUPLICATE_POLICY_INVALID","unsupported cross_shard_duplicate_policy",e)

    ext=doc.get("external_oracle",{})
    if ext.get("consumes_frozen_anchors_for_execution") is not True:
        fail("EXTERNAL_EXECUTION_ORACLE_UNBOUND","external execution oracle must consume frozen anchors",e)
    if ext.get("may_generate_candidates") is not False:
        fail("EXTERNAL_CANDIDATE_GENERATION_FORBIDDEN","external engine may not generate candidates in validation mode",e)
    if ext.get("may_select_candidates") is not False:
        fail("EXTERNAL_CANDIDATE_SELECTION_FORBIDDEN","external engine may not select candidates in validation mode",e)

    return {"status":"PASS" if not e else "FAIL","admission_level":"DECLARATIVE_PREFLIGHT_ONLY_NO_CAUSAL_OR_PARITY_PROOF","error_count":len(e),"errors":e}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--json",action="store_true")
    a=ap.parse_args()
    with open(a.spec,encoding="utf-8") as f:
        doc=json.load(f)
    r=validate(doc)
    if a.json:
        print(json.dumps(r,sort_keys=True,separators=(",",":")))
    else:
        print(r["status"])
        for x in r["errors"]:
            print(x["code"],x["message"])
    return 0 if r["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
