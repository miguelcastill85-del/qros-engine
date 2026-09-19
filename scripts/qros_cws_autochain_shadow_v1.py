#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, tempfile
from pathlib import Path

SCHEMA="QROS_CWS_AUTOCHAIN_STATE_1.0"
CERT_SCHEMA="QROS_CWS_AUTOCHAIN_COMPLETION_CERT_1.0"

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def hobj(x):
    return hashlib.sha256(canon(x)).hexdigest()

def hex64(x):
    return isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x) is not None

def spec_hash(task_id,objective_hash,target):
    return hobj({"task_id":task_id,"objective_hash":objective_hash,"target":target})

def genesis_root(task_id,objective_hash,target):
    return hobj({"schema":SCHEMA,"task_id":task_id,"objective_hash":objective_hash,"target":target,"generation":0})

def initial_state(task_id,objective_hash,target):
    if not task_id or not hex64(objective_hash) or target<1:
        raise ValueError("SPEC")
    return {
        "schema":SCHEMA,
        "task_id":task_id,
        "objective_hash":objective_hash,
        "target":target,
        "task_spec_hash":spec_hash(task_id,objective_hash,target),
        "generation":0,
        "status":"ACTIVE",
        "chain_root":genesis_root(task_id,objective_hash,target),
        "last_run_id":None,
        "manual_interventions":0
    }

def validate_state(s):
    req={"schema","task_id","objective_hash","target","task_spec_hash","generation","status","chain_root","last_run_id","manual_interventions"}
    if set(s)!=req: raise ValueError("STATE_FIELDS")
    if s["schema"]!=SCHEMA: raise ValueError("STATE_SCHEMA")
    if not s["task_id"] or not hex64(s["objective_hash"]): raise ValueError("IDENTITY")
    if not isinstance(s["target"],int) or s["target"]<1: raise ValueError("TARGET")
    if s["task_spec_hash"]!=spec_hash(s["task_id"],s["objective_hash"],s["target"]): raise ValueError("SPEC_HASH")
    if not isinstance(s["generation"],int) or not (0<=s["generation"]<=s["target"]): raise ValueError("GENERATION")
    if s["status"] not in {"ACTIVE","COMPLETE"}: raise ValueError("STATUS")
    if (s["generation"]==s["target"]) != (s["status"]=="COMPLETE"): raise ValueError("TERMINAL_CONSISTENCY")
    if not hex64(s["chain_root"]): raise ValueError("CHAIN_ROOT")
    if s["manual_interventions"]!=0: raise ValueError("MANUAL_INTERVENTION")
    if s["last_run_id"] is not None and not isinstance(s["last_run_id"],str): raise ValueError("RUN_ID")

def completion_certificate(s):
    validate_state(s)
    if s["status"]!="COMPLETE": raise ValueError("NOT_COMPLETE")
    body={
        "schema":CERT_SCHEMA,
        "task_id":s["task_id"],
        "task_spec_hash":s["task_spec_hash"],
        "objective_hash":s["objective_hash"],
        "target":s["target"],
        "generation":s["generation"],
        "final_chain_root":s["chain_root"],
        "manual_interventions":s["manual_interventions"]
    }
    return {**body,"certificate_sha256":hobj(body)}

def transition(s,expected_generation,run_id):
    validate_state(s)
    if not isinstance(expected_generation,int) or expected_generation<0: raise ValueError("EXPECTED_GENERATION")
    if s["status"]=="COMPLETE":
        return {"action":"NOOP_COMPLETE","changed":False,"state":s,"dispatch_next":False,"certificate":completion_certificate(s)}
    if expected_generation!=s["generation"]:
        return {"action":"NOOP_STALE","changed":False,"state":s,"dispatch_next":False,"certificate":None}
    nxt=s["generation"]+1
    root=hobj({
        "schema":"QROS_CWS_AUTOCHAIN_STEP_1.0",
        "task_spec_hash":s["task_spec_hash"],
        "prev_root":s["chain_root"],
        "generation":nxt
    })
    ns=dict(s)
    ns["generation"]=nxt
    ns["chain_root"]=root
    ns["last_run_id"]=str(run_id)
    ns["status"]="COMPLETE" if nxt==s["target"] else "ACTIVE"
    validate_state(ns)
    cert=completion_certificate(ns) if ns["status"]=="COMPLETE" else None
    return {
        "action":"COMPLETE" if cert else "ADVANCE",
        "changed":True,
        "state":ns,
        "dispatch_next":cert is None,
        "next_expected_generation":nxt,
        "certificate":cert
    }

def atomic_write(path,obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".tmp.",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(obj,f,sort_keys=True,indent=2)
            f.write("\n");f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--state",required=True)
    ap.add_argument("--expected-generation",required=True,type=int)
    ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    p=Path(a.state)
    s=json.loads(p.read_text())
    out=transition(s,a.expected_generation,a.run_id)
    if out["changed"]:
        atomic_write(p,out["state"])
    print(json.dumps({k:v for k,v in out.items() if k!="state"},sort_keys=True,separators=(",",":")))
if __name__=="__main__":
    main()
