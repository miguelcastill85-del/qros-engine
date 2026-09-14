#!/usr/bin/env python3
import argparse, hashlib, json, math, sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

EXPECTED_CONTRACT = "bc7f859c31f7de0584b8abecbe22641fdac2ceab"
EXPECTED_MULTIPLICITY = "bc5ce2b52ca5734328283fb3c1d67ee1d93905c1"
EXPECTED_CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
EMPTY_MASK = hashlib.sha256(b"").hexdigest()

class OracleFailure(Exception):
    pass

def dump(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def ds(v):
    if v is None: return None
    d = v if isinstance(v, Decimal) else Decimal(v)
    if not d.is_finite(): raise OracleFailure("NONFINITE_DECIMAL")
    s = format(d, "f")
    if "." in s: s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s

def to_decimal(x):
    try: d = Decimal(str(x))
    except (InvalidOperation, TypeError, ValueError): raise OracleFailure("INVALID_R")
    if not d.is_finite(): raise OracleFailure("NONFINITE_R")
    return d

def load_manifest(root):
    m = json.loads((root / "manifest.json").read_text())
    fields = {"schema","mode","campaign","asset","side","timeframe","shard_id","first_gate_order",
              "expected_distinct_mask_classes","per_shard_q_exact","multiplicity_contract_git_blob_sha1",
              "semantic_class_root_sha256","alias_root_sha256","scorer_contract_git_blob_sha1"}
    if not fields.issubset(m): raise OracleFailure("MANIFEST_FIELD_MISSING")
    if m["campaign"] != EXPECTED_CAMPAIGN: raise OracleFailure("CAMPAIGN_MISMATCH")
    if m["per_shard_q_exact"] != "1/1200": raise OracleFailure("Q_MISMATCH")
    if m["multiplicity_contract_git_blob_sha1"] != EXPECTED_MULTIPLICITY: raise OracleFailure("MULTIPLICITY_BLOB_MISMATCH")
    if m["scorer_contract_git_blob_sha1"] != EXPECTED_CONTRACT: raise OracleFailure("SCORER_CONTRACT_BLOB_MISMATCH")
    if m["mode"] == "SYNTHETIC_VALIDATION":
        if m.get("synthetic_fixture") is not True: raise OracleFailure("SYNTHETIC_FLAG_REQUIRED")
    elif m["mode"] == "PRODUCTION":
        er = m.get("trade_by_trade_execution_receipt")
        if m.get("execution_parity_pass") is not True: raise OracleFailure("EXECUTION_PARITY_REQUIRED")
        if not isinstance(er, dict) or not er.get("path") or not er.get("sha256"): raise OracleFailure("EXECUTION_RECEIPT_REQUIRED")
        if m.get("economic_exposure_authorized") is not True: raise OracleFailure("ECONOMIC_AUTHORIZATION_REQUIRED")
    else: raise OracleFailure("MODE_INVALID")
    return m

def load_dates(root):
    a = json.loads((root / "date_axis.json").read_text())
    if not isinstance(a, list) or not a or a != sorted(a) or len(a) != len(set(a)): raise OracleFailure("DATE_AXIS_NOT_SORTED_UNIQUE")
    for x in a:
        try: date.fromisoformat(x)
        except Exception: raise OracleFailure("DATE_AXIS_INVALID")
    return a

def nw(values, ntrades):
    n = len(values)
    if ntrades < 30 or n == 0: return None, 1.0, 0
    mu = math.fsum(values) / n
    lag = min(n - 1, math.floor(4 * ((n / 100.0) ** (2.0 / 9.0))))
    centered = [v - mu for v in values]
    covariance = []
    for h in range(lag + 1):
        products = [centered[i] * centered[i-h] for i in range(h, n)]
        covariance.append(math.fsum(products) / n)
    terms = [covariance[0]]
    for h in range(1, lag + 1):
        terms.append(2.0 * (1.0 - h / (lag + 1.0)) * covariance[h])
    longvar = math.fsum(terms)
    stderr = math.sqrt(max(longvar, 0.0) / n)
    if not math.isfinite(stderr) or stderr <= 0.0: return None, 1.0, lag
    stat = mu / stderr
    prob = 0.5 * math.erfc(stat / math.sqrt(2.0))
    if prob < 0.0: prob = 0.0
    if prob > 1.0: prob = 1.0
    return stat, prob, lag

def extra_metrics(axis, daily, net, count):
    cumulative = Decimal(0); high = Decimal(0); ddmax = Decimal(0)
    uwdays = 0; uwrun = 0; uwmax = 0
    annual = {}; monthly = {}
    for key, ret in zip(axis, daily):
        annual[key[:4]] = annual.get(key[:4], Decimal(0)) + ret
        monthly[key[:7]] = monthly.get(key[:7], Decimal(0)) + ret
        cumulative += ret
        if cumulative > high:
            high = cumulative; uwrun = 0
        elif cumulative < high:
            uwdays += 1; uwrun += 1; uwmax = max(uwmax, uwrun); ddmax = max(ddmax, high-cumulative)
        else: uwrun = 0
    flt = [float(v) for v in daily]; N = len(flt); avg = math.fsum(flt)/N if N else 0.0
    sharpe = None
    if N >= 2:
        variance = math.fsum((v-avg)*(v-avg) for v in flt)/(N-1)
        sd = math.sqrt(variance)
        if math.isfinite(sd) and sd > 0: sharpe = math.sqrt(252.0)*avg/sd
    down = math.sqrt(math.fsum((min(v,0.0))**2 for v in flt)/N) if N else 0.0
    sortino = math.sqrt(252.0)*avg/down if math.isfinite(down) and down > 0 else None
    def c(metric):
        denominator = sum(abs(x) for x in metric.values())
        return None if denominator == 0 else max(abs(x) for x in metric.values()) / denominator
    cy = c(annual); cm = c(monthly)
    if ddmax > 0: recovery = {"value": ds(net/ddmax), "state":"FINITE"}
    elif net > 0: recovery = {"value":None,"state":"POS_INF"}
    else: recovery = {"value":None,"state":"UNDEFINED"}
    years = max(1, len(annual))
    return {"DD_R":ds(ddmax),"recovery":recovery,"Sharpe":None if sharpe is None else repr(sharpe),
            "Sortino":None if sortino is None else repr(sortino),
            "year_concentration":None if cy is None else ds(cy),"month_concentration":None if cm is None else ds(cm),
            "year_net_R":{k:ds(v) for k,v in sorted(annual.items())},
            "month_net_R":{k:ds(v) for k,v in sorted(monthly.items())},
            "underwater":{"underwater_days":uwdays,"max_consecutive_underwater_days":uwmax},
            "frequency":{"trades_per_eligible_day":ds(Decimal(count)/Decimal(N)) if N else None,
                         "trades_per_distinct_DEV_year":ds(Decimal(count)/Decimal(years))}}

def candidate(row, axis, allowed):
    need = {"canonical_signal_config_id","event_mask_sha256","eligible_event_count","zero_event","trades"}
    if not need.issubset(row): raise OracleFailure("CANDIDATE_FIELD_MISSING")
    cid = row["canonical_signal_config_id"]; mask = row["event_mask_sha256"]
    if not isinstance(cid,str) or not cid: raise OracleFailure("CANDIDATE_ID_INVALID")
    if not isinstance(mask,str) or len(mask)!=64: raise OracleFailure("MASK_SHA_INVALID")
    try: int(mask,16)
    except Exception: raise OracleFailure("MASK_SHA_INVALID")
    events = row["eligible_event_count"]; zero = row["zero_event"]
    if not isinstance(events,int) or events < 0: raise OracleFailure("ELIGIBLE_EVENT_COUNT_INVALID")
    if not isinstance(zero,bool) or not isinstance(row["trades"],list): raise OracleFailure("CANDIDATE_TYPE_INVALID")
    if zero and (events != 0 or mask != EMPTY_MASK or len(row["trades"]) != 0): raise OracleFailure("ZERO_EVENT_INCONSISTENT")
    if not zero and events == 0: raise OracleFailure("NONZERO_EVENT_COUNT_ZERO")
    buckets = {d:Decimal(0) for d in axis}; seen=set(); returns=[]
    for trade in row["trades"]:
        if not isinstance(trade,dict) or not {"trade_id","trading_date","R"}.issubset(trade): raise OracleFailure("TRADE_FIELD_MISSING")
        tid=trade["trade_id"]; d=trade["trading_date"]
        if not isinstance(tid,str) or not tid: raise OracleFailure("TRADE_ID_INVALID")
        if tid in seen: raise OracleFailure("DUPLICATE_TRADE_ID")
        seen.add(tid)
        if d not in allowed: raise OracleFailure("TRADE_DATE_OUTSIDE_AXIS")
        r=to_decimal(trade["R"]); returns.append(r); buckets[d]+=r
    n=len(returns); net=sum(returns,Decimal(0)); positive=sum((v for v in returns if v>0),Decimal(0)); loss=-sum((v for v in returns if v<0),Decimal(0))
    expectation=None if n==0 else net/Decimal(n); win=None if n==0 else Decimal(sum(1 for v in returns if v>0))/Decimal(n)
    if loss>0:
        ratio=positive/loss; pf={"value":ds(ratio),"state":"FINITE"}; pfok=ratio>1
    elif positive>0:
        pf={"value":None,"state":"POS_INF"}; pfok=True
    else:
        pf={"value":None,"state":"UNDEFINED"}; pfok=False
    daily=[buckets[d] for d in axis]
    stat,p,lag=(None,1.0,0) if zero else nw([float(v) for v in daily],n)
    result={"canonical_signal_config_id":cid,"event_mask_sha256":mask,"eligible_event_count":events,"zero_event":zero,
            "trades":n,"net_R":ds(net),"expectancy_R":None if expectation is None else ds(expectation),"PF":pf,
            "win_rate":None if win is None else ds(win),"HAC_t":None if stat is None else repr(stat),"raw_p":repr(p),
            "HAC_lag":lag,"BY_rejected":False,"survives_first_gate":False}
    result.update(extra_metrics(axis,daily,net,n))
    return result,p,(net>0, expectation is not None and expectation>0, pfok)

def apply_by(items):
    m=len(items)
    with localcontext() as ctx:
        ctx.prec=80
        harmonic=Decimal(0)
        for j in range(1,m+1): harmonic += Decimal(1)/Decimal(j)
        idx=list(range(m)); idx.sort(key=lambda i:(items[i][1],items[i][0]["canonical_signal_config_id"]))
        boundary=0
        for rank,i in enumerate(idx,start=1):
            critical=(Decimal(rank)/Decimal(1200))/(Decimal(m)*harmonic)
            if Decimal.from_float(items[i][1]) <= critical: boundary=rank
        selected=set(idx[0:boundary])
    for i,(r,_,gate) in enumerate(items):
        r["BY_rejected"]=i in selected
        r["survives_first_gate"]=bool(i in selected and r["trades"]>=30 and gate[0] and gate[1] and gate[2])
    return boundary,ds(harmonic)

def execute(source,dest):
    source=Path(source); dest=Path(dest); dest.mkdir(parents=True,exist_ok=True)
    manifest=load_manifest(source); axis=load_dates(source); allowed=set(axis)
    items=[]; ids=set(); hashes=set()
    for text in (source/"candidates.jsonl").read_text().splitlines():
        if not text.strip(): continue
        r,p,g=candidate(json.loads(text),axis,allowed)
        if r["canonical_signal_config_id"] in ids: raise OracleFailure("DUPLICATE_CANDIDATE_ID")
        if r["event_mask_sha256"] in hashes: raise OracleFailure("DUPLICATE_MASK_SHA")
        ids.add(r["canonical_signal_config_id"]); hashes.add(r["event_mask_sha256"]); items.append((r,p,g))
    if len(items) != manifest["expected_distinct_mask_classes"]: raise OracleFailure("CANDIDATE_COUNT_MISMATCH")
    k,h=apply_by(items); rows=sorted((x[0] for x in items),key=lambda r:r["canonical_signal_config_id"])
    result=dest/"candidate_results.jsonl"
    result.write_text("".join(dump(r)+"\n" for r in rows))
    survivors=sum(1 for r in rows if r["survives_first_gate"]); mode=manifest["mode"]
    summary={"schema":"QROS_FIRST_GATE_SCORER_SUMMARY_1.0","mode":mode,"candidate_count":len(rows),"BY_k":k,
             "harmonic_c_m":h,"survivor_count":survivors,
             "shard_decision":"SYNTHETIC_NO_ECONOMIC_DECISION" if mode=="SYNTHETIC_VALIDATION" else ("PASS_FIRST_GATE" if survivors else "REJECTED_FIRST_GATE"),
             "candidate_results_sha256":hashlib.sha256(result.read_bytes()).hexdigest(),"economic_decision_authorized":mode=="PRODUCTION"}
    (dest/"summary.json").write_text(dump(summary)+"\n")
    receipt={"schema":"QROS_FIRST_GATE_SCORER_RECEIPT_1.0","implementation":"INDEPENDENT_ORACLE",
             "summary_sha256":hashlib.sha256((dest/"summary.json").read_bytes()).hexdigest(),
             "candidate_results_sha256":summary["candidate_results_sha256"],"input_mode":mode,
             "synthetic_test_reads_economic_pnl":False if mode=="SYNTHETIC_VALIDATION" else None}
    (dest/"receipt.json").write_text(dump(receipt)+"\n")
    return summary

def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    try: print(dump({"status":"PASS","summary":execute(a.input,a.output)}))
    except (OracleFailure,OSError,json.JSONDecodeError) as e:
        print(dump({"status":"FAIL_CLOSED","error":str(e)})); sys.exit(2)
if __name__=="__main__": main()
