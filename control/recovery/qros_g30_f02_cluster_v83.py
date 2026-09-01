#!/usr/bin/env python3
"""QROS G30 F02 non-economic clustering using the frozen V49 similarity rule.
DEV 2018-2019 only. Rebuilds signal and selected-trade identities and requires
trade-count + ordered-ledger parity against Gate-A before clustering.
"""
from __future__ import annotations
import argparse,json,math,hashlib,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
import qros_g30_f02_gate_a_v80 as f
TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.]; NS=[1,2,3,4,5,8]
TFS=['H1','M30','M15','M10','M5','M1']; FEATURES=['BID','MID']

def jacc(a,b):
 if not a and not b:return 1.0
 return len(a&b)/len(a|b)
def corr_daily(a,b):
 days=sorted(set(a)|set(b))
 if len(days)<2:return None
 x=np.asarray([a.get(d,0.0) for d in days]);y=np.asarray([b.get(d,0.0) for d in days])
 if np.std(x)==0 or np.std(y)==0:return None
 return float(np.corrcoef(x,y)[0,1])
def parse(sid):
 shard,side,key=sid.split(':',2);tf,feature=shard.split('_');meas,timing,t,fam,n=key.split('|')
 return {'shard':shard,'tf':tf,'feature':feature,'side':side,'measure':meas,'timing':timing,'threshold':float(t),'family':fam,'n':int(n),'key':key}
def adjacent(a,b,grid):
 try:i=grid.index(a);j=grid.index(b)
 except ValueError:return False
 return abs(i-j)==1
def local_neighbor(a,b):
 A=parse(a);B=parse(b)
 if A['side']!=B['side'] or A['tf']!=B['tf'] or A['family']!=B['family'] or A['measure']!=B['measure']:return False
 dif=0
 if A['feature']!=B['feature']:dif+=1
 if A['timing']!=B['timing']:dif+=1
 if A['threshold']!=B['threshold']:
  if not adjacent(A['threshold'],B['threshold'],TH):return False
  dif+=1
 if A['n']!=B['n']:
  if not adjacent(A['n'],B['n'],NS):return False
  dif+=1
 return dif==1
def ledger_sha(ch,et,xt,rr):
 h=hashlib.sha256()
 for q in ch:
  h.update(np.int64(et[q]).tobytes());h.update(np.int64(xt[q]).tobytes());h.update(np.float64(rr[q]).tobytes())
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--results-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 passers={}
 for tf in TFS:
  for feat in FEATURES:
   p=a.results_dir/f'{a.asset}_{tf}_{feat}.json';o=json.load(open(p))
   if o.get('trade_parity','').startswith('PASS') is False:raise SystemExit('GATE_A_PARITY_NOT_PASS '+str(p))
   for r in o['passers']:
    sid=f"{o['shard']}:{r['side']}:{r['id']}"
    if sid in passers:raise SystemExit('DUP_STABLE_ID '+sid)
    passers[sid]={'stable_id':sid,'metrics':r}
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  for shard in sorted(set(x.split(':',1)[0] for x in passers)):
   tfname,feat=shard.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);ks=('bo','bh','bl','bc') if feat=='BID' else ('mo','mh','ml','mc')
   A=c.bars_A(z['mb'],*[z[k] for k in ks],tf);atr,rows=f.rows_A(*A);_,_,uniq=f.canonicalize(rows);bykey={q[0]:q for q in uniq}
   items=[sid for sid in passers if sid.startswith(shard+':')]
   activeB=np.zeros(len(A[0]),bool);activeS=np.zeros(len(A[0]),bool)
   for sid in items:
    P=parse(sid)
    if P['key'] not in bykey:raise SystemExit('CANONICAL_KEY_NOT_FOUND '+sid)
    q=bykey[P['key']]
    if P['side']=='BUY':activeB|=q[1]
    else:activeS|=q[2]
   ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=tf*60000
   outB=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atr,step,*ex,activeB,1) if activeB.any() else None
   outS=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atr,step,*ex,activeS,-1) if activeS.any() else None
   for sid in items:
    P=parse(sid);q=bykey[P['key']];mask=q[1] if P['side']=='BUY' else q[2];out=outB if P['side']=='BUY' else outS
    chosen=c.select_A(mask,out[0],out[1]);m=passers[sid]['metrics']
    if len(chosen)!=int(m['n']):raise SystemExit('TRADE_COUNT_MISMATCH '+sid)
    if ledger_sha(chosen,out[0],out[1],out[5])!=m['ledger_sha256']:raise SystemExit('LEDGER_MISMATCH '+sid)
    sig=set(map(int,(A[0][mask]+step).tolist()));ent=set(map(int,out[0][chosen].tolist()));daily={}
    for t,r in zip(out[0][chosen],out[5][chosen]):
     d=int(t//86400000);daily[d]=daily.get(d,0.0)+float(r)
    passers[sid].update(signal_times=sig,entry_times=ent,daily=daily,selected_n_rebuilt=int(len(chosen)))
 ids=sorted(passers);pair={};adj={x:set() for x in ids};local_pairs=[]
 for i,x in enumerate(ids):
  px=parse(x)
  for y in ids[i+1:]:
   if px['side']!=parse(y)['side']:continue
   sj=jacc(passers[x]['signal_times'],passers[y]['signal_times']);tj=jacc(passers[x]['entry_times'],passers[y]['entry_times']);g=math.sqrt(sj*tj);dc=corr_daily(passers[x]['daily'],passers[y]['daily']);edge=sj>=0.5 and tj>=0.5 and g>=0.7
   pair[(x,y)]={'signal_jaccard':sj,'trade_jaccard':tj,'geometric':g,'daily_r_corr':dc,'edge':edge}
   if edge:adj[x].add(y);adj[y].add(x)
   if local_neighbor(x,y):local_pairs.append((x,y))
 seen=set();comps=[]
 for root in ids:
  if root in seen:continue
  stack=[root];seen.add(root);cc=[]
  while stack:
   x=stack.pop();cc.append(x)
   for y in adj[x]:
    if y not in seen:seen.add(y);stack.append(y)
  comps.append(sorted(cc))
 comps.sort(key=lambda q:q[0]);clusters=[];prefix='F02NQXC' if a.asset=='NQX' else 'F02XAUC'
 for ci,cc in enumerate(comps,1):
  local=[(x,y) for x,y in local_pairs if x in cc and y in cc]
  if len(cc)==1:rep=cc[0];means={rep:1.0}
  else:
   means={}
   for x in cc:
    vals=[]
    for y in cc:
     if x==y:continue
     k=(x,y) if x<y else (y,x);vals.append(pair[k]['geometric'])
    means[x]=float(np.mean(vals))
   best=max(means.values());rep=sorted([x for x,v in means.items() if abs(v-best)<=1e-15])[0]
  vals=[];corrs=[]
  for ii,x in enumerate(cc):
   for y in cc[ii+1:]:
    k=(x,y);vals.append(pair[k]['geometric']);
    if pair[k]['daily_r_corr'] is not None:corrs.append(pair[k]['daily_r_corr'])
  typ='PLATEAU_SUPPORTED' if len(cc)>=2 and local else ('ISOLATED_SINGLETON' if len(cc)==1 else 'MULTI_MEMBER_NONLOCAL')
  clusters.append({'cluster_id':f'{prefix}{ci:03d}','direction':parse(rep)['side'],'size':len(cc),'type':typ,'local_neighbor_pairs':len(local),'representative':rep,'representative_mean_geometric_similarity':means[rep],'members':cc,'mean_pair_geometric_similarity':float(np.mean(vals)) if vals else 1.0,'min_pair_geometric_similarity':float(np.min(vals)) if vals else 1.0,'mean_daily_r_correlation_diagnostic':float(np.mean(corrs)) if corrs else None})
 h=hashlib.sha256()
 for cl in clusters:h.update((cl['cluster_id']+'|'+cl['representative']+'|'+';'.join(cl['members'])+'\n').encode())
 obj={'schema':'QROS_G30_F02_NON_ECONOMIC_CLUSTERING_V83_v1','status':'PASS','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F02_SHOCK_MEASURE_ALTERNATIVES','asset':a.asset,'scope':'DEV_2018_2019_GATE_A_PASSERS_ONLY_NO_2020_PLUS_PNL','rule_ref':'control/QROS_G30_NQX_GATE_A_CLUSTERING_PREREG_V49_v1.json','survivor_count':len(ids),'cluster_count':len(clusters),'plateau_supported_clusters':sum(x['type']=='PLATEAU_SUPPORTED' for x in clusters),'isolated_singletons':sum(x['type']=='ISOLATED_SINGLETON' for x in clusters),'multi_member_nonlocal':sum(x['type']=='MULTI_MEMBER_NONLOCAL' for x in clusters),'graph_edges':sum(1 for v in pair.values() if v['edge']),'local_parameter_neighbor_pairs':len(local_pairs),'representatives':[x['representative'] for x in clusters],'clusters':clusters,'cluster_assignment_root_sha256':h.hexdigest(),'future_strategy_pnl_2020_plus_read':False,'representative_selection_used_economics':False,'ledger_parity_all_passers':True,'decision':'FREEZE_ONE_REPRESENTATIVE_PER_CLUSTER_ALL_ALIASES_PRESERVED'}
 a.out.write_text(json.dumps(obj,separators=(',',':')))
 print(json.dumps({k:obj[k] for k in ['asset','survivor_count','cluster_count','plateau_supported_clusters','isolated_singletons','multi_member_nonlocal','graph_edges','local_parameter_neighbor_pairs','cluster_assignment_root_sha256']},sort_keys=True))
 print('bytes',a.out.stat().st_size,'sha256',hashlib.sha256(a.out.read_bytes()).hexdigest())
if __name__=='__main__':main()
