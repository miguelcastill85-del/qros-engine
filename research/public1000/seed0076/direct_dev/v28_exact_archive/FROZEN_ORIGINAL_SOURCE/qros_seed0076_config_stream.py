#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, itertools, json
from pathlib import Path

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def product_rows(axes,order,exclude_all_off=False):
    rows=[]
    for vals in itertools.product(*(axes[k] for k in order)):
        d=dict(zip(order,vals))
        if exclude_all_off and all(v=="OFF" for v in d.values()): continue
        rows.append(d)
    rows.sort(key=canonical)
    return rows

def family_variants(spec,name):
    f=spec["filter_families"][name]
    if f["kind"]=="variants":
        rows=[dict(x) for x in f["variants"]]
    elif f["kind"]=="product_with_ema_triples":
        rows=[{"mode":m,"ema_triple":list(t)} for m,t in itertools.product(f["modes"],spec["ema_triples"])]
    elif f["kind"]=="product":
        order=tuple(f["axes"])
        rows=product_rows(f["axes"],order,bool(f.get("exclude_all_off")))
    else:
        raise ValueError(f["kind"])
    rows.sort(key=canonical)
    return rows

def filter_packages(spec):
    fam={n:family_variants(spec,n) for n in sorted(spec["filter_families"])}
    names=tuple(sorted(fam)); out=[{}]
    for depth in range(1,int(spec["max_active_filter_families"])+1):
        for chosen in itertools.combinations(names,depth):
            for vals in itertools.product(*(fam[n] for n in chosen)):
                out.append(dict(zip(chosen,vals)))
    out.sort(key=canonical)
    return out

def shard_base_rows(spec,asset,side,timeframe):
    axes=spec["base_axes"]
    fixed={"asset":asset,"side":side,"timeframe":timeframe}
    order=[k for k in spec["base_axis_order"] if k not in fixed]
    rows=[]
    for vals in itertools.product(*(axes[k] for k in order)):
        d=dict(fixed); d.update(dict(zip(order,vals))); rows.append(d)
    rows.sort(key=canonical)
    return rows

def config_bytes(base,filters):
    d=dict(base); d["filters"]=filters
    return canonical(d)

def stream_root(spec,asset,side,timeframe,out_ids=None):
    bases=shard_base_rows(spec,asset,side,timeframe); fps=filter_packages(spec)
    h=hashlib.sha256(); count=0
    fobj=open(out_ids,"wb") if out_ids else None
    try:
        for b in bases:
            for fp in fps:
                digest=hashlib.sha256(config_bytes(b,fp)).digest()
                h.update(digest); count+=1
                if fobj: fobj.write(digest)
    finally:
        if fobj: fobj.flush(); fobj.close()
    return bases,fps,count,h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",required=True); ap.add_argument("--asset",choices=["XAUUSD","NQX"],required=True)
    ap.add_argument("--side",choices=["BUY","SELL"],required=True); ap.add_argument("--timeframe",required=True)
    ap.add_argument("--receipt",required=True); ap.add_argument("--out-ids")
    a=ap.parse_args()
    s=json.loads(Path(a.spec).read_text(encoding="utf-8"))
    if a.timeframe not in s["base_axes"]["timeframe"]: raise SystemExit("TIMEFRAME_NOT_IN_FROZEN_SPEC")
    bases,fps,count,root=stream_root(s,a.asset,a.side,a.timeframe,a.out_ids)
    receipt={"schema":"QROS_SEED0076_CONFIG_STREAM_RECEIPT_1.0","seed":"WEB_SEED_0076",
             "asset":a.asset,"side":a.side,"timeframe":a.timeframe,
             "base_tuple_count":len(bases),"filter_package_count":len(fps),
             "signal_config_count":count,"ordered_config_id_stream_root_sha256":root,
             "ordering":"base canonical bytes ascending, then filter-package canonical bytes ascending",
             "config_id":"SHA256(canonical_json(MERGE(base,{filters:filter_package})))",
             "economic_pnl_read":False,"holdout_open":False}
    receipt["receipt_sha256"]=hashlib.sha256(canonical(receipt)).hexdigest()
    Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(count,root)
if __name__=="__main__": main()
