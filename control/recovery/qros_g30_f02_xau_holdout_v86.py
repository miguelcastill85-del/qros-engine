#!/usr/bin/env python3
"""QROS G30 F02 XAU clean holdout scorer (2025 through canonical 2026 partial).

Frozen cohort: 52 XAUUSD F02 representatives from V84/V83.
Gate: V85, frozen before holdout PnL.
Data: canonical XAU suffix beginning at global record 500,000,000, with 2024 context.
Two independent bar/signal paths and two independent raw-tick execution paths must agree exactly.
No retuning, no winner selection, no NQX clean-holdout claim.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast

SRC_SHA = '9a5a2b22e111b7005a41e7e66771decd5e31805f5b455f21e5b794a72822c26e'
CACHE_SHA = '201918b3a6d1a116a369d8b0d64ef90f11c28738e86f2dbf8d3957c0127b0e2d'
CAND_SHA = '18cf0a0aa5f00e2f2b921bf35bb1d751c798410f7a94b02e572f216af9ef33f2'
HOLDOUT_START = np.int64(1735689600000)  # 2025-01-01 source-clock boundary
YEAR_2026 = np.int64(1767225600000)       # 2026-01-01 source-clock boundary
FAMS = [
    'CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES',
    'STRICT_MONOTONIC_N_CLOSE_SEQUENCE',
    'CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME',
]


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def safe(v):
    if isinstance(v, float) and not math.isfinite(v):
        return 'INF' if v > 0 else ('-INF' if v < 0 else 'NAN')
    if isinstance(v, list):
        return [safe(x) for x in v]
    if isinstance(v, dict):
        return {k: safe(x) for k, x in v.items()}
    return v


def parse_rep(rep: str):
    shard, side, key = rep.split(':', 2)
    tf_name, feature = shard.split('_')
    tf = 60 if tf_name == 'H1' else int(tf_name[1:])
    meas, timing, threshold, fam, n = key.split('|')
    return shard, side, key, tf, feature, meas, timing, float(threshold), fam, int(n)


def base_A(h, l, cl, fam, n):
    L = len(cl)
    if fam == 'SHOCK_BAR_BODY_DIRECTION_ONLY':
        raise ValueError('body family has no persistence base')
    cw = np.lib.stride_tricks.sliding_window_view(cl, n + 1)
    b = np.zeros(L, bool); s = np.zeros(L, bool)
    if fam == FAMS[0]:
        b[n:] = cw[:, -1] > cw[:, :-1].max(axis=1)
        s[n:] = cw[:, -1] < cw[:, :-1].min(axis=1)
    elif fam == FAMS[1]:
        d = np.diff(cw, axis=1)
        b[n:] = np.all(d > 0, axis=1)
        s[n:] = np.all(d < 0, axis=1)
    elif fam == FAMS[2]:
        hw = np.lib.stride_tricks.sliding_window_view(h, n + 1)
        lw = np.lib.stride_tricks.sliding_window_view(l, n + 1)
        b[n:] = cw[:, -1] > hw[:, :-1].max(axis=1)
        s[n:] = cw[:, -1] < lw[:, :-1].min(axis=1)
    else:
        raise ValueError(fam)
    return b, s


def base_B(h, l, cl, fam, n):
    L = len(cl)
    if fam == 'SHOCK_BAR_BODY_DIRECTION_ONLY':
        raise ValueError('body family has no persistence base')
    b = np.zeros(L, bool); s = np.zeros(L, bool)
    pc = np.vstack([cl[n-k:L-k] for k in range(1, n + 1)])
    if fam == FAMS[0]:
        b[n:] = cl[n:] > pc.max(axis=0)
        s[n:] = cl[n:] < pc.min(axis=0)
    elif fam == FAMS[1]:
        d = np.diff(cl)
        pos = (d > 0).astype(np.int8); neg = (d < 0).astype(np.int8)
        b[n:] = c.rolling_sum_int(pos, n) == n
        s[n:] = c.rolling_sum_int(neg, n) == n
    elif fam == FAMS[2]:
        ph = np.vstack([h[n-k:L-k] for k in range(1, n + 1)])
        pl = np.vstack([l[n-k:L-k] for k in range(1, n + 1)])
        b[n:] = cl[n:] > ph.max(axis=0)
        s[n:] = cl[n:] < pl.min(axis=0)
    else:
        raise ValueError(fam)
    return b, s


def numerator_A(o, h, l, cl, meas):
    H = h.astype(float); L = l.astype(float); C = cl.astype(float); O = o.astype(float)
    pc = np.r_[np.nan, C[:-1]]
    if meas == 'TRUE_RANGE_OVER_ATR':
        return np.fmax(H-L, np.fmax(np.abs(H-pc), np.abs(L-pc)))
    if meas == 'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':
        return np.abs(C-pc)
    if meas == 'BODY_OVER_ATR':
        return np.abs(C-O)
    raise ValueError(meas)


def numerator_B(o, h, l, cl, meas):
    H = h.astype(np.int64); L = l.astype(np.int64); C = cl.astype(np.int64); O = o.astype(np.int64)
    pc = np.r_[C[0], C[:-1]]
    if meas == 'TRUE_RANGE_OVER_ATR':
        tr = np.maximum(H-L, np.maximum(np.abs(H-pc), np.abs(L-pc))).astype(np.int64)
        tr[0] = H[0] - L[0]
        return tr.astype(float)
    if meas == 'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':
        x = np.abs(C-pc).astype(np.int64); x[0] = 0
        return x.astype(float)
    if meas == 'BODY_OVER_ATR':
        return np.abs(C-O).astype(float)
    raise ValueError(meas)


def signal_A(bucket, o, h, l, cl, atr, meas, timing, threshold, fam, n, side):
    den = atr if timing == 'CURRENT_BAR_INCLUDED' else np.r_[np.nan, atr[:-1]]
    num = numerator_A(o, h, l, cl, meas)
    ratio = np.divide(num, den, out=np.full(len(cl), np.nan), where=np.isfinite(num) & np.isfinite(den) & (den > 0))
    weekday = ((bucket // 86400000 + 3) % 7) < 5
    shock = (ratio >= threshold) & weekday
    if fam == 'SHOCK_BAR_BODY_DIRECTION_ONLY':
        directional = (cl > o) if side == 'BUY' else (cl < o)
    else:
        b, s = base_A(h, l, cl, fam, n); directional = b if side == 'BUY' else s
    return shock & directional & ((bucket + np.int64(1)) >= np.int64(-9223372036854775807))


def signal_B(bucket, o, h, l, cl, atr, meas, timing, threshold, fam, n, side):
    den = atr if timing == 'CURRENT_BAR_INCLUDED' else np.r_[np.nan, atr[:-1]]
    num = numerator_B(o, h, l, cl, meas)
    ratio = np.divide(num, den, out=np.full(len(cl), np.nan), where=np.isfinite(den) & (den > 0))
    weekday = ((bucket // 86400000 + 3) % 7) < 5
    shock = (ratio >= threshold) & weekday
    if fam == 'SHOCK_BAR_BODY_DIRECTION_ONLY':
        directional = (cl > o) if side == 'BUY' else (cl < o)
    else:
        b, s = base_B(h, l, cl, fam, n); directional = b if side == 'BUY' else s
    return shock & directional


def ledger_sha(chosen, et, xt, rr):
    h = hashlib.sha256()
    for q in chosen:
        h.update(np.int64(et[q]).tobytes())
        h.update(np.int64(xt[q]).tobytes())
        h.update(np.float64(rr[q]).tobytes())
    return h.hexdigest()


def mask_sha(mask):
    return hashlib.sha256(np.ascontiguousarray(mask, dtype=np.uint8).tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--candidates', type=Path, required=True)
    ap.add_argument('--shard', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if sha_file(a.src) != SRC_SHA: raise SystemExit('SRC_SHA_MISMATCH')
    if sha_file(a.cache) != CACHE_SHA: raise SystemExit('CACHE_SHA_MISMATCH')
    if sha_file(a.candidates) != CAND_SHA: raise SystemExit('CANDIDATE_SHA_MISMATCH')

    co = json.load(a.candidates.open())
    xau = co['assets']['XAUUSD']['candidates']
    chosen_candidates = [q for q in xau if q['representative'].split(':', 1)[0] == a.shard]
    if not chosen_candidates: raise SystemExit('NO_CANDIDATES_FOR_SHARD')

    tf_name, feature = a.shard.split('_')
    tf = 60 if tf_name == 'H1' else int(tf_name[1:])
    step = np.int64(tf * 60000)
    mm = np.memmap(a.src, dtype=c.DT, mode='r')
    with np.load(a.cache) as z:
        mb = z['mb']
        ks = ('bo','bh','bl','bc') if feature == 'BID' else ('mo','mh','ml','mc')
        vals = [z[k] for k in ks]
        A = c.bars_A(mb, *vals, tf)
        B = c.bars_B(mb, *vals, tf)
        if c.digest_arrays(A) != c.digest_arrays(B): raise SystemExit('BAR_PARITY_FAIL')
        atrA = c.atr_A(A[2], A[3], A[4]); atrB = c.atr_B(B[2], B[3], B[4])
        holdout_bar = (A[0] + step) >= HOLDOUT_START
        masks = {}
        unionB = np.zeros(len(A[0]), bool); unionS = np.zeros(len(A[0]), bool)
        for q in chosen_candidates:
            rep = q['representative']
            shard, side, key, tf2, feature2, meas, timing, threshold, fam, n = parse_rep(rep)
            if shard != a.shard or tf2 != tf or feature2 != feature: raise SystemExit('REP_PARSE_MISMATCH')
            ma = signal_A(*A, atrA, meas, timing, threshold, fam, n, side) & holdout_bar
            mbb = signal_B(*B, atrB, meas, timing, threshold, fam, n, side) & holdout_bar
            if not np.array_equal(ma, mbb): raise SystemExit('SIGNAL_PARITY_FAIL ' + rep)
            masks[rep] = ma
            if side == 'BUY': unionB |= ma
            else: unionS |= ma

        ex = [z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')]
        outA_B = c.outcome_A(mm['ts'], mm['bid'], mm['ask'], A[0], atrA, step, *ex, unionB, 1) if unionB.any() else None
        outB_B = outcome_B_fast(mm['ts'], mm['bid'], mm['ask'], B[0], atrB, step, *ex, unionB, 1) if unionB.any() else None
        outA_S = c.outcome_A(mm['ts'], mm['bid'], mm['ask'], A[0], atrA, step, *ex, unionS, -1) if unionS.any() else None
        outB_S = outcome_B_fast(mm['ts'], mm['bid'], mm['ask'], B[0], atrB, step, *ex, unionS, -1) if unionS.any() else None

        records = []
        for q in chosen_candidates:
            rep = q['representative']; side = q['direction']; mask = masks[rep]
            OA, OB = (outA_B, outB_B) if side == 'BUY' else (outA_S, outB_S)
            ca = c.select_A(mask, OA[0], OA[1]); cb = c.select_B(mask, OB[0], OB[1])
            if not np.array_equal(ca, cb): raise SystemExit('SELECT_PARITY_FAIL ' + rep)
            if len(ca):
                for k in range(6):
                    if not np.array_equal(OA[k][ca], OB[k][cb]): raise SystemExit('TRADE_PARITY_FAIL ' + rep)
            rr = OA[5][ca].astype(float); ei = OA[2][ca]; xi = OA[3][ca]; dist = OA[4][ca]; et = OA[0][ca]
            if np.any(et < HOLDOUT_START): raise SystemExit('PRE_HOLDOUT_ENTRY_LEAK ' + rep)
            if len(ca):
                spread = (mm['ask'][ei]-mm['bid'][ei]).astype(float) + (mm['ask'][xi]-mm['bid'][xi]).astype(float)
                extra = np.divide(spread, dist, out=np.zeros(len(spread)), where=dist>0)
                cons = rr - 0.5*extra; sev = rr - extra
            else:
                cons = rr.copy(); sev = rr.copy()
            pfc = c.pf(rr); pfk = c.pf(cons); pfs = c.pf(sev)
            r2025 = float(rr[et < YEAR_2026].sum()); r2026 = float(rr[et >= YEAR_2026].sum())
            passed = (len(ca) >= 10 and pfc >= 1.20 and pfk >= 1.10 and pfs >= 1.00 and
                      float(rr.sum()) > 0 and float(cons.sum()) > 0 and float(sev.sum()) > 0 and r2025 > 0)
            records.append({
                'cluster_id': q['cluster_id'], 'representative': rep, 'direction': side,
                'cluster_type': q['type'], 'cluster_size': q['size'], 'members_sha256': q['members_sha256'],
                'signal_mask_sha256_holdout': mask_sha(mask), 'n': int(len(ca)),
                'net_c': float(rr.sum()), 'net_k': float(cons.sum()), 'net_s': float(sev.sum()),
                'pf_c': pfc, 'pf_k': pfk, 'pf_s': pfs,
                'r2025': r2025, 'r2026_partial': r2026,
                'ledger_sha256': ledger_sha(ca, OA[0], OA[1], OA[5]), 'pass': bool(passed)
            })

    obj = {
        'schema':'QROS_G30_F02_XAU_HOLDOUT_SHARD_V86_v1', 'status':'PASS',
        'campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1', 'frontier':'F02_SHOCK_MEASURE_ALTERNATIVES',
        'asset':'XAUUSD', 'scope':'CLEAN_HOLDOUT_2025_THROUGH_CANONICAL_2026_PARTIAL',
        'gate_ref':'control/QROS_G30_F02_XAU_HOLDOUT_GATE_V85_v1.json', 'shard':a.shard,
        'source_sha256':SRC_SHA, 'cache_sha256':CACHE_SHA, 'candidate_sha256':CAND_SHA,
        'candidate_count':len(records), 'trade_parity':'PASS_EXACT', 'signal_parity':'PASS_EXACT',
        'passed':sum(r['pass'] for r in records), 'passed_buy':sum(r['pass'] and r['direction']=='BUY' for r in records),
        'passed_sell':sum(r['pass'] and r['direction']=='SELL' for r in records),
        'records':records, 'holdout_opened':True, 'holdout_pnl_read':True, 'retuning':False,
        'mt5_executed':False
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(safe(obj), separators=(',',':'), allow_nan=False), encoding='utf-8')
    print(json.dumps({k:obj[k] for k in ['shard','candidate_count','passed','passed_buy','passed_sell','trade_parity','signal_parity']}, sort_keys=True))
    print('bytes', a.out.stat().st_size, 'sha256', sha_file(a.out))

if __name__ == '__main__': main()
