#!/usr/bin/env python3
from __future__ import annotations
import copy,hashlib,json,random
from pathlib import Path
from qros_cws_w09c_shadow_observer_v1 import observe

ROOT=Path(__file__).resolve().parent.parent
def load(p): return json.loads((ROOT/p).read_text())

frontier=load("control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json")
checkpoint=load("control/QROS_PUBLIC_1000_CURRENT_W09C_EXECUTION_CHECKPOINT.json")
dek=load("governance/QROS_DETERMINISTIC_EXECUTION_KERNEL_GOVERNANCE_v3.0.json")
cws=load("control/QROS_CWS_CURRENT.json")
spec=load("control/QROS_CWS_W09C_SHADOW_SPEC_20260919_v1.json")

def must_fail(f,c=checkpoint,d=dek,w=cws,s=spec):
    try: observe(f,c,d,w,s)
    except ValueError: return
    raise AssertionError("MUTATION_ACCEPTED")

def main():
    base=observe(frontier,checkpoint,dek,cws,spec)
    assert base["status"]=="PASS" and base["external_effects_executed"]==0 and base["w09c_writes"]==0
    assert base["decision"]=="INVOKE_DEK"

    # Every forbidden scientific/economic gate fails closed.
    for flag in spec["forbidden_flags"]:
        f=copy.deepcopy(frontier); f[flag]=True; must_fail(f)
        c=copy.deepcopy(checkpoint); c.setdefault("scientific_guards",{})[flag]=True; must_fail(frontier,c)

    # Authority/action drift fails closed.
    f=copy.deepcopy(frontier); f["scientific_state"]="DEVELOPMENT_RUNNING"; must_fail(f)
    f=copy.deepcopy(frontier); f["next_action"]="DEK_V3_ACTIVE: DIFFERENT"; must_fail(f)
    c=copy.deepcopy(checkpoint); c["next_automatic_action"]="DEK_V3_ACTIVE: DIFFERENT"; must_fail(frontier,c)
    d=copy.deepcopy(dek); d["status"]="CANDIDATE_VALIDATION"; must_fail(frontier,checkpoint,d)
    w=copy.deepcopy(cws); w["status"]="VALIDATED_DESIGN_SHADOW_INACTIVE"; must_fail(frontier,checkpoint,dek,w)

    rng=random.Random(20260919)
    rejected=0
    for i in range(100000):
        f=copy.deepcopy(frontier); c=copy.deepcopy(checkpoint)
        mode=rng.randrange(7)
        if mode<5:
            flag=spec["forbidden_flags"][mode]
            (f if rng.random()<0.5 else c.setdefault("scientific_guards",{}))[flag]=True
        elif mode==5:
            f["next_action"]=f["next_action"]+" DRIFT"
        else:
            c["next_automatic_action"]=c["next_automatic_action"]+" DRIFT"
        try: observe(f,c,dek,cws,spec)
        except ValueError: rejected+=1
    assert rejected==100000
    print(json.dumps({
      "status":"PASS","baseline":base,"mutation_cases":100000,"mutation_rejected":rejected,
      "external_effects_executed":0,"w09c_writes":0
    },sort_keys=True))
if __name__=="__main__": main()
