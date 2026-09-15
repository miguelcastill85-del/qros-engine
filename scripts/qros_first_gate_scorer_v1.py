#!/usr/bin/env python3
"""Deterministic primary scorer for Seed0076 FIRST_GATE.

Build and unit-test phases are non-economic. The module contains no market-data
loader and no repository discovery. Economic observations may only be supplied
later by an explicit FG_SCORER_PARITY_PASS execution ticket.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

SCHEMA_INPUT = "QROS_FIRST_GATE_CANONICAL_MASK_OBSERVATIONS_1.0"
SCHEMA_OUTPUT = "QROS_FIRST_GATE_SCORER_RESULT_1.0"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
PER_SHARD_Q = 1.0 / 1200.0
MIN_TRADES = 30
ANNUALIZATION_DAYS = 252.0


class ScorerError(RuntimeError):
    pass


@dataclass(frozen=True)
class HACTest:
    d: int
    lag: int
    mean_daily_r: float
    omega: float
    se: float
    t_hac: float
    raw_p: float


def _finite_number(x: Any, label: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ScorerError(f"NON_NUMERIC:{label}")
    y = float(x)
    if not math.isfinite(y):
        raise ScorerError(f"NON_FINITE:{label}")
    return y


def _metric_value(x: float) -> float | str | None:
    if math.isnan(x):
        return None
    if math.isinf(x):
        return "INF" if x > 0 else "-INF"
    return x


def hac_one_sided_positive_mean(daily_r: Iterable[float]) -> HACTest:
    values = [float(x) for x in daily_r]
    if any(not math.isfinite(x) for x in values):
        raise ScorerError("NON_FINITE_DAILY_R")
    d = len(values)
    if d == 0:
        return HACTest(0, 0, 0.0, 0.0, 0.0, 0.0, 1.0)
    mean_r = math.fsum(values) / d
    lag = min(d - 1, int(math.floor(4.0 * ((d / 100.0) ** (2.0 / 9.0)))))
    centered = [x - mean_r for x in values]
    gamma0 = math.fsum(x * x for x in centered) / d
    omega = gamma0
    for ell in range(1, lag + 1):
        gamma = math.fsum(centered[t] * centered[t - ell] for t in range(ell, d)) / d
        weight = 1.0 - (ell / (lag + 1.0))
        omega += 2.0 * weight * gamma
    omega_nonneg = max(omega, 0.0)
    se = math.sqrt(omega_nonneg / d)
    if not math.isfinite(se) or se <= 0.0:
        return HACTest(d, lag, mean_r, omega, se if math.isfinite(se) else 0.0, 0.0, 1.0)
    t_hac = mean_r / se
    raw_p = 0.5 * math.erfc(t_hac / math.sqrt(2.0))
    if not math.isfinite(raw_p):
        raw_p = 1.0
    raw_p = min(max(raw_p, 0.0), 1.0)
    return HACTest(d, lag, mean_r, omega, se, t_hac, raw_p)


def harmonic_number(m: int) -> float:
    if m <= 0:
        raise ScorerError("BY_MUST_HAVE_POSITIVE_M")
    return math.fsum(1.0 / j for j in range(1, m + 1))


def apply_benjamini_yekutieli(rows: list[dict[str, Any]], q: float = PER_SHARD_Q) -> int:
    if not rows:
        raise ScorerError("NO_HYPOTHESES")
    if not (0.0 < q < 1.0):
        raise ScorerError("INVALID_BY_Q")
    m = len(rows)
    c_m = harmonic_number(m)
    ordered = sorted(rows, key=lambda r: (float(r["raw_p"]), str(r["signal_config_id"])))
    k_star = 0
    for rank, row in enumerate(ordered, start=1):
        p = float(row["raw_p"])
        if not (0.0 <= p <= 1.0) or not math.isfinite(p):
            raise ScorerError("INVALID_RAW_P")
        critical = (rank * q) / (m * c_m)
        if p <= critical:
            k_star = rank
    rejected = {ordered[i]["signal_config_id"] for i in range(k_star)}
    for row in rows:
        row["by_rejected"] = row["signal_config_id"] in rejected
        row["by_q"] = q
        row["by_m"] = m
        row["by_c_m"] = c_m
    return k_star


def _max_drawdown(trade_r: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in trade_r:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _longest_underwater_days(daily_r: list[float]) -> int:
    equity = 0.0
    peak = 0.0
    streak = 0
    longest = 0
    for r in daily_r:
        equity += r
        if equity >= peak:
            peak = equity
            streak = 0
        else:
            streak += 1
            longest = max(longest, streak)
    return longest


def _annualized_sharpe(daily_r: list[float]) -> float:
    if len(daily_r) < 2:
        return 0.0
    mu = math.fsum(daily_r) / len(daily_r)
    sd = statistics.stdev(daily_r)
    if sd <= 0.0 or not math.isfinite(sd):
        return math.inf if mu > 0.0 else 0.0
    return math.sqrt(ANNUALIZATION_DAYS) * mu / sd


def _annualized_sortino(daily_r: list[float]) -> float:
    if not daily_r:
        return 0.0
    mu = math.fsum(daily_r) / len(daily_r)
    downside = math.sqrt(math.fsum(min(x, 0.0) ** 2 for x in daily_r) / len(daily_r))
    if downside <= 0.0 or not math.isfinite(downside):
        return math.inf if mu > 0.0 else 0.0
    return math.sqrt(ANNUALIZATION_DAYS) * mu / downside


def _period_concentration(period_values: dict[str, float]) -> dict[str, Any]:
    denom = math.fsum(abs(v) for v in period_values.values())
    if denom <= 0.0:
        share = 0.0
        dominant = None
    else:
        dominant, value = max(period_values.items(), key=lambda kv: (abs(kv[1]), kv[0]))
        share = abs(value) / denom
    return {"net_r": dict(sorted(period_values.items())), "max_abs_contribution_share": share, "dominant_period": dominant}


def _validate_dates(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ScorerError("ELIGIBLE_DEV_DATES_REQUIRED")
    if any(not isinstance(x, str) for x in values):
        raise ScorerError("INVALID_DEV_DATE_TYPE")
    if values != sorted(values) or len(values) != len(set(values)):
        raise ScorerError("DEV_DATES_MUST_BE_UNIQUE_SORTED")
    for x in values:
        try:
            date.fromisoformat(x)
        except Exception as exc:
            raise ScorerError(f"INVALID_DEV_DATE:{x}") from exc
    return values


def score_mask(mask: dict[str, Any], eligible_dates: list[str]) -> dict[str, Any]:
    config_id = mask.get("signal_config_id")
    event_sha = mask.get("event_mask_sha256")
    zero = mask.get("zero_event_class")
    trades = mask.get("trades")
    if not isinstance(config_id, str) or not config_id:
        raise ScorerError("INVALID_SIGNAL_CONFIG_ID")
    if not isinstance(event_sha, str) or len(event_sha) != 64:
        raise ScorerError(f"INVALID_EVENT_MASK_SHA:{config_id}")
    try:
        int(event_sha, 16)
    except Exception as exc:
        raise ScorerError(f"INVALID_EVENT_MASK_SHA:{config_id}") from exc
    if not isinstance(zero, bool) or not isinstance(trades, list):
        raise ScorerError(f"INVALID_MASK_FIELDS:{config_id}")
    if zero and trades:
        raise ScorerError(f"ZERO_EVENT_HAS_TRADES:{config_id}")

    eligible_set = set(eligible_dates)
    daily = {d: 0.0 for d in eligible_dates}
    normalized: list[tuple[int, str, str, float]] = []
    seen_trade_ids: set[str] = set()
    for t in trades:
        if not isinstance(t, dict):
            raise ScorerError(f"INVALID_TRADE_ROW:{config_id}")
        trade_id = t.get("trade_id")
        dev_date = t.get("dev_date")
        entry = t.get("entry_ts_ms")
        exit_ = t.get("exit_ts_ms")
        r = _finite_number(t.get("r"), f"trade_r:{config_id}")
        if not isinstance(trade_id, str) or not trade_id or trade_id in seen_trade_ids:
            raise ScorerError(f"INVALID_OR_DUPLICATE_TRADE_ID:{config_id}")
        seen_trade_ids.add(trade_id)
        if dev_date not in eligible_set:
            raise ScorerError(f"TRADE_DATE_OUTSIDE_DEV:{config_id}:{dev_date}")
        if not isinstance(entry, int) or isinstance(entry, bool) or not isinstance(exit_, int) or isinstance(exit_, bool) or exit_ < entry:
            raise ScorerError(f"INVALID_TRADE_TIMESTAMPS:{config_id}:{trade_id}")
        daily[dev_date] += r
        normalized.append((exit_, trade_id, dev_date, r))

    normalized.sort(key=lambda x: (x[0], x[1]))
    trade_r = [x[3] for x in normalized]
    daily_r = [daily[d] for d in eligible_dates]
    trade_count = len(trade_r)
    net_r = math.fsum(trade_r)
    gross_profit = math.fsum(x for x in trade_r if x > 0.0)
    gross_loss_abs = -math.fsum(x for x in trade_r if x < 0.0)
    pf_value = math.inf if gross_loss_abs == 0.0 and gross_profit > 0.0 else (gross_profit / gross_loss_abs if gross_loss_abs > 0.0 else 0.0)
    expectancy = net_r / trade_count if trade_count else 0.0
    win_rate = (sum(1 for x in trade_r if x > 0.0) / trade_count) if trade_count else 0.0
    dd_r = _max_drawdown(trade_r)
    recovery = (net_r / dd_r) if dd_r > 0.0 else (math.inf if net_r > 0.0 else 0.0)
    hac = hac_one_sided_positive_mean(daily_r)
    raw_p = 1.0 if zero or trade_count < MIN_TRADES else hac.raw_p

    yearly: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    for d, r in daily.items():
        yearly[d[:4]] += r
        monthly[d[:7]] += r

    return {
        "signal_config_id": config_id,
        "event_mask_sha256": event_sha,
        "zero_event_class": zero,
        "trades": trade_count,
        "net_R": net_r,
        "PF": _metric_value(pf_value),
        "expectancy_R": expectancy,
        "win_rate": win_rate,
        "DD_R": dd_r,
        "recovery": _metric_value(recovery),
        "Sharpe": _metric_value(_annualized_sharpe(daily_r)),
        "Sortino": _metric_value(_annualized_sortino(daily_r)),
        "year_concentration": _period_concentration(yearly),
        "month_concentration": _period_concentration(monthly),
        "underwater_max_eligible_days": _longest_underwater_days(daily_r),
        "frequency_trades_per_252_eligible_days": trade_count * ANNUALIZATION_DAYS / len(eligible_dates),
        "HAC_D": hac.d,
        "HAC_lag": hac.lag,
        "HAC_mean_daily_R": hac.mean_daily_r,
        "HAC_omega": hac.omega,
        "HAC_SE": hac.se,
        "HAC_t": hac.t_hac,
        "raw_p": raw_p,
        "pf_internal_gt_1": pf_value > 1.0,
    }


def score_document(doc: dict[str, Any]) -> dict[str, Any]:
    if doc.get("schema") != SCHEMA_INPUT:
        raise ScorerError("INPUT_SCHEMA_MISMATCH")
    if doc.get("campaign") != CAMPAIGN:
        raise ScorerError("CAMPAIGN_MISMATCH")
    ticket_id = doc.get("ticket_id")
    shard_id = doc.get("shard_id")
    if not isinstance(ticket_id, str) or not ticket_id or not isinstance(shard_id, str) or not shard_id:
        raise ScorerError("TICKET_OR_SHARD_MISSING")
    eligible_dates = _validate_dates(doc.get("eligible_dev_dates"))
    masks = doc.get("canonical_masks")
    if not isinstance(masks, list) or not masks:
        raise ScorerError("CANONICAL_MASKS_REQUIRED")

    results = [score_mask(m, eligible_dates) for m in masks]
    ids = [r["signal_config_id"] for r in results]
    shas = [r["event_mask_sha256"] for r in results]
    if len(ids) != len(set(ids)):
        raise ScorerError("DUPLICATE_SIGNAL_CONFIG_ID")
    if len(shas) != len(set(shas)):
        raise ScorerError("DUPLICATE_EVENT_MASK_SHA")
    expected_m = doc.get("expected_distinct_mask_classes")
    if expected_m is not None:
        if not isinstance(expected_m, int) or isinstance(expected_m, bool) or expected_m != len(results):
            raise ScorerError("DISTINCT_MASK_CLASS_COUNT_MISMATCH")

    k_star = apply_benjamini_yekutieli(results)
    survivor_count = 0
    for row in results:
        row["candidate_survives"] = bool(
            row["by_rejected"]
            and row["trades"] >= MIN_TRADES
            and row["net_R"] > 0.0
            and row["expectancy_R"] > 0.0
            and row["pf_internal_gt_1"]
            and not row["zero_event_class"]
        )
        row.pop("pf_internal_gt_1", None)
        survivor_count += int(row["candidate_survives"])

    results.sort(key=lambda r: r["signal_config_id"])
    decision = "PASS_FIRST_GATE" if survivor_count > 0 else "REJECTED_FIRST_GATE"
    return {
        "schema": SCHEMA_OUTPUT,
        "campaign": CAMPAIGN,
        "ticket_id": ticket_id,
        "shard_id": shard_id,
        "eligible_dev_date_count": len(eligible_dates),
        "distinct_mask_class_count": len(results),
        "by_q": PER_SHARD_Q,
        "by_rejection_rank_k": k_star,
        "survivor_count": survivor_count,
        "shard_decision": decision,
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    try:
        doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
        out = score_document(doc)
        Path(args.output).write_text(json.dumps(out, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    except (ScorerError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "output": args.output, "decision": out["shard_decision"], "survivors": out["survivor_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
