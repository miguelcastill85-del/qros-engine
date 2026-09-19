#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os
from pathlib import Path
import qros_fenced_runtime_lease_guard_v2 as fence

SCHEMA="QROS_CWS_REAL_CONTROL_SOAK_DRIVER_1.0"

FORBIDDEN=("economic_pnl_read","holdout_open","ga2_open","new_ga1_authorized","first_gate_execution_authorized","group12_opened")

def load(p): return json.loads(Path(p).read_text())
def dump(p,obj): Path(p).write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def hobj(x): return hashlib.sha256(canonical(x)).hexdigest()
def parse_ts(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(dt.timezone.utc)

def ensure_firewall(obj):
    for k in FORBIDDEN:
        if obj.get(k) is True:
            raise RuntimeError("FORBIDDEN_FLAG:"+k)

def make_cutover(old,auth,runtime_id,issued_at,expires_at):
    ensure_firewall(auth)
    required={
      "status","old_lease_id","old_lease_epoch","old_fence_token",
      "old_epoch_promotion_revoked","scientific_unit_same","new_epoch"
    }
    if required-set(auth): raise RuntimeError("CUTOVER_FIELDS_MISSING")
    if auth["status"]!="AUTHORIZED_MIGRATION_CUTOVER": raise RuntimeError("CUTOVER_NOT_AUTHORIZED")
    if auth["old_lease_id"]!=old["lease_id"] or int(auth["old_lease_epoch"])!=int(old["lease_epoch"]) or auth["old_fence_token"]!=old["fence_token"]:
        raise RuntimeError("CUTOVER_OLD_LEASE_MISMATCH")
    if int(auth["new_epoch"])!=int(old["lease_epoch"])+1: raise RuntimeError("CUTOVER_EPOCH_NOT_MONOTONIC")
    if auth["old_epoch_promotion_revoked"] is not True or auth["scientific_unit_same"] is not True:
        raise RuntimeError("CUTOVER_GUARD")
    new=fence.supersede_for_migration(old,runtime_id,issued_at,expires_at,auth)
    ok,why=fence.validate_lease(new,now=issued_at)
    if not ok: raise RuntimeError("NEW_LEASE_INVALID:"+why)
    receipt={
      "schema":"QROS_CWS_REAL_CONTROL_SOAK_CUTOVER_PASS_1.0",
      "status":"PASS",
      "job_id":new["job_id"],"group_index":new["group_index"],
      "old_lease_epoch":old["lease_epoch"],"new_lease_epoch":new["lease_epoch"],
      "old_lease_id":old["lease_id"],"new_lease_id":new["lease_id"],
      "fence_token":new["fence_token"],"owner_runtime_id":new["owner_runtime_id"],
      "issued_at":issued_at,"expires_at":expires_at,
      "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,
      "new_ga1_authorized":False,"first_gate_execution_authorized":False,"group12_opened":False
    }
    return new,receipt

def prepare_intent(lease,source,capsule,m1,ind,carrier_root,now):
    ok,why=fence.validate_lease(lease,now=now)
    if not ok: raise RuntimeError("LEASE_NOT_CURRENT:"+why)
    if source.get("status")!="PASS" or source.get("verification",{}).get("count_verified")!=9:
        raise RuntimeError("SOURCE_PACKAGE_NOT_PASS")
    if capsule.get("subject",{}).get("structural_group_index")!=11:
        raise RuntimeError("CAPSULE_GROUP")
    if m1.get("status")!="PASS" or ind.get("status")!="PASS":
        raise RuntimeError("CACHE_RECEIPT_NOT_PASS")
    pre=capsule["preconditions"]
    if m1["dev"]["sha256"]!=pre["dev_prefix_sha256"]: raise RuntimeError("DEV_IDENTITY")
    if m1["m1"]["content_sha256"]!=pre["bar_M1_content_sha256"]: raise RuntimeError("M1_IDENTITY")
    if ind["m1_indicators"]["content_root_sha256"]!=pre["indicator_M1_content_root_sha256"]: raise RuntimeError("INDICATOR_IDENTITY")
    paths={
      "dev":Path(carrier_root)/"QROS_XAUUSD_DEV_2018_2019_PACKED17.bin",
      "m1":Path(carrier_root)/"XAUUSD_M1_BID_BARS.npy",
      "indicators":Path(carrier_root)/"XAUUSD_M1_INDICATORS.npz"
    }
    present={k:p.exists() for k,p in paths.items()}
    all_present=all(present.values())
    intent={
      "schema":"QROS_CWS_GROUP11_EXECUTION_INTENT_1.0",
      "status":"READY_TO_SPAWN" if all_present else "CARRIER_MATERIALIZATION_REQUIRED",
      "job_id":lease["job_id"],"group_index":11,
      "lease_epoch":lease["lease_epoch"],"lease_id":lease["lease_id"],"fence_token":lease["fence_token"],
      "owner_runtime_id":lease["owner_runtime_id"],
      "source_package_status":"PASS_9_OF_9",
      "dev_sha256":pre["dev_prefix_sha256"],
      "m1_content_sha256":pre["bar_M1_content_sha256"],
      "indicator_content_root_sha256":pre["indicator_M1_content_root_sha256"],
      "carriers_present":present,
      "spawn_authorized":bool(all_present),
      "carrier_materialization_required":not all_present,
      "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,
      "new_ga1_authorized":False,"first_gate_execution_authorized":False,"group12_opened":False
    }
    ensure_firewall(intent)
    terminal={
      "schema":"QROS_CWS_REAL_CONTROL_PLANE_SOAK_FINAL_1.0",
      "status":"PASS",
      "lease_epoch":lease["lease_epoch"],
      "intent_status":intent["status"],
      "spawn_started":False,
      "safe_stop_reason":"CARRIERS_ABSENT_ON_GITHUB_RUNNER" if not all_present else "SPAWN_EXPLICITLY_OUT_OF_SCOPE_FOR_VALIDATION",
      "manual_interventions":0,
      "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,
      "new_ga1_authorized":False,"first_gate_execution_authorized":False,"group12_opened":False
    }
    return intent,terminal

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("cutover")
    for a in ["old_lease","cutover_auth","runtime_id","issued_at","expires_at","out_lease","out_receipt"]:
        p.add_argument("--"+a.replace("_","-"),required=True)
    p=sub.add_parser("intent")
    for a in ["lease","source","capsule","m1","ind","carrier_root","now","out_intent","out_terminal"]:
        p.add_argument("--"+a.replace("_","-"),required=True)
    a=ap.parse_args()
    if a.cmd=="cutover":
        new,rec=make_cutover(load(a.old_lease),load(a.cutover_auth),a.runtime_id,a.issued_at,a.expires_at)
        dump(a.out_lease,new); dump(a.out_receipt,rec)
        print(json.dumps({"schema":SCHEMA,"status":"PASS","stage":"CUTOVER","new_epoch":new["lease_epoch"],"fence_token":new["fence_token"]},sort_keys=True))
    else:
        intent,term=prepare_intent(load(a.lease),load(a.source),load(a.capsule),load(a.m1),load(a.ind),a.carrier_root,a.now)
        dump(a.out_intent,intent); dump(a.out_terminal,term)
        print(json.dumps({"schema":SCHEMA,"status":"PASS","stage":"INTENT","intent_status":intent["status"],"spawn_authorized":intent["spawn_authorized"]},sort_keys=True))
if __name__=="__main__": main()
