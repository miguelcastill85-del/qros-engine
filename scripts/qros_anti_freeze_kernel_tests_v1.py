#!/usr/bin/env python3
from itertools import product
from qros_anti_freeze_kernel_v1 import Snapshot, decide, validate_decision, classify_repeat, SAFE_ACTIONS

NAMED=[]
def check(name, snap, expected):
    d=decide(snap); errs=validate_decision(snap,d)
    assert not errs,(name,d,errs)
    assert d.action==expected,(name,d.action,expected)
    NAMED.append(name)

check('terminal pass advances', Snapshot(terminal='PASS'), 'ADVANCE_FROM_TERMINAL_PASS')
check('terminal fail closes', Snapshot(terminal='FAIL'), 'PERSIST_TERMINAL_FAIL_CLOSED')
check('current claim one status', Snapshot(current_runtime_claim=True), 'STATUS_ONCE_CURRENT_CLAIM')
check('foreign non-economic fenced migration', Snapshot(foreign_runtime_claim=True), 'FENCED_RUNTIME_CUTOVER')
check('foreign economic preserves', Snapshot(foreign_runtime_claim=True,economic_unit=True), 'PRESERVE_FOREIGN_CLAIM_FAIL_CLOSED')
check('exact outputs first', Snapshot(outputs_exact_present=True,current_runtime_claim=True), 'VALIDATE_EXISTING_OUTPUTS')
check('partial quarantine', Snapshot(partial_output_present=True), 'QUARANTINE_PARTIAL_AND_RECOVER')
check('direct locator before connector', Snapshot(inputs_ready=False,direct_locator_available=True), 'DIRECT_MATERIALIZE_BY_LOCATOR')
check('connector exact fetch', Snapshot(inputs_ready=False,direct_locator_available=False,connector_blob_available=True), 'FETCH_EXACT_BLOBS_VIA_CONNECTOR')
check('missing all routes blocks durably', Snapshot(inputs_ready=False,direct_locator_available=False,connector_blob_available=False), 'PERSIST_BLOCKED_BY_INFRASTRUCTURE')
check('route failure switches', Snapshot(route_failed=True,alternate_route_available=True), 'SWITCH_ROUTE_CIRCUIT_BREAKER')
check('two no-progress observations trip breaker', Snapshot(no_progress_repeats=2), 'SWITCH_ROUTE_CIRCUIT_BREAKER')
check('CAS conflict reconciles', Snapshot(cas_conflict=True), 'REFRESH_AND_CAS_RECONCILE')
check('connector safety block minimizes payload', Snapshot(safety_block_last_write=True), 'MINIMIZE_PAYLOAD_AND_RETRY_ONCE')
check('budget barrier at call 6', Snapshot(external_calls=6), 'PERSIST_CHECKPOINT_BUDGET_BARRIER')
check('ready launches nonblocking', Snapshot(), 'LAUNCH_NONBLOCKING_EXACTLY_ONCE')
check('duplicate launch forbidden', Snapshot(duplicate_attempt_requested=True), 'PERSIST_BLOCKED_BY_INFRASTRUCTURE')
check('authority drift blocks', Snapshot(authority_ok=False), 'PERSIST_BLOCKED_BY_INFRASTRUCTURE')
check('open expensive unit cannot start another', Snapshot(expensive_unit_open=True), 'STATUS_ONCE_CURRENT_CLAIM')

b={'authority_blob':'a','checkpoint_blob':'c','unit_id':'u','unit_state':'RUNNING','attempt':1,'lease_epoch':1,'artifact_root':None,'next_action':'status'}
a=dict(b)
assert classify_repeat(b,a,0)=='ONE_RECHECK_ALLOWED'
assert classify_repeat(b,a,1)=='CIRCUIT_BREAKER'
a['unit_state']='PASS'
assert classify_repeat(b,a,1)=='PROGRESS'
NAMED += ['first no-delta permits one recheck','second no-delta circuit breaks','state change proves progress']

fields=['authority_ok','current_runtime_claim','foreign_runtime_claim','economic_unit','fenced_migration_active','outputs_exact_present','partial_output_present','direct_locator_available','connector_blob_available','inputs_ready','safety_block_last_write','cas_conflict','route_failed','alternate_route_available']
count=0
for bits in product([False,True], repeat=len(fields)):
    kw=dict(zip(fields,bits))
    for repeat in (0,2):
      for calls in (0,6):
        s=Snapshot(**kw,no_progress_repeats=repeat,external_calls=calls)
        d=decide(s); errs=validate_decision(s,d)
        assert not errs,(kw,repeat,calls,d,errs)
        assert d.action in SAFE_ACTIONS
        assert d.action not in {'WAIT','SLEEP','POLL_LOOP','SYNC_HEAVY','RELAUNCH_BLIND','BROAD_SEARCH'}
        count+=1
print(f'PASS named={len(NAMED)} exhaustive={count} total_assertion_states={len(NAMED)+count}')
