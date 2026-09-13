#!/usr/bin/env python3
import argparse, hashlib, itertools, json

def cj(x):
    return json.dumps(x, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")

def root(rows):
    h=hashlib.sha256()
    for b in sorted(cj(x) for x in rows): h.update(hashlib.sha256(b).digest())
    return h.hexdigest()

def family_variants(spec,name):
    f=spec["filter_families"][name]; k=f["kind"]
    if k=="variants": return list(f["variants"])
    if k=="product_with_ema_triples":
        return [{"mode":m,"ema_triple":t} for m in f["modes"] for t in spec["ema_triples"]]
    if k=="product":
        keys=list(f["axes"]); out=[]
        def rec(i,d):
            if i==len(keys):
                if f.get("exclude_all_off") and all(v=="OFF" for v in d.values()): return
                out.append(dict(d)); return
            key=keys[i]
            for v in f["axes"][key]: d[key]=v; rec(i+1,d)
            d.pop(key,None)
        rec(0,{})
        return out
    raise ValueError(k)

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

def base_rows(spec):
    a=spec["base_axes"]; out=[]
    for asset in a["asset"]:
      for side in a["side"]:
       for tf in a["timeframe"]:
        for fw in a["fractal_window"]:
         for tr in a["trigger"]: out.append({"asset":asset,"side":side,"timeframe":tf,"fractal_window":fw,"trigger":tr})
    return out

def rvalue(s):
    if s in ("NONE","OFF"): return None
    if s.startswith("R"): return float(s[1:])
    if s.startswith("AT"): return float(s[2:].split("R")[0])
    if "_AT_" in s: return float(s.split("_AT_")[1].split("R")[0])
    return None

def management_rows(spec):
    a=spec["management_axes"]; out=[]
    for st in a["stop"]:
      for t in a["target"]:
       for be in a["breakeven"]:
        for tr in a["trailing"]:
         for p in a["partial"]:
          tv,bv,pv=rvalue(t),rvalue(be),rvalue(p)
          if pv is not None and tv is not None and tv<=pv: continue
          if bv is not None and tv is not None and tv<=bv: continue
          out.append({"stop":st,"target":t,"breakeven":be,"trailing":tr,"partial":p,"same_day_exit":True})
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--out",required=True); ns=ap.parse_args()
    spec=json.load(open(ns.spec,encoding="utf-8")); base=base_rows(spec); fp=filter_packages(spec); mg=management_rows(spec)
    desc={"schema":"QROS_FACTORIZED_SIGNAL_UNIVERSE_ROOT_1.0","base_tuple_count":len(base),"base_tuple_root_sha256":root(base),"filter_package_count":len(fp),"filter_package_root_sha256":root(fp),"cartesian_mapping":"CONFIG=MERGE(BASE_TUPLE,{filters:FILTER_PACKAGE}); canonical JSON sorted keys; ID=SHA256(bytes)","raw_signal_config_count":len(base)*len(fp)}
    desc["factorized_signal_universe_root_sha256"]=hashlib.sha256(cj(desc)).hexdigest()
    desc.update({"management_valid_count":len(mg),"management_root_sha256":root(mg),"execution_profile_count":len(spec["execution_profiles"]),"stress_profile_count":len(spec["stress_profiles"]),"enumerator":"A"})
    open(ns.out,"w",encoding="utf-8").write(json.dumps(desc,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
