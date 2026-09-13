#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def make_manifest(path):
    rows=[]
    for asset in ("XAUUSD","NQX"):
        for side in ("BUY","SELL"):
            d={"asset":asset,"side":side,"timeframe":"M1","work_units":37,"signal_configs":37}
            b=canonical(d); sid=hashlib.sha256(b).hexdigest()
            rows.append({"descriptor":d,"descriptor_sha256":sid,"shard_id":sid})
    rows.sort(key=lambda r:canonical(r["descriptor"]))
    h=hashlib.sha256()
    for r in rows: h.update(bytes.fromhex(r["descriptor_sha256"]))
    m={"schema":"QROS_SYNTH_SHARD_MANIFEST_1.0","seed":"SYNTH_TEST","shard_count":len(rows),
       "total_signal_configs":sum(r["descriptor"]["signal_configs"] for r in rows),
       "shard_descriptor_root_sha256":h.hexdigest(),"shards":rows}
    path.write_text(json.dumps(m,sort_keys=True,indent=2)+"\n",encoding="utf-8"); return m

def run(supervisor,manifest,work,worker,summary,env=None):
    cmd=[sys.executable,str(supervisor),"--manifest",str(manifest),"--work-root",str(work),"--worker",str(worker),
         "--worker-extra=--synthetic","--summary",str(summary)]
    return subprocess.run(cmd,text=True,capture_output=True,env=env)

def main():
    repo=Path(__file__).resolve().parents[1]
    supervisor=repo/"scripts/qros_transactional_shard_supervisor.py"; worker=repo/"scripts/qros_synthetic_shard_worker.py"
    td=Path(tempfile.mkdtemp(prefix="qros_shard_test_"))
    result={"schema":"QROS_TRANSACTIONAL_SHARD_SYNTHETIC_TEST_RECEIPT_1.0","tests":[],"status":"FAIL"}
    try:
        manifest=td/"manifest.json"; m=make_manifest(manifest); work=td/"work"
        fail_sid=m["shards"][1]["shard_id"]; marker=td/"fail_once.marker"
        env=os.environ.copy(); env["QROS_SYNTH_FAIL_ONCE_SHARD"]=fail_sid; env["QROS_SYNTH_FAIL_ONCE_MARKER"]=str(marker)
        s1=td/"summary1.json"; cp1=run(supervisor,manifest,work,worker,s1,env)
        j1=json.loads(s1.read_text()); t1=(cp1.returncode!=0 and j1["decision"]=="STOPPED_FAIL_CLOSED" and j1["valid_done_shards"]==1 and marker.exists())
        result["tests"].append({"id":"FAIL_CLOSED_ON_WORKER_CRASH","pass":t1,"returncode":cp1.returncode,"valid_done_after":j1["valid_done_shards"]})
        first_done=m["shards"][0]["shard_id"]; done_receipt=work/"done"/first_done/"worker_receipt.json"
        preserved_before=hashlib.sha256(done_receipt.read_bytes()).hexdigest()
        s2=td/"summary2.json"; cp2=run(supervisor,manifest,work,worker,s2,env); j2=json.loads(s2.read_text())
        preserved_after=hashlib.sha256(done_receipt.read_bytes()).hexdigest()
        t2=(cp2.returncode==0 and j2["decision"]=="ALL_SHARDS_COMPLETE" and j2["valid_done_shards"]==4 and preserved_before==preserved_after and
            any(a["action"]=="SKIP_VALID_DONE" and a["shard_id"]==first_done for a in j2["actions"]))
        result["tests"].append({"id":"RESUME_SKIPS_VALID_DONE","pass":t2,"global_done_root_sha256":j2.get("global_done_root_sha256")})
        s3=td/"summary3.json"; cp3=run(supervisor,manifest,work,worker,s3,env); j3=json.loads(s3.read_text())
        t3=(cp3.returncode==0 and j3["decision"]=="ALL_SHARDS_COMPLETE" and j3.get("global_done_root_sha256")==j2.get("global_done_root_sha256") and
            all(a["action"]=="SKIP_VALID_DONE" for a in j3["actions"]))
        result["tests"].append({"id":"IDEMPOTENT_COMPLETE_RERUN","pass":t3,"global_done_root_sha256":j3.get("global_done_root_sha256")})
        corrupt_sid=m["shards"][2]["shard_id"]; artifact=work/"done"/corrupt_sid/"event_mask_root.json"
        artifact.write_bytes(artifact.read_bytes()+b"CORRUPTION")
        s4=td/"summary4.json"; cp4=run(supervisor,manifest,work,worker,s4,env); j4=json.loads(s4.read_text())
        t4=(cp4.returncode!=0 and j4["decision"]=="STOPPED_FAIL_CLOSED" and "INVALID_EXISTING_DONE" in (j4.get("error") or ""))
        result["tests"].append({"id":"CORRUPTED_DONE_NEVER_RECOMPUTED_SILENTLY","pass":t4,"returncode":cp4.returncode})
        result["status"]="PASS" if all(t["pass"] for t in result["tests"]) else "FAIL"
        result["synthetic_manifest_root_sha256"]=m["shard_descriptor_root_sha256"]
        result["global_done_root_before_corruption"]=j2.get("global_done_root_sha256")
        result["economic_pnl_read"]=False; result["holdout_open"]=False
        result["receipt_sha256"]=hashlib.sha256(canonical(result)).hexdigest()
        out=repo/"control/QROS_TRANSACTIONAL_SHARD_SYNTHETIC_TEST_RECEIPT_V215_v1.json"
        out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print(result["status"])
        return 0 if result["status"]=="PASS" else 2
    finally:
        shutil.rmtree(td,ignore_errors=True)
if __name__=="__main__": raise SystemExit(main())
