#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess
from pathlib import Path

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()
def hash_decompressed(p):
 h=hashlib.sha256();n=0
 cp=subprocess.Popen(['zstd','-q','-dc',str(p)],stdout=subprocess.PIPE)
 assert cp.stdout is not None
 for b in iter(lambda:cp.stdout.read(8*1024*1024),b''): h.update(b);n+=len(b)
 rc=cp.wait()
 if rc!=0: raise RuntimeError(f'ZSTD_DECOMPRESS_FAIL:{p}:{rc}')
 return n,h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--groups-root',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 root=Path(a.groups_root); rows=[];total_o=total_c=0
 for gi in range(24):
  gd=root/f'group{gi:02d}';rp=gd/'worker_receipt.json';r=json.load(open(rp))
  art=next(x for x in r['artifacts'] if x['path']=='mask_classes.delta_u32.bin')
  src=gd/art['path']; dst=src.with_name(src.name+'.zst'); tmp=dst.with_suffix(dst.suffix+'.tmp')
  if not src.is_file() or src.stat().st_size!=art['bytes'] or sha256_file(src)!=art['sha256']: raise RuntimeError(f'ORIGINAL_INVALID:{gi}')
  if dst.exists():
   dn,dh=hash_decompressed(dst)
   if dn!=art['bytes'] or dh!=art['sha256']: raise RuntimeError(f'EXISTING_COMPRESSED_INVALID:{gi}')
  else:
   tmp.unlink(missing_ok=True)
   with tmp.open('wb') as out:
    cp=subprocess.run(['zstd','-q','-T0','-5','-c',str(src)],stdout=out)
   if cp.returncode!=0: raise RuntimeError(f'ZSTD_COMPRESS_FAIL:{gi}:{cp.returncode}')
   dn,dh=hash_decompressed(tmp)
   if dn!=art['bytes'] or dh!=art['sha256']: raise RuntimeError(f'DECOMPRESSED_IDENTITY_FAIL:{gi}')
   os.replace(tmp,dst)
  csha=sha256_file(dst);cb=dst.stat().st_size;total_o+=art['bytes'];total_c+=cb
  rows.append({'group':gi,'group_receipt_sha256':r['receipt_sha256'],'original_path':str(src.relative_to(root)),'original_bytes':art['bytes'],'original_sha256':art['sha256'],'compressed_path':str(dst.relative_to(root)),'compressed_bytes':cb,'compressed_sha256':csha,'decompressed_bytes':art['bytes'],'decompressed_sha256':art['sha256'],'identity_verified':True})
 rec={'schema':'QROS_GA1_MASK_BLOB_COMPACTION_RECEIPT_1.0','status':'PASS','codec':'zstd level5 multithread','groups':rows,'total_original_bytes':total_o,'total_compressed_bytes':total_c,'compression_ratio':total_c/total_o,'deletion_authorized_after_durable_receipt':True,'economic_pnl_read':False,'holdout_open':False}
 rec['receipt_sha256']=hashlib.sha256(canonical(rec)).hexdigest();Path(a.out).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':'PASS','groups':24,'original':total_o,'compressed':total_c,'ratio':rec['compression_ratio'],'receipt_sha256':rec['receipt_sha256']}))
if __name__=='__main__':main()
