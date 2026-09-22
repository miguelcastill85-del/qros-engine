#!/usr/bin/env python3
import hashlib, json, shutil, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
RESTORE=HERE.parent/"QROS_RESTORE_FULL_HISTORY_ZIP_v2.py"

def sha(b): return hashlib.sha256(b).hexdigest()

def build(root:Path):
    parts=root/"parts"; parts.mkdir()
    raw=b"".join(struct.pack("<qiiB",1700000000000+i*137,200000+i%1000,200007+i%1000,(2,4,6)[i%3]) for i in range(40003))
    carrier_sha=sha(raw); specs=[]; start=0; off=0
    for idx,nrec in enumerate((10000,10000,10000,10003),1):
        payload=raw[off*17:(off+nrec)*17]; off+=nrec
        member=f"CANARY_PACKED17_rows_{start:09d}_{start+nrec-1:09d}.bin"
        meta={"asset":"CANARY","carrier_sha256":carrier_sha,"first_timestamp_ms":struct.unpack_from("<q",payload,0)[0],
              "index":idx,"last_timestamp_ms":struct.unpack_from("<q",payload,len(payload)-17)[0],"parts_count":4,
              "payload_bytes":len(payload),"payload_member":member,"payload_sha256":sha(payload),"records":nrec,
              "schema":"QROS_PACKED17_ZIP_PART_2.0","start_record":start}
        name=f"CANARY_part{idx:03d}-of-004.zip"; p=parts/name
        with zipfile.ZipFile(p,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(member,payload); z.writestr("PART_META.json",json.dumps(meta,sort_keys=True))
        spec=dict(meta); spec.update({"file":name,"bytes":p.stat().st_size,"sha256":sha(p.read_bytes())}); specs.append(spec); start+=nrec
    manifest={"schema":"QROS_FULL_HISTORY_CARRIER_ZIP_PARTS_2.0","overall_verification":"PASS","asset":"CANARY",
              "carrier":{"file":"canary.bin","bytes":len(raw),"records":len(raw)//17,"sha256":carrier_sha,
                         "first_timestamp_ms":1700000000000,"last_timestamp_ms":1700000000000+(40003-1)*137},
              "multipart":{"parts":specs,"parts_count":4,"records_per_part":10000},
              "restore":{"output_file":"canary.bin","script":"QROS_RESTORE_FULL_HISTORY_ZIP_v2.py"},
              "development_prefix":{"parity":"SYNTHETIC"},"exposure_state":{"economic":"NONE"}}
    mp=root/"manifest.json"; mp.write_text(json.dumps(manifest,indent=2)+"\n")
    return mp,parts,raw

def run(mp,parts,out):
    return subprocess.run([sys.executable,str(RESTORE),str(mp),str(parts),str(out)],capture_output=True,text=True)

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); mp,parts,raw=build(root)
        good=run(mp,parts,root/"out")
        assert good.returncode==0 and (root/"out/canary.bin").read_bytes()==raw
        tamper=root/"tamper"; shutil.copytree(parts,tamper)
        p=tamper/"CANARY_part002-of-004.zip"; b=bytearray(p.read_bytes()); b[len(b)//2]^=1; p.write_bytes(b)
        bad=run(mp,tamper,root/"out_tamper"); assert bad.returncode!=0 and "zip verification failed" in (bad.stdout+bad.stderr)
        d=json.loads(mp.read_text()); d["multipart"]["parts"][0],d["multipart"]["parts"][1]=d["multipart"]["parts"][1],d["multipart"]["parts"][0]
        mr=root/"manifest_reordered.json"; mr.write_text(json.dumps(d,indent=2)+"\n")
        order=run(mr,parts,root/"out_reorder"); assert order.returncode!=0 and "unsafe or unordered part" in (order.stdout+order.stderr)
        result={"schema":"QROS_ZIP_RESTORE_CANARY_1.0","status":"PASS","records":40003,"carrier_sha256":sha(raw),
                "valid_restore":True,"tamper_rejected":True,"reorder_rejected":True}
        print(json.dumps(result,sort_keys=True))

if __name__=="__main__": main()
