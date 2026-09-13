#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, itertools, json
from pathlib import Path

def enc(o): return json.dumps(o,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()

def variants(spec,name):
    f=spec["filter_families"][name]
    if f["kind"]=="variants": rows=[dict(v) for v in f["variants"]]
    elif f["kind"]=="product_with_ema_triples":
        rows=[{"ema_triple":list(t),"mode":mode} for t in spec["ema_triples"] for mode in f["modes"]]
    elif f["kind"]=="product":
        ks=list(f["axes"]); rows=[]
        for vals in itertools.product(*(f["axes"][k] for k in ks)):
            d={k:v for k,v in zip(ks,vals)}
            if f.get("exclude_all_off") and not any(v!="OFF" for v in d.values()): continue
            rows.append(d)
    else: raise ValueError(f["kind"])
    return sorted(rows,key=enc)

def packages(spec):
    names=sorted(spec["filter_families"]); vv={n:variants(spec,n) for n in names}; rows=[{}]
    for n in names: rows.extend({n:v} for v in vv[n])
    for i,a in enumerate(names):
        for b in names[i+1:]: rows.extend({a:va,b:vb} for va in vv[a] for vb in vv[b])
    return sorted(rows,key=enc)

def bases(spec,asset,side,tf):
    free=("fractal_window","tie_policy","rearm_mode","trigger"); rows=[]
    for vals in itertools.product(*(spec["base_axes"][k] for k in free)):
        d={"asset":asset,"side":side,"timeframe":tf}
        for k,v in zip(free,vals): d[k]=v
        rows.append(d)
    return sorted(rows,key=enc)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--spec",required=True); ap.add_argument("--asset",required=True); ap.add_argument("--side",required=True); ap.add_argument("--timeframe",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    s=json.loads(Path(a.spec).read_text()); bp=bases(s,a.asset,a.side,a.timeframe); fp=packages(s); h=hashlib.sha256(); n=0
    for b in bp:
        for p in fp:
            c=dict(b); c["filters"]=p; h.update(hashlib.sha256(enc(c)).digest()); n+=1
    r={"schema":"QROS_SEED0076_CONFIG_STREAM_ORACLE_1.0","asset":a.asset,"side":a.side,"timeframe":a.timeframe,"base_tuple_count":len(bp),"filter_package_count":len(fp),"config_count":n,"ordered_config_id_stream_root_sha256":h.hexdigest(),"oracle":"independent itertools construction","economic_pnl_read":False}
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n"); print(n,h.hexdigest())
if __name__=="__main__": main()
