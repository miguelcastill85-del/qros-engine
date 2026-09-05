import sys, numpy as np, json, hashlib
sys.path.insert(0,'/mnt/data/qros_f13_v171')
import qros_g30_f13_primary_v171 as A
import qros_g30_f13_independent_v171 as B
rng=np.random.default_rng(17013)
n=2305
bucket=np.arange(n,dtype=np.int64)*60000+1514764800000
# inject 3 gaps but keep monotonic; direct bars signal test expects gaps relevant only F07 contiguity
bucket[700:]+=60000;bucket[1500:]+=120000
steps=rng.integers(-7,8,n);c=100000+np.cumsum(steps).astype(np.int64)
o=np.r_[c[0],c[:-1]]+rng.integers(-2,3,n);hi=np.maximum(o,c)+rng.integers(1,15,n);lo=np.minimum(o,c)-rng.integers(1,15,n)
spread=rng.integers(1,22,n,dtype=np.int64);spread[::97]=0
tick=rng.integers(1,90,n,dtype=np.int64)
pa=A.prepare(bucket,o,hi,lo,c,spread,tick,'NQX');pb=B.prepare(bucket,o,hi,lo,c,spread,tick,'NQX')
checks=[]
def eq(name,x,y):
 ok=np.array_equal(np.nan_to_num(x,nan=-999999.0),np.nan_to_num(y,nan=-999999.0));checks.append((name,ok));
 if not ok:
  q=np.flatnonzero(np.nan_to_num(x,nan=-999999.)!=np.nan_to_num(y,nan=-999999.));print('MISMATCH',name,q[:10]);raise SystemExit(2)
for p in (7,10,14,20,28,50):
 for sm in ('SMA_TR','WILDER_RMA_TR','EMA_TR'):eq(f'atr_{p}_{sm}',A.atr(hi,lo,c,p,sm),B.atr(hi,lo,c,p,sm))
for k in pa['bases']: eq('base_'+str(k),pa['bases'][k][0],pb['bases'][k][0]);eq('baseS_'+str(k),pa['bases'][k][1],pb['bases'][k][1])
for k in pa['loc']:eq('locB'+k,pa['loc'][k][0],pb['loc'][k][0]);eq('locS'+k,pa['loc'][k][1],pb['loc'][k][1])
for k in pa['wick']:eq('wickB'+k,pa['wick'][k][0],pb['wick'][k][0]);eq('wickS'+k,pa['wick'][k][1],pb['wick'][k][1])
for dname in ('vol_ctx','spread_ctx','tick_ctx'):
 for k in pa[dname]:eq(dname+str(k),pa[dname][k],pb[dname][k])
# bars aggregation independent path test on synthetic M1
for tf in (1,5,10,15,30,60):
 ba=A.bars(bucket,o,hi,lo,c,tf);bb=B.bars(bucket,o,hi,lo,c,tf)
 for j in range(5):eq(f'bars_{tf}_{j}',ba[j],bb[j])
print(json.dumps({'checks':len(checks),'all_pass':all(x[1] for x in checks)},sort_keys=True))
