#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, struct, tempfile, zipfile
from pathlib import Path

BUFFER=8*1024*1024
REC=17

def hash_file(path:Path):
    h=hashlib.sha256(); n=0
    with path.open("rb") as f:
        for b in iter(lambda:f.read(BUFFER),b""):
            h.update(b); n+=len(b)
    return n,h.hexdigest()

def atomic_json(path:Path,obj):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix="."+path.name+".")
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(obj,f,indent=2,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest",type=Path); ap.add_argument("parts_directory",type=Path); ap.add_argument("output_directory",type=Path)
    a=ap.parse_args()
    m=json.loads(a.manifest.read_text(encoding="utf-8"))
    if m.get("schema")!="QROS_FULL_HISTORY_CARRIER_ZIP_PARTS_2.0": raise SystemExit("unsupported manifest schema")
    if m.get("overall_verification")!="PASS": raise SystemExit("manifest is not verified")
    parts=m["multipart"]["parts"]
    if len(parts)!=m["multipart"]["parts_count"] or not 1<=len(parts)<=128: raise SystemExit("invalid part count")
    asset=m["asset"]; carrier=m["carrier"]
    if carrier["bytes"]!=carrier["records"]*REC: raise SystemExit("carrier layout mismatch")
    a.output_directory.mkdir(parents=True,exist_ok=True)
    out=a.output_directory/m["restore"]["output_file"]; partial=out.with_suffix(out.suffix+".partial")
    if partial.exists(): partial.unlink()
    final_h=hashlib.sha256(); total_bytes=0; total_records=0; first_global=None; last_global=None; prev_last=None
    part_receipts=[]
    with partial.open("xb") as dst:
        for expected_index,s in enumerate(parts,1):
            name=s["file"]
            if s["index"]!=expected_index or Path(name).name!=name or ".." in name: raise SystemExit("unsafe or unordered part")
            if s["asset"]!=asset or s["parts_count"]!=len(parts): raise SystemExit("asset/parts_count mismatch")
            if s["start_record"]!=total_records: raise SystemExit("record continuity mismatch")
            p=a.parts_directory/name
            zbytes,zsha=hash_file(p)
            if zbytes!=s["bytes"] or zsha!=s["sha256"]: raise SystemExit(f"zip verification failed: {name}")
            with zipfile.ZipFile(p) as z:
                names=z.namelist()
                if "PART_META.json" not in names or s["payload_member"] not in names: raise SystemExit(f"zip members missing: {name}")
                meta=json.loads(z.read("PART_META.json"))
                for k in ("asset","carrier_sha256","first_timestamp_ms","index","last_timestamp_ms","parts_count","payload_bytes","payload_member","payload_sha256","records","schema","start_record"):
                    if meta.get(k)!=s.get(k): raise SystemExit(f"part meta mismatch {name}:{k}")
                info=z.getinfo(s["payload_member"])
                if info.file_size!=s["payload_bytes"] or info.file_size!=s["records"]*REC: raise SystemExit(f"payload size mismatch: {name}")
                ph=hashlib.sha256(); pn=0; pfirst=None; plast=None
                with z.open(info) as src:
                    while True:
                        b=src.read(BUFFER)
                        if not b: break
                        if pn==0 and len(b)>=8: pfirst=struct.unpack_from("<q",b,0)[0]
                        ph.update(b); dst.write(b); final_h.update(b); pn+=len(b)
                        if len(b)>=REC: plast=struct.unpack_from("<q",b,len(b)-REC)[0]
                if pn!=s["payload_bytes"] or ph.hexdigest()!=s["payload_sha256"]: raise SystemExit(f"payload verification failed: {name}")
                if pfirst!=s["first_timestamp_ms"] or plast!=s["last_timestamp_ms"]: raise SystemExit(f"payload boundary mismatch: {name}")
                if prev_last is not None and pfirst<prev_last: raise SystemExit(f"cross-part chronology reversal: {name}")
                if first_global is None: first_global=pfirst
                last_global=plast; prev_last=plast
                total_bytes+=pn; total_records+=s["records"]
                part_receipts.append({"index":expected_index,"file":name,"zip_sha256":zsha,"payload_sha256":ph.hexdigest(),"records":s["records"]})
        dst.flush(); os.fsync(dst.fileno())
    if total_bytes!=carrier["bytes"] or total_records!=carrier["records"] or final_h.hexdigest()!=carrier["sha256"]: raise SystemExit("final carrier identity mismatch")
    if first_global!=carrier["first_timestamp_ms"] or last_global!=carrier["last_timestamp_ms"]: raise SystemExit("final boundary mismatch")
    if out.exists():
        ob,oh=hash_file(out)
        if ob!=carrier["bytes"] or oh!=carrier["sha256"]: raise SystemExit("existing output conflicts")
        partial.unlink()
    else:
        os.replace(partial,out)
    receipt={"schema":"QROS_FULL_HISTORY_ZIP_CAPABILITY_RECEIPT_2.0","asset":asset,"status":"CAPABILITY_PASS",
             "carrier_file":out.name,"carrier_bytes":total_bytes,"carrier_records":total_records,"carrier_sha256":final_h.hexdigest(),
             "first_timestamp_ms":first_global,"last_timestamp_ms":last_global,"parts":part_receipts,
             "development_prefix":m["development_prefix"],"exposure_state":m["exposure_state"]}
    rp=a.output_directory/(out.name+".receipt.json"); atomic_json(rp,receipt)
    print(json.dumps(receipt,sort_keys=True))

if __name__=="__main__": main()
