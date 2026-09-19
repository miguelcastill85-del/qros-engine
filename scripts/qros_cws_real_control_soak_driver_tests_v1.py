#!/usr/bin/env python3
from __future__ import annotations
import copy,json,random,tempfile
from pathlib import Path
import qros_fenced_runtime_lease_guard_v2 as fence
from qros_cws_real_control_soak_driver_v1 import make_cutover,prepare_intent

def base():
    old=fence.new_lease("JOB",11,2,"runtime-old","2026-09-19T14:28:33Z","2026-09-19T16:28:33Z")
    auth={"status":"AUTHORIZED_MIGRATION_CUTOVER","old_lease_id":old["lease_id"],"old_lease_epoch":2,"old_fence_token":old["fence_token"],
          "old_epoch_promotion_revoked":True,"scientific_unit_same":True,"new_epoch":3,
          "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"new_ga1_authorized":False,"first_gate_execution_authorized":False,"group12_opened":False}
    return old,auth

def fixtures():
    source={"status":"PASS","verification":{"count_verified":9}}
    capsule={"subject":{"structural_group_index":11},"preconditions":{"dev_prefix_sha256":"d"*64,"bar_M1_content_sha256":"b"*64,"indicator_M1_content_root_sha256":"1"*64}}
    m1={"status":"PASS","dev":{"sha256":"d"*64},"m1":{"content_sha256":"b"*64}}
    ind={"status":"PASS","m1_indicators":{"content_root_sha256":"1"*64}}
    return source,capsule,m1,ind

def main():
    old,auth=base()
    new,rec=make_cutover(old,auth,"gha:123:1","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z")
    assert new["lease_epoch"]==3 and rec["status"]=="PASS"
    ok,why=fence.validate_lease(new,now="2026-09-19T21:00:01Z"); assert ok,why
    for mut in ("old_lease_id","old_fence_token","new_epoch"):
        o,a=base(); b=copy.deepcopy(a); b[mut]=("bad" if mut!="new_epoch" else 4)
        try: make_cutover(o,b,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z"); raise AssertionError(mut)
        except RuntimeError: pass
    o,a=base();a["economic_pnl_read"]=True
    try: make_cutover(o,a,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z"); raise AssertionError("firewall")
    except RuntimeError: pass

    source,capsule,m1,ind=fixtures()
    with tempfile.TemporaryDirectory() as td:
        # carriers absent + owner mismatch
        intent,term=prepare_intent(new,source,capsule,m1,ind,td,"2026-09-19T21:00:02Z","gha:stage1")
        assert intent["status"]=="CARRIER_MATERIALIZATION_REQUIRED"
        assert intent["spawn_authorized"] is False and intent["carrier_materialization_required"] is True and intent["runtime_cutover_required"] is True
        assert len(term["safe_stop_reasons"])==2
        # carriers present + owner mismatch
        for fn in ("QROS_XAUUSD_DEV_2018_2019_PACKED17.bin","XAUUSD_M1_BID_BARS.npy","XAUUSD_M1_INDICATORS.npz"):
            Path(td,fn).write_bytes(b"x")
        intent2,term2=prepare_intent(new,source,capsule,m1,ind,td,"2026-09-19T21:00:03Z","gha:stage1")
        assert intent2["status"]=="RUNTIME_CUTOVER_REQUIRED"
        assert intent2["spawn_authorized"] is False and intent2["carrier_materialization_required"] is False and intent2["runtime_cutover_required"] is True
        # carriers present + owner match
        intent3,term3=prepare_intent(new,source,capsule,m1,ind,td,"2026-09-19T21:00:04Z",new["owner_runtime_id"])
        assert intent3["status"]=="READY_TO_SPAWN"
        assert intent3["spawn_authorized"] is True and intent3["carrier_materialization_required"] is False and intent3["runtime_cutover_required"] is False
        assert term3["spawn_started"] is False

    rng=random.Random(20260919); rejected=0
    for _ in range(100000):
        o,a=base(); mode=rng.randrange(6)
        if mode==0:a["old_lease_id"]="x"
        elif mode==1:a["old_fence_token"]="x"
        elif mode==2:a["new_epoch"]=4
        elif mode==3:a["scientific_unit_same"]=False
        elif mode==4:a["old_epoch_promotion_revoked"]=False
        else:a["holdout_open"]=True
        try: make_cutover(o,a,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z")
        except RuntimeError: rejected+=1
    assert rejected==100000
    print(json.dumps({"status":"PASS","adversarial_cases":100000,"rejected":rejected,"unsafe_accepts":0,"intent_matrix_cases":3},sort_keys=True))
if __name__=="__main__": main()
