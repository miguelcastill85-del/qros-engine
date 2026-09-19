#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from typing import Optional, FrozenSet
import hashlib, json, re

SPEC_SCHEMA="QROS_CWS_TASK_SPEC_1.0"
STATE_SCHEMA="QROS_CWS_STATE_1.0"
PROOF_SCHEMA="QROS_CWS_PROGRESS_PROOF_1.0"
CERT_SCHEMA="QROS_CWS_COMPLETION_CERT_1.0"

META_ACTIONS={
    "INVOKE_DEK","WAIT","RECORD_PROGRESS","RECONCILE",
    "PREEMPT","BLOCK_AUTHORITY","BLOCK_CAPABILITY","RESUME",
    "COMPLETE","NOOP","REFRESH_AUTHORITY","IGNORE_STALE"
}

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def hobj(x):
    return hashlib.sha256(canon(x)).hexdigest()

def hex64(x):
    return isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x) is not None

@dataclass(frozen=True)
class TaskSpec:
    schema:str
    task_id:str
    objective_hash:str
    revision:int
    capabilities:FrozenSet[str]
    no_progress_limit:int=2
    call_budget:int=8

@dataclass(frozen=True)
class State:
    schema:str
    task_id:str
    objective_hash:str
    revision:int
    task_spec_hash:str
    seq:int=0
    phase:str="ACTIVE"
    pending_effect_id:Optional[str]=None
    open_segment_id:Optional[str]=None
    open_segment_epoch:int=0
    last_progress_seq:int=-1
    last_progress_window:int=-1
    no_progress_streak:int=0
    progress_count:int=0
    terminal_root:Optional[str]=None
    blocked_reason:Optional[str]=None

@dataclass(frozen=True)
class Observation:
    authority_ok:bool=True
    call_index:int=1
    requested_revision:Optional[int]=None
    requested_objective_hash:Optional[str]=None
    required_capability:Optional[str]=None
    cas_conflict:bool=False
    heartbeat:bool=False
    progress_window:Optional[int]=None
    progress_proof:Optional[dict]=None
    effect_ack_id:Optional[str]=None
    segment_id:Optional[str]=None
    segment_epoch:Optional[int]=None
    segment_terminal:Optional[str]=None
    dek_terminal:bool=False
    dek_terminal_root:Optional[str]=None
    dek_terminal_task_spec_hash:Optional[str]=None

@dataclass(frozen=True)
class Decision:
    action:str
    next_state:State
    external_effect:bool
    effect_id:Optional[str]
    reason:str

def spec_material(s:TaskSpec):
    return {
        "schema":s.schema,"task_id":s.task_id,"objective_hash":s.objective_hash,
        "revision":s.revision,"capabilities":sorted(s.capabilities),
        "no_progress_limit":s.no_progress_limit,"call_budget":s.call_budget
    }

def spec_hash(s:TaskSpec):
    return hobj(spec_material(s))

def validate_spec(s:TaskSpec):
    if s.schema!=SPEC_SCHEMA: raise ValueError("SPEC_SCHEMA")
    if not s.task_id or len(s.task_id)>128: raise ValueError("TASK_ID")
    if not hex64(s.objective_hash): raise ValueError("OBJECTIVE_HASH")
    if s.revision<1 or s.no_progress_limit<1 or s.call_budget<1: raise ValueError("BOUNDS")
    if any(not isinstance(c,str) or not c.startswith("CAP_") for c in s.capabilities):
        raise ValueError("CAPABILITY")

def validate_state(spec:TaskSpec,s:State):
    validate_spec(spec)
    if s.schema!=STATE_SCHEMA: raise ValueError("STATE_SCHEMA")
    if (s.task_id,s.objective_hash,s.revision)!=(spec.task_id,spec.objective_hash,spec.revision):
        raise ValueError("TASK_BINDING")
    if s.task_spec_hash!=spec_hash(spec): raise ValueError("SPEC_HASH_BINDING")
    if s.phase not in {"ACTIVE","BLOCKED","PREEMPTED","COMPLETE"}: raise ValueError("PHASE")
    if s.seq<0 or s.open_segment_epoch<0 or s.last_progress_seq<-1 or s.last_progress_window<-1:
        raise ValueError("COUNTER")
    if s.phase=="COMPLETE" and not hex64(s.terminal_root):
        raise ValueError("COMPLETE_WITHOUT_ROOT")

def initial_state(spec:TaskSpec):
    validate_spec(spec)
    return State(
        schema=STATE_SCHEMA,task_id=spec.task_id,objective_hash=spec.objective_hash,
        revision=spec.revision,task_spec_hash=spec_hash(spec)
    )

def state_hash(s:State):
    return hobj(asdict(s))

def effect_id(spec:TaskSpec,s:State):
    return hobj({
        "schema":"QROS_CWS_DEK_WAKE_1.0","task_spec_hash":spec_hash(spec),
        "seq":s.seq,"state_hash":state_hash(s)
    })

def make_progress_proof(spec:TaskSpec,segment_id:str,segment_epoch:int,progress_seq:int,durable_root:str):
    body={
        "schema":PROOF_SCHEMA,"task_spec_hash":spec_hash(spec),
        "segment_id":segment_id,"segment_epoch":segment_epoch,
        "progress_seq":progress_seq,"durable_root":durable_root
    }
    return {**body,"proof_hash":hobj(body)}

def valid_progress_proof(spec:TaskSpec,s:State,p):
    if not isinstance(p,dict): return False
    keys={"schema","task_spec_hash","segment_id","segment_epoch","progress_seq","durable_root","proof_hash"}
    if set(p)!=keys: return False
    if p["schema"]!=PROOF_SCHEMA or p["task_spec_hash"]!=spec_hash(spec): return False
    if not isinstance(p["segment_id"],str) or not p["segment_id"]: return False
    if not isinstance(p["segment_epoch"],int) or p["segment_epoch"]<0: return False
    if not isinstance(p["progress_seq"],int) or p["progress_seq"]<=s.last_progress_seq: return False
    if not hex64(p["durable_root"]): return False
    body={k:p[k] for k in ("schema","task_spec_hash","segment_id","segment_epoch","progress_seq","durable_root")}
    if hobj(body)!=p["proof_hash"]: return False
    if s.open_segment_id is not None:
        if (p["segment_id"],p["segment_epoch"])!=(s.open_segment_id,s.open_segment_epoch): return False
    return True

def dec(s:State,action:str,reason:str,external=False,eid=None,advance=True,**kw):
    if action not in META_ACTIONS: raise RuntimeError("NON_META_ACTION")
    ns=replace(s,seq=s.seq+1,**kw) if advance else s
    return Decision(action,ns,external,eid,reason)

def compile_step(spec:TaskSpec,s:State,o:Observation):
    validate_state(spec,s)
    if o.call_index<1: raise ValueError("CALL_INDEX")
    if o.progress_window is not None and o.progress_window<0: raise ValueError("PROGRESS_WINDOW")

    if s.phase=="COMPLETE": return dec(s,"NOOP","ALREADY_COMPLETE",advance=False)
    if s.phase=="PREEMPTED": return dec(s,"NOOP","PREEMPTED_TASK",advance=False)

    changed_objective=(
        (o.requested_revision is not None and o.requested_revision>spec.revision) or
        (o.requested_objective_hash is not None and o.requested_objective_hash!=spec.objective_hash)
    )
    if changed_objective:
        return dec(s,"PREEMPT","OBJECTIVE_CHANGED",phase="PREEMPTED",
                   pending_effect_id=None,open_segment_id=None,blocked_reason=None)

    if s.phase=="BLOCKED":
        if s.blocked_reason=="AUTHORITY" and o.authority_ok:
            return dec(s,"RESUME","AUTHORITY_RECONCILED",phase="ACTIVE",blocked_reason=None,no_progress_streak=0)
        return dec(s,"NOOP","BLOCK_REQUIRES_NEW_EVIDENCE",advance=False)

    if not o.authority_ok:
        return dec(s,"BLOCK_AUTHORITY","AUTHORITY_NOT_RECONCILED",phase="BLOCKED",blocked_reason="AUTHORITY")

    if o.cas_conflict:
        return dec(s,"REFRESH_AUTHORITY","CAS_CONFLICT",advance=False)

    if o.required_capability and o.required_capability not in spec.capabilities:
        return dec(s,"BLOCK_CAPABILITY","CAPABILITY_NOT_GRANTED",phase="BLOCKED",
                   blocked_reason="CAPABILITY:"+o.required_capability)

    if o.call_index>=spec.call_budget:
        return dec(s,"WAIT","CALL_BUDGET_EXIT",advance=False)

    if o.progress_window is not None and o.progress_window>s.last_progress_window+1:
        return dec(s,"IGNORE_STALE","NON_CONTIGUOUS_PROGRESS_WINDOW",advance=False)

    if o.dek_terminal:
        if not hex64(o.dek_terminal_root) or o.dek_terminal_task_spec_hash!=s.task_spec_hash:
            return dec(s,"IGNORE_STALE","UNBOUND_DEK_TERMINAL",advance=False)
        return dec(s,"COMPLETE","TASK_TERMINAL",phase="COMPLETE",
                   terminal_root=o.dek_terminal_root,pending_effect_id=None,open_segment_id=None,
                   no_progress_streak=0,blocked_reason=None)

    if o.progress_proof is not None:
        if not valid_progress_proof(spec,s,o.progress_proof):
            return dec(s,"IGNORE_STALE","INVALID_PROGRESS_PROOF",advance=False)
        p=o.progress_proof
        win=max(s.last_progress_window,o.progress_window if o.progress_window is not None else s.last_progress_window)
        return dec(s,"RECORD_PROGRESS","DURABLE_PROGRESS",
                   last_progress_seq=p["progress_seq"],last_progress_window=win,
                   no_progress_streak=0,progress_count=s.progress_count+1,
                   open_segment_id=p["segment_id"],open_segment_epoch=p["segment_epoch"])

    new_window=(o.progress_window is not None and o.progress_window==s.last_progress_window+1)

    if s.pending_effect_id:
        if o.effect_ack_id is not None:
            if o.effect_ack_id!=s.pending_effect_id:
                return dec(s,"IGNORE_STALE","ACK_MISMATCH",advance=False)
            return dec(s,"WAIT","ACK_ACCEPTED",pending_effect_id=None,
                       open_segment_id=o.segment_id or s.open_segment_id,
                       open_segment_epoch=o.segment_epoch if o.segment_epoch is not None else s.open_segment_epoch,
                       no_progress_streak=0,
                       last_progress_window=max(s.last_progress_window,o.progress_window if o.progress_window is not None else s.last_progress_window))
        if not new_window:
            return dec(s,"WAIT","PENDING_EFFECT_SAME_WINDOW",advance=False)
        streak=s.no_progress_streak+1
        if streak>=spec.no_progress_limit:
            return dec(s,"RECONCILE","PENDING_EFFECT_STALLED",external=True,eid=s.pending_effect_id,
                       no_progress_streak=streak,last_progress_window=o.progress_window)
        return dec(s,"WAIT","PENDING_EFFECT_NO_PROGRESS",no_progress_streak=streak,last_progress_window=o.progress_window)

    if s.open_segment_id:
        if o.segment_terminal is not None:
            if (o.segment_id,o.segment_epoch)!=(s.open_segment_id,s.open_segment_epoch):
                return dec(s,"IGNORE_STALE","SEGMENT_IDENTITY_MISMATCH",advance=False)
            if o.segment_terminal=="FAIL":
                eid=effect_id(spec,s)
                return dec(s,"RECONCILE","SEGMENT_FAIL",external=True,eid=eid,no_progress_streak=0)
            if o.segment_terminal=="PASS":
                eid=effect_id(spec,s)
                return dec(s,"INVOKE_DEK","SEGMENT_PASS_REDUCE",external=True,eid=eid,
                           open_segment_id=None,pending_effect_id=eid,no_progress_streak=0)
        if not new_window:
            return dec(s,"WAIT","OPEN_SEGMENT_SAME_WINDOW",advance=False)
        streak=s.no_progress_streak+1
        if streak>=spec.no_progress_limit:
            eid=effect_id(spec,s)
            return dec(s,"RECONCILE","OPEN_SEGMENT_STALLED",external=True,eid=eid,
                       no_progress_streak=streak,last_progress_window=o.progress_window)
        return dec(s,"WAIT","OPEN_SEGMENT_NO_PROGRESS",no_progress_streak=streak,last_progress_window=o.progress_window)

    eid=effect_id(spec,s)
    return dec(s,"INVOKE_DEK","NO_OPEN_SEGMENT",external=True,eid=eid,pending_effect_id=eid,no_progress_streak=0)

def completion_certificate(spec:TaskSpec,s:State):
    validate_state(spec,s)
    if s.phase!="COMPLETE": raise ValueError("NOT_COMPLETE")
    body={
        "schema":CERT_SCHEMA,"task_id":spec.task_id,"task_spec_hash":spec_hash(spec),
        "objective_hash":spec.objective_hash,"revision":spec.revision,"terminal_root":s.terminal_root
    }
    return {**body,"certificate_sha256":hobj(body)}
