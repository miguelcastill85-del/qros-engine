#!/usr/bin/env python3
"""Exact GitHub-pinned W09B primary/oracle + frozen overlap policy synthetic seam.

Never reads market data. It cannot infer a real broker timezone nor grant production.
The frozen 14-field normalizer output is unchanged; provenance is a separate sidecar.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import date, datetime, timezone

import qros_first_gate_execution_normalizer_primary_v2 as primary
import qros_first_gate_execution_normalizer_oracle_v2 as oracle
import qros_seed0076_overlap_admission_v1 as overlap

CONTRACT = "5d7006c5b54d4647113c7caab5107e8c9229d2bf"
PRIMARY_SHA1 = "7774745805999db2faa59ff5f318c1e3072eeea5"
ORACLE_SHA1 = "347ff69ab1ffd85f99a0905701b47659ea324444"
OVERLAP_SHA1 = "690e0b82233b22fb800693741eede53ce223f5c2"
FIXTURE_ONLY = "SYNTHETIC_VALIDATION"


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_blob(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()


def verify_exact_source():
    root=Path(__file__).resolve().parent
    expected={
      "qros_first_gate_execution_normalizer_primary_v1.py":PRIMARY_SHA1,
      "qros_first_gate_execution_normalizer_oracle_v1.py":ORACLE_SHA1,
      "qros_first_gate_execution_normalizer_primary_v2.py":"323937c4c591c4531d3ebde2d20fa695e48a5067",
      "qros_first_gate_execution_normalizer_oracle_v2.py":"9581a725d4f2c0d590763fe97743dd8c21948b8f",
      "qros_seed0076_overlap_admission_v1.py":"da32c686301aa880587582b81d203e53546cc283",
    }
    for name,pin in expected.items():
        if git_blob(root/name)!=pin:raise ValueError("EXECUTED_SOURCE_BLOB_DRIFT_"+name)
    return expected


def validate_synthetic_fixture(scenarios):
    if not isinstance(scenarios,list) or not scenarios:raise ValueError("RAW_FIXTURE_MISSING")
    for row in scenarios:
        a=row["event_anchor"]
        for field in ("signal_observable_timestamp","entry_trigger_timestamp","session_close_timestamp"):
            if type(a[field]) is not int:raise ValueError("BOOL_OR_INVALID_ANCHOR_TIMESTAMP_"+field)
        if a["signal_observable_timestamp"]>a["entry_trigger_timestamp"] or a["entry_trigger_timestamp"]>a["session_close_timestamp"]:
            raise ValueError("NONCAUSAL_RAW_ANCHOR")
        for tick in row["ticks"]:
            for field in ("timestamp","carrier_sequence"):
                if type(tick[field]) is not int:raise ValueError("BOOL_OR_INVALID_TICK_"+field)


def ticks():
    # Canonical shared carrier; equal timestamps have distinct physical sequences.
    quotes = [(8,"100","100.2"),(10,"100.5","100.7"),(11,"101","101.2"),
              (15,"99","99.2"),(20,"103","103.2"),(25,"105","105.2"),
              (30,"104","104.2"),(35,"98","98.2"),(40,"100","100.2"),
              (50,"100","100.2"),(50,"100.8","101"),(60,"102","102.2"),
              (70,"101","101.2"),(80,"100","100.2"),(100,"99","99.2"),
              (101,"10","10.2")]  # Beyond frozen close: must never be read.
    return [{"carrier_sequence":n,"timestamp":ts,"bid":bid,"ask":ask}
            for n,(ts,bid,ask) in enumerate(quotes,1)]


def event(sid,cid="B",side="BUY",trigger=10,stop="98.5",close=100,obs=None,tape=None):
    if obs is None: obs=trigger-1
    return {"scenario_id":sid,
            "event_anchor":{"canonical_signal_config_id":cid,
              "event_mask_sha256":sha(cid.encode()),"event_id":sid,"side":side,
              "signal_observable_timestamp":obs,"entry_trigger_timestamp":trigger,
              "opposite_fractal_stop":stop,"session_close_timestamp":close,
              "synthetic_broker_trading_date":"2025-03-09", "synthetic_broker_session_id":"BROKER_CLOCK_NOT_VERIFIED"},
            "ticks":copy.deepcopy(tape if tape is not None else ticks())}


def make_fixture():
    tape=ticks()
    cases=[
        event("B0",tape=tape),             # First tie; stop loss gap ts35.
        event("B1",tape=tape),             # Same trigger, overlapping B0.
        event("B2",trigger=20,tape=tape), # Active B0 => rejected.
        event("B3",trigger=35,stop="95",tape=tape), # Equal exit time => rejected.
        event("B4",trigger=40,stop="90",tape=tape), # After exit => admitted same day.
        event("B5",trigger=60,stop="90",tape=tape), # Active B4 => rejected.
        event("C0",cid="C",trigger=20,stop="90",tape=tape), # Independent candidate.
        event("S0",cid="S",side="SELL",trigger=20,stop="104",tape=tape), # Adverse gap.
        event("S1",cid="S",side="SELL",trigger=25,stop="110",tape=tape),# Equal exit => rejected.
        event("S2",cid="S",side="SELL",trigger=30,stop="110",tape=tape),# New SELL, same day.
        event("E0",cid="E",trigger=50,stop="95",tape=tape), # Equal timestamp first physical tick.
        event("E1",cid="E",trigger=50,stop="95",tape=tape), # Equal trigger lexical tie.
        event("E2",cid="E",trigger=60,stop="95",tape=tape), # Active E0 => reject.
    ]
    return cases


def create_input(root, scenarios):
    root.mkdir(parents=True,exist_ok=True)
    manifest={"schema":"QROS_FIRST_GATE_EXECUTION_SYNTHETIC_FIXTURE_1.0",
        "mode":FIXTURE_ONLY,"campaign":overlap.CAMPAIGN,
        "execution_contract_git_blob_sha1":CONTRACT,"synthetic_fixture":True}
    (root/"manifest.json").write_text(canon(manifest)+"\n")
    (root/"scenarios.jsonl").write_text("".join(canon(s)+"\n" for s in scenarios))


def fetch_rows(folder):
    return [json.loads(line) for line in (Path(folder)/"normalized_trades.jsonl").read_text().splitlines() if line]


def _real_price(val):
    x=Decimal(str(val))
    if not x.is_finite() or x<=0: raise ValueError("SOURCE_PRICE_INVALID")
    return x


def provenance_sidecar(trades, scenarios):
    """Independent raw-tick replay; no W09B internals or adapter admission reuse."""
    byid={s["scenario_id"]:s for s in scenarios}
    if len(byid)!=len(scenarios): raise ValueError("DUPLICATE_RAW_SCENARIO")
    output=[]
    for tr in trades:
        s=byid[tr["scenario_id"]]; a=s["event_anchor"]
        validate_synthetic_fixture([s])
        seq=None; previous_ts=None; parsed=[]
        for q in s["ticks"]:
            sn,ts=q["carrier_sequence"],q["timestamp"]
            if type(sn)!=int or type(ts)!=int or (seq is not None and sn<=seq) or (previous_ts is not None and ts<previous_ts):
                raise ValueError("SOURCE_TICK_CHRONOLOGY_INVALID")
            bid,ask=_real_price(q["bid"]),_real_price(q["ask"])
            if bid>ask: raise ValueError("SOURCE_CROSSED_QUOTE")
            parsed.append((sn,ts,bid,ask));seq,previous_ts=sn,ts
        trigger=a["entry_trigger_timestamp"];close=a["session_close_timestamp"];side=a["side"]
        entry=next((i for i,(_,ts,_,_) in enumerate(parsed) if trigger<=ts<=close),None)
        if entry is None: raise ValueError("SOURCE_NO_ENTRY")
        seq0,ts0,bid0,ask0=parsed[entry]
        price0=ask0 if side=="BUY" else bid0
        stop=_real_price(a["opposite_fractal_stop"])
        if (side=="BUY" and not stop<price0) or (side=="SELL" and not stop>price0):
            raise ValueError("SOURCE_STOP_DIRECTION")
        eligible=[q for q in parsed[entry:] if q[1]<=close]
        stopped=[]
        for q in eligible:
            px=q[2] if side=="BUY" else q[3]
            if (px<=stop if side=="BUY" else px>=stop):
                stopped.append(q);break
        chosen=stopped[0] if stopped else eligible[-1]
        seq1,ts1,bid1,ask1=chosen
        px1=bid1 if side=="BUY" else ask1
        why="STOP" if stopped else "SAME_DAY"
        checks={"entry_timestamp":ts0,"exit_timestamp":ts1,"entry_price":price0,
                "exit_price":px1,"stop_price":stop,"exit_reason":why}
        for k,v in checks.items():
            if k.endswith("_price"):
                if _real_price(tr[k])!=v:raise ValueError("NORMALIZER_PRICE_MISMATCH_"+k)
            elif tr[k]!=v:raise ValueError("NORMALIZER_FIELD_MISMATCH_"+k)
        if ts1>close:raise ValueError("EXIT_AFTER_SESSION_CLOSE")
        if a["signal_observable_timestamp"]==ts0:
            source_avail_seq=a.get("synthetic_signal_available_after_sequence")
            if type(source_avail_seq) is not int:
                raise ValueError("SIGNAL_SEQUENCE_REQUIRED_FOR_TIMESTAMP_TIE")
            if source_avail_seq>=seq0:
                raise ValueError("SIGNAL_AVAILABLE_AFTER_OR_AT_ENTRY_QUOTE")
        if not isinstance(a.get("synthetic_broker_trading_date"),str) or not isinstance(a.get("synthetic_broker_session_id"),str) or not a["synthetic_broker_session_id"]:
            raise ValueError("SYNTHETIC_BROKER_CALENDAR_UNBOUND")
        try:
            if date.fromisoformat(a["synthetic_broker_trading_date"]).isoformat()!=a["synthetic_broker_trading_date"]:
                raise ValueError("SYNTHETIC_BROKER_DATE_INVALID")
        except ValueError:
            raise ValueError("SYNTHETIC_BROKER_DATE_INVALID")
        output.append({"scenario_id":tr["scenario_id"],
                       "source_scenario_sha256":sha((canon(s)+"\n").encode()),
                       "entry_carrier_sequence":seq0,"exit_carrier_sequence":seq1,
                       "session_close_timestamp":close,
                       "synthetic_broker_trading_date":a["synthetic_broker_trading_date"],
                       "synthetic_broker_session_id":a["synthetic_broker_session_id"],
                       "provenance_kind":"SYNTHETIC_ONLY_NO_BROKER_ASSERTION",
                       "signal_available_after_sequence":a.get("synthetic_signal_available_after_sequence")})
    return sorted(output,key=lambda x:x["scenario_id"])


def run(root):
    root=Path(root); verify_exact_source(); scenarios=make_fixture()
    validate_synthetic_fixture(scenarios)
    create_input(root/"input",scenarios)
    summary_p=primary.core.run(root/"input",root/"primary")
    summary_o=oracle.core.evaluate(root/"input",root/"oracle")
    pb=(root/"primary"/"normalized_trades.jsonl").read_bytes()
    ob=(root/"oracle"/"normalized_trades.jsonl").read_bytes()
    if pb!=ob:raise ValueError("W09B_TRADE_BY_TRADE_PARITY_FAILED")
    if summary_p!=summary_o:raise ValueError("W09B_SUMMARY_PARITY_FAILED")
    rows=fetch_rows(root/"primary")
    sidecar=provenance_sidecar(rows,scenarios)
    source=root/"adapter_input";source.mkdir(parents=True,exist_ok=True)
    (source/"normalized_trades.jsonl").write_bytes(pb)
    receipt_p=root/"primary"/"receipt.json"
    (source/"receipt.json").write_bytes(receipt_p.read_bytes())
    m={"schema":overlap.SCHEMA,"campaign":overlap.CAMPAIGN,"mode":overlap.MODE,
       "synthetic_fixture":True,"economic_pnl_read":False,"economic_decision_authorized":False,
       "overlap_policy_git_blob_sha1":OVERLAP_SHA1,
       "normalizer_contract_git_blob_sha1":CONTRACT,
       "normalizer_core_git_blob_sha1":PRIMARY_SHA1,
       "normalized_trades_sha256":sha(pb),"normalizer_receipt":{"path":"receipt.json","sha256":sha(receipt_p.read_bytes())}}
    (source/"manifest.json").write_text(canon(m)+"\n")
    overlap_summary=overlap.run(source,root/"admission")
    admitted, rejected=overlap.admit_normalized_events(rows)
    if len(admitted)!=overlap_summary["admitted_count"] or len(rejected)!=overlap_summary["rejected_count"]:
        raise ValueError("ADMISSION_READBACK_DRIFT")
    (root/"synthetic_provenance_sidecar.jsonl").write_text("".join(canon(x)+"\n" for x in sidecar))
    # Verify the *separately implemented* upstream normalizer outputs cannot be forged
    # by replacing just its receipt after the byte-parity check.
    receipt_o=json.loads((root/"oracle"/"receipt.json").read_text())
    receipt_p_json=json.loads(receipt_p.read_text())
    if receipt_p_json["normalized_trades_sha256"] != receipt_o["normalized_trades_sha256"]:
        raise ValueError("RECEIPT_PARITY_FAIL")
    report={"schema":"QROS_SEED0076_W09B_OVERLAP_SYNTHETIC_SEAM_RECEIPT_1.0",
      "status":"PASS_SYNTHETIC_ONLY","source_blobs":{"primary_v1":PRIMARY_SHA1,"oracle_v1":ORACLE_SHA1,
         "primary_v2":"323937c4c591c4531d3ebde2d20fa695e48a5067","oracle_v2":"9581a725d4f2c0d590763fe97743dd8c21948b8f",
         "normalizer_contract":CONTRACT,"overlap_policy":OVERLAP_SHA1},
      "scenario_count":len(rows),"normalizer_trade_by_trade_14_field_exact":True,
      "normalizer_trades_sha256":sha(pb),"synthetic_provenance_sidecar_sha256":sha((root/"synthetic_provenance_sidecar.jsonl").read_bytes()),
      "admitted_count":len(admitted),"rejected_count":len(rejected),
      "admitted_scenario_ids":[x["scenario_id"] for x in admitted],
      "rejected_scenario_ids":[x["scenario_id"] for x in rejected],
      "broker_timezone_real":"NOT_VERIFIED","historical_dev_bytes":"NOT_LOADED",
      "economic_pnl_read":False,"economic_decision_authorized":False,"production_grant":False,
      "true_forward":"NOT_STARTED","holdout_open":False}
    (root/"integration_receipt.json").write_text(canon(report)+"\n")
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);a=p.parse_args()
    print(canon(run(Path(a.output))))
if __name__=="__main__":main()
