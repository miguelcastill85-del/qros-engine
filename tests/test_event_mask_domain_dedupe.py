#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, struct, subprocess, sys, tempfile, shutil
from pathlib import Path

HDR=struct.Struct(">32sI")
def H(s): return hashlib.sha256(s.encode()).digest()
def write_stream(path,rows):
    with open(path,"wb") as f:
        for cfg,events in rows:
            ev=sorted(set(events)); mask=b"".join(ev); f.write(H(cfg)); f.write(struct.pack(">I",len(mask))); f.write(mask)

def run(script,stream,out,receipt,asset,side,tf):
    return subprocess.run([sys.executable,str(script),"--mask-stream",str(stream),"--asset",asset,"--side",side,"--timeframe",tf,
                           "--out-dir",str(out),"--receipt",str(receipt)],text=True,capture_output=True)

def main():
    repo=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=="tests" else Path(__file__).resolve().parent
    script=(repo/"scripts/qros_event_mask_domain_dedupe.py") if (repo/"scripts").exists() else repo/"qros_event_mask_domain_dedupe.py"
    td=Path(tempfile.mkdtemp(prefix="qros_mask_dedupe_test_")); tests=[]
    try:
        e1,e2,e3=H("E1"),H("E2"),H("E3")
        sx=td/"xau.bin"; write_stream(sx,[("C1",[e1,e2]),("C2",[e2,e1]),("C3",[]),("C4",[e3])])
        ox=td/"ox"; rx=td/"rx.json"; cpx=run(script,sx,ox,rx,"XAUUSD","BUY","M1"); jx=json.loads(rx.read_text())
        tests.append({"id":"SAME_DOMAIN_IDENTICAL_MASK_DEDUPES","pass":cpx.returncode==0 and jx["input_config_count"]==4 and jx["distinct_mask_class_count"]==3 and jx["duplicate_config_count"]==1})
        sn=td/"nqx.bin"; write_stream(sn,[("D1",[])])
        on=td/"on"; rn=td/"rn.json"; cpn=run(script,sn,on,rn,"NQX","BUY","M1"); jn=json.loads(rn.read_text())
        x_empty=None
        for line in (ox/"mask_classes.jsonl").read_text().splitlines():
            r=json.loads(line)
            if r["event_count"]==0: x_empty=r["class_hash"]
        n_empty=json.loads((on/"mask_classes.jsonl").read_text().splitlines()[0])["class_hash"]
        tests.append({"id":"EMPTY_MASK_NOT_ALIAS_ACROSS_ASSETS","pass":cpn.returncode==0 and x_empty!=n_empty})
        bad=td/"bad.bin"
        with open(bad,"wb") as f:
            mask=e2+e1; f.write(H("BAD")); f.write(struct.pack(">I",len(mask))); f.write(mask)
        ob=td/"ob"; rb=td/"rb.json"; cpb=run(script,bad,ob,rb,"XAUUSD","BUY","M1")
        tests.append({"id":"NONCANONICAL_MASK_FAILS_CLOSED","pass":cpb.returncode!=0 and not rb.exists()})
        result={"schema":"QROS_EVENT_MASK_DOMAIN_DEDUPE_SYNTHETIC_TEST_1.0","status":"PASS" if all(t["pass"] for t in tests) else "FAIL",
                "tests":tests,"xau_class_root_sha256":jx["class_root_sha256"],"xau_alias_root_sha256":jx["full_alias_mapping_root_sha256"],
                "economic_pnl_read":False,"holdout_open":False}
        result["receipt_sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        out=(repo/"control/QROS_EVENT_MASK_DOMAIN_DEDUPE_SYNTHETIC_TEST_V216_v1.json") if (repo/"control").exists() else repo/"dedupe_test_receipt.json"
        out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print(result["status"]); return 0 if result["status"]=="PASS" else 2
    finally: shutil.rmtree(td,ignore_errors=True)
if __name__=="__main__": raise SystemExit(main())
