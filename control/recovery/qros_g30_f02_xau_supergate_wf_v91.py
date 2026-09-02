#!/usr/bin/env python3
"""Aggregate certified V90 F02 XAU baseline shards and apply frozen V91 WF/WFE hard gate.
No parameter selection, no retuning, no MT5. Uses fixed frozen representatives only.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np

INPUT_SHA='0df9eefe74d6fae5541a0c6de1fed9bb4a5bd9141d106242bf65bb8be25019ab'
EXPECTED_SEGMENTS=('A_2018_2021','B_2022_2024','C_2025_2026')
EXPECTED_SHARDS=('H1_MID','M10_MID','M15_BID','M15_MID','M30_BID','M30_MID')
FOLDS=(
 ('2022H1',1640995200000,1656633600000),('2022H2',1656633600000,1672531200000),
 ('2023H1',1672531200000,1688169600000),('2023H2',1688169600000,1704067200000),
 ('2024H1',1704067200000,1719792000000),('2024H2',1719792000000,1735689600000),
 ('2025H1',1735689600000,1751328000000),('2025H2',1751328000000,1767225600000),
)
YEAR_BOUNDS={
 2018:(1514764800000,1546300800000),2019:(1546300800000,1577836800000),
 2020:(1577836800000,1609459200000),2021:(1609459200000,1640995200000),
 2022:(1640995200000,1672531200000),2023:(1672531200000,1704067200000),
 2024:(1704067200000,1735689600000),2025:(1735689600000,1767225600000),
 2026:(1767225600000,1798761600000),
}

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''): h.update(b)
 return h.hexdigest()

def pf(x):
 x=np.asarray(x,float); pos=float(x[x>0].sum()); neg=float(-x[x<0].sum())
 if neg==0: return float('inf') if pos>0 else 0.0
 return pos/neg

def safe(v):
 if isinstance(v,(np.integer,)): return int(v)
 if isinstance(v,(np.floating,)): v=float(v)
 if isinstance(v,float) and not math.isfinite(v): return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,dict): return {k:safe(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)): return [safe(x) for x in v]
 return v

def maxdd(x):
 x=np.asarray(x,float)
 if not len(x): return 0.0
 c=np.cumsum(x); peaks=np.maximum.accumulate(np.r_[0.0,c]); eq=np.r_[0.0,c]; dd=peaks-eq
 return float(dd.max())

def streaks(x):
 maxw=maxl=w=l=0
 for z in x:
  if z>0: w+=1;l=0
  elif z<0: l+=1;w=0
  else: w=l=0
  maxw=max(maxw,w);maxl=max(maxl,l)
 return maxw,maxl

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--baseline-dir',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if sha(a.input)!=INPUT_SHA: raise SystemExit('INPUT_SHA_MISMATCH')
 I=json.load(a.input.open()); expected={q['representative']:q for q in I['candidates']}
 if len(expected)!=28: raise SystemExit('EXPECTED_28_CANDIDATES')
 parts={rep:[] for rep in expected}; artifacts=[]
 for seg in EXPECTED_SEGMENTS:
  for shard in EXPECTED_SHARDS:
   p=a.baseline_dir/f'{seg}_{shard}.json'
   if not p.exists(): raise SystemExit('MISSING_BASELINE '+str(p))
   o=json.load(p.open())
   if o.get('schema')!='QROS_G30_F02_XAU_SUPERGATE_BASELINE_V90_v1' or o.get('status')!='PASS': raise SystemExit('BAD_BASELINE '+p.name)
   if o.get('segment')!=seg or o.get('shard')!=shard or o.get('input_sha256')!=INPUT_SHA: raise SystemExit('BASELINE_IDENTITY_MISMATCH '+p.name)
   artifacts.append({'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'candidate_count':o['candidate_count'],'signal_parity':o['signal_parity'],'trade_parity':o['trade_parity']})
   seen=set()
   for r in o['records']:
    rep=r['representative']
    if rep not in expected: raise SystemExit('UNEXPECTED_REP '+rep)
    if rep in seen: raise SystemExit('DUP_REP_IN_FILE '+rep)
    seen.add(rep); b=r['baseline']
    n=len(b['entry_t'])
    for k in ('exit_t','r_c','r_k','r_s'):
     if len(b[k])!=n: raise SystemExit('LEDGER_LENGTH_MISMATCH '+rep)
    parts[rep].append((seg,b))
 for rep,q in expected.items():
  if len(parts[rep])!=3: raise SystemExit(f'REP_SEGMENT_COUNT {rep} {len(parts[rep])}')
 records=[]; advanced=[]; rejected=[]
 for rep,q in sorted(expected.items(),key=lambda kv:kv[1]['cluster_id']):
  et=[];xt=[];rc=[];rk=[];rs=[]
  for seg,b in parts[rep]:
   et.extend(b['entry_t']);xt.extend(b['exit_t']);rc.extend(b['r_c']);rk.extend(b['r_k']);rs.extend(b['r_s'])
  et=np.asarray(et,np.int64);xt=np.asarray(xt,np.int64);rc=np.asarray(rc,float);rk=np.asarray(rk,float);rs=np.asarray(rs,float)
  order=np.argsort(et,kind='stable');et=et[order];xt=xt[order];rc=rc[order];rk=rk[order];rs=rs[order]
  if len(et)>1 and np.any(et[1:]<=et[:-1]): raise SystemExit('NON_STRICT_ENTRY_ORDER '+rep)
  annual={}
  for y,(lo,hi) in YEAR_BOUNDS.items():
   m=(et>=lo)&(et<hi);annual[str(y)]={'n':int(m.sum()),'net_c':float(rc[m].sum()),'net_k':float(rk[m].sum()),'net_s':float(rs[m].sum()),'pf_c':pf(rc[m]),'pf_s':pf(rs[m])}
  folds=[];den=0.0;oos_total=0.0
  for name,lo,hi in FOLDS:
   m=(et>=lo)&(et<hi); pre=et<lo;n=int(m.sum());net=float(rc[m].sum());iexp=float(rc[pre].mean()) if np.any(pre) else float('nan')
   folds.append({'fold':name,'n':n,'oos_net_c':net,'oos_pf_c':pf(rc[m]),'is_expectancy_c':iexp,'positive':bool(net>0)})
   if n and math.isfinite(iexp): den+=n*iexp;oos_total+=net
  wfe=float(oos_total/den) if den>0 else float('nan');pos=sum(x['positive'] for x in folds);wf_pass=bool(pos>=6 and math.isfinite(wfe) and wfe>=0.50)
  mw,ml=streaks(rc);dd=maxdd(rc)
  rec={'cluster_id':q['cluster_id'],'representative':rep,'direction':q['direction'],'type':q['type'],'size':q['size'],
       'baseline':{'n':int(len(et)),'net_c':float(rc.sum()),'net_k':float(rk.sum()),'net_s':float(rs.sum()),'pf_c':pf(rc),'pf_k':pf(rk),'pf_s':pf(rs),'expectancy_c':float(rc.mean()) if len(rc) else 0.0,'win_rate':float(np.mean(rc>0)) if len(rc) else 0.0,'max_dd_c_R':dd,'recovery_c':float(rc.sum()/dd) if dd>0 else float('inf'),'max_win_streak':mw,'max_loss_streak':ml},
       'annual':annual,'walk_forward':{'folds':folds,'positive_folds':pos,'folds_total':8,'wfe':wfe,'wfe_denominator':float(den),'oos_net_total':float(oos_total),'min_positive_folds':6,'min_wfe':0.50,'pass':wf_pass}}
  records.append(rec)
  (advanced if wf_pass else rejected).append(q['cluster_id'])
 root=hashlib.sha256(('\n'.join(advanced)+'\n').encode()).hexdigest() if advanced else hashlib.sha256(b'').hexdigest()
 obj={'schema':'QROS_G30_F02_XAU_SUPERGATE_WF_V91_RESULT_v1','status':'PASS_EVALUATED','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F02_SHOCK_MEASURE_ALTERNATIVES','asset':'XAUUSD','gate_ref':'control/QROS_G30_F02_XAU_SUPERGATE_WF_GATE_V91_v1.json','input_sha256':INPUT_SHA,'baseline_artifacts':artifacts,'candidate_count':28,'advanced_count':len(advanced),'rejected_count':len(rejected),'advanced_cluster_ids':advanced,'rejected_cluster_ids':rejected,'advanced_root_sha256':root,'records':records,'decision':'ONLY_WF_PASSERS_ADVANCE_TO_REMAINING_SUPERGATE_TESTS','guards':{'retuning':False,'economic_ranking':False,'holdout_reused_for_selection':False,'mt5':False,'branch_exhausted':False}}
 a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'status':obj['status'],'candidates':28,'advanced':len(advanced),'rejected':len(rejected),'advanced_cluster_ids':advanced},sort_keys=True));print('bytes',a.out.stat().st_size,'sha256',sha(a.out))
if __name__=='__main__': main()
