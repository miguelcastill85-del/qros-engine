"""
QROS Failed Auction Edge Score v1 (QFAES)
Reference math only. No PnL optimization. No hidden fitting.

This module contains deterministic, causal component functions for the
preregistered score and the target-before-stop label. Data materialization
and full carrier scanning are intentionally separate from the score contract.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp
from typing import Iterable, Sequence, Optional

EPS = 1e-12

def clip01(x: float) -> float:
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else float(x)

def triangular_peak(x: float, left: float = 0.03, peak: float = 0.15, right: float = 0.50) -> float:
    if not (left < peak < right):
        raise ValueError("Require left < peak < right")
    if x <= left or x >= right:
        return 0.0
    if x == peak:
        return 1.0
    if x < peak:
        return (x - left) / (peak - left)
    return (right - x) / (right - peak)

def directional_mid_imbalance(mid_prices: Sequence[float], side: str, lookback_changes: int = 32) -> float:
    """
    Maps signed mid-price changes to [0,1].
    BUY rewards positive changes; SELL rewards negative changes.
    Flat changes are ignored rather than treated as evidence.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if len(mid_prices) < 2:
        return 0.5
    changes = []
    start = max(1, len(mid_prices) - lookback_changes)
    for i in range(start, len(mid_prices)):
        d = mid_prices[i] - mid_prices[i-1]
        if d > 0:
            changes.append(1)
        elif d < 0:
            changes.append(-1)
    if not changes:
        return 0.5
    signed = sum(changes) / len(changes)
    if side == "SELL":
        signed *= -1.0
    return clip01((signed + 1.0) / 2.0)

@dataclass(frozen=True)
class QFAESInputs:
    side: str
    atr: float
    level: float
    extreme: float
    outbound_start_price: float
    first_out_ms: int
    extreme_ms: int
    reclaim_ms: int
    current_spread: float
    rolling_positive_spread_p50: float
    recent_mid_prices: Sequence[float]

@dataclass(frozen=True)
class QFAESResult:
    score: float
    depth_quality: float
    dwell_quality: float
    reclaim_velocity: float
    micro_reversal: float
    spread_quality: float
    depth_atr: float
    dwell_seconds: float

def score_qfaes(x: QFAESInputs) -> QFAESResult:
    if x.side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if x.atr <= 0:
        raise ValueError("ATR must be positive")
    if x.reclaim_ms < x.first_out_ms or x.extreme_ms < x.first_out_ms or x.reclaim_ms < x.extreme_ms:
        raise ValueError("timestamps must satisfy first_out <= extreme <= reclaim")

    excursion = abs(x.extreme - x.level)
    depth_atr = excursion / x.atr
    dq = triangular_peak(depth_atr, 0.03, 0.15, 0.50)

    dwell_seconds = (x.reclaim_ms - x.first_out_ms) / 1000.0
    dwq = exp(-dwell_seconds / 180.0)

    outbound_distance = abs(x.extreme - x.outbound_start_price)
    outbound_seconds = max((x.extreme_ms - x.first_out_ms) / 1000.0, 1e-6)
    return_distance = abs(x.extreme - x.level)
    return_seconds = max((x.reclaim_ms - x.extreme_ms) / 1000.0, 1e-6)
    outbound_speed = outbound_distance / outbound_seconds
    return_speed = return_distance / return_seconds
    vr = clip01((return_speed / max(outbound_speed, EPS)) / 2.0)

    mr = directional_mid_imbalance(x.recent_mid_prices, x.side, 32)

    if x.rolling_positive_spread_p50 <= 0:
        sq = 0.0
    else:
        sq = clip01(1.0 - x.current_spread / (2.0 * x.rolling_positive_spread_p50))

    score = 25.0*dq + 20.0*dwq + 20.0*vr + 20.0*mr + 15.0*sq
    return QFAESResult(
        score=score, depth_quality=dq, dwell_quality=dwq,
        reclaim_velocity=vr, micro_reversal=mr, spread_quality=sq,
        depth_atr=depth_atr, dwell_seconds=dwell_seconds
    )

def executable_entry(side: str, bid: float, ask: float) -> float:
    if ask < bid:
        raise ValueError("crossed quote is invalid for execution")
    return ask if side == "BUY" else bid

def stop_and_target(side: str, entry: float, extreme: float, atr: float):
    """
    Structural stop: 0.05*ATR beyond sweep extreme.
    Target: exactly 1R from executable entry.
    """
    b = 0.05 * atr
    if side == "BUY":
        stop = extreme - b
        risk = entry - stop
        if risk <= 0:
            raise ValueError("invalid BUY risk")
        target = entry + risk
    elif side == "SELL":
        stop = extreme + b
        risk = stop - entry
        if risk <= 0:
            raise ValueError("invalid SELL risk")
        target = entry - risk
    else:
        raise ValueError("side must be BUY or SELL")
    return stop, target, risk

def target_before_stop(side: str, stop: float, target: float, quotes: Iterable[tuple[float,float]]) -> Optional[int]:
    """
    quotes = iterable of (bid, ask) in causal order.
    Returns 1 target first, 0 stop first, None if neither.
    SL-first on same quote.
    BUY exits are tested on Bid; SELL exits are tested on Ask.
    """
    for bid, ask in quotes:
        if ask < bid:
            continue
        if side == "BUY":
            if bid <= stop:
                return 0
            if bid >= target:
                return 1
        else:
            if ask >= stop:
                return 0
            if ask <= target:
                return 1
    return None
