#!/usr/bin/env python3
from __future__ import annotations
import copy,datetime as dt,hashlib,json,random,tempfile
from pathlib import Path
import qros_fenced_runtime_lease_guard_v2 as fence
from qros_cws_real_control_soak_driver_v1 import make_cutover,prepare_intent

def base():
    issued="2026-09-19T14:28:33Z"; expires="2026-09-19T16:28:33Z"
    old=fence.new_lease("JOB",11,2,"runtime-old",issued,expires)
    auth={"status":"AUTHORIZED_MIGRATION_CUTOVER","old_lease_id":old["lease_id"],"old_lease_epoch":2,"old_fence_token":old["fence_token"],"old_epoch_promotion_revoked":True,"scientific_unit_same":True,"new_epoch":3,
          "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"new_ga1_authorized":False,"first_gate_execution_authorized":False,"group12_opened":False}
    return old,auth

def main():
    old,auth=base()
    new,rec=make_cutover(old,auth,"gha:123:1","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z")
    assert new["lease_epoch"]==3 and rec["status"]=="PASS"
    ok,why=fence.validate_lease(new,now="2026-09-19T21:00:01Z"); assert ok,why
    for mut in ("old_lease_id","old_fence_token","new_epoch"):
        o,a=base(); b=copy.deepcopy(a)
        b[mut]=("bad" if mut!="new_epoch" else 4)
        try: make_cutover(o,b,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z"); raise AssertionError(mut)
        except RuntimeError: pass
    o,a=base();a["economic_pnl_read"]=True
    try: make_cutover(o,a,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z"); raise AssertionError("firewall")
    except RuntimeError: pass

    source={"status":"PASS","verification":{"count_verified":9}}
    capsule={"subject":{"structural_group_index":11},"preconditions":{"dev_prefix_sha256":"d"*64,"bar_M1_content_sha256":"b"*64,"indicator_M1_content_root_sha256":"i"*64}}
    m1={"status":"PASS","dev":{"sha256":"d"*64},"m1":{"content_sha256":"b"*64}}
    ind={"status":"PASS","m1_indicators":{"content_root_sha256":"i"*64}}
    with tempfile.TemporaryDirectory() as td:
        intent,term=prepare_intent(new,source,capsule,m1,ind,td,"2026-09-19T21:00:02Z","gha:stage2")
        assert intent["status"]=="CARRIER_MATERIALIZATION_REQUIRED" and intent["spawn_authorized"] is False
        assert term["status"]=="PASS" and term["spawn_started"] is False
    rng=random.Random(20260919); rejected=0
    for _ in range(100000):
        o,a=base()
        mode=rng.randrange(6)
        if mode==0:a["old_lease_id"]="x"
        elif mode==1:a["old_fence_token"]="x"
        elif mode==2:a["new_epoch"]=4
        elif mode==3:a["scientific_unit_same"]=False
        elif mode==4:a["old_epoch_promotion_revoked"]=False
        else:a["holdout_open"]=True
        try: make_cutover(o,a,"gha","2026-09-19T21:00:00Z","2026-09-19T23:00:00Z")
        except RuntimeError: rejected+=1
    assert rejected==100000
    print(json.dumps({"status":"PASS","adversarial_cases":100000,"rejected":rejected,"unsafe_accepts":0},sort_keys=True))
if __name__=="__main__": main()
