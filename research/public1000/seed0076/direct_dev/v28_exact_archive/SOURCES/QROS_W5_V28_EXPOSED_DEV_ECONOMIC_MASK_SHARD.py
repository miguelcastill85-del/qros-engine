#!/usr/bin/env python3
"""V28 exploratory 2018-19 economic R and costs-in-spread, per frozen 10-family physical mask.
Real-data DEV is exposed for whole genealogy. No holdout, no GA2, no certified broker cost.
One channel per invocation, route-complete independent SHA checkpoints; no retests on closed bytes.
"""
from __future__ import annotations
import numpy as np,json,hashlib,os,sys,time,argparse
from pathlib import Path
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from qros_w5_v28_frozen_exploratory_economic_kernel import schedule_pure
PIN='18c19e3278843f5c38f17301549ee73b8c45215999ff861ea52fd70673398e26';BARS_SHA='8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13'
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);D18=int(np.datetime64('2018-01-01','D').astype('int64'));D19=int(np.datetime64('2019-01-01','D').astype('int64'));D20=int(np.datetime64('2020-01-01','D').astype('int64'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(8<<20),b''):h.update(x)
 return h.hexdigest()
def atomic_json(p,x):
 t=p.with_suffix(p.suffix+'.partial');t.write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def atomic_jsonl(p,rows):
 t=p.with_suffix(p.suffix+'.partial')
 with t.open('w') as f:
  for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
  f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def verify_inputs():
 assert sha(R/'V28_EXPLORATORY_ECONOMIC_EXECUTION_FROZEN_BEFORE_PNL.json')==PIN
 assert json.load(open(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'))['status']=='PASS'
 assert json.load(open(R/'V28_INDEPENDENT_EXANTE_STRATIFIED_REAL_TICK_TRADE_CANARY_RECEIPT.json'))['status']=='PASS'
 assert sha(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy')==BARS_SHA
 runner=R/'V28_EXACT_ECONOMIC_RUNNER_CODE_PRE_PNL_FREEZE.json';f=json.load(open(runner));assert f['worker_sha256']==sha(Path(__file__)) and f['preexisting_contract_sha256']==PIN
 return f
def load_trajectory(ch,route,candidate_root):
 p=R/f'V28_ECON_TAPE_CH{ch}_{route}/FULL_TRAJECTORY_MANIFEST.json';m=json.load(open(p));assert m['source_candidate_root']==candidate_root and m['status']=='PASS' and m['channel']==ch
 names=('entry_idx','exit_idx','entry_price','exit_price','risk','reason','stop','source_idx')
 z={n:[] for n in names}
 for s in m['verified_shards']:
  rp=p.parent/s['path'];assert sha(rp)==s['sha256'];t=json.load(open(rp));q=p.parent/f"part{t['part']:03d}_TRAJECTORY.npz";assert sha(q)==t['sha256']
  with np.load(q,allow_pickle=False) as d:
   for n in names:z[n].append(d[n])
 v={n:np.concatenate(z[n]) for n in names};assert len(v['source_idx'])==m['source_candidates'];return v

def dd(rs):
 if not len(rs):return 0.
 cum=np.cumsum(rs);return float(np.max(np.maximum.accumulate(np.r_[0.,cum])[1:]-cum))
def pf(rs):
 pos=float(rs[rs>0].sum());neg=float(-rs[rs<0].sum());return None if neg<=0 else pos/neg
def eval_mask(m,phys,si,trace,ts,sign):
 ids=np.flatnonzero(np.unpackbits(m,bitorder='little')[:len(si)])
 assert len(ids)==phys['accepted_signal_count'],('BIT_COUNT_MISMATCH',phys['physical_mask_id'])
 if len(ids)==0:
  return {'status':'NO_SIGNALS','signal_count':0,'trades':0,'rejections':[0]*8,'gross_spread_only_R':0.,'PF_spread_only':None,'DD_R':0.,'hypothetical_roundtrip_cost_2pts_R':0.,'hypothetical_roundtrip_cost_5pts_R':0.,'years':{'2018':{'trades':0,'R':0.},'2019':{'trades':0,'R':0.}}}
 a=schedule_pure(ts,si,ids,trace['entry_idx'],trace['exit_idx'],trace['entry_price'],trace['exit_price'],trace['risk'],trace['reason'],trace['stop'],sign,3,True)
 n,rsum,pos,neg,maxdd,rej,trade=a
 if rej[5] or (n and (np.any(trade[:,4]<trade[:,3]) or np.any(trade[:,3]<trade[:,2]) or np.any((trade[:,10]<D18)|(trade[:,10]>=D20)) or np.any(ts[trade[:,4].astype(np.int64)]//86400000!=trade[:,10]))):
  return {'status':'FAIL_CLOSED_INVALID_OR_UNRESOLVED_TRADE','signal_count':len(ids),'trades':int(n),'rejections':rej.tolist(),'economic_metrics':None}
 rv=trade[:,8];risk=trade[:,6] # tr col6 is stop, not risk! Correct risk inferred from entry-vs-stop
 risk=np.abs(trade[:,5]-trade[:,6]);assert (risk>0).all();cost2=rv-2./risk;cost5=rv-5./risk
 years={}
 for year,low,high in [('2018',D18,D19),('2019',D19,D20)]:
  v=(trade[:,10]>=low)&(trade[:,10]<high)
  years[year]={'trades':int(v.sum()),'spread_only_R':float(rv[v].sum()),'hypothetical_extra_2pts_R':float(cost2[v].sum()),'hypothetical_extra_5pts_R':float(cost5[v].sum())}
 return {'status':'EXPLORATORY_DEV_ONLY_BROKER_COST_UNCERTIFIED','signal_count':len(ids),'trades':int(n),'stops':int(np.sum(trade[:,9]==1)),'flat_exits':int(np.sum(trade[:,9]==2)),'rejections':rej.tolist(),'gross_spread_only_R':float(rsum),'PF_spread_only':pf(rv),'DD_R':float(maxdd),'hypothetical_roundtrip_cost_2pts_R':float(cost2.sum()),'hypothetical_roundtrip_cost_5pts_R':float(cost5.sum()),'hypothetical_PF_2pts':pf(cost2),'hypothetical_PF_5pts':pf(cost5),'years':years}
def execute(ch,max_routes=0,verify_only=False):
 freeze=verify_inputs();side='BUY' if ch<4 else 'SELL';sign=1 if ch<4 else -1;src=R/f'V27_FULL10_PRE_ECON_CH{ch}';m=json.load(open(src/'ALL_ROUTES_MANIFEST.json'));assert m['channel']==ch and m['side']==side and len(m['routes'])==(31 if ch in (0,4) else 7)
 for q in m['artifacts']:assert sha(src/q['name'])==q['sha256']
 if verify_only:print(json.dumps({'status':'PRE_RUN_COMPLETE_INPUT_BYTE_VERIFIED','channel':ch,'packages':m['packages'],'routes':len(m['routes']),'execution_code_SHA256':sha(Path(__file__))}));return
 out=R/f'V28_EXPOSED_DEV_SPREAD_ONLY_CH{ch}';out.mkdir(exist_ok=True)
 t0=time.monotonic();ticks=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r')
 last_root=None;trace=None;dup={};results=[];semantic_ids=set();done=0;processed=0
 for route in m['routes']:
  key=route['route'];rawkey=key.split('_batch')[0];pidroot=route['candidate_root']
  sem=src/f'{key}_SEMANTIC.jsonl';phys=src/f'{key}_PHYSICAL.jsonl';mp=src/f'{key}_PHYSICAL_MASKS.npz'
  rfile=out/f'{key}_ECON_RECEIPT.json';physical_out=out/f'{key}_ECON_PHYSICAL.jsonl';semantic_out=out/f'{key}_ECON_SEMANTIC.jsonl';pmap=[json.loads(line) for line in phys.read_text().splitlines()];smap=[json.loads(line) for line in sem.read_text().splitlines()];assert len(pmap)==route['physical_masks'] and len(smap)==route['packages']
  if rfile.exists():
   rec=json.load(open(rfile));assert rec['route']==key and rec['candidate_root_sha256']==pidroot and rec['semantic_packages']==len(smap)
   for a in rec['artifacts']:assert sha(out/a['name'])==a['sha256'] and (out/a['name']).stat().st_size==a['bytes']
   for line in physical_out.read_text().splitlines():
    row=json.loads(line);k=row['physical_mask_id'];assert k not in dup or dup[k]==row['metrics'];dup[k]=row['metrics']
   results.append({'receipt_sha256':sha(rfile),'route':key,'semantic_packages':len(smap),'physical_processed_or_reused':len(pmap)});semantic_ids.update(x['config_id'] for x in smap);done+=1;print(json.dumps({'status':'PASS_SHA_RESUME_PREVIOUS_METRICS','channel':ch,'route':key,'configs':len(smap)}),flush=True);continue
  assert not physical_out.exists() and not semantic_out.exists(),('UNRECONCILED_PARTIAL_ECON_SHARD',key)
  if trace is None or rawkey!=last_root:
   trace=load_trajectory(ch,rawkey,pidroot);last_root=rawkey
  assert pidroot==route['candidate_root'] and len(trace['source_idx'])==route['candidates']
  with np.load(mp,allow_pickle=False) as z:
   arr=z['masks'];ids=z['mask_ids'];assert str(z['candidate_root_sha256'])==pidroot and len(ids)==len(pmap)
   rows=[]
   for ix,rp in enumerate(pmap):
    mid=rp['physical_mask_id'];assert mid==ids[ix]
    if mid in dup:metric=dup[mid];status='REUSED_IDENTICAL_PHYSICAL_MASK'
    else:
     metric=eval_mask(arr[ix],rp,trace['source_idx'],trace,ticks['ts'],sign);dup[mid]=metric;status='NEW_EXPLORATORY_ECONOMIC_MASK';processed+=1
     if metric['status'].startswith('FAIL_CLOSED'):raise RuntimeError(('FAIL_CLOSED_UNRESOLVED_MASK',ch,key,mid,metric))
    rows.append({'physical_mask_id':mid,'channel':ch,'side':side,'route':key,'mask_index':ix,'candidate_root_sha256':pidroot,'status':status,'metrics':metric})
  ss=[{'config_index':x['config_index'],'config_id':x['config_id'],'physical_mask_id':x['physical_mask_id'],'side':side,'channel':ch,'route':key,'economic_mask_receipt_expected':f'{key}_ECON_RECEIPT.json'} for x in smap]
  atomic_jsonl(physical_out,rows);atomic_jsonl(semantic_out,ss)
  rec={'schema':'QROS_W5_V28_ONE_SHA_VERIFIED_ECONOMIC_MASK_SHARD','status':'PASS_EXPLORATORY_DEV_COSTS_UNCERTIFIED','side':side,'channel':ch,'route':key,'semantic_packages':len(ss),'physical_mask_occurrences':len(rows),'new_physical_mask_metrics_computed':sum(z['status']=='NEW_EXPLORATORY_ECONOMIC_MASK' for z in rows),'candidate_root_sha256':pidroot,'mask_source_SHA256':sha(mp),'trajectory_manifest_SHA256':sha(R/f'V28_ECON_TAPE_CH{ch}_{rawkey}/FULL_TRAJECTORY_MANIFEST.json'),'execution_contract_SHA256':PIN,'runner_release_sha256':sha(R/'V28_EXACT_ECONOMIC_RUNNER_CODE_PRE_PNL_FREEZE.json'),'artifacts':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in (physical_out,semantic_out)],'holdout_open':False,'GA2_open':False,'Gate_A_approved':False,'broker_cost_certified':False}
  atomic_json(rfile,rec);results.append({'receipt_sha256':sha(rfile),'route':key,'semantic_packages':len(ss),'physical_processed_or_reused':len(rows)});semantic_ids.update(x['config_id'] for x in smap)
  done+=1;atomic_json(out/'PROGRESS.json',{'side':side,'channel':ch,'sequence':done,'routes_verified':results,'semantic_processed':len(semantic_ids),'physical_evaluated_unique':len(dup),'seconds':round(time.monotonic()-t0,2)})
  print(json.dumps({'status':'PASS_EXPLORATORY_ONE_ECONOMIC_MASK_SHARD','channel':ch,'route':key,'configs':len(ss),'physical':len(rows),'new_unique':rec['new_physical_mask_metrics_computed'],'seconds':round(time.monotonic()-t0,2),'receipt_sha256':sha(rfile)}),flush=True)
  if max_routes and done>=max_routes:return
 assert len(semantic_ids)==m['packages'] and len(results)==len(m['routes'])
 outman={'schema':'QROS_W5_V28_ONE_COMPLETE_ECONOMIC_EXPLORATORY_CHANNEL','status':'PASS_EXPLORATORY_DEV_SPREAD_INCLUDED_BROKER_COST_UNCERTIFIED','channel':ch,'side':side,'semantic_configs':len(semantic_ids),'unique_physical_masks_this_channel':len(dup),'route_receipts':results,'source_full10_manifest_SHA256':sha(src/'ALL_ROUTES_MANIFEST.json'),'execution_contract_SHA256':PIN,'holdout_open':False,'GA2_open':False,'Gate_A_approved':False,'broker_cost_certified':False};atomic_json(out/'ALL_ECONOMIC_ROUTES_MANIFEST.json',outman)
 print(json.dumps({'status':'PASS_EXPLORATORY_CHANNEL','channel':ch,'configs':len(semantic_ids),'physical':len(dup),'routes':len(results),'sha256':sha(out/'ALL_ECONOMIC_ROUTES_MANIFEST.json'),'elapsed':round(time.monotonic()-t0,2)}),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--channel',type=int,choices=range(8),required=True);ap.add_argument('--max-routes',type=int,default=0);ap.add_argument('--verify-only',action='store_true');a=ap.parse_args();execute(a.channel,a.max_routes,a.verify_only)
