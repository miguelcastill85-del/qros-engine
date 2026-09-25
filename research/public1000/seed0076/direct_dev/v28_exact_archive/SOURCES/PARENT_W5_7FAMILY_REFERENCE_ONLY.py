#!/usr/bin/env python3
"""Seed0076 DIRECT DEV: next serial frozen V209 cell, XAUUSD M1 w5.

No historic 60-shard read. No unobserved OOS or portfolio optimization.
All seven previously validated V209 filter families (<=2 at once) are enumerated
for BUY and SELL, physical masks deduplicated per NEW raw signal coordinate tape,
and exact quote trajectories simulated once per raw candidate. Atomic checkpoint.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, sys, time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
PIN=HERE/'source_pins';sys.path.insert(0,str(PIN));sys.path.insert(0,str(HERE))
from qros_seed0076_config_stream import filter_packages,canonical
from qros_seed0076_gate_engine_v221 import GateContext,session_eval_ms
from qros_seed0076_structural_v220 import structural_states,box_history4
from seed0076_direct_dev_backtest_v2 import fractal_levels,close_break_signals,DTYPE
from direct_six_family_mask_batch_v1 import raw_side,cross_bool,sha,writejson,gitblob
from direct_economic_event_cache_v1_1 import bar_valid_extrema,precompute_trajectory,schedule_pure

ROOT=Path('/mnt/data/seed0076_direct_dev');RAW=ROOT/'XAUUSD_DEV_PACKED17_151382388.bin'
BAR=ROOT/'bars_full/XAUUSD_M1_BID_BARS.npy';IND=ROOT/'indicators_full/XAUUSD_M1_INDICATORS.npz'
SPEC=PIN/'QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'
OUT=HERE/'direct_w5_7family_dev_v1'
FAMS={'TREND','MOMENTUM','VOLATILITY','SESSION','EMA_CROSS_RECENCY','TREND_STRENGTH','GEOMETRY'}
PIN_BLOBS={'spec':'c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf','gate_engine':'74290f11e7a95a25f54c5c9989af110de7dde4e2','structural':'805044c9918a87456a95e150a1c9a1292112cf4c','config_stream':'a01268bd8bab639977b22c419926d94306754bba'}
PINS={'spec':SPEC,'gate_engine':PIN/'qros_seed0076_gate_engine_v221.py','structural':PIN/'qros_seed0076_structural_v220.py','config_stream':PIN/'qros_seed0076_config_stream.py'}

def independent_fractal5(hi,lo):
 """Independent shifted NumPy w5: tie-asym center >= 2 older, > 2 newer."""
 n=len(hi);p=np.arange(2,n-3,dtype=np.int64);i=p+3
 fh=(hi[p]>=hi[p-2])&(hi[p]>=hi[p-1])&(hi[p]>hi[p+1])&(hi[p]>hi[p+2])
 fl=(lo[p]<=lo[p-2])&(lo[p]<=lo[p-1])&(lo[p]<lo[p+1])&(lo[p]<lo[p+2])
 vi=np.full(n,-1,np.int64);vj=vi.copy();vi[i[fh]]=p[fh];vj[i[fl]]=p[fl]
 hid=np.maximum.accumulate(vi);lid=np.maximum.accumulate(vj)
 h=np.full(n,np.nan);l=np.full(n,np.nan);vh=hid>=0;vl=lid>=0;h[vh]=hi[hid[vh]];l[vl]=lo[lid[vl]]
 return h,l,hid,lid

def jsonl(path,rows):
 with path.open('w') as f:
  for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')

def run(out=OUT,canaries=104):
 t0=time.perf_counter()
 for key,p in PINS.items():
  if gitblob(p)!=PIN_BLOBS[key]:raise RuntimeError('FROZEN_SOURCE_DRIFT_'+key)
 old=json.loads((HERE/'QROS_GEOMETRY_DELTA_CHECKPOINT.json').read_text())
 if sha(HERE/'GEOMETRY_DELTA_LOCK.json')!=old['authority']['geometry_delta_lock_sha256']:raise RuntimeError('PARENT_GEOMETRY_LOCK_DRIFT')
 prev=json.loads((HERE/'direct_six_family_mask_batch_v1/MANIFEST.json').read_text())
 if RAW.stat().st_size!=2573500596 or sha(RAW)!=prev['input_raw_sha256']:raise RuntimeError('RAW_IDENTITY_DRIFT')
 if sha(BAR)!=prev['input_bars_sha256'] or sha(IND)!=prev['input_indicators_sha256']:raise RuntimeError('BAR_IND_IDENTITY_DRIFT')
 spec=json.loads(SPEC.read_text());fps=[x for x in filter_packages(spec) if x.keys()<=FAMS]
 if len(fps)!=8629:raise RuntimeError('FROZEN_ORIGINAL_7F_FILTER_COUNT_DRIFT_'+str(len(fps)))
 if out.exists() or out.with_name(out.name+'.tmp').exists():raise RuntimeError('OUTPUT_OR_STAGE_EXISTS_USE_VERIFIED_CHECKPOINT_OR_INSPECT_STAGE')
 stage=out.with_name(out.name+'.tmp');stage.mkdir()
 bars=np.load(BAR,mmap_mode='r',allow_pickle=False);z=np.load(IND,allow_pickle=False);ind={k:z[k] for k in z.files};z.close()
 hi=bars['high_bid'];lo=bars['low_bid'];reference=independent_fractal5(hi,lo)
 orig=structural_states(hi.astype(np.float64),lo.astype(np.float64),5,0)
 numeric=fractal_levels(hi.astype(np.float64),lo.astype(np.float64),5,0)
 for label,test in [('ORIGINAL',orig),('INDEPENDENT_NUMBA',numeric)]:
  for j,(a,b) in enumerate(zip(reference,test)):
   if not np.array_equal(a,b,equal_nan=True):raise RuntimeError('FRACTAL_W5_PARITY_'+label+'_'+str(j))
 print('W5_INDEPENDENT_NUMPY_SOURCE_V220_AND_V2_FRACTAL_PARITY_PASS',len(bars),flush=True)
 sh,sl,hid,lid=reference
 box=box_history4(sh*.01,sl*.01,hid,lid)
 atr=np.r_[np.nan,ind['ATR14'][:-1]];basevalid=np.isfinite(sh)&np.isfinite(sl)
 contract={};
 for k in (2,3,4):
  c=box[:,-k:];contract[k]=np.all(np.isfinite(c),axis=1)&np.all(c[:,:-1]>c[:,1:],axis=1)
 boxratio=np.divide(np.abs(sh-sl)*.01,atr,out=np.full(len(bars),np.nan),where=atr>0)
 boxpred={th:np.isfinite(boxratio)&(boxratio<=float(th)) for th in ('0.50','1.00','1.50','2.00')}
 fasts=sorted({int(t[0]) for t in spec['ema_triples']}|{35});mid=(sh+sl)*.005;midpred={}
 for f in fasts:
  ema=np.r_[np.nan,ind['EMA'+str(f)][:-1]];ratio=np.divide(np.abs(mid-ema),atr,out=np.full(len(bars),np.nan),where=atr>0)
  for th in ('0.50','1.00','2.00'):midpred[(f,th)]=np.isfinite(ratio)&(ratio<=float(th))
 ticks=np.memmap(RAW,dtype=DTYPE,mode='r');mint,maxt=bar_valid_extrema(ticks['bid'],ticks['ask'],bars['first_source_index'],bars['last_source_index'])
 print('W5_VALID_BAR_BID_ASK_EXTREMA_PASS',len(mint),'seconds',round(time.perf_counter()-t0,3),flush=True)
 stats={};semantic=[];phys=[];econ=[];baseline={};artifacts={};all_ids=set();all_masks=0;all_fail=0
 try:
  for sign,side in ((1,'BUY'),(-1,'SELL')):
   started=time.perf_counter();si,st,bi=raw_side(bars,reference,sign);nc=len(si);idx=bi-1;tm=bars['bucket_ms'][idx].astype(np.int64)+60000
   # GateContext consumes original frozen V221 evaluators but reuses one copy of pinned indicators.
   ctx=GateContext.__new__(GateContext);ctx.asset='XAUUSD';ctx.tf='M1';ctx.side=side;ctx.point=.01;ctx.bars=bars;ctx.ind=dict(ind);ctx.ind['_CLOSE']=bars['close_bid'].astype(np.float64)*.01;ctx._cache={'M1':(bars,ctx.ind)}
   # Baseline w5 EMA9/20/50 event+stop identity independently from source raw crossing.
   ef,em,es=(ind['EMA9'],ind['EMA20'],ind['EMA50']);eligible=(ef[idx]>em[idx])&(em[idx]>es[idx]) if sign==1 else (ef[idx]<em[idx])&(em[idx]<es[idx])
   bsi,bst=close_break_signals(bars['close_bid'],bars['first_source_index'],orig[0],orig[1],orig[2],orig[3],ef,em,es,sign)
   if not(np.array_equal(si[eligible],bsi) and np.array_equal(st[eligible],bst)):raise RuntimeError('W5_BASELINE_EVENT_AND_STOP_TAPE_DRIFT_'+side)
   baseline[side]={'EMA9_20_50_original_close_break_signals':len(bsi),'raw_candidates':nc,'raw_tape_sha256':hashlib.sha256(np.stack((si,st,bi),axis=1).astype('<i8').tobytes()).hexdigest()}
   np.savez_compressed(stage/(side+'_W5_RAW_CANDIDATES.npz'),source_ix=si,stop_cents=st,bar_idx=bi,session_server_ms=tm)
   rawhash=sha(stage/(side+'_W5_RAW_CANDIDATES.npz'))
   pre=precompute_trajectory(ticks['ts'],ticks['bid'],ticks['ask'],bars['bucket_ms'],bars['first_source_index'],bars['last_source_index'],mint,maxt,si,st,bi,sign)
   np.savez_compressed(stage/(side+'_W5_TRAJECTORIES.npz'),source_ix=si,stop_cents=st,entry_ix=pre[0],exit_ix=pre[1],entry_cents=pre[2],exit_cents=pre[3],risk_cents=pre[4],state=pre[5],raw_candidate_sha256=rawhash)
   print('W5_TRAJECTORY_PASS',side,'raw',nc,'states',np.bincount(pre[5],minlength=6).tolist(),flush=True)
   primitives={};crosses={};geos={};masks=[];ids={};counts={};checked=0
   # Freeze canary positions ex ante from original package order; force coverage of seven families.
   checks=set(np.linspace(0,len(fps)-1,canaries,dtype=int).tolist());checks|={next(i for i,p in enumerate(fps) if fam in p) for fam in FAMS}
   def standard(fam,var,trend):
    key=(fam,canonical(var),canonical(trend) if trend and fam=='EMA_CROSS_RECENCY' else None)
    if key not in primitives:
     if fam=='EMA_CROSS_RECENCY':
      fast,medium=map(int,trend['ema_triple'][:2]) if trend else (35,70)
      k=(fast,medium,int(var['lookback_bars']))
      if k not in crosses:crosses[k]=cross_bool(ind,idx,sign,*k)
      p=crosses[k]
     elif fam=='SESSION':p=session_eval_ms(tm,var)
     else:p=ctx.eval_family(fam,var,si,bi,sh*.01,sl*.01,box,trend,tm)
     if len(p)!=nc:raise RuntimeError('PREDICATE_SHAPE_'+fam)
     primitives[key]=np.asarray(p,dtype=bool);counts[fam]=counts.get(fam,0)+1
    return primitives[key]
   def geometry(var,trend):
    fast=int(trend['ema_triple'][0]) if trend else 35
    key=(canonical(var),fast)
    if key not in geos:
     p=basevalid.copy()
     if var['contraction_n']!='OFF':p &= contract[int(var['contraction_n'])]
     if var['max_box_atr']!='OFF':p &= boxpred[var['max_box_atr']]
     if var['max_midpoint_to_fast_ema_atr']!='OFF':p &= midpred[(fast,var['max_midpoint_to_fast_ema_atr'])]
     geos[key]=p[bi].copy()
    return geos[key]
   side_sem=[];side_phys=[];side_econ=[]
   for i,pkg in enumerate(fps):
    trend=pkg.get('TREND');bits=np.ones(nc,bool)
    for fam in sorted(pkg):bits &= geometry(pkg[fam],trend) if fam=='GEOMETRY' else standard(fam,pkg[fam],trend)
    if i in checks:
     ref=ctx.eval_gates(pkg,si,bi,sh*.01,sl*.01,box,tm)
     if not np.array_equal(ref,bits):raise RuntimeError('FROZEN_V221_GATE_CANARY_MISMATCH_'+side+'_'+str(i))
     checked+=1
    packed=np.packbits(bits,bitorder='little');pid=hashlib.sha256(b'QROS_DIRECT_M1_W5_PHYSMASK_V1\0'+side.encode()+b'\0'+rawhash.encode()+b'\0'+packed.tobytes()).hexdigest()
    if pid not in ids:
     ids[pid]=len(masks);masks.append(packed)
     side_phys.append({'physical_mask_id':pid,'side':side,'physical_index':len(masks)-1,'event_count':int(bits.sum()),'raw_candidate_count':nc,'coordinate_tape_sha256':rawhash})
    elif not np.array_equal(masks[ids[pid]],packed):raise RuntimeError('MASK_COLLISION_'+side)
    base={'asset':'XAUUSD','side':side,'timeframe':'M1','fractal_window':5,'tie_policy':'SOURCE_ASYMMETRIC','rearm_mode':'ONE_SIGNAL_PER_LEVEL','trigger':'CLOSE_BREAK'}
    cid=hashlib.sha256(canonical({**base,'filters':pkg})).hexdigest()
    if cid in all_ids:
     raise RuntimeError('DUPLICATE_SEMANTIC_CONFIG_ID')
    all_ids.add(cid)
    side_sem.append({'semantic_config_id':cid,'causal_hypothesis_id':cid,'side':side,'filters':pkg,'physical_mask_id':pid,'event_count':int(bits.sum()),'exposure':'2018_2019_DEV_EXPOSED_FOR_RELATED_GENEALOGY','base':base})
   if len(side_sem)!=8629:raise RuntimeError('INCOMPLETE_W5_SIDE_'+side)
   maskmat=np.stack(masks)
   np.savez_compressed(stage/(side+'_W5_UNIQUE_MASKS.npz'),masks=maskmat,mask_ids=np.array(list(ids),dtype='<U64'),raw_candidate_sha256=rawhash)
   for row in side_phys:
    m=masks[row['physical_index']];sel=np.flatnonzero(np.unpackbits(m,bitorder='little')[:nc]);n,rsum,pos,neg,dd,rej,_=schedule_pure(ticks['ts'],si,sel,*pre,st,sign)
    bad=int(rej[5]);all_fail+=int(bad>0)
    side_econ.append({'physical_mask_id':row['physical_mask_id'],'side':side,'signals':len(sel),'standalone_trades':int(n),'gross_R_spread_included_commission_excluded':None if bad else float(rsum),'PF_R_spread_only':None if bad or neg==0 else float(pos/neg),'DD_R':None if bad else float(dd),'unresolved_candidates_selected':bad,'status':'INVALID_UNRESOLVED' if bad else 'EXPLORATORY_DEV_EXPOSED_STANDALONE_ONLY'})
   jsonl(stage/(side+'_W5_SEMANTIC_MAP.jsonl'),side_sem);jsonl(stage/(side+'_W5_PHYSICAL_CLASSES.jsonl'),side_phys);jsonl(stage/(side+'_W5_ECONOMIC_DIAGNOSTICS.jsonl'),side_econ)
   semantic.extend(side_sem);phys.extend(side_phys);econ.extend(side_econ);all_masks+=len(masks)
   stats[side]={'raw_candidates':nc,'filter_packages':len(side_sem),'unique_masks':len(masks),'physical_aliases':len(side_sem)-len(masks),'gate_canaries_exact':checked,'candidate_states':np.bincount(pre[5],minlength=6).tolist(),'standalone_trade_rows_sum':sum(r['standalone_trades'] for r in side_econ),'invalid_unresolved_masks':sum(r['status']=='INVALID_UNRESOLVED' for r in side_econ),'secs_including_new_trajectories':round(time.perf_counter()-started,4)}
   print('W5_SEVEN_FAMILY_SIDE_PASS',side,json.dumps(stats[side],sort_keys=True),flush=True)
   del ctx,primitives,crosses,geos,masks,maskmat
  if len(semantic)!=17258 or len(all_ids)!=17258 or len(phys)!=len(econ) or all_fail:raise RuntimeError('W5_GLOBAL_COVERAGE_OR_UNRESOLVED')
  artifacts={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(stage.iterdir())}
  manifest={'schema':'QROS_SEED0076_DIRECT_ORIGINAL_V209_M1_W5_7F_DEV_V1','status':'PASS_EXPLORATORY_DEV_EXPOSED_NOT_GATE_A','original_V209_spec_git_blob':PIN_BLOBS['spec'],'code_sha256':sha(Path(__file__)),'asset':'XAUUSD','timeframe':'M1','fractal_window':5,'tie_policy':'SOURCE_ASYMMETRIC','rearm_mode':'ONE_SIGNAL_PER_LEVEL','trigger':'CLOSE_BREAK','sides':['BUY','SELL'],'seven_families':sorted(FAMS),'raw_xau_sha256':prev['input_raw_sha256'],'bar_sha256':prev['input_bars_sha256'],'ind_sha256':prev['input_indicators_sha256'],'previous_geometry_lock_sha256':sha(HERE/'GEOMETRY_DELTA_LOCK.json'),'semantic_configurations_new':len(semantic),'unique_physical_masks_new':len(phys),'no_causal_filter_family_added':True,'parent_w3_17258_reused_and_unmodified':True,'economic_overlay':'PREDECLARED_EXISTING_19_30_SERVER_EXPLORATORY_ONLY_NO_TP_OPPOSITE_FRACTAL_STOP_MAX3_PER_DAY_PER_SIDE','quotes':'REAL_BID_ASK_SKIP_ZERO_CROSSED_STOP_FIRST_GAP_REAL_QUOTE','broker_commission_included':False,'historical_symbol_calendar_certified':False,'holdout_open':False,'old_60_shards_inspected':False,'selection_performed':False,'multiplicity_count_full_semantic':len(all_ids),'baseline_signal_parity':baseline,'side_statistics':stats,'independent_full_tick_execution_oracle':'PENDING','artifacts':artifacts,'time_seconds_excluding_source_recovery':round(time.perf_counter()-t0,4)}
  writejson(stage/'MANIFEST.json',manifest);os.replace(stage,out)
  print('W5_SEVEN_FAMILY_BATCH_COMPLETE',json.dumps({'semantic':len(semantic),'physical':len(phys),'side':stats,'seconds':manifest['time_seconds_excluding_source_recovery']},sort_keys=True),flush=True)
  return manifest
 except Exception:
  print('W5_INCOMPLETE_STAGE_PRESERVED',stage,flush=True);raise

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--out',default=str(OUT));a.add_argument('--canaries',type=int,default=104);v=a.parse_args();run(Path(v.out),v.canaries)
