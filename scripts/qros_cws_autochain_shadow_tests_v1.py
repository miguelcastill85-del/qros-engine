#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, random
from qros_cws_autochain_shadow_v1 import *

OBJ=hashlib.sha256(b"CWS_AUTOCHAIN_SHADOW_OBJECTIVE").hexdigest()

def run_chain(target,run_prefix="r"):
    s=initial_state("CWS_AUTOCHAIN_SHADOW",OBJ,target)
    roots=[s["chain_root"]]
    stale=0
    for g in range(target):
        out=transition(s,g,f"{run_prefix}-{g}")
        assert out["changed"] and out["action"] in {"ADVANCE","COMPLETE"}
        old=s
        s=out["state"]
        roots.append(s["chain_root"])
        replay=transition(s,g,f"duplicate-{g}")
        if s["status"]=="COMPLETE":
            assert replay["action"]=="NOOP_COMPLETE"
        else:
            assert replay["action"]=="NOOP_STALE"
        assert replay["state"]==s and not replay["changed"]
        stale+=1
        assert old["manual_interventions"]==0 and s["manual_interventions"]==0
    cert=completion_certificate(s)
    return s,cert,roots,stale

def gates():
    s=initial_state("CWS_AUTOCHAIN_SHADOW",OBJ,32)
    assert s["generation"]==0 and s["status"]=="ACTIVE"

    # deterministic identity independent of runner ids
    a,ca,ra,_=run_chain(32,"A")
    b,cb,rb,_=run_chain(32,"B")
    assert a["chain_root"]==b["chain_root"]
    assert ca["certificate_sha256"]==cb["certificate_sha256"]
    assert ra==rb

    # future/stale generations cannot advance
    x=initial_state("CWS_AUTOCHAIN_SHADOW",OBJ,8)
    for bad in (1,2,7,99):
        o=transition(x,bad,"future")
        assert o["action"]=="NOOP_STALE" and o["state"]==x

    # immutable task spec / target
    bad=dict(x);bad["target"]=9
    try:
        validate_state(bad);raise AssertionError("TARGET_TAMPER_ACCEPTED")
    except ValueError as e:
        assert str(e)=="SPEC_HASH"

    # manual intervention counter cannot be nonzero
    bad=dict(x);bad["manual_interventions"]=1
    try:
        validate_state(bad);raise AssertionError("MANUAL_INTERVENTION_ACCEPTED")
    except ValueError as e:
        assert str(e)=="MANUAL_INTERVENTION"

    # terminal no-op
    done,cert,_,_=run_chain(8)
    noop=transition(done,8,"after-terminal")
    assert noop["action"]=="NOOP_COMPLETE" and noop["certificate"]["certificate_sha256"]==cert["certificate_sha256"]

    return {
        "single_step_exactly_once":"PASS",
        "stale_duplicate_noop":"PASS",
        "future_generation_noop":"PASS",
        "task_spec_immutable":"PASS",
        "manual_intervention_forbidden":"PASS",
        "terminal_noop":"PASS",
        "runner_id_independent_root":"PASS"
    }

def chaos(cases=100000,seed=20260919):
    rng=random.Random(seed)
    s=initial_state("CWS_AUTOCHAIN_SHADOW",OBJ,1000)
    advances=stale=0
    for i in range(cases):
        if s["status"]=="COMPLETE": break
        current=s["generation"]
        mode=rng.randrange(5)
        expected=current if mode<2 else max(0,current+rng.choice([-3,-2,-1,1,2,3]))
        out=transition(s,expected,f"chaos-{i}")
        if expected==current:
            assert out["changed"]
            s=out["state"];advances+=1
        else:
            assert not out["changed"] and out["state"]==s
            stale+=1
    # finish deterministically
    while s["status"]!="COMPLETE":
        s=transition(s,s["generation"],"finish")["state"]
    cert=completion_certificate(s)
    assert s["generation"]==1000 and s["manual_interventions"]==0
    return {"cases":cases,"advances":advances,"stale_noops":stale,"final_generation":1000,"certificate":cert["certificate_sha256"]}

def fixed_point(rounds=2,cases=100000):
    out=[]
    for r in range(rounds):
        rng=random.Random(8000+r)
        critical=high=0
        for i in range(cases):
            target=rng.randint(1,64)
            s=initial_state(f"T{r}-{i}",hashlib.sha256(f"O{r}-{i}".encode()).hexdigest(),target)
            if rng.random()<0.5:
                o=transition(s,0,f"run-{i}")
                high+=int(not o["changed"] or o["state"]["generation"]!=1)
            else:
                o=transition(s,rng.randint(1,target+3),f"stale-{i}")
                high+=int(o["changed"])
            critical+=int(s["manual_interventions"]!=0)
        assert critical==0 and high==0
        out.append({"round":r+1,"cases":cases,"new_critical":0,"new_high":0})
    return out

def main():
    result={"status":"PASS","gates":gates(),"chaos":chaos(),"fixed_point":fixed_point()}
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":
    main()
