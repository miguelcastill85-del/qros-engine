#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path

def load(path):
    s=importlib.util.spec_from_file_location("ek",path); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); return m

def main():
    repo=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=="tests" else Path(__file__).resolve().parent
    path=(repo/"scripts/qros_seed0076_event_kernel.py") if (repo/"scripts").exists() else (repo/"qros_seed0076_event_kernel.py")
    k=load(path); tests=[]
    highs=[1,2,5,3,4]
    tests.append({"id":"FRACTAL_NOT_KNOWN_BEFORE_RIGHT_BARS","pass":k.confirmed_fractal_high(highs,3,5,"SOURCE_ASYMMETRIC") is None})
    fh=k.confirmed_fractal_high(highs,4,5,"SOURCE_ASYMMETRIC")
    tests.append({"id":"FRACTAL_FIRST_KNOWN_AT_CONFIRMATION_CLOSE","pass":fh==(2,5)})
    highs_tie=[1,5,5,3,2]
    a=k.confirmed_fractal_high(highs_tie,4,5,"SOURCE_ASYMMETRIC")
    b=k.confirmed_fractal_high(highs_tie,4,5,"STRICT_ALL_NEIGHBORS")
    tests.append({"id":"TIE_POLICY_BRANCH_IS_REAL","pass":a==(2,5) and b is None})
    st=k.LevelState("BUY","RETURN_INSIDE_OR_LEVEL_REPLACED"); st.replace_level(5,"L1")
    pre=k.crossed(4.9,5.1,5,"BUY")
    fresh=k.LevelState("BUY","RETURN_INSIDE_OR_LEVEL_REPLACED")
    tests.append({"id":"NO_EXECUTABLE_BREAK_WITHOUT_CONFIRMED_LEVEL","pass":fresh.breakout(4.9,5.1,5,False)=="NONE" and pre})
    ev=st.breakout(4.9,5.1,5,False); fin=st.finalize_candidate(False)
    later=st.breakout(5.1,5.2,5,False)
    tests.append({"id":"FILTER_FAIL_CONSUMES_OPPORTUNITY","pass":ev=="FINAL_CANDIDATE" and fin=="FILTERED_CONSUMED" and later=="NONE"})
    rearmed=st.observe_rearm_price(4.95); again=st.breakout(4.95,5.2,5,False)
    tests.append({"id":"RETURN_INSIDE_REARMS","pass":rearmed and again=="FINAL_CANDIDATE"})
    st.finalize_candidate(True); st.replace_level(5.5,"L2")
    tests.append({"id":"LEVEL_REPLACEMENT_REARMS","pass":not st.consumed and st.level==5.5})
    rt=k.LevelState("BUY","ONE_SIGNAL_PER_LEVEL"); rt.replace_level(5,"L1")
    armed=rt.breakout(4.9,5.1,5,True); touch=rt.retest_tick(5.1,4.95); reclaim=rt.retest_tick(4.95,5.05); signal=rt.finalize_candidate(True)
    tests.append({"id":"RETEST_ORDERING_BREAK_TOUCH_RECLAIM","pass":armed=="RETEST_ARMED" and touch=="RETEST_TOUCHED" and reclaim=="FINAL_CANDIDATE" and signal=="SIGNAL"})
    rt2=k.LevelState("BUY","ONE_SIGNAL_PER_LEVEL"); rt2.replace_level(5,"L1"); rt2.breakout(4.9,5.1,5,True); rt2.replace_level(5.5,"L2")
    tests.append({"id":"LEVEL_REPLACEMENT_CANCELS_PENDING_RETEST","pass":not rt2.pending_retest and rt2.level==5.5})
    tests.append({"id":"BUFFER_IS_PRE_BREAK_TRANSFORM","pass":k.threshold(5,"BUY",atr=2,buffer_atr="0.25")==5.5 and k.threshold(5,"SELL",atr=2,buffer_atr="0.25")==4.5})
    tests.append({"id":"CLOSE_BREAK_TRANSITION","pass":k.close_cross(4.9,5.1,5,"BUY") and not k.close_cross(5.1,5.2,5,"BUY")})
    receipt={"schema":"QROS_SEED0076_EVENT_KERNEL_SYNTHETIC_TEST_1.0","status":"PASS" if all(x["pass"] for x in tests) else "FAIL",
             "tests":tests,"economic_pnl_read":False,"holdout_open":False}
    raw=json.dumps(receipt,sort_keys=True,separators=(",",":")).encode(); receipt["receipt_sha256"]=hashlib.sha256(raw).hexdigest()
    out=(repo/"control/QROS_PUBLIC_1000_SEED_0076_EVENT_KERNEL_SYNTHETIC_TEST_V215_v1.json") if (repo/"control").exists() else (repo/"event_kernel_receipt.json")
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(receipt["status"]); return 0 if receipt["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
