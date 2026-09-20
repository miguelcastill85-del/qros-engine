#!/usr/bin/env python3
from dataclasses import asdict
from qros_runtime_enforcement_guard_v1 import *

def s(**kw):
    base=State(invocation_id="T",authority_ref="A")
    return replace(base,**kw)

def ok(cond,msg):
    if not cond: raise AssertionError(msg)

# 1 normal bounded read
p=preflight(s(),"authority_read")
ok(p.allow,"bounded read should pass")

# 2 heavy sync forbidden
p=preflight(s(),"download",expected_bytes=100_000_000,expected_seconds=10,adoptable=False)
ok((not p.allow) and p.reason=="SYNC_HEAVY_REQUIRES_ADOPTABLE_JOB","heavy sync must fail")

# 3 heavy adoptable allowed
p=preflight(s(),"download",expected_bytes=100_000_000,expected_seconds=10,adoptable=True)
ok(p.allow,"heavy adoptable should pass")

# 4 writes require durable intent
p=preflight(s(),"upload",durable_intent=False,adoptable=True)
ok((not p.allow) and p.reason=="WRITE_REQUIRES_DURABLE_INTENT","write without intent must fail")

# 5 one external effect max
st=s(external_effects=1)
p=preflight(st,"external_write",durable_intent=True,adoptable=True)
ok((not p.allow) and p.reason=="SECOND_EXTERNAL_EFFECT_FORBIDDEN","second external effect must fail")

# 6 one expensive unit max even reads
st=s(expensive_units=1)
p=preflight(st,"materialize",adoptable=True)
ok((not p.allow) and p.reason=="SECOND_EXPENSIVE_UNIT_FORBIDDEN","second expensive unit must fail")

# 7 checkpoint barrier
st=s(calls_used=CHECKPOINT_CALL)
p=preflight(st,"metadata_read")
ok((not p.allow) and p.reason=="CHECKPOINT_BARRIER_REQUIRES_PERSIST_AND_EXIT","checkpoint barrier must stop reads")

# 8 timeout forces exit
st=postflight(s(),"status_read",success=False,timeout=True)
ok(st.must_exit and st.blocked_reason=="CONNECTOR_TIMEOUT_CHECKPOINT_EXIT","timeout must force exit")

# 9 no delta repeat forces circuit breaker
st=postflight(s(),"metadata_read",success=True,evidence_hash=None)
st=postflight(st,"metadata_read",success=True,evidence_hash=None)
ok(st.must_exit and st.blocked_reason=="NO_EVIDENCE_DELTA_CIRCUIT_BREAKER","second no-delta must exit")

# 10 durable persist closes
st=postflight(s(),"persist",success=True,durable=True,evidence_hash="x")
ok(st.must_exit and st.terminal_durable and st.checkpoint_persisted,"durable persist must exit")

# 11 pointer must advance and pin receipt
old={"current_blocker":"CARRIER","scientific_state":"PREREGISTERED_NO_RESULTS",
     "economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"new_ga1_authorized":False,"group12_opened":False}
new={**old,"current_blocker":"CLOUD_RUNTIME","resolved_blocker_receipt_sha":"abc"}
ok(validate_pointer_advance(old,new,resolved_receipt_sha="abc")==[],"valid pointer advance rejected")

# 12 stale pointer rejected
bad={**old,"resolved_blocker_receipt_sha":"abc"}
ok("STALE_BLOCKER_NOT_ADVANCED" in validate_pointer_advance(old,bad,resolved_receipt_sha="abc"),"stale blocker not detected")

# 13 scientific drift rejected
bad={**new,"scientific_state":"APPROVED_FINAL"}
ok("SCIENTIFIC_STATE_DRIFT" in validate_pointer_advance(old,bad,resolved_receipt_sha="abc"),"scientific drift not detected")

# 14 forbidden boundary rejected
bad={**new,"holdout_open":True}
ok(any(x.startswith("FORBIDDEN_BOUNDARY_OPEN") for x in validate_pointer_advance(old,bad,resolved_receipt_sha="abc")),"boundary drift not detected")

# 15 terminal durable forbids diagnostics
p=preflight(s(terminal_durable=True),"search")
ok((not p.allow) and p.reason=="TERMINAL_DURABLE_REQUIRES_EXIT","terminal durable must forbid search")

# 16 hard cap
p=preflight(s(calls_used=HARD_CAP_CALLS),"persist")
ok((not p.allow) and p.reason=="HARD_CAP_REACHED","hard cap must stop")

print("PASS_16_OF_16")
