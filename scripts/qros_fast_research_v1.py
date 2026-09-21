#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "qros_seed0076_ga1_cached_wrapper_v236.py"
WORKER = HERE / "qros_seed0076_ga1_shard_worker_v223.py"

def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode())
    h.update(data)
    return h.hexdigest()

def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def parse_args():
    p = argparse.ArgumentParser(description="QROS FAST Research v1 — one full scientific domain per invocation.")
    p.add_argument("--run-spec", required=True)
    p.add_argument("--shard-json", required=True)
    p.add_argument("--machine-spec", required=True)
    p.add_argument("--ticks", required=True)
    p.add_argument("--bar-root", required=True)
    p.add_argument("--ind-root", required=True)
    p.add_argument("--tick-raw-cache", required=True)
    p.add_argument("--point", type=float, required=True)
    p.add_argument("--work-root", required=True)
    return p.parse_args()

def require_file(path: str, label: str) -> Path:
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"MISSING_{label}:{p}")
    return p

def require_dir(path: str, label: str) -> Path:
    p = Path(path)
    if not p.is_dir():
        raise SystemExit(f"MISSING_{label}:{p}")
    return p

def main() -> int:
    a = parse_args()
    spec = json.loads(Path(a.run_spec).read_text(encoding="utf-8"))
    work = Path(a.work_root)
    work.mkdir(parents=True, exist_ok=True)
    resume = work / "resume.json"
    summary = work / "summary.json"
    out = work / "result"
    out.mkdir(parents=True, exist_ok=True)
    receipt = out / "worker_receipt.json"

    expected_wrapper = spec["code_pins"]["wrapper_git_blob_sha1"]
    expected_worker = spec["code_pins"]["worker_git_blob_sha1"]
    if git_blob_sha1(WRAPPER) != expected_wrapper:
        raise SystemExit("WRAPPER_BLOB_MISMATCH")
    if git_blob_sha1(WORKER) != expected_worker:
        raise SystemExit("WORKER_BLOB_MISMATCH")

    shard = require_file(a.shard_json, "SHARD_JSON")
    machine = require_file(a.machine_spec, "MACHINE_SPEC")
    ticks = require_file(a.ticks, "TICKS")
    raw = require_file(a.tick_raw_cache, "TICK_RAW_CACHE")
    bars = require_dir(a.bar_root, "BAR_ROOT")
    inds = require_dir(a.ind_root, "IND_ROOT")

    state = {
        "schema": "QROS_FAST_RESEARCH_RESUME_1.0",
        "run_id": spec["run_id"],
        "status": "RUNNING",
        "domain": spec["domain"],
        "drive_run_folder_id": spec["storage"]["drive_run_folder_id"],
        "started_unix": time.time(),
        "economic_pnl_read": False,
        "ga2_open": False,
        "holdout_open": False,
    }
    atomic_json(resume, state)

    cmd = [
        sys.executable, str(WRAPPER),
        "--tick-raw-cache", str(raw),
        "--shard-json", str(shard),
        "--spec", str(machine),
        "--out-dir", str(out),
        "--receipt", str(receipt),
        "--ticks", str(ticks),
        "--bar-root", str(bars),
        "--ind-root", str(inds),
        "--point", str(a.point),
        "--expected-config-root", spec["golden"]["ordered_config_id_stream_root_sha256"],
    ]

    env = os.environ.copy()
    env.update({
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    })

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - t0

    if not receipt.is_file():
        state.update({
            "status": "FAIL",
            "wall_seconds": wall,
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-4000:],
            "stdout_tail": proc.stdout[-4000:],
            "failure": "MISSING_WORKER_RECEIPT",
        })
        atomic_json(resume, state)
        return 2

    r = json.loads(receipt.read_text(encoding="utf-8"))
    failures = []
    if proc.returncode != 0:
        failures.append(f"WORKER_EXIT_{proc.returncode}")
    if r.get("status") != "PASS":
        failures.append("WORKER_RECEIPT_NOT_PASS")
    if r.get("economic_pnl_read") or r.get("holdout_open"):
        failures.append("SCIENTIFIC_FIREWALL_VIOLATION")

    for key, expected in spec["golden"]["receipt_exact"].items():
        if r.get(key) != expected:
            failures.append(f"GOLDEN_MISMATCH:{key}")

    final = {
        "schema": "QROS_FAST_RESEARCH_SUMMARY_1.0",
        "run_id": spec["run_id"],
        "mode": "RESEARCH_FAST",
        "domain": spec["domain"],
        "status": "PASS" if not failures else "FAIL",
        "wall_seconds": wall,
        "worker_returncode": proc.returncode,
        "worker_receipt": str(receipt),
        "drive_run_folder_id": spec["storage"]["drive_run_folder_id"],
        "golden_parity_failures": failures,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "economic_pnl_read": False,
        "ga2_open": False,
        "holdout_open": False,
        "design": {
            "scientific_domains": 1,
            "execution_groups_exposed": 0,
            "group_merge_required": False,
            "cws_required": False,
            "github_required_during_compute": False,
        },
    }
    atomic_json(summary, final)

    state.update({
        "status": final["status"],
        "finished_unix": time.time(),
        "wall_seconds": wall,
        "summary": str(summary),
        "failures": failures,
    })
    atomic_json(resume, state)

    print(json.dumps({
        "status": final["status"],
        "run_id": spec["run_id"],
        "wall_seconds": round(wall, 6),
        "failures": failures,
    }, sort_keys=True))
    return 0 if not failures else 2

if __name__ == "__main__":
    raise SystemExit(main())
