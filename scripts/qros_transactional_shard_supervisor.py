#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

CHUNK=1024*1024

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def sha256_file(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(CHUNK),b""): h.update(b)
    return h.hexdigest()

def fsync_file(path: Path):
    with path.open("rb") as f: os.fsync(f.fileno())

def fsync_dir(path: Path):
    fd=os.open(path,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def validate_manifest(m):
    required={"schema","seed","shard_count","total_signal_configs","shard_descriptor_root_sha256","shards"}
    miss=required-set(m)
    if miss: raise RuntimeError("MANIFEST_MISSING:"+",".join(sorted(miss)))
    if m["shard_count"]!=len(m["shards"]): raise RuntimeError("MANIFEST_SHARD_COUNT_MISMATCH")
    seen=set(); total=0; rows=[]
    for row in m["shards"]:
        d=row["descriptor"]; b=canonical(d); digest=hashlib.sha256(b).hexdigest()
        if row.get("descriptor_sha256")!=digest or row.get("shard_id")!=digest:
            raise RuntimeError("MANIFEST_DESCRIPTOR_HASH_MISMATCH")
        if digest in seen: raise RuntimeError("DUPLICATE_SHARD_ID")
        seen.add(digest); total+=int(d.get("signal_configs",d.get("work_units",0))); rows.append((b,digest))
    if total!=m["total_signal_configs"]: raise RuntimeError("MANIFEST_TOTAL_SIGNAL_CONFIG_MISMATCH")
    h=hashlib.sha256()
    for _,digest in sorted(rows,key=lambda x:x[0]): h.update(bytes.fromhex(digest))
    if h.hexdigest()!=m["shard_descriptor_root_sha256"]: raise RuntimeError("MANIFEST_ROOT_MISMATCH")

def validate_done(done_dir: Path, row: dict):
    rp=done_dir/"worker_receipt.json"
    if not rp.is_file(): return False,"DONE_RECEIPT_MISSING"
    try: r=load_json(rp)
    except Exception as e: return False,"DONE_RECEIPT_PARSE:"+type(e).__name__
    if r.get("status")!="PASS": return False,"DONE_STATUS_NOT_PASS"
    if r.get("shard_id")!=row["shard_id"]: return False,"DONE_SHARD_ID_MISMATCH"
    if r.get("descriptor_sha256")!=row["descriptor_sha256"]: return False,"DONE_DESCRIPTOR_HASH_MISMATCH"
    expected=int(row["descriptor"].get("signal_configs",row["descriptor"].get("work_units",0)))
    if r.get("processed_signal_configs",r.get("processed_work_units"))!=expected:
        return False,"DONE_WORK_COUNT_MISMATCH"
    arts=r.get("artifacts")
    if not isinstance(arts,list) or not arts: return False,"DONE_ARTIFACT_LIST_INVALID"
    for a in arts:
        rel=a.get("path")
        if not isinstance(rel,str) or rel.startswith("/") or ".." in Path(rel).parts: return False,"DONE_ARTIFACT_PATH_INVALID"
        p=done_dir/rel
        if not p.is_file(): return False,"DONE_ARTIFACT_MISSING:"+rel
        if p.stat().st_size!=a.get("bytes"): return False,"DONE_ARTIFACT_SIZE_MISMATCH:"+rel
        if sha256_file(p)!=a.get("sha256"): return False,"DONE_ARTIFACT_SHA_MISMATCH:"+rel
    return True,"PASS"

def append_recovery_log(path: Path, record: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    line=canonical(record)+b"\n"
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
    try:
        os.write(fd,line); os.fsync(fd)
    finally: os.close(fd)

def run_one(row, done_root: Path, tmp_root: Path, worker: Path, worker_extra: list[str], recovery_log: Path):
    sid=row["shard_id"]; done=done_root/sid
    if done.exists():
        ok,why=validate_done(done,row)
        if ok: return {"shard_id":sid,"action":"SKIP_VALID_DONE","status":"PASS"}
        raise RuntimeError(f"INVALID_EXISTING_DONE:{sid}:{why}")
    prefix=sid+".tmp."
    for p in sorted(tmp_root.glob(prefix+"*")):
        append_recovery_log(recovery_log,{"event":"ABANDON_INCOMPLETE_TEMP","shard_id":sid,"temp_name":p.name})
        if p.is_dir(): shutil.rmtree(p)
        else: p.unlink()
    tmp=Path(tempfile.mkdtemp(prefix=prefix,dir=tmp_root))
    shard_json=tmp/"shard.json"; receipt=tmp/"worker_receipt.json"
    shard_json.write_text(json.dumps(row,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    cmd=[sys.executable,str(worker),"--shard-json",str(shard_json),"--out-dir",str(tmp),"--receipt",str(receipt),*worker_extra]
    cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    (tmp/"worker.stdout.txt").write_text(cp.stdout,encoding="utf-8")
    (tmp/"worker.stderr.txt").write_text(cp.stderr,encoding="utf-8")
    if cp.returncode!=0:
        append_recovery_log(recovery_log,{"event":"WORKER_FAILED","shard_id":sid,"returncode":cp.returncode,"temp_name":tmp.name})
        raise RuntimeError(f"WORKER_FAILED:{sid}:{cp.returncode}")
    ok,why=validate_done(tmp,row)
    if not ok:
        append_recovery_log(recovery_log,{"event":"WORKER_OUTPUT_INVALID","shard_id":sid,"reason":why,"temp_name":tmp.name})
        raise RuntimeError(f"WORKER_OUTPUT_INVALID:{sid}:{why}")
    for p in tmp.rglob("*"):
        if p.is_file(): fsync_file(p)
    fsync_dir(tmp)
    os.replace(tmp,done)
    fsync_dir(done_root)
    ok,why=validate_done(done,row)
    if not ok: raise RuntimeError(f"POST_PROMOTION_VALIDATION_FAIL:{sid}:{why}")
    return {"shard_id":sid,"action":"PROMOTE_ATOMIC_DONE","status":"PASS"}

def root_of_done(done_root: Path, rows: list[dict]):
    leaves=[]
    for row in rows:
        d=done_root/row["shard_id"]
        ok,why=validate_done(d,row)
        if not ok: raise RuntimeError(f"GLOBAL_DONE_INVALID:{row['shard_id']}:{why}")
        r=load_json(d/"worker_receipt.json")
        leaf={"shard_id":row["shard_id"],"descriptor_sha256":row["descriptor_sha256"],
              "processed_signal_configs":r.get("processed_signal_configs",r.get("processed_work_units")),
              "artifacts":r["artifacts"]}
        leaves.append(canonical(leaf))
    h=hashlib.sha256()
    for b in sorted(leaves): h.update(hashlib.sha256(b).digest())
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",required=True); ap.add_argument("--work-root",required=True); ap.add_argument("--worker",required=True)
    ap.add_argument("--worker-extra",action="append",default=[]); ap.add_argument("--only-shard"); ap.add_argument("--max-shards",type=int)
    ap.add_argument("--summary",required=True)
    ns=ap.parse_args()
    m=load_json(Path(ns.manifest)); validate_manifest(m)
    wr=Path(ns.work_root); done=wr/"done"; tmp=wr/"tmp"; done.mkdir(parents=True,exist_ok=True); tmp.mkdir(parents=True,exist_ok=True)
    rows=m["shards"]
    if ns.only_shard: rows=[r for r in rows if r["shard_id"]==ns.only_shard]
    if ns.max_shards is not None: rows=rows[:ns.max_shards]
    actions=[]; status="PASS"; error=None
    try:
        for row in rows:
            actions.append(run_one(row,done,tmp,Path(ns.worker),ns.worker_extra,wr/"recovery_log.jsonl"))
    except Exception as e:
        status="FAIL"; error=f"{type(e).__name__}:{e}"
    valid_done=0
    for row in m["shards"]:
        d=done/row["shard_id"]
        if d.exists():
            ok,_=validate_done(d,row)
            if ok: valid_done+=1
    summary={"schema":"QROS_TRANSACTIONAL_SHARD_SUPERVISOR_SUMMARY_1.0","status":status,"seed":m["seed"],
             "manifest_root_sha256":m["shard_descriptor_root_sha256"],"target_shards":len(m["shards"]),
             "valid_done_shards":valid_done,"actions":actions,"error":error}
    if status=="PASS" and valid_done==len(m["shards"]):
        summary["global_done_root_sha256"]=root_of_done(done,m["shards"])
        summary["decision"]="ALL_SHARDS_COMPLETE"
    elif status=="PASS":
        summary["decision"]="PARTIAL_VALID_PROGRESS"
    else:
        summary["decision"]="STOPPED_FAIL_CLOSED"
    payload=canonical(summary); summary["summary_sha256"]=hashlib.sha256(payload).hexdigest()
    Path(ns.summary).write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(summary["decision"])
    return 0 if status=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
