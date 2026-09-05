#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f11_signal_primary_v159 as sa
import qros_g30_f11_signal_independent_v159 as sb
import qros_g30_f10_exec_core_v127 as ex
AUTH={'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca'},'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'}}
EXPECTED_RAW=2052

def sha_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for z in iter(lambda:f.read(8<<20),b''):h.update(z)
 return h.hexdigest()

def digest_arrays(arrs):
 h=hashlib.sha256()
 for a in arrs:
  z=np.ascontiguousarray(a);h.update(str(z.dtype).encode()+b'\0');h.update(np.int64(z.size).tobytes());h.update(z.tobytes())
 return h.hexdigest()

def safe(v):
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 return v

def specs():
 for r in sa.REFRACTORY:
  for timing in sa.TIM:
   for th in sa.TH:
    for fam in sa.FAMS:
     for n in sa.NS:yield(r,timing,th,fam,n)
    yield(r,timing,th,'SHOCK_BAR_BODY_DIRECTION_ONLY',1)

def spec_key(s):
 r,timing,th,fam,n=s;return f'REFRACTORY_R{r}|{timing}|{th:g}|{fam}|{n}'
def save_arr(root,name,a):np.save(root/f'{name}.npy',a,allow_pickle=False)
def load_arr(root,name):return np.load(root/f'{name}.npy',mmap_mode='r')
def shard_name(tf,fs):return ('H1' if tf==60 else f'M{tf}')+'_'+fs

def build_bars_prep(cache,tf,fs):
 z=np.load(cache);mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
 A=sa.bars(mb,*vals,tf);B=sb.bars(mb,*vals,tf)
 if digest_arrays(A)!=digest_arrays(B):z.close();raise SystemExit('BAR_PARITY_FAIL')
 return z,A,B,sa.prepare(*A),sb.prepare(*B)

def prepare(a):
 root=a.work;root.mkdir(parents=True,exist_ok=True);auth=AUTH[a.asset]
 for p,k,label in ((a.src,'src','DEV'),(a.cache,'cache','CACHE')):
  if sha_file(p)!=auth[k]:raise SystemExit(label+'_SHA_MISMATCH')
 mm=np.memmap(a.src,dtype=ex.DT,mode='r');z,A,B,pa,pb=build_bars_prep(a.cache,a.tf,a.feature_side)
 try:
  atrA=sa.atr_sma(A[2],A[3],A[4],14);atrB=sb.atr_sma(B[2],B[3],B[4],14)
  if not np.array_equal(np.nan_to_num(atrA,nan=-1.),np.nan_to_num(atrB,nan=-1.)):raise SystemExit('MANAGEMENT_ATR_PARITY_FAIL')
  seq=hashlib.sha256();by={};order=[];uB=np.zeros(len(A[0]),bool);uS=np.zeros(len(A[0]),bool);raw=0
  for sp in specs():
   raw+=1;key=spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
   d=ex.mask_digest(bA,sA)
   if d!=ex.mask_digest(bB,sB):raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
   seq.update(key.encode()+b'\0'+bytes.fromhex(d));uB|=bA;uS|=sA
   if d not in by:by[d]={'key':key,'aliases':[key],'spec':list(sp)};order.append(d)
   else:by[d]['aliases'].append(key)
  if raw!=EXPECTED_RAW:raise SystemExit('RAW_CARDINALITY_FAIL')
  bars=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  oaB=ex.outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*bars,uB,1);obB=ex.outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*bars,uB,1)
  oaS=ex.outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*bars,uS,-1);obS=ex.outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*bars,uS,-1)
  for OA,OB,u,label in ((oaB,obB,uB,'BUY'),(oaS,obS,uS,'SELL')):
   q=np.flatnonzero(u)
   for k in range(6):
    if not np.array_equal(OA[k][q],OB[k][q]):raise SystemExit(f'RAW_OUTCOME_PARITY_FAIL {label} {k}')
  for side,OA in [('B',oaB),('S',oaS)]:
   for k,name in enumerate(('et','xt','ei','xi','dist','rr')):save_arr(root,side+'_'+name,OA[k])
  meta={'asset':a.asset,'shard':shard_name(a.tf,a.feature_side),'bars':len(A[0]),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'bar_digest':digest_arrays(A),'raw_identity_sequence_sha256':seq.hexdigest(),'unique_mask_set_sha256':hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest(),'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'order':order,'by':by,'src':str(a.src),'cache':str(a.cache),'tf':a.tf,'feature_side':a.feature_side}
  (root/'manifest.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8');print(json.dumps({k:meta[k] for k in ('asset','shard','raw_identities','unique_masks','union_buy','union_sell')},sort_keys=True))
 finally:z.close()

def score(a):
 root=a.work;meta=json.loads((root/'manifest.json').read_text());order=meta['order'];end=min(a.end,len(order))
 if a.start<0 or a.start>=end:raise SystemExit('BAD_RANGE')
 mm=np.memmap(meta['src'],dtype=ex.DT,mode='r');z,A,B,pa,pb=build_bars_prep(Path(meta['cache']),meta['tf'],meta['feature_side'])
 try:
  OB=tuple(load_arr(root,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OS=tuple(load_arr(root,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'));records=[];passers=[]
  for i in range(a.start,end):
   d=order[i];m=meta['by'][d];sp=tuple(m['spec']);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB) or ex.mask_digest(bA,sA)!=d or ex.mask_digest(bB,sB)!=d:raise SystemExit('REPLAY_SIGNAL_PARITY_FAIL '+m['key'])
   for side,mask,O in (('BUY',bA,OB),('SELL',sA,OS)):
    ids=np.flatnonzero(mask).astype(np.int64);chA=ex.select_a(ids,O[0],O[1]);chB=ex.select_b(ids,O[0],O[1])
    if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL')
    rr=O[5][chA].astype(float);ei=O[2][chA];xi=O[3][chA];dist=O[4][chA];et=O[0][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    y18=float(rr[et<ex.CUT_2019].sum());y19=float(rr[et>=ex.CUT_2019].sum());passed=len(chA)>=60 and ex.pf(rr)>=1.20 and ex.pf(cons)>=1.10 and ex.pf(sev)>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
    rec={'id':m['key'],'aliases':m['aliases'],'signal_sha256':d,'side':side,'n':len(chA),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':ex.pf(rr),'pf_k':ex.pf(cons),'pf_s':ex.pf(sev),'r2018':y18,'r2019':y19,'ledger_sha256':ex.ledger_sha(chA,O[0],O[1],O[5]),'pass':bool(passed)};records.append(rec)
    if passed:passers.append(rec)
  obj={'start':a.start,'end':end,'records':records,'passers':passers};a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'start':a.start,'end':end,'records':len(records),'passers':len(passers)},sort_keys=True))
 finally:z.close()

def merge(a):
 meta=json.loads((a.work/'manifest.json').read_text());chunks=sorted((json.loads(Path(p).read_text()) for p in a.chunks),key=lambda x:x['start']);cur=0;records=[];passers=[]
 for c in chunks:
  if c['start']!=cur:raise SystemExit(f'CHUNK_GAP {cur} {c["start"]}')
  cur=c['end'];records+=c['records'];passers+=c['passers']
 if cur!=meta['unique_masks']:raise SystemExit(f'INCOMPLETE {cur}/{meta["unique_masks"]}')
 obj={'schema':'QROS_G30_F11_GATE_A_SHARD_V159_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F11_REFRACTORY','asset':meta['asset'],'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':meta['shard'],'bars':meta['bars'],'raw_identities':meta['raw_identities'],'unique_masks':meta['unique_masks'],'exact_alias_count':meta['exact_alias_count'],'evaluated_configurations':len(records),'bar_digest':meta['bar_digest'],'raw_identity_sequence_sha256':meta['raw_identity_sequence_sha256'],'unique_mask_set_sha256':meta['unique_mask_set_sha256'],'union_buy':meta['union_buy'],'union_sell':meta['union_sell'],'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','event_refractory_bars':list(sa.REFRACTORY),'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
 a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ('asset','shard','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell')},sort_keys=True))

def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
 p=sub.add_parser('prepare');p.add_argument('--asset',choices=sorted(AUTH),required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--work',type=Path,required=True)
 p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
 p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();{'prepare':prepare,'score':score,'merge':merge}[a.cmd](a)
if __name__=='__main__':main()
