from __future__ import annotations
import numpy as np, json, hashlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import qros_g30_f10_signal_primary_v127 as A
import qros_g30_f10_signal_independent_v127 as B
import qros_g30_f10_exec_core_v127 as E
rng=np.random.default_rng(20260904)
N=45*24*60;start=np.int64(1514764800000);mb=start+np.arange(N,dtype=np.int64)*60000
raw_n=(1+(np.arange(N)%7)).astype(np.int64);raw_n[np.arange(N)%97<7]+=5;raw_n[np.arange(N)%211==0]+=12
inc=rng.integers(-4,5,size=N,dtype=np.int64);inc[(np.arange(N)%131)<4]=3;inc[(np.arange(N)%173)<3]=-3
close=100000+np.cumsum(inc,dtype=np.int64);open_=np.r_[np.int64(100000),close[:-1]]
T=int(raw_n.sum());ts=np.empty(T,np.int64);bid=np.empty(T,np.int64);ask=np.empty(T,np.int64);pos=0
for i,n in enumerate(raw_n.tolist()):
 offs=np.linspace(1000,59000,n,dtype=np.int64);sl=slice(pos,pos+n);ts[sl]=mb[i]+offs
 vals=np.rint(np.linspace(open_[i],close[i],n)).astype(np.int64);vals += ((np.arange(n)+i)%3)-1;bid[sl]=vals
 sp=(2+((np.arange(n)+i)%5)).astype(np.int64);ask[sl]=vals+sp
 if n>=3 and i%223==0:ask[pos+n-2]=bid[pos+n-2]
 if n>=4 and i%509==0:ask[pos+n-3]=bid[pos+n-3]-1
 pos+=n
ok=ask>=bid;idx=np.flatnonzero(ok);tv=ts[idx];bv=bid[idx];av=ask[idx];bk=(tv//60000)*60000;st=np.r_[0,np.flatnonzero(bk[1:]!=bk[:-1])+1];en=np.r_[st[1:],len(bk)]
assert len(st)==N and np.array_equal(bk[st],mb)
b2=bv*2;mid=bv+av
bo=b2[st];bh=np.maximum.reduceat(b2,st);bl=np.minimum.reduceat(b2,st);bc=b2[en-1];mo=mid[st];mh=np.maximum.reduceat(mid,st);ml=np.minimum.reduceat(mid,st);mc=mid[en-1];cnt=(en-st).astype(np.int64)
ex=ask>bid;ix=np.flatnonzero(ex);te=ts[ix];be=bid[ix];ae=ask[ix];eb=(te//60000)*60000;es=np.r_[0,np.flatnonzero(eb[1:]!=eb[:-1])+1];ee=np.r_[es[1:],len(eb)]
assert len(es)==N and np.array_equal(eb[es],mb)
first=ix[es].astype(np.int64);last=ix[ee-1].astype(np.int64);ebh=np.maximum.reduceat(be,es);ebl=np.minimum.reduceat(be,es);eah=np.maximum.reduceat(ae,es);eal=np.minimum.reduceat(ae,es)
SPECS=[]
for ctx in A.CTX:
 for L in A.LBS:
  for timing in A.TIM:
   for th in A.TH:
    for fam in A.FAMS:
     for n in A.NS:SPECS.append((ctx,L,timing,th,fam,n))
    SPECS.append((ctx,L,timing,th,'SHOCK_BAR_BODY_DIRECTION_ONLY',1))
assert len(SPECS)==2736
summary={'schema':'QROS_G30_F10_SYNTHETIC_PARITY_V127_v1','seed':20260904,'minutes':N,'raw_ticks':T,'canonical_non_crossed_ticks':int(ok.sum()),'executable_ticks':int(ex.sum()),'identities_per_tf':2736,'timeframes':{},'status':'PASS'}
for tf in (1,5,10,15,30,60):
 PA=A.bars(mb,bo,bh,bl,bc,tf);PB=B.bars(mb,bo,bh,bl,bc,tf);CA=A.count_bars(mb,cnt,tf);CB=B.count_bars(mb,cnt,tf)
 for x,y in zip(PA,PB):
  if not np.array_equal(x,y):raise SystemExit(f'BAR_PARITY_FAIL {tf}')
 if not np.array_equal(CA,CB):raise SystemExit(f'COUNT_PARITY_FAIL {tf}')
 pa=A.prepare(*PA,CA);pb=B.prepare(*PB,CB)
 for k in pa['contexts']:
  if not np.array_equal(pa['contexts'][k],pb['contexts'][k]):raise SystemExit(f'CTX_PARITY_FAIL {tf} {k}')
 seq=hashlib.sha256();uB=np.zeros(len(PA[0]),bool);uS=np.zeros(len(PA[0]),bool);nonempty=0
 for sp in SPECS:
  ba,sa=A.mask(pa,*PA[1:],*sp);bb,sb=B.mask(pb,*PB[1:],*sp)
  if not np.array_equal(ba,bb) or not np.array_equal(sa,sb):raise SystemExit(f'SIGNAL_PARITY_FAIL {tf} {sp}')
  d=E.mask_digest(ba,sa);d2=E.mask_digest(bb,sb)
  if d!=d2:raise SystemExit('DIGEST_FAIL')
  seq.update(repr(sp).encode()+b'\0'+bytes.fromhex(d));uB|=ba;uS|=sa;nonempty+=int(ba.any() or sa.any())
 step=tf*60000;atr=A.atr_sma(PA[2],PA[3],PA[4],14);args=(ts,bid,ask,PA[0],atr,step,mb,ebh,ebl,eah,eal,first,last)
 oaB=E.outcome_primary(*args,uB,1);obB=E.outcome_independent(*args,uB,1);oaS=E.outcome_primary(*args,uS,-1);obS=E.outcome_independent(*args,uS,-1)
 for side,oa,ob,u in [('BUY',oaB,obB,uB),('SELL',oaS,obS,uS)]:
  q=np.flatnonzero(u)
  for k in range(6):
   if not np.array_equal(oa[k][q],ob[k][q]):raise SystemExit(f'EXEC_PARITY_FAIL {tf} {side} {k}')
  c1=E.select_a(q.astype(np.int64),oa[0],oa[1]);c2=E.select_b(q.astype(np.int64),oa[0],oa[1])
  if not np.array_equal(c1,c2):raise SystemExit(f'SELECT_PARITY_FAIL {tf} {side}')
 summary['timeframes'][str(tf)]={'bars':int(len(PA[0])),'identities':2736,'nonempty_identity_pairs':nonempty,'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'identity_sequence_sha256':seq.hexdigest(),'tick_count_sum':int(CA.sum()),'execution_union_buy_parity':'PASS_EXACT','execution_union_sell_parity':'PASS_EXACT'}
 print(json.dumps({'tf':tf,**summary['timeframes'][str(tf)]},sort_keys=True),flush=True)
out=ROOT/'F10_SYNTHETIC_PARITY_V127.json';out.write_text(json.dumps(summary,separators=(',',':')),encoding='utf-8');print('RESULT_SHA256',hashlib.sha256(out.read_bytes()).hexdigest());print('PASS_F10_SYNTHETIC_PARITY')
