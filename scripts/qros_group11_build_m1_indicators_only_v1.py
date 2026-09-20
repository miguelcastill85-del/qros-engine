#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qros_seed0076_indicators_v220 import compute_all
from qros_seed0076_build_indicator_cache_v220 import canonical_root

EXPECTED_BARS = 681772
EXPECTED_CONTENT_ROOT_SHA256 = "2b7b9a1fe666993a9a303f34f466950b6411f274136ec5f1f34adafdd2ee394c"
EXPECTED_FILE_BYTES = 196359134
EXPECTED_FILE_SHA256 = "f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--receipt", required=True)
    a = ap.parse_args()

    bars = Path(a.bars)
    out = Path(a.out_dir)
    receipt = Path(a.receipt)
    out.mkdir(parents=True, exist_ok=True)

    b = np.load(bars, mmap_mode="r", allow_pickle=False)
    scale = 0.01
    h = b["high_bid"].astype(np.float64) * scale
    l = b["low_bid"].astype(np.float64) * scale
    c = b["close_bid"].astype(np.float64) * scale

    d = compute_all(h, l, c)
    completion = np.full(len(b), -1, dtype=np.int64)
    if len(b) > 1:
        completion[:-1] = b["first_source_index"][1:]
    d["completion_source_index"] = completion

    p = out / "XAUUSD_M1_INDICATORS.npz"
    np.savez(p, **d)
    root = canonical_root(d)
    fsha = sha256_file(p)
    rec = {
        "schema": "QROS_GROUP11_SELFHOSTED_M1_INDICATOR_GATE_1.0",
        "status": "PASS",
        "bars": int(len(b)),
        "content_root_sha256": root,
        "file_bytes": p.stat().st_size,
        "file_sha256": fsha,
        "economic_pnl_read": False,
        "holdout_open": False,
    }
    if rec["bars"] != EXPECTED_BARS:
        raise RuntimeError(f"IND_BARS:{rec['bars']}")
    if root != EXPECTED_CONTENT_ROOT_SHA256:
        raise RuntimeError("IND_CONTENT_ROOT")
    if rec["file_bytes"] != EXPECTED_FILE_BYTES:
        raise RuntimeError(f"IND_FILE_BYTES:{rec['file_bytes']}")
    if fsha != EXPECTED_FILE_SHA256:
        raise RuntimeError("IND_FILE_SHA256")

    receipt.write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
