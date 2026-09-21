from __future__ import annotations
import hashlib, json, struct
from typing import Any
from qros_typed_action import validate_environment_manifest

NODE_MAGIC=b"QROS_TYPED_DAG_NODE_V1\n"
NODE_LEN=struct.Struct(">Q")
NODE_SCHEMA="QROS_TYPED_DAG_NODE_OBJECT_1.0"
PROOF_SCHEMA="QROS_REUSE_PROOF_1.1"
SCIENTIFIC_CONTEXT_INPUT="__scientific_context__"
DECISIONS={"REUSE","VERIFY_ONLY","QUARANTINE","INVALIDATE"}

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def scientific_context_hash(context: dict[str,Any]) -> str:
    if not isinstance(context,dict) or not context:
        raise ValueError("SCIENTIFIC_CONTEXT_REQUIRED")
    return sha256_bytes(canonical_bytes(context))

def _hex64(v:Any,label:str)->str:
    if not isinstance(v,str) or len(v)!=64:
        raise ValueError(label+"_INVALID")
    int(v,16)
    return v

def parse_node_object(data: bytes) -> dict[str,Any]:
    if not isinstance(data,(bytes,bytearray,memoryview)):
        raise ValueError("NODE_BYTES_REQUIRED")
    data=bytes(data)
    if not data.startswith(NODE_MAGIC):
        raise ValueError("NODE_MAGIC_MISMATCH")
    pos=len(NODE_MAGIC)
    if len(data)<pos+NODE_LEN.size:
        raise ValueError("NODE_TRUNCATED_LENGTH")
    (hlen,)=NODE_LEN.unpack_from(data,pos); pos+=NODE_LEN.size
    if hlen<=0 or hlen>64*1024*1024 or len(data)<pos+hlen:
        raise ValueError("NODE_HEADER_INVALID")
    hb=data[pos:pos+hlen]; pos+=hlen
    try: header=json.loads(hb.decode("utf-8"))
    except Exception as e: raise ValueError("NODE_HEADER_JSON_INVALID") from e
    if canonical_bytes(header)!=hb:
        raise ValueError("NODE_HEADER_NOT_CANONICAL")
    if header.get("schema")!=NODE_SCHEMA:
        raise ValueError("NODE_SCHEMA_MISMATCH")
    payload=header.get("action_payload")
    if not isinstance(payload,dict):
        raise ValueError("ACTION_PAYLOAD_MISSING")
    psha=sha256_bytes(canonical_bytes(payload))
    if header.get("action_payload_sha256")!=psha:
        raise ValueError("ACTION_PAYLOAD_SHA_MISMATCH")
    if header.get("action_key")!=psha:
        raise ValueError("ACTION_KEY_MISMATCH")
    output=data[pos:]
    if header.get("output_bytes")!=len(output):
        raise ValueError("OUTPUT_LENGTH_MISMATCH")
    if header.get("output_sha256")!=sha256_bytes(output):
        raise ValueError("OUTPUT_SHA_MISMATCH")
    return {"header":header,"payload":payload,"output":output,"object_sha256":sha256_bytes(data)}

def make_reuse_proof(*,node_object:bytes,scientific_context:dict[str,Any],
                     validation_receipts:dict[str,str],parent_state:str,status:str="VALIDATED")->dict[str,Any]:
    if not isinstance(parent_state,str) or not parent_state:
        raise ValueError("PARENT_STATE_REQUIRED")
    node=parse_node_object(node_object)
    sc_hash=scientific_context_hash(scientific_context)
    proof={
      "schema":PROOF_SCHEMA,
      "status":status,
      "artifact_sha256":node["object_sha256"],
      "action_key":node["header"]["action_key"],
      "scientific_context":scientific_context,
      "scientific_context_sha256":sc_hash,
      "scientific_context_binding_input":SCIENTIFIC_CONTEXT_INPUT,
      "validation_receipts":dict(sorted(validation_receipts.items())),
      "parent_state":parent_state,
    }
    for k,v in proof["validation_receipts"].items():
        if not isinstance(k,str) or not k: raise ValueError("VALIDATION_ID_INVALID")
        _hex64(v,"VALIDATION_HASH")
    proof["proof_sha256"]=sha256_bytes(canonical_bytes(proof))
    return proof

def _verify_proof(proof:dict[str,Any])->None:
    if not isinstance(proof,dict) or proof.get("schema")!=PROOF_SCHEMA:
        raise ValueError("PROOF_SCHEMA_INVALID")
    got=proof.get("proof_sha256")
    clean={k:v for k,v in proof.items() if k!="proof_sha256"}
    if got!=sha256_bytes(canonical_bytes(clean)):
        raise ValueError("PROOF_SELF_HASH_MISMATCH")
    _hex64(proof.get("artifact_sha256"),"ARTIFACT_SHA")
    _hex64(proof.get("action_key"),"ACTION_KEY")
    _hex64(proof.get("scientific_context_sha256"),"SCIENTIFIC_CONTEXT_SHA")
    if proof.get("scientific_context_binding_input")!=SCIENTIFIC_CONTEXT_INPUT:
        raise ValueError("SCIENTIFIC_CONTEXT_BINDING_LABEL_INVALID")
    if scientific_context_hash(proof.get("scientific_context"))!=proof["scientific_context_sha256"]:
        raise ValueError("SCIENTIFIC_CONTEXT_PROOF_HASH_MISMATCH")
    if not isinstance(proof.get("parent_state"),str) or not proof["parent_state"]:
        raise ValueError("PARENT_STATE_REQUIRED")
    vals=proof.get("validation_receipts")
    if not isinstance(vals,dict):
        raise ValueError("VALIDATION_RECEIPTS_INVALID")
    for k,v in vals.items():
        if not isinstance(k,str) or not k: raise ValueError("VALIDATION_ID_INVALID")
        _hex64(v,"VALIDATION_HASH")

def evaluate_reuse(*,node_object:bytes,proof:dict[str,Any],request:dict[str,Any])->dict[str,Any]:
    try:
        node=parse_node_object(node_object)
        _verify_proof(proof)
    except Exception as e:
        return {"decision":"INVALIDATE","reasons":[str(e)]}
    reasons=[]
    if proof.get("status")!="VALIDATED":
        return {"decision":"QUARANTINE","reasons":["PROOF_STATUS_NOT_VALIDATED"]}
    if proof["artifact_sha256"]!=node["object_sha256"]:
        return {"decision":"INVALIDATE","reasons":["ARTIFACT_CONTENT_MISMATCH"]}
    if proof["action_key"]!=node["header"]["action_key"]:
        return {"decision":"INVALIDATE","reasons":["PROOF_ACTION_KEY_MISMATCH"]}
    payload=node["payload"]
    try:
        validate_environment_manifest(payload.get("environment"))
    except Exception as e:
        return {"decision":"INVALIDATE","reasons":["ARTIFACT_ENVIRONMENT_INVALID:" + str(e)]}
    if not isinstance(request,dict):
        return {"decision":"QUARANTINE","reasons":["REQUEST_INVALID"]}
    expected_action=request.get("action_payload")
    expected_context=request.get("scientific_context")
    required_validations=request.get("required_validations",{})
    expected_parent=request.get("parent_state")
    if not isinstance(expected_action,dict) or not isinstance(expected_context,dict) or not expected_context:
        return {"decision":"QUARANTINE","reasons":["REQUEST_PROVENANCE_INCOMPLETE"]}
    try:
        validate_environment_manifest(expected_action.get("environment"))
    except Exception as e:
        return {"decision":"QUARANTINE","reasons":["REQUEST_ENVIRONMENT_INVALID:" + str(e)]}
    if not isinstance(expected_parent,str) or not expected_parent:
        return {"decision":"QUARANTINE","reasons":["REQUEST_PARENT_STATE_REQUIRED"]}
    if proof["parent_state"]!=expected_parent:
        return {"decision":"VERIFY_ONLY","reasons":["PARENT_STATE_MISMATCH_REQUIRES_SUPERSESSION_PROOF"]}
    if not isinstance(required_validations,dict):
        return {"decision":"QUARANTINE","reasons":["REQUIRED_VALIDATIONS_INVALID"]}

    for field,reason in [
        ("operation","SEMANTIC_OPERATION_MISMATCH"),
        ("operation_version","SEMANTIC_VERSION_MISMATCH"),
        ("code_hashes","CODE_IDENTITY_MISMATCH"),
        ("domain","DOMAIN_SEMANTICS_MISMATCH"),
        ("parameters","PARAMETER_SEMANTICS_MISMATCH"),
        ("input_artifacts","DEPENDENCY_IDENTITY_MISMATCH"),
        ("environment","ENVIRONMENT_INCOMPATIBLE"),
    ]:
        if payload.get(field)!=expected_action.get(field):
            reasons.append(reason)
    if reasons:
        return {"decision":"INVALIDATE","reasons":reasons}

    sc_hash=scientific_context_hash(expected_context)
    if proof["scientific_context_sha256"]!=sc_hash or proof["scientific_context"]!=expected_context:
        return {"decision":"INVALIDATE","reasons":["SCIENTIFIC_CONTEXT_MISMATCH"]}
    bound=payload.get("input_artifacts",{}).get(SCIENTIFIC_CONTEXT_INPUT)
    if bound is None:
        return {"decision":"QUARANTINE","reasons":["SCIENTIFIC_CONTEXT_UNBOUND_TO_ACTION_KEY"]}
    if bound!=sc_hash:
        return {"decision":"INVALIDATE","reasons":["SCIENTIFIC_CONTEXT_BINDING_MISMATCH"]}

    missing=[];mismatch=[]
    vals=proof["validation_receipts"]
    for vid,vhash in required_validations.items():
        try:_hex64(vhash,"REQUIRED_VALIDATION_HASH")
        except Exception:
            return {"decision":"QUARANTINE","reasons":["REQUIRED_VALIDATION_SPEC_INVALID"]}
        if vid not in vals: missing.append(vid)
        elif vals[vid]!=vhash: mismatch.append(vid)
    if mismatch:
        return {"decision":"INVALIDATE","reasons":["VALIDATION_RECEIPT_MISMATCH:"+",".join(sorted(mismatch))]}
    if missing:
        return {"decision":"VERIFY_ONLY","reasons":["VALIDATION_RECEIPT_MISSING:"+",".join(sorted(missing))]}

    return {
      "decision":"REUSE",
      "reasons":[],
      "artifact_sha256":node["object_sha256"],
      "action_key":node["header"]["action_key"],
      "scientific_context_sha256":sc_hash,
      "output_sha256":node["header"]["output_sha256"],
    }
