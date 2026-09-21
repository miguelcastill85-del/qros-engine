from __future__ import annotations
import hashlib, json, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qros_recovery_root_verifier import canonical_bytes, git_blob_sha1, sha256_bytes, verify_recovery_root

def write(p: Path, b: bytes):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b)

def receipt(name):
    o={"schema":"TEST_RECEIPT","name":name,"status":"PASS"}
    o["receipt_sha256"]=sha256_bytes(canonical_bytes(o))
    return canonical_bytes(o)

def make_fixture(base: Path):
    art_json=base/"control"/"a.json"; rawj=receipt("a"); write(art_json,rawj)
    art_bin=base/"data"/"b.bin"; rawb=b"\x00\xffBINARY"; write(art_bin,rawb)
    events=[]
    prev=None
    for i,(name,rel,raw,typ) in enumerate([
        ("a","control/a.json",rawj,"VALIDATED"),
        ("b","data/b.bin",rawb,"VALIDATED"),
    ]):
        payload={"seq":i,"previous":prev,"event":{"artifact":name,"path":rel,"git_blob_sha1":git_blob_sha1(raw),"type":typ,"proposition":"fixture"}}
        h=sha256_bytes(canonical_bytes(payload)); events.append({"payload":payload,"sha256":h}); prev=h
    ledger_raw=("".join(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n" for x in events)).encode()
    lrel="research/ledger.jsonl"; write(base/lrel,ledger_raw)
    root={
      "schema":"QROS_GA1_EVIDENCE_NATIVE_RECOVERY_ROOT_1.0",
      "status":"VERIFIED_RECOVERY_ROOT",
      "event_ledger":{"path":lrel,"file_sha256":sha256_bytes(ledger_raw),"head_sha256":prev,"records":2},
      "reusable_evidence_set":[
        {"path":"control/a.json","git_blob_sha1":git_blob_sha1(rawj)},
        {"path":"data/b.bin","git_blob_sha1":git_blob_sha1(rawb)}
      ]
    }
    root["recovery_root_sha256"]=sha256_bytes(canonical_bytes(root))
    rrel="research/root.json"; write(base/rrel,json.dumps(root,indent=2,sort_keys=True).encode()+b"\n")
    return rrel,root

def expect_fail(base,rrel,token):
    try: verify_recovery_root(base,rrel); raise AssertionError("EXPECTED_FAIL:"+token)
    except ValueError as e: assert token in str(e),(token,str(e))

with tempfile.TemporaryDirectory() as td:
    base=Path(td); rrel,root=make_fixture(base)
    ok=verify_recovery_root(base,rrel)
    assert ok["reusable_artifacts_verified"]==2
    rpath=base/rrel; original=rpath.read_bytes(); o=json.loads(original); o["status"]="X"; write(rpath,json.dumps(o).encode()); expect_fail(base,rrel,"RECOVERY_ROOT_STATUS_INVALID"); write(rpath,original)
    lp=base/root["event_ledger"]["path"]; lorig=lp.read_bytes(); x=bytearray(lorig); x[0]^=1; write(lp,bytes(x)); expect_fail(base,rrel,"LEDGER_FILE_SHA256_MISMATCH"); write(lp,lorig)
    ap=base/"data/b.bin"; araw=ap.read_bytes(); ap.unlink(); expect_fail(base,rrel,"ARTIFACT_MISSING"); write(ap,araw)
    ap.write_bytes(b"different"); expect_fail(base,rrel,"ARTIFACT_BLOB_SHA1_MISMATCH"); write(ap,araw)
    jp=base/"control/a.json"; jo=json.loads(jp.read_bytes()); jo["status"]="FAIL"; badj=canonical_bytes(jo); write(jp,badj)
    lines=[json.loads(x) for x in lorig.decode().splitlines()]
    lines[0]["payload"]["event"]["git_blob_sha1"]=git_blob_sha1(badj)
    prev=None
    for i,row in enumerate(lines):
        row["payload"]["previous"]=prev; row["sha256"]=sha256_bytes(canonical_bytes(row["payload"])); prev=row["sha256"]
    newledger=("".join(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n" for x in lines)).encode(); write(lp,newledger)
    ro=json.loads(original); ro["event_ledger"].update({"file_sha256":sha256_bytes(newledger),"head_sha256":prev}); ro["reusable_evidence_set"][0]["git_blob_sha1"]=git_blob_sha1(badj); ro["recovery_root_sha256"]=sha256_bytes(canonical_bytes({k:v for k,v in ro.items() if k!="recovery_root_sha256"})); write(rpath,json.dumps(ro).encode())
    expect_fail(base,rrel,"RECEIPT_SELF_HASH_MISMATCH")
    rrel,root=make_fixture(base); ro=json.loads((base/rrel).read_bytes()); ro["reusable_evidence_set"][0]["path"]="../escape"; ro["recovery_root_sha256"]=sha256_bytes(canonical_bytes({k:v for k,v in ro.items() if k!="recovery_root_sha256"})); write(base/rrel,json.dumps(ro).encode()); expect_fail(base,rrel,"ARTIFACT_PATH_INVALID")
    print(json.dumps({"status":"PASS","valid_root_pass":True,"non_json_artifact_accepted":True,"root_tamper_rejected":True,"ledger_tamper_rejected":True,"missing_artifact_rejected":True,"blob_drift_rejected":True,"receipt_self_hash_drift_rejected":True,"path_traversal_rejected":True},sort_keys=True))
