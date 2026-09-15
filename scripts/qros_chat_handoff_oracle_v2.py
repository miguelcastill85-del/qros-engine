#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

ALLOWED={
"stable_scientific_pointer","stable_target","candidate_validation_receipt","active_validation_receipt","active_execution_validation_receipt",
"kernel_governance","execution_map","decision_ledger","master_workgraph","gap_register","kernel_compiler","kernel_oracle","kernel_adversarial_suite","kernel_mode_resolver","kernel_external_workflow","kernel_compiler_v2","kernel_oracle_v2",
"primary_policy","multiplicity_contract","gate_a_plan","minimal_dev_carrier_binding","xau_m1_completion","promotion_ledger","rise_fixed_point_receipt"
}
def sh(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def rb(r,p): return (r/p).read_bytes()
def rj(r,p): return json.loads(rb(r,p).decode())
def bad(c,d=""): print(json.dumps({"status":"FAIL","code":c,"detail":d},sort_keys=True,separators=(",",":"))); raise SystemExit(2)
def ck(x,c,d=""):
    if not x: bad(c,d)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--candidate-pointer",default="control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json"); a=ap.parse_args(); r=Path(a.root)
    try:
        cp=rj(r,a.candidate_pointer); hp=cp["handoff_path"]; ck(sh(rb(r,hp))==cp["handoff_git_blob_sha1"],"O_HANDOFF_PIN")
        h=rj(r,hp); ck(h["schema"]=="QROS_PUBLIC1000_CHAT_MIGRATION_HANDOFF_2.0","O_SCHEMA")
        es=h["bootstrap_manifest"]["entries"]; dm={e["role"]:e for e in es}
        ck(len(dm)==len(es),"O_DUP_ROLE"); ck(set(dm)==ALLOWED,"O_ALLOWED_SET"); ck(set(h["bootstrap_manifest"]["required_roles"])==ALLOWED,"O_REQUIRED_SET")
        ck(h["bootstrap_manifest"]["normal_execution_repository_search_allowed"] is False,"O_SEARCH_POLICY")
        for role,e in dm.items(): ck(sh(rb(r,e["path"]))==e["git_blob_sha1"],"O_DEP_PIN",role)
        st=rj(r,dm["stable_scientific_pointer"]["path"]); ex=h["authority"]["stable_scientific_pointer_expected"]
        ck(sh(rb(r,dm["stable_scientific_pointer"]["path"]))==ex["git_blob_sha1"],"O_STALE")
        ck(st["current_version"]==ex["version"] and st["target_path"]==ex["target_path"] and st["target_git_blob_sha1"]==ex["target_git_blob_sha1"],"O_STABLE_BIND")
        tg=rj(r,dm["stable_target"]["path"]); ck(sh(rb(r,dm["stable_target"]["path"]))==dm["stable_target"]["git_blob_sha1"],"O_TARGET_PIN")
        ck(tg["scientific_execution_authorized"] is False and st["scientific_execution_authorized"] is True,"O_LATCH_PRECEDENCE")
        pr=h["authority_precedence"]; ck(pr["stale_handoff_rule"]=="FAIL_CLOSED_REGENERATE_FROM_NEW_STABLE_POINTER_DO_NOT_MERGE","O_STALE_RULE"); ck(pr["target_latch_conflict_resolution"]=="STABLE_POINTER_AND_PINNED_VALIDATION_RECEIPTS_OVERRIDE_PREPROMOTION_TARGET_LATCH_FIELDS_ONLY","O_LATCH_RULE")
        t=h["machine_ticket"]; ck(t["ticket_id"]==st["machine_action_ticket_id"] and t["action"]==st["machine_action_type"] and t["subject"]==st["machine_subject"],"O_TICKET")
        ck(t["action"]=="BUILD_FIRST_GATE_SCORER","O_ACTION"); ck(all(st[k] is False for k in ["economic_pnl_read","ga2_open","holdout_open","first_gate_execution_authorized","new_ga1_authorized"]),"O_FIREWALL")
        for key,role,status in [("candidate_validation_receipt","candidate_validation_receipt","candidate_validation_status"),("active_validation_receipt","active_validation_receipt","active_validation_status"),("active_execution_validation_receipt","active_execution_validation_receipt","active_execution_validation_status")]:
            ck(st[status]=="PASS","O_VALID_STATUS",status); e=dm[role]; ck(st[key]["path"]==e["path"] and st[key]["git_blob_sha1"]==e["git_blob_sha1"],"O_VALID_PIN",role); rr=rj(r,e["path"]); ck(rr["status"]=="PASS" and rr["ticket"]["ticket_id"]==t["ticket_id"],"O_VALID_RECEIPT",role)
        wg=rj(r,dm["master_workgraph"]["path"]); gr=rj(r,dm["gap_register"]["path"]); pl=rj(r,dm["promotion_ledger"]["path"]); mc=rj(r,dm["multiplicity_contract"]["path"])
        ck(wg["current_node"]=="W09_FIRST_GATE_SCORER_BUILD" and gr["current_blocking_gap"]=="GAP-S03","O_NODE_GAP")
        ck(pl["current_first_gate_order"]==1 and pl["current_first_gate_shard_id"]==t["subject"]["shard_id"] and pl["first_gate_pending_count"]==8,"O_FIFO")
        ck(mc["status"]=="FROZEN_PRE_PNL" and mc["cross_shard_error_budget"]["per_shard_q_exact"]=="1/1200","O_MULTIPLICITY")
        ck(h["architecture_defect"]["execution_capsule_status"]=="NOT_IMPLEMENTED" and h["architecture_defect"]["normal_execution_repository_search_allowed"] is False,"O_CAPSULE_GAP")
        cur=rj(r,h["authority"]["current_chat_handoff_pointer_path"]); mode="ACTIVE" if cur.get("handoff_path")==hp and cur.get("handoff_git_blob_sha1")==cp["handoff_git_blob_sha1"] else "CANDIDATE"
        print(json.dumps({"status":"PASS","mode":mode,"oracle_version":"2","handoff_git_blob_sha1":cp["handoff_git_blob_sha1"],"stable_version":st["current_version"],"ticket_id":t["ticket_id"],"dependency_count":len(dm)},sort_keys=True,separators=(",",":")))
    except (KeyError,FileNotFoundError,json.JSONDecodeError) as e: bad("O_STRUCTURE",str(e))
if __name__=="__main__": main()
