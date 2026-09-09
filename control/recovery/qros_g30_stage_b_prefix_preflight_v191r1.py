#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sys, tempfile
from pathlib import Path
import numpy as np

DT = np.dtype([("ts","<i8"),("bid","<i4"),("ask","<i4"),("flags","u1")])
ROW_BYTES = DT.itemsize
STAGE_START = 1577836800000
STAGE_END = 1640995200000

AUTH = {
    "NQX": {
        "prefix_bytes": 2490863052,
        "prefix_records": 146521356,
        "prefix_sha256": "d2530ae084311e0b454f30a5d7a2bc0d0f4ca932bb81d9dd2252ba7295491a05",
        "dev_bytes": 1018984420,
        "dev_records": 59940260,
        "dev_sha256": "451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf",
        "dev_cache_sha256": "8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca",
        "prefix_cache_sha256": "2bad94f5051c41f00a5e6fd9f39efa4278488f12b0b2f6d95737386cddecf598",
        "stage_records": 86581096,
        "stage_bytes": 1471878632,
        "stage_sha256": "f6cef828431a2f8153e9fc9a07aa78978069fb11eef32778b43ee5654ba11fd5",
    },
    "XAUUSD": {
        "prefix_bytes": 5502262228,
        "prefix_records": 323662484,
        "prefix_sha256": "77da8423b07d7d33168d8b713ef691627f0698760461c7349fa5ccc5e49ceaeb",
        "dev_bytes": 2573500596,
        "dev_records": 151382388,
        "dev_sha256": "3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53",
        "dev_cache_sha256": "f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62",
        "prefix_cache_sha256": "35abe473cfb9b02c51f525ccd3ef870bff51106005f94236e8197a9f4a2d8bfd",
        "stage_records": 172280096,
        "stage_bytes": 2928761632,
        "stage_sha256": None,
    },
}

def sha_file(path: Path, offset: int = 0, length: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = length
    with path.open("rb") as f:
        if offset:
            f.seek(offset)
        while True:
            want = 8 << 20 if remaining is None else min(8 << 20, remaining)
            if want <= 0:
                break
            b = f.read(want)
            if not b:
                break
            h.update(b)
            if remaining is not None:
                remaining -= len(b)
    if remaining not in (None, 0):
        raise SystemExit("SLICE_LENGTH_MISMATCH")
    return h.hexdigest()

def copy_prefix(src: Path, dst: Path, nbytes: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with src.open("rb") as fi, tmp.open("wb") as fo:
        remaining = nbytes
        while remaining:
            b = fi.read(min(8 << 20, remaining))
            if not b:
                raise SystemExit("UNEXPECTED_EOF_DURING_DEV_EXTRACTION")
            fo.write(b)
            remaining -= len(b)
        fo.flush()
        os.fsync(fo.fileno())
    os.replace(tmp, dst)

def build_cache(src: Path, out: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import qros_g30_cache_v58 as cache_builder
    tmp = out.with_suffix(out.suffix + ".tmp.npz")
    if tmp.exists():
        tmp.unlink()
    cache_builder.main(src, tmp)
    os.replace(tmp, out)

def verify_prefix(asset: str, prefix: Path) -> dict:
    a = AUTH[asset]
    st = prefix.stat()
    if st.st_size != a["prefix_bytes"]:
        raise SystemExit(f"PREFIX_SIZE_MISMATCH expected={a['prefix_bytes']} got={st.st_size}")
    if st.st_size % ROW_BYTES:
        raise SystemExit("PREFIX_ROW_ALIGNMENT_FAIL")
    if st.st_size // ROW_BYTES != a["prefix_records"]:
        raise SystemExit("PREFIX_RECORD_COUNT_MISMATCH")
    psha = sha_file(prefix)
    if psha != a["prefix_sha256"]:
        raise SystemExit("PREFIX_SHA256_MISMATCH")
    mm = np.memmap(prefix, dtype=DT, mode="r")
    if len(mm) != a["prefix_records"]:
        raise SystemExit("PREFIX_MEMMAP_COUNT_MISMATCH")
    if len(mm) <= a["dev_records"]:
        raise SystemExit("PREFIX_HAS_NO_STAGE_B_RECORDS")
    if int(mm[a["dev_records"] - 1]["ts"]) >= STAGE_START:
        raise SystemExit("DEV_BOUNDARY_CONTAINS_STAGE_B")
    if int(mm[a["dev_records"]]["ts"]) < STAGE_START:
        raise SystemExit("STAGE_B_BOUNDARY_START_FAIL")
    if int(mm[-1]["ts"]) >= STAGE_END:
        raise SystemExit("PREFIX_CONTAINS_2022_PLUS")
    # Memory-bounded monotonicity audit; never allocate a full-carrier boolean array.
    chunk = 10_000_000
    prev = int(mm[0]["ts"])
    for lo in range(1, len(mm), chunk):
        hi = min(len(mm), lo + chunk)
        ts = mm["ts"][lo:hi]
        if len(ts):
            if int(ts[0]) < prev:
                raise SystemExit("PREFIX_OUT_OF_ORDER")
            if len(ts) > 1 and np.any(ts[1:] < ts[:-1]):
                raise SystemExit("PREFIX_OUT_OF_ORDER")
            prev = int(ts[-1])
    return {
        "records": int(len(mm)),
        "bytes": int(st.st_size),
        "sha256": psha,
        "first_timestamp_ms": int(mm[0]["ts"]),
        "dev_last_timestamp_ms": int(mm[a["dev_records"] - 1]["ts"]),
        "stage_first_timestamp_ms": int(mm[a["dev_records"]]["ts"]),
        "last_timestamp_ms": int(mm[-1]["ts"]),
    }

def execute(asset: str, prefix: Path, work: Path, receipt: Path) -> None:
    a = AUTH[asset]
    work.mkdir(parents=True, exist_ok=True)
    prefix_meta = verify_prefix(asset, prefix)

    stage_offset = a["dev_bytes"]
    stage_sha = sha_file(prefix, stage_offset, a["stage_bytes"])
    if a["stage_sha256"] is not None and stage_sha != a["stage_sha256"]:
        raise SystemExit("STAGE_B_SLICE_SHA256_MISMATCH")

    dev = work / f"{asset}_DEV_2018_2019.bin"
    copy_prefix(prefix, dev, a["dev_bytes"])
    if dev.stat().st_size != a["dev_bytes"] or sha_file(dev) != a["dev_sha256"]:
        raise SystemExit("DEV_REMATERIALIZATION_MISMATCH")

    dev_cache = work / f"{asset}_DEV_2018_2019_M1_CACHE.npz"
    prefix_cache = work / f"{asset}_PREFIX_2018_2021_M1_CACHE.npz"
    build_cache(dev, dev_cache)
    if sha_file(dev_cache) != a["dev_cache_sha256"]:
        raise SystemExit("DEV_CACHE_SHA256_MISMATCH")
    build_cache(prefix, prefix_cache)
    if sha_file(prefix_cache) != a["prefix_cache_sha256"]:
        raise SystemExit("PREFIX_CACHE_SHA256_MISMATCH")

    obj = {
        "schema": "QROS_G30_STAGE_B_PREFIX_PREFLIGHT_V191R1_RECEIPT_v1",
        "status": "PASS_EXACT_NO_STRATEGY_PNL_READ",
        "campaign": "QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1",
        "scope": "F03_F12_STAGE_B_INPUT_PREFLIGHT_2018_2021_PREFIX_ONLY",
        "asset": asset,
        "prefix": prefix_meta,
        "dev": {
            "records": a["dev_records"], "bytes": a["dev_bytes"],
            "sha256": a["dev_sha256"], "cache_sha256": a["dev_cache_sha256"],
        },
        "stage_b_slice": {
            "records": a["stage_records"], "bytes": a["stage_bytes"],
            "sha256_observed": stage_sha, "sha256_expected": a["stage_sha256"],
        },
        "prefix_cache_sha256": a["prefix_cache_sha256"],
        "guards": {
            "strategy_pnl_read": False,
            "2022_plus_present": False,
            "retuning": False,
            "mt5": False,
            "live": False,
        },
        "next_action": "REPLAY_F03_GATE_A_24_SHARDS_EXACT_THEN_STAGE_B_ALL_1928_PASSERS",
    }
    tmp = receipt.with_suffix(receipt.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, receipt)
    print(json.dumps({"status": obj["status"], "asset": asset, "receipt": str(receipt),
                      "receipt_sha256": sha_file(receipt)}, sort_keys=True))

def selftest() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "x.bin"
        payload = bytes(range(64)) * 1024
        src.write_bytes(payload)
        got_full = sha_file(src)
        exp_full = hashlib.sha256(payload).hexdigest()
        if got_full != exp_full:
            raise SystemExit("SELFTEST_FULL_HASH_FAIL")
        off, ln = 101, 777
        got_slice = sha_file(src, off, ln)
        exp_slice = hashlib.sha256(payload[off:off+ln]).hexdigest()
        if got_slice != exp_slice:
            raise SystemExit("SELFTEST_SLICE_HASH_FAIL")
        dst = root / "prefix.bin"
        copy_prefix(src, dst, 4097)
        if dst.read_bytes() != payload[:4097]:
            raise SystemExit("SELFTEST_ATOMIC_PREFIX_COPY_FAIL")
    print(json.dumps({"schema":"QROS_G30_STAGE_B_PREFIX_PREFLIGHT_V191R1_SELFTEST_v1",
                      "tests":3,"passed":3,"status":"PASS"}))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--asset", choices=sorted(AUTH))
    ap.add_argument("--prefix", type=Path)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--receipt", type=Path)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not all((a.asset, a.prefix, a.work, a.receipt)):
        raise SystemExit("ASSET_PREFIX_WORK_RECEIPT_REQUIRED")
    execute(a.asset, a.prefix, a.work, a.receipt)

if __name__ == "__main__":
    main()
