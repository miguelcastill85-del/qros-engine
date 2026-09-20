#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from dataclasses import dataclass, asdict, replace
from typing import Optional

SCHEMA="QROS_RUNTIME_ENFORCEMENT_STATE_1.0"
CHECKPOINT_CALL=6
HARD_CAP_CALLS=8
MAX_EXTERNAL_EFFECTS=1
SYNC_PAYLOAD_MAX_BYTES=50_000_000
SYNC_WALLCLOCK_MAX_SECONDS=5.0

READ_KINDS={"authority_read","metadata_read","status_read","search"}
PERSIST_KINDS={"persist","checkpoint"}
EXPENSIVE_KINDS={"materialize","download","upload","external_write","launch","new_work"}
WRITE_KINDS={"upload","external_write","launch","new_work"}
ALL_KINDS=READ_KINDS|PERSIST_KINDS|EXPENSIVE_KINDS

@dataclass(frozen=True)
class State:
    schema:str=SCHEMA
    invocation_id:str="UNSET"
    authority_ref:str="UNSET"
    calls_used:int=0
    external_effects:int=0
    expensive_units:int=0
    open_effect_id:Optional[str]=None
    checkpoint_persisted:bool=False
    terminal_durable:bool=False
    must_exit:bool=False
    last_evidence_hash:Optional[str]=None
    no_delta_streak:int=0
    last_action:Optional[str]=None
    blocked_reason:Optional[str]=None

@dataclass(frozen=True)
class Preflight:
    allow:bool
    reason:str
    effect_id:Optional[str]=None
    must_exit:bool=False

def canonical(obj)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def sha256_obj(obj)->str:
    return hashlib.sha256(canonical(obj)).hexdigest()

def effect_id(s:State,kind:str,locator:str="")->str:
    return sha256_obj({"schema":SCHEMA,"invocation_id":s.invocation_id,"authority_ref":s.authority_ref,
                       "calls_used":s.calls_used,"kind":kind,"locator":locator})

def preflight(s:State,kind:str,*,expected_bytes:int=0,expected_seconds:float=0.0,
              adoptable:bool=False,locator:str="",durable_intent:bool=False)->Preflight:
    if s.schema!=SCHEMA:
        return Preflight(False,"STATE_SCHEMA_MISMATCH",must_exit=True)
    if kind not in ALL_KINDS:
        return Preflight(False,"UNKNOWN_CALL_KIND",must_exit=True)
    if s.must_exit:
        return Preflight(False,"INVOCATION_ALREADY_MUST_EXIT",must_exit=True)
    if s.calls_used>=HARD_CAP_CALLS:
        return Preflight(False,"HARD_CAP_REACHED",must_exit=True)
    if s.calls_used>=CHECKPOINT_CALL and kind not in PERSIST_KINDS:
        return Preflight(False,"CHECKPOINT_BARRIER_REQUIRES_PERSIST_AND_EXIT",must_exit=True)
    if s.terminal_durable and kind not in PERSIST_KINDS:
        return Preflight(False,"TERMINAL_DURABLE_REQUIRES_EXIT",must_exit=True)
    if s.external_effects>=MAX_EXTERNAL_EFFECTS and kind in WRITE_KINDS:
        return Preflight(False,"SECOND_EXTERNAL_EFFECT_FORBIDDEN",must_exit=True)
    if s.expensive_units>=1 and kind in EXPENSIVE_KINDS:
        return Preflight(False,"SECOND_EXPENSIVE_UNIT_FORBIDDEN",must_exit=True)
    if kind in EXPENSIVE_KINDS:
        heavy=(expected_bytes>SYNC_PAYLOAD_MAX_BYTES) or (expected_seconds>SYNC_WALLCLOCK_MAX_SECONDS)
        if heavy and not adoptable:
            return Preflight(False,"SYNC_HEAVY_REQUIRES_ADOPTABLE_JOB",must_exit=True)
        if kind in WRITE_KINDS and not durable_intent:
            return Preflight(False,"WRITE_REQUIRES_DURABLE_INTENT",must_exit=True)
    iid=effect_id(s,kind,locator) if kind in WRITE_KINDS else None
    return Preflight(True,"ALLOW",iid,False)

def postflight(s:State,kind:str,*,success:bool,evidence_hash:Optional[str]=None,
               timeout:bool=False,durable:bool=False,effect_id_value:Optional[str]=None)->State:
    calls=s.calls_used+1
    delta=evidence_hash is not None and evidence_hash!=s.last_evidence_hash
    streak=0 if delta else s.no_delta_streak+1
    ext=s.external_effects+(1 if kind in WRITE_KINDS and success else 0)
    exp=s.expensive_units+(1 if kind in EXPENSIVE_KINDS else 0)
    must=s.must_exit
    blocked=s.blocked_reason
    open_effect=s.open_effect_id
    terminal=s.terminal_durable

    if kind in WRITE_KINDS and success:
        open_effect=effect_id_value or effect_id(s,kind)
    if timeout:
        must=True
        blocked="CONNECTOR_TIMEOUT_CHECKPOINT_EXIT"
    if streak>=2:
        must=True
        blocked=blocked or "NO_EVIDENCE_DELTA_CIRCUIT_BREAKER"
    if kind in PERSIST_KINDS and success and durable:
        terminal=True
        open_effect=None
        must=True
    if calls>=CHECKPOINT_CALL:
        must=True
        blocked=blocked or "CHECKPOINT_CALL_BARRIER"

    return replace(s,calls_used=calls,external_effects=ext,expensive_units=exp,
                   open_effect_id=open_effect,checkpoint_persisted=s.checkpoint_persisted or (kind in PERSIST_KINDS and success and durable),
                   terminal_durable=terminal,must_exit=must,last_evidence_hash=evidence_hash or s.last_evidence_hash,
                   no_delta_streak=streak,last_action=kind,blocked_reason=blocked)

def validate_pointer_advance(old:dict,new:dict,*,resolved_receipt_sha:str)->list[str]:
    errors=[]
    if old.get("current_blocker")==new.get("current_blocker"):
        errors.append("STALE_BLOCKER_NOT_ADVANCED")
    if new.get("resolved_blocker_receipt_sha")!=resolved_receipt_sha:
        errors.append("RESOLVED_RECEIPT_NOT_PINNED")
    if new.get("scientific_state")!=old.get("scientific_state"):
        errors.append("SCIENTIFIC_STATE_DRIFT")
    for k in ("economic_pnl_read","holdout_open","ga2_open","new_ga1_authorized","group12_opened"):
        if bool(new.get(k,False)):
            errors.append(f"FORBIDDEN_BOUNDARY_OPEN:{k}")
    return errors

def main()->int:
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="cmd",required=True)
    p=sp.add_parser("preflight")
    p.add_argument("--state-json",required=True)
    p.add_argument("--kind",required=True)
    p.add_argument("--expected-bytes",type=int,default=0)
    p.add_argument("--expected-seconds",type=float,default=0)
    p.add_argument("--adoptable",action="store_true")
    p.add_argument("--durable-intent",action="store_true")
    p.add_argument("--locator",default="")
    a=ap.parse_args()
    if a.cmd=="preflight":
        s=State(**json.loads(a.state_json))
        print(json.dumps(asdict(preflight(s,a.kind,expected_bytes=a.expected_bytes,
             expected_seconds=a.expected_seconds,adoptable=a.adoptable,locator=a.locator,
             durable_intent=a.durable_intent)),sort_keys=True))
        return 0
    return 2
if __name__=="__main__":
    raise SystemExit(main())
