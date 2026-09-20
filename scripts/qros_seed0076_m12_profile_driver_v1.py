#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import pstats
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError:
    resource=None

HERE=Path(__file__).resolve().parent
WRAPPER=HERE/"qros_seed0076_ga1_cached_wrapper_v236.py"
EXPECTED_WRAPPER_BLOB="2ab8e0cd7b2cd576289cd5c555e3a5227e10e78f"
EXPECTED_WORKER_BLOB="c77e0a5156c5bb1a874d3c33fde49f162a2a3041"
EXPECTED_M12_CONFIG_ROOT="07c6c3fc57503198b0db78afc6e587948b1cb449d745bc51cdd1604a3e4ca714"
GOLDEN_FULL={
    "processed_signal_configs":804672,
    "distinct_mask_class_count":248010,
    "duplicate_config_count":556662,
    "zero_event_class_alias_count":69351,
    "semantic_class_root_sha256":"44cf066910a98f8d2a0988efe9f0bec14834683934369fa9972bb59e870161b0",
    "full_alias_mapping_root_sha256":"c5bec36e0b78c896f81578de5a69b42fd6f673a54630efbb8311f33e7e09c0a7",
    "ordered_config_id_stream_root_sha256":EXPECTED_M12_CONFIG_ROOT,
}
REPRESENTATIVE_GROUPS=(0,7,15,23)

def git_blob_sha1(path:Path)->str:
    b=path.read_bytes()
    h=hashlib.sha1()
    h.update(f"blob {len(b)}\0".encode())
    h.update(b)
    return h.hexdigest()

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(8*1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def tree_bytes(path:Path)->int:
    total=0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        if p.is_file():
            total+=p.stat().st_size
    return total

def usage_snapshot():
    if resource is None:
        return None
    r=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "utime":float(r.ru_utime),
        "stime":float(r.ru_stime),
        "maxrss":int(r.ru_maxrss),
        "inblock":int(getattr(r,"ru_inblock",0)),
        "oublock":int(getattr(r,"ru_oublock",0)),
    }

def usage_delta(before,after):
    if before is None or after is None:
        return None
    return {
        "child_user_seconds":max(0.0,after["utime"]-before["utime"]),
        "child_system_seconds":max(0.0,after["stime"]-before["stime"]),
        "child_maxrss_after":after["maxrss"],
        "child_inblock_delta":max(0,after["inblock"]-before["inblock"]),
        "child_oublock_delta":max(0,after["oublock"]-before["oublock"]),
    }

def profile_rows(pstats_path:Path,limit:int=60):
    st=pstats.Stats(str(pstats_path))
    rows=[]
    for (filename,line,funcname),(cc,nc,tt,ct,callers) in st.stats.items():
        rows.append({
            "file":str(filename),
            "line":int(line),
            "function":str(funcname),
            "primitive_calls":int(cc),
            "total_calls":int(nc),
            "self_seconds":float(tt),
            "cumulative_seconds":float(ct),
        })
    rows.sort(key=lambda r:(-r["cumulative_seconds"],-r["self_seconds"],r["file"],r["line"],r["function"]))
    return rows[:limit]

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=["group","full"],required=True)
    ap.add_argument("--group-index",type=int)
    ap.add_argument("--instrumentation",choices=["off","cprofile"],default="off")
    ap.add_argument("--shard-json",required=True)
    ap.add_argument("--spec",required=True)
    ap.add_argument("--ticks",required=True)
    ap.add_argument("--bar-root",required=True)
    ap.add_argument("--ind-root",required=True)
    ap.add_argument("--tick-raw-cache",required=True)
    ap.add_argument("--point",type=float,required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--benchmark-json",required=True)
    return ap.parse_args()

def main()->int:
    a=parse_args()
    if git_blob_sha1(WRAPPER)!=EXPECTED_WRAPPER_BLOB:
        raise SystemExit("WRAPPER_BLOB_MISMATCH")
    worker=HERE/"qros_seed0076_ga1_shard_worker_v223.py"
    if git_blob_sha1(worker)!=EXPECTED_WORKER_BLOB:
        raise SystemExit("WORKER_BLOB_MISMATCH")
    if a.mode=="group":
        if a.group_index not in range(24):
            raise SystemExit("GROUP_INDEX_REQUIRED_0_23")
    elif a.group_index is not None:
        raise SystemExit("GROUP_INDEX_FORBIDDEN_IN_FULL_MODE")

    out=Path(a.out_dir)
    out.mkdir(parents=True,exist_ok=True)
    label="full" if a.mode=="full" else f"group{a.group_index:02d}"
    run_dir=out/f"{label}_{a.instrumentation}"
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit("BENCHMARK_OUTPUT_DIR_NOT_EMPTY")
    run_dir.mkdir(parents=True,exist_ok=True)
    receipt=run_dir/"worker_receipt.json"
    pstats_path=run_dir/"profile.pstats"

    worker_args=[
        str(WRAPPER),
        "--tick-raw-cache",a.tick_raw_cache,
        "--shard-json",a.shard_json,
        "--spec",a.spec,
        "--out-dir",str(run_dir),
        "--receipt",str(receipt),
        "--ticks",a.ticks,
        "--bar-root",a.bar_root,
        "--ind-root",a.ind_root,
        "--point",str(a.point),
        "--expected-config-root",EXPECTED_M12_CONFIG_ROOT,
    ]
    if a.mode=="group":
        worker_args += ["--only-group-index",str(a.group_index)]
    cmd=[sys.executable]+worker_args
    if a.instrumentation=="cprofile":
        cmd=[sys.executable,"-m","cProfile","-o",str(pstats_path)]+worker_args

    env=os.environ.copy()
    env.update({
        "PYTHONHASHSEED":"0",
        "OMP_NUM_THREADS":"1",
        "OPENBLAS_NUM_THREADS":"1",
        "MKL_NUM_THREADS":"1",
        "NUMEXPR_NUM_THREADS":"1",
    })

    before_usage=usage_snapshot()
    bytes_before=tree_bytes(run_dir)
    t0=time.perf_counter()
    proc=subprocess.run(cmd,env=env,capture_output=True,text=True)
    wall=time.perf_counter()-t0
    after_usage=usage_snapshot()
    bytes_after=tree_bytes(run_dir)

    result={
        "schema":"QROS_SEED0076_M12_PROFILE_RESULT_1.1",
        "mode":a.mode,
        "group_index":a.group_index,
        "instrumentation":a.instrumentation,
        "status":"FAIL",
        "environment":{
            "python":sys.version,
            "platform":platform.platform(),
            "machine":platform.machine(),
            "processor":platform.processor(),
            "cpu_count":os.cpu_count(),
            "thread_env":{
                k:env[k] for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS")
            }
        },
        "wrapper_git_blob_sha1":EXPECTED_WRAPPER_BLOB,
        "worker_git_blob_sha1":EXPECTED_WORKER_BLOB,
        "expected_config_root_sha256":EXPECTED_M12_CONFIG_ROOT,
        "wall_seconds":wall,
        "resource_usage":usage_delta(before_usage,after_usage),
        "output_bytes_delta":max(0,bytes_after-bytes_before),
        "returncode":proc.returncode,
        "stdout_tail":proc.stdout[-4000:],
        "stderr_tail":proc.stderr[-4000:],
        "economic_pnl_read":False,
        "holdout_open":False,
        "ga2_open":False,
    }

    failures=[]
    if proc.returncode!=0:
        failures.append(f"WORKER_EXIT_{proc.returncode}")
    if not receipt.is_file():
        failures.append("MISSING_WORKER_RECEIPT")
    else:
        wr=json.loads(receipt.read_text(encoding="utf-8"))
        result["worker_receipt"]=wr
        if wr.get("status")!="PASS":
            failures.append("WORKER_RECEIPT_NOT_PASS")
        if wr.get("economic_pnl_read") or wr.get("holdout_open"):
            failures.append("SCIENTIFIC_FIREWALL_VIOLATION")
        if wr.get("ordered_config_id_stream_root_sha256")!=EXPECTED_M12_CONFIG_ROOT:
            failures.append("CONFIG_ROOT_MISMATCH")
        if a.mode=="group":
            if wr.get("processed_signal_configs")!=33528:
                failures.append("GROUP_CONFIG_COUNT_MISMATCH")
        else:
            for k,v in GOLDEN_FULL.items():
                if wr.get(k)!=v:
                    failures.append(f"GOLDEN_MISMATCH:{k}")

    if a.instrumentation=="cprofile":
        if pstats_path.is_file():
            result["profile_top_cumulative"]=profile_rows(pstats_path,80)
            result["profile_sha256"]=sha256_file(pstats_path)
            result["profile_bytes"]=pstats_path.stat().st_size
        else:
            failures.append("MISSING_PROFILE_PSTATS")
    elif pstats_path.exists():
        failures.append("UNEXPECTED_PROFILE_PSTATS")

    result["failures"]=failures
    result["status"]="PASS" if not failures else "FAIL"
    result["benchmark_contract"]="M12 golden; timing and profiling separated; no semantic mutation"
    out_json=Path(a.benchmark_json)
    out_json.parent.mkdir(parents=True,exist_ok=True)
    out_json.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":result["status"],
        "mode":a.mode,
        "group_index":a.group_index,
        "instrumentation":a.instrumentation,
        "wall_seconds":round(wall,6),
        "failures":failures,
    },sort_keys=True))
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
