#!/usr/bin/env python3
"""QROS v3 stateless receipt/provenance guard, extracted for v2.2 single-owner use.

No process spawn, retries, state transitions, Git/Drive access, or scientific promotion.
The contract must be pre-pinned via SHA-256 in the frozen stage's input manifest.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, re, tempfile

SCHEMA="QROS_V3_STATELESS_GUARD_CONTRACT_V1"
PROOF_SCHEMA="QROS_V3_STATELESS_GUARD_RECEIPT_V1"
H64=re.compile(r"^[0-9a-f]{64}$")
H40=re.compile(r"^[0-9a-f]{40}$")
class GuardFailure(ValueError): pass

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def inside(root,name,output=False):
    if not isinstance(name,str) or not name or name.startswith("/") or "\\" in name or "\x00" in name:
        raise GuardFailure("UNSAFE_PATH")
    parts=name.split("/")
    if any(p in ("",".","..") for p in parts):
        raise GuardFailure("UNSAFE_PATH")
    here=root
    for part in parts:
        here=here/part
        if here.is_symlink(): raise GuardFailure("SYMLINK_FORBIDDEN:"+name)
    resolved=here.resolve()
    if not resolved.is_relative_to(root) or resolved==root:raise GuardFailure("PATH_ESCAPE")
    if not output and not resolved.is_file():raise GuardFailure("REQUIRED_FILE_ABSENT:"+name)
    return resolved

def read_frozen_contract(root,contract_name,contract_pin):
    if not isinstance(contract_pin,str) or not H64.fullmatch(contract_pin):
        raise GuardFailure("EXTERNAL_CONTRACT_SHA_REQUIRED")
    path=inside(root,contract_name)
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=contract_pin:
        raise GuardFailure("EXTERNAL_CONTRACT_PIN_DRIFT")
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("schema")!=SCHEMA:
        raise GuardFailure("BAD_CONTRACT_SCHEMA")
    a=obj.get("authority")
    if (not isinstance(a,dict) or not a.get("repo") or not a.get("branch")
        or not isinstance(a.get("base_commit"),str) or not H40.fullmatch(a["base_commit"])):
        raise GuardFailure("AUTHORITY_NOT_FROZEN")
    for key in ("lane_id","stage_id"):
        if not isinstance(obj.get(key),str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,128}",obj[key]):
            raise GuardFailure("INVALID_"+key.upper())
    exp=obj.get("expected_receipt")
    if (not isinstance(exp,dict) or not isinstance(exp.get("job_id"),str)
        or not exp["job_id"] or not isinstance(exp.get("spec_sha256"),str)
        or not H64.fullmatch(exp["spec_sha256"])):
        raise GuardFailure("FROZEN_WORKER_IDENTITY_REQUIRED")
    outputs=obj.get("artifacts")
    if not isinstance(outputs,list) or not outputs:
        raise GuardFailure("FROZEN_ARTIFACTS_REQUIRED")
    names=[]
    for item in outputs:
        if not isinstance(item,dict) or not isinstance(item.get("path"),str):
            raise GuardFailure("BAD_ARTIFACT_CONTRACT")
        inside(root,item["path"],output=True)
        if type(item.get("bytes")) is not int or item["bytes"]<0:
            raise GuardFailure("FROZEN_ARTIFACT_SIZE_REQUIRED")
        if not isinstance(item.get("sha256"),str) or not H64.fullmatch(item["sha256"]):
            raise GuardFailure("FROZEN_ARTIFACT_HASH_REQUIRED")
        names.append(item["path"])
    if len(set(names))!=len(names):raise GuardFailure("DUPLICATED_ARTIFACT")
    rec=obj.get("worker_receipt");proof=obj.get("proof_path")
    if rec in names or proof in names or rec==proof:
        raise GuardFailure("RECEIPT_OUTPUT_COLLISION")
    inside(root,rec,output=True);inside(root,proof,output=True)
    if not proof.endswith(".json"):raise GuardFailure("PROOF_MUST_BE_JSON")
    return obj

def independently_attest(root,contract_name,contract_pin):
    root=pathlib.Path(root).resolve()
    obj=read_frozen_contract(root,contract_name,contract_pin)
    rp=inside(root,obj["worker_receipt"])
    rec=json.loads(rp.read_bytes())
    if not isinstance(rec,dict):raise GuardFailure("WORKER_RECEIPT_INVALID")
    for k,v in obj["expected_receipt"].items():
        if rec.get(k)!=v:raise GuardFailure("WORKER_IDENTITY_MISMATCH:"+k)
    arts=rec.get("artifacts")
    if not isinstance(arts,list) or len(arts)!=len(obj["artifacts"]):
        raise GuardFailure("WORKER_ARTIFACT_CARDINALITY")
    observed=[]
    for pin,claim in zip(obj["artifacts"],arts):
        if not isinstance(claim,dict) or claim.get("path")!=pin["path"]:
            raise GuardFailure("WORKER_ARTIFACT_ORDER_OR_PATH_DRIFT")
        if type(claim.get("bytes")) is not int or claim["bytes"]!=pin["bytes"]:
            raise GuardFailure("WORKER_ARTIFACT_SIZE_CLAIM_DRIFT")
        if claim.get("sha256")!=pin["sha256"]:
            raise GuardFailure("WORKER_ARTIFACT_SHA_CLAIM_DRIFT")
        f=inside(root,pin["path"])
        if f.stat().st_size!=pin["bytes"] or sha256_file(f)!=pin["sha256"]:
            raise GuardFailure("PHYSICAL_ARTIFACT_BYTES_MISMATCH")
        observed.append({"path":pin["path"],"bytes":pin["bytes"],"sha256":pin["sha256"]})
    proof={
        "schema":PROOF_SCHEMA,
        "status":"PASS_FROZEN_PHYSICAL_ARTIFACTS",
        "lane_id":obj["lane_id"],"stage_id":obj["stage_id"],
        "authority":obj["authority"],"contract_sha256":contract_pin,
        "worker_receipt_sha256":sha256_file(rp),
        "artifacts":observed,
        "scientific_promotion":False,
        "external_data_readback_proven":False
    }
    dest=inside(root,obj["proof_path"],output=True)
    raw=json.dumps(proof,sort_keys=True,separators=(",",":"),allow_nan=False).encode()+b"\n"
    if dest.exists():
        if not dest.is_file() or dest.read_bytes()!=raw:
            raise GuardFailure("EXISTING_PROOF_DRIFT")
    else:
        dest.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=".guard.",dir=str(dest.parent))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
            if os.name=="posix":
                d=os.open(dest.parent,os.O_RDONLY)
                try:os.fsync(d)
                finally:os.close(d)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return proof
