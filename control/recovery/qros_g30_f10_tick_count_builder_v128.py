#!/usr/bin/env python3
"""Deterministic F10 M1 non-crossed quote-count cache builder."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import numpy as np

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
AUTH={
 'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca','bars':673097,'non_crossed':59940100,'crossed':160,'out':'04d02aa0c14efeae2ee22b5dff11b022ac97276653ece6fad50edc4e17be80ec'},
 'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62','bars':681772,'non_crossed':151382314,'crossed':74,'out':'6afb91bf589dbaf02e995d2a5915f760ca2ae1dd88179469528c3b7f8beab2d2'}
}
def sha_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(8<<20),b''):h.update(z)
 return h.hexdigest()
def build_counts(src:Path,cache:Path,chunk_records:int=5_000_000)->tuple[np.ndarray,int]:
 if src.stat().st_size%DT.itemsize:raise ValueError('RAW_SIZE_NOT_MULTIPLE_OF_17')
 mm=np.memmap(src,dtype=DT,mode='r');z=np.load(cache)
 try:
  mb=np.asarray(z['mb'],dtype=np.int64)
  if len(mb)==0 or np.any(mb[1:]<=mb[:-1]) or np.any(mb%60000):raise ValueError('INVALID_CANONICAL_M1_BUCKETS')
  out=np.zeros(len(mb),np.int64);crossed=0
  for start in range(0,len(mm),chunk_records):
   q=mm[start:min(start+chunk_records,len(mm))];ok=q['ask']>=q['bid'];crossed+=int((~ok).sum())
   buckets=(q['ts'][ok]//60000)*60000;ix=np.searchsorted(mb,buckets)
   valid=(ix<len(mb))
   if not np.all(valid):raise ValueError('QUOTE_BUCKET_OUTSIDE_CACHE')
   if not np.all(mb[ix]==buckets):raise ValueError('QUOTE_BUCKET_MISSING_FROM_CACHE')
   out+=np.bincount(ix,minlength=len(mb)).astype(np.int64)
  return out,crossed
 finally:z.close()
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=sorted(AUTH),required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--chunk-records',type=int,default=5_000_000);a=ap.parse_args();auth=AUTH[a.asset]
 if sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
 if sha_file(a.cache)!=auth['cache']:raise SystemExit('BAR_CACHE_SHA_MISMATCH')
 counts,crossed=build_counts(a.src,a.cache,a.chunk_records)
 if len(counts)!=auth['bars'] or int(counts.sum())!=auth['non_crossed'] or crossed!=auth['crossed']:raise SystemExit('COUNT_IDENTITY_MISMATCH')
 a.out.parent.mkdir(parents=True,exist_ok=True);tmp=a.out.with_name(a.out.name+'.tmp')
 with tmp.open('wb') as f:np.save(f,counts,allow_pickle=False)
 os.replace(tmp,a.out);out_sha=sha_file(a.out)
 if out_sha!=auth['out']:raise SystemExit('OUTPUT_SHA_MISMATCH')
 print(json.dumps({'asset':a.asset,'bars':len(counts),'non_crossed':int(counts.sum()),'crossed_excluded':crossed,'sha256':out_sha,'status':'PASS'},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
