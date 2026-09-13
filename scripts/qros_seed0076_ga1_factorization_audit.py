#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from collections import Counter
from pathlib import Path

TRANSFORM=("BREAKOUT_BUFFER","RETEST_ENTRY")

def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def load_streamer(path):
    s=importlib.util.spec_from_file_location("qros_config_stream",path)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",required=True); ap.add_argument("--streamer",required=True); ap.add_argument("--out",required=True)
    a=ap.parse_args()
    spec=json.loads(Path(a.spec).read_text(encoding="utf-8")); mod=load_streamer(a.streamer)
    packages=mod.filter_packages(spec)
    classes=Counter(); signatures=set(); rows=[]; failures=[]
    for p in packages:
        transforms={k:p[k] for k in TRANSFORM if k in p}
        gates={k:v for k,v in p.items() if k not in TRANSFORM}
        rebuilt=dict(transforms); rebuilt.update(gates)
        if canonical(rebuilt)!=canonical(p): failures.append("NON_INVERTIBLE_PACKAGE")
        if len(transforms)+len(gates)>spec["max_active_filter_families"]: failures.append("DEPTH_OVERFLOW")
        tkeys=tuple(sorted(transforms))
        if not tkeys: cls="NO_TRANSFORM"
        elif tkeys==("BREAKOUT_BUFFER",): cls="BUFFER_ONLY"
        elif tkeys==("RETEST_ENTRY",): cls="RETEST_ONLY"
        elif tkeys==("BREAKOUT_BUFFER","RETEST_ENTRY"): cls="BUFFER_RETEST"
        else: cls="UNEXPECTED"
        classes[cls]+=1
        sig=canonical(transforms)
        signatures.add(sig)
        rows.append({"package_sha256":hashlib.sha256(canonical(p)).hexdigest(),
                     "transform_signature_sha256":hashlib.sha256(sig).hexdigest(),
                     "gate_signature_sha256":hashlib.sha256(canonical(gates)).hexdigest()})
    h=hashlib.sha256()
    for b in sorted(canonical(r) for r in rows): h.update(hashlib.sha256(b).digest())
    signature_root=hashlib.sha256(b"".join(hashlib.sha256(b).digest() for b in sorted(signatures))).hexdigest()
    receipt={
      "schema":"QROS_SEED0076_GA1_FILTER_FACTORIZATION_AUDIT_1.0",
      "seed":"WEB_SEED_0076","status":"PASS" if not failures else "FAIL",
      "filter_package_count":len(packages),"operator_class_counts":dict(sorted(classes.items())),
      "unique_transform_signature_count":len(signatures),
      "base_tuples_per_shard":72,
      "candidate_carriers_per_shard":72*len(signatures),
      "total_candidate_carriers":60*72*len(signatures),
      "package_factorization_map_root_sha256":h.hexdigest(),
      "transform_signature_root_sha256":signature_root,
      "invertible_package_mapping":not failures,
      "failures":failures,"economic_pnl_read":False,"holdout_open":False}
    if len(packages)!=11176: receipt["failures"].append("FILTER_PACKAGE_COUNT_MISMATCH")
    if len(signatures)!=28: receipt["failures"].append("TRANSFORM_SIGNATURE_COUNT_MISMATCH")
    receipt["status"]="PASS" if not receipt["failures"] else "FAIL"
    raw=canonical(receipt); receipt["receipt_sha256"]=hashlib.sha256(raw).hexdigest()
    Path(a.out).write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(receipt["status"],len(packages),len(signatures),dict(classes))
    return 0 if receipt["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
