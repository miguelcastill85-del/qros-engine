from __future__ import annotations
import hashlib, json, tempfile
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qros_geometry_compiler import compile_geometry_primitives, evaluate_compiled_geometry
from qros_factor_ir import FactorIR
from qros_typed_action import action_key, environment_manifest, receipt_self_hash, validate_receipt, atomic_publish_bytes, sha256_bytes

def safe(arr, idx):
    out=np.full(len(idx),np.nan);v=(idx>=0)&(idx<len(arr));out[v]=arr[idx[v]];return out

def reference_geometry(ind, bar_idx, variant, sh, sl, boxhist, active_trend=None):
    bar_idx=np.asarray(bar_idx,np.int64);idx=bar_idx-1;n=len(idx);ok=np.ones(n,bool)
    valid=(bar_idx>=0)&(bar_idx<len(sh))&(idx>=0)&(idx<len(ind['ATR14']));ok &= valid
    fh=safe(sh,bar_idx);fl=safe(sl,bar_idx);atr=safe(ind['ATR14'],idx);ok &= ~np.isnan(fh)&~np.isnan(fl)
    cn=variant['contraction_n'];mba=variant['max_box_atr'];mm=variant['max_midpoint_to_fast_ema_atr']
    if cn!='OFF':
        k=int(cn);vals=np.full((n,k),np.nan);vv=valid.copy();vals[vv]=boxhist[bar_idx[vv],-k:];ok &= ~np.isnan(vals).any(1)
        for j in range(k-1):ok &= vals[:,j]>vals[:,j+1]
    if mba!='OFF':ok &= (atr>0)&(np.abs(fh-fl)/atr<=float(mba))
    if mm!='OFF':
        fast=int(active_trend['ema_triple'][0]) if active_trend else 35
        ef=safe(ind[f'EMA{fast}'],idx);mid=(fh+fl)/2;ok &= (atr>0)&~np.isnan(ef)&(np.abs(mid-ef)/atr<=float(mm))
    return ok

rng=np.random.default_rng(20260921)
n=800
sh=np.cumsum(rng.normal(0,0.2,n))+100
sl=sh-rng.uniform(0.2,2.0,n)
sh[:9]=np.nan;sl[:9]=np.nan
boxhist=np.full((n,4),np.nan)
width=np.abs(sh-sl)
for i in range(n):
    if i>=3: boxhist[i]=width[i-3:i+1]
atr=np.abs(rng.normal(1.0,0.25,n));atr[[0,17,91]]=np.nan;atr[33]=0
ind={'ATR14':atr}
for fast in [5,9,18,35,44,53,70]:
    x=np.cumsum(rng.normal(0,0.05,n))+99.5
    x[:fast-1]=np.nan
    ind[f'EMA{fast}']=x
bar_idx=rng.integers(-3,n+3,3000,dtype=np.int64)
fasts=(5,9,18,35,44,53,70)
pr=compile_geometry_primitives(ind,sh,sl,boxhist,fasts)
variants=[]
for cn in ['OFF','2','3','4']:
  for mba in ['OFF','0.50','1.00','2.00']:
    for mm in ['OFF','0.50','1.00','2.00']:
      if cn=='OFF' and mba=='OFF' and mm=='OFF':continue
      variants.append({'contraction_n':cn,'max_box_atr':mba,'max_midpoint_to_fast_ema_atr':mm})
geometry_cases=0
for v in variants:
    for fast in (None,5,9,35,70):
        trend=None if fast is None else {'ema_triple':[fast,100,200]}
        a=reference_geometry(ind,bar_idx,v,sh,sl,boxhist,trend)
        b=evaluate_compiled_geometry(pr,bar_idx,v,trend)
        if not np.array_equal(a,b):
            raise SystemExit(f'GEOMETRY_MISMATCH:{v}:{fast}:{np.flatnonzero(a!=b)[:10].tolist()}')
        geometry_cases+=1

T=500
probe=np.arange(1,T+1,dtype=np.int64)
v={'contraction_n':'4','max_box_atr':'1.00','max_midpoint_to_fast_ema_atr':'2.00'}
base=evaluate_compiled_geometry(pr,probe,v,{'ema_triple':[35,70,105]})
sh2=sh.copy();sl2=sl.copy();bh2=boxhist.copy();ind2={k:v.copy() for k,v in ind.items()}
sh2[T+1:]+=rng.normal(50,10,len(sh2)-T-1);sl2[T+1:]-=rng.normal(50,10,len(sl2)-T-1);bh2[T+1:]=rng.normal(100,20,bh2[T+1:].shape)
for k in ind2:ind2[k][T+1:]+=rng.normal(100,20,len(ind2[k])-T-1)
pr2=compile_geometry_primitives(ind2,sh2,sl2,bh2,fasts)
after=evaluate_compiled_geometry(pr2,probe,v,{'ema_triple':[35,70,105]})
if not np.array_equal(base,after):raise SystemExit('FUTURE_PERTURBATION_CHANGED_PAST')

ind_short={k:v.copy() for k,v in ind.items()}
ind_short['ATR14']=ind_short['ATR14'][:-50]
pr_short=compile_geometry_primitives(ind_short,sh,sl,boxhist,fasts)
late=np.arange(n-40,n,dtype=np.int64)
contract_only={'contraction_n':'2','max_box_atr':'OFF','max_midpoint_to_fast_ema_atr':'OFF'}
ref_short=reference_geometry(ind_short,late,contract_only,sh,sl,boxhist,None)
new_short=evaluate_compiled_geometry(pr_short,late,contract_only,None)
if not np.array_equal(ref_short,new_short):raise SystemExit('INDICATOR_LENGTH_DRIFT_NOT_FAIL_CLOSED')

source=np.cumsum(rng.integers(1,20,4096,dtype=np.uint64))
p1=rng.random(4096)<0.12;p2=rng.random(4096)<0.45;p3=p1.copy();p4=rng.random(4096)<0.02
prims={'A':p1,'B':p2,'C_SAME_PHYSICAL_AS_A':p3,'D':p4}
recipes={'r0':(),'r1':('A',),'r2':('A','B'),'r3':('C_SAME_PHYSICAL_AS_A','B'),'r4':('A','B','D')}
ir=FactorIR.build(source,prims,recipes)
if ir.semantic_to_physical['A']!=ir.semantic_to_physical['C_SAME_PHYSICAL_AS_A']:raise SystemExit('PHYSICAL_DEDUPE_MISSED')
if len(ir.semantic_to_physical)!=4 or len(ir.physical_bitmaps)!=3:raise SystemExit('SEMANTIC_PHYSICAL_COUNTS_WRONG')
for rid,keys in recipes.items():
    direct=np.ones(len(source),bool)
    for k in keys:direct &= prims[k]
    if not np.array_equal(ir.recipe_mask(rid),direct):raise SystemExit('IR_RECONSTRUCTION_MISMATCH')
    raw=source[direct].astype('<u8',copy=False).tobytes();domain={'asset':'NQX','side':'BUY','timeframe':'M2'}
    want=hashlib.sha256(json.dumps(domain,sort_keys=True,separators=(',',':')).encode()+b'\0'+raw).hexdigest()
    if ir.class_hash(rid,domain)!=want:raise SystemExit('IR_CLASS_HASH_MISMATCH')

env=environment_manifest({'test':'adversarial'})
base_kwargs=dict(operation='GEOMETRY_COMPILE',operation_version='1',code_hashes={'geometry':'a'*64},domain={'asset':'NQX','side':'BUY','timeframe':'M2'},parameters={'fractal':3},input_artifacts={'bars':'b'*64,'ind':'c'*64},environment=env)
k0,payload=action_key(**base_kwargs)
mutations=[]
for label,mut in [
 ('code',{'code_hashes':{'geometry':'d'*64}}),
 ('domain',{'domain':{'asset':'NQX','side':'SELL','timeframe':'M2'}}),
 ('param',{'parameters':{'fractal':5}}),
 ('input',{'input_artifacts':{'bars':'b'*64,'ind':'e'*64}}),
 ('environment',{'environment':{**env,'numpy':'0.0.0'}}),
]:
    kw=base_kwargs.copy();kw.update(mut);k,_=action_key(**kw)
    if k==k0:raise SystemExit('ACTION_KEY_COLLISION:'+label)
    mutations.append(label)
receipt={'schema':'TEST','action_key':k0,'status':'PASS'};receipt['receipt_sha256']=receipt_self_hash(receipt);validate_receipt(receipt,expected_action_key=k0)
bad=dict(receipt);bad['status']='FAIL'
try:validate_receipt(bad,expected_action_key=k0);raise SystemExit('RECEIPT_TAMPER_ACCEPTED')
except ValueError:pass

with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'final.bin'
    try:atomic_publish_bytes(f,b'abc',crash_before_rename=True)
    except RuntimeError:pass
    if f.exists():raise SystemExit('CRASH_PUBLISHED_FINAL')
    h=atomic_publish_bytes(f,b'abc')
    if h!=sha256_bytes(b'abc') or f.read_bytes()!=b'abc':raise SystemExit('ATOMIC_RESUME_MISMATCH')

print(json.dumps({
 'status':'PASS',
 'geometry_exact_cases':geometry_cases,
 'future_perturbation_pass':True,
 'factor_ir_semantic_primitives':len(ir.semantic_to_physical),
 'factor_ir_physical_bitmaps':len(ir.physical_bitmaps),
 'factor_ir_recipes':len(ir.recipes),
 'action_key_mutations_rejected':mutations,
 'receipt_tamper_rejected':True,
 'atomic_crash_publish_rejected':True,
 'environment':env,
},sort_keys=True))
