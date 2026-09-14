#!/usr/bin/env python3
import argparse, hashlib, json, sys
from decimal import Decimal
from pathlib import Path

EXPECTED_CONTRACT="b864a34ca664d11ce0508781c800275f925f0167"
EXPECTED_CAMPAIGN="PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
class OracleFailure(Exception): pass

def dump(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def number(v):
    try: x=Decimal(str(v))
    except Exception: raise OracleFailure("NONFINITE_PRICE")
    if not x.is_finite(): raise OracleFailure("NONFINITE_PRICE")
    return x
def textnum(x):
    s=format(x,"f")
    if "." in s: s=s.rstrip("0").rstrip(".")
    return "0" if s in ("","-0") else s

def header_ok(m):
    need={"schema","mode","campaign","execution_contract_git_blob_sha1","synthetic_fixture"}
    if not isinstance(m,dict) or not need.issubset(m): raise OracleFailure("MANIFEST_FIELD_MISSING")
    if m["campaign"]!=EXPECTED_CAMPAIGN: raise OracleFailure("CAMPAIGN_MISMATCH")
    if m["execution_contract_git_blob_sha1"]!=EXPECTED_CONTRACT: raise OracleFailure("CONTRACT_PIN_MISMATCH")
    mode=m["mode"]
    if mode=="PRODUCTION": raise OracleFailure("OVERLAPPING_EVENT_POLICY_UNBOUND_IN_PRODUCTION")
    if mode!="SYNTHETIC_VALIDATION": raise OracleFailure("UNSUPPORTED_MODE")
    if m["synthetic_fixture"] is not True: raise OracleFailure("SYNTHETIC_FLAG_REQUIRED")

def normalize_scenario(s):
    if not isinstance(s,dict) or not {"scenario_id","event_anchor","ticks"}.issubset(s): raise OracleFailure("SCENARIO_FIELD_MISSING")
    sid=s["scenario_id"]
    if not isinstance(sid,str) or sid=="": raise OracleFailure("SCENARIO_ID_INVALID")
    a=s["event_anchor"]
    required={"canonical_signal_config_id","event_mask_sha256","event_id","side","signal_observable_timestamp","entry_trigger_timestamp","opposite_fractal_stop","session_close_timestamp"}
    if not isinstance(a,dict) or not required.issubset(a): raise OracleFailure("EVENT_ANCHOR_FIELD_MISSING")
    cid=a["canonical_signal_config_id"]; mask=a["event_mask_sha256"]; eid=a["event_id"]; side=a["side"]
    if not isinstance(cid,str) or not cid: raise OracleFailure("CANDIDATE_ID_INVALID")
    if not isinstance(mask,str) or len(mask)!=64: raise OracleFailure("MASK_SHA_INVALID")
    try: int(mask,16)
    except Exception: raise OracleFailure("MASK_SHA_INVALID")
    if not isinstance(eid,str) or not eid: raise OracleFailure("EVENT_ID_INVALID")
    if side not in {"BUY","SELL"}: raise OracleFailure("SIDE_INVALID")
    obs=a["signal_observable_timestamp"]; trig=a["entry_trigger_timestamp"]; close=a["session_close_timestamp"]
    if any(not isinstance(x,int) for x in (obs,trig,close)): raise OracleFailure("TIMESTAMP_INVALID")
    if obs>trig: raise OracleFailure("SIGNAL_AFTER_TRIGGER")
    if trig>close: raise OracleFailure("TRIGGER_AFTER_SESSION_CLOSE")
    stop=number(a["opposite_fractal_stop"])
    if stop<=0: raise OracleFailure("NONFINITE_PRICE")
    rawticks=s["ticks"]
    if not isinstance(rawticks,list) or len(rawticks)==0: raise OracleFailure("NO_EXECUTABLE_ENTRY")
    ticks=[]; seq0=None; ts0=None
    for q in rawticks:
        if not isinstance(q,dict) or not {"carrier_sequence","timestamp","bid","ask"}.issubset(q): raise OracleFailure("TICK_FIELD_MISSING")
        seq=q["carrier_sequence"]; ts=q["timestamp"]
        if not isinstance(seq,int) or not isinstance(ts,int): raise OracleFailure("TICK_ORDER_INVALID")
        if seq0 is not None and seq<=seq0: raise OracleFailure("NONMONOTONIC_CARRIER_SEQUENCE")
        if ts0 is not None and ts<ts0: raise OracleFailure("BACKWARD_TIMESTAMP")
        bid=number(q["bid"]); ask=number(q["ask"])
        if bid<=0 or ask<=0 or ask<bid: raise OracleFailure("CROSSED_OR_INVALID_QUOTE")
        ticks.append({"ts":ts,"bid":bid,"ask":ask}); seq0=seq; ts0=ts
    entry_pos=next((i for i,q in enumerate(ticks) if q["ts"]>=trig and q["ts"]<=close),None)
    if entry_pos is None: raise OracleFailure("NO_EXECUTABLE_ENTRY")
    eq=ticks[entry_pos]; entry=eq["ask"] if side=="BUY" else eq["bid"]
    if (side=="BUY" and stop>=entry) or (side=="SELL" and stop<=entry): raise OracleFailure("INVALID_STOP_DIRECTION")
    risk=(entry-stop) if side=="BUY" else (stop-entry)
    chosen=None
    eligible=[]
    for q in ticks[entry_pos:]:
        if q["ts"]>close: break
        eligible.append(q)
        outq=q["bid"] if side=="BUY" else q["ask"]
        hit=outq<=stop if side=="BUY" else outq>=stop
        if hit:
            chosen=(q["ts"],outq,"STOP"); break
    if chosen is None:
        if not eligible: raise OracleFailure("NO_SAME_DAY_EXIT_TICK")
        q=eligible[-1]; chosen=(q["ts"],q["bid"] if side=="BUY" else q["ask"],"SAME_DAY")
    xt,xp,why=chosen
    rv=(xp-entry)/risk if side=="BUY" else (entry-xp)/risk
    return {"scenario_id":sid,"canonical_signal_config_id":cid,"event_mask_sha256":mask,"event_id":eid,"side":side,"signal_observable_timestamp":obs,"entry_trigger_timestamp":trig,"entry_timestamp":eq["ts"],"entry_price":textnum(entry),"stop_price":textnum(stop),"exit_timestamp":xt,"exit_price":textnum(xp),"R":textnum(rv),"exit_reason":why}

def evaluate(indir,outdir):
    root=Path(indir); dest=Path(outdir); dest.mkdir(parents=True,exist_ok=True)
    header_ok(json.loads((root/"manifest.json").read_text()))
    parsed=[]; used=set()
    for line in (root/"scenarios.jsonl").read_text().splitlines():
        if not line.strip(): continue
        obj=json.loads(line)
        sid=obj.get("scenario_id") if isinstance(obj,dict) else None
        if sid in used: raise OracleFailure("DUPLICATE_SCENARIO_ID")
        one=normalize_scenario(obj); used.add(one["scenario_id"]); parsed.append(one)
    if not parsed: raise OracleFailure("NO_SCENARIOS")
    parsed=sorted(parsed,key=lambda r:r["scenario_id"])
    trades=dest/"normalized_trades.jsonl"; trades.write_text("".join(dump(x)+"\n" for x in parsed))
    th=hashlib.sha256(trades.read_bytes()).hexdigest()
    summary={"schema":"QROS_FIRST_GATE_EXECUTION_NORMALIZER_SUMMARY_1.0","mode":"SYNTHETIC_VALIDATION","scenario_count":len(parsed),"normalized_trades_sha256":th,"economic_decision_authorized":False,"economic_pnl_read":False}
    sp=dest/"summary.json"; sp.write_text(dump(summary)+"\n")
    receipt={"schema":"QROS_FIRST_GATE_EXECUTION_NORMALIZER_RECEIPT_1.0","implementation":"ORACLE","status":"PASS","normalized_trades_sha256":th,"summary_sha256":hashlib.sha256(sp.read_bytes()).hexdigest(),"synthetic_only":True,"economic_pnl_read":False}
    (dest/"receipt.json").write_text(dump(receipt)+"\n")
    return summary

def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    try: print(dump({"status":"PASS","summary":evaluate(a.input,a.output)}))
    except OracleFailure as e: print(dump({"status":"FAIL_CLOSED","error":str(e)})); sys.exit(2)
    except Exception as e: print(dump({"status":"FAIL_CLOSED","error":"UNEXPECTED_ERROR","detail":type(e).__name__})); sys.exit(2)
if __name__=="__main__": main()
