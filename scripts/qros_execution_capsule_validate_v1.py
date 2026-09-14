#!/usr/bin/env python3
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

class CapsuleError(Exception): pass
REQUIRED=["capsule_id","machine_state_id","single_action","subject","preconditions","exact_inputs","exact_commands","expected_outputs","pass_criteria","fail_closed_codes","forbidden_actions","terminal_receipt_path","next_state_on_pass"]
REQUIRED_INPUT_KEYS={"reconciliation_policy","workgraph","gap_register","scorer_terminal_receipt","execution_contract","build_spec","primary_core","oracle_core","primary_bound","oracle_bound","adversarial_suite"}

def canon(o): return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def git_blob(root,path):
    try: return subprocess.check_output(["git","-C",str(root),"hash-object",path],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: raise CapsuleError("CAPSULE_DEPENDENCY_UNREADABLE")
def validate(c,root,check_git=True):
    if not isinstance(c,dict) or any(k not in c for k in REQUIRED): raise CapsuleError("CAPSULE_FIELD_MISSING")
    if c.get("schema")!="QROS_EXECUTION_CAPSULE_1.0": raise CapsuleError("CAPSULE_SCHEMA_INVALID")
    if not isinstance(c["single_action"],str) or not c["single_action"]: raise CapsuleError("CAPSULE_ACTION_INVALID")
    inputs=c["exact_inputs"]
    if not isinstance(inputs,dict) or not REQUIRED_INPUT_KEYS.issubset(inputs): raise CapsuleError("CAPSULE_REQUIRED_INPUT_MISSING")
    seen=set()
    for name,node in inputs.items():
        if not isinstance(node,dict) or set(("path","git_blob_sha1"))-set(node): raise CapsuleError("CAPSULE_INPUT_NODE_INVALID")
        p=node["path"]; h=node["git_blob_sha1"]
        if not isinstance(p,str) or not p or any(ch in p for ch in "*?[]"): raise CapsuleError("CAPSULE_PATH_NONDETERMINISTIC")
        if p in seen: raise CapsuleError("CAPSULE_DUPLICATE_PATH")
        seen.add(p)
        if not isinstance(h,str) or len(h)!=40:
            raise CapsuleError("CAPSULE_PIN_INVALID")
        try: int(h,16)
        except Exception: raise CapsuleError("CAPSULE_PIN_INVALID")
        if check_git and git_blob(root,p)!=h: raise CapsuleError("CAPSULE_PIN_MISMATCH")
    cmds=c["exact_commands"]
    if not isinstance(cmds,list) or not cmds or any(not isinstance(x,str) or not x.strip() for x in cmds): raise CapsuleError("CAPSULE_COMMAND_INVALID")
    if any("*" in x or "?" in x or " latest " in (" "+x.lower()+" ") for x in cmds): raise CapsuleError("CAPSULE_COMMAND_NONDETERMINISTIC")
    fw=c.get("economic_firewall")
    if not isinstance(fw,dict) or any(fw.get(k) is not False for k in ("economic_pnl_read","ga2_open","holdout_open","first_gate_execution_authorized")): raise CapsuleError("ECONOMIC_FIREWALL_VIOLATION")
    forbidden=set(c["forbidden_actions"]) if isinstance(c["forbidden_actions"],list) else set()
    for need in ("OPEN_ENDED_REPOSITORY_SEARCH","READ_ECONOMIC_PNL","EXECUTE_FIRST_GATE"):
        if need not in forbidden: raise CapsuleError("CAPSULE_FORBIDDEN_SET_INCOMPLETE")
    return {"status":"PASS","capsule_id":c["capsule_id"],"machine_state_id":c["machine_state_id"],"single_action":c["single_action"],"input_count":len(inputs),"capsule_content_sha256":hashlib.sha256(canon(c).encode()).hexdigest()}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--capsule",required=True); ap.add_argument("--no-git",action="store_true"); a=ap.parse_args(); root=Path(__file__).resolve().parents[1]
    try:
        c=json.loads(Path(a.capsule).read_text()); print(canon(validate(c,root,not a.no_git)))
    except CapsuleError as e: print(canon({"status":"FAIL_CLOSED","error":str(e)})); sys.exit(2)
    except Exception as e: print(canon({"status":"FAIL_CLOSED","error":"UNEXPECTED_ERROR","detail":type(e).__name__})); sys.exit(2)
if __name__=="__main__": main()
