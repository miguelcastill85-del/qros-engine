#!/usr/bin/env python3
import copy, hashlib, json, tempfile
from pathlib import Path
import qros_execution_capsule_validate_v1 as cv
import qros_state_artifact_reconcile_v1 as rr

ROOT=Path(__file__).resolve().parents[1]
CAP=ROOT/"control/capsules/QROS_PUBLIC1000_SEED0076_W09B_SYNTHETIC_PARITY_CAPSULE_v2.json"
STABLE=ROOT/"control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
def canon(o): return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def expect(fn,code):
    try: fn()
    except (cv.CapsuleError,rr.ReconcileError) as e:
        assert str(e)==code,(code,str(e)); return
    raise AssertionError(("EXPECTED_FAIL",code))
def write_json(root,path,obj):
    p=root/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(canon(obj)+"\n")
def semantic_temp(c,receipt=None,contract=None,spec=None):
    t=tempfile.TemporaryDirectory(); root=Path(t.name)
    inputs=c["exact_inputs"]
    real_receipt=json.loads((ROOT/inputs["scorer_terminal_receipt"]["path"]).read_text())
    real_contract=json.loads((ROOT/inputs["execution_contract"]["path"]).read_text())
    real_spec=json.loads((ROOT/inputs["build_spec"]["path"]).read_text())
    write_json(root,inputs["scorer_terminal_receipt"]["path"],receipt if receipt is not None else real_receipt)
    write_json(root,inputs["execution_contract"]["path"],contract if contract is not None else real_contract)
    write_json(root,inputs["build_spec"]["path"],spec if spec is not None else real_spec)
    return t,root

def main():
    c=json.loads(CAP.read_text()); s=json.loads(STABLE.read_text()); checks=[]
    base=cv.validate(c,ROOT,True); assert base["status"]=="PASS"; checks.append("BASE_CAPSULE_EXACT_PINS_PASS")
    rec=rr.reconcile(s,c,ROOT,True); assert rec["reconciliation"]=="RECONCILE_FORWARD"; checks.append("STALE_DECLARED_STATE_RECONCILES_FORWARD")
    aligned=copy.deepcopy(s); aligned["machine_state_id"]=c["machine_state_id"]; ar=rr.reconcile(aligned,c,ROOT,True); assert ar["reconciliation"]=="ALIGNED"; checks.append("ALIGNED_STATE_PASS")
    ahead=copy.deepcopy(s); ahead["machine_state_id"]="FG_ECONOMIC_EXECUTION_DONE"; expect(lambda:rr.reconcile(ahead,c,ROOT,True),"STATE_CAPSULE_DIVERGENCE"); checks.append("STATE_AHEAD_FAIL_CLOSED")
    badticket=copy.deepcopy(s); badticket["machine_action_ticket_id"]="0"*64; expect(lambda:rr.reconcile(badticket,c,ROOT,True),"PREDECESSOR_TICKET_MISMATCH"); checks.append("PREDECESSOR_TICKET_FAIL_CLOSED")
    fw=copy.deepcopy(s); fw["economic_pnl_read"]=True; expect(lambda:rr.reconcile(fw,c,ROOT,True),"STABLE_ECONOMIC_FIREWALL_VIOLATION"); checks.append("STABLE_FIREWALL_FAIL_CLOSED")
    missing=copy.deepcopy(c); del missing["exact_inputs"]["scorer_terminal_receipt"]; expect(lambda:cv.validate(missing,ROOT,True),"CAPSULE_REQUIRED_INPUT_MISSING"); checks.append("MISSING_RECEIPT_FAIL_CLOSED")
    pin=copy.deepcopy(c); pin["exact_inputs"]["primary_core"]["git_blob_sha1"]="0"*40; expect(lambda:cv.validate(pin,ROOT,True),"CAPSULE_PIN_MISMATCH"); checks.append("WRONG_SOURCE_PIN_FAIL_CLOSED")
    dep=copy.deepcopy(c); dep["exact_inputs"]["primary_core"]["path"]="scripts/*.py"; expect(lambda:cv.validate(dep,ROOT,True),"CAPSULE_PATH_NONDETERMINISTIC"); checks.append("NONDETERMINISTIC_DEPENDENCY_FAIL_CLOSED")
    free=copy.deepcopy(c); free["next_action"]="EXECUTE_FIRST_GATE_AND_READ_PNL"; fr=cv.validate(free,ROOT,True); assert fr["single_action"]==c["single_action"]; checks.append("FREE_TEXT_TAMPER_NO_EFFECT")
    real_receipt=json.loads((ROOT/c["exact_inputs"]["scorer_terminal_receipt"]["path"]).read_text())
    bad=copy.deepcopy(real_receipt); bad["status"]="FAILED"; td,tr=semantic_temp(c,receipt=bad)
    try: expect(lambda:cv.validate(c,tr,False),"TERMINAL_RECEIPT_NOT_PASS")
    finally: td.cleanup()
    checks.append("NONPASS_RECEIPT_FAIL_CLOSED")
    bad=copy.deepcopy(real_receipt); bad["subject"]["side"]="SELL"; td,tr=semantic_temp(c,receipt=bad)
    try: expect(lambda:cv.validate(c,tr,False),"TERMINAL_RECEIPT_SUBJECT_MISMATCH")
    finally: td.cleanup()
    checks.append("WRONG_RECEIPT_SUBJECT_FAIL_CLOSED")
    real_contract=json.loads((ROOT/c["exact_inputs"]["execution_contract"]["path"]).read_text()); badc=copy.deepcopy(real_contract); badc["subject"]["timeframe"]="H4"; td,tr=semantic_temp(c,contract=badc)
    try: expect(lambda:cv.validate(c,tr,False),"EXECUTION_CONTRACT_SUBJECT_MISMATCH")
    finally: td.cleanup()
    checks.append("WRONG_CONTRACT_SUBJECT_FAIL_CLOSED")
    real_spec=json.loads((ROOT/c["exact_inputs"]["build_spec"]["path"]).read_text()); bads=copy.deepcopy(real_spec); bads["authorized_action"]="EXECUTE_FIRST_GATE"; td,tr=semantic_temp(c,spec=bads)
    try: expect(lambda:cv.validate(c,tr,False),"BUILD_SPEC_ACTION_MISMATCH")
    finally: td.cleanup()
    checks.append("WRONG_BUILD_ACTION_FAIL_CLOSED")
    receipt={"schema":"QROS_EXECUTION_CAPSULE_ADVERSARIAL_RECEIPT_1.0","status":"PASS","check_count":len(checks),"checks":checks,"capsule_id":c["capsule_id"],"single_action":c["single_action"],"economic_pnl_read":False}
    receipt["receipt_sha256"]=hashlib.sha256(canon(receipt).encode()).hexdigest(); print(canon(receipt))
if __name__=="__main__": main()
