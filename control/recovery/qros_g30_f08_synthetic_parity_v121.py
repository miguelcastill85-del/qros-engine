from __future__ import annotations
import json, hashlib, sys, time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import qros_g30_f08_signal_primary_v121 as A
import qros_g30_f08_signal_independent_v121 as B
import qros_g30_f08_transactional_v121 as W
base=W.base
rng=np.random.default_rng(20260903)
N=45*24*60
start=np.int64(1514764800000)
mb=start+np.arange(N,dtype=np.int64)*60000
inc=rng.integers(-4,5,size=N,dtype=np.int64)
inc[(np.arange(N)%97)<5]=3
inc[(np.arange(N)%131)<4]=-3
c=100000+np.cumsum(inc,dtype=np.int64)
o=np.r_[np.int64(100000),c[:-1]]
base_rng=(2+(np.arange(N)%7)).astype(np.int64)
base_rng[(np.arange(N)%211)<20]=4
base_rng[np.arange(N)%137==0]=30
base_rng[np.arange(N)%509==0]=65
h=np.maximum(o,c)+base_rng
l=np.minimum(o,c)-base_rng
flat=(np.arange(N)%997)<7
c[flat]=o[flat]
h=np.maximum(h,np.maximum(o,c)+1);l=np.minimum(l,np.minimum(o,c)-1)
T=3
ts=np.repeat(mb,T)+np.tile(np.array([0,20000,50000],dtype=np.int64),N)
p0=o;p1=np.where(np.arange(N)%2==0,h,l);p2=c
bid=np.column_stack([p0,p1,p2]).reshape(-1).astype(np.int64)
spread=(2+(np.arange(N*T)%5)).astype(np.int64)
ask=bid+spread
idx=np.arange(N*T);ask[idx%1009==0]=bid[idx%1009==0];ask[idx%2017==0]=bid[idx%2017==0]-1
first=np.arange(0,N*T,T,dtype=np.int64);last=first+(T-1)
eb=mb.copy();bmat=bid.reshape(N,T);amat=ask.reshape(N,T)
ebh=bmat.max(1);ebl=bmat.min(1);eah=amat.max(1);eal=amat.min(1)
EX=(eb,ebh,ebl,eah,eal,first,last)
SPECS=list(W.specs());assert len(SPECS)==6840
summary={'schema':'QROS_G30_F08_SYNTHETIC_PARITY_V121_v1','seed':20260903,'minutes':N,'ticks':int(N*T),'specs_per_tf':len(SPECS),'timeframes':{},'status':'PASS'}
for tf in (1,5,10,15,30,60):
    t0=time.time();AA=A.bars(mb,o,h,l,c,tf);BB=B.bars(mb,o,h,l,c,tf)
    if base.digest_arrays(AA)!=base.digest_arrays(BB): raise SystemExit(f'BAR_PARITY_FAIL tf={tf}')
    pa=A.prepare(*AA);pb=B.prepare(*BB)
    ma=A.atr_sma(AA[2],AA[3],AA[4],14);mbb=B.atr_sma(BB[2],BB[3],BB[4],14)
    if not np.array_equal(np.nan_to_num(ma,nan=-1.0),np.nan_to_num(mbb,nan=-1.0)): raise SystemExit(f'ATR_PARITY_FAIL tf={tf}')
    for k in pa['contexts']:
        if not np.array_equal(pa['contexts'][k],pb['contexts'][k]): raise SystemExit(f'CONTEXT_PARITY_FAIL tf={tf} {k}')
    seq=hashlib.sha256();uB=np.zeros(len(AA[0]),bool);uS=np.zeros(len(AA[0]),bool);active_nonempty=0
    for sp in SPECS:
        ba,sa=A.mask(pa,*AA[1:],*sp);bb,sb=B.mask(pb,*BB[1:],*sp)
        if not np.array_equal(ba,bb) or not np.array_equal(sa,sb): raise SystemExit(f'SIGNAL_PARITY_FAIL tf={tf} {W.spec_key(sp)}')
        d=base.mask_digest(ba,sa);d2=base.mask_digest(bb,sb)
        if d!=d2:raise SystemExit(f'SIGNAL_DIGEST_FAIL tf={tf} {W.spec_key(sp)}')
        seq.update(W.spec_key(sp).encode()+b'\0'+bytes.fromhex(d));uB|=ba;uS|=sa
        active_nonempty += int(ba.any() or sa.any())
    step=tf*60000
    oaB=base.outcome_primary(ts,bid,ask,AA[0],ma,step,*EX,uB,1);obB=base.outcome_independent(ts,bid,ask,BB[0],mbb,step,*EX,uB,1)
    oaS=base.outcome_primary(ts,bid,ask,AA[0],ma,step,*EX,uS,-1);obS=base.outcome_independent(ts,bid,ask,BB[0],mbb,step,*EX,uS,-1)
    for side,OA,OB,U in [('BUY',oaB,obB,uB),('SELL',oaS,obS,uS)]:
        q=np.flatnonzero(U)
        for k in range(6):
            if not np.array_equal(OA[k][q],OB[k][q]):raise SystemExit(f'EXECUTION_PARITY_FAIL tf={tf} side={side} field={k}')
        ch1=base.select_a(q.astype(np.int64),OA[0],OA[1]);ch2=base.select_b(q.astype(np.int64),OA[0],OA[1])
        if not np.array_equal(ch1,ch2):raise SystemExit(f'SELECTION_PARITY_FAIL tf={tf} side={side}')
    summary['timeframes'][str(tf)]={'bars':int(len(AA[0])),'identities':6840,'nonempty_identity_pairs':active_nonempty,'union_buy':int(uB.sum()),'union_sell':int(uS.sum()),'identity_sequence_sha256':seq.hexdigest(),'execution_union_buy_parity':'PASS_EXACT','execution_union_sell_parity':'PASS_EXACT','seconds':round(time.time()-t0,3)}
    print(json.dumps({'tf':tf,**summary['timeframes'][str(tf)]},sort_keys=True),flush=True)
out=ROOT/'F08_SYNTHETIC_PARITY_V121.json';out.write_text(json.dumps(summary,separators=(',',':')),encoding='utf-8')
print('RESULT_SHA256',hashlib.sha256(out.read_bytes()).hexdigest(),flush=True)
print('PASS_F08_SYNTHETIC_PARITY',flush=True)
