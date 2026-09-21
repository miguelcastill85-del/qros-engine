from __future__ import annotations
import json,sys
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_geometry_compiler import compile_geometry_primitives,evaluate_compiled_geometry

TF_N={'M1':257,'M2':211,'M15':173,'H1':149,'H4':131}
FASTS=[5,8,9,13,18,20,21,26,35,44,50,53,70]
CNS=['OFF','2','3','4']; MBAS=['OFF','0.50','1.00','1.50','2.00']; MMS=['OFF','0.50','1.00','2.00']
VARIANTS=[{'contraction_n':a,'max_box_atr':b,'max_midpoint_to_fast_ema_atr':c} for a in CNS for b in MBAS for c in MMS if not(a==b==c=='OFF')]
if len(VARIANTS)!=79:raise SystemExit('GEOMETRY_VARIANT_COUNT_MISMATCH')

def fixture(n):
    rng=np.random.default_rng(7601000+n)
    base=np.cumsum(rng.normal(0,0.08,n))+100
    width=np.abs(rng.normal(0.8,0.25,n))+0.05
    sh=base+width/2;sl=base-width/2
    sh[::37]=np.nan;sl[::43]=np.nan
    bh=np.abs(rng.normal(0.8,0.25,(n,4)))+0.02
    for i in range(5,n,11):bh[i]=np.array([1.6,1.2,0.9,0.6])
    bh[::29,0]=np.nan
    atr=np.abs(rng.normal(0.9,0.2,n))+0.05;atr[::31]=0;atr[::47]=np.nan
    ind={'ATR14':atr}
    for f in FASTS:ind[f'EMA{f}']=base+rng.normal(0,0.35,n)+(f-35)*0.001
    return ind,sh,sl,bh

def oracle(ind,sh,sl,bh,bars,var,fast=None):
    out=[]
    for b in map(int,bars):
        if b<0 or b>=len(sh) or b-1<0 or b-1>=len(ind['ATR14']):out.append(False);continue
        if np.isnan(sh[b]) or np.isnan(sl[b]):out.append(False);continue
        ok=True;cn=var['contraction_n'];atr=ind['ATR14'][b-1]
        if cn!='OFF':
            k=int(cn);vals=bh[b,-k:]
            ok=not np.isnan(vals).any() and all(vals[j]>vals[j+1] for j in range(k-1))
        if ok and var['max_box_atr']!='OFF':
            ok=not np.isnan(atr) and atr>0 and abs(sh[b]-sl[b])/atr<=float(var['max_box_atr'])
        if ok and var['max_midpoint_to_fast_ema_atr']!='OFF':
            ff=35 if fast is None else fast;ema=ind[f'EMA{ff}'][b-1]
            ok=not np.isnan(atr) and atr>0 and not np.isnan(ema) and abs((sh[b]+sl[b])/2-ema)/atr<=float(var['max_midpoint_to_fast_ema_atr'])
        out.append(bool(ok))
    return np.array(out,dtype=bool)

comparisons=mismatches=future_checks=future_fail=true_count=0
per_tf={}
for tf,n in TF_N.items():
    ind,sh,sl,bh=fixture(n)
    bars=np.unique(np.r_[[-2,-1,0,1,n,n+2],np.arange(0,n,3),np.arange(2,n,7)]).astype(np.int64)
    pr=compile_geometry_primitives(ind,sh,sl,bh,tuple(FASTS))
    tfcmp=0
    for v in VARIANTS:
        fasts=[None] if v['max_midpoint_to_fast_ema_atr']=='OFF' else [None]+FASTS
        for fast in fasts:
            trend=None if fast is None else {'ema_triple':[fast,100,200]}
            a=evaluate_compiled_geometry(pr,bars,v,trend);b=oracle(ind,sh,sl,bh,bars,v,fast)
            comparisons+=1;tfcmp+=1;mismatches+=int(not np.array_equal(a,b));true_count+=int(a.sum())
    cutoff=int(n*0.6);ind2={k:v.copy() for k,v in ind.items()};sh2=sh.copy();sl2=sl.copy();bh2=bh.copy()
    for k in ind2:ind2[k][cutoff+1:]+=777.0
    sh2[cutoff+1:]+=333;sl2[cutoff+1:]-=333;bh2[cutoff+1:]=bh2[cutoff+1:,::-1]+99
    pr2=compile_geometry_primitives(ind2,sh2,sl2,bh2,tuple(FASTS));pre=bars[bars<=cutoff]
    for v in VARIANTS:
        for fast in ([None,5,35,70] if v['max_midpoint_to_fast_ema_atr']!='OFF' else [None]):
            trend=None if fast is None else {'ema_triple':[fast,100,200]}
            a=evaluate_compiled_geometry(pr,pre,v,trend);b=evaluate_compiled_geometry(pr2,pre,v,trend)
            future_checks+=1;future_fail+=int(not np.array_equal(a,b))
    per_tf[tf]={'bars':n,'candidate_indices':len(bars),'parity_comparisons':tfcmp,'future_cutoff_bar':cutoff}
if mismatches:raise SystemExit(f'GEOMETRY_PARITY_MISMATCH:{mismatches}')
if future_fail:raise SystemExit(f'GEOMETRY_FUTURE_PERTURBATION_FAIL:{future_fail}')
if true_count<=0:raise SystemExit('DEGENERATE_ALL_FALSE')
out={'status':'PASS','classification':'SYNTHETIC_NON_ECONOMIC','frozen_geometry_variants':len(VARIANTS),'fast_periods_tested':FASTS,'timeframes':per_tf,'parity_comparisons':comparisons,'mismatches':mismatches,'future_perturbation_checks':future_checks,'future_perturbation_failures':future_fail,'nondegenerate_true_results':true_count,'historical_claim':False,'retest_rearm_touched':False}
print(json.dumps(out,sort_keys=True,separators=(',',':')))
