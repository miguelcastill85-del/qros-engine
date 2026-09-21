from __future__ import annotations
import copy,hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_scientific_context import bind_scientific_context,SCHEMA,BINDING_INPUT
from qros_typed_action import action_key
from qros_reuse_contract import NODE_MAGIC,NODE_LEN,NODE_SCHEMA,canonical_bytes,sha256_bytes,make_reuse_proof,evaluate_reuse

ENV={"python":"3.13.5","implementation":"CPython","platform":"fixture-linux","numpy":"2.3.5","numba":"0.65.1","byteorder":"little"}

H=lambda s:hashlib.sha256(s.encode()).hexdigest()
CTX={"schema":SCHEMA,"campaign_id":"C","seed_id":"S","genealogy_id":"G","phase":"GA1","asset":"NQX","side":"BUY","timeframe":"M2","development_period":{"start":"2018","end":"2019","timezone":"BROKER"},"scientific_state":"PREREGISTERED_NO_RESULTS","holdout_state":"CLOSED","exposure_state":"DEV_ONLY","multiplicity_scope":"M60","cost_model_id":"COST1","gate_policy_id":"GATE1","selection_policy_id":"SEL1","thesis_fingerprint":H("T"),"data_context_fingerprint":H("D"),"extensions":{}}
MAN={"schema":"QROS_TYPED_DAG_MANIFEST_1.0","nodes":[{"id":"a","operation":"EMIT","operation_version":"1","code_hashes":{"impl":H("code")},"domain":{"asset":"NQX","side":"BUY","timeframe":"M2"},"parameters":{"x":1},"static_inputs":{"fixture":H("fixture")},"environment":ENV,"deps":[]}]}
def payload(comp):
    n=comp["manifest"]["nodes"][0]
    return action_key(operation=n["operation"],operation_version=n["operation_version"],code_hashes=n["code_hashes"],domain=n["domain"],parameters=n["parameters"],input_artifacts=n["static_inputs"],environment=n["environment"])
def node_obj(akey,pay,out=b"RESULT"):
    h={"schema":NODE_SCHEMA,"action_key":akey,"action_payload":pay,"action_payload_sha256":sha256_bytes(canonical_bytes(pay)),"output_sha256":sha256_bytes(out),"output_bytes":len(out)}
    hb=canonical_bytes(h)
    return NODE_MAGIC+NODE_LEN.pack(len(hb))+hb+out

bound=bind_scientific_context(MAN,CTX); k,p=payload(bound); obj=node_obj(k,p); vals={"oracle":H("oracle")}
proof=make_reuse_proof(node_object=obj,scientific_context=CTX,validation_receipts=vals,parent_state="V259")
req={"action_payload":p,"scientific_context":CTX,"required_validations":vals,"parent_state":"V259"}
assert evaluate_reuse(node_object=obj,proof=proof,request=req)["decision"]=="REUSE"
bound2=bind_scientific_context(MAN,copy.deepcopy(CTX)); k2,p2=payload(bound2)
assert k2==k and p2==p

fields=[("genealogy_id","G2"),("development_period",{"start":"2020","end":"2021","timezone":"BROKER"}),("holdout_state","EXPOSED"),("exposure_state","DEV_PLUS_DIAGNOSTIC"),("multiplicity_scope","M120"),("cost_model_id","COST2"),("gate_policy_id","GATE2"),("selection_policy_id","SEL2"),("thesis_fingerprint",H("T2")),("data_context_fingerprint",H("D2"))]
for f,v in fields:
    c=copy.deepcopy(CTX); c[f]=v; z=bind_scientific_context(MAN,c); kz,pz=payload(z)
    assert kz!=k
    rz=evaluate_reuse(node_object=obj,proof=proof,request={"action_payload":pz,"scientific_context":c,"required_validations":vals,"parent_state":"V259"})
    assert rz["decision"]=="INVALIDATE",(f,rz)

n=MAN["nodes"][0]
ku,pu=action_key(operation=n["operation"],operation_version=n["operation_version"],code_hashes=n["code_hashes"],domain=n["domain"],parameters=n["parameters"],input_artifacts=n["static_inputs"],environment=n["environment"])
uobj=node_obj(ku,pu)
uproof=make_reuse_proof(node_object=uobj,scientific_context=CTX,validation_receipts=vals,parent_state="V259")
ur=evaluate_reuse(node_object=uobj,proof=uproof,request={"action_payload":pu,"scientific_context":CTX,"required_validations":vals,"parent_state":"V259"})
assert ur["decision"]=="QUARANTINE" and "SCIENTIFIC_CONTEXT_UNBOUND_TO_ACTION_KEY" in ur["reasons"]

stale=make_reuse_proof(node_object=obj,scientific_context=CTX,validation_receipts=vals,parent_state="V258")
sr=evaluate_reuse(node_object=obj,proof=stale,request=req)
assert sr["decision"]=="VERIFY_ONLY" and "PARENT_STATE_MISMATCH_REQUIRES_SUPERSESSION_PROOF" in sr["reasons"]
missing_parent={"action_payload":p,"scientific_context":CTX,"required_validations":vals}
assert evaluate_reuse(node_object=obj,proof=proof,request=missing_parent)["decision"]=="QUARANTINE"

print(json.dumps({"status":"PASS","bound_exact_reuse":True,"same_context_same_action_key":True,"scientific_changes_invalidated":len(fields),"unbound_legacy_quarantined":True,"stale_parent_verify_only":True,"missing_parent_quarantined":True,"shard11_opened":False,"economic_data_read":False},sort_keys=True))
