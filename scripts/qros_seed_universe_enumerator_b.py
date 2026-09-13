#!/usr/bin/env python3
import argparse, hashlib, itertools, json

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",",":"), sort_keys=True).encode()

def merkleish(rows):
    leaves=sorted(hashlib.sha256(canonical(x)).digest() for x in rows)
    h=hashlib.sha256()
    for x in leaves: h.update(x)
    return h.hexdigest()

def expand(spec):
    fam={}
    for name,f in spec["filter_families"].items():
        if f["kind"]=="variants": fam[name]=[dict(x) for x in f["variants"]]
        elif f["kind"]=="product_with_ema_triples":
            fam[name]=[dict(mode=m,ema_triple=list(t)) for m,t in itertools.product(tuple(f["modes"]),tuple(tuple(x) for x in spec["ema_triples"]))]
        elif f["kind"]=="product":
            keys=tuple(f["axes"]); vals=tuple(tuple(f["axes"][k]) for k in keys)
            rows=[dict(zip(keys,p)) for p in itertools.product(*vals)]
            if f.get("exclude_all_off"): rows=[r for r in rows if any(v!="OFF" for v in r.values())]
            fam[name]=rows
        else: raise ValueError(f["kind"])
    names=tuple(sorted(fam)); out=[]
    for depth in range(spec["max_active_filter_families"]+1):
        for chosen in itertools.combinations(names,depth):
            if not chosen: out.append({}); continue
            for vals in itertools.product(*(fam[n] for n in chosen)): out.append(dict(zip(chosen,vals)))
    return out

def bases(spec):
    a=spec["base_axes"]; keys=("asset","side","timeframe","fractal_window","trigger")
    return [dict(zip(keys,p)) for p in itertools.product(*(a[k] for k in keys))]

def rv(s):
    if s in ("NONE","OFF"): return None
    if s.startswith("R"): return float(s[1:])
    if s.startswith("AT"): return float(s[2:].split("R")[0])
    if "_AT_" in s: return float(s.split("_AT_")[1].split("R")[0])
    return None

def management(spec):
    a=spec["management_axes"]; keys=("stop","target","breakeven","trailing","partial"); rows=[]
    for p in itertools.product(*(a[k] for k in keys)):
        d=dict(zip(keys,p)); tv,bv,pv=rv(d["target"]),rv(d["breakeven"]),rv(d["partial"])
        if not ((pv is None or tv is None or tv>pv) and (bv is None or tv is None or tv>bv)): continue
        d["same_day_exit"]=True; rows.append(d)
    return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument("spec"); p.add_argument("--out",required=True); a=p.parse_args(); s=json.load(open(a.spec,encoding="utf-8"))
    br=bases(s); fp=expand(s); mg=management(s)
    d={"schema":"QROS_FACTORIZED_SIGNAL_UNIVERSE_ROOT_1.0","base_tuple_count":len(br),"base_tuple_root_sha256":merkleish(br),"filter_package_count":len(fp),"filter_package_root_sha256":merkleish(fp),"cartesian_mapping":"CONFIG=MERGE(BASE_TUPLE,{filters:FILTER_PACKAGE}); canonical JSON sorted keys; ID=SHA256(bytes)","raw_signal_config_count":len(br)*len(fp)}
    d["factorized_signal_universe_root_sha256"]=hashlib.sha256(canonical(d)).hexdigest(); d.update({"management_valid_count":len(mg),"management_root_sha256":merkleish(mg),"execution_profile_count":len(s["execution_profiles"]),"stress_profile_count":len(s["stress_profiles"]),"enumerator":"B"})
    open(a.out,"w",encoding="utf-8").write(json.dumps(d,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
