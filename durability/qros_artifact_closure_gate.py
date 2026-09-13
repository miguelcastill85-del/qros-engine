#!/usr/bin/env python3
"""QROS deterministic artifact durability closure gate (stdlib only)."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, shutil, tempfile

SCHEMA = "QROS_ARTIFACT_DURABILITY_CLOSURE_GATE_V2"

def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()

def evaluate(manifest: dict, roots: dict[str, pathlib.Path]) -> dict:
    errors, objects = [], []
    if manifest.get("schema") != SCHEMA:
        errors.append("SCHEMA_MISMATCH")
    if not manifest.get("stage_id") or not manifest.get("next_stage_id"):
        errors.append("STAGE_ID_REQUIRED")
    stores = manifest.get("durable_stores", [])
    declared_ids=[s.get("id") for s in stores]
    if len(declared_ids) != len(set(declared_ids)):
        errors.append("DUPLICATE_STORE_ID")
    if len({s.get("id") for s in stores if s.get("independent") is True}) < 2:
        errors.append("TWO_INDEPENDENT_DURABLE_STORES_REQUIRED")
    object_ids=[x.get("id") for x in manifest.get("objects",[])]
    if len(object_ids) != len(set(object_ids)):
        errors.append("DUPLICATE_OBJECT_ID")
    for item in sorted(manifest.get("objects", []), key=lambda x: x.get("id", "")):
        oid, expected = item.get("id"), item.get("sha256")
        if not oid or not expected or len(expected) != 64:
            errors.append(f"INVALID_OBJECT_IDENTITY:{oid}"); continue
        copies=[]
        for sid in item.get("required_store_ids", []):
            if sid not in declared_ids:
                errors.append(f"UNDECLARED_STORE:{oid}:{sid}"); continue
            root=roots.get(sid)
            rel=item.get("store_paths", {}).get(sid)
            if root is None or not rel:
                errors.append(f"STORE_MAPPING_MISSING:{oid}:{sid}"); continue
            p=(root/rel).resolve()
            if root.resolve() not in p.parents:
                errors.append(f"PATH_ESCAPE:{oid}:{sid}"); continue
            if not p.is_file():
                errors.append(f"BYTES_MISSING:{oid}:{sid}"); continue
            actual=sha256(p); size=p.stat().st_size
            if actual != expected: errors.append(f"HASH_MISMATCH:{oid}:{sid}")
            if size != item.get("bytes"): errors.append(f"SIZE_MISMATCH:{oid}:{sid}")
            copies.append({"store_id":sid,"sha256":actual,"bytes":size})
        if len(copies) < 2: errors.append(f"INSUFFICIENT_VERIFIED_COPIES:{oid}")
        objects.append({"id":oid,"copies":copies})
    required={"PAYLOAD","SOURCE","INPUT_MANIFEST","OUTPUT_MANIFEST","DEPENDENCY_DAG","NEXT_STAGE_PACKET"}
    roles={x.get("role") for x in manifest.get("objects",[])}
    for role in sorted(required-roles): errors.append(f"MISSING_ROLE:{role}")
    if manifest.get("runtime_sandbox_is_authority") is not False:
        errors.append("RUNTIME_AUTHORITY_FORBIDDEN")
    if manifest.get("holdout_accessed") is not False:
        errors.append("HOLDOUT_STATE_NOT_CLEANLY_DECLARED")
    body={"schema":"QROS_ARTIFACT_DURABILITY_CLOSURE_RECEIPT_V2","stage_id":manifest.get("stage_id"),
          "manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest(),"objects":objects,
          "errors":sorted(set(errors)),"decision":"GATE_CLOSE_FORBIDDEN" if errors else "GATE_CLOSE_AUTHORIZED"}
    return body

def restore_canary(manifest: dict, roots: dict[str,pathlib.Path], receipt: dict) -> dict:
    errors=[]
    with tempfile.TemporaryDirectory(prefix="qros-restore-") as td:
        target=pathlib.Path(td)
        for item in sorted(manifest.get("objects",[]),key=lambda x:x["id"]):
            restored=None
            for sid in item["required_store_ids"]:
                p=(roots[sid]/item["store_paths"][sid]).resolve()
                if p.is_file() and sha256(p)==item["sha256"]:
                    restored=target/item["id"]; shutil.copyfile(p,restored); break
            if restored is None or sha256(restored)!=item["sha256"]:
                errors.append(f"RESTORE_FAILED:{item['id']}")
    return {"decision":"RESTORE_PASS" if not errors and receipt["decision"]=="GATE_CLOSE_AUTHORIZED" else "RESTORE_FAIL","errors":errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",required=True); ap.add_argument("--store",action="append",default=[]); ap.add_argument("--out",required=True)
    ns=ap.parse_args(); manifest=json.loads(pathlib.Path(ns.manifest).read_text())
    roots={k:pathlib.Path(v) for k,v in (x.split("=",1) for x in ns.store)}
    receipt=evaluate(manifest,roots); receipt["restore"]=restore_canary(manifest,roots,receipt)
    if receipt["restore"]["decision"]!="RESTORE_PASS": receipt["decision"]="GATE_CLOSE_FORBIDDEN"
    receipt["receipt_sha256"]=hashlib.sha256(canonical(receipt)).hexdigest()
    pathlib.Path(ns.out).write_bytes(canonical(receipt)); raise SystemExit(0 if receipt["decision"]=="GATE_CLOSE_AUTHORIZED" else 2)

if __name__ == "__main__": main()
