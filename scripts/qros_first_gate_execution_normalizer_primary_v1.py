#!/usr/bin/env python3
import argparse, hashlib, json, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

CONTRACT_BLOB = "b864a34ca664d11ce0508781c800275f925f0167"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"

class ExecutionError(Exception):
    pass

def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def dec(v):
    try:
        x = Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        raise ExecutionError("NONFINITE_PRICE")
    if not x.is_finite():
        raise ExecutionError("NONFINITE_PRICE")
    return x

def ds(x):
    s = format(x, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s

def validate_manifest(m):
    req = ["schema","mode","campaign","execution_contract_git_blob_sha1","synthetic_fixture"]
    if any(k not in m for k in req):
        raise ExecutionError("MANIFEST_FIELD_MISSING")
    if m["campaign"] != CAMPAIGN:
        raise ExecutionError("CAMPAIGN_MISMATCH")
    if m["execution_contract_git_blob_sha1"] != CONTRACT_BLOB:
        raise ExecutionError("CONTRACT_PIN_MISMATCH")
    if m["mode"] == "PRODUCTION":
        raise ExecutionError("OVERLAPPING_EVENT_POLICY_UNBOUND_IN_PRODUCTION")
    if m["mode"] != "SYNTHETIC_VALIDATION":
        raise ExecutionError("UNSUPPORTED_MODE")
    if m["synthetic_fixture"] is not True:
        raise ExecutionError("SYNTHETIC_FLAG_REQUIRED")

def validate_anchor(a):
    req=["canonical_signal_config_id","event_mask_sha256","event_id","side","signal_observable_timestamp","entry_trigger_timestamp","opposite_fractal_stop","session_close_timestamp"]
    if not isinstance(a,dict) or any(k not in a for k in req):
        raise ExecutionError("EVENT_ANCHOR_FIELD_MISSING")
    if not isinstance(a["canonical_signal_config_id"],str) or not a["canonical_signal_config_id"]:
        raise ExecutionError("CANDIDATE_ID_INVALID")
    mh=a["event_mask_sha256"]
    if not isinstance(mh,str) or len(mh)!=64:
        raise ExecutionError("MASK_SHA_INVALID")
    try: int(mh,16)
    except Exception: raise ExecutionError("MASK_SHA_INVALID")
    if not isinstance(a["event_id"],str) or not a["event_id"]:
        raise ExecutionError("EVENT_ID_INVALID")
    if a["side"] not in ("BUY","SELL"):
        raise ExecutionError("SIDE_INVALID")
    for k in ("signal_observable_timestamp","entry_trigger_timestamp","session_close_timestamp"):
        if not isinstance(a[k],int):
            raise ExecutionError("TIMESTAMP_INVALID")
    if a["signal_observable_timestamp"] > a["entry_trigger_timestamp"]:
        raise ExecutionError("SIGNAL_AFTER_TRIGGER")
    if a["entry_trigger_timestamp"] > a["session_close_timestamp"]:
        raise ExecutionError("TRIGGER_AFTER_SESSION_CLOSE")
    stop=dec(a["opposite_fractal_stop"])
    if stop <= 0:
        raise ExecutionError("NONFINITE_PRICE")
    return stop

def validate_ticks(ticks):
    if not isinstance(ticks,list) or not ticks:
        raise ExecutionError("NO_EXECUTABLE_ENTRY")
    prev_seq=None; prev_ts=None; out=[]
    for t in ticks:
        if not isinstance(t,dict) or any(k not in t for k in ("carrier_sequence","timestamp","bid","ask")):
            raise ExecutionError("TICK_FIELD_MISSING")
        seq=t["carrier_sequence"]; ts=t["timestamp"]
        if not isinstance(seq,int) or not isinstance(ts,int):
            raise ExecutionError("TICK_ORDER_INVALID")
        if prev_seq is not None and seq <= prev_seq:
            raise ExecutionError("NONMONOTONIC_CARRIER_SEQUENCE")
        if prev_ts is not None and ts < prev_ts:
            raise ExecutionError("BACKWARD_TIMESTAMP")
        bid=dec(t["bid"]); ask=dec(t["ask"])
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ExecutionError("CROSSED_OR_INVALID_QUOTE")
        out.append((seq,ts,bid,ask)); prev_seq=seq; prev_ts=ts
    return out

def execute(row):
    if not isinstance(row,dict) or any(k not in row for k in ("scenario_id","event_anchor","ticks")):
        raise ExecutionError("SCENARIO_FIELD_MISSING")
    sid=row["scenario_id"]
    if not isinstance(sid,str) or not sid:
        raise ExecutionError("SCENARIO_ID_INVALID")
    a=row["event_anchor"]; stop=validate_anchor(a); ticks=validate_ticks(row["ticks"])
    trigger=a["entry_trigger_timestamp"]; close=a["session_close_timestamp"]; side=a["side"]
    entry_i=None
    for i,(_,ts,_,_) in enumerate(ticks):
        if ts >= trigger and ts <= close:
            entry_i=i; break
    if entry_i is None:
        raise ExecutionError("NO_EXECUTABLE_ENTRY")
    _,entry_ts,entry_bid,entry_ask=ticks[entry_i]
    entry = entry_ask if side=="BUY" else entry_bid
    if side=="BUY":
        if stop >= entry: raise ExecutionError("INVALID_STOP_DIRECTION")
        risk=entry-stop
    else:
        if stop <= entry: raise ExecutionError("INVALID_STOP_DIRECTION")
        risk=stop-entry
    exit_ts=None; exit_px=None; reason=None
    last_eligible=None
    for _,ts,bid,ask in ticks[entry_i:]:
        if ts > close: break
        last_eligible=(ts,bid,ask)
        quote=bid if side=="BUY" else ask
        crossed=(quote <= stop) if side=="BUY" else (quote >= stop)
        if crossed:
            exit_ts=ts; exit_px=quote; reason="STOP"; break
    if exit_ts is None:
        if last_eligible is None:
            raise ExecutionError("NO_SAME_DAY_EXIT_TICK")
        exit_ts,bid,ask=last_eligible
        exit_px=bid if side=="BUY" else ask
        reason="SAME_DAY"
    r=(exit_px-entry)/risk if side=="BUY" else (entry-exit_px)/risk
    return {
        "scenario_id":sid,"canonical_signal_config_id":a["canonical_signal_config_id"],"event_mask_sha256":a["event_mask_sha256"],"event_id":a["event_id"],"side":side,
        "signal_observable_timestamp":a["signal_observable_timestamp"],"entry_trigger_timestamp":trigger,"entry_timestamp":entry_ts,
        "entry_price":ds(entry),"stop_price":ds(stop),"exit_timestamp":exit_ts,"exit_price":ds(exit_px),"R":ds(r),"exit_reason":reason
    }

def run(inp,outdir):
    inp=Path(inp); outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    m=json.loads((inp/"manifest.json").read_text()); validate_manifest(m)
    rows=[]; ids=set()
    with (inp/"scenarios.jsonl").open() as f:
        for line in f:
            if not line.strip(): continue
            raw=json.loads(line); sid=raw.get("scenario_id") if isinstance(raw,dict) else None
            if sid in ids: raise ExecutionError("DUPLICATE_SCENARIO_ID")
            res=execute(raw); ids.add(res["scenario_id"]); rows.append(res)
    if not rows: raise ExecutionError("NO_SCENARIOS")
    rows.sort(key=lambda x:x["scenario_id"])
    p=outdir/"normalized_trades.jsonl"
    p.write_text("".join(canon(r)+"\n" for r in rows))
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    summary={"schema":"QROS_FIRST_GATE_EXECUTION_NORMALIZER_SUMMARY_1.0","mode":"SYNTHETIC_VALIDATION","scenario_count":len(rows),"normalized_trades_sha256":h,"economic_decision_authorized":False,"economic_pnl_read":False}
    (outdir/"summary.json").write_text(canon(summary)+"\n")
    receipt={"schema":"QROS_FIRST_GATE_EXECUTION_NORMALIZER_RECEIPT_1.0","implementation":"PRIMARY","status":"PASS","normalized_trades_sha256":h,"summary_sha256":hashlib.sha256((outdir/"summary.json").read_bytes()).hexdigest(),"synthetic_only":True,"economic_pnl_read":False}
    (outdir/"receipt.json").write_text(canon(receipt)+"\n")
    return summary

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--output",required=True); a=ap.parse_args()
    try:
        print(canon({"status":"PASS","summary":run(a.input,a.output)}))
    except ExecutionError as e:
        print(canon({"status":"FAIL_CLOSED","error":str(e)})); sys.exit(2)
    except Exception as e:
        print(canon({"status":"FAIL_CLOSED","error":"UNEXPECTED_ERROR","detail":type(e).__name__})); sys.exit(2)
if __name__=="__main__": main()
