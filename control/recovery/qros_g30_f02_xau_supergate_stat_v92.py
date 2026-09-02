#!/usr/bin/env python3
"""QROS G30 F02 XAU statistical Supergate V92.
Consumes only certified V90 baseline ledgers for the six V91 WF survivors.
No rule search, no retuning, no MT5, no raw-tick stress in this stage.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, math
from pathlib import Path
import numpy as np

ADV=("F02XAUC023","F02XAUC024","F02XAUC027","F02XAUC033","F02XAUC038","F02XAUC043")
ROOT="e1babe1842b91c0e8c4c397851ffd96ef8c268d552c37997f744cbdf47fdc6cd"
SEED=int(ROOT[:16],16)
EXPECTED_SEGMENTS=("A_2018_2021","B_2022_2024","C_2025_2026")
EXPECTED_SHARDS=("H1_MID","M10_MID","M15_BID","M15_MID","M30_BID","M30_MID")
YEAR_BOUNDS={
 2018:(1514764800000,1546300800000),2019:(1546300800000,1577836800000),
 2020:(1577836800000,1609459200000),2021:(1609459200000,1640995200000),
 2022:(1640995200000,1672531200000),2023:(1672531200000,1704067200000),
 2024:(1704067200000,1735689600000),2025:(1735689600000,1767225600000),
 2026:(1767225600000,1798761600000),
}
FOLDS=(
 ('2022H1',1640995200000,1656633600000),('2022H2',1656633600000,1672531200000),
 ('2023H1',1672531200000,1688169600000),('2023H2',1688169600000,1704067200000),
 ('2024H1',1704067200000,1719792000000),('2024H2',1719792000000,1735689600000),
 ('2025H1',1735689600000,1751328000000),('2025H2',1751328000000,1767225600000),
)

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''): h.update(b)
 return h.hexdigest()

def pf(x):
 x=np.asarray(x,float); gp=float(x[x>0].sum()); gl=float(-x[x<0].sum())
 if gl==0: return float('inf') if gp>0 else 0.0
 return gp/gl

def maxdd(x):
 x=np.asarray(x,float)
 if len(x)==0:return 0.0
 eq=np.r_[0.0,np.cumsum(x)]; peak=np.maximum.accumulate(eq)
 return float(np.max(peak-eq))

def safe(v):
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.floating,)):v=float(v)
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,np.ndarray):return [safe(x) for x in v.tolist()]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [safe(x) for x in v]
 return v

def pctl(a,q):return float(np.quantile(np.asarray(a,float),q))

def sharpe_sortino(x,ann=1.0):
 x=np.asarray(x,float)
 if len(x)<2:return (float('nan'),float('nan'))
 sd=float(np.std(x,ddof=1)); sh=float(np.mean(x)/sd*math.sqrt(ann)) if sd>0 else float('inf') if np.mean(x)>0 else 0.0
 dn=x[x<0]
 if len(dn)<2: so=float('inf') if np.mean(x)>0 else 0.0
 else:
  dsd=float(np.std(dn,ddof=1)); so=float(np.mean(x)/dsd*math.sqrt(ann)) if dsd>0 else float('inf') if np.mean(x)>0 else 0.0
 return sh,so

def group_sum(ts,r,period_ms):
 if len(ts)==0:return np.empty(0,float)
 key=ts//period_ms
 cuts=np.r_[0,np.flatnonzero(key[1:]!=key[:-1])+1]
 return np.add.reduceat(r,cuts)

def month_key_from_epoch_ms(ts):
 d=ts.astype('datetime64[ms]').astype('datetime64[M]').astype(np.int64)
 return d

def group_month(ts,r):
 if len(ts)==0:return np.empty(0,float)
 k=month_key_from_epoch_ms(ts); cuts=np.r_[0,np.flatnonzero(k[1:]!=k[:-1])+1]
 return np.add.reduceat(r,cuts)

def streaks_underwater(ts,r):
 maxw=maxl=w=l=0
 eq=0.0;peak=0.0;uw_start_i=None;uw_start_t=None;max_uw_tr=0;max_uw_ms=0
 for i,(t,z) in enumerate(zip(ts,r)):
  if z>0:w+=1;l=0
  elif z<0:l+=1;w=0
  else:w=l=0
  maxw=max(maxw,w);maxl=max(maxl,l)
  eq+=float(z)
  if eq>=peak-1e-15:
   peak=max(peak,eq)
   if uw_start_i is not None:
    max_uw_tr=max(max_uw_tr,i-uw_start_i+1);max_uw_ms=max(max_uw_ms,int(t)-int(uw_start_t));uw_start_i=uw_start_t=None
  elif uw_start_i is None:
   uw_start_i=i;uw_start_t=int(t)
 if uw_start_i is not None and len(ts):
  max_uw_tr=max(max_uw_tr,len(ts)-uw_start_i);max_uw_ms=max(max_uw_ms,int(ts[-1])-int(uw_start_t))
 return {'max_win_streak':maxw,'max_loss_streak':maxl,'max_underwater_trades':max_uw_tr,'max_underwater_days':max_uw_ms/86400000.0}

def block_bootstrap(r,rng,runs=20000,block=5,batch=500):
 r=np.asarray(r,float);n=len(r); nets=[];pfs=[];dds=[];nb=(n+block-1)//block;offs=np.arange(block)
 for s in range(0,runs,batch):
  m=min(batch,runs-s);starts=rng.integers(0,n,size=(m,nb),endpoint=False);idx=(starts[...,None]+offs)%n;idx=idx.reshape(m,-1)[:,:n];x=r[idx]
  nets.append(x.sum(1));gp=np.where(x>0,x,0).sum(1);gl=-np.where(x<0,x,0).sum(1);pfs.append(np.divide(gp,gl,out=np.full(m,np.inf),where=gl>0))
  c=np.cumsum(x,axis=1);c=np.concatenate([np.zeros((m,1)),c],axis=1);pk=np.maximum.accumulate(c,axis=1);dds.append(np.max(pk-c,axis=1))
 return np.concatenate(nets),np.concatenate(pfs),np.concatenate(dds)

def failure_mc(r,rng,miss,runs=10000,batch=1000):
 r=np.asarray(r,float);n=len(r);out=[]
 for s in range(0,runs,batch):
  m=min(batch,runs-s);keep=rng.random((m,n))>=miss;out.append((keep*r).sum(1))
 return np.concatenate(out)

def yearly_bootstrap(year_nets,rng,runs=10000):
 y=np.asarray(year_nets,float);idx=rng.integers(0,len(y),size=(runs,len(y)));return y[idx].sum(1)

def load_ledgers(base:Path,input_path:Path):
 I=json.load(input_path.open());meta={q['cluster_id']:q for q in I['candidates'] if q['cluster_id'] in ADV}
 if set(meta)!=set(ADV):raise SystemExit('ADVANCED_IDS_NOT_FOUND_EXACTLY')
 rows={x:[] for x in ADV};arts=[]
 for seg in EXPECTED_SEGMENTS:
  for shard in EXPECTED_SHARDS:
   p=base/f'{seg}_{shard}.json';o=json.load(p.open());arts.append({'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size})
   if o.get('status')!='PASS' or o.get('signal_parity')!='PASS_EXACT' or o.get('trade_parity')!='PASS_EXACT':raise SystemExit('BASELINE_PARITY_NOT_PASS '+p.name)
   for rec in o['records']:
    cid=rec['cluster_id']
    if cid not in rows:continue
    b=rec['baseline'];rows[cid].append((np.asarray(b['entry_t'],np.int64),np.asarray(b['exit_t'],np.int64),np.asarray(b['r_c'],float),np.asarray(b['r_k'],float),np.asarray(b['r_s'],float)))
 led={}
 for cid in ADV:
  if len(rows[cid])!=3:raise SystemExit(f'{cid}_SEGMENTS_{len(rows[cid])}')
  vals=[np.concatenate([x[j] for x in rows[cid]]) for j in range(5)];order=np.argsort(vals[0],kind='stable');vals=[x[order] for x in vals]
  if len(vals[0])>1 and np.any(vals[0][1:]<=vals[0][:-1]):raise SystemExit('NON_STRICT_ENTRY '+cid)
  led[cid]=vals
 return meta,led,arts

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--baseline-dir',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 meta,led,arts=load_ledgers(a.baseline_dir,a.input);records=[]
 for ci,cid in enumerate(ADV):
  q=meta[cid];et,xt,rc,rk,rs=led[cid];rng=np.random.default_rng(np.random.SeedSequence([SEED,ci]))
  annual={};yn_s=[];positive_full=0
  for y,(lo,hi) in YEAR_BOUNDS.items():
   m=(et>=lo)&(et<hi);nc=float(rc[m].sum());ns=float(rs[m].sum());annual[str(y)]={'n':int(m.sum()),'net_c':nc,'net_k':float(rk[m].sum()),'net_s':ns,'pf_c':pf(rc[m]),'pf_s':pf(rs[m])}
   if y<=2025:
    yn_s.append(ns);positive_full+=int(nc>0)
  fold_s=[]
  for name,lo,hi in FOLDS:
   m=(et>=lo)&(et<hi);fold_s.append((name,float(rs[m].sum()),int(m.sum())))
  cpcv=[]
  for i,j in itertools.combinations(range(8),2):
   net=fold_s[i][1]+fold_s[j][1];cpcv.append({'folds':[fold_s[i][0],fold_s[j][0]],'net_s':net,'positive':bool(net>0)})
  cpcv_pass=all(x['positive'] for x in cpcv)
  mc_net,mc_pf,mc_dd=block_bootstrap(rs,rng,20000,5)
  yb=yearly_bootstrap(yn_s,rng,10000)
  f10=failure_mc(rs,rng,.10,10000);f20=failure_mc(rs,rng,.20,10000)
  n25=max(1,int(math.ceil(.025*len(rs))));n5=max(1,int(math.ceil(.05*len(rs))));ordbest=np.argsort(rs)[::-1]
  rem25=np.delete(rs,ordbest[:n25]);rem5=np.delete(rs,ordbest[:n5])
  loyo=[]
  for y,(lo,hi) in YEAR_BOUNDS.items():
   if y>2025:continue
   m=~((et>=lo)&(et<hi));loyo.append({'removed_year':y,'n':int(m.sum()),'net_s':float(rs[m].sum()),'pf_s':pf(rs[m]),'positive':bool(rs[m].sum()>0)})
  daily=group_sum(et,rc,86400000);monthly=group_month(et,rc);sh_t,so_t=sharpe_sortino(rc,1);sh_d,so_d=sharpe_sortino(daily,252);sh_m,so_m=sharpe_sortino(monthly,12)
  var=float(np.quantile(daily,.05)) if len(daily) else float('nan');tail=daily[daily<=var] if len(daily) else np.empty(0);cvar=float(tail.mean()) if len(tail) else float('nan')
  dd=maxdd(rc);eq=np.r_[0,np.cumsum(rc)];pk=np.maximum.accumulate(eq);ulcer=float(np.sqrt(np.mean((pk-eq)**2)))
  stress={'neighbor_plateau':q['type']=='PLATEAU_SUPPORTED','cost_stress':bool(rs.sum()>0 and pf(rs)>1.0),'annual_consistency':positive_full>=7,'cpcv':cpcv_pass,'mc_block5':pctl(mc_net,.05)>0,'bootstrap_years':pctl(yb,.05)>0,'failure10':pctl(f10,.05)>0,'failure20':pctl(f20,.05)>0,'best2p5_removed':float(rem25.sum())>0,'best5_removed':float(rem5.sum())>0,'loyo':all(x['positive'] for x in loyo)}
  hard_pass=all(stress.values())
  records.append({'cluster_id':cid,'representative':q['representative'],'direction':q['direction'],'cluster_type':q['type'],'baseline':{'n':len(rc),'net_c':float(rc.sum()),'net_k':float(rk.sum()),'net_s':float(rs.sum()),'pf_c':pf(rc),'pf_k':pf(rk),'pf_s':pf(rs),'expectancy_c':float(rc.mean()),'win_rate':float(np.mean(rc>0)),'max_dd_c_R':dd,'recovery_c':float(rc.sum()/dd) if dd>0 else float('inf'),'ulcer_R':ulcer,'trade_sharpe':sh_t,'trade_sortino':so_t,'daily_sharpe_ann':sh_d,'daily_sortino_ann':so_d,'monthly_sharpe_ann':sh_m,'monthly_sortino_ann':so_m,'VaR95_daily_R':var,'CVaR95_daily_R':cvar,**streaks_underwater(et,rc)},'annual':annual,'positive_full_years_central':positive_full,'cpcv':{'paths':28,'positive_paths':sum(x['positive'] for x in cpcv),'min_net_s':min(x['net_s'] for x in cpcv),'paths_detail':cpcv},'monte_carlo_block5_20000':{'net_p05':pctl(mc_net,.05),'pf_p05':pctl(mc_pf,.05),'dd_p95':pctl(mc_dd,.95),'prob_net_negative':float(np.mean(mc_net<=0))},'bootstrap_years_10000':{'net_p05':pctl(yb,.05),'prob_net_negative':float(np.mean(yb<=0))},'random_failure_10pct_10000':{'net_p05':pctl(f10,.05),'prob_net_negative':float(np.mean(f10<=0))},'random_failure_20pct_10000':{'net_p05':pctl(f20,.05),'prob_net_negative':float(np.mean(f20<=0))},'best_trade_removal':{'remove_2p5pct_n':n25,'net_s':float(rem25.sum()),'pf_s':pf(rem25),'remove_5pct_n':n5,'net_s_5pct':float(rem5.sum()),'pf_s_5pct':pf(rem5)},'leave_one_year_out':loyo,'hard_gate_components':stress,'hard_gate_pass':hard_pass})
  print(cid,'PASS' if hard_pass else 'FAIL',stress,flush=True)
 pair=[]
 for i in range(len(ADV)):
  for j in range(i+1,len(ADV)):
   ai,aj=ADV[i],ADV[j];ti,_,ri,_,_=led[ai];tj,_,rj,_,_=led[aj]
   exact=len(set(map(int,ti)).intersection(map(int,tj)));jac=exact/(len(ti)+len(tj)-exact) if len(ti)+len(tj)-exact else 1.0
   di={int(t//86400000):0.0 for t in ti};dj={int(t//86400000):0.0 for t in tj}
   for t,z in zip(ti,ri):di[int(t//86400000)]=di.get(int(t//86400000),0.0)+float(z)
   for t,z in zip(tj,rj):dj[int(t//86400000)]=dj.get(int(t//86400000),0.0)+float(z)
   keys=sorted(set(di)|set(dj));xi=np.array([di.get(k,0.0) for k in keys]);xj=np.array([dj.get(k,0.0) for k in keys]);corr=float(np.corrcoef(xi,xj)[0,1]) if np.std(xi)>0 and np.std(xj)>0 else float('nan')
   pair.append({'a':ai,'b':aj,'exact_entry_overlap':exact,'entry_jaccard':jac,'daily_R_corr_raw_epoch_day':corr})
 passed=[r['cluster_id'] for r in records if r['hard_gate_pass']];failed=[r['cluster_id'] for r in records if not r['hard_gate_pass']]
 obj={'schema':'QROS_G30_F02_XAU_SUPERGATE_STAT_V92_RESULT_v1','status':'PASS_EVALUATED','gate_ref':'control/QROS_G30_F02_XAU_SUPERGATE_STAT_GATE_V92_v1.json','candidate_root_sha256':ROOT,'seed_uint64':SEED,'candidate_count':6,'passed_count':len(passed),'failed_count':len(failed),'passed_cluster_ids':passed,'failed_cluster_ids':failed,'baseline_artifacts':arts,'records':records,'pairwise_redundancy_diagnostic':pair,'decision':'ONLY_V92_PASSERS_ADVANCE_TO_RAW_TICK_STRESS_STAGE','guards':{'retuning':False,'economic_ranking':False,'mt5':False,'branch_exhausted':False}}
 a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'status':obj['status'],'passed':passed,'failed':failed},sort_keys=True));print('bytes',a.out.stat().st_size,'sha256',sha(a.out))
if __name__=='__main__':main()
