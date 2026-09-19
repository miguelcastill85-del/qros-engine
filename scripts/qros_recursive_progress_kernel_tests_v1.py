#!/usr/bin/env python3
from itertools import product
from qros_recursive_progress_kernel_v1 import *

named=[]
def ck(name,s,o,action):
    t=compile_transition(s,o)
    assert t.action==action,(name,t.action,action)
    assert t.action not in FORBIDDEN
    assert t.durable_before_effect
    if t.effect: assert t.idempotency_key
    named.append(name)

S=lambda **kw: State(campaign_id="C",unit_id="U",**kw)
O=lambda **kw: Observation(**kw)
ck("budget barrier",S(call_count=6),O(authority_ok=False),"CHECKPOINT_EXIT")
ck("terminal pass",S(),O(terminal_receipt="PASS"),"ADVANCE_UNIT")
ck("terminal fail",S(),O(terminal_receipt="FAIL"),"FAIL_CLOSED")
ck("authority block",S(),O(authority_ok=False),"BLOCK_DURABLE")
ck("artifact reuse",S(),O(exact_outputs_present=True,exact_outputs_valid=True,evidence_hash="x"),"VALIDATE_EXISTING_OUTPUTS")
ck("artifact quarantine",S(),O(exact_outputs_present=True,exact_outputs_valid=False,evidence_hash="x"),"QUARANTINE_PARTIAL")
ck("locator",S(),O(direct_locator_available=True),"MATERIALIZE_DIRECT_LOCATOR")
ck("connector",S(),O(connector_blobs_available=True),"FETCH_EXACT_CONNECTOR_BLOBS")
ck("no route",S(),O(),"BLOCK_DURABLE")
ck("launch",S(),O(inputs_ready=True,current_runtime_id="R"),"LAUNCH_EXACTLY_ONCE")
ck("live claim exits",S(open_effect_id="e"),O(same_runtime_claim_live=True),"CHECKPOINT_EXIT")
ck("foreign cutover",S(open_effect_id="e"),O(foreign_runtime_claim=True,current_runtime_id="R"),"FENCED_CUTOVER")
ck("economic foreign blocks",S(open_effect_id="e",open_effect_economic=True),O(foreign_runtime_claim=True),"BLOCK_DURABLE")
ck("proven death",S(open_effect_id="e",attempt=1),O(proven_dead=True,current_runtime_id="R"),"LAUNCH_EXACTLY_ONCE")
ck("unknown open effect exits",S(open_effect_id="e"),O(),"CHECKPOINT_EXIT")
ck("cas",S(),O(cas_conflict=True),"REFRESH_THEN_CAS")
ck("route fail",S(),O(route_failed=True),"SWITCH_ROUTE")
ck("second no delta",S(no_delta_streak=1),O(),"SWITCH_ROUTE")
ck("second no delta open",S(no_delta_streak=1,open_effect_id="e"),O(),"CHECKPOINT_EXIT")

s=S();o=O(inputs_ready=True,current_runtime_id="R")
a=compile_transition(s,o);b=compile_transition(s,o)
assert a==b and a.idempotency_key==b.idempotency_key
named.append("duplicate invocation deterministic")

ev=[];prev=None
for i in range(50):
    e=append_event(prev,i,"TICK",{"i":i});ev.append(e);prev=e["event_hash"]
assert verify_event_chain(ev)
bad=[dict(x) for x in ev]; bad[17]=dict(bad[17]); bad[17]["payload"]={"i":999}
assert not verify_event_chain(bad)
named += ["event chain valid","event chain tamper detected"]

fields=["authority_ok","exact_outputs_present","exact_outputs_valid","inputs_ready","direct_locator_available","connector_blobs_available","same_runtime_claim_live","foreign_runtime_claim","proven_dead","fencing_supported","cas_conflict","route_failed","connector_write_blocked"]
count=0
for bits in product([False,True], repeat=len(fields)):
    kw=dict(zip(fields,bits))
    for terminal in (None,"PASS","FAIL"):
      for open_effect in (None,"effect"):
       for economic in (False,True):
        for streak in (0,1):
         for calls in (0,6):
          s=S(open_effect_id=open_effect,open_effect_economic=economic,no_delta_streak=streak,call_count=calls)
          o=O(terminal_receipt=terminal,current_runtime_id="R",**kw)
          t=compile_transition(s,o)
          assert t.action not in FORBIDDEN,(s,o,t)
          assert t.durable_before_effect
          if calls>=6: assert t.action=="CHECKPOINT_EXIT"
          if t.effect: assert t.idempotency_key
          if o.exact_outputs_present and o.authority_ok and calls<6 and terminal is None and not o.cas_conflict and not o.connector_write_blocked and not o.route_failed and streak==0:
              assert t.action in {"VALIDATE_EXISTING_OUTPUTS","QUARANTINE_PARTIAL"}
          if open_effect and economic and o.foreign_runtime_claim and o.authority_ok and calls<6 and terminal is None and not o.cas_conflict and not o.connector_write_blocked and not o.route_failed and streak==0 and not o.exact_outputs_present:
              assert t.action!="FENCED_CUTOVER"
          count+=1
print(f"PASS named={len(named)} exhaustive={count} total={len(named)+count}")
