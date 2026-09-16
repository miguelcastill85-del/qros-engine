#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

def stable(o):
    return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def check(x):
    needed={"canonical_signal_config_id","event_id","entry_trigger_timestamp","entry_timestamp","exit_timestamp"}
    if not isinstance(x,dict) or not needed.issubset(x): raise RuntimeError("TRADE_FIELD_MISSING")
    if type(x["entry_trigger_timestamp"]) is not int or type(x["entry_timestamp"]) is not int or type(x["exit_timestamp"]) is not int: raise RuntimeError("TIMESTAMP_INVALID")
    if x["entry_trigger_timestamp"]>x["entry_timestamp"] or x["entry_timestamp"]>x["exit_timestamp"]: raise RuntimeError("TRADE_TIME_ORDER_INVALID")

def rank(x): return (x["entry_trigger_timestamp"],x["entry_timestamp"],x["event_id"],x.get("scenario_id",""))

def oracle(rows):
    for x in rows: check(x)
    candidates=sorted({x["canonical_signal_config_id"] for x in rows}); keep=[]; drop=[]
    for c in candidates:
        pool=sorted([x for x in rows if x["canonical_signal_config_id"]==c],key=rank); free_after=None
        while pool:
            x=pool.pop(0); trig=x["entry_trigger_timestamp"]
            if free_after is not None and not (trig>free_after):
                drop.append({"canonical_signal_config_id":c,"event_id":x["event_id"],"entry_trigger_timestamp":trig,"blocking_exit_timestamp":free_after,"reason":"OVERLAP_ACTIVE_POSITION"})
            else:
                keep.append(x); free_after=x["exit_timestamp"]
    keep=sorted(keep,key=lambda x:(x["canonical_signal_config_id"],)+rank(x)); drop=sorted(drop,key=lambda x:(x["canonical_signal_config_id"],x["entry_trigger_timestamp"],x["event_id"]))
    return keep,drop

def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",required=True); p.add_argument("--out-dir",required=True); a=p.parse_args()
    rows=[json.loads(s) for s in Path(a.input).read_text().splitlines() if s.strip()]; k,d=oracle(rows); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    ka=out/"admitted_trades.jsonl"; dr=out/"rejected_events.jsonl"; ka.write_text("".join(stable(x)+"\n" for x in k)); dr.write_text("".join(stable(x)+"\n" for x in d))
    s={"schema":"QROS_SEED0076_OVERLAP_ADMISSION_SUMMARY_1.0","policy":"SERIAL_SAME_CANDIDATE_REJECT_WHILE_ACTIVE_V1","input_count":len(rows),"admitted_count":len(k),"rejected_count":len(d),"admitted_sha256":hashlib.sha256(ka.read_bytes()).hexdigest(),"rejected_sha256":hashlib.sha256(dr.read_bytes()).hexdigest(),"economic_pnl_read":False}
    (out/"summary.json").write_text(stable(s)+"\n"); print(stable(s))
if __name__=="__main__": main()
