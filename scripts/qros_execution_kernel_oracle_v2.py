#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

CAMP="PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
TERMINAL={"PASS_FIRST_GATE","REJECTED_FIRST_GATE","INVALID_FIRST_GATE","BLOCKED_BY_INFRASTRUCTURE"}
GUARDS={"P01_PRE_ECONOMIC_SCORER_NOT_BUILT","P02_PRE_ECONOMIC_SCORER_PRIMARY_BUILT","P03_PRE_ECONOMIC_SCORER_PARITY_PASS","P04_ECONOMIC_EXECUTION_COMPLETE_UNVALIDATED","P05_ECONOMIC_RESULT_ORACLE_PASS","P06_TERMINAL_PERSISTED","P07_FIFO_PENDING_SCORER_REUSABLE","P08_BACKLOG_DRAINED_NEXT_GA1_FROZEN","P09_GA1_AUTHORIZED_NO_PENDING_FIRST_GATE","P10_GA1_COMPLETE_UNPROMOTED","P11_ALL_GA1_AND_FIRST_GATE_TERMINAL","P12_EXPLICIT_POLICY_REQUIRED_BLOCK","P13_INTEGRITY_INCIDENT_ONLY"}
SUBJECTS={"OLDEST_PENDING_FIRST_GATE","LAST_TERMINAL_FIRST_GATE","NEXT_PREREGISTERED_GA1","CURRENT_GA1","CAMPAIGN"}
SELECTORS={"SEL01_LEDGER_AFTER_TERMINAL"}
KKEYS=("governance","execution_map","decision_ledger","master_workgraph","gap_register","compiler","oracle","adversarial_suite","external_workflow")

def cj(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def h(x): return hashlib.sha256(cj(x)).hexdigest()
def gb(p):
    b=p.read_bytes(); return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def ok(x,c):
    if not x: raise ValueError(c)
def valid_rel(r): return isinstance(r,str) and bool(r) and not r.startswith("/") and ".." not in Path(r).parts
def rd(root,r):
    ok(valid_rel(r),f"ORACLE_BAD_PATH:{r!r}"); p=root/r; ok(p.is_file(),f"ORACLE_MISSING:{r}"); return json.loads(p.read_text(encoding="utf-8"))
def pcheck(root,r,w,label):
    ok(valid_rel(r) and isinstance(w,str) and w,f"ORACLE_PIN_ABSENT:{label}"); p=root/r; ok(p.is_file(),f"ORACLE_PIN_FILE_ABSENT:{label}"); g=gb(p); ok(g==w,f"ORACLE_PIN_DIFF:{label}:{g}!={w}"); return g
def domain(x): return (x.get("asset"),x.get("side"),x.get("timeframe"))

def audit_map(m):
    st=m.get("states",{}); ok(isinstance(st,dict) and st,"ORACLE_MAP_EMPTY")
    dg={v.get("guard_profile") for v in st.values()}; ds={v.get("subject_selector") for v in st.values()}; dx={v.get("success_state_selector") for v in st.values() if v.get("success_state_selector")}
    ok(dg==GUARDS,"ORACLE_GUARD_COVERAGE"); ok(ds<=SUBJECTS and None not in ds,"ORACLE_SUBJECT_COVERAGE"); ok(dx==SELECTORS,"ORACLE_SELECTOR_COVERAGE")
    for sid,s in st.items():
        ok(isinstance(s.get("authorized_action"),str) and s.get("authorized_action"),f"ORACLE_ACTION:{sid}")
        ok(s.get("failure_state") in st,f"ORACLE_FAILURE_EDGE:{sid}")
        if s.get("success_state") is not None: ok(s.get("success_state") in st,f"ORACLE_SUCCESS_EDGE:{sid}")
        else:
            ok(s.get("success_state_selector") in SELECTORS,f"ORACLE_SELECTOR_EDGE:{sid}")
            for d in s.get("allowed_success_states",[]): ok(d in st,f"ORACLE_DYNAMIC_EDGE:{sid}:{d}")
    return st

def facts(led):
    rows=led.get("completed_and_promoted_shards"); ok(isinstance(rows,list),"ORACLE_LEDGER_ROWS")
    orders=[r.get("first_gate_order") for r in rows]; ok(all(isinstance(v,int) and v>0 for v in orders),"ORACLE_ORDER_TYPE"); ok(orders==sorted(orders),"ORACLE_ORDER_SORT"); ok(len(orders)==len(set(orders)),"ORACLE_ORDER_DUP")
    pen=[r for r in rows if r.get("first_gate_status")=="PENDING"]; term=[r for r in rows if r.get("first_gate_status") in TERMINAL]
    ok(len(pen)==led.get("first_gate_pending_count"),"ORACLE_PENDING_COUNT"); ok(len(term)==led.get("first_gate_terminal_count"),"ORACLE_TERMINAL_COUNT")
    oldest=min(pen,key=lambda r:r["first_gate_order"]) if pen else None
    return rows,pen,term,oldest

def receipt_pin(root,node,label):
    ok(isinstance(node,dict),f"ORACLE_STRUCT_RECEIPT:{label}"); return pcheck(root,node.get("path"),node.get("git_blob_sha1"),label)
def firewall(t,e=None,g=None):
    ok(t.get("holdout_open") is False,"ORACLE_HOLDOUT_OPEN")
    if e is not None: ok(t.get("economic_pnl_read") is e,"ORACLE_ECON_FLAG")
    if g is not None: ok(t.get("ga2_open") is g,"ORACLE_GA2_FLAG")

def subject(sel,t,led,f):
    rows,pen,term,old=f
    if sel=="OLDEST_PENDING_FIRST_GATE":
        ok(old is not None,"ORACLE_NO_PENDING_SUBJECT"); return {k:old.get(k) for k in ("asset","side","timeframe","shard_id","first_gate_order","distinct_mask_classes")}
    if sel=="LAST_TERMINAL_FIRST_GATE":
        c=t.get("transition_context",{}).get("last_terminal_first_gate"); ok(isinstance(c,dict),"ORACLE_LAST_TERM_CONTEXT")
        q=[r for r in term if r.get("shard_id")==c.get("shard_id") and r.get("first_gate_order")==c.get("first_gate_order")]; ok(len(q)==1,"ORACLE_LAST_TERM_UNIQUE"); r=q[0]; return {k:r.get(k) for k in ("asset","side","timeframe","shard_id","first_gate_order","distinct_mask_classes")}
    if sel=="NEXT_PREREGISTERED_GA1":
        n=t.get("next_preregistered_ga1") or led.get("next_preregistered_ga1"); ok(isinstance(n,dict) and n.get("shard_id"),"ORACLE_NEXT_GA1"); return {k:n.get(k) for k in ("asset","side","timeframe","shard_id","config_root_sha256","status")}
    if sel=="CURRENT_GA1":
        g=t.get("current_ga1"); ok(isinstance(g,dict) and g.get("shard_id"),"ORACLE_CURRENT_GA1"); return {k:g.get(k) for k in ("asset","side","timeframe","shard_id","config_root_sha256","status")}
    if sel=="CAMPAIGN": return {"campaign":CAMP}
    raise ValueError(f"ORACLE_UNKNOWN_SUBJECT:{sel}")

def suc(spec,t,led,f):
    if spec.get("success_state") is not None: return spec["success_state"]
    ok(spec.get("success_state_selector")=="SEL01_LEDGER_AFTER_TERMINAL","ORACLE_BAD_SUCCESS_SELECTOR")
    rows,pen,term,old=f
    if pen: return "FG_NEXT_PENDING_READY"
    c=t.get("verified_counts",{})
    if c.get("ga1_formally_completed_shards")==60 and len(term)==60: return "GA1_ALL_60_COMPLETE"
    n=t.get("next_preregistered_ga1") or led.get("next_preregistered_ga1")
    if isinstance(n,dict) and n.get("shard_id"): return "FIRST_GATE_BACKLOG_DRAINED"
    raise ValueError("ORACLE_SUCCESS_NO_MATCH")

def guard(pr,root,t,led,f,b):
    rows,pen,term,old=f; s=t.get("first_gate_scorer",{}); c=t.get("verified_counts",{})
    if pr=="P01_PRE_ECONOMIC_SCORER_NOT_BUILT":
        ok(old is not None and t.get("first_gate_data_ready") is True,"O_P01_DATA"); ok(s.get("status")=="NOT_BUILT","O_P01_SCORER"); firewall(t,False,False); ok(b.get("full_history_completion_required_for_first_gate") is False,"O_P01_FULL"); ok(b.get("xau",{}).get("verification")=="PASS_BYTE_EXACT_PREFIX" and b.get("nqx",{}).get("verification")=="PASS_BYTE_EXACT_PREFIX","O_P01_PREFIX")
    elif pr=="P02_PRE_ECONOMIC_SCORER_PRIMARY_BUILT":
        ok(old is not None and s.get("status")=="PRIMARY_BUILT","O_P02"); pcheck(root,s.get("primary_source_path"),s.get("primary_source_git_blob_sha1"),"scorer_primary"); firewall(t,False,False)
    elif pr=="P03_PRE_ECONOMIC_SCORER_PARITY_PASS":
        ok(old is not None and s.get("status")=="PARITY_PASS" and s.get("independent_oracle_pass") is True,"O_P03"); pcheck(root,s.get("primary_source_path"),s.get("primary_source_git_blob_sha1"),"scorer_primary"); pcheck(root,s.get("oracle_source_path"),s.get("oracle_source_git_blob_sha1"),"scorer_oracle"); receipt_pin(root,s.get("parity_receipt",{}),"scorer_parity"); firewall(t,False,False)
    elif pr=="P04_ECONOMIC_EXECUTION_COMPLETE_UNVALIDATED":
        ok(old is not None and s.get("status")=="PARITY_PASS","O_P04_FIFO"); ex=t.get("first_gate_execution",{}); ok(ex.get("status")=="COMPLETE_UNVALIDATED","O_P04_STATUS"); receipt_pin(root,ex.get("execution_receipt",{}),"fg_execution"); firewall(t,True,True)
    elif pr=="P05_ECONOMIC_RESULT_ORACLE_PASS":
        ok(old is not None,"O_P05_FIFO"); o=t.get("first_gate_result_oracle",{}); ok(o.get("status")=="PASS" and o.get("independent_implementation") is True,"O_P05_ORACLE"); receipt_pin(root,o.get("receipt",{}),"fg_result_oracle"); firewall(t,True,True)
    elif pr=="P06_TERMINAL_PERSISTED":
        ok(term,"O_P06_TERM"); ctx=t.get("transition_context",{}).get("last_terminal_first_gate",{}); q=[r for r in term if r.get("shard_id")==ctx.get("shard_id") and r.get("first_gate_order")==ctx.get("first_gate_order")]; ok(len(q)==1 and q[0].get("first_gate_result_receipt") is not None,"O_P06_CONTEXT"); firewall(t,True,True)
    elif pr=="P07_FIFO_PENDING_SCORER_REUSABLE":
        ok(old is not None and s.get("status")=="PARITY_PASS" and s.get("independent_oracle_pass") is True,"O_P07"); firewall(t,True,True)
    elif pr=="P08_BACKLOG_DRAINED_NEXT_GA1_FROZEN":
        ok(not pen and len(term)==len(rows) and len(rows)<60,"O_P08_COUNTS"); n=t.get("next_preregistered_ga1") or led.get("next_preregistered_ga1"); ok(isinstance(n,dict) and n.get("shard_id") and n.get("status") in ("BLOCKED_BY_FIRST_GATE_BACKLOG","PREREGISTERED_PENDING_AUTHORIZATION"),"O_P08_NEXT"); ok(t.get("new_ga1_authorized") is False,"O_P08_AUTH"); firewall(t,True,True)
    elif pr=="P09_GA1_AUTHORIZED_NO_PENDING_FIRST_GATE":
        ok(not pen,"O_P09_PENDING"); g=t.get("current_ga1",{}); ok(g.get("status")=="AUTHORIZED" and t.get("new_ga1_authorized") is True,"O_P09_AUTH"); firewall(t,True,True)
    elif pr=="P10_GA1_COMPLETE_UNPROMOTED":
        ok(not pen,"O_P10_PENDING"); g=t.get("current_ga1",{}); ok(g.get("status")=="COMPLETE_UNPROMOTED","O_P10_STATUS"); receipt_pin(root,g.get("completion_receipt",{}),"current_ga1_completion"); firewall(t,True,True)
    elif pr=="P11_ALL_GA1_AND_FIRST_GATE_TERMINAL":
        ok(not pen and len(rows)==60 and len(term)==60,"O_P11_COUNTS"); ok(c.get("ga1_formally_completed_shards")==60 and c.get("first_gate_terminal")==60,"O_P11_TARGET"); firewall(t,True,True)
    elif pr=="P12_EXPLICIT_POLICY_REQUIRED_BLOCK":
        ok(t.get("policy_required") is True and t.get("scientific_execution_authorized") is False,"O_P12_BLOCK"); firewall(t,t.get("economic_pnl_read"),t.get("ga2_open"))
    elif pr=="P13_INTEGRITY_INCIDENT_ONLY":
        i=t.get("integrity_incident",{}); ok(i.get("status")=="OPEN" and i.get("scientific_execution_authorized") is False,"O_P13_INCIDENT"); ok(t.get("holdout_open") is False,"O_P13_HOLDOUT")
    else: raise ValueError(f"ORACLE_UNSUPPORTED_GUARD:{pr}")

def derive(root,t,tp):
    ok(t.get("campaign")==CAMP,"ORACLE_CAMPAIGN"); k=t.get("execution_kernel",{}); ok(k.get("status")=="ACTIVE" and k.get("single_authoritative_action") is True and k.get("free_text_next_action_authoritative") is False,"ORACLE_KERNEL")
    kp={}
    for name in KKEYS:
        n=k.get(name,{}); kp[name]=pcheck(root,n.get("path"),n.get("git_blob_sha1"),name)
    gov=rd(root,k["governance"]["path"]); m=rd(root,k["execution_map"]["path"]); dl=rd(root,k["decision_ledger"]["path"]); wg=rd(root,k["master_workgraph"]["path"]); gr=rd(root,k["gap_register"]["path"])
    ok(gov.get("status")=="FROZEN_ACTIVE" and gov.get("chat_runtime_role")=="EPHEMERAL_EXECUTOR_ONLY" and gov.get("no_memory_as_authority") is True,"ORACLE_GOV"); ok(m.get("status")=="FROZEN_ACTIVE" and m.get("campaign")==CAMP,"ORACLE_MAP"); ok(dl.get("status")=="FROZEN_ACTIVE" and dl.get("campaign")==CAMP,"ORACLE_LEDGER2"); ok(wg.get("status")=="FROZEN_ARCHITECTURE_MAP" and wg.get("campaign")==CAMP,"ORACLE_WORKGRAPH"); ok(gr.get("status")=="FROZEN_ACTIVE" and gr.get("campaign")==CAMP,"ORACLE_GAPS")
    states=audit_map(m)
    au=t.get("authority",{}); ap=t.get("authority_pins",{}); pairs={"primary_policy":"primary_policy_git_blob_sha1","first_gate_multiplicity_contract":"multiplicity_contract_git_blob_sha1","gate_a_plan":"gate_a_plan_git_blob_sha1","minimal_dev_carrier_binding":"minimal_dev_carrier_binding_git_blob_sha1","xau_m1_completion":"xau_m1_completion_git_blob_sha1","promotion_ledger":"promotion_ledger_git_blob_sha1"}; sp={}
    for x,y in pairs.items(): sp[x]=pcheck(root,au.get(x),ap.get(y),x)
    pol=rd(root,au["primary_policy"]); con=rd(root,au["first_gate_multiplicity_contract"]); gp=rd(root,au["gate_a_plan"]); bind=rd(root,au["minimal_dev_carrier_binding"]); comp=rd(root,au["xau_m1_completion"]); led=rd(root,au["promotion_ledger"])
    ok(pol.get("status")=="ACTIVE_PRIMARY","ORACLE_POLICY"); ok(con.get("status")=="FROZEN_PRE_PNL","ORACLE_CONTRACT"); ok(gp.get("state")=="FROZEN_PRE_PNL","ORACLE_GATE"); ok(bind.get("status")=="PASS","ORACLE_BINDING"); ok(comp.get("status")=="PASS_DOUBLE_ORACLE","ORACLE_XAU"); ok(led.get("campaign")==CAMP,"ORACLE_PROMOTION")
    f=facts(led); sid=k.get("current_state"); ok(sid in states,"ORACLE_STATE"); spec=states[sid]; sub=subject(spec["subject_selector"],t,led,f)
    if spec["subject_selector"]=="OLDEST_PENDING_FIRST_GATE":
        cf=t.get("current_first_gate",{}); ok(cf.get("shard_id")==sub.get("shard_id") and cf.get("first_gate_order")==sub.get("first_gate_order") and domain(cf)==(sub.get("asset"),sub.get("side"),sub.get("timeframe")),"ORACLE_CURRENT_SUBJECT")
    guard(spec["guard_profile"],root,t,led,f,bind); success=suc(spec,t,led,f); ok(success in states,"ORACLE_RESOLVED_SUCCESS")
    z={"schema":"QROS_DETERMINISTIC_ACTION_TICKET_2.0","campaign":CAMP,"frontier_version":t.get("version"),"frontier_target_path":tp,"kernel_epoch":k.get("kernel_epoch"),"action_sequence":k.get("action_sequence"),"state_id":sid,"guard_profile":spec["guard_profile"],"subject_selector":spec["subject_selector"],"action_type":spec["authorized_action"],"subject":sub,"resolved_success_state":success,"failure_state":spec["failure_state"],"required_outputs":spec.get("required_outputs",[]),"forbidden_actions":spec.get("forbidden_actions",[]),"authority_pins":{**kp,**sp},"map_coverage":{"guard_profiles_total":len(GUARDS),"guard_profiles_exact_match":True,"subject_selectors_supported":sorted(SUBJECTS),"success_state_selectors_exact_match":True},"invariants":{"exactly_one_authoritative_action":True,"chat_memory_authoritative":False,"free_text_next_action_authoritative":False,"holdout_open":t.get("holdout_open"),"economic_pnl_read":t.get("economic_pnl_read"),"ga2_open":t.get("ga2_open")}}
    z["ticket_id"]=h(z); return z

def main():
    a=argparse.ArgumentParser(); a.add_argument("--repo-root",required=True); a.add_argument("--primary-ticket",required=True); a.add_argument("--out",required=True); a.add_argument("--target",default=None); x=a.parse_args(); root=Path(x.repo_root).resolve(); sr="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"; st=rd(root,sr)
    if x.target:
        tp=x.target; t=rd(root,tp); ok(t.get("supersedes_frontier_version")==st.get("current_version"),"ORACLE_PARENT_VERSION"); ok(t.get("superseded_stable_pointer_blob_sha1")==gb(root/sr),"ORACLE_PARENT_BLOB")
    else:
        tp=st.get("target_path"); t=rd(root,tp); ok(t.get("version")==st.get("current_version"),"ORACLE_ACTIVE_VERSION")
    exp=derive(root,t,tp); got=json.loads(Path(x.primary_ticket).read_text(encoding="utf-8")); ok(got==exp,"PRIMARY_ORACLE_TICKET_MISMATCH")
    r={"schema":"QROS_DETERMINISTIC_ACTION_ORACLE_RECEIPT_2.0","status":"PASS","frontier_version":exp["frontier_version"],"state_id":exp["state_id"],"guard_profile":exp["guard_profile"],"action_type":exp["action_type"],"resolved_success_state":exp["resolved_success_state"],"ticket_id":exp["ticket_id"],"independent_implementation":True,"imports_primary_compiler":False,"declared_guard_profiles_covered":len(GUARDS)}; r["receipt_sha256"]=h(r); Path(x.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8"); print(json.dumps(r,sort_keys=True)); return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e: print(json.dumps({"status":"FAIL_CLOSED","error":str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
