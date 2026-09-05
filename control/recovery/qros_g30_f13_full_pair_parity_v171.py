import sys,json,hashlib,os,time
from pathlib import Path
import numpy as np
sys.path.insert(0,'/mnt/data/qros_f13_v171');sys.path.insert(0,'/mnt/data')
import qros_g30_f13_primary_v171 as A
import qros_g30_f13_independent_v171 as B
import qros_f13_universe_v170 as U
OUT=Path('/mnt/data/qros_f13_v171/full_pair_parity_parts');OUT.mkdir(exist_ok=True)
LONG={'F08_VOLATILITY_CONTEXT','F09_SPREAD_CONTEXT','F10_TICK_INTENSITY'}

def dataset(n,seed):
 rng=np.random.default_rng(seed);step=3600000
 bucket=np.arange(n,dtype=np.int64)*step+1514764800000
 for idx,extra in [(n//5,step),(n//2,2*step),(4*n//5,3*step)]: bucket[idx:]+=extra
 d=rng.integers(-11,12,n);c=140000+np.cumsum(d).astype(np.int64)
 o=np.r_[c[0],c[:-1]]+rng.integers(-4,5,n);h=np.maximum(o,c)+rng.integers(1,22,n);l=np.minimum(o,c)-rng.integers(1,22,n)
 spread=rng.integers(1,23,n,dtype=np.int64);spread[10]=0;spread[-9]=0
 tick=rng.integers(1,150,n,dtype=np.int64)
 return bucket,o,h,l,c,spread,tick
short=dataset(420,1711301);long=dataset(2150,1711302)
preps={}
for name,data in [('short',short),('long',long)]:
 preps[(name,'A')]=A.prepare(*data[:5],data[5],data[6],'NQX');preps[(name,'B')]=B.prepare(*data[:5],data[5],data[6],'NQX')
ps=list(A.persistence_specs());assert ps==list(B.persistence_specs()) and len(ps)==18
groups=[];cur=None
for pair in U.specs():
 k=tuple(pair['frontiers'])
 if cur is None or cur[0]!=k:
  cur=[k,[]];groups.append(cur)
 cur[1].append(pair)
assert len(groups)==55 and sum(len(x[1]) for x in groups)==2229
master=hashlib.sha256();done_groups=0;total_cmp=0
for gi,(gkey,pairs) in enumerate(groups):
 fn=OUT/f'{gi:02d}_{gkey[0]}__X__{gkey[1]}.json'
 if fn.exists():
  obj=json.loads(fn.read_text())
  if obj.get('status')=='PASS_EXACT':
   master.update(bytes.fromhex(obj['root_sha256']));done_groups+=1;total_cmp+=obj['buy_sell_mask_comparisons'];continue
 mode='long' if any(x in LONG for x in gkey) else 'short';pa=preps[(mode,'A')];pb=preps[(mode,'B')]
 root=hashlib.sha256();cmpn=0;t0=time.time();mismatch=None
 for pair in pairs:
  root.update(json.dumps(pair,sort_keys=True,separators=(',',':')).encode()+b'\n')
  for timing in A.TIM:
   for th in A.TH:
    for fam,nn in ps:
     ba,sa=A.mask(pa,pair,timing,th,fam,nn);bb,sb=B.mask(pb,pair,timing,th,fam,nn);cmpn+=2
     if not np.array_equal(ba,bb) or not np.array_equal(sa,sb):
      mismatch={'pair':pair,'timing':timing,'threshold':th,'family':fam,'n':nn,'buy_diff':int(np.count_nonzero(ba!=bb)),'sell_diff':int(np.count_nonzero(sa!=sb))};break
     root.update(hashlib.sha256(np.packbits(ba).tobytes()).digest());root.update(hashlib.sha256(np.packbits(sa).tobytes()).digest())
    if mismatch:break
   if mismatch:break
  if mismatch:break
 obj={'schema':'QROS_G30_F13_PAIR_GROUP_SYNTHETIC_PARITY_V171_v1','group_index':gi,'frontiers':list(gkey),'pair_value_combinations':len(pairs),'dataset_mode':mode,'bars':len(pa['bucket']),'core_identities_per_pair':324,'buy_sell_mask_comparisons':cmpn,'mismatch':mismatch,'root_sha256':root.hexdigest(),'elapsed_sec':round(time.time()-t0,6),'status':'FAIL' if mismatch else 'PASS_EXACT'}
 tmp=fn.with_suffix('.tmp');tmp.write_text(json.dumps(obj,sort_keys=True,separators=(',',':')));os.replace(tmp,fn)
 print(json.dumps({'group':gi,'frontiers':gkey,'pairs':len(pairs),'mode':mode,'comparisons':cmpn,'status':obj['status'],'elapsed_sec':obj['elapsed_sec'],'root':obj['root_sha256']}),flush=True)
 if mismatch:raise SystemExit(2)
 master.update(bytes.fromhex(obj['root_sha256']));done_groups+=1;total_cmp+=cmpn
summary={'schema':'QROS_G30_F13_FULL_SYNTHETIC_PAIR_PARITY_V171_v1','groups':done_groups,'pair_value_combinations':2229,'core_identities_per_pair':324,'buy_sell_mask_comparisons':total_cmp,'mismatches':0,'status':'PASS_EXACT','group_root_sha256':master.hexdigest(),'primary_sha256':hashlib.sha256(Path(A.__file__).read_bytes()).hexdigest(),'independent_sha256':hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest()}
Path('/mnt/data/qros_f13_v171/QROS_G30_F13_FULL_SYNTHETIC_PAIR_PARITY_V171_v1.json').write_text(json.dumps(summary,sort_keys=True,separators=(',',':')))
print('FINAL '+json.dumps(summary,sort_keys=True,separators=(',',':')),flush=True)
