#!/usr/bin/env python3
import argparse, hashlib, json, math, sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

EMPTY_SHA = hashlib.sha256(b"").hexdigest()
CONTRACT_BLOB = "bc7f859c31f7de0584b8abecbe22641fdac2ceab"
MULTIPLICITY_BLOB = "bc5ce2b52ca5734328283fb3c1d67ee1d93905c1"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"

class ScorerError(Exception):
    pass

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def decstr(x):
    if x is None:
        return None
    if not isinstance(x, Decimal):
        x = Decimal(x)
    if not x.is_finite():
        raise ScorerError("NONFINITE_DECIMAL")
    s = format(x, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s

def finite_decimal(v):
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        raise ScorerError("INVALID_R")
    if not d.is_finite():
        raise ScorerError("NONFINITE_R")
    return d

def parse_axis(path):
    axis = json.loads(path.read_text())
    if not isinstance(axis, list) or not axis:
        raise ScorerError("DATE_AXIS_INVALID")
    if axis != sorted(axis) or len(axis) != len(set(axis)):
        raise ScorerError("DATE_AXIS_NOT_SORTED_UNIQUE")
    for s in axis:
        if not isinstance(s, str):
            raise ScorerError("DATE_AXIS_INVALID")
        try:
            date.fromisoformat(s)
        except Exception:
            raise ScorerError("DATE_AXIS_INVALID")
    return axis

def validate_manifest(m):
    req = ["schema", "mode", "campaign", "asset", "side", "timeframe", "shard_id",
           "first_gate_order", "expected_distinct_mask_classes", "per_shard_q_exact",
           "multiplicity_contract_git_blob_sha1", "semantic_class_root_sha256",
           "alias_root_sha256", "scorer_contract_git_blob_sha1"]
    if any(k not in m for k in req):
        raise ScorerError("MANIFEST_FIELD_MISSING")
    if m["campaign"] != CAMPAIGN:
        raise ScorerError("CAMPAIGN_MISMATCH")
    if m["per_shard_q_exact"] != "1/1200":
        raise ScorerError("Q_MISMATCH")
    if m["multiplicity_contract_git_blob_sha1"] != MULTIPLICITY_BLOB:
        raise ScorerError("MULTIPLICITY_BLOB_MISMATCH")
    if m["scorer_contract_git_blob_sha1"] != CONTRACT_BLOB:
        raise ScorerError("SCORER_CONTRACT_BLOB_MISMATCH")
    mode = m["mode"]
    if mode == "SYNTHETIC_VALIDATION":
        if m.get("synthetic_fixture") is not True:
            raise ScorerError("SYNTHETIC_FLAG_REQUIRED")
    elif mode == "PRODUCTION":
        if m.get("execution_parity_pass") is not True:
            raise ScorerError("EXECUTION_PARITY_REQUIRED")
        er = m.get("trade_by_trade_execution_receipt")
        if not isinstance(er, dict) or not er.get("path") or not er.get("sha256"):
            raise ScorerError("EXECUTION_RECEIPT_REQUIRED")
        if m.get("economic_exposure_authorized") is not True:
            raise ScorerError("ECONOMIC_AUTHORIZATION_REQUIRED")
    else:
        raise ScorerError("MODE_INVALID")
    return mode

def hac(daily, trades):
    D = len(daily)
    if trades < 30 or D == 0:
        return None, 1.0, 0
    mean = math.fsum(daily) / D
    L = min(D - 1, math.floor(4 * ((D / 100.0) ** (2.0 / 9.0))))
    centered = [x - mean for x in daily]
    gammas = []
    for lag in range(L + 1):
        gammas.append(math.fsum(centered[t] * centered[t - lag] for t in range(lag, D)) / D)
    omega = math.fsum([gammas[0]] + [2.0 * (1.0 - l / (L + 1.0)) * gammas[l] for l in range(1, L + 1)])
    se = math.sqrt(max(omega, 0.0) / D)
    if (not math.isfinite(se)) or se <= 0:
        return None, 1.0, L
    t = mean / se
    p = max(0.0, min(1.0, 0.5 * math.erfc(t / math.sqrt(2.0))))
    return t, p, L

def diagnostics(axis, daily_dec, net, trades):
    daily = [float(x) for x in daily_dec]
    D = len(daily)
    cum = Decimal(0); peak = Decimal(0); maxdd = Decimal(0)
    underwater_days = 0; max_underwater = 0; run = 0
    by_year = defaultdict(Decimal); by_month = defaultdict(Decimal)
    for ds, r in zip(axis, daily_dec):
        by_year[ds[:4]] += r; by_month[ds[:7]] += r
        cum += r
        if cum > peak:
            peak = cum; run = 0
        elif cum < peak:
            underwater_days += 1; run += 1; max_underwater = max(max_underwater, run)
            maxdd = max(maxdd, peak - cum)
        else:
            run = 0
    mean = math.fsum(daily) / D if D else 0.0
    sharpe = None
    if D >= 2:
        sd = math.sqrt(math.fsum((x - mean) ** 2 for x in daily) / (D - 1))
        if math.isfinite(sd) and sd > 0:
            sharpe = math.sqrt(252.0) * mean / sd
    downside = math.sqrt(math.fsum(min(x, 0.0) ** 2 for x in daily) / D) if D else 0.0
    sortino = math.sqrt(252.0) * mean / downside if downside > 0 and math.isfinite(downside) else None
    def concentration(mp):
        vals = list(mp.values()); den = sum(abs(x) for x in vals)
        return None if den == 0 else max(abs(x) for x in vals) / den
    yc = concentration(by_year); mc = concentration(by_month)
    years = max(1, len(by_year))
    if maxdd > 0:
        recovery = {"value": decstr(net / maxdd), "state": "FINITE"}
    elif net > 0:
        recovery = {"value": None, "state": "POS_INF"}
    else:
        recovery = {"value": None, "state": "UNDEFINED"}
    return {
        "DD_R": decstr(maxdd), "recovery": recovery,
        "Sharpe": None if sharpe is None else repr(sharpe),
        "Sortino": None if sortino is None else repr(sortino),
        "year_concentration": None if yc is None else decstr(yc),
        "month_concentration": None if mc is None else decstr(mc),
        "year_net_R": {k: decstr(v) for k, v in sorted(by_year.items())},
        "month_net_R": {k: decstr(v) for k, v in sorted(by_month.items())},
        "underwater": {"underwater_days": underwater_days, "max_consecutive_underwater_days": max_underwater},
        "frequency": {"trades_per_eligible_day": decstr(Decimal(trades) / Decimal(D)) if D else None,
                      "trades_per_distinct_DEV_year": decstr(Decimal(trades) / Decimal(years))}
    }

def score_candidate(row, axis, axis_set):
    req = ["canonical_signal_config_id", "event_mask_sha256", "eligible_event_count", "zero_event", "trades"]
    if any(k not in row for k in req):
        raise ScorerError("CANDIDATE_FIELD_MISSING")
    cid = row["canonical_signal_config_id"]; mh = row["event_mask_sha256"]
    if not isinstance(cid, str) or not cid:
        raise ScorerError("CANDIDATE_ID_INVALID")
    if not isinstance(mh, str) or len(mh) != 64:
        raise ScorerError("MASK_SHA_INVALID")
    try: int(mh, 16)
    except Exception: raise ScorerError("MASK_SHA_INVALID")
    ec = row["eligible_event_count"]
    if not isinstance(ec, int) or ec < 0:
        raise ScorerError("ELIGIBLE_EVENT_COUNT_INVALID")
    z = row["zero_event"]
    if not isinstance(z, bool) or not isinstance(row["trades"], list):
        raise ScorerError("CANDIDATE_TYPE_INVALID")
    if z and (ec != 0 or mh != EMPTY_SHA or row["trades"]):
        raise ScorerError("ZERO_EVENT_INCONSISTENT")
    if (not z) and ec == 0:
        raise ScorerError("NONZERO_EVENT_COUNT_ZERO")
    trade_ids = set(); daily_map = defaultdict(Decimal); rs = []
    for tr in row["trades"]:
        if not isinstance(tr, dict) or any(k not in tr for k in ("trade_id", "trading_date", "R")):
            raise ScorerError("TRADE_FIELD_MISSING")
        tid = tr["trade_id"]; ds = tr["trading_date"]
        if not isinstance(tid, str) or not tid:
            raise ScorerError("TRADE_ID_INVALID")
        if tid in trade_ids:
            raise ScorerError("DUPLICATE_TRADE_ID")
        trade_ids.add(tid)
        if ds not in axis_set:
            raise ScorerError("TRADE_DATE_OUTSIDE_AXIS")
        r = finite_decimal(tr["R"]); rs.append(r); daily_map[ds] += r
    daily_dec = [daily_map[d] for d in axis]
    n = len(rs); net = sum(rs, Decimal(0))
    gp = sum((r for r in rs if r > 0), Decimal(0)); gl = -sum((r for r in rs if r < 0), Decimal(0))
    exp = None if n == 0 else net / Decimal(n); wins = sum(1 for r in rs if r > 0)
    win = None if n == 0 else Decimal(wins) / Decimal(n)
    if gl > 0:
        ratio = gp / gl; pf = {"value": decstr(ratio), "state": "FINITE"}; pf_gt1 = ratio > 1
    elif gp > 0:
        pf = {"value": None, "state": "POS_INF"}; pf_gt1 = True
    else:
        pf = {"value": None, "state": "UNDEFINED"}; pf_gt1 = False
    t, p, L = (None, 1.0, 0) if z else hac([float(x) for x in daily_dec], n)
    out = {"canonical_signal_config_id": cid, "event_mask_sha256": mh, "eligible_event_count": ec,
           "zero_event": z, "trades": n, "net_R": decstr(net),
           "expectancy_R": None if exp is None else decstr(exp), "PF": pf,
           "win_rate": None if win is None else decstr(win), "HAC_t": None if t is None else repr(t),
           "raw_p": repr(p), "HAC_lag": L, "BY_rejected": False, "survives_first_gate": False}
    out.update(diagnostics(axis, daily_dec, net, n))
    out["_gate"] = {"net_pos": net > 0, "exp_pos": exp is not None and exp > 0, "pf_gt1": pf_gt1}
    return out, p

def by_apply(scored):
    m = len(scored)
    with localcontext() as ctx:
        ctx.prec = 80
        cm = sum((Decimal(1) / Decimal(j) for j in range(1, m + 1)), Decimal(0))
        order = sorted(range(m), key=lambda i: (scored[i][1], scored[i][0]["canonical_signal_config_id"]))
        kmax = 0
        for rank, idx in enumerate(order, 1):
            threshold = (Decimal(rank) / Decimal(1200)) / (Decimal(m) * cm)
            if Decimal.from_float(scored[idx][1]) <= threshold:
                kmax = rank
        rejected = set(order[:kmax])
    for i, (row, _) in enumerate(scored):
        row["BY_rejected"] = i in rejected
        g = row.pop("_gate")
        row["survives_first_gate"] = bool(row["BY_rejected"] and row["trades"] >= 30 and g["net_pos"] and g["exp_pos"] and g["pf_gt1"])
    return kmax, decstr(cm)

def run(inp, outdir):
    inp = Path(inp); outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((inp / "manifest.json").read_text()); mode = validate_manifest(manifest)
    axis = parse_axis(inp / "date_axis.json"); axis_set = set(axis)
    scored = []; ids = set(); masks = set()
    with (inp / "candidates.jsonl").open() as f:
        for line in f:
            if not line.strip(): continue
            res, p = score_candidate(json.loads(line), axis, axis_set)
            cid = res["canonical_signal_config_id"]; mh = res["event_mask_sha256"]
            if cid in ids: raise ScorerError("DUPLICATE_CANDIDATE_ID")
            if mh in masks: raise ScorerError("DUPLICATE_MASK_SHA")
            ids.add(cid); masks.add(mh); scored.append((res, p))
    if len(scored) != manifest["expected_distinct_mask_classes"]:
        raise ScorerError("CANDIDATE_COUNT_MISMATCH")
    kmax, cm = by_apply(scored)
    rows = sorted((r for r, _ in scored), key=lambda r: r["canonical_signal_config_id"])
    result_path = outdir / "candidate_results.jsonl"
    with result_path.open("w") as f:
        for r in rows: f.write(canon(r) + "\n")
    survivors = sum(1 for r in rows if r["survives_first_gate"])
    summary = {"schema": "QROS_FIRST_GATE_SCORER_SUMMARY_1.0", "mode": mode,
               "candidate_count": len(rows), "BY_k": kmax, "harmonic_c_m": cm,
               "survivor_count": survivors,
               "shard_decision": "SYNTHETIC_NO_ECONOMIC_DECISION" if mode == "SYNTHETIC_VALIDATION" else ("PASS_FIRST_GATE" if survivors else "REJECTED_FIRST_GATE"),
               "candidate_results_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
               "economic_decision_authorized": mode == "PRODUCTION"}
    (outdir / "summary.json").write_text(canon(summary) + "\n")
    receipt = {"schema": "QROS_FIRST_GATE_SCORER_RECEIPT_1.0", "implementation": "PRIMARY",
               "summary_sha256": hashlib.sha256((outdir / "summary.json").read_bytes()).hexdigest(),
               "candidate_results_sha256": summary["candidate_results_sha256"], "input_mode": mode,
               "synthetic_test_reads_economic_pnl": False if mode == "SYNTHETIC_VALIDATION" else None}
    (outdir / "receipt.json").write_text(canon(receipt) + "\n")
    return summary

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--input", required=True); ap.add_argument("--output", required=True)
    a = ap.parse_args()
    try:
        print(canon({"status": "PASS", "summary": run(a.input, a.output)}))
    except (ScorerError, OSError, json.JSONDecodeError) as e:
        print(canon({"status": "FAIL_CLOSED", "error": str(e)})); sys.exit(2)

if __name__ == "__main__":
    main()
