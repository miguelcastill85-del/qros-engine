#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

STABLE="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
CANDIDATE="control/QROS_PUBLIC_1000_EXECUTION_KERNEL_CANDIDATE_POINTER.json"

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p,o): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(o,sort_keys=True,indent=2)+"\n",encoding="utf-8")
def blob(p):
    b=Path(p).read_bytes(); return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def run(cmd): return subprocess.run(cmd,text=True,capture_output=True)
def errcode(r):
    try: return json.loads((r.stderr or "").strip().splitlines()[-1]).get("error","")
    except Exception: return (r.stderr or "")[-1000:]
def must(c,msg):
    if not c: raise RuntimeError(msg)

def compile_cmd(root,target,out,validation=True):
    cmd=[sys.executable,str(root/"scripts/qros_execution_kernel_compile_v3.py"),"--repo-root",str(root),"--out",str(out)]
    if target: cmd += ["--target",target]
    if validation: cmd += ["--validation-only"]
    return cmd

def copyrepo(repo,dst): shutil.copytree(repo,dst,ignore=shutil.ignore_patterns('.git','__pycache__'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--target",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    repo=Path(a.repo_root).resolve(); target_rel=a.target; cases=[]
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); base_ticket=td/"base_ticket.json"
        r=run(compile_cmd(repo,target_rel,base_ticket,True)); must(r.returncode==0,f"baseline compiler: {r.stderr}")
        oracle=td/"oracle.json"; ro=run([sys.executable,str(repo/"scripts/qros_execution_kernel_oracle_v3.py"),"--repo-root",str(repo),"--target",target_rel,"--validation-only","--primary-ticket",str(base_ticket),"--out",str(oracle)])
        must(ro.returncode==0,f"baseline oracle: {ro.stderr}"); base=load(base_ticket); cases.append({"case":"baseline_primary_oracle","expected":"PASS","observed":"PASS","ticket_id":base["ticket_id"]})

        def neg(name,mutate,expected,command_kind="candidate"):
            root=td/name; copyrepo(repo,root); mutate(root)
            out=root/"ticket.json"
            if command_kind=="candidate": rr=run(compile_cmd(root,target_rel,out,True))
            elif command_kind=="candidate_no_validation": rr=run(compile_cmd(root,target_rel,out,False))
            else: rr=run(compile_cmd(root,None,out,False))
            code=errcode(rr); ok=rr.returncode!=0 and expected in code
            cases.append({"case":name,"expected":f"FAIL_CLOSED:{expected}","observed":f"FAIL_CLOSED:{code}" if rr.returncode!=0 else "UNEXPECTED_PASS"}); must(ok,f"{name} wrong failure: {code}")

        def m_parent_version(root):
            t=load(root/target_rel); t["supersedes_frontier_version"]="IMPOSSIBLE_PARENT"; dump(root/target_rel,t)
        neg("parent_version_mismatch",m_parent_version,"CANDIDATE_PARENT_VERSION_MISMATCH")

        def m_parent_blob(root):
            t=load(root/target_rel); t["superseded_stable_pointer_blob_sha1"]="0"*40; dump(root/target_rel,t)
        neg("parent_blob_mismatch",m_parent_blob,"CANDIDATE_PARENT_BLOB_MISMATCH")

        neg("target_without_validation_only",lambda r:None,"TARGET_REQUIRES_VALIDATION_ONLY","candidate_no_validation")

        def m_firewall(root):
            t=load(root/target_rel); t["economic_pnl_read"]=True; dump(root/target_rel,t)
        neg("blocker_economic_firewall",m_firewall,"BLOCKER_FIREWALL")

        def m_evidence(root):
            t=load(root/target_rel); n=t["pre_scientific_blocker"]["evidence_pins"][0]; p=root/n["path"]; o=load(p); o["__adversarial_mutation__"]=True; dump(p,o)
        neg("blocker_evidence_pin_mutation",m_evidence,"PIN_MISMATCH:blocker_evidence_0")

        def active_root(name,validation="PENDING",authorized=False,scope="MACHINE_ACTION_TICKET_ONLY",with_receipt=False,wrong_ticket=False):
            root=td/name; copyrepo(repo,root); t=load(root/target_rel); s=load(root/STABLE)
            s.update({"current_version":t["version"],"target_path":target_rel,"target_git_blob_sha1":blob(root/target_rel),"active_validation_status":validation,"scientific_execution_authorized":authorized,"authorized_action_scope":scope,"machine_action_ticket_id":base["ticket_id"],"machine_action_type":base["action_type"],"machine_state_id":base["state_id"],"machine_subject":base["subject"]})
            if wrong_ticket: s["machine_action_ticket_id"]="0"*64
            if with_receipt:
                rp="control/TEST_ACTIVE_VALIDATION_RECEIPT.json"; dump(root/rp,{"status":"PASS"}); s["active_validation_receipt"]={"path":rp,"git_blob_sha1":blob(root/rp)}
            dump(root/STABLE,s); return root

        root=active_root("active_pending")
        rr=run(compile_cmd(root,None,root/"ticket.json",False)); code=errcode(rr); must(rr.returncode!=0 and "EXEC_LATCH_ACTIVE_VALIDATION_NOT_PASS" in code,"active pending latch"); cases.append({"case":"active_validation_pending_latch","expected":"FAIL_CLOSED:EXEC_LATCH_ACTIVE_VALIDATION_NOT_PASS","observed":f"FAIL_CLOSED:{code}"})

        root=active_root("active_not_authorized",validation="PASS",authorized=False)
        rr=run(compile_cmd(root,None,root/"ticket.json",False)); code=errcode(rr); must(rr.returncode!=0 and "EXEC_LATCH_SCIENTIFIC_NOT_AUTHORIZED" in code,"not authorized latch"); cases.append({"case":"scientific_authorization_latch","expected":"FAIL_CLOSED:EXEC_LATCH_SCIENTIFIC_NOT_AUTHORIZED","observed":f"FAIL_CLOSED:{code}"})

        root=active_root("active_missing_receipt",validation="PASS",authorized=True)
        rr=run(compile_cmd(root,None,root/"ticket.json",False)); code=errcode(rr); must(rr.returncode!=0 and "PIN_NODE_MISSING:active_validation_receipt" in code,"missing receipt latch"); cases.append({"case":"active_receipt_pin_required","expected":"FAIL_CLOSED:PIN_NODE_MISSING:active_validation_receipt","observed":f"FAIL_CLOSED:{code}"})

        root=active_root("active_ticket_mismatch",validation="PASS",authorized=True,with_receipt=True,wrong_ticket=True)
        rr=run(compile_cmd(root,None,root/"ticket.json",False)); code=errcode(rr); must(rr.returncode!=0 and "EXEC_LATCH_TICKET_ID" in code,"ticket mismatch latch"); cases.append({"case":"stable_ticket_binding","expected":"FAIL_CLOSED:EXEC_LATCH_TICKET_ID","observed":f"FAIL_CLOSED:{code}"})

        root=td/"free_text"; copyrepo(repo,root); t=load(root/target_rel); t["next_action"]="MALICIOUS_FREE_TEXT_DO_SOMETHING_ELSE"; dump(root/target_rel,t)
        rr=run(compile_cmd(root,target_rel,root/"ticket.json",True)); must(rr.returncode==0,rr.stderr); ft=load(root/"ticket.json"); must(ft==base,"free text changed ticket"); cases.append({"case":"free_text_non_authority","expected":"IDENTICAL_TICKET","observed":"IDENTICAL_TICKET","ticket_id":ft["ticket_id"]})

        root=td/"future_version"; copyrepo(repo,root); t=load(root/target_rel); t["version"]="V999999_GENERIC_TEST"; dump(root/target_rel,t)
        cp=load(root/CANDIDATE); cp["candidate_version"]=t["version"]; cp["candidate_target_git_blob_sha1"]=blob(root/target_rel); dump(root/CANDIDATE,cp)
        rr=run(compile_cmd(root,target_rel,root/"ticket.json",True)); must(rr.returncode==0,rr.stderr); fut=load(root/"ticket.json"); must(fut["frontier_version"]=="V999999_GENERIC_TEST" and fut["action_type"]==base["action_type"],"future version hardcode detected"); cases.append({"case":"generic_future_version_no_hardcode","expected":"PASS","observed":"PASS","frontier_version":fut["frontier_version"]})

    res={"schema":"QROS_DETERMINISTIC_EXECUTION_KERNEL_ADVERSARIAL_RECEIPT_3.0","status":"PASS","cases":cases,"negative_cases_require_expected_error_code":True,"negative_mutations":sum(1 for c in cases if str(c["expected"]).startswith("FAIL_CLOSED")),"positive_non_authority_tests":1,"generic_future_version_test":True,"independent_oracle_executed":True}
    res["receipt_sha256"]=hashlib.sha256(json.dumps(res,sort_keys=True,separators=(",",":")).encode()).hexdigest(); Path(a.out).write_text(json.dumps(res,sort_keys=True,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"status":"PASS","cases":len(cases),"negative_mutations":res["negative_mutations"],"receipt_sha256":res["receipt_sha256"]},sort_keys=True)); return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
