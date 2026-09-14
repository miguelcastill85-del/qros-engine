#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

STABLE = "control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"


def canonical(x): return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
def h256(x): return hashlib.sha256(canonical(x)).hexdigest()
def git_blob(p: Path):
    b=p.read_bytes(); return hashlib.sha1(b"blob "+str(len(b)).encode("ascii")+b"\0"+b).hexdigest()
def req(c, code, detail=None):
    if not c: raise RuntimeError(code if detail is None else f"{code}:{detail}")
def load(root: Path, rel: str):
    req(isinstance(rel,str) and rel and not rel.startswith("/") and ".." not in Path(rel).parts,"INVALID_PATH",rel)
    p=root/rel; req(p.is_file(),"MISSING",rel)
    return json.loads(p.read_text(encoding="utf-8"))
def pin(root: Path, node: dict, label: str):
    req(isinstance(node,dict),"PIN_NODE_MISSING",label)
    rel,want=node.get("path"),node.get("git_blob_sha1")
    req(rel and want,"PIN_MISSING",label); p=root/rel; req(p.is_file(),"PIN_FILE_MISSING",label)
    got=git_blob(p); req(got==want,"PIN_MISMATCH",f"{label}:{got}!={want}"); return got


def verify_kernel_pins(root: Path, target: dict):
    k=target.get("execution_kernel",{}); req(k.get("status")=="ACTIVE_CANDIDATE" or k.get("status")=="ACTIVE","KERNEL_STATUS")
    names=("governance","execution_map","decision_ledger","master_workgraph","gap_register","compiler","oracle","adversarial_suite","mode_resolver","external_workflow")
    out={n:pin(root,k.get(n),n) for n in names}
    tc=k.get("transitive_core",{})
    out["core_compiler_v2"]=pin(root,tc.get("compiler_v2"),"core_compiler_v2")
    out["core_oracle_v2"]=pin(root,tc.get("oracle_v2"),"core_oracle_v2")
    return out


def blocker_ticket(root: Path, target: dict, target_rel: str, pins: dict):
    b=target.get("pre_scientific_blocker")
    req(isinstance(b,dict) and b.get("status")=="OPEN_BLOCKING","BLOCKER_INVALID")
    req(b.get("blocking_class") in {"EVIDENCE_BINDING_REQUIRED","INTEGRITY_REPAIR_REQUIRED","POLICY_REQUIRED"},"BLOCKER_CLASS")
    req(target.get("economic_pnl_read") is False and target.get("holdout_open") is False and target.get("ga2_open") is False,"BLOCKER_FIREWALL")
    evidence_pins={}
    for i,node in enumerate(b.get("evidence_pins",[])):
        evidence_pins[f"blocker_evidence_{i}"]=pin(root,node,f"blocker_evidence_{i}")
    t={
      "schema":"QROS_DETERMINISTIC_ACTION_TICKET_3.0",
      "campaign":target.get("campaign"),
      "frontier_version":target.get("version"),
      "frontier_target_path":target_rel,
      "kernel_epoch":target.get("execution_kernel",{}).get("kernel_epoch"),
      "action_sequence":target.get("execution_kernel",{}).get("action_sequence"),
      "state_id":"PRE_SCIENTIFIC_BLOCKER",
      "guard_profile":b.get("guard_profile"),
      "action_type":b.get("authorized_action"),
      "subject":b.get("subject"),
      "resolved_success_state":b.get("success_state"),
      "failure_state":"FAIL_CLOSED",
      "required_outputs":b.get("required_outputs",[]),
      "forbidden_actions":b.get("forbidden_actions",[]),
      "authority_pins":{**pins,**evidence_pins},
      "invariants":{"exactly_one_authoritative_action":True,"pre_scientific_blocker_preempts_science":True,"economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"chat_memory_authoritative":False,"free_text_next_action_authoritative":False}
    }
    req(all([t["guard_profile"],t["action_type"],t["subject"],t["resolved_success_state"]]),"BLOCKER_TICKET_FIELD_MISSING")
    t["ticket_id"]=h256(t); return t


def core_ticket(root: Path, target_rel: str|None, target: dict):
    core=target["execution_kernel"]["transitive_core"]["compiler_v2"]["path"]
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)/"ticket.json"
        cmd=[sys.executable,str(root/core),"--repo-root",str(root),"--out",str(out)]
        if target_rel is not None: cmd.extend(["--target",target_rel])
        r=subprocess.run(cmd,text=True,capture_output=True)
        req(r.returncode==0,"CORE_COMPILER_FAIL",r.stderr[-1000:])
        return json.loads(out.read_text(encoding="utf-8"))


def executable_latch(root: Path, stable: dict, ticket: dict):
    req(stable.get("active_validation_status")=="PASS","EXEC_LATCH_ACTIVE_VALIDATION_NOT_PASS")
    req(stable.get("scientific_execution_authorized") is True,"EXEC_LATCH_SCIENTIFIC_NOT_AUTHORIZED")
    req(stable.get("authorized_action_scope")=="MACHINE_ACTION_TICKET_ONLY","EXEC_LATCH_SCOPE")
    r=stable.get("active_validation_receipt",{}); req(isinstance(r,dict),"EXEC_LATCH_RECEIPT_NODE")
    pin(root,r,"active_validation_receipt")
    req(stable.get("machine_action_ticket_id")==ticket.get("ticket_id"),"EXEC_LATCH_TICKET_ID")
    req(stable.get("machine_action_type")==ticket.get("action_type"),"EXEC_LATCH_ACTION_TYPE")
    req(stable.get("machine_state_id")==ticket.get("state_id"),"EXEC_LATCH_STATE_ID")
    req(stable.get("machine_subject")==ticket.get("subject"),"EXEC_LATCH_SUBJECT")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--out",required=True); ap.add_argument("--target"); ap.add_argument("--validation-only",action="store_true"); a=ap.parse_args()
    root=Path(a.repo_root).resolve(); stable=load(root,STABLE)
    if a.target:
        req(a.validation_only,"TARGET_REQUIRES_VALIDATION_ONLY")
        target_rel=a.target; target=load(root,target_rel)
        req(target.get("supersedes_frontier_version")==stable.get("current_version"),"CANDIDATE_PARENT_VERSION_MISMATCH")
        want=target.get("superseded_stable_pointer_blob_sha1"); req(want and git_blob(root/STABLE)==want,"CANDIDATE_PARENT_BLOB_MISMATCH")
    else:
        target_rel=stable.get("target_path"); target=load(root,target_rel)
        req(target.get("version")==stable.get("current_version"),"ACTIVE_VERSION_MISMATCH")
        req(git_blob(root/target_rel)==stable.get("target_git_blob_sha1"),"ACTIVE_TARGET_BLOB_MISMATCH")
    pins=verify_kernel_pins(root,target)
    if target.get("pre_scientific_blocker") is not None:
        ticket=blocker_ticket(root,target,target_rel,pins)
    else:
        ticket=core_ticket(root,target_rel if a.target else None,target)
    if not a.validation_only:
        executable_latch(root,stable,ticket)
    Path(a.out).write_text(json.dumps(ticket,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","validation_only":a.validation_only,"state_id":ticket.get("state_id"),"action_type":ticket.get("action_type"),"ticket_id":ticket.get("ticket_id")},sort_keys=True)); return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
