#!/usr/bin/env python3
from qros_anti_freeze_kernel_v1 import Snapshot, decide, validate_decision, FORBIDDEN_ACTIONS

SCENARIOS = {
 'runtime_migration_mid_job': [
   Snapshot(foreign_runtime_claim=True, inputs_ready=False, direct_locator_available=True),
   Snapshot(inputs_ready=False, direct_locator_available=True),
   Snapshot(inputs_ready=True),
   Snapshot(current_runtime_claim=True),
   Snapshot(terminal='PASS'),
 ],
 'sync_timeout_left_partial': [
   Snapshot(partial_output_present=True, inputs_ready=False, direct_locator_available=True),
   Snapshot(inputs_ready=False,direct_locator_available=True),
   Snapshot(inputs_ready=True),
   Snapshot(current_runtime_claim=True),
   Snapshot(terminal='PASS'),
 ],
 'local_git_network_denied': [
   Snapshot(route_failed=True,alternate_route_available=True,inputs_ready=False,connector_blob_available=True),
   Snapshot(inputs_ready=False,direct_locator_available=False,connector_blob_available=True),
   Snapshot(inputs_ready=True),
   Snapshot(terminal='PASS'),
 ],
 'connector_safety_block_then_reference_retry': [
   Snapshot(safety_block_last_write=True),
   Snapshot(cas_conflict=True),
   Snapshot(terminal='PASS'),
 ],
 'repeated_no_delta': [
   Snapshot(no_progress_repeats=2),
   Snapshot(inputs_ready=False,direct_locator_available=True),
   Snapshot(inputs_ready=True),
   Snapshot(terminal='PASS'),
 ],
 'stale_epoch_economic': [
   Snapshot(foreign_runtime_claim=True,economic_unit=True),
 ],
 'artifact_exists_after_controller_loss': [
   Snapshot(outputs_exact_present=True,foreign_runtime_claim=True),
   Snapshot(terminal='PASS'),
 ],
 'corrupt_partial_never_promotes': [
   Snapshot(partial_output_present=True),
   Snapshot(inputs_ready=False,direct_locator_available=True),
 ],
 'call_budget_exhaustion': [
   Snapshot(external_calls=6,current_runtime_claim=True),
 ],
 'duplicate_attempt_request': [
   Snapshot(duplicate_attempt_requested=True),
 ],
 'authority_drift': [
   Snapshot(authority_ok=False),
 ],
 'one_expensive_unit_only': [
   Snapshot(expensive_unit_open=True),
 ],
}

allowed_first = {
 'runtime_migration_mid_job':'FENCED_RUNTIME_CUTOVER',
 'sync_timeout_left_partial':'QUARANTINE_PARTIAL_AND_RECOVER',
 'local_git_network_denied':'SWITCH_ROUTE_CIRCUIT_BREAKER',
 'connector_safety_block_then_reference_retry':'MINIMIZE_PAYLOAD_AND_RETRY_ONCE',
 'repeated_no_delta':'SWITCH_ROUTE_CIRCUIT_BREAKER',
 'stale_epoch_economic':'PRESERVE_FOREIGN_CLAIM_FAIL_CLOSED',
 'artifact_exists_after_controller_loss':'VALIDATE_EXISTING_OUTPUTS',
 'corrupt_partial_never_promotes':'QUARANTINE_PARTIAL_AND_RECOVER',
 'call_budget_exhaustion':'PERSIST_CHECKPOINT_BUDGET_BARRIER',
 'duplicate_attempt_request':'PERSIST_BLOCKED_BY_INFRASTRUCTURE',
 'authority_drift':'PERSIST_BLOCKED_BY_INFRASTRUCTURE',
 'one_expensive_unit_only':'STATUS_ONCE_CURRENT_CLAIM',
}

steps=0
for name, seq in SCENARIOS.items():
    actions=[]
    for s in seq:
        d=decide(s); errs=validate_decision(s,d)
        assert not errs,(name,d,errs)
        assert d.action not in FORBIDDEN_ACTIONS,(name,d)
        assert d.durable_required,(name,d)
        actions.append(d.action); steps+=1
    assert actions[0] == allowed_first[name], (name,actions[0],allowed_first[name])
    if name in {'runtime_migration_mid_job','sync_timeout_left_partial','local_git_network_denied','connector_safety_block_then_reference_retry','repeated_no_delta','artifact_exists_after_controller_loss'}:
        assert actions[-1]=='ADVANCE_FROM_TERMINAL_PASS',(name,actions)
    print(name, ' -> '.join(actions))
print(f'PASS scenarios={len(SCENARIOS)} steps={steps}')
