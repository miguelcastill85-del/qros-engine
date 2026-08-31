#!/usr/bin/env python3
"""Exact DEV-only 626-ledger parity: direct oracle vs frozen G30 M30 finalizer."""
import argparse
import ast
import hashlib
import json
import sys
import time
import types
from pathlib import Path

import numpy as np

DT = np.dtype([("ts", "<i8"), ("bid", "<i4"), ("ask", "<i4"), ("flags", "u1")])
STEP = 1_800_000
THR = [1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4]
NS = [1, 2, 3, 4, 5, 8]
TIM = ["CURRENT_BAR_INCLUDED", "LAGGED_ONE_BAR_PRE_SHOCK"]
FAMS = ["CLOSE_EXCEEDS_PRIOR_N_CLOSES", "STRICT_MONOTONIC_N_CLOSE_SEQUENCE", "CLOSE_BREAKS_PRIOR_N_BAR_EXTREME"]
CANONICAL = "451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf"
FROZEN = "a9c755f225878aa4f50748a80b530a7f23c7f0900baeac6c974d3d594939ece3"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_minutes(parts):
    rows = []
    for k in range(16):
        with np.load(parts / f"part_{k:02d}.npz") as z:
            rows.extend(zip(z["mb"], z["bh"], z["bl"], z["ah"], z["al"], z["first"], z["last"]))
    rows.sort(key=lambda r: (int(r[0]), int(r[5])))
    merged = []
    for raw in rows:
        r = tuple(map(int, raw))
        if merged and merged[-1][0] == r[0]:
            q = merged[-1]
            merged[-1] = (q[0], max(q[1], r[1]), min(q[2], r[2]), max(q[3], r[3]), min(q[4], r[4]), min(q[5], r[5]), max(q[6], r[6]))
        else:
            merged.append(r)
    return np.asarray(merged, dtype=np.int64)


def make_bars(mm):
    ids = np.flatnonzero(mm["ask"] >= mm["bid"])
    ts = mm["ts"][ids]
    values = mm["bid"][ids].astype(np.int64)
    buckets = (ts // STEP) * STEP
    starts = np.r_[0, np.flatnonzero(buckets[1:] != buckets[:-1]) + 1]
    ends = np.r_[starts[1:], len(buckets)]
    return (buckets[starts].astype(np.int64), values[starts], np.maximum.reduceat(values, starts),
            np.minimum.reduceat(values, starts), values[ends - 1])


def atr14(high, low, close):
    high = high.astype(float); low = low.astype(float); close = close.astype(float)
    prior = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prior), np.abs(low - prior)))
    cs = np.cumsum(np.nan_to_num(tr)); out = np.full(len(close), np.nan)
    out[13:] = (cs[13:] - np.r_[0.0, cs[:-14]]) / 14.0
    return out


def signal_masks_window(bucket, opn, high, low, close):
    """Oracle signal engine: NumPy windows."""
    atr = atr14(high, low, close); weekday = ((bucket // 86_400_000 + 3) % 7) < 5
    bases = {}
    for n in NS:
        cw = np.lib.stride_tricks.sliding_window_view(close, n + 1)
        hw = np.lib.stride_tricks.sliding_window_view(high, n + 1)
        lw = np.lib.stride_tricks.sliding_window_view(low, n + 1)
        a = np.zeros(len(close), bool); b = np.zeros(len(close), bool)
        a[n:] = cw[:, -1] > cw[:, :-1].max(axis=1); b[n:] = cw[:, -1] < cw[:, :-1].min(axis=1)
        bases[(FAMS[0], n)] = (a, b)
        a = np.zeros(len(close), bool); b = np.zeros(len(close), bool)
        d = np.diff(cw, axis=1); a[n:] = np.all(d > 0, axis=1); b[n:] = np.all(d < 0, axis=1)
        bases[(FAMS[1], n)] = (a, b)
        a = np.zeros(len(close), bool); b = np.zeros(len(close), bool)
        a[n:] = cw[:, -1] > hw[:, :-1].max(axis=1); b[n:] = cw[:, -1] < lw[:, :-1].min(axis=1)
        bases[(FAMS[2], n)] = (a, b)
    result = []
    for ti, timing in enumerate(TIM):
        den = atr if ti == 0 else np.r_[np.nan, atr[:-1]]
        ratio = np.divide(high - low, den, out=np.full(len(close), np.nan), where=np.isfinite(den) & (den > 0))
        for threshold in THR:
            shock = (ratio >= threshold) & weekday
            for family in FAMS:
                for n in NS:
                    buy, sell = bases[(family, n)]
                    result.append((f"{timing}|{threshold:g}|{family}|{n}", buy & shock, sell & shock))
            result.append((f"{timing}|{threshold:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1", (close > opn) & shock, (close < opn) & shock))
    return atr, result


def signal_masks_loops(bucket, opn, high, low, close):
    """Independent signal engine: explicit per-bar base predicates."""
    atr = atr14(high, low, close); weekday = ((bucket // 86_400_000 + 3) % 7) < 5
    bases = {}
    for family in FAMS:
        for n in NS:
            buy = np.zeros(len(close), bool); sell = np.zeros(len(close), bool)
            for i in range(n, len(close)):
                if family == FAMS[0]:
                    z = close[i-n:i]; buy[i] = close[i] > z.max(); sell[i] = close[i] < z.min()
                elif family == FAMS[1]:
                    z = close[i-n:i+1]; buy[i] = bool(np.all(z[1:] > z[:-1])); sell[i] = bool(np.all(z[1:] < z[:-1]))
                else:
                    buy[i] = close[i] > high[i-n:i].max(); sell[i] = close[i] < low[i-n:i].min()
            bases[(family, n)] = (buy, sell)
    result = []
    for ti, timing in enumerate(TIM):
        den = atr if ti == 0 else np.r_[np.nan, atr[:-1]]
        ratio = np.divide(high - low, den, out=np.full(len(close), np.nan), where=np.isfinite(den) & (den > 0))
        for threshold in THR:
            shock = (ratio >= threshold) & weekday
            for family in FAMS:
                for n in NS:
                    buy, sell = bases[(family, n)]
                    result.append((f"{timing}|{threshold:g}|{family}|{n}", buy & shock, sell & shock))
            result.append((f"{timing}|{threshold:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1", (close > opn) & shock, (close < opn) & shock))
    return atr, result


def direct_outcomes(mm, bucket, atr, minute, side):
    """Oracle execution engine, written independently from the frozen runner."""
    ts, bid, ask = mm["ts"], mm["bid"], mm["ask"]
    mb, bh, bl, ah, al, first, last = [minute[:, i] for i in range(7)]
    entry_t = np.full(len(bucket), -1, np.int64); exit_t = np.full(len(bucket), -1, np.int64)
    rr = np.zeros(len(bucket), np.float64)
    for bi, bar in enumerate(bucket):
        if not np.isfinite(atr[bi]) or atr[bi] <= 0: continue
        close = int(bar + STEP); deadline = min(close + 20 * STEP, ((close // 86_400_000) + 1) * 86_400_000)
        mi = int(np.searchsorted(mb, close)); mend = int(np.searchsorted(mb, deadline))
        if mi >= len(mb) or mb[mi] >= deadline: continue
        ei = int(first[mi])
        while ei <= last[mi] and (ts[ei] < close or ask[ei] <= bid[ei]): ei += 1
        if ei > last[mi] or ts[ei] >= deadline: continue
        entry = int(ask[ei] if side == 1 else bid[ei]); distance = 3.0 * atr[bi]
        stop = entry - distance if side == 1 else entry + distance
        take = entry + 1.5 * distance if side == 1 else entry - 1.5 * distance
        entry_t[bi] = ts[ei]; hit_minute = -1
        for mj in range(mi, mend):
            if (side == 1 and (bl[mj] <= stop or bh[mj] >= take)) or (side == -1 and (ah[mj] >= stop or al[mj] <= take)):
                hit_minute = mj; break
        hit = False
        if hit_minute >= 0:
            for j in range(max(int(first[hit_minute]), ei), int(last[hit_minute]) + 1):
                if ts[j] >= deadline: break
                if ask[j] <= bid[j]: continue
                if side == 1 and bid[j] <= stop: rr[bi] = -1.0; exit_t[bi] = ts[j]; hit = True; break
                if side == 1 and bid[j] >= take: rr[bi] = 1.5; exit_t[bi] = ts[j]; hit = True; break
                if side == -1 and ask[j] >= stop: rr[bi] = -1.0; exit_t[bi] = ts[j]; hit = True; break
                if side == -1 and ask[j] <= take: rr[bi] = 1.5; exit_t[bi] = ts[j]; hit = True; break
        if not hit:
            if mend <= mi: entry_t[bi] = -1; continue
            j = int(last[mend - 1])
            while j >= first[mend - 1] and (ts[j] >= deadline or ask[j] <= bid[j]): j -= 1
            if j < ei: entry_t[bi] = -1; continue
            exit_t[bi] = ts[j]
            rr[bi] = (bid[j] - entry) / distance if side == 1 else (entry - ask[j]) / distance
    return entry_t, exit_t, rr


def direct_select(mask, entry_t, exit_t):
    chosen = []; previous_exit = -1
    for q in np.flatnonzero(mask):
        if entry_t[q] < 0 or entry_t[q] <= previous_exit: continue
        chosen.append(int(q)); previous_exit = int(exit_t[q])
    return np.asarray(chosen, dtype=np.int64)


def unique_masks(rows):
    seen = set(); out = []
    for key, buy, sell in rows:
        encoded = np.zeros(len(buy), np.int8); encoded[buy] = 1; encoded[sell] = -1
        digest = hashlib.sha256(encoded.tobytes()).hexdigest()
        if digest not in seen:
            seen.add(digest); out.append((key, buy, sell, digest))
    return out


def ledger_rows(unique, outcomes_buy, outcomes_sell, selector):
    records = []
    for key, buy, sell, signal_hash in unique:
        for side, mask, outcome in (("BUY", buy, outcomes_buy), ("SELL", sell, outcomes_sell)):
            et, xt, rr = outcome; chosen = selector(mask, et, xt); h = hashlib.sha256()
            for q in chosen:
                h.update(np.int64(et[q]).tobytes()); h.update(np.int64(xt[q]).tobytes()); h.update(np.float64(rr[q]).tobytes())
            records.append({"id": key, "signal_sha256": signal_hash, "side": side, "n": int(len(chosen)),
                            "net_r": float(rr[chosen].sum()), "ledger_sha256": h.hexdigest()})
    return records


def load_frozen(path):
    if sha(path) != FROZEN: raise SystemExit("frozen runner SHA-256 mismatch")
    fake = types.ModuleType("numba"); fake.njit = lambda fn: fn; sys.modules.setdefault("numba", fake)
    tree = ast.parse(Path(path).read_text(), filename=str(path))
    if not isinstance(tree.body[-1], ast.Expr) or not isinstance(tree.body[-1].value, ast.Call) or getattr(tree.body[-1].value.func, "id", None) != "main":
        raise SystemExit("unexpected frozen runner terminator")
    tree.body.pop(); ns = {"__file__": str(path), "__name__": "frozen_g30_m30"}; exec(compile(tree, str(path), "exec"), ns)
    return ns


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", type=Path, required=True); ap.add_argument("--parts", type=Path, required=True)
    ap.add_argument("--frozen", type=Path, required=True); ap.add_argument("--out", type=Path, required=True); args = ap.parse_args()
    started = time.time()
    if sha(args.src) != CANONICAL: raise SystemExit("canonical NQX DEV SHA-256 mismatch")
    minute = load_minutes(args.parts); mm = np.memmap(args.src, dtype=DT, mode="r")
    bucket, opn, high, low, close = make_bars(mm)
    atr_a, sig_a = signal_masks_window(bucket, opn, high, low, close)
    atr_b, sig_b = signal_masks_loops(bucket, opn, high, low, close)
    unique_a, unique_b = unique_masks(sig_a), unique_masks(sig_b)
    signal_exact = len(unique_a) == len(unique_b) and all(a[0] == b[0] and a[3] == b[3] for a, b in zip(unique_a, unique_b))
    oracle_buy = direct_outcomes(mm, bucket, atr_a, minute, 1); oracle_sell = direct_outcomes(mm, bucket, atr_a, minute, -1)
    oracle = ledger_rows(unique_a, oracle_buy, oracle_sell, direct_select)
    frozen = load_frozen(args.frozen)
    frozen_buy = frozen["outcomes"](mm["ts"], mm["bid"], mm["ask"], bucket, atr_b, *[minute[:, i] for i in range(7)], 1)
    frozen_sell = frozen["outcomes"](mm["ts"], mm["bid"], mm["ask"], bucket, atr_b, *[minute[:, i] for i in range(7)], -1)
    candidate = ledger_rows(unique_b, frozen_buy, frozen_sell, frozen["sel"])
    left = {(r["signal_sha256"], r["side"]): r for r in oracle}; right = {(r["signal_sha256"], r["side"]): r for r in candidate}
    mismatches = [k for k in sorted(set(left) | set(right)) if k not in left or k not in right or left[k]["ledger_sha256"] != right[k]["ledger_sha256"]]
    obj = {"schema": "QROS_G30_NQX_M30_626_EXACT_PARITY_V1", "scope": "DEV_2018_2019_ONLY_NO_HOLDOUT",
           "input_sha256": CANONICAL, "frozen_runner_sha256": FROZEN, "minute_part_hashes": [sha(args.parts / f"part_{k:02d}.npz") for k in range(16)],
           "bars": int(len(bucket)), "raw_identities": int(len(sig_a)), "unique_masks": int(len(unique_a)), "records": candidate,
           "oracle_records": oracle, "signal_engines_exact": signal_exact, "same_keyset": set(left) == set(right),
           "ledger_hash_mismatches": len(mismatches), "mismatch_keys": mismatches, "holdout_opened": False}
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(obj, separators=(",", ":")))
    summary = {"bars": len(bucket), "raw_identities": len(sig_a), "unique_masks": len(unique_a), "side_records": len(candidate),
               "signal_engines_exact": signal_exact, "same_keyset": set(left) == set(right), "ledger_hash_mismatches": len(mismatches),
               "total_trades": sum(r["n"] for r in candidate), "net_r_sum": sum(r["net_r"] for r in candidate),
               "oracle_total_trades": sum(r["n"] for r in oracle), "oracle_net_r_sum": sum(r["net_r"] for r in oracle),
               "exec_minutes": len(minute), "runner_sha256": sha(__file__), "frozen_runner_sha256": sha(args.frozen),
               "output_sha256": sha(args.out), "holdout_opened": False, "seconds": time.time() - started}
    Path(str(args.out) + ".summary.json").write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=2))
    if not signal_exact or set(left) != set(right) or mismatches or len(candidate) != 626: raise SystemExit(2)


if __name__ == "__main__":
    main()
