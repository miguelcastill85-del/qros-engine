#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path
from collections import Counter
import numpy as np

DT=np.dtype([("ts","<i8"),("bid","<i4"),("ask","<i4"),("flags","u1")])
REC=17
CHUNK_RECORDS=1_000_000

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(8<<20),b""): h.update(b)
    return h.hexdigest()

def label(ms):
    import datetime as dt
    sec,milli=divmod(int(ms),1000)
    x=dt.datetime(1970,1,1)+dt.timedelta(seconds=sec,milliseconds=milli)
    return x.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def scan_zip(path,gap_ms=3600000):
    p=Path(path)
    out={"file":p.name,"zip_sha256":sha256_file(p),"records":0,"reversals":0,
         "same_ts_adjacent":0,"gaps_ge_60m":0}
    with zipfile.ZipFile(p) as z:
        bins=[i for i in z.infolist() if i.filename.endswith(".bin") and i.file_size%REC==0]
        if len(bins)!=1: raise RuntimeError(f"{p}: expected exactly one 17-byte .bin payload")
        info=bins[0]; out["payload_member"]=info.filename
        prev=None; pairs=Counter(); top=[]; n=0; rem=b""
        with z.open(info) as f:
            while True:
                b=f.read(CHUNK_RECORDS*REC)
                if not b: break
                b=rem+b; cut=(len(b)//REC)*REC; rem=b[cut:]; b=b[:cut]
                if not b: continue
                a=np.frombuffer(b,dtype=DT); ts=a["ts"]
                if "first_ts_ms" not in out: out["first_ts_ms"]=int(ts[0])
                if prev is not None:
                    d0=int(ts[0])-prev
                    out["reversals"]+=int(d0<0); out["same_ts_adjacent"]+=int(d0==0)
                    if d0>=gap_ms:
                        out["gaps_ge_60m"]+=1
                        pairs[(label(prev)[11:16],label(int(ts[0]))[11:16])]+=1
                        top.append((d0,prev,int(ts[0])))
                if len(ts)>1:
                    d=np.diff(ts)
                    out["reversals"]+=int(np.count_nonzero(d<0))
                    out["same_ts_adjacent"]+=int(np.count_nonzero(d==0))
                    for j in np.flatnonzero(d>=gap_ms):
                        aa=int(ts[j]); bb=int(ts[j+1]); dd=int(d[j])
                        out["gaps_ge_60m"]+=1
                        pairs[(label(aa)[11:16],label(bb)[11:16])]+=1
                        top.append((dd,aa,bb))
                prev=int(ts[-1]); n+=len(ts)
        if rem: raise RuntimeError(f"{p}: trailing bytes={len(rem)}")
        out["records"]=n; out["last_ts_ms"]=prev
        out["first_label"]=label(out["first_ts_ms"]); out["last_label"]=label(prev)
        out["gap_hour_pairs"]=[{"from":a,"to":b,"count":c} for (a,b),c in pairs.most_common(12)]
        out["top_gaps"]=[{"gap_ms":g,"gap_minutes":g/60000.0,"from_label":label(a),"to_label":label(b)}
                         for g,a,b in sorted(top,reverse=True)[:20]]
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True); ap.add_argument("zips",nargs="+")
    a=ap.parse_args()
    r={"schema":"QROS_TIMEBASE_STRUCTURAL_AUDIT_1.0",
       "timestamp_rendering_policy":"LABEL_ONLY_FROM_INTEGER; NOT_UTC_ASSERTION",
       "gap_threshold_ms":3600000,
       "inputs":[scan_zip(p) for p in a.zips]}
    payload=json.dumps(r,sort_keys=True,separators=(",",":")).encode()
    r["payload_sha256"]=hashlib.sha256(payload).hexdigest()
    Path(a.out).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__=="__main__": main()
