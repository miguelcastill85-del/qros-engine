#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict, replace
from typing import Optional

SCHEMA = "QROS_RECURSIVE_PROGRESS_KERNEL_1.0"
STATE_SCHEMA = "QROS_RECURSIVE_PROGRESS_STATE_1.0"
EVENT_SCHEMA = "QROS_RECURSIVE_PROGRESS_EVENT_1.0"
FORBIDDEN = {"WAIT","SLEEP","POLL_LOOP","SYNC_HEAVY","BROAD_SEARCH","BLIND_RELAUNCH","REPEAT_SAME_FAILED_ROUTE","UNBOUNDED_DIAGNOSTIC"}

@dataclass(frozen=True)
class State:
    schema: str = STATE_SCHEMA
    campaign_id: str = "UNSET"
    unit_id: str = "UNSET"
    seq: int = 0
    phase: str = "READY"
    scientific_state: str = "PREREGISTERED_NO_RESULTS"
    attempt: int = 0
    lease_epoch: int = 0
    route_index: int = 0
    no_delta_streak: int = 0
    call_count: int = 0
    checkpoint_call: int = 6
    hard_cap_calls: int = 8
    open_effect_id: Optional[str] = None
    open_effect_action: Optional[str] = None
    open_effect_runtime: Optional[str] = None
    open_effect_economic: bool = False
    last_evidence_hash: Optional[str] = None
    prev_state_hash: Optional[str] = None
    last_action: Optional[str] = None
    blocked_reason: Optional[str] = None

@dataclass(frozen=True)
class Observation:
    authority_ok: bool = True
    terminal_receipt: Optional[str] = None
    exact_outputs_present: bool = False
    exact_outputs_valid: bool = False
    inputs_ready: bool = False
    direct_locator_available: bool = False
    connector_blobs_available: bool = False
    same_runtime_claim_live: bool = False
    foreign_runtime_claim: bool = False
    proven_dead: bool = False
    fencing_supported: bool = True
    cas_conflict: bool = False
    current_runtime_id: Optional[str] = None
    evidence_hash: Optional[str] = None
    route_failed: bool = False
    connector_write_blocked: bool = False

@dataclass(frozen=True)
class Transition:
    action: str
    next_state: State
    durable_before_effect: bool
    effect: bool
    idempotency_key: Optional[str]
    reason: str

def canonical(obj)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def sha256_obj(obj)->str:
    return hashlib.sha256(canonical(obj)).hexdigest()

def state_hash(s:State)->str:
    return sha256_obj(asdict(s))

def evidence_delta(s:State,o:Observation)->bool:
    return o.evidence_hash is not None and o.evidence_hash != s.last_evidence_hash

def effect_id(s:State,action:str)->str:
    return sha256_obj({"schema":SCHEMA,"campaign_id":s.campaign_id,"unit_id":s.unit_id,"seq":s.seq,"state_hash":state_hash(s),"action":action})

def _advance(s:State,**kw)->State:
    base=replace(s,seq=s.seq+1,prev_state_hash=state_hash(s),call_count=s.call_count+1)
    return replace(base,**kw)

def _t(s:State,action:str,reason:str,*,effect=False,**kw)->Transition:
    ns=_advance(s,last_action=action,**kw)
    iid=effect_id(s,action) if effect else None
    return Transition(action,ns,True,effect,iid,reason)

def compile_transition(s:State,o:Observation)->Transition:
    if s.schema != STATE_SCHEMA:
        return _t(s,"FAIL_CLOSED","STATE_SCHEMA_MISMATCH",phase="BLOCKED",blocked_reason="STATE_SCHEMA_MISMATCH")
    if s.call_count >= s.checkpoint_call:
        return _t(s,"CHECKPOINT_EXIT","CHECKPOINT_CALL_BARRIER")
    if not o.authority_ok:
        return _t(s,"BLOCK_DURABLE","AUTHORITY_NOT_RECONCILED",phase="BLOCKED",blocked_reason="AUTHORITY_NOT_RECONCILED")
    delta=evidence_delta(s,o)
    streak=0 if delta else s.no_delta_streak+1
    if o.terminal_receipt=="PASS":
        return _t(s,"ADVANCE_UNIT","AUTHORITATIVE_TERMINAL_PASS",phase="DONE",no_delta_streak=0,last_evidence_hash=o.evidence_hash or s.last_evidence_hash,open_effect_id=None,open_effect_action=None,open_effect_runtime=None)
    if o.terminal_receipt=="FAIL":
        return _t(s,"FAIL_CLOSED","AUTHORITATIVE_TERMINAL_FAIL",phase="BLOCKED",blocked_reason="TERMINAL_FAIL",no_delta_streak=0,last_evidence_hash=o.evidence_hash or s.last_evidence_hash)
    if o.cas_conflict:
        return _t(s,"REFRESH_THEN_CAS","CAS_CONFLICT_REFRESH_REQUIRED",no_delta_streak=streak,last_evidence_hash=o.evidence_hash or s.last_evidence_hash)
    if o.connector_write_blocked or o.route_failed:
        return _t(s,"SWITCH_ROUTE","FAILED_ROUTE_CIRCUIT_BREAKER",route_index=s.route_index+1,no_delta_streak=0)
    if streak>=2:
        if s.open_effect_id:
            return _t(s,"CHECKPOINT_EXIT","NO_DELTA_WITH_OPEN_EFFECT_NO_POLL",no_delta_streak=streak)
        return _t(s,"SWITCH_ROUTE","NO_EVIDENCE_DELTA_CIRCUIT_BREAKER",route_index=s.route_index+1,no_delta_streak=0)
    if o.exact_outputs_present:
        if o.exact_outputs_valid:
            return _t(s,"VALIDATE_EXISTING_OUTPUTS","ARTIFACT_FIRST_REUSE",phase="VALIDATING",no_delta_streak=0,last_evidence_hash=o.evidence_hash or s.last_evidence_hash)
        return _t(s,"QUARANTINE_PARTIAL","OUTPUTS_NOT_EXACT",phase="READY",open_effect_id=None,open_effect_action=None,open_effect_runtime=None,no_delta_streak=0)
    if s.open_effect_id:
        if o.same_runtime_claim_live:
            return _t(s,"CHECKPOINT_EXIT","CURRENT_EFFECT_LIVE_EXIT_NO_POLL",phase="RUNNING",no_delta_streak=streak)
        if o.foreign_runtime_claim:
            if (not s.open_effect_economic) and o.fencing_supported:
                return _t(s,"FENCED_CUTOVER","FOREIGN_RUNTIME_NON_ECONOMIC",effect=True,phase="EFFECT_INTENT",lease_epoch=s.lease_epoch+1,open_effect_id=None,open_effect_action=None,open_effect_runtime=o.current_runtime_id,no_delta_streak=0)
            return _t(s,"BLOCK_DURABLE","FOREIGN_RUNTIME_UNSAFE",phase="BLOCKED",blocked_reason="FOREIGN_RUNTIME_UNSAFE")
        if o.proven_dead:
            action="LAUNCH_EXACTLY_ONCE"; iid=effect_id(s,action)
            ns=_advance(s,last_action=action,phase="EFFECT_INTENT",attempt=s.attempt+1,open_effect_id=iid,open_effect_action=action,open_effect_runtime=o.current_runtime_id,no_delta_streak=0)
            return Transition(action,ns,True,True,iid,"PROVEN_DEATH_NEW_ATTEMPT")
        return _t(s,"CHECKPOINT_EXIT","OPEN_EFFECT_UNKNOWN_EXIT_NO_POLL",no_delta_streak=streak)
    if not o.inputs_ready:
        if o.direct_locator_available:
            action="MATERIALIZE_DIRECT_LOCATOR"; iid=effect_id(s,action)
            ns=_advance(s,last_action=action,phase="EFFECT_INTENT",route_index=1,open_effect_id=iid,open_effect_action=action,open_effect_runtime=o.current_runtime_id,no_delta_streak=0)
            return Transition(action,ns,True,True,iid,"DIRECT_LOCATOR")
        if o.connector_blobs_available:
            action="FETCH_EXACT_CONNECTOR_BLOBS"; iid=effect_id(s,action)
            ns=_advance(s,last_action=action,phase="EFFECT_INTENT",route_index=2,open_effect_id=iid,open_effect_action=action,open_effect_runtime=o.current_runtime_id,no_delta_streak=0)
            return Transition(action,ns,True,True,iid,"CONNECTOR_BLOBS")
        return _t(s,"BLOCK_DURABLE","NO_INPUT_ROUTE",phase="BLOCKED",blocked_reason="NO_INPUT_ROUTE")
    action="LAUNCH_EXACTLY_ONCE"; iid=effect_id(s,action)
    ns=_advance(s,last_action=action,phase="EFFECT_INTENT",attempt=max(1,s.attempt),open_effect_id=iid,open_effect_action=action,open_effect_runtime=o.current_runtime_id,no_delta_streak=0)
    return Transition(action,ns,True,True,iid,"INPUTS_READY")

def append_event(prev_hash,seq,kind,payload):
    body={"schema":EVENT_SCHEMA,"seq":seq,"kind":kind,"payload":payload,"prev_event_hash":prev_hash}
    return {**body,"event_hash":sha256_obj(body)}

def verify_event_chain(events):
    prev=None
    for i,e in enumerate(events):
        body={k:e[k] for k in ("schema","seq","kind","payload","prev_event_hash")}
        if e.get("schema")!=EVENT_SCHEMA or e.get("seq")!=i or e.get("prev_event_hash")!=prev: return False
        if sha256_obj(body)!=e.get("event_hash"): return False
        prev=e["event_hash"]
    return True
