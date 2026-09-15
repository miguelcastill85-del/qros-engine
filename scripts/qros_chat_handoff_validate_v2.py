#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
import qros_chat_handoff_validate_v1 as core

ALLOWED_ROLES={
"stable_scientific_pointer","stable_target","candidate_validation_receipt","active_validation_receipt","active_execution_validation_receipt",
"kernel_governance","execution_map","decision_ledger","master_workgraph","gap_register","kernel_compiler","kernel_oracle","kernel_adversarial_suite","kernel_mode_resolver","kernel_external_workflow","kernel_compiler_v2","kernel_oracle_v2",
"primary_policy","multiplicity_contract","gate_a_plan","minimal_dev_carrier_binding","xau_m1_completion","promotion_ledger","rise_fixed_point_receipt"
}

def extra_checks(root: Path, candidate_pointer: str):
    cp=core.readj(root,candidate_pointer); hp=cp["handoff_path"]; h=core.readj(root,hp)
    entries=h.get("bootstrap_manifest",{}).get("entries",[]); roles={e.get("role") for e in entries}; reqroles=set(h.get("bootstrap_manifest",{}).get("required_roles",[]))
    core.req(roles==ALLOWED_ROLES,"BOOTSTRAP_ALLOWED_ROLE_SET",f"actual={sorted(roles)}")
    core.req(reqroles==ALLOWED_ROLES,"BOOTSTRAP_REQUIRED_ROLE_SET",f"actual={sorted(reqroles)}")
    bm=h.get("bootstrap_manifest",{})
    core.req(bm.get("normal_execution_repository_search_allowed") is False,"BOOTSTRAP_SEARCH_POLICY")
    core.req(bm.get("dependency_resolution_rule")=="ONLY_EXACT_PINNED_BOOTSTRAP_ROLES_UNTIL_EXECUTION_CAPSULE_PASS","BOOTSTRAP_RESOLUTION_RULE")
    ar=h.get("authority_precedence",{})
    core.req(ar.get("stale_handoff_rule")=="FAIL_CLOSED_REGENERATE_FROM_NEW_STABLE_POINTER_DO_NOT_MERGE","STALE_RULE")
    core.req(ar.get("target_latch_conflict_resolution")=="STABLE_POINTER_AND_PINNED_VALIDATION_RECEIPTS_OVERRIDE_PREPROMOTION_TARGET_LATCH_FIELDS_ONLY","TARGET_LATCH_RULE")
    core.req(h.get("architecture_defect",{}).get("normal_execution_repository_search_allowed") is False,"CAPSULE_SEARCH_POLICY")
    core.req(h.get("resume_protocol",{}).get("on_stable_pointer_mismatch")=="STOP_USING_HANDOFF_TICKET_AND_REGENERATE_FROM_NEW_STABLE_AUTHORITY","RESUME_STALE_RULE")
    core.req(h.get("resume_protocol",{}).get("closed_work_replay_allowed") is False,"REPLAY_POLICY")
    return h

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--candidate-pointer",default="control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json"); a=ap.parse_args(); root=Path(a.root)
    try:
        extra_checks(root,a.candidate_pointer)
        res=core.validate(root,a.candidate_pointer); res["validator_version"]="2"; res["allowed_role_count"]=len(ALLOWED_ROLES)
        print(json.dumps(res,sort_keys=True,separators=(",",":"))); return 0
    except core.AuditError as e:
        print(json.dumps({"status":"FAIL","code":e.code,"detail":e.detail},sort_keys=True,separators=(",",":"))); return 2
if __name__=="__main__": raise SystemExit(main())
