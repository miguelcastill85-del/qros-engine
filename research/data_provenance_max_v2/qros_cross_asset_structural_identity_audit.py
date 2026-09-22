#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np

REC=17
DT=np.dtype([("ts","<i8"),("bid","<i4"),("ask","<i4"),("flags","u1")])
KNOWN_FLAGS={2,4,6}

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(8<<20),b""): h.update(b)
    return h.hexdigest()

def scan(path, expected_asset, unit):
    p=Path(path); h=hashlib.sha256()
    with zipfile.ZipFile(p) as z:
        names=z.namelist()
        if "PART_META.json" not in names:
            raise RuntimeError(f"{p}: PART_META.json missing")
        meta_raw=z.read("PART_META.json"); meta=json.loads(meta_raw)
        bins=[i for i in z.infolist() if i.filename.endswith(".bin") and i.file_size%REC==0]
        if len(bins)!=1: raise RuntimeError(f"{p}: expected one PACKED17 payload")
        info=bins[0]
        if meta.get("asset")!=expected_asset: raise RuntimeError(f"{p}: asset mismatch")
        if meta.get("payload_member")!=info.filename: raise RuntimeError(f"{p}: member mismatch")
        n=0; mn_b=None; mx_b=None; mn_a=None; mx_a=None; flags={}
        with z.open(info) as f:
            while True:
                b=f.read(REC*1_000_000)
                if not b: break
                h.update(b)
                a=np.frombuffer(b,dtype=DT)
                if n==0: first_ts=int(a["ts"][0])
                last_ts=int(a["ts"][-1]); n+=len(a)
                vals,c=np.unique(a["flags"],return_counts=True)
                for v,k in zip(vals,c): flags[int(v)]=flags.get(int(v),0)+int(k)
                bmn,bmx=int(a["bid"].min()),int(a["bid"].max())
                amn,amx=int(a["ask"].min()),int(a["ask"].max())
                mn_b=bmn if mn_b is None else min(mn_b,bmn); mx_b=bmx if mx_b is None else max(mx_b,bmx)
                mn_a=amn if mn_a is None else min(mn_a,amn); mx_a=amx if mx_a is None else max(mx_a,amx)
        payload_sha=h.hexdigest()
        checks={
            "asset_tag":meta.get("asset")==expected_asset,
            "payload_sha":payload_sha==meta.get("payload_sha256"),
            "records":n==meta.get("records"),
            "payload_bytes":info.file_size==meta.get("payload_bytes")==n*REC,
            "first_ts":first_ts==meta.get("first_timestamp_ms"),
            "last_ts":last_ts==meta.get("last_timestamp_ms"),
            "flags_domain":set(flags).issubset(KNOWN_FLAGS),
            "zip_sha":sha256_file(p)==meta.get("sha256") if meta.get("sha256") else True
        }
        return {
            "file":p.name,"expected_asset":expected_asset,"unit":unit,
            "zip_sha256":sha256_file(p),"part_meta_sha256":sha256_bytes(meta_raw),
            "payload_member":info.filename,"payload_sha256":payload_sha,
            "carrier_sha256":meta.get("carrier_sha256"),"records":n,
            "first_timestamp_ms":first_ts,"last_timestamp_ms":last_ts,
            "bid_min":mn_b*unit,"bid_max":mx_b*unit,
            "ask_min":mn_a*unit,"ask_max":mx_a*unit,
            "flags":flags,"checks":checks,"pass":all(checks.values())
        }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True)
    ap.add_argument("--nqx",nargs="+",required=True)
    ap.add_argument("--xau",nargs="+",required=True)
    a=ap.parse_args()
    nqx=[scan(p,"NQX",0.1) for p in a.nqx]
    xau=[scan(p,"XAU",0.01) for p in a.xau]
    all_rows=nqx+xau
    carrier_separation=len({r["carrier_sha256"] for r in all_rows})==2
    cross_payload_collision=len({r["payload_sha256"] for r in all_rows})==len(all_rows)
    member_prefix_ok=all(r["payload_member"].startswith(r["expected_asset"]+"_PACKED17_") for r in all_rows)
    r={"schema":"QROS_CROSS_ASSET_STRUCTURAL_IDENTITY_AUDIT_1.0",
       "scope":"boundary carriers + full manifests; non-economic",
       "assets":{"NQX":nqx,"XAU":xau},
       "cross_checks":{"distinct_carrier_roots":carrier_separation,
                       "no_payload_hash_collision_in_scanned_boundaries":cross_payload_collision,
                       "member_prefix_matches_asset":member_prefix_ok},
       "limitations":["Does not prove provider/source acquisition binding.",
                      "Does not prove absence of a single misplaced row inside unscanned interior payloads.",
                      "Does not resolve NQX roll/back-adjustment semantics or timezone/DST."],
       "pass":all(x["pass"] for x in all_rows) and carrier_separation and cross_payload_collision and member_prefix_ok}
    payload=json.dumps(r,sort_keys=True,separators=(",",":")).encode()
    r["payload_sha256"]=hashlib.sha256(payload).hexdigest()
    Path(a.out).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__=="__main__": main()
