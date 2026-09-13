#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ASSETS=("XAUUSD","NQX")
SIDES=("BUY","SELL")
TIMEFRAMES=("M1","M2","M3","M4","M5","M6","M10","M12","M15","M20","M30","H1","H2","H3","H4")
BASE_TUPLES_PER_SHARD=72
FILTER_PACKAGES=11176
SIGNALS_PER_SHARD=804672
EXPECTED_ROOT="629093e113aa4fa22f7640ff32c9f4affb4b0f89797f21420a3a9c8293e99f21"

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def descriptor(asset,side,timeframe):
    return {
        "asset":asset,
        "side":side,
        "timeframe":timeframe,
        "base_tuples":BASE_TUPLES_PER_SHARD,
        "filter_packages":FILTER_PACKAGES,
        "signal_configs":SIGNALS_PER_SHARD,
    }

def build_manifest():
    rows=[]
    for asset in ASSETS:
        for side in SIDES:
            for tf in TIMEFRAMES:
                d=descriptor(asset,side,tf)
                b=canonical(d)
                rows.append({"descriptor":d,"descriptor_sha256":hashlib.sha256(b).hexdigest(),"shard_id":hashlib.sha256(b).hexdigest()})
    rows.sort(key=lambda r: canonical(r["descriptor"]))
    h=hashlib.sha256()
    for r in rows:
        h.update(bytes.fromhex(r["descriptor_sha256"]))
    manifest={
        "schema":"QROS_SEED0076_GATE_A_SHARD_MANIFEST_1.0",
        "seed":"WEB_SEED_0076",
        "ordering":"lexicographic canonical descriptor bytes",
        "shard_count":len(rows),
        "total_signal_configs":sum(r["descriptor"]["signal_configs"] for r in rows),
        "shard_descriptor_root_sha256":h.hexdigest(),
        "shards":rows,
    }
    if manifest["shard_count"]!=60: raise RuntimeError("SHARD_COUNT_MISMATCH")
    if manifest["total_signal_configs"]!=48280320: raise RuntimeError("TOTAL_CONFIG_COUNT_MISMATCH")
    if manifest["shard_descriptor_root_sha256"]!=EXPECTED_ROOT: raise RuntimeError("ROOT_MISMATCH")
    return manifest

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ns=ap.parse_args()
    m=build_manifest()
    Path(ns.out).write_text(json.dumps(m,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(m["shard_descriptor_root_sha256"])
if __name__=="__main__": main()
