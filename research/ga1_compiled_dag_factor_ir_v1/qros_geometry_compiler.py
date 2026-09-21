from __future__ import annotations
from dataclasses import dataclass
import numpy as np

SCHEMA = "QROS_GEOMETRY_COMPILED_PRIMITIVES_1.0"


def _safe(arr: np.ndarray, idx: np.ndarray) -> np.ndarray:
    idx = np.asarray(idx, dtype=np.int64)
    out = np.full(len(idx), np.nan, dtype=np.float64)
    valid = (idx >= 0) & (idx < len(arr))
    out[valid] = np.asarray(arr, dtype=np.float64)[idx[valid]]
    return out


@dataclass(frozen=True)
class GeometryPrimitives:
    # All arrays are indexed by signal bar index. Indicator values are causally
    # anchored to bar_idx-1, exactly matching GateContext.eval_family V221.
    valid_struct: np.ndarray
    valid_indicator_index: np.ndarray
    atr_prev: np.ndarray
    box_atr: np.ndarray
    contraction2: np.ndarray
    contraction3: np.ndarray
    contraction4: np.ndarray
    midpoint_ema_atr_by_fast: dict[int, np.ndarray]


def compile_geometry_primitives(ind: dict[str, np.ndarray], sh: np.ndarray, sl: np.ndarray,
                                boxhist: np.ndarray, fast_periods: tuple[int, ...]) -> GeometryPrimitives:
    sh = np.asarray(sh, dtype=np.float64)
    sl = np.asarray(sl, dtype=np.float64)
    boxhist = np.asarray(boxhist, dtype=np.float64)
    n = len(sh)
    if len(sl) != n or boxhist.shape != (n, 4):
        raise ValueError("GEOMETRY_SHAPE_MISMATCH")
    bar = np.arange(n, dtype=np.int64)
    ii = bar - 1
    atr_source = np.asarray(ind["ATR14"], dtype=np.float64)
    atr_prev = _safe(atr_source, ii)
    valid_indicator_index = (ii >= 0) & (ii < len(atr_source))
    valid_struct = ~np.isnan(sh) & ~np.isnan(sl)
    width = np.abs(sh - sl)
    box_atr = np.full(n, np.nan, dtype=np.float64)
    ok_atr = (atr_prev > 0) & valid_struct
    box_atr[ok_atr] = width[ok_atr] / atr_prev[ok_atr]

    def contraction(k: int) -> np.ndarray:
        vals = boxhist[:, -k:]
        ok = ~np.isnan(vals).any(axis=1)
        for j in range(k - 1):
            ok &= vals[:, j] > vals[:, j + 1]
        return ok

    midpoint = (sh + sl) / 2.0
    dist: dict[int, np.ndarray] = {}
    for fast in sorted(set(int(x) for x in fast_periods) | {35}):
        ema = _safe(np.asarray(ind[f"EMA{fast}"], dtype=np.float64), ii)
        r = np.full(n, np.nan, dtype=np.float64)
        ok = ok_atr & ~np.isnan(ema)
        r[ok] = np.abs(midpoint[ok] - ema[ok]) / atr_prev[ok]
        dist[fast] = r
    return GeometryPrimitives(
        valid_struct=valid_struct,
        valid_indicator_index=valid_indicator_index,
        atr_prev=atr_prev,
        box_atr=box_atr,
        contraction2=contraction(2),
        contraction3=contraction(3),
        contraction4=contraction(4),
        midpoint_ema_atr_by_fast=dist,
    )


def evaluate_compiled_geometry(pr: GeometryPrimitives, bar_idx: np.ndarray,
                               variant: dict, active_trend: dict | None = None) -> np.ndarray:
    b = np.asarray(bar_idx, dtype=np.int64)
    nbar = len(pr.valid_struct)
    valid = (b >= 0) & (b < nbar)
    in_range = valid.copy()
    valid[in_range] &= pr.valid_indicator_index[b[in_range]]
    out = np.zeros(len(b), dtype=bool)
    if not np.any(valid):
        return out
    bv = b[valid]
    ok = pr.valid_struct[bv].copy()
    cn = variant["contraction_n"]
    if cn != "OFF":
        k = int(cn)
        table = {2: pr.contraction2, 3: pr.contraction3, 4: pr.contraction4}
        if k not in table:
            raise ValueError("UNSUPPORTED_CONTRACTION_N")
        ok &= table[k][bv]
    mba = variant["max_box_atr"]
    if mba != "OFF":
        x = pr.box_atr[bv]
        ok &= ~np.isnan(x) & (x <= float(mba))
    mm = variant["max_midpoint_to_fast_ema_atr"]
    if mm != "OFF":
        fast = int(active_trend["ema_triple"][0]) if active_trend else 35
        if fast not in pr.midpoint_ema_atr_by_fast:
            raise ValueError("FAST_EMA_NOT_COMPILED")
        x = pr.midpoint_ema_atr_by_fast[fast][bv]
        ok &= ~np.isnan(x) & (x <= float(mm))
    out[valid] = ok
    return out
