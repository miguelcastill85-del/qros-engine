#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

SAFE_ACTIONS = {
    'ADVANCE_FROM_TERMINAL_PASS',
    'PERSIST_TERMINAL_FAIL_CLOSED',
    'VALIDATE_EXISTING_OUTPUTS',
    'STATUS_ONCE_CURRENT_CLAIM',
    'FENCED_RUNTIME_CUTOVER',
    'PRESERVE_FOREIGN_CLAIM_FAIL_CLOSED',
    'DIRECT_MATERIALIZE_BY_LOCATOR',
    'FETCH_EXACT_BLOBS_VIA_CONNECTOR',
    'LAUNCH_NONBLOCKING_EXACTLY_ONCE',
    'SWITCH_ROUTE_CIRCUIT_BREAKER',
    'PERSIST_CHECKPOINT_BUDGET_BARRIER',
    'PERSIST_BLOCKED_BY_INFRASTRUCTURE',
    'MINIMIZE_PAYLOAD_AND_RETRY_ONCE',
    'REFRESH_AND_CAS_RECONCILE',
    'QUARANTINE_PARTIAL_AND_RECOVER',
}
FORBIDDEN_ACTIONS = {'WAIT','SLEEP','POLL_LOOP','RELAUNCH_BLIND','BROAD_SEARCH','SYNC_HEAVY'}

@dataclass(frozen=True)
class Snapshot:
    authority_ok: bool = True
    terminal: Optional[str] = None  # PASS / FAIL / None
    current_runtime_claim: bool = False
    foreign_runtime_claim: bool = False
    economic_unit: bool = False
    fenced_migration_active: bool = True
    outputs_exact_present: bool = False
    partial_output_present: bool = False
    direct_locator_available: bool = False
    connector_blob_available: bool = True
    inputs_ready: bool = True
    safety_block_last_write: bool = False
    cas_conflict: bool = False
    route_failed: bool = False
    alternate_route_available: bool = True
    no_progress_repeats: int = 0
    external_calls: int = 0
    checkpoint_call: int = 6
    hard_cap_calls: int = 8
    expensive_unit_open: bool = False
    launch_requested: bool = False
    duplicate_attempt_requested: bool = False

@dataclass(frozen=True)
class Decision:
    action: str
    durable_required: bool
    reason: str
    expensive_start_allowed: bool = False


def decide(s: Snapshot) -> Decision:
    if s.external_calls >= s.checkpoint_call:
        return Decision('PERSIST_CHECKPOINT_BUDGET_BARRIER', True, 'CALL_BUDGET_CHECKPOINT_BARRIER')
    if not s.authority_ok:
        return Decision('PERSIST_BLOCKED_BY_INFRASTRUCTURE', True, 'AUTHORITY_NOT_RECONCILED')
    if s.terminal == 'PASS':
        return Decision('ADVANCE_FROM_TERMINAL_PASS', True, 'TERMINAL_PASS_AUTHORITATIVE')
    if s.terminal == 'FAIL':
        return Decision('PERSIST_TERMINAL_FAIL_CLOSED', True, 'TERMINAL_FAIL_AUTHORITATIVE')
    if s.cas_conflict:
        return Decision('REFRESH_AND_CAS_RECONCILE', True, 'CAS_CONFLICT_NO_OVERWRITE')
    if s.safety_block_last_write:
        return Decision('MINIMIZE_PAYLOAD_AND_RETRY_ONCE', True, 'CONNECTOR_SAFETY_BLOCK_REFERENCE_ONLY_RETRY')
    if s.no_progress_repeats >= 2 or (s.route_failed and s.alternate_route_available):
        return Decision('SWITCH_ROUTE_CIRCUIT_BREAKER', True, 'NO_EVIDENCE_DELTA_OR_ROUTE_FAILURE')
    if s.partial_output_present and not s.outputs_exact_present:
        return Decision('QUARANTINE_PARTIAL_AND_RECOVER', True, 'PARTIAL_OUTPUT_NOT_SCIENTIFIC_RESULT')
    if s.outputs_exact_present:
        return Decision('VALIDATE_EXISTING_OUTPUTS', True, 'ARTIFACT_FIRST_RESUMPTION')
    if s.current_runtime_claim:
        return Decision('STATUS_ONCE_CURRENT_CLAIM', True, 'ADOPT_CURRENT_ATTEMPT_NO_POLL')
    if s.foreign_runtime_claim:
        if (not s.economic_unit) and s.fenced_migration_active:
            return Decision('FENCED_RUNTIME_CUTOVER', True, 'FOREIGN_RUNTIME_NON_ECONOMIC_FENCED_MIGRATION')
        return Decision('PRESERVE_FOREIGN_CLAIM_FAIL_CLOSED', True, 'FOREIGN_RUNTIME_NO_SAFE_CUTOVER')
    if not s.inputs_ready:
        if s.direct_locator_available:
            return Decision('DIRECT_MATERIALIZE_BY_LOCATOR', True, 'MANIFEST_FIRST_DIRECT_RECOVERY')
        if s.connector_blob_available:
            return Decision('FETCH_EXACT_BLOBS_VIA_CONNECTOR', True, 'EXACT_CONNECTOR_FETCH_NO_LOCAL_NETWORK_DEPENDENCY')
        return Decision('PERSIST_BLOCKED_BY_INFRASTRUCTURE', True, 'NO_RECOVERABLE_INPUT_ROUTE')
    if s.duplicate_attempt_requested:
        return Decision('PERSIST_BLOCKED_BY_INFRASTRUCTURE', True, 'DUPLICATE_ATTEMPT_FORBIDDEN')
    if s.expensive_unit_open:
        return Decision('STATUS_ONCE_CURRENT_CLAIM', True, 'ONE_EXPENSIVE_UNIT_OPEN')
    if s.launch_requested or s.inputs_ready:
        return Decision('LAUNCH_NONBLOCKING_EXACTLY_ONCE', True, 'READY_NONBLOCKING_LAUNCH', True)
    return Decision('PERSIST_BLOCKED_BY_INFRASTRUCTURE', True, 'NO_ADMISSIBLE_ROUTE')


def validate_decision(s: Snapshot, d: Decision) -> list[str]:
    e=[]
    if d.action not in SAFE_ACTIONS: e.append('UNSAFE_OR_UNKNOWN_ACTION')
    if d.action in FORBIDDEN_ACTIONS: e.append('FORBIDDEN_WAIT_ACTION')
    if not d.durable_required: e.append('NON_DURABLE_DECISION')
    if d.expensive_start_allowed and s.expensive_unit_open: e.append('SECOND_EXPENSIVE_UNIT')
    if d.action == 'LAUNCH_NONBLOCKING_EXACTLY_ONCE' and s.duplicate_attempt_requested: e.append('DUPLICATE_LAUNCH')
    if d.action == 'FENCED_RUNTIME_CUTOVER' and (s.economic_unit or not s.fenced_migration_active): e.append('ILLEGAL_CUTOVER')
    if s.external_calls >= s.checkpoint_call and d.action != 'PERSIST_CHECKPOINT_BUDGET_BARRIER': e.append('BUDGET_BARRIER_BYPASSED')
    return e


def progress_fingerprint(state: dict) -> tuple:
    keys=('authority_blob','checkpoint_blob','unit_id','unit_state','attempt','lease_epoch','artifact_root','next_action')
    return tuple(state.get(k) for k in keys)


def evidence_delta(before: dict, after: dict) -> bool:
    return progress_fingerprint(before) != progress_fingerprint(after)


def classify_repeat(before: dict, after: dict, repeat_count: int) -> str:
    if evidence_delta(before, after): return 'PROGRESS'
    if repeat_count >= 1: return 'CIRCUIT_BREAKER'
    return 'ONE_RECHECK_ALLOWED'
