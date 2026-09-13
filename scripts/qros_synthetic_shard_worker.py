#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path

def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-json",required=True); ap.add_argument("--out-dir",required=True); ap.add_argument("--receipt",required=True)
    ap.add_argument("--synthetic",action="store_true")
    ns=ap.parse_args()
    row=json.loads(Path(ns.shard_json).read_text(encoding="utf-8")); sid=row["shard_id"]; out=Path(ns.out_dir)
    fail_sid=os.environ.get("QROS_SYNTH_FAIL_ONCE_SHARD")
    marker_path=os.environ.get("QROS_SYNTH_FAIL_ONCE_MARKER")
    if fail_sid==sid and marker_path:
        marker=Path(marker_path)
        if not marker.exists():
            marker.parent.mkdir(parents=True,exist_ok=True); marker.write_text("failed-once\n",encoding="utf-8")
            (out/"partial.bin").write_bytes(b"partial-not-authoritative")
            raise SystemExit(17)
    units=int(row["descriptor"].get("signal_configs",row["descriptor"].get("work_units",0)))
    h=hashlib.sha256()
    for i in range(units):
        h.update(hashlib.sha256(canonical({"shard_id":sid,"i":i})).digest())
    artifact=out/"event_mask_root.json"
    artifact_obj={"schema":"QROS_SYNTH_SHARD_ARTIFACT_1.0","shard_id":sid,"work_units":units,"synthetic_event_mask_root_sha256":h.hexdigest()}
    artifact.write_text(json.dumps(artifact_obj,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    receipt={"schema":"QROS_SHARD_WORKER_RECEIPT_1.0","status":"PASS","shard_id":sid,
             "descriptor_sha256":row["descriptor_sha256"],
             "processed_signal_configs":units,
             "artifacts":[{"path":"event_mask_root.json","bytes":artifact.stat().st_size,"sha256":sha256_file(artifact)}],
             "economic_pnl_read":False,"holdout_open":False,"synthetic":True}
    Path(ns.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
