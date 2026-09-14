#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
import qros_execution_capsule_validate_v1 as cv

class ReconcileError(Exception): pass
def canon(o): return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def reconcile(stable,capsule,root,check_git=True):
    cap=cv.validate(capsule,root,check_git)
    for k in ("economic_pnl_read","ga2_open","holdout_open","first_gate_execution_authorized"):
        if stable.get(k) is not False: raise ReconcileError("STABLE_ECONOMIC_FIREWALL_VIOLATION")
    cur=stable.get("machine_state_id"); target=capsule.get("machine_state_id")
    if cur==target:
        return {"status":"PASS","reconciliation":"ALIGNED","from_state":cur,"to_state":target,"single_action":cap["single_action"],"capsule_id":cap["capsule_id"]}
    if cur==capsule.get("predecessor_state_id"):
        if stable.get("machine_action_ticket_id")!=capsule.get("predecessor_action_ticket_id"): raise ReconcileError("PREDECESSOR_TICKET_MISMATCH")
        key=capsule.get("predecessor_terminal_evidence_key")
        if key not in capsule.get("exact_inputs",{}): raise ReconcileError("PREDECESSOR_EVIDENCE_MISSING")
        return {"status":"PASS","reconciliation":"RECONCILE_FORWARD","from_state":cur,"to_state":target,"single_action":cap["single_action"],"capsule_id":cap["capsule_id"],"reason":"PINNED_TERMINAL_EVIDENCE_OUTRANKS_STALE_DECLARED_STATE"}
    raise ReconcileError("STATE_CAPSULE_DIVERGENCE")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--stable",required=True); ap.add_argument("--capsule",required=True); ap.add_argument("--no-git",action="store_true"); a=ap.parse_args(); root=Path(__file__).resolve().parents[1]
    try:
        s=json.loads(Path(a.stable).read_text()); c=json.loads(Path(a.capsule).read_text()); print(canon(reconcile(s,c,root,not a.no_git)))
    except (ReconcileError,cv.CapsuleError) as e: print(canon({"status":"FAIL_CLOSED","error":str(e)})); sys.exit(2)
    except Exception as e: print(canon({"status":"FAIL_CLOSED","error":"UNEXPECTED_ERROR","detail":type(e).__name__})); sys.exit(2)
if __name__=="__main__": main()
