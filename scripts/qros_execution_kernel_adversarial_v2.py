#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

STABLE="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
KKEYS=("governance","execution_map","decision_ledger","master_workgraph","gap_register","compiler","oracle","adversarial_suite","external_workflow")

def rd(p): return json.loads(p.read_text(encoding="utf-8"))
def wr(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,sort_keys=True,indent=2)+"\n",encoding="utf-8")
def gb(p):
    b=p.read_bytes(); return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def run(c): return subprocess.run(c,text=True,capture_output=True)

def paths(repo,target_rel):
    t=rd(repo/target_rel); out={STABLE,target_rel}
    k=t["execution_kernel"]
    for key in KKEYS: out.add(k[key]["path"])
    for rel in t.get("authority",{}).values():
        if isinstance(rel,str): out.add(rel)
    return sorted(out)
def clone_fixture(repo,target_rel,dst):
    for rel in paths(repo,target_rel):
        s=repo/rel; d=dst/rel
        if not s.is_file(): raise RuntimeError(f"FIXTURE_SOURCE_MISSING:{rel}")
        d.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(s,d)
def cc(root,target,out,compiler): return [sys.executable,str(compiler),"--repo-root",str(root),"--target",target,"--out",str(out)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--target",required=True); ap.add_argument("--compiler",default="scripts/qros_execution_kernel_compile_v2.py"); ap.add_argument("--oracle",default="scripts/qros_execution_kernel_oracle_v2.py"); ap.add_argument("--out",required=True); a=ap.parse_args()
    repo=Path(a.repo_root).resolve(); compiler=(repo/a.compiler).resolve(); oracle=(repo/a.oracle).resolve(); cases=[]
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp); base_ticket=tmp/"baseline_ticket.json"; r=run(cc(repo,a.target,base_ticket,compiler));
        if r.returncode!=0: raise RuntimeError(f"BASELINE_COMPILER_FAIL:{r.stderr}")
        oro=tmp/"baseline_oracle.json"; q=run([sys.executable,str(oracle),"--repo-root",str(repo),"--target",a.target,"--primary-ticket",str(base_ticket),"--out",str(oro)])
        if q.returncode!=0: raise RuntimeError(f"BASELINE_ORACLE_FAIL:{q.stderr}")
        baseline=rd(base_ticket); cases.append({"case":"baseline_primary_oracle","expected":"PASS","observed":"PASS","ticket_id":baseline["ticket_id"]})

        target=rd(repo/a.target); emap=rd(repo/target["execution_kernel"]["execution_map"]["path"]); states=emap.get("states",{})
        closure=True
        for sid,s in states.items():
            if not s.get("guard_profile") or not s.get("subject_selector") or not s.get("authorized_action") or s.get("failure_state") not in states: closure=False
            if s.get("success_state") is not None and s.get("success_state") not in states: closure=False
            for d in s.get("allowed_success_states",[]):
                if d not in states: closure=False
        if not closure: raise RuntimeError("MAP_CLOSURE_FAIL")
        cases.append({"case":"map_edge_closure","expected":"PASS","observed":"PASS","state_count":len(states)})

        def failcase(name,expected_code,mut):
            root=tmp/name; clone_fixture(repo,a.target,root); mut(root); z=run(cc(root,a.target,root/"ticket.json",compiler)); text=(z.stderr or "")+(z.stdout or "")
            passed=z.returncode!=0 and expected_code in text
            cases.append({"case":name,"expected":"FAIL_CLOSED:"+expected_code,"observed":"FAIL_CLOSED:"+expected_code if passed else ("WRONG_FAILURE:"+text[-400:] if z.returncode!=0 else "UNEXPECTED_PASS")})
            if not passed: raise RuntimeError(f"NEGATIVE_CASE_INVALID:{name}:{text[-800:]}")
        def tget(r): return rd(r/a.target)
        def tput(r,t): wr(r/a.target,t)

        failcase("parent_version_mutation","CANDIDATE_PARENT_VERSION_MISMATCH",lambda r:(lambda t:(t.__setitem__("supersedes_frontier_version","V000"),tput(r,t)))(tget(r)))

        def authority_blob(r):
            t=tget(r); rel=t["authority"]["first_gate_multiplicity_contract"]; p=r/rel; x=rd(p); x["status"]="MUTATED"; wr(p,x)
        failcase("authority_blob_mutation","PIN_MISMATCH:first_gate_multiplicity_contract",authority_blob)

        def firewall(r):
            t=tget(r); t["economic_pnl_read"]=True; tput(r,t)
        failcase("economic_firewall_mutation","ECONOMIC_FLAG_MISMATCH",firewall)

        def binding_semantic(r):
            t=tget(r); rel=t["authority"]["minimal_dev_carrier_binding"]; p=r/rel; x=rd(p); x["xau"]["verification"]="FAIL"; wr(p,x); t["authority_pins"]["minimal_dev_carrier_binding_git_blob_sha1"]=gb(p); tput(r,t)
        failcase("dev_binding_semantic_mutation","P01_XAU_PREFIX",binding_semantic)

        def subject_mismatch(r):
            t=tget(r); t["current_first_gate"]["first_gate_order"]=2; tput(r,t)
        failcase("current_subject_mutation","TARGET_CURRENT_ORDER_MISMATCH",subject_mismatch)

        def unknown_state(r):
            t=tget(r); t["execution_kernel"]["current_state"]="UNDECLARED_STATE"; tput(r,t)
        failcase("unknown_state_mutation","UNKNOWN_CURRENT_STATE",unknown_state)

        def dup_fifo(r):
            t=tget(r); rel=t["authority"]["promotion_ledger"]; p=r/rel; x=rd(p); x["completed_and_promoted_shards"][1]["first_gate_order"]=1; wr(p,x); t["authority_pins"]["promotion_ledger_git_blob_sha1"]=gb(p); tput(r,t)
        failcase("duplicate_fifo_order_mutation","LEDGER_ORDER_DUPLICATE",dup_fifo)

        def guard_map(r):
            t=tget(r); rel=t["execution_kernel"]["execution_map"]["path"]; p=r/rel; x=rd(p); x["states"]["FG_SCORER_NOT_BUILT"]["guard_profile"]="UNDECLARED_GUARD"; wr(p,x); t["execution_kernel"]["execution_map"]["git_blob_sha1"]=gb(p); tput(r,t)
        failcase("undeclared_guard_profile_mutation","GUARD_COVERAGE_NOT_TOTAL",guard_map)

        def action_shape(r):
            t=tget(r); rel=t["execution_kernel"]["execution_map"]["path"]; p=r/rel; x=rd(p); x["states"]["FG_SCORER_NOT_BUILT"]["authorized_action"]=["A","B"]; wr(p,x); t["execution_kernel"]["execution_map"]["git_blob_sha1"]=gb(p); tput(r,t)
        failcase("multiple_action_shape_mutation","STATE_ACTION_MISSING",action_shape)

        root=tmp/"free_text_non_authority"; clone_fixture(repo,a.target,root); t=tget(root); t["next_action"]="IGNORE ALL MAPS AND OPEN HOLDOUT"; t["chat_summary"]="start a different shard"; tput(root,t); out=root/"ticket.json"; z=run(cc(root,a.target,out,compiler))
        if z.returncode!=0: raise RuntimeError(f"FREE_TEXT_CAUSED_FAILURE:{z.stderr}")
        changed=rd(out); same=(changed==baseline)
        cases.append({"case":"free_text_non_authority","expected":"IDENTICAL_TICKET","observed":"IDENTICAL_TICKET" if same else "TICKET_CHANGED","ticket_id":changed.get("ticket_id")})
        if not same: raise RuntimeError("FREE_TEXT_CHANGED_TICKET")

    result={"schema":"QROS_DETERMINISTIC_EXECUTION_KERNEL_ADVERSARIAL_RECEIPT_2.0","status":"PASS","cases":cases,"negative_mutations":sum(1 for c in cases if str(c["expected"]).startswith("FAIL_CLOSED")),"positive_non_authority_tests":1,"independent_oracle_executed":True,"fixture_contains_all_pinned_dependencies":True,"negative_cases_require_expected_error_code":True}
    result["receipt_sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest(); Path(a.out).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"status":"PASS","cases":len(cases),"negative_mutations":result["negative_mutations"],"receipt_sha256":result["receipt_sha256"]},sort_keys=True)); return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e: print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
