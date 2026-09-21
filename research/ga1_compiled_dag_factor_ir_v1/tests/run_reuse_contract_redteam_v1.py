from __future__ import annotations
import copy,hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_reuse_contract import *

def H(s): return hashlib.sha256(s.encode()).hexdigest()
def node(payload,output=b"RESULT"):
    psha=sha256_bytes(canonical_bytes(payload))
    header={"schema":NODE_SCHEMA,"action_key":psha,"action_payload":payload,"action_payload_sha256":psha,"output_sha256":sha256_bytes(output),"output_bytes":len(output)}
    hb=canonical_bytes(header)
    return NODE_MAGIC+NODE_LEN.pack(len(hb))+hb+output

SC={"campaign":"SEED0076","genealogy":"FRACTALBOX_3EMA","asset":"NQX","side":"BUY","timeframe":"M2",
    "dev_period":"2018-2019","holdout_state":"CLOSED","multiplicity_scope":"GA1_60_SHARDS","economic_pnl_read":False}
SCH=scientific_context_hash(SC)
PAY={"schema":"QROS_TYPED_ACTION_KEY_1.0","operation":"MASK","operation_version":"2","code_hashes":{"impl":H("code")},
     "domain":{"asset":"NQX","side":"BUY","timeframe":"M2"},"parameters":{"fractal":3},
     "input_artifacts":{"bars":H("bars"),"dep:x":H("parent"),SCIENTIFIC_CONTEXT_INPUT:SCH},
     "environment":{"python":"3.13.5","numpy":"2.3.5","numba":"0.65.1","byteorder":"little"}}
OBJ=node(PAY)
VAL={"generator_oracle":H("oracle"),"tamper_suite":H("tamper")}
PROOF=make_reuse_proof(node_object=OBJ,scientific_context=SC,validation_receipts=VAL,parent_state="V259")
REQ={"action_payload":PAY,"scientific_context":SC,"required_validations":VAL}
assert evaluate_reuse(node_object=OBJ,proof=PROOF,request=REQ)["decision"]=="REUSE"
bad=bytearray(OBJ);bad[-1]^=1
assert evaluate_reuse(node_object=bytes(bad),proof=PROOF,request=REQ)["decision"]=="INVALIDATE"
for field in ["operation","operation_version","code_hashes","domain","parameters","input_artifacts","environment"]:
    q=copy.deepcopy(REQ)
    if field=="operation": q["action_payload"][field]="OTHER"
    elif field=="operation_version": q["action_payload"][field]="999"
    elif field=="code_hashes": q["action_payload"][field]={"impl":H("other")}
    elif field=="domain": q["action_payload"][field]={"asset":"XAU","side":"BUY","timeframe":"M2"}
    elif field=="parameters": q["action_payload"][field]={"fractal":5}
    elif field=="input_artifacts":
        q["action_payload"][field]=dict(PAY[field]);q["action_payload"][field]["bars"]=H("other-bars")
    else:q["action_payload"][field]=dict(PAY[field]);q["action_payload"][field]["numpy"]="0.0.0"
    assert evaluate_reuse(node_object=OBJ,proof=PROOF,request=q)["decision"]=="INVALIDATE",field
q=copy.deepcopy(REQ);q["scientific_context"]["genealogy"]="OTHER"
assert evaluate_reuse(node_object=OBJ,proof=PROOF,request=q)["decision"]=="INVALIDATE"
unbound=copy.deepcopy(PAY);unbound["input_artifacts"].pop(SCIENTIFIC_CONTEXT_INPUT)
UOBJ=node(unbound)
UPROOF=make_reuse_proof(node_object=UOBJ,scientific_context=SC,validation_receipts=VAL,parent_state="V259")
UREQ={"action_payload":unbound,"scientific_context":SC,"required_validations":VAL}
r=evaluate_reuse(node_object=UOBJ,proof=UPROOF,request=UREQ)
assert r["decision"]=="QUARANTINE" and "SCIENTIFIC_CONTEXT_UNBOUND_TO_ACTION_KEY" in r["reasons"]
q=copy.deepcopy(REQ);q["required_validations"]["extra"]=H("extra")
assert evaluate_reuse(node_object=OBJ,proof=PROOF,request=q)["decision"]=="VERIFY_ONLY"
q=copy.deepcopy(REQ);q["required_validations"]["generator_oracle"]=H("wrong")
assert evaluate_reuse(node_object=OBJ,proof=PROOF,request=q)["decision"]=="INVALIDATE"
p=copy.deepcopy(PROOF);p["parent_state"]="OTHER"
assert evaluate_reuse(node_object=OBJ,proof=p,request=REQ)["decision"]=="INVALIDATE"
p=make_reuse_proof(node_object=OBJ,scientific_context=SC,validation_receipts=VAL,parent_state="V259",status="DRAFT")
assert evaluate_reuse(node_object=OBJ,proof=p,request=REQ)["decision"]=="QUARANTINE"
assert evaluate_reuse(node_object=OBJ,proof=PROOF,request={"action_payload":PAY})["decision"]=="QUARANTINE"
print(json.dumps({
 "status":"PASS","exact_reuse_pass":True,"content_tamper_invalidated":True,
 "semantic_dimensions_invalidated":7,"scientific_context_mismatch_invalidated":True,
 "unbound_scientific_context_quarantined":True,"missing_validation_verify_only":True,
 "wrong_validation_invalidated":True,"proof_tamper_invalidated":True,
 "draft_proof_quarantined":True,"incomplete_request_quarantined":True
},sort_keys=True))
