#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, asdict, field, replace
from typing import Tuple, Optional

SCHEMA="QROS_TURN_ENFORCEMENT_STATE_2.0"
MAX_LOGICAL_TRANSACTIONS=3
MAX_PLATFORM_CALLS=4
SYNC_PAYLOAD_MAX_BYTES=50_000_000
SYNC_WALLCLOCK_MAX_SECONDS=5.0
AUTHORITY_TX="AUTHORITY_BUNDLE"
ACTION_TX="ONE_ACTION"
PERSIST_TX="PERSIST_AND_EXIT"
TX_KINDS={AUTHORITY_TX,ACTION_TX,PERSIST_TX}

@dataclass(frozen=True)
class State:
    schema:str=SCHEMA
    invocation_id:str="UNSET"
    authority_ref:str="UNSET"
    logical_transactions:int=0
    platform_calls:int=0
    phase:str="AUTHORITY"
    authority_done:bool=False
    action_attempted:bool=False
    action_succeeded:bool=False
    checkpoint_persisted:bool=False
    must_exit:bool=False
    blocked_reason:Optional[str]=None
    probed_capabilities:Tuple[str,...]=field(default_factory=tuple)
    failed_capabilities:Tuple[str,...]=field(default_factory=tuple)
    attempt_fingerprints:Tuple[str,...]=field(default_factory=tuple)

@dataclass(frozen=True)
class Preflight:
    allow:bool
    reason:str
    must_exit:bool=False

def deny(reason:str)->Preflight:
    return Preflight(False,reason,True)

def preflight(s:State,tx_kind:str,*,capability:str="",attempt_fingerprint:str="",
              expected_bytes:int=0,expected_seconds:float=0.0,adoptable:bool=False)->Preflight:
    if s.schema!=SCHEMA: return deny("STATE_SCHEMA_MISMATCH")
    if tx_kind not in TX_KINDS: return deny("UNKNOWN_TRANSACTION_KIND")
    if s.logical_transactions>=MAX_LOGICAL_TRANSACTIONS: return deny("TURN_TRANSACTION_BUDGET_EXHAUSTED")
    if s.platform_calls>=MAX_PLATFORM_CALLS and tx_kind!=PERSIST_TX: return deny("PLATFORM_CALL_BUDGET_EXHAUSTED")
    if s.must_exit and tx_kind!=PERSIST_TX: return deny("MUST_EXIT_ONLY_PERSIST_ALLOWED")
    if s.checkpoint_persisted: return deny("CHECKPOINT_ALREADY_DURABLE")
    if tx_kind==AUTHORITY_TX:
        if s.phase!="AUTHORITY" or s.authority_done or s.logical_transactions!=0:
            return deny("AUTHORITY_BUNDLE_ALREADY_CONSUMED")
    elif tx_kind==ACTION_TX:
        if not s.authority_done or s.phase!="ACTION": return deny("ACTION_REQUIRES_AUTHORITY")
        if s.action_attempted: return deny("SECOND_ACTION_FORBIDDEN")
        heavy=expected_bytes>SYNC_PAYLOAD_MAX_BYTES or expected_seconds>SYNC_WALLCLOCK_MAX_SECONDS
        if heavy and not adoptable: return deny("SYNC_HEAVY_ACTION_FORBIDDEN")
        if capability and capability in s.failed_capabilities: return deny("FAILED_CAPABILITY_LEASE_FORBIDS_RETRY")
        if capability and capability in s.probed_capabilities: return deny("ONE_PROBE_PER_CAPABILITY")
        if attempt_fingerprint and attempt_fingerprint in s.attempt_fingerprints: return deny("DUPLICATE_ATTEMPT_FINGERPRINT")
    elif tx_kind==PERSIST_TX:
        if not s.authority_done: return deny("PERSIST_REQUIRES_AUTHORITY")
        if s.phase not in ("PERSIST","EXIT"): return deny("PERSIST_NOT_YET_ALLOWED")
    return Preflight(True,"ALLOW",False)

def postflight(s:State,tx_kind:str,*,success:bool,timeout:bool=False,
               infrastructure_error:bool=False,capability:str="",attempt_fingerprint:str="",
               durable:bool=False,platform_calls_used:int=1)->State:
    if platform_calls_used<0: raise ValueError("NEGATIVE_PLATFORM_CALLS")
    probes=s.probed_capabilities; failed=s.failed_capabilities; fps=s.attempt_fingerprints
    phase=s.phase; authority=s.authority_done; attempted=s.action_attempted
    action_ok=s.action_succeeded; persisted=s.checkpoint_persisted
    must=s.must_exit; blocked=s.blocked_reason

    if tx_kind==AUTHORITY_TX:
        authority=success
        phase="ACTION" if success else "PERSIST"
        if not success:
            must=True; blocked="AUTHORITY_BUNDLE_FAILED"
    elif tx_kind==ACTION_TX:
        attempted=True; phase="PERSIST"
        if capability and capability not in probes: probes=probes+(capability,)
        if attempt_fingerprint and attempt_fingerprint not in fps: fps=fps+(attempt_fingerprint,)
        action_ok=bool(success and not timeout and not infrastructure_error)
        if timeout or infrastructure_error:
            if capability and capability not in failed: failed=failed+(capability,)
            must=True; blocked="INFRASTRUCTURE_FAILURE_PERSIST_AND_EXIT"
        elif not success:
            must=True; blocked="ACTION_FAILED_PERSIST_AND_EXIT"
    elif tx_kind==PERSIST_TX:
        if success and durable: persisted=True
        phase="EXIT"; must=True
        blocked=blocked or ("TURN_CLOSED_DURABLY" if persisted else "PERSIST_FAILED_EXIT_WITHOUT_RETRY")

    calls=s.platform_calls+platform_calls_used
    if calls>=MAX_PLATFORM_CALLS and not persisted:
        must=True; blocked=blocked or "PLATFORM_CALL_BUDGET_REACHED"

    return replace(s,logical_transactions=s.logical_transactions+1,platform_calls=calls,phase=phase,
                   authority_done=authority,action_attempted=attempted,action_succeeded=action_ok,
                   checkpoint_persisted=persisted,must_exit=must,blocked_reason=blocked,
                   probed_capabilities=probes,failed_capabilities=failed,attempt_fingerprints=fps)

BOUNDARY_KEYS=("scientific_state","economic_pnl_read","holdout_open","ga2_open",
               "new_ga1_authorized","authorization_scope","first_gate_execution_authorized")

def validate_control_plane_pointer_preservation(old:dict,new:dict)->list[str]:
    errors=[]
    for k in BOUNDARY_KEYS:
        if old.get(k)!=new.get(k): errors.append(f"SCIENTIFIC_BOUNDARY_DRIFT:{k}")
    if old.get("subject")!=new.get("subject"): errors.append("SCIENTIFIC_SUBJECT_DRIFT")
    return errors

def main()->int:
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="cmd",required=True)
    p=sp.add_parser("preflight")
    p.add_argument("--state-json",required=True); p.add_argument("--tx-kind",required=True)
    p.add_argument("--capability",default=""); p.add_argument("--attempt-fingerprint",default="")
    p.add_argument("--expected-bytes",type=int,default=0); p.add_argument("--expected-seconds",type=float,default=0)
    p.add_argument("--adoptable",action="store_true")
    a=ap.parse_args()
    s=State(**json.loads(a.state_json))
    print(json.dumps(asdict(preflight(s,a.tx_kind,capability=a.capability,
          attempt_fingerprint=a.attempt_fingerprint,expected_bytes=a.expected_bytes,
          expected_seconds=a.expected_seconds,adoptable=a.adoptable)),sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
