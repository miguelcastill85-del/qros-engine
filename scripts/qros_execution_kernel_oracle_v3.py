#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

STABLE="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def h256(x): return hashlib.sha256(canon(x)).hexdigest()
def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def must(c,code,detail=None):
    if not c: raise ValueError(code if detail is None else f"{code}:{detail}")
def load(root:Path,rel:str):
    must(isinstance(rel,str) and rel and not rel.startswith("/") and ".." not in Path(rel).parts,"ORACLE_BAD_PATH",rel)
    p=root/rel; must(p.is_file(),"ORACLE_MISSING",rel); return json.loads(p.read_text(encoding="utf-8"))
def pinned(root:Path,node,label):
    must(isinstance(node,dict),"ORACLE_PIN_NODE",label); rel,want=node.get("path"),node.get("git_blob_sha1")
    must(rel and want,"ORACLE_PIN_ABSENT",label); p=root/rel; must(p.is_file(),"ORACLE_PIN_FILE",label)
    got=blob(p); must(got==want,"ORACLE_PIN_DIFF",f"{label}:{got}!={want}"); return got

def kernel_pins(root,target):
    k=target.get("execution_kernel",{}); must(k.get("status") in {"ACTIVE_CANDIDATE","ACTIVE"},"ORACLE_KERNEL_STATUS")
    names=("governance","execution_map","decision_ledger","master_workgraph","gap_register","compiler","oracle","adversarial_suite","mode_resolver","external_workflow")
    out={n:pinned(root,k.get(n),n) for n in names}; tc=k.get("transitive_core",{})
    out["core_compiler_v2"]=pinned(root,tc.get("compiler_v2"),"core_compiler_v2")
    out["core_oracle_v2"]=pinned(root,tc.get("oracle_v2"),"core_oracle_v2")
    return out

def blocker_expected(root,target,target_rel,pins):
    b=target.get("pre_scientific_blocker"); must(isinstance(b,dict) and b.get("status")=="OPEN_BLOCKING","ORACLE_BLOCKER_INVALID")
    must(b.get("blocking_class") in {"EVIDENCE_BINDING_REQUIRED","INTEGRITY_REPAIR_REQUIRED","POLICY_REQUIRED"},"ORACLE_BLOCKER_CLASS")
    must(target.get("economic_pnl_read") is False and target.get("holdout_open") is False and target.get("ga2_open") is False,"ORACLE_BLOCKER_FIREWALL")
    ep={}
    for i,n in enumerate(b.get("evidence_pins",[])): ep[f"blocker_evidence_{i}"]=pinned(root,n,f"blocker_evidence_{i}")
    t={"schema":"QROS_DETERMINISTIC_ACTION_TICKET_3.0","campaign":target.get("campaign"),"frontier_version":target.get("version"),"frontier_target_path":target_rel,"kernel_epoch":target.get("execution_kernel",{}).get("kernel_epoch"),"action_sequence":target.get("execution_kernel",{}).get("action_sequence"),"state_id":"PRE_SCIENTIFIC_BLOCKER","guard_profile":b.get("guard_profile"),"action_type":b.get("authorized_action"),"subject":b.get("subject"),"resolved_success_state":b.get("success_state"),"failure_state":"FAIL_CLOSED","required_outputs":b.get("required_outputs",[]),"forbidden_actions":b.get("forbidden_actions",[]),"authority_pins":{**pins,**ep},"invariants":{"exactly_one_authoritative_action":True,"pre_scientific_blocker_preempts_science":True,"economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"chat_memory_authoritative":False,"free_text_next_action_authoritative":False}}
    must(t["guard_profile"] and t["action_type"] and t["subject"] and t["resolved_success_state"],"ORACLE_BLOCKER_FIELDS"); t["ticket_id"]=h256(t); return t

def core_expected(root,target_rel,target,primary_ticket):
    oracle=target["execution_kernel"]["transitive_core"]["oracle_v2"]["path"]
    with tempfile.TemporaryDirectory() as td:
        prim=Path(td)/"primary.json"; out=Path(td)/"oracle.json"; prim.write_text(json.dumps(primary_ticket,sort_keys=True,indent=2)+"\n")
        cmd=[sys.executable,str(root/oracle),"--repo-root",str(root),"--primary-ticket",str(prim),"--out",str(out)]
        if target_rel is not None: cmd.extend(["--target",target_rel])
        r=subprocess.run(cmd,text=True,capture_output=True); must(r.returncode==0,"ORACLE_CORE_FAIL",r.stderr[-1000:])
        return primary_ticket

def latch(root,stable,ticket):
    must(stable.get("active_validation_status")=="PASS","ORACLE_EXEC_ACTIVE_VALIDATION_NOT_PASS")
    must(stable.get("scientific_execution_authorized") is True,"ORACLE_EXEC_SCIENTIFIC_NOT_AUTHORIZED")
    must(stable.get("authorized_action_scope")=="MACHINE_ACTION_TICKET_ONLY","ORACLE_EXEC_SCOPE")
    pinned(root,stable.get("active_validation_receipt"),"active_validation_receipt")
    must(stable.get("machine_action_ticket_id")==ticket.get("ticket_id"),"ORACLE_EXEC_TICKET_ID")
    must(stable.get("machine_action_type")==ticket.get("action_type"),"ORACLE_EXEC_ACTION_TYPE")
    must(stable.get("machine_state_id")==ticket.get("state_id"),"ORACLE_EXEC_STATE_ID")
    must(stable.get("machine_subject")==ticket.get("subject"),"ORACLE_EXEC_SUBJECT")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--primary-ticket",required=True); ap.add_argument("--out",required=True); ap.add_argument("--target"); ap.add_argument("--validation-only",action="store_true"); a=ap.parse_args()
    root=Path(a.repo_root).resolve(); stable=load(root,STABLE); got=json.loads(Path(a.primary_ticket).read_text(encoding="utf-8"))
    if a.target:
        must(a.validation_only,"ORACLE_TARGET_REQUIRES_VALIDATION_ONLY"); target_rel=a.target; target=load(root,target_rel)
        must(target.get("supersedes_frontier_version")==stable.get("current_version"),"ORACLE_CANDIDATE_PARENT_VERSION")
        must(target.get("superseded_stable_pointer_blob_sha1")==blob(root/STABLE),"ORACLE_CANDIDATE_PARENT_BLOB")
    else:
        target_rel=stable.get("target_path"); target=load(root,target_rel)
        must(target.get("version")==stable.get("current_version"),"ORACLE_ACTIVE_VERSION")
        must(blob(root/target_rel)==stable.get("target_git_blob_sha1"),"ORACLE_ACTIVE_TARGET_BLOB")
    pins=kernel_pins(root,target)
    if target.get("pre_scientific_blocker") is not None: exp=blocker_expected(root,target,target_rel,pins)
    else: exp=core_expected(root,target_rel if a.target else None,target,got)
    must(got==exp,"PRIMARY_ORACLE_TICKET_MISMATCH")
    if not a.validation_only: latch(root,stable,exp)
    rec={"schema":"QROS_DETERMINISTIC_ACTION_ORACLE_RECEIPT_3.0","status":"PASS","validation_only":a.validation_only,"independent_implementation":True,"imports_primary_compiler":False,"frontier_version":exp.get("frontier_version"),"state_id":exp.get("state_id"),"action_type":exp.get("action_type"),"ticket_id":exp.get("ticket_id")}; rec["receipt_sha256"]=h256(rec)
    Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+"\n"); print(json.dumps(rec,sort_keys=True)); return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
