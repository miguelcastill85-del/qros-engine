#!/usr/bin/env python3
import argparse, hashlib, itertools, json

def enc(x): return json.dumps(x,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()
def root(rows):
    # Canonical QROS set-root definition: sort canonical row bytes first, then hash leaves in that order.
    h=hashlib.sha256()
    for b in sorted(enc(x) for x in rows): h.update(hashlib.sha256(b).digest())
    return h.hexdigest()
def base_rows(spec):
    order=tuple(spec["base_axis_order"]); axes=spec["base_axes"]
    return [dict(zip(order,p)) for p in itertools.product(*(axes[k] for k in order))]
def fams(spec):
    out={}
    for n,f in spec["filter_families"].items():
        if f["kind"]=="variants": out[n]=[dict(v) for v in f["variants"]]
        elif f["kind"]=="product_with_ema_triples": out[n]=[dict(mode=m,ema_triple=list(t)) for m,t in itertools.product(tuple(f["modes"]),tuple(tuple(x) for x in spec["ema_triples"]))]
        elif f["kind"]=="product":
            ks=tuple(f["axes"]); rows=[dict(zip(ks,p)) for p in itertools.product(*(f["axes"][k] for k in ks))]
            if f.get("exclude_all_off"): rows=[r for r in rows if any(v!="OFF" for v in r.values())]
            out[n]=rows
        else: raise ValueError(f["kind"])
    return out
def filter_packages(spec):
    f=fams(spec); names=tuple(sorted(f)); out=[]
    for depth in range(spec["max_active_filter_families"]+1):
        for chosen in itertools.combinations(names,depth):
            if not chosen: out.append({}); continue
            out.extend(dict(zip(chosen,p)) for p in itertools.product(*(f[n] for n in chosen)))
    return out
def rv(s):
    if s in ("NONE","OFF"): return None
    if s.startswith("R"): return float(s[1:])
    if s.startswith("AT"): return float(s[2:].split("R")[0])
    if "_AT_" in s: return float(s.split("_AT_")[1].split("R")[0])
    return None
def management(spec):
    a=spec["management_axes"]; ks=("stop","target","breakeven","trailing","partial"); out=[]
    for p in itertools.product(*(a[k] for k in ks)):
        d=dict(zip(ks,p)); tv,bv,pv=rv(d["target"]),rv(d["breakeven"]),rv(d["partial"])
        if not ((pv is None or tv is None or tv>pv) and (bv is None or tv is None or tv>bv)): continue
        d["same_day_exit"]=True; out.append(d)
    return out
def main():
    p=argparse.ArgumentParser(); p.add_argument("spec"); p.add_argument("--out",required=True); a=p.parse_args(); s=json.load(open(a.spec,encoding="utf-8"))
    br=base_rows(s); fp=filter_packages(s); mg=management(s)
    d={"base_tuple_count":len(br),"base_tuple_root_sha256":root(br),"filter_package_count":len(fp),"filter_package_root_sha256":root(fp),"raw_signal_config_count":len(br)*len(fp),"management_valid_count":len(mg),"management_root_sha256":root(mg),"execution_profile_count":len(s["execution_profiles"]),"stress_profile_count":len(s["stress_profiles"]),"enumerator":"B_v3","root_definition":"SORT_CANONICAL_ROW_BYTES_THEN_SHA256_LEAF_AGGREGATE"}
    open(a.out,"w",encoding="utf-8").write(json.dumps(d,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
