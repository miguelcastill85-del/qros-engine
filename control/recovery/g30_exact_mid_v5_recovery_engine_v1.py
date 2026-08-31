#!/usr/bin/env python3
"""Durable G30 DEV recovery engine for exact BID/MID signal identity + frozen V5 execution.

This is a NEW implementation identity created under
control/G30_V5_LEGACY_RUNNER_SOURCE_MIGRATION_PREREG_v1.json.
It does not claim either missing historical runner SHA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit

DT = np.dtype([("ts", "<i8"), ("bid", "<i4"), ("ask", "<i4"), ("flags", "u1")])
CANONICAL_NQX_DEV_SHA256 = "451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf"
THRESHOLDS = [1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4]
NS = [1, 2, 3, 4, 5, 8]
TIMINGS = ["CURRENT_BAR_INCLUDED", "LAGGED_ONE_BAR_PRE_SHOCK"]
FAMILIES = [
    "CLOSE_EXCEEDS_PRIOR_N_CLOSES",
    "STRICT_MONOTONIC_N_CLOSE_SEQUENCE",
    "CLOSE_BREAKS_PRIOR_N_BAR_EXTREME",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_exec_minutes(parts: Path) -> np.ndarray:
    files = sorted(parts.glob("part_*.npz"))
    if not files:
        raise SystemExit("no executable-minute NPZ parts")
    rows = []
    for path in files:
        with np.load(path) as z:
            rows.extend(zip(z["mb"], z["bh"], z["bl"], z["ah"], z["al"], z["first"], z["last"]))
    rows.sort(key=lambda r: (int(r[0]), int(r[5])))
    merged = []
    for raw in rows:
        r = tuple(map(int, raw))
        if merged and merged[-1][0] == r[0]:
            q = merged[-1]
            merged[-1] = (
                q[0], max(q[1], r[1]), min(q[2], r[2]), max(q[3], r[3]), min(q[4], r[4]),
                min(q[5], r[5]), max(q[6], r[6]),
            )
        else:
            merged.append(r)
    return np.asarray(merged, dtype=np.int64)


def make_feature_bars(mm: np.memmap, step_ms: int, feature_side: str):
    valid = mm["ask"] >= mm["bid"]
    ids = np.flatnonzero(valid)
    ts = mm["ts"][ids]
    if feature_side == "BID":
        values_x2 = mm["bid"][ids].astype(np.int64) * 2
    elif feature_side == "MID":
        # Exact contemporaneous midpoint represented without rounding.
        values_x2 = mm["bid"][ids].astype(np.int64) + mm["ask"][ids].astype(np.int64)
    else:
        raise ValueError(feature_side)
    buckets = (ts // step_ms) * step_ms
    starts = np.r_[0, np.flatnonzero(buckets[1:] != buckets[:-1]) + 1]
    ends = np.r_[starts[1:], len(buckets)]
    return (
        buckets[starts].astype(np.int64),
        values_x2[starts],
        np.maximum.reduceat(values_x2, starts),
        np.minimum.reduceat(values_x2, starts),
        values_x2[ends - 1],
    )


def atr14(high_x2, low_x2, close_x2):
    high = high_x2.astype(np.float64)
    low = low_x2.astype(np.float64)
    close = close_x2.astype(np.float64)
    previous_close = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - previous_close), np.abs(low - previous_close)))
    cs = np.cumsum(np.nan_to_num(tr))
    out = np.full(len(close), np.nan)
    out[13:] = (cs[13:] - np.r_[0.0, cs[:-14]]) / 14.0
    return out


def signal_masks(bucket, opn, high, low, close):
    atr_x2 = atr14(high, low, close)
    weekday = ((bucket // 86_400_000 + 3) % 7) < 5
    bases = {}
    for n in NS:
        cw = np.lib.stride_tricks.sliding_window_view(close, n + 1)
        hw = np.lib.stride_tricks.sliding_window_view(high, n + 1)
        lw = np.lib.stride_tricks.sliding_window_view(low, n + 1)

        buy = np.zeros(len(close), bool); sell = np.zeros(len(close), bool)
        buy[n:] = cw[:, -1] > cw[:, :-1].max(axis=1)
        sell[n:] = cw[:, -1] < cw[:, :-1].min(axis=1)
        bases[(FAMILIES[0], n)] = (buy, sell)

        buy = np.zeros(len(close), bool); sell = np.zeros(len(close), bool)
        diff = np.diff(cw, axis=1)
        buy[n:] = np.all(diff > 0, axis=1)
        sell[n:] = np.all(diff < 0, axis=1)
        bases[(FAMILIES[1], n)] = (buy, sell)

        buy = np.zeros(len(close), bool); sell = np.zeros(len(close), bool)
        buy[n:] = cw[:, -1] > hw[:, :-1].max(axis=1)
        sell[n:] = cw[:, -1] < lw[:, :-1].min(axis=1)
        bases[(FAMILIES[2], n)] = (buy, sell)

    result = []
    for ti, timing in enumerate(TIMINGS):
        denominator = atr_x2 if ti == 0 else np.r_[np.nan, atr_x2[:-1]]
        ratio = np.divide(high - low, denominator, out=np.full(len(close), np.nan), where=np.isfinite(denominator) & (denominator > 0))
        for threshold in THRESHOLDS:
            shock = (ratio >= threshold) & weekday
            for family in FAMILIES:
                for n in NS:
                    buy, sell = bases[(family, n)]
                    result.append((f"{timing}|{threshold:g}|{family}|{n}", buy & shock, sell & shock))
            result.append((f"{timing}|{threshold:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1", (close > opn) & shock, (close < opn) & shock))
    return atr_x2, result


@njit
def lower_bound(a, x):
    lo = 0; hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


@njit
def outcomes(ts, bid, ask, bucket, atr_x2, step_ms, mb, bh, bl, ah, al, first, last, side):
    n = len(bucket)
    entry_t = np.full(n, -1, np.int64)
    exit_t = np.full(n, -1, np.int64)
    rr = np.zeros(n, np.float64)
    for bi in range(n):
        if not np.isfinite(atr_x2[bi]) or atr_x2[bi] <= 0:
            continue
        close_t = bucket[bi] + step_ms
        deadline = min(close_t + 20 * step_ms, ((close_t // 86_400_000) + 1) * 86_400_000)
        mi = lower_bound(mb, close_t)
        if mi >= len(mb) or mb[mi] >= deadline:
            continue
        ei = first[mi]
        while ei <= last[mi] and (ts[ei] < close_t or ask[ei] <= bid[ei]):
            ei += 1
        if ei > last[mi] or ts[ei] >= deadline:
            continue
        entry = ask[ei] if side == 1 else bid[ei]
        # atr_x2 is twice the native packed-price ATR for BID and exact MID.
        distance = 3.0 * atr_x2[bi] / 2.0
        stop = entry - distance if side == 1 else entry + distance
        take = entry + 1.5 * distance if side == 1 else entry - 1.5 * distance
        entry_t[bi] = ts[ei]
        mend = lower_bound(mb, deadline)
        hit_minute = -1
        for mj in range(mi, mend):
            if side == 1:
                if bl[mj] <= stop or bh[mj] >= take:
                    hit_minute = mj; break
            else:
                if ah[mj] >= stop or al[mj] <= take:
                    hit_minute = mj; break
        hit = False
        if hit_minute >= 0:
            j0 = max(first[hit_minute], ei)
            j1 = last[hit_minute] + 1
            for j in range(j0, j1):
                if ts[j] >= deadline:
                    break
                if ask[j] <= bid[j]:
                    continue
                if side == 1:
                    if bid[j] <= stop:
                        rr[bi] = -1.0; exit_t[bi] = ts[j]; hit = True; break
                    if bid[j] >= take:
                        rr[bi] = 1.5; exit_t[bi] = ts[j]; hit = True; break
                else:
                    if ask[j] >= stop:
                        rr[bi] = -1.0; exit_t[bi] = ts[j]; hit = True; break
                    if ask[j] <= take:
                        rr[bi] = 1.5; exit_t[bi] = ts[j]; hit = True; break
        if not hit:
            if mend <= mi:
                entry_t[bi] = -1; continue
            j = last[mend - 1]
            while j >= first[mend - 1] and (ts[j] >= deadline or ask[j] <= bid[j]):
                j -= 1
            if j < ei:
                entry_t[bi] = -1; continue
            exit_t[bi] = ts[j]
            rr[bi] = (bid[j] - entry) / distance if side == 1 else (entry - ask[j]) / distance
    return entry_t, exit_t, rr


@njit
def select_one_position(mask, entry_t, exit_t):
    ids = np.flatnonzero(mask)
    out = np.empty(len(ids), np.int64)
    k = 0
    previous_exit = -1
    for q in ids:
        if entry_t[q] < 0 or entry_t[q] <= previous_exit:
            continue
        out[k] = q; k += 1; previous_exit = exit_t[q]
    return out[:k]


def unique_masks(rows):
    seen = set(); result = []
    for key, buy, sell in rows:
        encoded = np.zeros(len(buy), np.int8)
        encoded[buy] = 1; encoded[sell] = -1
        digest = hashlib.sha256(encoded.tobytes()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            result.append((key, buy, sell, digest))
    return result


def ledger_records(unique, buy_outcomes, sell_outcomes):
    records = []
    for key, buy, sell, signal_sha in unique:
        for side_name, mask, result in (("BUY", buy, buy_outcomes), ("SELL", sell, sell_outcomes)):
            et, xt, rr = result
            chosen = select_one_position(mask, et, xt)
            h = hashlib.sha256()
            for q in chosen:
                h.update(np.int64(et[q]).tobytes())
                h.update(np.int64(xt[q]).tobytes())
                h.update(np.float64(rr[q]).tobytes())
            records.append({
                "id": key,
                "signal_sha256": signal_sha,
                "side": side_name,
                "n": int(len(chosen)),
                "net_r": float(rr[chosen].sum()),
                "ledger_sha256": h.hexdigest(),
            })
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--exec-minutes-dir", type=Path, required=True)
    ap.add_argument("--tf-minutes", type=int, required=True)
    ap.add_argument("--feature-side", choices=["BID", "MID"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if sha256_file(args.src) != CANONICAL_NQX_DEV_SHA256:
        raise SystemExit("canonical NQX DEV SHA-256 mismatch")
    step_ms = args.tf_minutes * 60_000
    mm = np.memmap(args.src, dtype=DT, mode="r")
    minute = load_exec_minutes(args.exec_minutes_dir)
    bucket, opn, high, low, close = make_feature_bars(mm, step_ms, args.feature_side)
    atr_x2, masks = signal_masks(bucket, opn, high, low, close)
    unique = unique_masks(masks)
    mb, bh, bl, ah, al, first, last = [minute[:, i] for i in range(7)]
    buy = outcomes(mm["ts"], mm["bid"], mm["ask"], bucket, atr_x2, step_ms, mb, bh, bl, ah, al, first, last, 1)
    sell = outcomes(mm["ts"], mm["bid"], mm["ask"], bucket, atr_x2, step_ms, mb, bh, bl, ah, al, first, last, -1)
    records = ledger_records(unique, buy, sell)
    obj = {
        "schema": "QROS_G30_EXACT_MID_V5_RECOVERY_ENGINE_OUTPUT_v1",
        "scope": "DEV_2018_2019_ONLY_NO_HOLDOUT",
        "input_sha256": CANONICAL_NQX_DEV_SHA256,
        "tf_minutes": args.tf_minutes,
        "feature_side": args.feature_side,
        "bars": int(len(bucket)),
        "raw_identities": int(len(masks)),
        "unique_masks": int(len(unique)),
        "records": records,
        "holdout_opened": False,
    }
    args.out.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "bars": obj["bars"], "raw_identities": obj["raw_identities"], "unique_masks": obj["unique_masks"],
        "side_ledgers": len(records), "output_sha256": sha256_file(args.out)
    }, sort_keys=True))


if __name__ == "__main__":
    main()
