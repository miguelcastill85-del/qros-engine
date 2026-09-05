import sys, hashlib, json
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f11_signal_primary_v159 as A
import qros_g30_f11_signal_independent_v159 as B
rng=np.random.default_rng(20260905)
n=60*24*60
mb=np.arange(n,dtype=np.int64)*60000 + np.int64(1514764800000)
steps=rng.integers(-8,9,size=n,dtype=np.int64)
c=130000+np.cumsum(steps)
o=np.r_[c[0],c[:-1]]
wig_hi=rng.integers(0,12,size=n,dtype=np.int64);wig_lo=rng.integers(0,12,size=n,dtype=np.int64)
h=np.maximum(o,c)+wig_hi;l=np.minimum(o,c)-wig_lo
root=hashlib.sha256();comparisons=0
for tf in (1,5,10,15,30,60):
    ba=A.bars(mb,o,h,l,c,tf);bb=B.bars(mb,o,h,l,c,tf)
    if any(not np.array_equal(x,y) for x,y in zip(ba,bb)): raise SystemExit(f'BAR_PARITY_FAIL_{tf}')
    pa=A.prepare(*ba);pb=B.prepare(*bb)
    if not np.array_equal(np.nan_to_num(pa['atr14'],nan=-1.),np.nan_to_num(pb['atr14'],nan=-1.)):raise SystemExit(f'ATR_PARITY_FAIL_{tf}')
    for r in A.REFRACTORY:
      for timing in A.TIM:
       for th in A.TH:
        for fam in A.FAMS:
         for nn in A.NS:
          xa=A.mask(pa,*ba[1:],r,timing,th,fam,nn);xb=B.mask(pb,*bb[1:],r,timing,th,fam,nn)
          if any(not np.array_equal(u,v) for u,v in zip(xa,xb)):raise SystemExit(f'MASK_FAIL {tf} {r} {timing} {th} {fam} {nn}')
          for side,z in zip(('B','S'),xa):root.update(f'{tf}|{r}|{timing}|{th}|{fam}|{nn}|{side}'.encode()+b'\0'+z.tobytes())
          comparisons+=2
        xa=A.mask(pa,*ba[1:],r,timing,th,'SHOCK_BAR_BODY_DIRECTION_ONLY',1);xb=B.mask(pb,*bb[1:],r,timing,th,'SHOCK_BAR_BODY_DIRECTION_ONLY',1)
        if any(not np.array_equal(u,v) for u,v in zip(xa,xb)):raise SystemExit(f'BODY_FAIL {tf} {r} {timing} {th}')
        for side,z in zip(('B','S'),xa):root.update(f'{tf}|{r}|{timing}|{th}|BODY|1|{side}'.encode()+b'\0'+z.tobytes())
        comparisons+=2
m=np.zeros(20,bool);m[[1,2,3,5,6,10,11,12,18]]=True
expected={1:[1,3,5,10,12,18],2:[1,5,10,18],3:[1,5,10,18],5:[1,10,18],8:[1,10],13:[1,18]}
for r,idx in expected.items():
    a=np.flatnonzero(A.refractory_first(m,r)).tolist();b=np.flatnonzero(B.refractory_scan(m,r)).tolist()
    if a!=idx or b!=idx:raise SystemExit(f'REFRACTORY_SEMANTICS_FAIL r={r} a={a} b={b} exp={idx}')
print(json.dumps({'status':'PASS_EXACT','timeframes':6,'raw_identities_per_shard':2052,'buy_sell_comparisons':comparisons,'refractory_values':list(A.REFRACTORY),'synthetic_root_sha256':root.hexdigest()},sort_keys=True))
