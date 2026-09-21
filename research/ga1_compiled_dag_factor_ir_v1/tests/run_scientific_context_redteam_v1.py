from __future__ import annotations
import copy, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qros_scientific_context import *
from qros_typed_action import action_key

H=lambda s: hashlib.sha256(s.encode()).hexdigest()
CTX={
 "schema":SCHEMA,"campaign_id":"PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA","seed_id":"WEB_SEED_0076",
 "genealogy_id":"FRACTALBOX_3EMA","phase":"GA1","asset":"NQX","side":"BUY","timeframe":"M2",
 "development_period":{"start":"2018-01-01","end":"2019-12-31","timezone":"BROKER_FROZEN"},
 "scientific_state":"PREREGISTERED_NO_RESULTS","holdout_state":"CLOSED","exposure_state":"DEV_ONLY",
 "multiplicity_scope":"GA1_60_SHARDS","cost_model_id":"COST_MODEL_FROZEN_V1","gate_policy_id":"GA1_POLICY_V1",
 "selection_policy_id":"NO_ECONOMIC_SELECTION_PRE_GA1_COMPLETE",
 "thesis_fingerprint":H("thesis"),"data_context_fingerprint":H("data-context"),"extensions":{}
}
MAN={"schema":"QROS_TYPED_DAG_MANIFEST_1.0","nodes":[
 {"id":"a","operation":"EMIT","operation_version":"1","code_hashes":{"impl":H("code")},"domain":{"asset":"NQX","side":"BUY","timeframe":"M2"},"parameters":{"x":1},"static_inputs":{"fixture":H("fixture")},"environment":{"python":"test"},"deps":[]},
 {"id":"b","operation":"EMIT","operation_version":"1","code_hashes":{"impl":H("code")},"domain":{"asset":"NQX","side":"BUY","timeframe":"M2"},"parameters":{"x":2},"static_inputs":{"fixture":H("fixture2")},"environment":{"python":"test"},"deps":[]}
]}
orig=copy.deepcopy(MAN)
a=bind_scientific_context(MAN,CTX); b=bind_scientific_context(MAN,CTX)
assert MAN==orig and a==b
for n in a["manifest"]["nodes"]:
    assert n["static_inputs"][BINDING_INPUT]==a["scientific_context_sha256"]
def keys(compiled):
    out=[]
    for n in compiled["manifest"]["nodes"]:
        k,_=action_key(operation=n["operation"],operation_version=n["operation_version"],code_hashes=n["code_hashes"],domain=n["domain"],parameters=n["parameters"],input_artifacts=n["static_inputs"],environment=n["environment"])
        out.append(k)
    return out
base=keys(a)
changes=[
 ("genealogy_id","OTHER"),("development_period",{"start":"2020-01-01","end":"2021-12-31","timezone":"BROKER_FROZEN"}),
 ("holdout_state","EXPOSED"),("exposure_state","DEV_PLUS_DIAGNOSTIC"),("multiplicity_scope","OTHER_SCOPE"),
 ("cost_model_id","COST_V2"),("gate_policy_id","GATE_V2"),("selection_policy_id","SELECTION_V2"),
 ("thesis_fingerprint",H("other-thesis")),("data_context_fingerprint",H("other-data"))
]
changed=0
for field,val in changes:
    c=copy.deepcopy(CTX); c[field]=val; z=bind_scientific_context(MAN,c)
    assert z["scientific_context_sha256"]!=a["scientific_context_sha256"]
    assert all(x!=y for x,y in zip(base,keys(z))), field
    changed+=1
conf=copy.deepcopy(MAN); conf["nodes"][0]["static_inputs"][BINDING_INPUT]=H("manual")
try: bind_scientific_context(conf,CTX); raise AssertionError("RESERVED_CONFLICT_ACCEPTED")
except ValueError as e: assert "RESERVED_SCIENTIFIC_CONTEXT_INPUT_PRESENT" in str(e)
bad=copy.deepcopy(CTX); bad.pop("multiplicity_scope")
try: bind_scientific_context(MAN,bad); raise AssertionError("MISSING_CONTEXT_ACCEPTED")
except ValueError as e: assert "SCIENTIFIC_CONTEXT_FIELDS_INVALID" in str(e)
bad=copy.deepcopy(CTX); bad["unexpected"]="x"
try: bind_scientific_context(MAN,bad); raise AssertionError("EXTRA_CONTEXT_ACCEPTED")
except ValueError as e: assert "SCIENTIFIC_CONTEXT_FIELDS_INVALID" in str(e)
bad=copy.deepcopy(CTX); bad["thesis_fingerprint"]="xyz"
try: bind_scientific_context(MAN,bad); raise AssertionError("BAD_FINGERPRINT_ACCEPTED")
except ValueError as e: assert "THESIS_FINGERPRINT_INVALID" in str(e)
print(json.dumps({"status":"PASS","deterministic_same_context":True,"original_manifest_unchanged":True,"all_nodes_bound":2,"scientific_dimensions_changed_action_keys":changed,"reserved_key_conflict_rejected":True,"missing_field_rejected":True,"unknown_field_rejected":True,"bad_fingerprint_rejected":True},sort_keys=True))
