import sys, json, hashlib, numpy as np
sys.path.insert(0,'/mnt/data/qros_f13_v171')
sys.path.insert(0,'/mnt/data')
import qros_g30_f13_primary_v171 as A
import qros_g30_f13_independent_v171 as B
import qros_f13_universe_v170 as U
rng=np.random.default_rng(17113)
n=420
bucket=np.arange(n,dtype=np.int64)*60000+1514764800000
bucket[91:]+=60000; bucket[207:]+=120000; bucket[332:]+=180000
steps=rng.integers(-9,10,n); c=120000+np.cumsum(steps).astype(np.int64)
o=np.r_[c[0],c[:-1]]+rng.integers(-3,4,n)
h=np.maximum(o,c)+rng.integers(1,18,n); l=np.minimum(o,c)-rng.integers(1,18,n)
spread=rng.integers(1,24,n,dtype=np.int64); spread[::113]=0
tick=rng.integers(1,120,n,dtype=np.int64)
pa=A.prepare(bucket,o,h,l,c,spread,tick,'NQX'); pb=B.prepare(bucket,o,h,l,c,spread,tick,'NQX')
ps=list(A.persistence_specs()); assert ps==list(B.persistence_specs()) and len(ps)==18
wanted={('F07_POST_SHOCK_CONFIRMATION','F11_REFRACTORY'),('F07_POST_SHOCK_CONFIRMATION','F12_DAY_OF_WEEK')}
root=hashlib.sha256(); comps=0; mism=[]; pairs=0
for pair in U.specs():
 if tuple(pair['frontiers']) not in wanted: continue
 pairs+=1
 for timing in A.TIM:
  for th in A.TH:
   for fam,nn in ps:
    ba,sa=A.mask(pa,pair,timing,th,fam,nn); bb,sb=B.mask(pb,pair,timing,th,fam,nn)
    comps+=2
    if not np.array_equal(ba,bb) or not np.array_equal(sa,sb):
     mism.append({'pair':pair,'timing':timing,'th':th,'fam':fam,'n':nn,'buy_diff':int(np.count_nonzero(ba!=bb)),'sell_diff':int(np.count_nonzero(sa!=sb))})
     if len(mism)>=10: break
    root.update(np.packbits(ba).tobytes());root.update(np.packbits(sa).tobytes())
   if mism: break
  if mism: break
 if mism: break
out={'pairs':pairs,'buy_sell_mask_comparisons':comps,'mismatches':mism,'pass':not mism,'root':root.hexdigest()}
print(json.dumps(out,sort_keys=True,separators=(',',':')))
