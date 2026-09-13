#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np

DT=np.dtype([("ts","<i8"),("bid","<i4"),("ask","<i4"),("flags","u1")],align=False)
HASH_CHUNK=16*1024*1024
AUDIT_ROWS=5_000_000

def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(HASH_CHUNK),b""): h.update(b)
    return h.hexdigest()

def audit_file(path: Path,spec: dict,record_bytes: int):
    exp_bytes=int(spec["target_bytes"]); exp_records=int(spec["target_records"]); exp_sha=spec["target_sha256"].lower(); errors=[]
    if not path.is_file(): return {"status":"FAIL","file":str(path),"errors":["FILE_MISSING"]}
    size=path.stat().st_size
    if size!=exp_bytes: errors.append(f"BYTE_COUNT:{size}!={exp_bytes}")
    if record_bytes!=DT.itemsize: errors.append(f"DTYPE_ITEMSIZE:{DT.itemsize}!={record_bytes}")
    if size%record_bytes: errors.append("FILE_NOT_RECORD_ALIGNED")
    actual_sha=sha256_file(path) if not errors or size%record_bytes==0 else None
    if actual_sha!=exp_sha: errors.append("SHA256_MISMATCH")
    records=size//record_bytes if size%record_bytes==0 else 0
    if records!=exp_records: errors.append(f"RECORD_COUNT:{records}!={exp_records}")
    stats={"records":records,"bytes":size,"sha256":actual_sha,"out_of_order":0,"crossed_spread":0,"zero_spread":0,"nonpositive_bid":0,"nonpositive_ask":0}
    if records and size%record_bytes==0:
        mm=np.memmap(path,dtype=DT,mode="r",shape=(records,)); prev_last=None
        for start in range(0,records,AUDIT_ROWS):
            x=mm[start:min(start+AUDIT_ROWS,records)]; ts=x["ts"]; bid=x["bid"]; ask=x["ask"]
            if prev_last is not None and int(ts[0])<prev_last: stats["out_of_order"]+=1
            if len(ts)>1: stats["out_of_order"]+=int(np.count_nonzero(ts[1:]<ts[:-1]))
            stats["crossed_spread"]+=int(np.count_nonzero(ask<bid)); stats["zero_spread"]+=int(np.count_nonzero(ask==bid))
            stats["nonpositive_bid"]+=int(np.count_nonzero(bid<=0)); stats["nonpositive_ask"]+=int(np.count_nonzero(ask<=0)); prev_last=int(ts[-1])
        stats["first_timestamp_ms"]=int(mm[0]["ts"]); stats["last_timestamp_ms"]=int(mm[-1]["ts"]); del mm
    if stats["out_of_order"]!=0: errors.append("OUT_OF_ORDER_TICKS")
    if stats["nonpositive_bid"]!=0 or stats["nonpositive_ask"]!=0: errors.append("NONPOSITIVE_PRICE")
    return {"status":"PASS" if not errors else "FAIL","file":str(path),"errors":errors,"stats":stats}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",required=True); ap.add_argument("--data-dir",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    m=json.loads(Path(a.manifest).read_text(encoding="utf-8")); rb=int(m["record_bytes"]); data=Path(a.data_dir); results={}
    for asset in ("NQX","XAUUSD"): results[asset]=audit_file(data/m[asset]["target_file"],m[asset],rb)
    ok=all(v["status"]=="PASS" for v in results.values())
    r={"schema":"QROS_SEED0076_DATA_EXECUTION_READY_PREFLIGHT_1.0","seed":"WEB_SEED_0076","status":"PASS" if ok else "FAIL","decision":"DATA_EXECUTION_READY" if ok else "DATA_EXECUTION_NOT_READY","manifest":str(Path(a.manifest)),"results":results,"crossed_spreads_allowed_for_audit_but_never_fill":True,"zero_spreads_preserved_no_artificial_advantage":True,"economic_pnl_read":False,"holdout_open":False}
    r["receipt_sha256"]=hashlib.sha256(canonical(r)).hexdigest(); Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8"); print(r["decision"])
    return 0 if ok else 2
if __name__=="__main__": raise SystemExit(main())
