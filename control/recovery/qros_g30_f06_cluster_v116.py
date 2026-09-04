#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib,math,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f06_transactional_v115 as r
import qros_g30_f06_signal_primary_v115 as sa

TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.];NS=[1,2,3,4,5,8]

def jacc(a,b):
 if not a and not b:return 1.0
 return len(a&b)/len(a|b)
def parse(sid):
 shard,side,key=sid.split(':',2);tf,feature=shard.split('_');wick,timing,t,fam,n=key.split('|')
 return {'shard':shard,'tf':tf,'feature':feature,'side':side,'wick':wick,'timing':timing,'threshold':float(t),'family':fam,'n':int(n),'key':key}
def adjacent(a,b,g):
 try:return abs(g.index(a)-g.index(b))==1
 except ValueError:return False
def local_neighbor(a,b):
 A=parse(a);B=parse(b)
 if A['side']!=B['side'] or A['tf']!=B['tf'] or A['family']!=B['family']:return False
 dif=0
 if A['feature']!=B['feature']:dif+=1
 if A['timing']!=B['timing']:dif+=1
 if A['threshold']!=B['threshold']:
  if not adjacent(A['threshold'],B['threshold'],TH):return False
  dif+=1
 if A['n']!=B['n']:
  if not adjacent(A['n'],B['n'],NS):return False
  dif+=1
 # wick is intentionally not an added V49 dimension and does not disqualify a V49-local pair
 return dif==1
def corr_daily(a,b):
 days=sorted(set(a)|set(b))
 if len(days)<2:return None
 x=np.asarray([a.get(d,0.) for d in days]);y=np.asarray([b.get(d,0.) for d in days])
 if np.std(x)==0 or np.std(y)==0:return None
 return float(np.corrcoef(x,y)[0,1])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 results=a.root/'results';work=a.root/'work';passers={}
 for p in sorted(results.glob(f'{a.asset}_*.json')):
  o=json.load(open(p)); shard=o['shard']
  for q in o['passers']:
   sid=f"{shard}:{q['side']}:{q['id']}"
   if sid in passers:raise SystemExit('DUP '+sid)
   passers[sid]={'stable_id':sid,'metrics':q,'aliases':q.get('aliases',[])}
 for shard in sorted(set(x.split(':',1)[0] for x in passers)):
  tfname,fs=shard.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);W=work/f'{a.asset}_{tfname}_{fs}';meta=json.load(open(W/'manifest.json'))
  z,A,B,pa,pb=r.build_bars_prep(Path(meta['cache']),tf,fs)
  try:
   OA_B=tuple(r.load_arr(W,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(r.load_arr(W,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'))
   step=tf*60000
   for sid in [x for x in passers if x.startswith(shard+':')]:
    m=passers[sid]['metrics'];d=m['signal_sha256'];spec=tuple(meta['by'][d]['spec']);b,s=sa.mask(pa,*A[1:],*spec);mask=b if m['side']=='BUY' else s;OA=OA_B if m['side']=='BUY' else OA_S
    ids=np.flatnonzero(mask).astype(np.int64);ch=r.select_a(ids,OA[0],OA[1])
    if len(ch)!=int(m['n']):raise SystemExit('TRADE_COUNT_MISMATCH '+sid)
    if r.ledger_sha(ch,OA[0],OA[1],OA[5])!=m['ledger_sha256']:raise SystemExit('LEDGER_MISMATCH '+sid)
    sig=set(map(int,(A[0][mask]+step).tolist()));ent=set(map(int,OA[0][ch].tolist()));daily={}
    for t,x in zip(OA[0][ch],OA[5][ch]):
     day=int(t//86400000);daily[day]=daily.get(day,0.)+float(x)
    passers[sid].update(signal_times=sig,entry_times=ent,daily=daily)
  finally:z.close()
 ids=sorted(passers);adj={x:set() for x in ids};pair={};local=[]
 for i,x in enumerate(ids):
  px=parse(x)
  for y in ids[i+1:]:
   if px['side']!=parse(y)['side']:continue
   sj=jacc(passers[x]['signal_times'],passers[y]['signal_times']);tj=jacc(passers[x]['entry_times'],passers[y]['entry_times']);g=math.sqrt(sj*tj);edge=sj>=.5 and tj>=.5 and g>=.7
   pair[(x,y)]=(sj,tj,g)
   if edge:adj[x].add(y);adj[y].add(x)
   if local_neighbor(x,y):local.append((x,y))
 seen=set();comps=[]
 for root in ids:
  if root in seen:continue
  stack=[root];seen.add(root);cc=[]
  while stack:
   x=stack.pop();cc.append(x)
   for y in adj[x]:
    if y not in seen:seen.add(y);stack.append(y)
  comps.append(sorted(cc))
 comps.sort(key=lambda q:q[0]);clusters=[];prefix='F06NQXC' if a.asset=='NQX' else 'F06XAUC'
 for ci,cc in enumerate(comps,1):
  ccset=set(cc);lp=[(x,y) for x,y in local if x in ccset and y in ccset]
  if len(cc)==1:means={cc[0]:1.};rep=cc[0]
  else:
   means={}
   for x in cc:
    vv=[]
    for y in cc:
     if x==y:continue
     k=(x,y) if x<y else (y,x);vv.append(pair[k][2])
    means[x]=float(np.mean(vv))
   best=max(means.values());rep=sorted([x for x,v in means.items() if abs(v-best)<=1e-15])[0]
  vals=[];corrs=[]
  for j,x in enumerate(cc):
   for y in cc[j+1:]:
    vals.append(pair[(x,y)][2]);c=corr_daily(passers[x]['daily'],passers[y]['daily'])
    if c is not None:corrs.append(c)
  typ='PLATEAU_SUPPORTED' if len(cc)>=2 and lp else ('ISOLATED_SINGLETON' if len(cc)==1 else 'MULTI_MEMBER_NONLOCAL')
  aliases={x:passers[x]['aliases'] for x in cc}
  clusters.append({'cluster_id':f'{prefix}{ci:03d}','direction':parse(rep)['side'],'size':len(cc),'type':typ,'local_neighbor_pairs':len(lp),'representative':rep,'representative_mean_geometric_similarity':means[rep],'members':cc,'aliases_by_member':aliases,'mean_pair_geometric_similarity':float(np.mean(vals)) if vals else 1.0,'min_pair_geometric_similarity':float(np.min(vals)) if vals else 1.0,'mean_daily_r_correlation_diagnostic':float(np.mean(corrs)) if corrs else None})
 h=hashlib.sha256()
 for cl in clusters:h.update((cl['cluster_id']+'|'+cl['representative']+'|'+';'.join(cl['members'])+'\n').encode())
 obj={'schema':'QROS_G30_F06_NON_ECONOMIC_CLUSTERING_V116_v1','status':'PASS','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F06_WICK','asset':a.asset,'scope':'DEV_2018_2019_GATE_A_PASSERS_ONLY_NO_2020_PLUS_PNL','rule_ref':'control/QROS_G30_F06_NON_ECONOMIC_CLUSTERING_BINDING_V116_v1.json','survivor_count':len(ids),'cluster_count':len(clusters),'buy_clusters':sum(x['direction']=='BUY' for x in clusters),'sell_clusters':sum(x['direction']=='SELL' for x in clusters),'plateau_supported_clusters':sum(x['type']=='PLATEAU_SUPPORTED' for x in clusters),'isolated_singletons':sum(x['type']=='ISOLATED_SINGLETON' for x in clusters),'multi_member_nonlocal':sum(x['type']=='MULTI_MEMBER_NONLOCAL' for x in clusters),'graph_edges':sum(len(v) for v in adj.values())//2,'local_parameter_neighbor_pairs':len(local),'representatives':[x['representative'] for x in clusters],'clusters':clusters,'cluster_assignment_root_sha256':h.hexdigest(),'future_strategy_pnl_2020_plus_read':False,'representative_selection_used_economics':False,'ledger_parity_all_passers':True,'decision':'FREEZE_ONE_REPRESENTATIVE_PER_CLUSTER_ALL_ALIASES_PRESERVED'}
 a.out.write_text(json.dumps(obj,separators=(',',':')))
 b=a.out.read_bytes();print(json.dumps({k:obj[k] for k in ['asset','survivor_count','cluster_count','buy_clusters','sell_clusters','plateau_supported_clusters','isolated_singletons','multi_member_nonlocal','graph_edges','local_parameter_neighbor_pairs','cluster_assignment_root_sha256']},sort_keys=True));print('bytes',len(b),'sha256',hashlib.sha256(b).hexdigest())
if __name__=='__main__':main()
