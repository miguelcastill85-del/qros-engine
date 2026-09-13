#!/usr/bin/env python3
import argparse, hashlib, json

def cj(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def root(rows):
    h=hashlib.sha256()
    for b in sorted(cj(x) for x in rows): h.update(hashlib.sha256(b).digest())
    return h.hexdigest()

def product_rows(axes,order,exclude_all_off=False):
    out=[]
    def rec(i,d):
        if i==len(order):
            if exclude_all_off and all(v=="OFF" for v in d.values()): return
            out.append(dict(d)); return
        k=order[i]
        for v in axes[k]: d[k]=v; rec(i+1,d)
        d.pop(k,None)
    rec(0,{})
    return out

def family_variants(spec,name):
    f=spec["filter_families"][name]
    if f["kind"]=="variants": return [dict(x) for x in f["variants"]]
    if f["kind"]=="product_with_ema_triples": return [{"mode":m,"ema_triple":t} for m in f["modes"] for t in spec["ema_triples"]]
    if f["kind"]=="product": return product_rows(f["axes"],list(f["axes"]),bool(f.get("exclude_all_off")))
    raise ValueError(f["kind"])

def filter_packages(spec):
    fam={n:family_variants(spec,n) for n in sorted(spec["filter_families"])}; names=list(fam); out=[{}]
    for n in names:
        for v in fam[n]: out.append({n:v})
    if spec["max_active_filter_families"]>=2:
        for i,a in enumerate(names):
            for b in names[i+1:]:
                for va in fam[a]:
                    for vb in fam[b]: out.append({a:va,b:vb})
    return out

def rv(s):
    if s in ("NONE","OFF"): return None
    if s.startswith("R"): return float(s[1:])
    if s.startswith("AT"): return float(s[2:].split("R")[0])
    if "_AT_" in s: return float(s.split("_AT_")[1].split("R")[0])
    return None

def management(spec):
    a=spec["management_axes"]; order=["stop","target","breakeven","trailing","partial"]; rows=product_rows(a,order)
    out=[]
    for d in rows:
        tv,bv,pv=rv(d["target"]),rv(d["breakeven"]),rv(d["partial"])
        if pv is not None and tv is not None and tv<=pv: continue
        if bv is not None and tv is not None and tv<=bv: continue
        d=dict(d); d["same_day_exit"]=True; out.append(d)
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument("spec"); p.add_argument("--out",required=True); a=p.parse_args(); s=json.load(open(a.spec,encoding="utf-8"))
    br=product_rows(s["base_axes"],s["base_axis_order"]); fp=filter_packages(s); mg=management(s)
    d={"base_tuple_count":len(br),"base_tuple_root_sha256":root(br),"filter_package_count":len(fp),"filter_package_root_sha256":root(fp),"raw_signal_config_count":len(br)*len(fp),"management_valid_count":len(mg),"management_root_sha256":root(mg),"execution_profile_count":len(s["execution_profiles"]),"stress_profile_count":len(s["stress_profiles"]),"enumerator":"A_v2"}
    open(a.out,"w",encoding="utf-8").write(json.dumps(d,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
