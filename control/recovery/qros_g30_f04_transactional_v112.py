#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,gc,sys
from pathlib import Path
import numpy as np
from numba import njit
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f04_signal_primary_v112 as sa
import qros_g30_f04_signal_independent_v112 as sb

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
ASSET_AUTH={
 'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca'},
 'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'}
}
CUT_2019=np.int64(1546300800000)
EXPECTED_RAW=684
STOP_ATR_MULT=3.0
ATR_STORAGE_DIVISOR=2.0
TAKE_R_MULT=1.5
TIME_STOP_BARS=20

def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def digest_arrays(arrs):
 h=hashlib.sha256()
 for a in arrs:
  z=np.ascontiguousarray(a);h.update(str(z.dtype).encode()+b'\0');h.update(np.int64(z.size).tobytes());h.update(z.tobytes())
 return h.hexdigest()
def mask_digest(b,s):
 enc=np.zeros(len(b),np.int8);enc[b]=1;enc[s]=-1
 return hashlib.sha256(enc.tobytes()).hexdigest()
def specs():
 for sm in sa.SMOOTH:
  for timing in sa.TIM:
   for t in sa.TH:
    for fam in sa.FAMS:
     for n in sa.NS:yield (sm,timing,t,fam,n)
    yield (sm,timing,t,'SHOCK_BAR_BODY_DIRECTION_ONLY',1)
def spec_key(sp):
 sm,timing,t,fam,n=sp
 return f'{sm}|{timing}|{t:g}|{fam}|{n}'
def pf(x):
 pos=float(x[x>0].sum());neg=float(-x[x<0].sum())
 if neg==0:return float('inf') if pos>0 else 0.0
 return pos/neg
def safe(v):
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 return v
def ledger_sha(ch,et,xt,rr):
 rec=np.empty(len(ch),dtype=np.dtype([('et','<i8'),('xt','<i8'),('rr','<f8')]))
 rec['et']=et[ch];rec['xt']=xt[ch];rec['rr']=rr[ch]
 return hashlib.sha256(rec.tobytes()).hexdigest()

@njit(cache=True)
def lower(a,x):
 lo=0;hi=len(a)
 while lo<hi:
  m=(lo+hi)//2
  if a[m]<x:lo=m+1
  else:hi=m
 return lo

@njit(cache=True)
def outcome_primary(ts,bid,ask,bucket,atr14,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not active[bi] or not np.isfinite(atr14[bi]) or atr14[bi]<=0:continue
  close=bucket[bi]+step;deadline=min(close+TIME_STOP_BARS*step,((close//86400000)+1)*86400000);mi=lower(eb,close)
  if mi>=len(eb) or eb[mi]>=deadline:continue
  ei=first[mi]
  while ei<=last[mi] and (ts[ei]<close or ask[ei]<=bid[ei]):ei+=1
  if ei>last[mi] or ts[ei]>=deadline:continue
  entry=ask[ei] if side==1 else bid[ei];d=STOP_ATR_MULT*atr14[bi]/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d
  et[bi]=ts[ei];eiout[bi]=ei;dist[bi]=d;mend=lower(eb,deadline);hit=False
  for mj in range(mi,mend):
   possible=(ebl[mj]<=stop or ebh[mj]>=take) if side==1 else (eah[mj]>=stop or eal[mj]<=take)
   if not possible:continue
   j0=first[mj]
   if j0<ei:j0=ei
   for j in range(j0,last[mj]+1):
    if ts[j]>=deadline:break
    if ask[j]<=bid[j]:continue
    if side==1:
     if bid[j]<=stop:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
     if bid[j]>=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
    else:
     if ask[j]>=stop:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
     if ask[j]<=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
   if hit:break
  if not hit:
   if mend<=mi:et[bi]=-1;eiout[bi]=-1;continue
   j=last[mend-1]
   while j>=ei and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
   if j<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
 return et,xt,eiout,xiout,dist,rr

@njit(cache=True)
def outcome_independent(ts,bid,ask,bucket,atr14,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 bi=0
 while bi<n:
  if active[bi] and np.isfinite(atr14[bi]) and atr14[bi]>0:
   close=bucket[bi]+step;deadline=close+TIME_STOP_BARS*step;day=((close//86400000)+1)*86400000
   if deadline>day:deadline=day
   mi=lower(eb,close)
   if mi<len(eb) and eb[mi]<deadline:
    q=first[mi]
    while q<=last[mi] and (ts[q]<close or ask[q]<=bid[q]):q+=1
    if q<=last[mi] and ts[q]<deadline:
     ei=q;entry=ask[q] if side==1 else bid[q];d=(STOP_ATR_MULT*atr14[bi])/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+(TAKE_R_MULT*d) if side==1 else entry-(TAKE_R_MULT*d)
     et[bi]=ts[q];eiout[bi]=q;dist[bi]=d;mend=lower(eb,deadline);done=False;m=mi
     while m<mend and not done:
      may=False
      if side==1:
       if ebl[m]<=stop or ebh[m]>=take:may=True
      else:
       if eah[m]>=stop or eal[m]<=take:may=True
      if may:
       j=first[m]
       if j<ei:j=ei
       while j<=last[m] and ts[j]<deadline:
        if ask[j]>bid[j]:
         if side==1:
          if bid[j]<=stop:
           xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;done=True;break
          elif bid[j]>=take:
           xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;done=True;break
         else:
          if ask[j]>=stop:
           xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;done=True;break
          elif ask[j]<=take:
           xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;done=True;break
        j+=1
      m+=1
     if not done:
      if mend>mi:
       j=last[mend-1]
       while j>=ei and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
       if j>=ei:
        xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
       else:
        et[bi]=-1;eiout[bi]=-1
      else:
       et[bi]=-1;eiout[bi]=-1
  bi+=1
 return et,xt,eiout,xiout,dist,rr

@njit(cache=True)
def select_a(ids,et,xt):
 out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1)
 for i in range(len(ids)):
  q=ids[i]
  if et[q]<0 or et[q]<=prev:continue
  out[k]=q;k+=1;prev=xt[q]
 return out[:k]

@njit(cache=True)
def select_b(ids,et,xt):
 out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1);i=0
 while i<len(ids):
  q=ids[i]
  if et[q]>=0 and et[q]>prev:
   out[k]=q;k+=1;prev=xt[q]
  i+=1
 return out[:k]

def save_arr(root,name,a):np.save(root/f'{name}.npy',a,allow_pickle=False)
def load_arr(root,name):return np.load(root/f'{name}.npy',mmap_mode='r')
def shard_name(tf,fs):return ('H1' if tf==60 else f'M{tf}')+'_'+fs

def build_bars_prep(cache,tf,fs):
 z=np.load(cache)
 mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
 A=sa.bars(mb,*vals,tf);B=sb.bars(mb,*vals,tf)
 if digest_arrays(A)!=digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
 pa=sa.prepare(*A);pb=sb.prepare(*B)
 return z,A,B,pa,pb

def prepare(a):
 root=a.work;root.mkdir(parents=True,exist_ok=True);auth=ASSET_AUTH[a.asset]
 if sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
 if sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
 mm=np.memmap(a.src,dtype=DT,mode='r');z,A,B,pa,pb=build_bars_prep(a.cache,a.tf,a.feature_side)
 try:
  mgA=sa.atr_sma(A[2],A[3],A[4],14);mgB=sb.atr_sma(B[2],B[3],B[4],14)
  if not np.array_equal(np.nan_to_num(mgA,nan=-1.0),np.nan_to_num(mgB,nan=-1.0)):raise SystemExit('MANAGEMENT_ATR14_SMA_PARITY_FAIL')
  seq=hashlib.sha256();by={};order=[];uB=np.zeros(len(A[0]),bool);uS=np.zeros(len(A[0]),bool);raw=0
  for sp in specs():
   raw+=1;key=spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
   d=mask_digest(bA,sA)
   if d!=mask_digest(bB,sB):raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
   seq.update(key.encode()+b'\0'+bytes.fromhex(d));uB|=bA;uS|=sA
   if d not in by:by[d]={'key':key,'aliases':[key],'spec':list(sp)};order.append(d)
   else:by[d]['aliases'].append(key)
  if raw!=EXPECTED_RAW:raise SystemExit(f'RAW_CARDINALITY_FAIL {raw}')
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  oaB=outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],mgA,step,*ex,uB,1);obB=outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],mgB,step,*ex,uB,1)
  oaS=outcome_primary(mm['ts'],mm['bid'],mm['ask'],A[0],mgA,step,*ex,uS,-1);obS=outcome_independent(mm['ts'],mm['bid'],mm['ask'],B[0],mgB,step,*ex,uS,-1)
  for OA,OB,u,label in ((oaB,obB,uB,'BUY'),(oaS,obS,uS,'SELL')):
   q=np.flatnonzero(u)
   for k in range(6):
    if not np.array_equal(OA[k][q],OB[k][q]):raise SystemExit('RAW_OUTCOME_PARITY_FAIL '+label+' '+str(k))
  for side,OA in [('B',oaB),('S',oaS)]:
   for k,name in enumerate(('et','xt','ei','xi','dist','rr')):save_arr(root,f'{side}_{name}',OA[k])
  meta={'asset':a.asset,'shard':shard_name(a.tf,a.feature_side),'bars':int(len(A[0])),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'bar_digest':digest_arrays(A),'raw_identity_sequence_sha256':seq.hexdigest(),'unique_mask_set_sha256':hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest(),'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'order':order,'by':by,'src':str(a.src),'cache':str(a.cache),'tf':a.tf,'feature_side':a.feature_side}
  (root/'manifest.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
  print(json.dumps({k:meta[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','union_buy','union_sell']},sort_keys=True),flush=True)
 finally:z.close()

def score(a):
 root=a.work;meta=json.loads((root/'manifest.json').read_text());order=meta['order'];end=min(a.end,len(order))
 if a.start<0 or a.start>=end:raise SystemExit('BAD_RANGE')
 mm=np.memmap(meta['src'],dtype=DT,mode='r');z,A,B,pa,pb=build_bars_prep(Path(meta['cache']),meta['tf'],meta['feature_side'])
 try:
  OA_B=tuple(load_arr(root,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(load_arr(root,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'));recs=[];passers=[]
  for i in range(a.start,end):
   d=order[i];m=meta['by'][d];sp=tuple(m['spec']);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB) or mask_digest(bA,sA)!=d or mask_digest(bB,sB)!=d:raise SystemExit('REPLAY_SIGNAL_PARITY_FAIL '+m['key'])
   for side,mask,OA in [('BUY',bA,OA_B),('SELL',sA,OA_S)]:
    ids=np.flatnonzero(mask).astype(np.int64);chA=select_a(ids,OA[0],OA[1]);chB=select_b(ids,OA[0],OA[1])
    if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+m['key']+' '+side)
    rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    y18=float(rr[et<CUT_2019].sum());y19=float(rr[et>=CUT_2019].sum());pfc=pf(rr);pfk=pf(cons);pfs=pf(sev);passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
    rec={'id':m['key'],'aliases':m['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':ledger_sha(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)};recs.append(rec)
    if passed:passers.append(rec)
  out={'start':a.start,'end':end,'records':recs,'passers':passers};a.out.write_text(json.dumps(safe(out),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'start':a.start,'end':end,'records':len(recs),'passers':len(passers)},sort_keys=True),flush=True)
 finally:z.close()

def merge(a):
 root=a.work;meta=json.loads((root/'manifest.json').read_text());chunks=[json.loads(Path(p).read_text()) for p in a.chunks];chunks.sort(key=lambda x:x['start']);cur=0;records=[];passers=[]
 for c in chunks:
  if c['start']!=cur:raise SystemExit(f'CHUNK_GAP expected={cur} got={c["start"]}')
  cur=c['end'];records.extend(c['records']);passers.extend(c['passers'])
 if cur!=meta['unique_masks']:raise SystemExit(f'INCOMPLETE {cur}/{meta["unique_masks"]}')
 obj={'schema':'QROS_G30_F04_GATE_A_SHARD_V112_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F04_ATR_SMOOTHING','asset':meta['asset'],'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':meta['shard'],'bars':meta['bars'],'raw_identities':meta['raw_identities'],'unique_masks':meta['unique_masks'],'exact_alias_count':meta['exact_alias_count'],'evaluated_configurations':len(records),'bar_digest':meta['bar_digest'],'raw_identity_sequence_sha256':meta['raw_identity_sequence_sha256'],'unique_mask_set_sha256':meta['unique_mask_set_sha256'],'union_buy':meta['union_buy'],'union_sell':meta['union_sell'],'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','signal_atr':{'period':14,'smoothing':['WILDER_RMA_TR','EMA_TR'],'reference_timing':['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']},'management':{'stop_atr_period':14,'stop_atr_smoothing':'SMA_TR','atr_stop_mult':3.0,'reward_r_multiple':1.5,'time_stop_bars':20},'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
 a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['asset','shard','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','signal_parity','trade_parity']},sort_keys=True),flush=True)

def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
 p=sub.add_parser('prepare');p.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--work',type=Path,required=True)
 p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
 p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();{'prepare':prepare,'score':score,'merge':merge}[a.cmd](a)
if __name__=='__main__':main()
