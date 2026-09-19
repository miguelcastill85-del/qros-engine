#!/usr/bin/env python3
from __future__ import annotations
import random,json
from qros_cws_control_plane_activation_guard_v1 import evaluate,FORBIDDEN_FLAGS,REQUIRED_RECEIPTS

def safe():
    receipts={r:"PASS" for r in REQUIRED_RECEIPTS}
    flags={f:False for f in FORBIDDEN_FLAGS}
    return receipts,dict(flags),dict(flags)

def main():
    r,f,c=safe()
    ok=evaluate(r,f,c,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")
    assert ok["status"]=="ELIGIBLE_CONTROL_PLANE_SHADOW_ACTIVE"

    for receipt in REQUIRED_RECEIPTS:
        rr=dict(r);rr[receipt]="PENDING"
        assert evaluate(rr,f,c,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="PENDING"

    for flag in FORBIDDEN_FLAGS:
        ff=dict(f);ff[flag]=True
        assert evaluate(r,ff,c,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="BLOCKED"
        cc=dict(c);cc[flag]=True
        assert evaluate(r,f,cc,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="BLOCKED"

    assert evaluate(r,f,c,"CANDIDATE_VALIDATION","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="BLOCKED"
    assert evaluate(r,f,c,"FROZEN_ACTIVE","WRONG","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="BLOCKED"
    assert evaluate(r,f,c,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","OTHER: SAFE","CAP_NON_ECONOMIC_CONTROL")["status"]=="BLOCKED"
    assert evaluate(r,f,c,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_HOLDOUT_OPEN")["status"]=="BLOCKED"

    rng=random.Random(20260919)
    blocked=0
    for _ in range(100000):
        rr,ff,cc=safe()
        mode=rng.randrange(10)
        if mode<4: rr[REQUIRED_RECEIPTS[mode]]="PENDING"
        elif mode<9:
            flag=FORBIDDEN_FLAGS[mode-4]
            (ff if rng.random()<0.5 else cc)[flag]=True
        else:
            cc["economic_pnl_read"]=True
        out=evaluate(rr,ff,cc,"FROZEN_ACTIVE","VALIDATED_DESIGN_AUTOCHAIN_SHADOW_PASS","DEK_V3_ACTIVE: SAFE","CAP_NON_ECONOMIC_CONTROL")
        assert out["status"]!="ELIGIBLE_CONTROL_PLANE_SHADOW_ACTIVE"
        blocked+=1

    print(json.dumps({"status":"PASS","adversarial_cases":100000,"unsafe_eligible":0,"blocked_or_pending":blocked},sort_keys=True))
if __name__=="__main__": main()
