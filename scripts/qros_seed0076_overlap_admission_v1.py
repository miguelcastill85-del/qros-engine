#!/usr/bin/env python3
"""Frozen Seed0076 same-candidate admission, SYNTHETIC ONLY.

Inputs: actual normalized_trades.jsonl and synthetic W09B receipt bytes.
The frozen overlap policy orders trigger, actual entry, event_id, scenario_id.
This module never grants production scoring, never infers trading_date/session,
and never treats a missing artifact as an economic rejection.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
OVERLAP_POLICY_SHA1 = "690e0b82233b22fb800693741eede53ce223f5c2"
NORMALIZER_CONTRACT_SHA1 = "5d7006c5b54d4647113c7caab5107e8c9229d2bf"
NORMALIZER_CORE_SHA1 = "7774745805999db2faa59ff5f318c1e3072eeea5"
MODE = "SYNTHETIC_VALIDATION"
SCHEMA = "QROS_SEED0076_OVERLAP_ADMISSION_SYNTHETIC_1.0"
HASH64 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED = ("scenario_id", "canonical_signal_config_id", "event_mask_sha256", "event_id", "side",
            "signal_observable_timestamp", "entry_trigger_timestamp", "entry_timestamp", "entry_price",
            "stop_price", "exit_timestamp", "exit_price", "R", "exit_reason")


class AdmissionError(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise AdmissionError(reason)


def canonical(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def regular_child(root, name):
    demand(isinstance(name, str) and name and "\\" not in name and not Path(name).is_absolute(), "PATH_INVALID")
    demand(".." not in Path(name).parts, "PATH_TRAVERSAL")
    base = Path(root).resolve(strict=True)
    try:
        child = (base / name).resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise AdmissionError("INPUT_MISSING")
    demand(child.is_relative_to(base) and child.is_file(), "INPUT_ESCAPES_ROOT")
    return child


def decimal(value, field):
    demand(not isinstance(value, bool), "INVALID_" + field)
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AdmissionError("INVALID_" + field)
    demand(v.is_finite(), "NONFINITE_" + field)
    return v


def timestamp(row, key):
    v = row[key]
    demand(isinstance(v, int) and not isinstance(v, bool), "TIMESTAMP_INVALID")
    return v


def validate_event(row):
    demand(isinstance(row, dict) and all(k in row for k in REQUIRED), "NORMALIZED_TRADE_FIELDS_MISSING")
    for k in ("scenario_id", "canonical_signal_config_id", "event_id"):
        demand(isinstance(row[k], str) and bool(row[k].strip()), "EVENT_IDENTITY_INVALID")
    demand(isinstance(row["event_mask_sha256"], str) and HASH64.fullmatch(row["event_mask_sha256"]), "MASK_HASH_INVALID")
    side = row["side"]
    demand(side in ("BUY", "SELL"), "SIDE_INVALID")
    signal, trigger, entry, exit_ = (timestamp(row, k) for k in ("signal_observable_timestamp", "entry_trigger_timestamp", "entry_timestamp", "exit_timestamp"))
    demand(signal <= trigger <= entry <= exit_, "NONCAUSAL_EVENT_TIMESTAMPS")
    entry_px, stop, exit_px = (decimal(row[k], k.upper()) for k in ("entry_price", "stop_price", "exit_price"))
    r = decimal(row["R"], "R")
    demand(entry_px > 0 and stop > 0 and exit_px > 0, "NONPOSITIVE_PRICE")
    demand((stop < entry_px) if side == "BUY" else (stop > entry_px), "INVALID_STOP_DIRECTION")
    reason = row["exit_reason"]
    demand(reason in ("STOP", "SAME_DAY"), "EXIT_REASON_INVALID")
    crossed = (exit_px <= stop) if side == "BUY" else (exit_px >= stop)
    demand((reason == "STOP") == crossed, "EXIT_REASON_PRICE_CONFLICT")
    with localcontext() as context:
        context.prec = 50
        expected_r = (exit_px-entry_px)/(entry_px-stop) if side == "BUY" else (entry_px-exit_px)/(stop-entry_px)
        demand(abs(r-expected_r) <= Decimal("1e-24") * max(Decimal(1), abs(expected_r)), "R_PRICE_CONFLICT")
    return row


def sort_key(row):
    return (row["entry_trigger_timestamp"], row["entry_timestamp"], row["event_id"], row["scenario_id"])


def admit_normalized_events(rows):
    """Pure policy implementation; no datetime/price inference and no shared candidate risk."""
    demand(isinstance(rows, list) and bool(rows), "NO_NORMALIZED_EVENTS")
    candidates = defaultdict(list)
    scenario_ids, event_ids, mask_to_candidate, candidate_meta = set(), set(), {}, {}
    for raw in rows:
        row = validate_event(raw)
        sid, cid, eid, mh = row["scenario_id"], row["canonical_signal_config_id"], row["event_id"], row["event_mask_sha256"]
        demand(sid not in scenario_ids, "DUPLICATE_SCENARIO_ID")
        demand((cid, eid) not in event_ids, "DUPLICATE_CANDIDATE_EVENT_ID")
        scenario_ids.add(sid); event_ids.add((cid, eid))
        meta = (mh, row["side"])
        demand(cid not in candidate_meta or candidate_meta[cid] == meta, "CANDIDATE_IDENTITY_DRIFT")
        demand(mh not in mask_to_candidate or mask_to_candidate[mh] == cid, "DUPLICATE_MASK_ACROSS_CANDIDATES")
        candidate_meta[cid] = meta; mask_to_candidate[mh] = cid
        candidates[cid].append(row)
    admitted, rejected = [], []
    for cid in sorted(candidates):
        ordered = sorted(candidates[cid], key=sort_key)
        current = None
        # Multiple independent windows at one trigger cannot legitimately disagree
        # about the first executable quote under one frozen carrier.
        for i in range(1, len(ordered)):
            prev, nxt = ordered[i-1], ordered[i]
            if prev["entry_trigger_timestamp"] == nxt["entry_trigger_timestamp"]:
                demand(prev["entry_timestamp"] == nxt["entry_timestamp"], "SAME_TRIGGER_ENTRY_INCONSISTENT")
        for event in ordered:
            if current is None or event["entry_trigger_timestamp"] > current["exit_timestamp"]:
                current = event
                admitted.append(event)
            else:
                # A supposedly later signal filling before the selected earlier
                # signal betrays incompatible truncated tick windows. Quarantine.
                demand(event["entry_timestamp"] >= current["entry_timestamp"], "ENTRY_CHRONOLOGY_INVERSION")
                rejected.append({"canonical_signal_config_id":cid,"event_id":event["event_id"],
                                 "scenario_id":event["scenario_id"],"entry_trigger_timestamp":event["entry_trigger_timestamp"],
                                 "entry_timestamp":event["entry_timestamp"],"reason":"ACTIVE_THROUGH_EXIT_INCLUSIVE",
                                 "active_event_id":current["event_id"],"active_exit_timestamp":current["exit_timestamp"]})
    return admitted, rejected


def validate_source_manifest(root):
    manifest_path = regular_child(root, "manifest.json")
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    demand(isinstance(m, dict), "MANIFEST_INVALID")
    demand(m.get("schema") == SCHEMA and m.get("campaign") == CAMPAIGN, "MANIFEST_SCHEMA_OR_CAMPAIGN_DRIFT")
    demand(m.get("mode") == MODE and m.get("synthetic_fixture") is True, "PRODUCTION_OR_UNTRUSTED_INPUT_FORBIDDEN")
    demand(m.get("economic_pnl_read") is False and m.get("economic_decision_authorized") is False, "ECONOMIC_FIREWALL_DRIFT")
    demand(m.get("overlap_policy_git_blob_sha1") == OVERLAP_POLICY_SHA1, "OVERLAP_POLICY_DRIFT")
    demand(m.get("normalizer_contract_git_blob_sha1") == NORMALIZER_CONTRACT_SHA1, "NORMALIZER_CONTRACT_DRIFT")
    demand(m.get("normalizer_core_git_blob_sha1") == NORMALIZER_CORE_SHA1, "NORMALIZER_CORE_DRIFT")
    trades = regular_child(root, "normalized_trades.jsonl")
    demand(sha256(trades) == m.get("normalized_trades_sha256"), "NORMALIZED_TRADES_BYTES_DRIFT")
    ref = m.get("normalizer_receipt")
    demand(isinstance(ref, dict) and isinstance(ref.get("sha256"), str), "NORMALIZER_RECEIPT_REF_MISSING")
    receipt_path = regular_child(root, ref.get("path"))
    demand(sha256(receipt_path) == ref["sha256"], "NORMALIZER_RECEIPT_BYTES_DRIFT")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    demand(receipt.get("status") == "PASS" and receipt.get("implementation") == "PRIMARY" and
           receipt.get("synthetic_only") is True and receipt.get("economic_pnl_read") is False and
           receipt.get("normalized_trades_sha256") == m["normalized_trades_sha256"], "NORMALIZER_RECEIPT_SEMANTICS_DRIFT")
    rows = []
    with trades.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return m, rows


def write_synced(path, data):
    with Path(path).open("wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def run(input_dir, output_dir):
    root = Path(input_dir).resolve(strict=True)
    manifest, rows = validate_source_manifest(root)
    admitted, rejected = admit_normalized_events(rows)
    parent = Path(output_dir).absolute().parent
    demand(parent.is_dir(), "OUTPUT_PARENT_MISSING")
    dest = parent / Path(output_dir).name
    body = {"admitted_normalized_trades.jsonl": "".join(canonical(x)+"\n" for x in admitted).encode(),
            "rejected_events.jsonl": "".join(canonical(x)+"\n" for x in rejected).encode()}
    sums = {k: hashlib.sha256(v).hexdigest() for k,v in body.items()}
    summary = {"schema":"QROS_SEED0076_OVERLAP_SYNTHETIC_SUMMARY_1.0","mode":MODE,"overlap_policy_git_blob_sha1":OVERLAP_POLICY_SHA1,
               "normalized_trades_sha256":manifest["normalized_trades_sha256"],"input_event_count":len(rows),
               "admitted_count":len(admitted),"rejected_count":len(rejected),"artifacts_sha256":sums,
               "trade_by_trade_production_parity":"NOT_PROVED","economic_decision_authorized":False,"production_grant":False}
    body["summary.json"] = (canonical(summary)+"\n").encode()
    receipt = {"schema":"QROS_SEED0076_OVERLAP_SYNTHETIC_RECEIPT_1.0","status":"PASS_SYNTHETIC_ONLY",
               "summary_sha256":hashlib.sha256(body["summary.json"]).hexdigest(),"economic_pnl_read":False,
               "scientific_state":"PREREGISTERED_NO_RESULTS","production_grant":False}
    body["receipt.json"] = (canonical(receipt)+"\n").encode()
    if dest.exists():
        demand(dest.is_dir() and (dest/"summary.json").is_file() and (dest/"receipt.json").is_file(), "OUTPUT_UNCOMMITTED")
        for name, content in body.items():
            demand((dest/name).is_file() and hashlib.sha256((dest/name).read_bytes()).digest() == hashlib.sha256(content).digest(), "NON_IDEMPOTENT_REPLAY")
        return {**summary, "idempotent_replay":True}
    tmp = Path(tempfile.mkdtemp(prefix="."+dest.name+".staging.",dir=parent))
    try:
        for name, content in body.items():
            write_synced(tmp/name, content)
        os.replace(tmp, dest)  # one directory commit: no partial scientific promotion
        if hasattr(os, "O_DIRECTORY"):
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
    except BaseException:
        # Staged files are not scientific results; cleanup only this fresh staging dir.
        if tmp.exists(): shutil.rmtree(tmp)
        raise
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(canonical({"status":"PASS_SYNTHETIC_ONLY","summary":run(args.input,args.output)}))
    except (AdmissionError,OSError,ValueError,json.JSONDecodeError) as exc:
        print(canonical({"status":"FAIL_CLOSED","error":str(exc)}))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
