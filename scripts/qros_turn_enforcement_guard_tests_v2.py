#!/usr/bin/env python3
from dataclasses import replace
from qros_turn_enforcement_guard_v2 import *

def S(**kw): return replace(State(invocation_id="T",authority_ref="A"),**kw)
def ok(v,m):
    if not v: raise AssertionError(m)

ok(preflight(S(),AUTHORITY_TX).allow,"01")
ok(preflight(S(),ACTION_TX).reason=="ACTION_REQUIRES_AUTHORITY","02")
s=postflight(S(),AUTHORITY_TX,success=True)
ok(s.phase=="ACTION" and s.authority_done,"03")
ok(not preflight(s,AUTHORITY_TX).allow,"04")
ok(preflight(s,ACTION_TX,capability="LOCAL",attempt_fingerprint="p1").allow,"05")
ok(preflight(s,ACTION_TX,expected_bytes=50_000_001).reason=="SYNC_HEAVY_ACTION_FORBIDDEN","06")
f=postflight(s,ACTION_TX,success=False,capability="LOCAL",attempt_fingerprint="p1")
ok(f.must_exit and f.phase=="PERSIST","07")
ok(preflight(f,ACTION_TX).reason=="MUST_EXIT_ONLY_PERSIST_ALLOWED","08")
t=postflight(s,ACTION_TX,success=False,timeout=True,capability="LOCAL",attempt_fingerprint="p1")
ok(t.blocked_reason=="INFRASTRUCTURE_FAILURE_PERSIST_AND_EXIT","09")
ok(preflight(t,PERSIST_TX).allow,"10")
ok(not preflight(t,ACTION_TX).allow,"11")
ok("LOCAL" in t.failed_capabilities,"12")
ok(preflight(replace(s,probed_capabilities=("LOCAL",)),ACTION_TX,capability="LOCAL").reason=="ONE_PROBE_PER_CAPABILITY","13")
ok(preflight(replace(s,failed_capabilities=("LOCAL",)),ACTION_TX,capability="LOCAL").reason=="FAILED_CAPABILITY_LEASE_FORBIDS_RETRY","14")
ok(preflight(replace(s,attempt_fingerprints=("same",)),ACTION_TX,attempt_fingerprint="same").reason=="DUPLICATE_ATTEMPT_FINGERPRINT","15")
p=postflight(t,PERSIST_TX,success=True,durable=True)
ok(p.phase=="EXIT" and p.checkpoint_persisted and p.must_exit,"16")
ok(not preflight(p,PERSIST_TX).allow,"17")
ok(preflight(replace(s,logical_transactions=3,phase="PERSIST"),PERSIST_TX).reason=="TURN_TRANSACTION_BUDGET_EXHAUSTED","18")
ok(preflight(replace(s,platform_calls=4),ACTION_TX).reason=="PLATFORM_CALL_BUDGET_EXHAUSTED","19")
old={"scientific_state":"PREREGISTERED_NO_RESULTS","economic_pnl_read":False,"holdout_open":False,
     "ga2_open":False,"new_ga1_authorized":True,"authorization_scope":"EXACTLY_SHARD09_NQX_BUY_M15",
     "first_gate_execution_authorized":False,"subject":{"asset":"NQX","side":"BUY","timeframe":"M15"}}
ok(validate_control_plane_pointer_preservation(old,dict(old))==[],"20")
bad=dict(old);bad["new_ga1_authorized"]=False
ok("SCIENTIFIC_BOUNDARY_DRIFT:new_ga1_authorized" in validate_control_plane_pointer_preservation(old,bad),"21")
bad=dict(old);bad["authorization_scope"]="ANY"
ok("SCIENTIFIC_BOUNDARY_DRIFT:authorization_scope" in validate_control_plane_pointer_preservation(old,bad),"22")
bad=dict(old);bad["subject"]={"asset":"XAUUSD"}
ok("SCIENTIFIC_SUBJECT_DRIFT" in validate_control_plane_pointer_preservation(old,bad),"23")
e=postflight(s,ACTION_TX,success=False,infrastructure_error=True,capability="FILES",attempt_fingerprint="x")
ok(e.must_exit and e.phase=="PERSIST","24")
print("PASS_24_OF_24")
