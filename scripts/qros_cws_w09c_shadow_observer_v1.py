#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from qros_continuous_work_scheduler_v1 import TaskSpec,Observation,initial_state,compile_step,SPEC_SCHEMA

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def hobj(x): return hashlib.sha256(canon(x)).hexdigest()

def load(path): return json.loads(Path(path).read_text())

def _false_flags(obj,names):
    return all(obj.get(n) is False for n in names)

def observe(frontier,checkpoint,dek,cws,spec):
    if spec["status"]!="PREREGISTERED_NO_RESULTS": raise ValueError("SPEC_NOT_PREREGISTERED")
    if frontier.get("schema")!=spec["expected_frontier_schema"]: raise ValueError("FRONTIER_SCHEMA")
    if checkpoint.get("schema")!=spec["expected_checkpoint_schema"]: raise ValueError("CHECKPOINT_SCHEMA")
    if frontier.get("scientific_state")!=spec["expected_scientific_state"]: raise ValueError("SCIENTIFIC_STATE")
    if dek.get("status")!=spec["expected_dek_status"]: raise ValueError("DEK_STATUS")
    if cws.get("status")!=spec["expected_cws_status"]: raise ValueError("CWS_STATUS")
    if not _false_flags(frontier,spec["forbidden_flags"]): raise ValueError("FRONTIER_FIREWALL")
    guards=checkpoint.get("scientific_guards",{})
    if not _false_flags(guards,spec["forbidden_flags"]): raise ValueError("CHECKPOINT_FIREWALL")
    na=frontier.get("next_action")
    nb=checkpoint.get("next_automatic_action")
    if not isinstance(na,str) or not isinstance(nb,str) or na!=nb: raise ValueError("NEXT_ACTION_PARITY")
    if not na.startswith("DEK_V3_ACTIVE:"): raise ValueError("NOT_DEK_ACTION")
    objective=hobj({
      "frontier_schema":frontier["schema"],
      "checkpoint_schema":checkpoint["schema"],
      "next_action":na,
      "scientific_state":frontier["scientific_state"]
    })
    ts=TaskSpec(SPEC_SCHEMA,"CWS_W09C_SHADOW",objective,1,frozenset(spec["allowed_capabilities"]),2,8)
    state=initial_state(ts)
    decision=compile_step(ts,state,Observation(authority_ok=True,required_capability="CAP_NON_ECONOMIC_CONTROL"))
    if decision.action!=spec["expected_decision"] or not decision.external_effect:
        raise ValueError("CWS_DECISION_PARITY")
    return {
      "status":"PASS",
      "mode":"SHADOW_READ_ONLY",
      "decision":decision.action,
      "would_effect_id":decision.effect_id,
      "external_effects_executed":0,
      "w09c_writes":0,
      "economic_pnl_read":False,
      "holdout_open":False,
      "ga2_open":False,
      "new_ga1_authorized":False,
      "first_gate_execution_authorized":False,
      "authority_objective_hash":objective
    }

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--frontier",required=True);ap.add_argument("--checkpoint",required=True)
    ap.add_argument("--dek",required=True);ap.add_argument("--cws",required=True);ap.add_argument("--spec",required=True)
    a=ap.parse_args()
    print(json.dumps(observe(load(a.frontier),load(a.checkpoint),load(a.dek),load(a.cws),load(a.spec)),sort_keys=True))
if __name__=="__main__": main()
