#!/usr/bin/env python3
"""Seed0076 exploratory DEV: independent event trajectory once, 1864 mask schedulers.

Same 19:30 experimental flat as already exposed V2. No real broker commission;
no per-symbol historical holiday calendar certification, no holdout or selection.
"""
from __future__ import annotations
import csv,hashlib,json,os,time,sys
from pathlib import Path
import numpy as np
from numba import njit

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from seed0076_direct_dev_backtest_v2 import simulate as v2_simulate,config as old_config
from direct_six_family_mask_batch_v1 import sha,writejson
ROOT=Path('/mnt/data/seed0076_direct_dev')
RAW=ROOT/'XAUUSD_DEV_PACKED17_151382388.bin'
BAR=ROOT/'bars_full/XAUUSD_M1_BID_BARS.npy'
MASK=HERE/'direct_six_family_mask_batch_v1'
DAY=86400000;OPEN=61*60000;FLAT=(19*60+30)*60000;CLOSE=(23*60+59)*60000;FRI=(23*60+55)*60000
TICK=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])

@njit(cache=True)
def bar_valid_extrema(ts_bid,ts_ask,first,last):
 n=len(first);minb=np.full(n,np.iinfo(np.int32).max,np.int32);maxa=np.full(n,np.iinfo(np.int32).min,np.int32)
 for bi in range(n):
  mb=np.iinfo(np.int32).max;ma=np.iinfo(np.int32).min
  for ix in range(first[bi],last[bi]+1):
   bid=ts_bid[ix];ask=ts_ask[ix]
   if bid>0 and ask>bid:
    if bid<mb:mb=bid
    if ask>ma:ma=ask
  minb[bi]=mb;maxa[bi]=ma
 return minb,maxa

@njit(cache=True)
def precompute_trajectory(ts,bid,ask,bucket,first,last,minb,maxa,raw_idx,stops,bar_idx,side):
 n=len(raw_idx);entry_ix=np.full(n,-1,np.int64);exit_ix=np.full(n,-1,np.int64);entrypx=np.zeros(n,np.int32);exitpx=np.zeros(n,np.int32);risk=np.zeros(n,np.int32);reason=np.zeros(n,np.int8)
 # reason codes: 0 out-of-session; 1 no quote in signal minute; 2 stop geometry; 3 unresolved exit; 4 STOP; 5 FLAT
 for j in range(n):
  si=raw_idx[j];s=stops[j];b=bar_idx[j]
  if si<0 or si>=len(ts):raise RuntimeError('CANDIDATE_OOB')
  day=ts[si]//DAY;tod=ts[si]%DAY;week=(day+3)%7
  if week>4 or tod<OPEN or tod>=FLAT:continue
  bar_end=(ts[si]//60000+1)*60000
  ei=-1
  for k in range(si,last[b]+1):
   if ts[k]>=bar_end:break
   if bid[k]>0 and ask[k]>bid[k]:ei=k;break
  if ei<0:reason[j]=1;continue
  price=ask[ei] if side==1 else bid[ei];r=price-s if side==1 else s-price
  if r<=0 or (side==1 and bid[ei]<=s) or (side==-1 and ask[ei]>=s):reason[j]=2;continue
  entry_ix[j]=ei;entrypx[j]=price;risk[j]=r
  end=(day*DAY)+(FRI if week==4 else CLOSE)
  out=-1;px=0;why=3
  for bi in range(b,len(bucket)):
   if bucket[bi]//DAY!=day or bucket[bi]>=end:break
   start=first[bi];endbar=last[bi]
   if start<ei:start=ei
   if start>endbar:continue
   postflat=bucket[bi]>=day*DAY+FLAT
   # If bar strictly before flat and no executable quote can touch stop, skip entire bar.
   if not postflat and ((side==1 and minb[bi]>s) or (side==-1 and maxa[bi]<s)):continue
   for k in range(start,endbar+1):
    if ts[k]>=end:break
    if bid[k]<=0 or ask[k]<=bid[k]:continue
    mark=bid[k] if side==1 else ask[k]
    if (side==1 and mark<=s) or (side==-1 and mark>=s):out=k;px=mark;why=4;break
    if ts[k]>=day*DAY+FLAT:out=k;px=mark;why=5;break
   if out>=0:break
  exit_ix[j]=out;exitpx[j]=px;reason[j]=why
 return entry_ix,exit_ix,entrypx,exitpx,risk,reason

# Single pure scheduler: timestamps are explicit provenance-bound inputs.
@njit(cache=True)
def schedule_pure(timestamps,tr_raw,ix,ei,xi,ep,xp,risk,reason,stop,side,num_max=3,return_trades=False):
 current=-1;daily=0;active=-1;N=0;rsum=0.;pos=0.;neg=0.;high=0.;dd=0.;rejected=np.zeros(8,np.int64)
 tr=np.empty((len(ix),11),np.float64) if return_trades else np.empty((0,11),np.float64)
 for ci in ix:
  si=tr_raw[ci];state=reason[ci]
  if si<=active:rejected[0]+=1;continue
  if state==0:rejected[1]+=1;continue
  day=timestamps[si]//DAY
  if day!=current:current=day;daily=0
  if daily>=num_max:rejected[2]+=1;continue
  if state==1:rejected[3]+=1;continue
  if state==2:rejected[4]+=1;continue
  if state==3:rejected[5]+=1;break
  if state not in (4,5):raise RuntimeError('BAD_PRECOMPUTED_EVENT_STATE')
  rv=(xp[ci]-ep[ci])/risk[ci] if side==1 else (ep[ci]-xp[ci])/risk[ci]
  rsum+=rv
  if rv>0:pos+=rv
  elif rv<0:neg-=rv
  if rsum>high:high=rsum
  d=high-rsum
  if d>dd:dd=d
  if return_trades:tr[N]=[ci,side,si,ei[ci],xi[ci],ep[ci],stop[ci],xp[ci],rv,1 if state==4 else 2,day]
  N+=1;daily+=1;active=xi[ci]
 return N,rsum,pos,neg,dd,rejected,tr[:N]

def run(path=HERE/'direct_six_family_economic_v1'):
 start=time.perf_counter();man=json.loads((MASK/'MANIFEST.json').read_text())
 if man['input_raw_sha256']!='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53':raise RuntimeError('RAW_SHA_MISMATCH')
 if man['input_bars_sha256']!=sha(BAR):raise RuntimeError('BAR_SHA_MISMATCH')
 if path.exists():raise RuntimeError('OUTPUT_EXISTS_REUSE_ONLY')
 tmp=path.with_name(path.name+'.tmp');tmp.mkdir(exist_ok=False)
 ticks=np.memmap(RAW,dtype=TICK,mode='r');bars=np.load(BAR,mmap_mode='r',allow_pickle=False)
 t0=time.perf_counter()
 mn,mx=bar_valid_extrema(ticks['bid'],ticks['ask'],bars['first_source_index'],bars['last_source_index'])
 print('BAR_VALID_QUOTE_EXTREMA',len(mn),'seconds',round(time.perf_counter()-t0,3),flush=True)
 per={};catalog=[];tapes={};samples={}
 for side,name in [(1,'BUY'),(-1,'SELL')]:
  q=np.load(MASK/(name+'_RAW_CANDIDATES.npz'),allow_pickle=False)
  si=q['source_ix'];st=q['stop_cents'];bi=q['bar_idx']
  t1=time.perf_counter()
  t=precompute_trajectory(ticks['ts'],ticks['bid'],ticks['ask'],bars['bucket_ms'],bars['first_source_index'],bars['last_source_index'],mn,mx,si,st,bi,side)
  states=np.bincount(t[5],minlength=6)
  np.savez_compressed(tmp/(name+'_TRAJECTORIES.npz'),source_ix=si,stop_cents=st,entry_ix=t[0],exit_ix=t[1],entry_cents=t[2],exit_cents=t[3],risk_cents=t[4],state=t[5])
  print('EVENT_TRAJECTORY',name,{'raw_events':len(si),'states':states.tolist(),'seconds':round(time.perf_counter()-t1,3)},flush=True)
  masks=np.load(MASK/(name+'_UNIQUE_MASKS.npz'),allow_pickle=False)
  array=masks['masks'];mids=masks['mask_ids'];validclasses=0;invalidclasses=0;trade_total=0
  for i,(packed,pid) in enumerate(zip(array,mids)):
   selected=np.flatnonzero(np.unpackbits(packed,bitorder='little')[:len(si)])
   r=schedule_pure(ticks['ts'],si,selected,*t,st,side)
   n,rsum,pos,neg,dd,reject,_=r
   status='EXPLORATORY_SPREAD_ONLY_NO_COMMISSION_NO_FINAL_SESSION_CERT' if reject[5]==0 else 'INVALID_UNRESOLVED_QUOTE_STOPPED'
   catalog.append({'physical_mask_id':str(pid),'side':name,'n_signals':int(len(selected)),'n_trades':int(n),'R_spread_included_commission_excluded':float(rsum) if reject[5]==0 else None,'PF_spread_only':float(pos/neg) if neg and reject[5]==0 else None,'max_dd_R':float(dd) if reject[5]==0 else None,'status':status,'rejected_counts':reject.tolist()})
   if reject[5]:invalidclasses+=1
   else:validclasses+=1
   trade_total+=n
  tapes[name]=(si,st,t)
  per[name]={'physical_masks':len(array),'valid_exploratory_masks':validclasses,'unresolved_masks':invalidclasses,'raw_candidate_states':states.tolist(),'sum_trades_across_standalone_masks':trade_total,'trajectory_seconds':round(time.perf_counter()-t1,3)}
  print('STANDALONE_BATCH',name,per[name],flush=True)
 # Recreate EXACT existing 2-configuration shared-cap benchmark, including cross-side interference.
 # Earlier batch source masks are canonical V209 IDs and include the same frozen EMA9/20/50 baseline.
 wanted={name:old_config(side)['semantic_config_id'] for side,name in [(1,'BUY'),(-1,'SELL')]}
 # Build a semantic->physical mapping from the verified MASK manifest, never from PnL results.
 sem=[json.loads(x) for x in (MASK/'SEMANTIC_CONFIG_TO_PHYSICAL_MASK.jsonl').read_text().splitlines()]
 info={x['semantic_config_id']:(x['side'],x['physical_mask_id']) for x in sem}
 combined=[]
 for side,name in [(1,'BUY'),(-1,'SELL')]:
  assert wanted[name] in info and info[wanted[name]][0]==name
  si,st,t=tapes[name]
  q=np.load(MASK/(name+'_UNIQUE_MASKS.npz'),allow_pickle=False)
  masks=q['masks'];keys=q['mask_ids'];at=int(np.flatnonzero(keys==info[wanted[name]][1])[0]);b=np.unpackbits(masks[at],bitorder='little')[:len(si)]
  selected=np.flatnonzero(b)
  for ci in selected:combined.append((int(si[ci]),0 if side==1 else 1,int(ci),side))
 combined.sort(key=lambda x:(x[0],x[1]))
 # Scheduler selects side-specific precomputed outcomes while sharing one per-asset active_until+3/day limit.
 cday=-1;daily=0;until=-1;trade_rows=[];rej=np.zeros(8,np.int64)
 for index,cfg,ci,side in combined:
  si,st,t=tapes['BUY' if side==1 else 'SELL'];state=int(t[5][ci]);day=int(ticks['ts'][index])//DAY
  if index<=until:rej[0]+=1;continue
  if state==0:rej[1]+=1;continue
  if day!=cday:cday=day;daily=0
  if daily>=3:rej[2]+=1;continue
  if state==1:rej[3]+=1;continue
  if state==2:rej[4]+=1;continue
  if state==3:rej[5]+=1;break
  en,ex,ep,xp,risk,why=t
  rv=(int(xp[ci])-int(ep[ci]))/int(risk[ci]) if side==1 else (int(ep[ci])-int(xp[ci]))/int(risk[ci])
  trade_rows.append((cfg,side,index,int(en[ci]),int(ex[ci]),int(ep[ci]),int(st[ci]),int(xp[ci]),rv,1 if state==4 else 2,day));daily+=1;until=int(ex[ci])
 # Ground exact historical baseline from packaged V2 trades, not summary similarity.
 base_file=HERE/'run_v2/trades_exploratory_dev.csv'
 with base_file.open(newline='') as f:ref=list(csv.DictReader(f))
 if rej[5] or len(trade_rows)!=len(ref):raise RuntimeError('SHARED_PORTFOLIO_BASELINE_NTRADES_MISMATCH_'+str((rej[5],len(trade_rows),len(ref))))
 for i,(got,row) in enumerate(zip(trade_rows,ref)):
  cfg,side,si,ei,xi,ep,sp,xp,rv,why,day=got
  chk=[(cfg,row['config_id']==wanted['BUY'] if cfg==0 else row['config_id']==wanted['SELL']),(side,(side==1 and row['side']=='BUY') or(side==-1 and row['side']=='SELL')),(si,int(row['signal_source_tick'])==si),(ei,int(row['entry_source_tick'])==ei),(xi,int(row['exit_source_tick'])==xi),(ep,int(row['entry_cents'])==ep),(sp,int(row['stop_cents'])==sp),(xp,int(row['exit_cents'])==xp),(why,(why==1 and row['exit_reason']=='STOP') or(why==2 and row['exit_reason']=='PLANNED_FLAT'))]
  for v,ok in chk:
   if not ok:raise RuntimeError('EXACT_BASELINE_TRADE_MISMATCH_ROW_'+str(i)+'_'+str(v))
  if not np.isclose(rv,float(row['R']),rtol=0.,atol=1e-14):raise RuntimeError('R_BASELINE_MISMATCH_'+str(i))
 print('SHARED_TWO_CONFIG_PORTFOLIO_TRADE_BY_TRADE_PASS',len(trade_rows),'all_11_fields',flush=True)
 with (tmp/'PHYSICAL_MASK_ECONOMIC_DIAGNOSTICS.jsonl').open('w') as f:
  for z in catalog:f.write(json.dumps(z,sort_keys=True,separators=(',',':'))+'\n')
 artifacts={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(tmp.iterdir())}
 receipt={'schema':'QROS_SEED0076_DIRECT_6F_ECONOMIC_CACHE_V1','source_data':'XAUUSD_2018_2019_DEV_ECONOMICALLY_EXPOSED','status':'PASS_EXPLORATORY_ONLY','mask_manifest_sha256':sha(MASK/'MANIFEST.json'),'old_work_inspected':False,'input_raw_sha256':man['input_raw_sha256'],'fixed_profile':'OPPOSITE_FRACTAL_STOP_NO_TP_FIXED_19_30_SERVER_FLAT_MAX3_PER_DAY','quotes':'BUY_ASK_BID_EXIT_SELL_BID_ASK_EXIT_STOP_FIRST_SKIP_ZERO_CROSSED','commission':'NOT_INCLUDED_BROKER_COST_UNKNOWN','symbol_holiday_calendar':'NOT_CERTIFIED','standalone_mask_diagnostics_are_not_combined_portfolio_returns':True,'hypotheses_count':3670,'unique_physical_mask_count':len(catalog),'sides':per,'baseline_joint_two_configs_exact_trade_by_trade':{'status':'PASS','trades':len(trade_rows),'compared_columns':11},'artifacts':artifacts,'elapsed_seconds_excludes_raw_sha':round(time.perf_counter()-start,3),'holdout_open':False,'no_selection_performed':True,'limits':['Fixed 19:30 exploratory profile already exposed economically; cannot use its DEV PnL to retrospectively tune the rule.','Individual stand-alone mask diagnostics do not model between-mask competition for one position/3 entries daily.','Real broker commission and historical per-symbol early close are not independently verified; do not label metrics as final net.']}
 writejson(tmp/'RECEIPT.json',receipt)
 os.replace(tmp,path)
 return receipt

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',default=str(HERE/'direct_six_family_economic_v1'));a=p.parse_args();q=run(Path(a.out));print('ECONOMIC_EVENT_CACHE_BATCH_PASS',json.dumps({'sides':q['sides'],'nclasses':q['unique_physical_mask_count'],'baseline':q['baseline_joint_two_configs_exact_trade_by_trade'],'seconds':q['elapsed_seconds_excludes_raw_sha']}),flush=True)
