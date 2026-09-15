#!/usr/bin/env python3
import argparse, hashlib, json, sys
from pathlib import Path

def bsha(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def rb(root,p): return (root/p).read_bytes()
def rj(root,p): return json.loads(rb(root,p).decode())
def die(code,detail=""):
    print(json.dumps({"status":"FAIL","code":code,"detail":detail},sort_keys=True,separators=(",",":"))); raise SystemExit(2)
def ck(x,code,detail=""):
    if not x: die(code,detail)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--candidate-pointer",default="control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json"); a=ap.parse_args(); root=Path(a.root)
    try:
        cp=rj(root,a.candidate_pointer); hp=cp["handoff_path"]; hs=cp["handoff_git_blob_sha1"]
        ck(bsha(rb(root,hp))==hs,"ORACLE_HANDOFF_PIN")
        h=rj(root,hp); ck(h.get("schema")=="QROS_PUBLIC1000_CHAT_MIGRATION_HANDOFF_2.0","ORACLE_SCHEMA")
        entries=h["bootstrap_manifest"]["entries"]; d={e["role"]:e for e in entries}
        ck(len(d)==len(entries),"ORACLE_DUP_ROLE"); ck(set(d)==set(h["bootstrap_manifest"]["required_roles"]),"ORACLE_ROLE_SET")
        for role,e in d.items(): ck(bsha(rb(root,e["path"]))==e["git_blob_sha1"],"ORACLE_DEP_PIN",role)
        st=rj(root,d["stable_scientific_pointer"]["path"]); ex=h["authority"]["stable_scientific_pointer_expected"]
        ck(bsha(rb(root,d["stable_scientific_pointer"]["path"]))==ex["git_blob_sha1"],"ORACLE_STALE")
        ck(st["current_version"]==ex["version"] and st["target_path"]==ex["target_path"] and st["target_git_blob_sha1"]==ex["target_git_blob_sha1"],"ORACLE_STABLE_BIND")
        tg=rj(root,ex["target_path"]); ck(bsha(rb(root,ex["target_path"]))==ex["target_git_blob_sha1"],"ORACLE_TARGET_PIN")
        t=h["machine_ticket"]
        ck((t["ticket_id"],t["action"],t["state_id"],t["guard_profile"],t["subject"])==(st["machine_action_ticket_id"],st["machine_action_type"],st["machine_state_id"],st["machine_guard_profile"],st["machine_subject"]),"ORACLE_TICKET")
        ck(t["action"]=="BUILD_FIRST_GATE_SCORER","ORACLE_ACTION")
        ck(st["scientific_execution_authorized"] is True,"ORACLE_LATCH")
        ck(all(st[k] is False for k in ["economic_pnl_read","ga2_open","holdout_open","first_gate_execution_authorized","new_ga1_authorized"]),"ORACLE_FIREWALL")
        for key,role,status in [("candidate_validation_receipt","candidate_validation_receipt","candidate_validation_status"),("active_validation_receipt","active_validation_receipt","active_validation_status"),("active_execution_validation_receipt","active_execution_validation_receipt","active_execution_validation_status")]:
            ck(st[status]=="PASS","ORACLE_VALIDATION_STATUS",status); e=d[role]; ck(st[key]["path"]==e["path"] and st[key]["git_blob_sha1"]==e["git_blob_sha1"],"ORACLE_VALIDATION_PIN",role); rr=rj(root,e["path"]); ck(rr["status"]=="PASS" and rr["ticket"]["ticket_id"]==t["ticket_id"],"ORACLE_VALIDATION_RECEIPT",role)
        wg=rj(root,d["master_workgraph"]["path"]); gr=rj(root,d["gap_register"]["path"]); pl=rj(root,d["promotion_ledger"]["path"]); mc=rj(root,d["multiplicity_contract"]["path"])
        ck(wg["current_node"]=="W09_FIRST_GATE_SCORER_BUILD" and wg["automatic_next_action"]=="BUILD_FIRST_GATE_SCORER","ORACLE_WG")
        ck(gr["current_blocking_gap"]=="GAP-S03","ORACLE_GAP")
        ck(pl["current_first_gate_order"]==1 and pl["current_first_gate_shard_id"]==t["subject"]["shard_id"],"ORACLE_FIFO")
        ck(mc["status"]=="FROZEN_PRE_PNL" and mc["cross_shard_error_budget"]["per_shard_q_exact"]=="1/1200","ORACLE_MULTIPLICITY")
        p=h["authority_precedence"]; ck(p["scientific_authority"]=="CURRENT_FRONTIER_POINTER" and p["immutable_candidate_target_role"]=="HISTORICAL_CANDIDATE_EVIDENCE_NOT_DYNAMIC_LATCH_AUTHORITY" and p["dynamic_latch_authority"]=="STABLE_SCIENTIFIC_POINTER_PLUS_PINNED_EXTERNAL_VALIDATION_RECEIPTS","ORACLE_PRECEDENCE")
        ck(h["architecture_defect"]["execution_capsule_status"]=="NOT_IMPLEMENTED","ORACLE_CAPSULE_STATE")
        cur=rj(root,h["authority"]["current_chat_handoff_pointer_path"]); mode="ACTIVE" if cur.get("handoff_path")==hp and cur.get("handoff_git_blob_sha1")==hs else "CANDIDATE"
        print(json.dumps({"status":"PASS","mode":mode,"handoff_git_blob_sha1":hs,"stable_version":st["current_version"],"ticket_id":t["ticket_id"],"action":t["action"],"dependency_count":len(d)},sort_keys=True,separators=(",",":")))
    except (KeyError,FileNotFoundError,json.JSONDecodeError) as e: die("ORACLE_STRUCTURE",str(e))
if __name__=="__main__": main()
