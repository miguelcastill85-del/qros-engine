#!/usr/bin/env python3
import argparse, hashlib, json, sys
from pathlib import Path

class AuditError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(detail); self.code=code; self.detail=detail

def req(x, code, detail=""):
    if not x: raise AuditError(code, detail)

def blob_sha(data: bytes):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def readb(root, p):
    f=root/p
    req(f.exists(), "FILE_MISSING", p)
    return f.read_bytes()

def readj(root,p):
    try: return json.loads(readb(root,p).decode())
    except AuditError: raise
    except Exception as e: raise AuditError("JSON_INVALID", f"{p}:{e}")

def sha(root,p): return blob_sha(readb(root,p))

def depmap(h):
    m=h.get("bootstrap_manifest",{}); es=m.get("entries",[]); rr=m.get("required_roles",[])
    req(isinstance(es,list) and es, "BOOTSTRAP_EMPTY")
    roles={}; paths=set()
    for e in es:
        req(isinstance(e,dict),"BOOTSTRAP_ENTRY_TYPE")
        r,p,s=e.get("role"),e.get("path"),e.get("git_blob_sha1")
        req(r and p and s,"BOOTSTRAP_ENTRY_FIELDS",str(e))
        req(r not in roles,"BOOTSTRAP_DUP_ROLE",r); req(p not in paths,"BOOTSTRAP_DUP_PATH",p)
        roles[r]=e; paths.add(p)
    req(set(rr)==set(roles),"BOOTSTRAP_ROLE_CLOSURE",f"expected={sorted(rr)} actual={sorted(roles)}")
    return roles

def validate(root: Path, candidate_pointer="control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json"):
    cp=readj(root,candidate_pointer)
    req(cp.get("schema")=="QROS_PUBLIC1000_CHAT_HANDOFF_CANDIDATE_POINTER_1.0","CANDIDATE_SCHEMA")
    hp,hs=cp.get("handoff_path"),cp.get("handoff_git_blob_sha1")
    req(hp and hs,"CANDIDATE_HANDOFF_REF")
    req(sha(root,hp)==hs,"HANDOFF_BLOB_MISMATCH")
    h=readj(root,hp)
    req(h.get("schema")=="QROS_PUBLIC1000_CHAT_MIGRATION_HANDOFF_2.0","HANDOFF_SCHEMA")
    req(h.get("status")=="FROZEN_IMMUTABLE","HANDOFF_STATUS")
    req(h.get("campaign")==cp.get("campaign"),"CAMPAIGN_MISMATCH")
    roles=depmap(h)
    for role,e in roles.items():
        req(sha(root,e["path"])==e["git_blob_sha1"],"DEPENDENCY_BLOB_MISMATCH",role)
    p=h.get("authority_precedence",{})
    req(p.get("bootstrap_pointer")=="CURRENT_CHAT_HANDOFF_POINTER","PRECEDENCE_BOOTSTRAP")
    req(p.get("scientific_authority")=="CURRENT_FRONTIER_POINTER","PRECEDENCE_SCIENTIFIC")
    req(p.get("immutable_candidate_target_role")=="HISTORICAL_CANDIDATE_EVIDENCE_NOT_DYNAMIC_LATCH_AUTHORITY","PRECEDENCE_TARGET")
    req(p.get("dynamic_latch_authority")=="STABLE_SCIENTIFIC_POINTER_PLUS_PINNED_EXTERNAL_VALIDATION_RECEIPTS","PRECEDENCE_LATCH")
    req(p.get("memory_authoritative") is False and p.get("free_text_authoritative") is False,"PRECEDENCE_TEXT")
    sp=roles["stable_scientific_pointer"]
    st=readj(root,sp["path"]); ex=h["authority"]["stable_scientific_pointer_expected"]
    req(sha(root,sp["path"])==sp["git_blob_sha1"],"STABLE_POINTER_PIN")
    req(sha(root,sp["path"])==ex["git_blob_sha1"],"STALE_HANDOFF_STABLE_POINTER")
    req(st.get("current_version")==ex["version"],"STALE_HANDOFF_VERSION")
    req(st.get("target_path")==ex["target_path"] and st.get("target_git_blob_sha1")==ex["target_git_blob_sha1"],"STABLE_TARGET_BINDING")
    tg=readj(root,ex["target_path"]); req(sha(root,ex["target_path"])==ex["target_git_blob_sha1"],"TARGET_PIN")
    req(tg.get("scientific_execution_authorized") is False,"TARGET_PREPROMOTION_LATCH")
    req(st.get("scientific_execution_authorized") is True,"STABLE_LATCH")
    for k in ("economic_pnl_read","ga2_open","holdout_open","first_gate_execution_authorized","new_ga1_authorized"):
        req(st.get(k) is False,"FIREWALL_"+k.upper())
    ht=h["machine_ticket"]
    checks=[("ticket_id","machine_action_ticket_id"),("action","machine_action_type"),("state_id","machine_state_id"),("guard_profile","machine_guard_profile"),("subject","machine_subject")]
    for a,b in checks: req(ht.get(a)==st.get(b),"TICKET_MISMATCH_"+a.upper())
    req(ht.get("action")=="BUILD_FIRST_GATE_SCORER","ACTION_UNEXPECTED")
    for key,role,status in [("candidate_validation_receipt","candidate_validation_receipt","candidate_validation_status"),("active_validation_receipt","active_validation_receipt","active_validation_status"),("active_execution_validation_receipt","active_execution_validation_receipt","active_execution_validation_status")]:
        req(st.get(status)=="PASS","VALIDATION_STATUS",status)
        sr=st.get(key); e=roles[role]
        req(isinstance(sr,dict) and sr.get("path")==e["path"] and sr.get("git_blob_sha1")==e["git_blob_sha1"],"VALIDATION_PIN",key)
        r=readj(root,e["path"])
        req(r.get("status")=="PASS" and r.get("frontier_version")==st["current_version"],"VALIDATION_CONTENT",key)
        req(r.get("ticket",{}).get("ticket_id")==ht["ticket_id"],"VALIDATION_TICKET",key)
    wg=readj(root,roles["master_workgraph"]["path"]); gr=readj(root,roles["gap_register"]["path"]); dl=readj(root,roles["decision_ledger"]["path"])
    req(wg.get("current_node")=="W09_FIRST_GATE_SCORER_BUILD" and wg.get("automatic_next_action")=="BUILD_FIRST_GATE_SCORER","WORKGRAPH")
    req(gr.get("current_blocking_gap")=="GAP-S03","GAP_REGISTER")
    req("BUILD_FIRST_GATE_SCORER" in dl.get("decision",""),"DECISION_LEDGER")
    pl=readj(root,roles["promotion_ledger"]["path"])
    req(pl.get("current_first_gate_order")==1,"FIFO_ORDER")
    req(pl.get("current_first_gate_shard_id")==ht["subject"]["shard_id"],"FIFO_SHARD")
    req(pl.get("current_first_gate_domain")=={k:ht["subject"][k] for k in ("asset","side","timeframe")},"FIFO_DOMAIN")
    req(pl.get("first_gate_pending_count")==8 and pl.get("first_gate_terminal_count")==0,"FIFO_COUNTS")
    mc=readj(root,roles["multiplicity_contract"]["path"])
    req(mc.get("status")=="FROZEN_PRE_PNL","MULTIPLICITY_STATUS")
    req(mc.get("cross_shard_error_budget",{}).get("per_shard_q_exact")=="1/1200","MULTIPLICITY_Q")
    ek=tg["execution_kernel"]
    direct={"kernel_governance":ek["governance"],"execution_map":ek["execution_map"],"decision_ledger":ek["decision_ledger"],"master_workgraph":ek["master_workgraph"],"gap_register":ek["gap_register"],"kernel_compiler":ek["compiler"],"kernel_oracle":ek["oracle"],"kernel_adversarial_suite":ek["adversarial_suite"],"kernel_mode_resolver":ek["mode_resolver"],"kernel_external_workflow":ek["external_workflow"],"kernel_compiler_v2":ek["transitive_core"]["compiler_v2"],"kernel_oracle_v2":ek["transitive_core"]["oracle_v2"]}
    for role,ref in direct.items(): req(roles[role]["path"]==ref["path"] and roles[role]["git_blob_sha1"]==ref["git_blob_sha1"],"KERNEL_PIN_CLOSURE",role)
    au=tg["authority"]; pins=tg["authority_pins"]
    for role,path,pin in [("primary_policy",au["primary_policy"],pins["primary_policy_git_blob_sha1"]),("multiplicity_contract",au["first_gate_multiplicity_contract"],pins["multiplicity_contract_git_blob_sha1"]),("gate_a_plan",au["gate_a_plan"],pins["gate_a_plan_git_blob_sha1"]),("minimal_dev_carrier_binding",au["minimal_dev_carrier_binding"],pins["minimal_dev_carrier_binding_git_blob_sha1"]),("xau_m1_completion",au["xau_m1_completion"],pins["xau_m1_completion_git_blob_sha1"]),("promotion_ledger",au["promotion_ledger"],pins["promotion_ledger_git_blob_sha1"]),("rise_fixed_point_receipt",au["rise_fixed_point_pass"]["path"],au["rise_fixed_point_pass"]["git_blob_sha1"])]:
        req(roles[role]["path"]==path and roles[role]["git_blob_sha1"]==pin,"AUTHORITY_PIN_CLOSURE",role)
    ad=h.get("architecture_defect",{})
    req(ad.get("id")=="ARCH-GAP-EXEC-CAPSULE-001" and ad.get("execution_capsule_status")=="NOT_IMPLEMENTED","CAPSULE_GAP_STATE")
    req(ad.get("economic_access_allowed") is False and ad.get("holdout_access_allowed") is False,"CAPSULE_GAP_FIREWALL")
    req(h.get("next_automatic_action")=="IMPLEMENT_AND_EXTERNALLY_VALIDATE_EXECUTION_CAPSULE_LAYER_FOR_CURRENT_MACHINE_TICKET_THEN_BUILD_FIRST_GATE_SCORER","NEXT_ACTION")
    req(h.get("data_policy",{}).get("additional_zip_upload_required_for_current_action") is False,"ZIP_POLICY")
    cur=readj(root,h["authority"]["current_chat_handoff_pointer_path"])
    mode="ACTIVE" if cur.get("handoff_path")==hp and cur.get("handoff_git_blob_sha1")==hs else "CANDIDATE"
    return {"status":"PASS","mode":mode,"handoff_path":hp,"handoff_git_blob_sha1":hs,"stable_version":st["current_version"],"stable_pointer_blob_sha1":sha(root,sp["path"]),"ticket_id":ht["ticket_id"],"action":ht["action"],"bootstrap_dependency_count":len(roles),"current_node":"W09_FIRST_GATE_SCORER_BUILD","current_gap":"GAP-S03"}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--candidate-pointer",default="control/QROS_PUBLIC_1000_CHAT_HANDOFF_CANDIDATE.json"); a=ap.parse_args()
    try:
        print(json.dumps(validate(Path(a.root),a.candidate_pointer),sort_keys=True,separators=(",",":"))); return 0
    except AuditError as e:
        print(json.dumps({"status":"FAIL","code":e.code,"detail":e.detail},sort_keys=True,separators=(",",":"))); return 2
if __name__=="__main__": raise SystemExit(main())
