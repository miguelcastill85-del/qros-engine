#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, struct, tempfile
from pathlib import Path

REC_HDR=struct.Struct(">32sI")

def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def domain_bytes(asset,side,timeframe): return canonical({"asset":asset,"side":side,"timeframe":timeframe})
def class_hash(domain_b,mask_b): return hashlib.sha256(domain_b+b"\0"+mask_b).digest()

def iter_records(path: Path):
    with path.open("rb") as f:
        while True:
            h=f.read(REC_HDR.size)
            if not h: return
            if len(h)!=REC_HDR.size: raise RuntimeError("TRUNCATED_RECORD_HEADER")
            cfg,n=REC_HDR.unpack(h)
            if n%32: raise RuntimeError("MASK_BYTES_NOT_EVENT_ID_ALIGNED")
            mask=f.read(n)
            if len(mask)!=n: raise RuntimeError("TRUNCATED_MASK")
            ids=[mask[i:i+32] for i in range(0,n,32)]
            if ids!=sorted(ids) or len(ids)!=len(set(ids)): raise RuntimeError("MASK_NOT_SORTED_UNIQUE")
            yield cfg,mask

def build(path: Path,db_path: Path,asset,side,timeframe):
    dbytes=domain_bytes(asset,side,timeframe)
    cx=sqlite3.connect(db_path)
    cx.execute("PRAGMA journal_mode=DELETE"); cx.execute("PRAGMA synchronous=FULL")
    cx.execute("CREATE TABLE classes (class_hash BLOB PRIMARY KEY, mask BLOB NOT NULL, rep BLOB NOT NULL, alias_count INTEGER NOT NULL)")
    cx.execute("CREATE TABLE aliases (config_id BLOB PRIMARY KEY, class_hash BLOB NOT NULL)")
    count=0
    try:
        for cfg,mask in iter_records(path):
            ch=class_hash(dbytes,mask)
            row=cx.execute("SELECT mask,rep,alias_count FROM classes WHERE class_hash=?",(ch,)).fetchone()
            if row is None:
                cx.execute("INSERT INTO classes VALUES(?,?,?,?)",(ch,mask,cfg,1))
            else:
                oldmask,rep,n=row
                if oldmask!=mask: raise RuntimeError("SHA256_CLASS_HASH_COLLISION")
                newrep=cfg if cfg<rep else rep
                cx.execute("UPDATE classes SET rep=?,alias_count=? WHERE class_hash=?",(newrep,n+1,ch))
            cx.execute("INSERT INTO aliases VALUES(?,?)",(cfg,ch)); count+=1
        cx.commit()
    finally: cx.close()
    return count

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def finalize(db_path: Path,out_dir: Path,asset,side,timeframe):
    cx=sqlite3.connect(db_path)
    classes=list(cx.execute("SELECT class_hash,rep,alias_count,length(mask) FROM classes ORDER BY class_hash"))
    total=int(cx.execute("SELECT count(*) FROM aliases").fetchone()[0])
    alias_pairs=out_dir/"duplicate_alias_pairs.bin"; class_file=out_dir/"mask_classes.jsonl"
    hclass=hashlib.sha256(); halias=hashlib.sha256(); duplicates=0
    with class_file.open("wb") as cf:
        for ch,rep,n,masklen in classes:
            row={"class_hash":bytes(ch).hex(),"representative_config_id":bytes(rep).hex(),"alias_count":int(n),"event_count":int(masklen)//32}
            b=canonical(row); cf.write(b+b"\n"); hclass.update(hashlib.sha256(b).digest())
    with alias_pairs.open("wb") as af:
        q="SELECT a.config_id,a.class_hash,c.rep FROM aliases a JOIN classes c ON a.class_hash=c.class_hash ORDER BY a.config_id"
        for cfg,ch,rep in cx.execute(q):
            cfg,ch,rep=bytes(cfg),bytes(ch),bytes(rep); halias.update(cfg); halias.update(ch)
            if cfg!=rep: af.write(cfg); af.write(rep); duplicates+=1
    cx.close()
    return {"domain":{"asset":asset,"side":side,"timeframe":timeframe},"input_config_count":total,"distinct_mask_class_count":len(classes),
      "duplicate_config_count":duplicates,"class_root_sha256":hclass.hexdigest(),"full_alias_mapping_root_sha256":halias.hexdigest(),
      "class_file":{"path":class_file.name,"bytes":class_file.stat().st_size,"sha256":sha256_file(class_file)},
      "duplicate_alias_file":{"path":alias_pairs.name,"bytes":alias_pairs.stat().st_size,"sha256":sha256_file(alias_pairs)}}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mask-stream",required=True); ap.add_argument("--asset",required=True); ap.add_argument("--side",required=True); ap.add_argument("--timeframe",required=True)
    ap.add_argument("--out-dir",required=True); ap.add_argument("--receipt",required=True)
    a=ap.parse_args(); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="mask_dedupe.",suffix=".sqlite",dir=out); os.close(fd); db=Path(tmp); db.unlink()
    try:
        n=build(Path(a.mask_stream),db,a.asset,a.side,a.timeframe); result=finalize(db,out,a.asset,a.side,a.timeframe)
        if result["input_config_count"]!=n: raise RuntimeError("DEDUPE_COUNT_MISMATCH")
        receipt={"schema":"QROS_EVENT_MASK_DOMAIN_DEDUPE_RECEIPT_1.0","status":"PASS",**result,
                 "dedupe_scope":"same asset+side+timeframe only","economic_pnl_read":False,"holdout_open":False}
        receipt["receipt_sha256"]=hashlib.sha256(canonical(receipt)).hexdigest()
        Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print("PASS",n,result["distinct_mask_class_count"],result["duplicate_config_count"]); return 0
    finally: db.unlink(missing_ok=True)
if __name__=="__main__": raise SystemExit(main())
