from __future__ import annotations
import copy, hashlib, json, struct, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from qros_typed_action import action_key, environment_manifest, validate_environment_manifest
from qros_scientific_dag import compile_scientific_manifest
from qros_reuse_contract import (
    NODE_MAGIC,NODE_LEN,NODE_SCHEMA,canonical_bytes,sha256_bytes,
    make_reuse_proof,evaluate_reuse,SCIENTIFIC_CONTEXT_INPUT
)

H=lambda s: hashlib.sha256(s.encode()).hexdigest()
ENV={"python":"3.13.5","implementation":"CPython","platform":"fixture-linux","numpy":"2.3.5","numba":"0.65.1","byteorder":"little"}
SC={"campaign":"SEED0076","genealogy":"FRACTALBOX_3EMA","asset":"NQX","side":"BUY","timeframe":"M2","state":"PREREGISTERED_NO_RESULTS"}
SCH=hashlib.sha256(canonical_bytes(SC)).hexdigest()

def payload(env):
    return action_key(
        operation="ENV_CANARY",operation_version="1",code_hashes={"impl":H("code")},
        domain={"asset":"NQX","side":"BUY","timeframe":"M2"},parameters={"x":1},
        input_artifacts={"fixture":H("fixture"),SCIENTIFIC_CONTEXT_INPUT:SCH},environment=env
    )

def node_obj(akey,pay,out=b"RESULT"):
    header={"schema":NODE_SCHEMA,"action_key":akey,"action_payload":pay,
            "action_payload_sha256":sha256_bytes(canonical_bytes(pay)),
            "output_sha256":sha256_bytes(out),"output_bytes":len(out)}
    hb=canonical_bytes(header)
    return NODE_MAGIC+NODE_LEN.pack(len(hb))+hb+out

# Baseline contract and canonical ordering.
assert validate_environment_manifest(ENV)==ENV
generated=environment_manifest({"canary":"v1"})
assert validate_environment_manifest(generated)==generated
reordered={k:ENV[k] for k in reversed(list(ENV))}
k0,p0=payload(ENV); kr,pr=payload(reordered)
assert k0==kr and p0==pr

# Every material runtime identity dimension changes the action key.
mutations={
  "python":"3.14.0",
  "implementation":"PyPy",
  "platform":"fixture-other",
  "numpy":"9.9.9",
  "numba":"9.9.9",
  "byteorder":"big",
}
changed=0
for field,value in mutations.items():
    e=copy.deepcopy(ENV);e[field]=value
    validate_environment_manifest(e)
    k,_=payload(e)
    assert k!=k0,field
    changed+=1

# Invalid/incomplete manifests fail closed at the scientific contract.
invalid=[]
for field in ("python","implementation","platform","numpy","numba","byteorder"):
    e=copy.deepcopy(ENV);del e[field];invalid.append(e)
invalid += [
  {**ENV,"byteorder":"sideways"},
  {**ENV,"python":123},
  {**ENV,"implementation":None},
  {**ENV,"platform":""},
  {**ENV,"numpy":123},
  {**ENV,"numba":123},
  {**ENV,"extra":"not-a-dict"},
  {**ENV,"unexpected":"x"},
]
rejected=0
for e in invalid:
    try:validate_environment_manifest(e);raise AssertionError("INVALID_ENVIRONMENT_ACCEPTED")
    except ValueError:rejected+=1

CTX={
 "schema":"QROS_SCIENTIFIC_CONTEXT_1.0","campaign_id":"C","seed_id":"S","genealogy_id":"G","phase":"GA1",
 "asset":"NQX","side":"BUY","timeframe":"M2",
 "development_period":{"start":"2018","end":"2019","timezone":"BROKER"},
 "scientific_state":"PREREGISTERED_NO_RESULTS","holdout_state":"CLOSED","exposure_state":"DEV_ONLY",
 "multiplicity_scope":"M60","cost_model_id":"COST","gate_policy_id":"V259","selection_policy_id":"FROZEN",
 "thesis_fingerprint":H("T"),"data_context_fingerprint":H("D"),"extensions":{}
}
MAN={"schema":"QROS_TYPED_DAG_MANIFEST_1.0","nodes":[{
 "id":"a","operation":"EMIT","operation_version":"1","code_hashes":{"impl":H("code")},
 "domain":{"asset":"NQX","side":"BUY","timeframe":"M2"},"parameters":{},
 "static_inputs":{"fixture":H("fixture")},"environment":ENV,"deps":[]
}]}
compile_scientific_manifest(MAN,CTX)
badman=copy.deepcopy(MAN);badman["nodes"][0]["environment"]={"python":"fixture"}
try:compile_scientific_manifest(badman,CTX);raise AssertionError("SCIENTIFIC_PARTIAL_ENV_ACCEPTED")
except ValueError as e:assert "SCIENTIFIC_ENVIRONMENT_INVALID" in str(e)

# Reuse: invalid stored artifact => INVALIDATE; invalid request => QUARANTINE.
obj=node_obj(k0,p0);vals={"oracle":H("oracle")}
proof=make_reuse_proof(node_object=obj,scientific_context=SC,validation_receipts=vals,parent_state="V259")
req={"action_payload":p0,"scientific_context":SC,"required_validations":vals,"parent_state":"V259"}
assert evaluate_reuse(node_object=obj,proof=proof,request=req)["decision"]=="REUSE"

bad_env={"python":"fixture"}
bk,bp=payload(bad_env);bobj=node_obj(bk,bp)
bproof=make_reuse_proof(node_object=bobj,scientific_context=SC,validation_receipts=vals,parent_state="V259")
r=evaluate_reuse(node_object=bobj,proof=bproof,request={"action_payload":bp,"scientific_context":SC,"required_validations":vals,"parent_state":"V259"})
assert r["decision"]=="INVALIDATE" and r["reasons"][0].startswith("ARTIFACT_ENVIRONMENT_INVALID:")

badreq=copy.deepcopy(req);badreq["action_payload"]["environment"]={"python":"fixture"}
r=evaluate_reuse(node_object=obj,proof=proof,request=badreq)
assert r["decision"]=="QUARANTINE" and r["reasons"][0].startswith("REQUEST_ENVIRONMENT_INVALID:")

# Raw action identity remains technical-only and intentionally does not become a scientific gate.
raw_key,_=payload({"python":"fixture"})
assert isinstance(raw_key,str) and len(raw_key)==64

print(json.dumps({
 "status":"PASS","classification":"SYNTHETIC_NON_ECONOMIC",
 "valid_environment_generated":True,"canonical_key_order_invariant":True,
 "environment_identity_mutations_changed_action_key":changed,
 "invalid_environment_cases_rejected":rejected,
 "scientific_partial_environment_rejected":True,
 "reuse_invalid_artifact_environment_invalidated":True,
 "reuse_invalid_request_environment_quarantined":True,
 "raw_action_key_remains_technical_permissive":True,
 "retest_rearm_touched":False
},sort_keys=True,separators=(",",":")))
