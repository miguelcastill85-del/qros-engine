from __future__ import annotations
import copy, hashlib, json, tempfile
from pathlib import Path
import qros_typed_dag
from qros_scientific_context import BINDING_INPUT
from qros_scientific_dag import compile_scientific_manifest, execute_scientific_manifest, validate_scientific_run

ENV={"python":"3.13.5","implementation":"CPython","platform":"fixture-linux","numpy":"2.3.5","numba":"0.65.1","byteorder":"little"}

H=lambda s: hashlib.sha256(s.encode()).hexdigest()

def base_manifest():
    return {
      "schema":"QROS_TYPED_DAG_MANIFEST_1.0",
      "nodes":[
        {"id":"a","operation":"emit","operation_version":"1","code_hashes":{"emit":H("code-a")},
         "domain":{"asset":"NQX","timeframe":"M2"},"parameters":{"x":1},
         "static_inputs":{"fixture":H("fixture-a")},"environment":ENV,"deps":[]},
        {"id":"b","operation":"join","operation_version":"1","code_hashes":{"join":H("code-b")},
         "domain":{"asset":"NQX","timeframe":"M2"},"parameters":{"y":2},
         "static_inputs":{"fixture":H("fixture-b")},"environment":ENV,"deps":["a"]},
      ]
    }

def context(tag="A"):
    return {
      "schema":"QROS_SCIENTIFIC_CONTEXT_1.0",
      "campaign_id":"PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA",
      "seed_id":"WEB_SEED_0076",
      "genealogy_id":"SEED0076_GA1",
      "phase":"GA1_ARCHITECTURE_RESEARCH_"+tag,
      "asset":"NQX","side":"BUY","timeframe":"M2",
      "development_period":{"start":"2018-01-01","end":"2026-09-20","timezone":"BROKER_DARWINEX"},
      "scientific_state":"PREREGISTERED_NO_RESULTS",
      "holdout_state":"CLOSED","exposure_state":"DEV_ONLY",
      "multiplicity_scope":"GA1_SEED0076",
      "cost_model_id":"CLOSED_NOT_EVALUATED",
      "gate_policy_id":"V259",
      "selection_policy_id":"FROZEN_NO_RESULTS",
      "thesis_fingerprint":H("thesis"),
      "data_context_fingerprint":H("data"),
      "extensions":{"tag":tag},
    }

def emit(payload,deps):
    return ("emit:"+payload["input_artifacts"][BINDING_INPUT]).encode()

def join(payload,deps):
    return deps["a"] + b"|join|" + payload["input_artifacts"][BINDING_INPUT].encode()

ops={"emit":emit,"join":join}
m=base_manifest(); c=context("A")
m_before=copy.deepcopy(m); c_before=copy.deepcopy(c)
compiled=compile_scientific_manifest(m,c)
assert m==m_before and c==c_before
assert qros_typed_dag.EXECUTION_CONTRACT=="TECHNICAL_ONLY_UNBOUND_MANIFESTS_NOT_SCIENTIFICALLY_ADMISSIBLE"
assert all(n["static_inputs"][BINDING_INPUT]==compiled["scientific_context_sha256"] for n in compiled["manifest"]["nodes"])

m["nodes"][0]["parameters"]["x"]=999
c["extensions"]["tag"]="MUTATED"
assert compiled["manifest"]["nodes"][0]["parameters"]["x"]==1
assert compiled["scientific_context"]["extensions"]["tag"]=="A"

bad=base_manifest(); bad["nodes"][0]["static_inputs"][BINDING_INPUT]=H("attacker")
try:
    compile_scientific_manifest(bad, context("A"))
    raise AssertionError("reserved-key bypass accepted")
except ValueError as e:
    assert "RESERVED_SCIENTIFIC_CONTEXT_INPUT_PRESENT" in str(e)

badc=context("A"); del badc["gate_policy_id"]
try:
    compile_scientific_manifest(base_manifest(),badc)
    raise AssertionError("missing context accepted")
except ValueError as e:
    assert "SCIENTIFIC_CONTEXT_FIELDS_INVALID" in str(e)

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    r1=execute_scientific_manifest(base_manifest(),context("A"),td,ops)
    v1=validate_scientific_run(base_manifest(),context("A"),td)
    r2=execute_scientific_manifest(base_manifest(),context("A"),td,ops)
    assert r1["executed_nodes"]==2 and r1["reused_nodes"]==0
    assert r2["executed_nodes"]==0 and r2["reused_nodes"]==2
    assert v1["status"]=="PASS" and v1["node_count"]==2
    keysA={k:v["action_key"] for k,v in r1["nodes"].items()}

    rB=execute_scientific_manifest(base_manifest(),context("B"),td,ops)
    keysB={k:v["action_key"] for k,v in rB["nodes"].items()}
    assert rB["executed_nodes"]==2 and rB["reused_nodes"]==0
    assert set(keysA)==set(keysB)
    assert all(keysA[k]!=keysB[k] for k in keysA), (keysA,keysB)

with tempfile.TemporaryDirectory() as td:
    raw=qros_typed_dag.execute_manifest(base_manifest(),td,{"emit":lambda payload,deps:b"raw-a","join":lambda payload,deps:deps["a"]+b"|raw-b"})
    assert raw["status"]=="PASS"
    assert qros_typed_dag.EXECUTION_CONTRACT.startswith("TECHNICAL_ONLY_")

out={
  "status":"PASS",
  "tests":{
    "raw_executor_contract_technical_only":True,
    "scientific_wrapper_binds_every_node":True,
    "original_manifest_immutable":True,
    "original_context_immutable":True,
    "reserved_binding_bypass_rejected":True,
    "missing_context_rejected":True,
    "same_context_warm_reuse":True,
    "changed_context_invalidates_all_action_keys":True,
    "scientific_run_receipt_validates":True,
    "raw_direct_call_labeled_non_scientific":True,
  },
  "action_key_propagation_changed_nodes":2,
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
