#!/usr/bin/env python3
"""Independent G30 M1 MID DEV parity engine.

New implementation identity for software-parity validation only. It is intentionally
independent from g30_exact_mid_v5_recovery_engine_v1.py and does not read holdout,
rank configurations, or report aggregate profitability.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from numba import njit

DT = np.dtype([("ts", "<i8"), ("bid", "<i4"), ("ask", "<i4"), ("flags", "u1")])
CANONICAL_NQX_DEV_SHA256 = "451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf"
STEP_MS = 60_000
THRESHOLDS = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0)
NS = (1, 2, 3, 4, 5, 8)
FAMILIES = (
    "CLOSE_EXCEEDS_PRIOR_N_CLOSES",
    "STRICT_MONOTONIC_N_CLOSE_SEQUENCE",
    "CLOSE_BREAKS_PRIOR_N_BAR_EXTREME",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


@njit
def _count_feature_and_exec_minutes(ts, bid, ask):
    nf = 0
    ne = 0
    last_f = np.int64(-9223372036854775807)
    last_e = np.int64(-9223372036854775807)
    for i in range(len(ts)):
        minute = (ts[i] // STEP_MS) * STEP_MS
        if ask[i] >= bid[i]:
            if minute != last_f:
                nf += 1
                last_f = minute
        if ask[i] > bid[i]:
            if minute != last_e:
                ne += 1
                last_e = minute
    return nf, ne


@njit
def build_m1_mid_and_exec_minutes(ts, bid, ask):
    nf, ne = _count_feature_and_exec_minutes(ts, bid, ask)
    bucket = np.empty(nf, np.int64)
    opn = np.empty(nf, np.int64)
    high = np.empty(nf, np.int64)
    low = np.empty(nf, np.int64)
    close = np.empty(nf, np.int64)

    mb = np.empty(ne, np.int64)
    bh = np.empty(ne, np.int64)
    bl = np.empty(ne, np.int64)
    ah = np.empty(ne, np.int64)
    al = np.empty(ne, np.int64)
    first = np.empty(ne, np.int64)
    last = np.empty(ne, np.int64)

    fi = -1
    ei = -1
    current_f = np.int64(-9223372036854775807)
    current_e = np.int64(-9223372036854775807)

    for i in range(len(ts)):
        minute = (ts[i] // STEP_MS) * STEP_MS
        b = np.int64(bid[i])
        a = np.int64(ask[i])
        if a >= b:
            x2 = b + a
            if minute != current_f:
                fi += 1
                current_f = minute
                bucket[fi] = minute
                opn[fi] = x2
                high[fi] = x2
                low[fi] = x2
                close[fi] = x2
            else:
                if x2 > high[fi]:
                    high[fi] = x2
                if x2 < low[fi]:
                    low[fi] = x2
                close[fi] = x2
        if a > b:
            if minute != current_e:
                ei += 1
                current_e = minute
                mb[ei] = minute
                bh[ei] = b
                bl[ei] = b
                ah[ei] = a
                al[ei] = a
                first[ei] = i
                last[ei] = i
            else:
                if b > bh[ei]:
                    bh[ei] = b
                if b < bl[ei]:
                    bl[ei] = b
                if a > ah[ei]:
                    ah[ei] = a
                if a < al[ei]:
                    al[ei] = a
                last[ei] = i
    return bucket, opn, high, low, close, mb, bh, bl, ah, al, first, last


@njit
def atr14_independent(high, low, close):
    n = len(close)
    out = np.full(n, np.nan, np.float64)
    tr = np.empty(n, np.float64)
    rolling = 0.0
    for i in range(n):
        v = float(high[i] - low[i])
        if i > 0:
            a = abs(float(high[i] - close[i - 1]))
            b = abs(float(low[i] - close[i - 1]))
            if a > v:
                v = a
            if b > v:
                v = b
        tr[i] = v
        rolling += v
        if i >= 14:
            rolling -= tr[i - 14]
        if i >= 13:
            out[i] = rolling / 14.0
    return out


@njit
def predicates_for_n(close, high, low, n):
    size = len(close)
    c_up = np.zeros(size, np.bool_)
    c_dn = np.zeros(size, np.bool_)
    mono_up = np.zeros(size, np.bool_)
    mono_dn = np.zeros(size, np.bool_)
    brk_up = np.zeros(size, np.bool_)
    brk_dn = np.zeros(size, np.bool_)
    for i in range(n, size):
        max_c = close[i - n]
        min_c = close[i - n]
        max_h = high[i - n]
        min_l = low[i - n]
        up = True
        dn = True
        for j in range(i - n, i):
            if close[j] > max_c:
                max_c = close[j]
            if close[j] < min_c:
                min_c = close[j]
            if high[j] > max_h:
                max_h = high[j]
            if low[j] < min_l:
                min_l = low[j]
            if close[j + 1] <= close[j]:
                up = False
            if close[j + 1] >= close[j]:
                dn = False
        c_up[i] = close[i] > max_c
        c_dn[i] = close[i] < min_c
        mono_up[i] = up
        mono_dn[i] = dn
        brk_up[i] = close[i] > max_h
        brk_dn[i] = close[i] < min_l
    return c_up, c_dn, mono_up, mono_dn, brk_up, brk_dn


def unique_signal_masks(bucket, opn, high, low, close):
    atr = atr14_independent(high, low, close)
    weekday = ((bucket // 86_400_000 + 3) % 7) < 5
    bases = {}
    for n in NS:
        p = predicates_for_n(close, high, low, n)
        bases[(FAMILIES[0], n)] = (p[0], p[1])
        bases[(FAMILIES[1], n)] = (p[2], p[3])
        bases[(FAMILIES[2], n)] = (p[4], p[5])

    seen = set()
    result = []
    for timing_index, timing in enumerate(("CURRENT_BAR_INCLUDED", "LAGGED_ONE_BAR_PRE_SHOCK")):
        if timing_index == 0:
            denominator = atr
        else:
            denominator = np.r_[np.nan, atr[:-1]]
        ratio = np.divide(high - low, denominator, out=np.full(len(close), np.nan), where=np.isfinite(denominator) & (denominator > 0))
        for threshold in THRESHOLDS:
            shock = (ratio >= threshold) & weekday
            for family in FAMILIES:
                for n in NS:
                    buy, sell = bases[(family, n)]
                    encoded = np.zeros(len(close), np.int8)
                    encoded[buy & shock] = 1
                    encoded[sell & shock] = -1
                    digest = hashlib.sha256(encoded.tobytes()).hexdigest()
                    if digest not in seen:
                        seen.add(digest)
                        result.append((f"{timing}|{threshold:g}|{family}|{n}", digest, encoded))
            encoded = np.zeros(len(close), np.int8)
            encoded[(close > opn) & shock] = 1
            encoded[(close < opn) & shock] = -1
            digest = hashlib.sha256(encoded.tobytes()).hexdigest()
            if digest not in seen:
                seen.add(digest)
                result.append((f"{timing}|{threshold:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1", digest, encoded))
    return atr, result


@njit
def lower_bound(a, x):
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


@njit
def outcomes_independent(ts, bid, ask, bucket, atr_x2, mb, bh, bl, ah, al, first, last, side):
    n = len(bucket)
    entry_t = np.full(n, -1, np.int64)
    exit_t = np.full(n, -1, np.int64)
    r_value = np.zeros(n, np.float64)
    for i in range(n):
        if not np.isfinite(atr_x2[i]) or atr_x2[i] <= 0:
            continue
        signal_close = bucket[i] + STEP_MS
        day_end = ((signal_close // 86_400_000) + 1) * 86_400_000
        deadline = signal_close + 20 * STEP_MS
        if deadline > day_end:
            deadline = day_end
        minute_index = lower_bound(mb, signal_close)
        if minute_index >= len(mb) or mb[minute_index] >= deadline:
            continue
        entry_index = first[minute_index]
        while entry_index <= last[minute_index]:
            if ts[entry_index] >= signal_close and ask[entry_index] > bid[entry_index]:
                break
            entry_index += 1
        if entry_index > last[minute_index] or ts[entry_index] >= deadline:
            continue
        entry_price = ask[entry_index] if side == 1 else bid[entry_index]
        distance = 1.5 * atr_x2[i]
        stop = entry_price - distance if side == 1 else entry_price + distance
        take = entry_price + 1.5 * distance if side == 1 else entry_price - 1.5 * distance
        entry_t[i] = ts[entry_index]
        end_minute = lower_bound(mb, deadline)
        candidate_minute = -1
        for mi in range(minute_index, end_minute):
            if side == 1:
                if bl[mi] <= stop or bh[mi] >= take:
                    candidate_minute = mi
                    break
            else:
                if ah[mi] >= stop or al[mi] <= take:
                    candidate_minute = mi
                    break
        resolved = False
        if candidate_minute >= 0:
            start_tick = first[candidate_minute]
            if start_tick < entry_index:
                start_tick = entry_index
            for j in range(start_tick, last[candidate_minute] + 1):
                if ts[j] >= deadline:
                    break
                if ask[j] <= bid[j]:
                    continue
                if side == 1:
                    if bid[j] <= stop:
                        r_value[i] = -1.0
                        exit_t[i] = ts[j]
                        resolved = True
                        break
                    if bid[j] >= take:
                        r_value[i] = 1.5
                        exit_t[i] = ts[j]
                        resolved = True
                        break
                else:
                    if ask[j] >= stop:
                        r_value[i] = -1.0
                        exit_t[i] = ts[j]
                        resolved = True
                        break
                    if ask[j] <= take:
                        r_value[i] = 1.5
                        exit_t[i] = ts[j]
                        resolved = True
                        break
        if not resolved:
            if end_minute <= minute_index:
                entry_t[i] = -1
                continue
            j = last[end_minute - 1]
            while j >= first[end_minute - 1] and (ts[j] >= deadline or ask[j] <= bid[j]):
                j -= 1
            if j < entry_index:
                entry_t[i] = -1
                continue
            exit_t[i] = ts[j]
            if side == 1:
                r_value[i] = (bid[j] - entry_price) / distance
            else:
                r_value[i] = (entry_price - ask[j]) / distance
    return entry_t, exit_t, r_value


@njit
def select_one_position_independent(encoded, side, entry_t, exit_t):
    out = np.empty(len(encoded), np.int64)
    count = 0
    previous_exit = np.int64(-1)
    target = np.int8(1 if side == 1 else -1)
    for i in range(len(encoded)):
        if encoded[i] != target:
            continue
        if entry_t[i] < 0 or entry_t[i] <= previous_exit:
            continue
        out[count] = i
        count += 1
        previous_exit = exit_t[i]
    return out[:count]


def ordered_ledger_sha(encoded, side, entry_t, exit_t, r_value):
    chosen = select_one_position_independent(encoded, side, entry_t, exit_t)
    h = hashlib.sha256()
    for q in chosen:
        h.update(np.int64(entry_t[q]).tobytes())
        h.update(np.int64(exit_t[q]).tobytes())
        h.update(np.float64(r_value[q]).tobytes())
    return h.hexdigest(), int(len(chosen))
