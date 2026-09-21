from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
import numpy as np,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_geometry_compiler import compile_geometry_primitives,evaluate_compiled_geometry
from qros_factor_ir import FactorIR
from qros_typed_action import action_key,environment_manifest,receipt_self_hash,validate_receipt
from qros_maskpack_regression import MAGIC,PACK_HDR,INDEX_REC,MAP_REC,canonical,verify_maskpack

def safe(a,i):
 out=np.full(len(i),np.nan);v=(i>=0)&(i<len(a));out[v]=a[i[v]];return out

def ref(ind,b,v,sh,sl,bh,tr=None):
 b=np.asarray(b,np.int64);ii=b-1;ok=(b>=0)&(b<len(sh))&(ii>=0)&(ii<len(ind['ATR14']))
 fh=safe(sh,b);fl=safe(sl,b);atr=safe(ind['ATR14'],ii);ok &= ~np.isnan(fh)&~np.isnan(fl)
 if v['contraction_n']!='OFF':
  k=int(v['contraction_n']);x=np.full((len(b),k),np.nan);vv=(b>=0)&(b<len(sh))&(ii>=0)&(ii<len(ind['ATR14']));x[vv]=bh[b[vv],-k:];ok &= ~np.isnan(x).any(1)
  for j in range(k-1):ok &= x[:,j]>x[:,j+1]
 if v['max_box_atr']!='OFF':ok &= (atr>0)&(np.abs(fh-fl)/atr<=float(v['max_box_atr']))
 if v['max_midpoint_to_fast_ema_atr']!='OFF':
  fast=int(tr['ema_triple'][0]) if tr else 35;ema=safe(ind[f'EMA{fast}'],ii);ok &= (atr>0)&~np.isnan(ema)&(np.abs((fh+fl)/2-ema)/atr<=float(v['max_midpoint_to_fast_ema_atr']))
 return ok

geo_checks=0;ir_checks=0
for seed in range(40):
 rng=np.random.default_rng(seed+88000);n=int(rng.integers(35,240));m=int(rng.integers(max(1,n-25),n+1))
 sh=np.cumsum(rng.normal(size=n))+100;sl=sh-rng.uniform(.01,3,n);bh=np.full((n,4),np.nan);w=np.abs(sh-sl)
 sh[:rng.integers(0,8)]=np.nan;sl[:rng.integers(0,8)]=np.nan
 for i in range(3,n):bh[i]=w[i-3:i+1]
 atr=np.abs(rng.normal(1,.8,m));
 if len(atr): atr[rng.integers(0,len(atr),min(3,len(atr)))]=np.nan
 if len(atr)>4:atr[4]=0
 ind={'ATR14':atr};fasts=[5,9,18,35,70]
 for f in fasts:
  L=int(rng.integers(max(1,n-10),n+1));x=np.cumsum(rng.normal(0,.1,L))+100;x[:min(f-1,L)]=np.nan;ind[f'EMA{f}']=x
 pr=compile_geometry_primitives(ind,sh,sl,bh,tuple(fasts));bars=rng.integers(-4,n+4,500)
 for _ in range(20):
  v={'contraction_n':rng.choice(['OFF','2','3','4']),'max_box_atr':rng.choice(['OFF','0.50','1.00','2.00']),'max_midpoint_to_fast_ema_atr':rng.choice(['OFF','0.50','1.00','2.00'])}
  if v=={'contraction_n':'OFF','max_box_atr':'OFF','max_midpoint_to_fast_ema_atr':'OFF'}:v['contraction_n']='2'
  fast=int(rng.choice(fasts));tr=None if rng.random()<.2 else {'ema_triple':[fast,100,200]}
  a=ref(ind,bars,v,sh,sl,bh,tr);b=evaluate_compiled_geometry(pr,bars,v,tr)
  if not np.array_equal(a,b):raise SystemExit(f'FUZZ_GEOMETRY_MISMATCH:{seed}:{v}:{fast}')
  geo_checks+=1
 count=int(rng.integers(1,3000));src=np.cumsum(rng.integers(1,100,count,dtype=np.uint64));prims={f'p{i}':rng.random(count)<rng.random() for i in range(12)};prims['dup']=prims['p0'].copy();recipes={}
 for r in range(20):recipes[f'r{r}']=tuple(rng.choice(list(prims),size=int(rng.integers(0,5)),replace=False))
 ir=FactorIR.build(src,prims,recipes);dom={'asset':'NQX','side':'BUY','timeframe':'M2'}
 for rid,ks in recipes.items():
  d=np.ones(count,bool)
  for k in ks:d &= prims[k]
  if not np.array_equal(d,ir.recipe_mask(rid)):raise SystemExit('FUZZ_IR_MASK_MISMATCH')
  raw=src[d].astype('<u8').tobytes();want=hashlib.sha256(canonical(dom)+b'\0'+raw).hexdigest()
  if ir.class_hash(rid,dom)!=want:raise SystemExit('FUZZ_IR_HASH_MISMATCH')
  ir_checks+=1
for bad in [np.array([-1,2,3],dtype=np.int64),np.array([1.,2.,3.]),np.array([1,1,2],dtype=np.int64),np.array([3,2,4],dtype=np.int64)]:
 try:FactorIR.build(bad,{'a':np.ones(len(bad),bool)},{'r':['a']});raise SystemExit('BAD_SOURCE_INDEX_ACCEPTED')
 except ValueError:pass
env=environment_manifest({'fuzz':'v1'});keys=set()
for i in range(100):
 k,_=action_key(operation='X',operation_version='1',code_hashes={'c':'a'*64},domain={'d':1},parameters={'p':1},input_artifacts={'x':hashlib.sha256(str(i).encode()).hexdigest()},environment=env);keys.add(k)
if len(keys)!=100:raise SystemExit('ACTION_KEY_COLLISION_FUZZ')
print(json.dumps({'status':'PASS','geometry_fuzz_checks':geo_checks,'factor_ir_fuzz_checks':ir_checks,'bad_source_index_cases_rejected':4,'action_key_unique_mutations':len(keys)},sort_keys=True))
