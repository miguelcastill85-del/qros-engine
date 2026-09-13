#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

DT=np.dtype([("ts","<i8"),("bid","<i4"),("ask","<i4"),("flags","u1")],align=False)

def mk(path,rows):
    a=np.array(rows,dtype=DT); path.write_bytes(a.tobytes())
    return {"bytes":path.stat().st_size,"records":len(a),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def run(script,manifest,data,out):
    return subprocess.run([sys.executable,str(script),"--manifest",str(manifest),"--data-dir",str(data),"--out",str(out)],text=True,capture_output=True)

def main():
    repo=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=="tests" else Path(__file__).resolve().parent
    script=(repo/"scripts/qros_seed0076_data_execution_ready_preflight.py") if (repo/"scripts").exists() else repo/"qros_seed0076_data_execution_ready_preflight.py"
    td=Path(tempfile.mkdtemp(prefix="qros_data_ready_test_")); tests=[]
    try:
        data=td/"data"; data.mkdir()
        n=mk(data/"n.bin",[(1000,100,101,0),(1010,101,101,0),(1020,102,104,0)])
        x=mk(data/"x.bin",[(2000,200,201,0),(2010,202,201,0),(2020,202,202,0)])
        man={"record_bytes":17,"NQX":{"target_file":"n.bin","target_bytes":n["bytes"],"target_records":n["records"],"target_sha256":n["sha256"]},"XAUUSD":{"target_file":"x.bin","target_bytes":x["bytes"],"target_records":x["records"],"target_sha256":x["sha256"]}}
        mp=td/"m.json"; mp.write_text(json.dumps(man))
        out1=td/"r1.json"; cp1=run(script,mp,data,out1); r1=json.loads(out1.read_text())
        tests.append({"id":"EXACT_BYTES_WITH_ZERO_AND_CROSSED_AUDIT_PASS","pass":cp1.returncode==0 and r1["decision"]=="DATA_EXECUTION_READY" and r1["results"]["XAUUSD"]["stats"]["crossed_spread"]==1 and r1["results"]["XAUUSD"]["stats"]["zero_spread"]==1})
        bad=mk(data/"n.bin",[(1000,100,101,0),(990,101,102,0),(1020,102,103,0)])
        man["NQX"].update({"target_bytes":bad["bytes"],"target_records":bad["records"],"target_sha256":bad["sha256"]}); mp.write_text(json.dumps(man))
        out2=td/"r2.json"; cp2=run(script,mp,data,out2); r2=json.loads(out2.read_text())
        tests.append({"id":"OUT_OF_ORDER_FAILS_DESPITE_EXACT_HASH","pass":cp2.returncode!=0 and "OUT_OF_ORDER_TICKS" in r2["results"]["NQX"]["errors"]})
        good=mk(data/"n.bin",[(1000,100,101,0),(1010,101,102,0),(1020,102,103,0)])
        man["NQX"].update({"target_bytes":good["bytes"],"target_records":good["records"],"target_sha256":good["sha256"]}); mp.write_text(json.dumps(man))
        b=bytearray((data/"n.bin").read_bytes()); b[-1]^=1; (data/"n.bin").write_bytes(bytes(b))
        out3=td/"r3.json"; cp3=run(script,mp,data,out3); r3=json.loads(out3.read_text())
        tests.append({"id":"BYTE_TAMPER_FAILS_HASH","pass":cp3.returncode!=0 and "SHA256_MISMATCH" in r3["results"]["NQX"]["errors"]})
        result={"schema":"QROS_SEED0076_DATA_EXECUTION_READY_PREFLIGHT_SYNTHETIC_TEST_1.0","status":"PASS" if all(t["pass"] for t in tests) else "FAIL","tests":tests,"economic_pnl_read":False,"holdout_open":False}
        result["receipt_sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        out=(repo/"control/QROS_SEED0076_DATA_EXECUTION_READY_PREFLIGHT_SYNTHETIC_TEST_V216_v1.json") if (repo/"control").exists() else repo/"data_ready_test_receipt.json"
        out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n"); print(result["status"]); return 0 if result["status"]=="PASS" else 2
    finally: shutil.rmtree(td,ignore_errors=True)
if __name__=="__main__": raise SystemExit(main())
