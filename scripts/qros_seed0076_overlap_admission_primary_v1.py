#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

POLICY = "SERIAL_SAME_CANDIDATE_REJECT_WHILE_ACTIVE_V1"

def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def key(t):
    return (int(t["entry_trigger_timestamp"]), int(t["entry_timestamp"]), str(t["event_id"]), str(t.get("scenario_id","")))

def validate(t):
    req=("canonical_signal_config_id","event_id","entry_trigger_timestamp","entry_timestamp","exit_timestamp")
    if not isinstance(t,dict) or any(k not in t for k in req):
        raise ValueError("TRADE_FIELD_MISSING")
    if not isinstance(t["canonical_signal_config_id"],str) or not t["canonical_signal_config_id"]:
        raise ValueError("CANDIDATE_ID_INVALID")
    for k in ("entry_trigger_timestamp","entry_timestamp","exit_timestamp"):
        if not isinstance(t[k],int):
            raise ValueError("TIMESTAMP_INVALID")
    if t["entry_trigger_timestamp"] > t["entry_timestamp"] or t["entry_timestamp"] > t["exit_timestamp"]:
        raise ValueError("TRADE_TIME_ORDER_INVALID")

def apply(rows):
    groups={}
    for row in rows:
        validate(row)
        groups.setdefault(row["canonical_signal_config_id"],[]).append(row)
    accepted=[]; rejected=[]
    for cid in sorted(groups):
        active_exit=None
        for row in sorted(groups[cid], key=key):
            trigger=int(row["entry_trigger_timestamp"])
            if active_exit is not None and trigger <= active_exit:
                rejected.append({"canonical_signal_config_id":cid,"event_id":row["event_id"],"entry_trigger_timestamp":trigger,"blocking_exit_timestamp":active_exit,"reason":"OVERLAP_ACTIVE_POSITION"})
                continue
            accepted.append(row)
            active_exit=int(row["exit_timestamp"])
    accepted.sort(key=lambda r:(r["canonical_signal_config_id"],)+key(r))
    rejected.sort(key=lambda r:(r["canonical_signal_config_id"],r["entry_trigger_timestamp"],r["event_id"]))
    return accepted,rejected

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out-dir",required=True); a=ap.parse_args()
    rows=[json.loads(x) for x in Path(a.input).read_text().splitlines() if x.strip()]
    acc,rej=apply(rows); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    apath=out/"admitted_trades.jsonl"; rpath=out/"rejected_events.jsonl"
    apath.write_text("".join(canon(x)+"\n" for x in acc)); rpath.write_text("".join(canon(x)+"\n" for x in rej))
    summary={"schema":"QROS_SEED0076_OVERLAP_ADMISSION_SUMMARY_1.0","policy":POLICY,"input_count":len(rows),"admitted_count":len(acc),"rejected_count":len(rej),"admitted_sha256":hashlib.sha256(apath.read_bytes()).hexdigest(),"rejected_sha256":hashlib.sha256(rpath.read_bytes()).hexdigest(),"economic_pnl_read":False}
    (out/"summary.json").write_text(canon(summary)+"\n"); print(canon(summary))
if __name__=="__main__": main()
