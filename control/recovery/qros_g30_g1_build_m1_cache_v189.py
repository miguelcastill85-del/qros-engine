#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, io, json, zipfile
from pathlib import Path
import numpy as np
from numba import njit

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
STEP=60_000
AUTH={
'NQX':{'sha':'f6cef828431a2f8153e9fc9a07aa78978069fb11eef32778b43ee5654ba11fd5','records':86581096},
'XAUUSD':{'sha':'44803dfab56ff61acfee94ed71749a4c76526d046baf73b83a985a27ee0afe55','records':172280096},
}
KEYS=('mb','bo','bh','bl','bc','mo','mh','ml','mc','eb','ebh','ebl','eah','eal','first','last')

def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(16<<20),b''):h.update(b)
 return h.hexdigest()

def array_sha(a):
 z=np.ascontiguousarray(a)
 h=hashlib.sha256();h.update(str(z.dtype).encode());h.update(b'\0');h.update(np.asarray(z.shape,dtype='<i8').tobytes());h.update(z.tobytes())
 return h.hexdigest()

def root_sha(arrs):
 h=hashlib.sha256()
 for k in KEYS:
  h.update(k.encode()+b'\0'+bytes.fromhex(array_sha(arrs[k])))
 return h.hexdigest()

def deterministic_npz(path:Path, arrs):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as zf:
  for k in KEYS:
   bio=io.BytesIO(); np.save(bio,np.ascontiguousarray(arrs[k]),allow_pickle=False)
   info=zipfile.ZipInfo(k+'.npy',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.external_attr=0o600<<16
   zf.writestr(info,bio.getvalue())

def _merge_feature(parts):
 if not parts: return tuple(np.empty(0,np.int64) for _ in range(9))
 cols=[np.concatenate([p[i] for p in parts]) for i in range(9)]
 mb=cols[0]
 st=np.r_[0,np.flatnonzero(mb[1:]!=mb[:-1])+1]; en=np.r_[st[1:],len(mb)]
 out=[mb[st]]
 # BID o,h,l,c cols 1..4; MID 5..8
 for base in (1,5):
  o=cols[base][st]
  h=np.maximum.reduceat(cols[base+1],st)
  l=np.minimum.reduceat(cols[base+2],st)
  c=cols[base+3][en-1]
  out += [o,h,l,c]
 return tuple(out)

def _merge_exec(parts):
 if not parts: return tuple(np.empty(0,np.int64) for _ in range(7))
 cols=[np.concatenate([p[i] for p in parts]) for i in range(7)]
 eb=cols[0]; st=np.r_[0,np.flatnonzero(eb[1:]!=eb[:-1])+1]; en=np.r_[st[1:],len(eb)]
 return (eb[st],np.maximum.reduceat(cols[1],st),np.minimum.reduceat(cols[2],st),np.maximum.reduceat(cols[3],st),np.minimum.reduceat(cols[4],st),cols[5][st],cols[6][en-1])

def primary(mm,chunk=2_000_000):
 fp=[]; ep=[]; n=len(mm)
 for s in range(0,n,chunk):
  e=min(n,s+chunk); ts=mm['ts'][s:e]; b=mm['bid'][s:e]; a=mm['ask'][s:e]
  vf=a>=b
  if np.any(vf):
   tv=ts[vf].astype(np.int64,copy=False); bv=b[vf].astype(np.int64); av=a[vf].astype(np.int64); buck=(tv//STEP)*STEP
   st=np.r_[0,np.flatnonzero(buck[1:]!=buck[:-1])+1]; en=np.r_[st[1:],len(buck)]
   bx=bv*2; mx=bv+av
   fp.append((buck[st],bx[st],np.maximum.reduceat(bx,st),np.minimum.reduceat(bx,st),bx[en-1],mx[st],np.maximum.reduceat(mx,st),np.minimum.reduceat(mx,st),mx[en-1]))
  ve=a>b
  if np.any(ve):
   idx=np.flatnonzero(ve).astype(np.int64)+s; tv=ts[ve].astype(np.int64,copy=False); bv=b[ve].astype(np.int64); av=a[ve].astype(np.int64); buck=(tv//STEP)*STEP
   st=np.r_[0,np.flatnonzero(buck[1:]!=buck[:-1])+1]; en=np.r_[st[1:],len(buck)]
   ep.append((buck[st],np.maximum.reduceat(bv,st),np.minimum.reduceat(bv,st),np.maximum.reduceat(av,st),np.minimum.reduceat(av,st),idx[st],idx[en-1]))
 f=_merge_feature(fp); x=_merge_exec(ep)
 return dict(zip(KEYS, f+x))

@njit(cache=False)
def _counts(ts,bid,ask):
 nf=0;ne=0;lf=np.int64(-9223372036854775807);le=lf
 for i in range(len(ts)):
  m=(ts[i]//STEP)*STEP
  if ask[i]>=bid[i] and m!=lf:
   nf+=1;lf=m
  if ask[i]>bid[i] and m!=le:
   ne+=1;le=m
 return nf,ne

@njit(cache=False)
def _independent(ts,bid,ask):
 nf,ne=_counts(ts,bid,ask)
 mb=np.empty(nf,np.int64);bo=np.empty(nf,np.int64);bh=np.empty(nf,np.int64);bl=np.empty(nf,np.int64);bc=np.empty(nf,np.int64)
 mo=np.empty(nf,np.int64);mh=np.empty(nf,np.int64);ml=np.empty(nf,np.int64);mc=np.empty(nf,np.int64)
 eb=np.empty(ne,np.int64);ebh=np.empty(ne,np.int64);ebl=np.empty(ne,np.int64);eah=np.empty(ne,np.int64);eal=np.empty(ne,np.int64);first=np.empty(ne,np.int64);last=np.empty(ne,np.int64)
 fi=-1;ei=-1;cf=np.int64(-9223372036854775807);ce=cf
 for i in range(len(ts)):
  m=(ts[i]//STEP)*STEP;b=np.int64(bid[i]);a=np.int64(ask[i])
  if a>=b:
   bx=b*2;mx=b+a
   if m!=cf:
    fi+=1;cf=m;mb[fi]=m;bo[fi]=bx;bh[fi]=bx;bl[fi]=bx;bc[fi]=bx;mo[fi]=mx;mh[fi]=mx;ml[fi]=mx;mc[fi]=mx
   else:
    if bx>bh[fi]:bh[fi]=bx
    if bx<bl[fi]:bl[fi]=bx
    bc[fi]=bx
    if mx>mh[fi]:mh[fi]=mx
    if mx<ml[fi]:ml[fi]=mx
    mc[fi]=mx
  if a>b:
   if m!=ce:
    ei+=1;ce=m;eb[ei]=m;ebh[ei]=b;ebl[ei]=b;eah[ei]=a;eal[ei]=a;first[ei]=i;last[ei]=i
   else:
    if b>ebh[ei]:ebh[ei]=b
    if b<ebl[ei]:ebl[ei]=b
    if a>eah[ei]:eah[ei]=a
    if a<eal[ei]:eal[ei]=a
    last[ei]=i
 return mb,bo,bh,bl,bc,mo,mh,ml,mc,eb,ebh,ebl,eah,eal,first,last

def independent(mm):
 vals=_independent(mm['ts'],mm['bid'],mm['ask'])
 return dict(zip(KEYS,vals))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=AUTH,required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);ap.add_argument('--chunk',type=int,default=2_000_000);a=ap.parse_args()
 got=sha_file(a.src)
 if got!=AUTH[a.asset]['sha']:raise SystemExit('SOURCE_SHA_MISMATCH '+got)
 mm=np.memmap(a.src,dtype=DT,mode='r')
 if len(mm)!=AUTH[a.asset]['records']:raise SystemExit('SOURCE_RECORD_COUNT_MISMATCH')
 print(json.dumps({'phase':'source_pass','asset':a.asset,'records':len(mm),'sha256':got}),flush=True)
 p=primary(mm,a.chunk);print(json.dumps({'phase':'primary_done','asset':a.asset,'feature_minutes':len(p['mb']),'exec_minutes':len(p['eb'])}),flush=True)
 q=independent(mm);print(json.dumps({'phase':'independent_done','asset':a.asset,'feature_minutes':len(q['mb']),'exec_minutes':len(q['eb'])}),flush=True)
 mism=[]
 for k in KEYS:
  if not np.array_equal(p[k],q[k]):mism.append(k)
 if mism:raise SystemExit('PARITY_FAIL '+','.join(mism))
 arr_sha={k:array_sha(q[k]) for k in KEYS}; root=root_sha(q)
 deterministic_npz(a.out,q);outsha=sha_file(a.out)
 obj={'schema':'QROS_G30_G1_M1_CACHE_PARITY_RECEIPT_V189_v1','status':'PASS_EXACT','asset':a.asset,'source_sha256':got,'source_records':len(mm),'builder_semantics':{'feature_quote':'ASK_GTE_BID','exec_quote':'ASK_GT_BID','bucket_ms':60000,'bid_x2':'2*BID','mid_x2':'BID+ASK','primary':'NUMPY_CHUNKED_REDUCEAT','independent':'NUMBA_SEQUENTIAL_TICK_LOOP'},'feature_minutes':len(q['mb']),'exec_minutes':len(q['eb']),'first_feature_bucket_ms':int(q['mb'][0]),'last_feature_bucket_ms':int(q['mb'][-1]),'first_exec_bucket_ms':int(q['eb'][0]),'last_exec_bucket_ms':int(q['eb'][-1]),'array_sha256':arr_sha,'array_root_sha256':root,'cache_file':a.out.name,'cache_bytes':a.out.stat().st_size,'cache_sha256':outsha,'primary_independent_mismatches':0,'economic_metrics_read':False,'strategy_pnl_read':False,'years_2022_plus_read':False,'decision':'G1_M1_CACHE_EXACT_PARITY_PASS'}
 a.receipt.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
 print(json.dumps({'phase':'PASS','asset':a.asset,'feature_minutes':len(q['mb']),'exec_minutes':len(q['eb']),'array_root_sha256':root,'cache_sha256':outsha,'cache_bytes':a.out.stat().st_size}),flush=True)
if __name__=='__main__':main()
