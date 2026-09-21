#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, time
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORKER_PATH=HERE/"qros_seed0076_ga1_shard_worker_v223.py"
WRAPPER_PATH=HERE/"qros_seed0076_ga1_cached_wrapper_v236.py"
EXPECTED_WORKER_BLOB="c77e0a5156c5bb1a874d3c33fde49f162a2a3041"
EXPECTED_WRAPPER_BLOB="2ab8e0cd7b2cd576289cd5c555e3a5227e10e78f"
EXPECTED_M12_CONFIG_ROOT="07c6c3fc57503198b0db78afc6e587948b1cb449d745bc51cdd1604a3e4ca714"

def git_blob_sha1(p:Path)->str:
    b=p.read_bytes()
    h=hashlib.sha1()
    h.update(f"blob {len(b)}\0".encode())
    h.update(b)
    return h.hexdigest()

if git_blob_sha1(WORKER_PATH)!=EXPECTED_WORKER_BLOB:
    raise RuntimeError("WORKER_BLOB_MISMATCH")
if git_blob_sha1(WRAPPER_PATH)!=EXPECTED_WRAPPER_BLOB:
    raise RuntimeError("WRAPPER_BLOB_MISMATCH")

spec=importlib.util.spec_from_file_location("qros_worker_phase_profile",WORKER_PATH)
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

PHASE=defaultdict(lambda:{"calls":0,"seconds":0.0})

def wrap(name,fn):
    def inner(*a,**kw):
        t0=time.perf_counter()
        try:
            return fn(*a,**kw)
        finally:
            d=PHASE[name]
            d["calls"]+=1
            d["seconds"]+=time.perf_counter()-t0
    return inner

# Functions that partition the current worker's cost without changing return values.
w.config_id=wrap("config_id",w.config_id)
w.filter_packages=wrap("filter_packages",w.filter_packages)
w.package_partition=wrap("package_partition",w.package_partition)
w.shard_base_rows=wrap("shard_base_rows",w.shard_base_rows)
w.build_structural_cache=wrap("build_structural_cache",w.build_structural_cache)
w.raw_cache_for=wrap("raw_cache_for",w.raw_cache_for)
w.next_replacement_source=wrap("next_replacement_source",w.next_replacement_source)
w.filter_raw_to_candidates=wrap("filter_raw_to_candidates",w.filter_raw_to_candidates)
w.session_ms_for_candidates=wrap("session_ms_for_candidates",w.session_ms_for_candidates)
w.CarrierMaskEngine=wrap("CarrierMaskEngine_ctor",w.CarrierMaskEngine)
w.group_packages_exact=wrap("group_packages_exact",w.group_packages_exact)
w.finalize_artifacts=wrap("finalize_artifacts",w.finalize_artifacts)

_orig_register=w.ClassDB.register
def _register(self,*a,**kw):
    t0=time.perf_counter()
    try:
        return _orig_register(self,*a,**kw)
    finally:
        d=PHASE["ClassDB.register"]
        d["calls"]+=1
        d["seconds"]+=time.perf_counter()-t0
w.ClassDB.register=_register

_orig_init=w.ClassDB.__init__
def _init(self,*a,**kw):
    t0=time.perf_counter()
    try:
        return _orig_init(self,*a,**kw)
    finally:
        d=PHASE["ClassDB.__init__"]
        d["calls"]+=1
        d["seconds"]+=time.perf_counter()-t0
w.ClassDB.__init__=_init

_orig_close=w.ClassDB.close
def _close(self,*a,**kw):
    t0=time.perf_counter()
    try:
        return _orig_close(self,*a,**kw)
    finally:
        d=PHASE["ClassDB.close"]
        d["calls"]+=1
        d["seconds"]+=time.perf_counter()-t0
w.ClassDB.close=_close

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-json",required=True)
    ap.add_argument("--spec",required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--receipt",required=True)
    ap.add_argument("--ticks",required=True)
    ap.add_argument("--bar-root",required=True)
    ap.add_argument("--ind-root",required=True)
    ap.add_argument("--point",type=float,required=True)
    ap.add_argument("--only-group-index",type=int,required=True)
    a=ap.parse_args()

    if a.only_group_index not in range(24):
        raise SystemExit("GROUP_INDEX_0_23_REQUIRED")

    shard=json.loads(Path(a.shard_json).read_text(encoding="utf-8"))
    out=Path(a.out_dir)
    out.mkdir(parents=True,exist_ok=True)

    t0=time.perf_counter()
    res=w.process(
        shard,a.spec,a.ticks,a.bar_root,a.ind_root,a.point,out,
        EXPECTED_M12_CONFIG_ROOT,None,a.only_group_index
    )
    wall=time.perf_counter()-t0

    expected=33528
    status="PASS" if (
        res["input_config_count"]==expected and
        res["ordered_config_id_stream_root_sha256"]==EXPECTED_M12_CONFIG_ROOT
    ) else "FAIL"

    accounted=sum(v["seconds"] for v in PHASE.values())
    rows=[
        {"phase":k,"calls":int(v["calls"]),"seconds":float(v["seconds"]),
         "fraction_of_wall":(float(v["seconds"])/wall if wall else 0.0)}
        for k,v in PHASE.items()
    ]
    rows.sort(key=lambda x:(-x["seconds"],x["phase"]))

    receipt={
        "schema":"QROS_SEED0076_M12_PHASE_PROFILE_1.0",
        "status":status,
        "group_index":a.only_group_index,
        "processed_signal_configs":res["input_config_count"],
        "ordered_config_id_stream_root_sha256":res["ordered_config_id_stream_root_sha256"],
        "worker_git_blob_sha1":EXPECTED_WORKER_BLOB,
        "wrapper_git_blob_sha1":EXPECTED_WRAPPER_BLOB,
        "wall_seconds":wall,
        "phase_rows":rows,
        "sum_inclusive_phase_seconds":accounted,
        "inclusive_overlap_warning":"Phase timings are inclusive and nested; sums can exceed wall time. Use call-specific rows and cProfile together for attribution.",
        "worker_metrics":res["metrics"],
        "worker_elapsed_seconds":res["elapsed_seconds"],
        "economic_pnl_read":False,
        "holdout_open":False,
        "ga2_open":False,
    }
    Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":status,"group":a.only_group_index,"wall_seconds":round(wall,6),"top_phases":rows[:8]},sort_keys=True))
    return 0 if status=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
