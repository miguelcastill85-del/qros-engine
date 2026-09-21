from __future__ import annotations
import copy, json, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qros_recovery_verifier import canonical_bytes, git_blob_sha1, sha256_bytes, verify_recovery_root

def write(root: Path, rel: str, data: bytes):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)

def receipt(name: str) -> bytes:
    obj={"schema":"TEST_RECEIPT","name":name,"status":"PASS"}
    obj["receipt_sha256"]=sha256_bytes(canonical_bytes(obj))
    return json.dumps(obj,sort_keys=True,indent=2).encode()+b"\n"

def make_fixture(base: Path):
    pointer_path="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json"
    target_path="control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V259_v1.json"
    handoff_path="control/QROS_PUBLIC_1000_CURRENT_CHAT_HANDOFF.json"
    target_obj={"scientific_state":"PREREGISTERED_NO_RESULTS","shard11_open":False,"economic_pnl_read":False,"ga2_open":False,"holdout_open":False,
                "verified_counts":{"ga1_formally_completed_shards":10,"shards_total":60}}
    target=(json.dumps(target_obj,sort_keys=True)+"\n").encode(); target_blob=git_blob_sha1(target)
    pointer=(json.dumps({"current_version":"V259","target_path":target_path,"target_git_blob_sha1":target_blob},sort_keys=True)+"\n").encode()
    handoff=(json.dumps({"stable_frontier_version":"V259","stable_frontier_target_git_blob_sha1":target_blob},sort_keys=True)+"\n").encode()
    write(base,target_path,target); write(base,pointer_path,pointer); write(base,handoff_path,handoff)
    ev_path="evidence/a.json"; ev=receipt("a"); write(base,ev_path,ev)
    bin_path="evidence/b.bin"; binraw=b"\x00\xffBINARY"; write(base,bin_path,binraw)
    ledger_events=[
      {"artifact":"pointer","path":pointer_path,"git_blob_sha1":git_blob_sha1(pointer),"proposition":"frontier","type":"VALIDATED"},
      {"artifact":"evidence","path":ev_path,"git_blob_sha1":git_blob_sha1(ev),"proposition":"receipt","type":"VALIDATED"},
      {"artifact":"binary","path":bin_path,"git_blob_sha1":git_blob_sha1(binraw),"proposition":"binary","type":"VALIDATED"},
    ]
    lines=[];prev=None
    for i,event in enumerate(ledger_events):
        payload={"event":event,"previous":prev,"seq":i}; h=sha256_bytes(canonical_bytes(payload)); lines.append(json.dumps({"payload":payload,"sha256":h},sort_keys=True,separators=(",",":"))); prev=h
    ledger=("\n".join(lines)+"\n").encode(); ledger_path="ledger.jsonl"; write(base,ledger_path,ledger)
    code_paths={
      "event_canary":"research/ga1_compiled_dag_factor_ir_v1/qros_independent_event_canary.py",
      "factor_ir":"research/ga1_compiled_dag_factor_ir_v1/qros_factor_ir.py",
      "factor_ir_store":"research/ga1_compiled_dag_factor_ir_v1/qros_factor_ir_store.py",
      "geometry_compiler":"research/ga1_compiled_dag_factor_ir_v1/qros_geometry_compiler.py",
      "maskpack_regression":"research/ga1_compiled_dag_factor_ir_v1/qros_maskpack_regression.py",
      "typed_action":"research/ga1_compiled_dag_factor_ir_v1/qros_typed_action.py",
      "typed_dag":"research/ga1_compiled_dag_factor_ir_v1/qros_typed_dag.py",
      "recovery_verifier":"research/ga1_compiled_dag_factor_ir_v1/qros_recovery_verifier.py",
    }
    code={}
    for name,p in code_paths.items():
        b=(name+"-bytes").encode(); write(base,p,b); code[name]=git_blob_sha1(b)
    root={
      "schema":"QROS_GA1_EVIDENCE_NATIVE_RECOVERY_ROOT_1.0","status":"VERIFIED_RECOVERY_ROOT",
      "scientific_state":"PREREGISTERED_NO_RESULTS",
      "authority_vector":{"CODE_AUTHORITY":code,
        "OPERATIONAL_AUTHORITY":{"handoff_git_blob_sha1":git_blob_sha1(handoff),"seed0076_pointer_git_blob_sha1":git_blob_sha1(pointer)},
        "SCIENTIFIC_AUTHORITY":{"scientific_state":"PREREGISTERED_NO_RESULTS","shard11_open":False,"economic_pnl_read":False,"ga2_open":False,"holdout_open":False,"ga1_completed":10,"ga1_total":60}},
      "event_ledger":{"path":ledger_path,"file_sha256":sha256_bytes(ledger),"head_sha256":prev,"records":3},
      "reusable_evidence_set":[
        {"path":pointer_path,"git_blob_sha1":git_blob_sha1(pointer)},
        {"path":target_path,"git_blob_sha1":target_blob},
        {"path":ev_path,"git_blob_sha1":git_blob_sha1(ev)},
        {"path":bin_path,"git_blob_sha1":git_blob_sha1(binraw)}
      ],
      "verified_recovery_root":{"scientific_anchor":{"stable_frontier":"V259","target_git_blob_sha1":target_blob}},
    }
    root["recovery_root_sha256"]=sha256_bytes(canonical_bytes(root))
    rp=base/"root.json"; rp.write_text(json.dumps(root,indent=2,sort_keys=True)+"\n")
    return rp,root,{"pointer":pointer_path,"target":target_path,"handoff":handoff_path,"evidence":ev_path,"binary":bin_path,"ledger":ledger_path}

def rebuild_root(path: Path, root: dict):
    root=copy.deepcopy(root); root.pop("recovery_root_sha256",None); root["recovery_root_sha256"]=sha256_bytes(canonical_bytes(root)); path.write_text(json.dumps(root,indent=2,sort_keys=True)+"\n"); return root

def rebuild_ledger(base: Path, r: dict, rows: list[dict], ledger_path: str):
    prev=None; out=[]
    for i,row in enumerate(rows):
        row["payload"]["previous"]=prev; row["payload"]["seq"]=i; row["sha256"]=sha256_bytes(canonical_bytes(row["payload"])); prev=row["sha256"]; out.append(json.dumps(row,sort_keys=True,separators=(",",":")))
    raw=("\n".join(out)+"\n").encode(); (base/ledger_path).write_bytes(raw); r["event_ledger"].update({"file_sha256":sha256_bytes(raw),"head_sha256":prev,"records":len(rows)})
    return raw

def expect_fail(fn, token):
    try: fn(); raise AssertionError(token+"_ACCEPTED")
    except ValueError as e: assert token in str(e),(token,str(e))

with tempfile.TemporaryDirectory() as td:
    base=Path(td); rp,root,p=make_fixture(base)
    good=verify_recovery_root(base,rp); assert good["status"]=="PASS" and good["stable_frontier"]=="V259"

    b=Path(td)/"stale"; rp2,r2,p2=make_fixture(b)
    ptr={"current_version":"V258","target_path":p2["target"],"target_git_blob_sha1":git_blob_sha1((b/p2["target"]).read_bytes())}
    raw=(json.dumps(ptr,sort_keys=True)+"\n").encode(); (b/p2["pointer"]).write_bytes(raw); newblob=git_blob_sha1(raw)
    for row in r2["reusable_evidence_set"]:
        if row["path"]==p2["pointer"]: row["git_blob_sha1"]=newblob
    r2["authority_vector"]["OPERATIONAL_AUTHORITY"]["seed0076_pointer_git_blob_sha1"]=newblob
    rows=[json.loads(x) for x in (b/p2["ledger"]).read_text().splitlines()]; rows[0]["payload"]["event"]["git_blob_sha1"]=newblob
    rebuild_ledger(b,r2,rows,p2["ledger"]); rebuild_root(rp2,r2); expect_fail(lambda:verify_recovery_root(b,rp2),"STALE_POINTER_VERSION")

    b=Path(td)/"blob"; rp2,r2,p2=make_fixture(b); (b/p2["evidence"]).write_bytes(b"TAMPER"); expect_fail(lambda:verify_recovery_root(b,rp2),"GIT_BLOB_MISMATCH")
    b=Path(td)/"missing"; rp2,r2,p2=make_fixture(b); (b/p2["evidence"]).unlink(); expect_fail(lambda:verify_recovery_root(b,rp2),"MISSING_ARTIFACT")
    b=Path(td)/"ledger"; rp2,r2,p2=make_fixture(b); raw=bytearray((b/p2["ledger"]).read_bytes()); raw[-2]^=1; (b/p2["ledger"]).write_bytes(raw); expect_fail(lambda:verify_recovery_root(b,rp2),"LEDGER_FILE_SHA256_MISMATCH")
    b=Path(td)/"receipt"; rp2,r2,p2=make_fixture(b); obj=json.loads((b/p2["evidence"]).read_text()); obj["status"]="FAIL"; bad=(json.dumps(obj,sort_keys=True,indent=2)+"\n").encode(); (b/p2["evidence"]).write_bytes(bad); newblob=git_blob_sha1(bad)
    for row in r2["reusable_evidence_set"]:
        if row["path"]==p2["evidence"]: row["git_blob_sha1"]=newblob
    rows=[json.loads(x) for x in (b/p2["ledger"]).read_text().splitlines()]; rows[1]["payload"]["event"]["git_blob_sha1"]=newblob; rebuild_ledger(b,r2,rows,p2["ledger"]); rebuild_root(rp2,r2)
    expect_fail(lambda:verify_recovery_root(b,rp2),"RECEIPT_SELF_HASH_MISMATCH")
    b=Path(td)/"root"; rp2,r2,p2=make_fixture(b); r2["scientific_state"]="CHANGED"; rp2.write_text(json.dumps(r2,indent=2,sort_keys=True)+"\n"); expect_fail(lambda:verify_recovery_root(b,rp2),"RECOVERY_ROOT_SELF_HASH_MISMATCH")
    b=Path(td)/"path"; rp2,r2,p2=make_fixture(b); r2["reusable_evidence_set"][0]["path"]="../escape"; rebuild_root(rp2,r2); expect_fail(lambda:verify_recovery_root(b,rp2),"PATH_INVALID")
    b=Path(td)/"handoff"; rp2,r2,p2=make_fixture(b); h={"stable_frontier_version":"V258","stable_frontier_target_git_blob_sha1":git_blob_sha1((b/p2["target"]).read_bytes())}; raw=(json.dumps(h,sort_keys=True)+"\n").encode(); (b/p2["handoff"]).write_bytes(raw); r2["authority_vector"]["OPERATIONAL_AUTHORITY"]["handoff_git_blob_sha1"]=git_blob_sha1(raw); rebuild_root(rp2,r2); expect_fail(lambda:verify_recovery_root(b,rp2),"HANDOFF_FRONTIER_SPLIT")
    b=Path(td)/"firewall"; rp2,r2,p2=make_fixture(b); tobj=json.loads((b/p2["target"]).read_text()); tobj["shard11_open"]=True; traw=(json.dumps(tobj,sort_keys=True)+"\n").encode(); (b/p2["target"]).write_bytes(traw); newt=git_blob_sha1(traw)
    pobj=json.loads((b/p2["pointer"]).read_text()); pobj["target_git_blob_sha1"]=newt; praw=(json.dumps(pobj,sort_keys=True)+"\n").encode(); (b/p2["pointer"]).write_bytes(praw)
    hobj=json.loads((b/p2["handoff"]).read_text()); hobj["stable_frontier_target_git_blob_sha1"]=newt; hraw=(json.dumps(hobj,sort_keys=True)+"\n").encode(); (b/p2["handoff"]).write_bytes(hraw)
    for row in r2["reusable_evidence_set"]:
        if row["path"]==p2["target"]: row["git_blob_sha1"]=newt
        if row["path"]==p2["pointer"]: row["git_blob_sha1"]=git_blob_sha1(praw)
    r2["authority_vector"]["OPERATIONAL_AUTHORITY"]["seed0076_pointer_git_blob_sha1"]=git_blob_sha1(praw)
    r2["authority_vector"]["OPERATIONAL_AUTHORITY"]["handoff_git_blob_sha1"]=git_blob_sha1(hraw)
    r2["verified_recovery_root"]["scientific_anchor"]["target_git_blob_sha1"]=newt
    rows=[json.loads(x) for x in (b/p2["ledger"]).read_text().splitlines()]; rows[0]["payload"]["event"]["git_blob_sha1"]=git_blob_sha1(praw); rebuild_ledger(b,r2,rows,p2["ledger"]); rebuild_root(rp2,r2)
    expect_fail(lambda:verify_recovery_root(b,rp2),"SCIENTIFIC_FIREWALL_NOT_CLOSED:shard11_open")

    print(json.dumps({"status":"PASS","valid_fixture_pass":True,"binary_artifact_pass":True,"stale_pointer_rejected":True,"reference_tamper_rejected":True,"missing_artifact_rejected":True,"ledger_tamper_rejected":True,"receipt_self_hash_tamper_rejected":True,"root_self_hash_tamper_rejected":True,"path_traversal_rejected":True,"handoff_split_rejected":True,"scientific_firewall_open_rejected":True},sort_keys=True))
