#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qros_seed0076_build_bar_cache_v220 import build_m1, validate, save_bar, content_root, sha256_file

EXPECTED_BARS = 681772
EXPECTED_CONTENT_SHA256 = "55630b61810c087c8230f9395214270b23773fec19d7af08d0547fb2ffe17bf4"
EXPECTED_FILE_BYTES = 27271136
EXPECTED_FILE_SHA256 = "35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--receipt", required=True)
    a = ap.parse_args()

    ticks = Path(a.ticks)
    out = Path(a.out_dir)
    receipt = Path(a.receipt)
    out.mkdir(parents=True, exist_ok=True)

    m1 = build_m1(ticks)
    failures = validate(m1)
    if failures:
        raise RuntimeError("M1_VALIDATE:" + ",".join(failures))

    p = out / "XAUUSD_M1_BID_BARS.npy"
    save_bar(p, m1)
    root = content_root(m1)
    fsha = sha256_file(p)
    rec = {
        "schema": "QROS_GROUP11_SELFHOSTED_M1_GATE_1.0",
        "status": "PASS",
        "bars": int(len(m1)),
        "content_sha256": root,
        "file_bytes": p.stat().st_size,
        "file_sha256": fsha,
        "economic_pnl_read": False,
        "holdout_open": False,
    }
    if rec["bars"] != EXPECTED_BARS:
        raise RuntimeError(f"M1_BARS:{rec['bars']}")
    if root != EXPECTED_CONTENT_SHA256:
        raise RuntimeError("M1_CONTENT_HASH")
    if rec["file_bytes"] != EXPECTED_FILE_BYTES:
        raise RuntimeError(f"M1_FILE_BYTES:{rec['file_bytes']}")
    if fsha != EXPECTED_FILE_SHA256:
        raise RuntimeError("M1_FILE_SHA256")

    receipt.write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
