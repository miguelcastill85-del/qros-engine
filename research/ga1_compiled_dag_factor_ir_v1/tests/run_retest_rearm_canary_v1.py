from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parents[1]
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT/"scripts"))

from qros_independent_retest_rearm_canary import REARM_CODES, TRANSFORMS, make_fixture, perturb_after, raw_breaks, oracle_filter
from qros_seed0076_structural_v220 import filter_raw_to_candidates

def arr(rows,col,dtype):
    return np.asarray([x[col] for x in rows],dtype=dtype)

def production(fx,rows,opp,side,bm,rearm,retest,window):
    return filter_raw_to_candidates(
        fx["bid"],fx["first"],fx["last"],fx["bar_low"],fx["bar_high"],fx["bar_close"],
        fx["level"],fx["level_id"],fx["next_repl"],fx["atr_prev"],
        arr(rows,0,np.int64),arr(rows,1,np.int32),arr(rows,2,np.int64),
        arr(opp,0,np.int64),side,fx["point"],bm,rearm,retest,window
    )

fx=make_fixture()
agg={k:0 for k in ("raw","pending_skip","rearm_skip","touch_success","close_success","retest_fail","cancel_replacement","cancel_opposite","return_rearm","replacement_rearm","accepted")}
outputs={}
cases=mismatches=nonempty=0

for side in (1,-1):
    for trigger in ("TICK_BREAK","CLOSE_BREAK"):
        for bm in (0.0,0.10):
            rows=raw_breaks(fx,side,bm,trigger)
            opp=raw_breaks(fx,-side,bm,trigger)
            ri=arr(rows,0,np.int64); rb=arr(rows,1,np.int32); rl=arr(rows,2,np.int64); oi=arr(opp,0,np.int64)
            for rearm_name,rearm in REARM_CODES.items():
                for transform_name,retest,window in TRANSFORMS:
                    oracle=oracle_filter(fx,ri,rb,rl,oi,side,bm,rearm,retest,window,True)
                    prod=production(fx,rows,opp,side,bm,rearm,retest,window)
                    cases+=1
                    nonempty+=int(len(prod[0])>0)
                    if not (np.array_equal(oracle[0],prod[0]) and np.array_equal(oracle[1],prod[1])):
                        mismatches+=1
                    outputs[(side,trigger,bm,rearm,retest,window)]=tuple(int(x) for x in prod[0])
                    for k,v in oracle[2].items():agg[k]+=int(v)

if cases!=168 or mismatches:
    raise SystemExit(f"MATRIX_PARITY_FAIL:{cases}:{mismatches}")
required_trace=("pending_skip","rearm_skip","touch_success","close_success","retest_fail","cancel_replacement","cancel_opposite","return_rearm","replacement_rearm","accepted")
if any(agg[k]<=0 for k in required_trace):
    raise SystemExit("MECHANISM_NOT_EXERCISED:"+",".join(k for k in required_trace if agg[k]<=0))

rearm_diff=0
for side in (1,-1):
    for trigger in ("TICK_BREAK","CLOSE_BREAK"):
        for bm in (0.0,0.10):
            for _,retest,window in TRANSFORMS:
                if outputs[(side,trigger,bm,0,retest,window)]!=outputs[(side,trigger,bm,1,retest,window)]:
                    rearm_diff+=1

retest_diff=0
for side in (1,-1):
    for trigger in ("TICK_BREAK","CLOSE_BREAK"):
        for bm in (0.0,0.10):
            for rearm in (0,1,2):
                base=outputs[(side,trigger,bm,rearm,0,0)]
                for _,retest,window in TRANSFORMS[1:]:
                    if outputs[(side,trigger,bm,rearm,retest,window)]!=base:
                        retest_diff+=1

trigger_diff=0
for side in (1,-1):
    for bm in (0.0,0.10):
        for rearm in (0,1,2):
            for _,retest,window in TRANSFORMS:
                if outputs[(side,"TICK_BREAK",bm,rearm,retest,window)]!=outputs[(side,"CLOSE_BREAK",bm,rearm,retest,window)]:
                    trigger_diff+=1

if min(rearm_diff,retest_diff,trigger_diff)<=0:
    raise SystemExit(f"MODE_DISCRIMINATION_FAIL:{rearm_diff}:{retest_diff}:{trigger_diff}")

cutoff=int(fx["last"][19])
future=perturb_after(fx,cutoff)
future_cases=future_fail=0
for side in (1,-1):
    for trigger in ("TICK_BREAK","CLOSE_BREAK"):
        for bm in (0.0,0.10):
            base_rows=raw_breaks(fx,side,bm,trigger); base_opp=raw_breaks(fx,-side,bm,trigger)
            fut_rows=raw_breaks(future,side,bm,trigger); fut_opp=raw_breaks(future,-side,bm,trigger)
            for rearm in (0,1,2):
                for _,retest,window in TRANSFORMS:
                    a=production(fx,base_rows,base_opp,side,bm,rearm,retest,window)
                    b=production(future,fut_rows,fut_opp,side,bm,rearm,retest,window)
                    aa=tuple((int(i),int(bar)) for i,bar in zip(a[0],a[1]) if i<=cutoff)
                    bb=tuple((int(i),int(bar)) for i,bar in zip(b[0],b[1]) if i<=cutoff)
                    future_cases+=1
                    future_fail+=int(aa!=bb)
if future_cases!=168 or future_fail:
    raise SystemExit(f"FUTURE_PERTURBATION_FAIL:{future_cases}:{future_fail}")

out={
  "status":"PASS",
  "classification":"SYNTHETIC_NON_ECONOMIC",
  "production_semantics":"scripts/qros_seed0076_structural_v220.py::filter_raw_to_candidates",
  "matrix_cases":cases,
  "matrix_mismatches":mismatches,
  "nonempty_cases":nonempty,
  "coverage":{
    "sides":["BUY","SELL"],
    "triggers":["TICK_BREAK","CLOSE_BREAK"],
    "buffer_multipliers":[0.0,0.10],
    "rearm_modes":list(REARM_CODES),
    "retest_transforms":[x[0] for x in TRANSFORMS],
    "total_combinations":168
  },
  "mechanism_counts":agg,
  "mode_discrimination":{"rearm":rearm_diff,"retest":retest_diff,"trigger":trigger_diff},
  "future_perturbation":{"cutoff_source_index":cutoff,"cases":future_cases,"failures":future_fail}
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
