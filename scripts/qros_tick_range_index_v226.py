from __future__ import annotations
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ticks',required=True);ap.add_argument('--block-size',type=int,default=1024);ap.add_argument('--out',required=True);ap.add_argument('--receipt',required=True);a=ap.parse_args();t0=time.time()
 ticks=np.memmap(a.ticks,dtype=TICK_DTYPE,mode='r');x=ticks['bid'];bs=a.block_size;n=len(x);nb=(n+bs-1)//bs
 mins=np.empty(nb,np.int32);maxs=np.empty(nb,np.int32)
 full=n//bs
 if full:
  v=x[:full*bs].reshape(full,bs);mins[:full]=v.min(axis=1);maxs[:full]=v.max(axis=1)
 if full<nb:
  mins[full]=x[full*bs:].min();maxs[full]=x[full*bs:].max()
 np.savez(a.out,block_size=np.array([bs],np.int32),n_ticks=np.array([n],np.int64),block_min=mins,block_max=maxs)
 rec={'schema':'QROS_TICK_RANGE_INDEX_1.0','status':'PASS','ticks':Path(a.ticks).name,'block_size':bs,'n_ticks':n,'blocks':nb,'index_bytes':Path(a.out).stat().st_size,'index_sha256':sha256_file(a.out),'elapsed_seconds':round(time.time()-t0,6),'economic_pnl_read':False,'holdout_open':False}
 Path(a.receipt).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps(rec))
if __name__=='__main__':main()
