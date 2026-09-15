#!/usr/bin/env python3
"""Independent deterministic oracle for Seed0076 FIRST_GATE scorer parity.

This module implements the frozen multiplicity contract directly and deliberately
DOES NOT import qros_first_gate_scorer_v1.  Construction/parity validation is
synthetic/adversarial only; no market-data or repository-wide discovery exists.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "QROS_FIRST_GATE_CANONICAL_MASK_OBSERVATIONS_1.0"
OUTPUT_SCHEMA = "QROS_FIRST_GATE_SCORER_RESULT_1.0"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
Q_SHARD = 1.0 / 1200.0
MIN_TRADES = 30
ANNUALIZATION_DAYS = 252.0


class OracleError(RuntimeError):
    pass


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleError(f"NON_NUMERIC:{label}")
    out = float(value)
    if not math.isfinite(out):
        raise OracleError(f"NON_FINITE:{label}")
    return out


def _json_metric(value: float) -> float | str | None:
    if math.isnan(value):
        return None
    if math.isinf(value):
        return "INF" if value > 0.0 else "-INF"
    return value


def _dates(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise OracleError("ELIGIBLE_DEV_DATES_REQUIRED")
    if any(not isinstance(x, str) for x in raw):
        raise OracleError("INVALID_DEV_DATE_TYPE")
    if raw != sorted(raw) or len(raw) != len(set(raw)):
        raise OracleError("DEV_DATES_MUST_BE_UNIQUE_SORTED")
    for item in raw:
        try:
            date.fromisoformat(item)
        except Exception as exc:
            raise OracleError(f"INVALID_DEV_DATE:{item}") from exc
    return list(raw)


def _hac(daily: list[float]) -> dict[str, float | int]:
    if any(not math.isfinite(v) for v in daily):
        raise OracleError("NON_FINITE_DAILY_R")
    d = len(daily)
    if d == 0:
        return {"d": 0, "lag": 0, "mean": 0.0, "omega": 0.0, "se": 0.0, "t": 0.0, "p": 1.0}
    mean = math.fsum(daily) / d
    lag = min(d - 1, int(math.floor(4.0 * ((d / 100.0) ** (2.0 / 9.0)))))
    centered = [v - mean for v in daily]
    gamma0 = math.fsum(v * v for v in centered) / d
    omega_terms = [gamma0]
    for ell in range(1, lag + 1):
        gamma = math.fsum(centered[t] * centered[t - ell] for t in range(ell, d)) / d
        omega_terms.append(2.0 * (1.0 - ell / (lag + 1.0)) * gamma)
    omega = math.fsum(omega_terms)
    se = math.sqrt(max(omega, 0.0) / d)
    if not math.isfinite(se) or se <= 0.0:
        return {"d": d, "lag": lag, "mean": mean, "omega": omega, "se": 0.0 if not math.isfinite(se) else se, "t": 0.0, "p": 1.0}
    t_stat = mean / se
    p = 0.5 * math.erfc(t_stat / math.sqrt(2.0))
    if not math.isfinite(p):
        p = 1.0
    p = min(1.0, max(0.0, p))
    return {"d": d, "lag": lag, "mean": mean, "omega": omega, "se": se, "t": t_stat, "p": p}


def _harmonic(m: int) -> float:
    if m <= 0:
        raise OracleError("BY_MUST_HAVE_POSITIVE_M")
    return math.fsum(1.0 / j for j in range(1, m + 1))


def _apply_by(rows: list[dict[str, Any]], q: float = Q_SHARD) -> int:
    if not rows:
        raise OracleError("NO_HYPOTHESES")
    if not 0.0 < q < 1.0:
        raise OracleError("INVALID_BY_Q")
    m = len(rows)
    c_m = _harmonic(m)
    ordered = sorted(rows, key=lambda row: (float(row["raw_p"]), str(row["signal_config_id"])))
    k_star = 0
    for rank, row in enumerate(ordered, 1):
        p = float(row["raw_p"])
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            raise OracleError("INVALID_RAW_P")
        if p <= (rank * q) / (m * c_m):
            k_star = rank
    rejected = {ordered[i]["signal_config_id"] for i in range(k_star)}
    for row in rows:
        row["by_rejected"] = row["signal_config_id"] in rejected
        row["by_q"] = q
        row["by_m"] = m
        row["by_c_m"] = c_m
    return k_star


def _drawdown(trade_r: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in trade_r:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _underwater(daily: list[float]) -> int:
    equity = 0.0
    peak = 0.0
    run = 0
    longest = 0
    for value in daily:
        equity += value
        if equity >= peak:
            peak = equity
            run = 0
        else:
            run += 1
            longest = max(longest, run)
    return longest


def _sharpe(daily: list[float]) -> float:
    if len(daily) < 2:
        return 0.0
    mean = math.fsum(daily) / len(daily)
    sd = statistics.stdev(daily)
    if sd <= 0.0 or not math.isfinite(sd):
        return math.inf if mean > 0.0 else 0.0
    return math.sqrt(ANNUALIZATION_DAYS) * mean / sd


def _sortino(daily: list[float]) -> float:
    if not daily:
        return 0.0
    mean = math.fsum(daily) / len(daily)
    downside = math.sqrt(math.fsum(min(v, 0.0) ** 2 for v in daily) / len(daily))
    if downside <= 0.0 or not math.isfinite(downside):
        return math.inf if mean > 0.0 else 0.0
    return math.sqrt(ANNUALIZATION_DAYS) * mean / downside


def _concentration(values: dict[str, float]) -> dict[str, Any]:
    denom = math.fsum(abs(v) for v in values.values())
    if denom <= 0.0:
        dominant = None
        share = 0.0
    else:
        dominant, amount = max(values.items(), key=lambda kv: (abs(kv[1]), kv[0]))
        share = abs(amount) / denom
    return {"net_r": dict(sorted(values.items())), "max_abs_contribution_share": share, "dominant_period": dominant}


def _score_mask(mask: dict[str, Any], eligible_dates: list[str]) -> dict[str, Any]:
    config_id = mask.get("signal_config_id")
    event_sha = mask.get("event_mask_sha256")
    zero = mask.get("zero_event_class")
    trades = mask.get("trades")
    if not isinstance(config_id, str) or not config_id:
        raise OracleError("INVALID_SIGNAL_CONFIG_ID")
    if not isinstance(event_sha, str) or len(event_sha) != 64:
        raise OracleError(f"INVALID_EVENT_MASK_SHA:{config_id}")
    try:
        int(event_sha, 16)
    except Exception as exc:
        raise OracleError(f"INVALID_EVENT_MASK_SHA:{config_id}") from exc
    if not isinstance(zero, bool) or not isinstance(trades, list):
        raise OracleError(f"INVALID_MASK_FIELDS:{config_id}")
    if zero and trades:
        raise OracleError(f"ZERO_EVENT_HAS_TRADES:{config_id}")

    eligible_set = set(eligible_dates)
    daily_by_date = {d: 0.0 for d in eligible_dates}
    normalized: list[tuple[int, str, str, float]] = []
    seen: set[str] = set()
    for trade in trades:
        if not isinstance(trade, dict):
            raise OracleError(f"INVALID_TRADE_ROW:{config_id}")
        trade_id = trade.get("trade_id")
        dev_date = trade.get("dev_date")
        entry = trade.get("entry_ts_ms")
        exit_ = trade.get("exit_ts_ms")
        r = _number(trade.get("r"), f"trade_r:{config_id}")
        if not isinstance(trade_id, str) or not trade_id or trade_id in seen:
            raise OracleError(f"INVALID_OR_DUPLICATE_TRADE_ID:{config_id}")
        seen.add(trade_id)
        if dev_date not in eligible_set:
            raise OracleError(f"TRADE_DATE_OUTSIDE_DEV:{config_id}:{dev_date}")
        if not isinstance(entry, int) or isinstance(entry, bool) or not isinstance(exit_, int) or isinstance(exit_, bool) or exit_ < entry:
            raise OracleError(f"INVALID_TRADE_TIMESTAMPS:{config_id}:{trade_id}")
        daily_by_date[dev_date] += r
        normalized.append((exit_, trade_id, dev_date, r))

    normalized.sort(key=lambda row: (row[0], row[1]))
    trade_r = [row[3] for row in normalized]
    daily = [daily_by_date[d] for d in eligible_dates]
    count = len(trade_r)
    net = math.fsum(trade_r)
    profit = math.fsum(v for v in trade_r if v > 0.0)
    loss = -math.fsum(v for v in trade_r if v < 0.0)
    pf = math.inf if loss == 0.0 and profit > 0.0 else (profit / loss if loss > 0.0 else 0.0)
    expectancy = net / count if count else 0.0
    win_rate = sum(1 for v in trade_r if v > 0.0) / count if count else 0.0
    dd = _drawdown(trade_r)
    recovery = net / dd if dd > 0.0 else (math.inf if net > 0.0 else 0.0)
    test = _hac(daily)
    raw_p = 1.0 if zero or count < MIN_TRADES else float(test["p"])

    yearly: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    for d, value in daily_by_date.items():
        yearly[d[:4]] += value
        monthly[d[:7]] += value

    return {
        "signal_config_id": config_id,
        "event_mask_sha256": event_sha,
        "zero_event_class": zero,
        "trades": count,
        "net_R": net,
        "PF": _json_metric(pf),
        "expectancy_R": expectancy,
        "win_rate": win_rate,
        "DD_R": dd,
        "recovery": _json_metric(recovery),
        "Sharpe": _json_metric(_sharpe(daily)),
        "Sortino": _json_metric(_sortino(daily)),
        "year_concentration": _concentration(yearly),
        "month_concentration": _concentration(monthly),
        "underwater_max_eligible_days": _underwater(daily),
        "frequency_trades_per_252_eligible_days": count * ANNUALIZATION_DAYS / len(eligible_dates),
        "HAC_D": int(test["d"]),
        "HAC_lag": int(test["lag"]),
        "HAC_mean_daily_R": float(test["mean"]),
        "HAC_omega": float(test["omega"]),
        "HAC_SE": float(test["se"]),
        "HAC_t": float(test["t"]),
        "raw_p": raw_p,
        "pf_internal_gt_1": pf > 1.0,
    }


def oracle_score_document(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema") != INPUT_SCHEMA:
        raise OracleError("INPUT_SCHEMA_MISMATCH")
    if document.get("campaign") != CAMPAIGN:
        raise OracleError("CAMPAIGN_MISMATCH")
    ticket_id = document.get("ticket_id")
    shard_id = document.get("shard_id")
    if not isinstance(ticket_id, str) or not ticket_id or not isinstance(shard_id, str) or not shard_id:
        raise OracleError("TICKET_OR_SHARD_MISSING")
    eligible_dates = _dates(document.get("eligible_dev_dates"))
    masks = document.get("canonical_masks")
    if not isinstance(masks, list) or not masks:
        raise OracleError("CANONICAL_MASKS_REQUIRED")

    rows = [_score_mask(mask, eligible_dates) for mask in masks]
    ids = [row["signal_config_id"] for row in rows]
    shas = [row["event_mask_sha256"] for row in rows]
    if len(ids) != len(set(ids)):
        raise OracleError("DUPLICATE_SIGNAL_CONFIG_ID")
    if len(shas) != len(set(shas)):
        raise OracleError("DUPLICATE_EVENT_MASK_SHA")
    expected = document.get("expected_distinct_mask_classes")
    if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or expected != len(rows)):
        raise OracleError("DISTINCT_MASK_CLASS_COUNT_MISMATCH")

    k_star = _apply_by(rows)
    survivor_count = 0
    for row in rows:
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

    rows.sort(key=lambda row: row["signal_config_id"])
    return {
        "schema": OUTPUT_SCHEMA,
        "campaign": CAMPAIGN,
        "ticket_id": ticket_id,
        "shard_id": shard_id,
        "eligible_dev_date_count": len(eligible_dates),
        "distinct_mask_class_count": len(rows),
        "by_q": Q_SHARD,
        "by_rejection_rank_k": k_star,
        "survivor_count": survivor_count,
        "shard_decision": "PASS_FIRST_GATE" if survivor_count else "REJECTED_FIRST_GATE",
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        document = json.loads(Path(args.input).read_text(encoding="utf-8"))
        output = oracle_score_document(document)
        Path(args.output).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "shard_decision": output["shard_decision"], "survivor_count": output["survivor_count"]}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
