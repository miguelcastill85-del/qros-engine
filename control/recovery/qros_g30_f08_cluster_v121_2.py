#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib,math,sys
from pathlib import Path
import numpy as np
from scipy import sparse
from numba import njit
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f08_transactional_v121 as r
import qros_g30_f08_signal_primary_v121 as sa
TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.];NS=[1,2,3,4,5,8]

def parse(sid):
 shard,side,key=sid.split(':',2);tf,feature=shard.split('_');ctxlb,timing,t,fam,n=key.split('|');ctx,L=ctxlb.rsplit('@L',1)
 return {'shard':shard,'tf':tf,'feature':feature,'side':side,'context':ctx,'lookback':int(L),'timing':timing,'threshold':float(t),'family':fam,'n':int(n),'key':key}
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
 return dif==1

def build_binary(arrays):
 if not arrays:return sparse.csr_matrix((0,0),dtype=np.int32),np.zeros(0,np.int64)
 lens=np.asarray([len(x) for x in arrays],np.int64);total=int(lens.sum())
 if total==0:return sparse.csr_matrix((len(arrays),0),dtype=np.int32),lens
 allv=np.concatenate(arrays);uniq=np.unique(allv);rows=np.repeat(np.arange(len(arrays),dtype=np.int32),lens);cols=np.searchsorted(uniq,allv).astype(np.int32);data=np.ones(total,np.int32)
 return sparse.csr_matrix((data,(rows,cols)),shape=(len(arrays),len(uniq)),dtype=np.int32),lens

def exact_jacc_dense(arrays):
 M,lens=build_binary(arrays);n=len(arrays)
 if n==0:return np.zeros((0,0),np.float64)
 inter=(M@M.T).toarray().astype(np.float64);union=lens[:,None]+lens[None,:]-inter;out=np.zeros((n,n),np.float64);np.divide(inter,union,out=out,where=union>0);out[union==0]=1.0;return out

def components_union(edge):
 n=edge.shape[0];p=np.arange(n,dtype=np.int32);rank=np.zeros(n,np.int8)
 def find(x):
  while p[x]!=x:p[x]=p[p[x]];x=int(p[x])
  return x
 def union(a,b):
  a=find(a);b=find(b)
  if a==b:return
  if rank[a]<rank[b]:a,b=b,a
  p[b]=a
  if rank[a]==rank[b]:rank[a]+=1
 ii,jj=np.where(np.triu(edge,1))
 for a,b in zip(ii.tolist(),jj.tolist()):union(a,b)
 groups={}
 for i in range(n):groups.setdefault(find(i),[]).append(i)
 return [sorted(v) for _,v in sorted(groups.items(),key=lambda kv:min(kv[1]))]

def components_dfs(edge):
 n=edge.shape[0];seen=np.zeros(n,bool);out=[]
 for root in range(n):
  if seen[root]:continue
  st=[root];seen[root]=1;cc=[]
  while st:
   x=st.pop();cc.append(x)
   for y in np.flatnonzero(edge[x]):
    if not seen[y]:seen[y]=1;st.append(int(y))
  out.append(sorted(cc))
 return out

def flatten_sorted(arrays):
 lens=np.asarray([len(x) for x in arrays],np.int64);off=np.zeros(len(arrays)+1,np.int64);off[1:]=np.cumsum(lens)
 vals=np.concatenate(arrays).astype(np.int64,copy=False) if int(off[-1]) else np.empty(0,np.int64)
 return vals,off

@njit(cache=True)
def jacc_flat(vals,off,i,j):
 a=off[i];ae=off[i+1];b=off[j];be=off[j+1];inter=0
 while a<ae and b<be:
  va=vals[a];vb=vals[b]
  if va==vb:inter+=1;a+=1;b+=1
  elif va<vb:a+=1
  else:b+=1
 u=(ae-off[i])+(be-off[j])-inter
 return 1.0 if u==0 else inter/u

@njit(cache=True)
def verify_edges_exact(si,sio,ti,tio,ii,jj):
 for k in range(len(ii)):
  a=ii[k];b=jj[k];sj=jacc_flat(si,sio,a,b);tj=jacc_flat(ti,tio,a,b);g=(sj*tj)**0.5
  if not (sj>=0.5 and tj>=0.5 and g>=0.7):return False,k,sj,tj,g
 return True,-1,0.0,0.0,0.0

@njit(cache=True)
def medoid_scores_exact(si,sio,ti,tio,cc):
 m=len(cc);scores=np.ones(m,np.float64)
 if m<=1:return scores
 sums=np.zeros(m,np.float64)
 for x in range(m):
  i=cc[x]
  for y in range(x+1,m):
   j=cc[y];g=(jacc_flat(si,sio,i,j)*jacc_flat(ti,tio,i,j))**0.5;sums[x]+=g;sums[y]+=g
 for x in range(m):scores[x]=sums[x]/(m-1)
 return scores

@njit(cache=True)
def local_pair_stats(tf,fam,feat,timing,thr,nv,labels,ncomp):
 n=len(tf);total=0;within=np.zeros(ncomp,np.int64)
 for i in range(n):
  for j in range(i+1,n):
   if tf[i]!=tf[j] or fam[i]!=fam[j]:continue
   dif=0
   if feat[i]!=feat[j]:dif+=1
   if timing[i]!=timing[j]:dif+=1
   if thr[i]!=thr[j]:
    if abs(thr[i]-thr[j])!=1:continue
    dif+=1
   if nv[i]!=nv[j]:
    if abs(nv[i]-nv[j])!=1:continue
    dif+=1
   if dif==1:
    total+=1
    if labels[i]==labels[j]:within[labels[i]]+=1
 return total,within

def categorical_metadata(ids,comps):
 P=[parse(x) for x in ids]
 tf_names={x:i for i,x in enumerate(sorted({p['tf'] for p in P}))};fam_names={x:i for i,x in enumerate(sorted({p['family'] for p in P}))}
 tf=np.asarray([tf_names[p['tf']] for p in P],np.int16);fam=np.asarray([fam_names[p['family']] for p in P],np.int16);feat=np.asarray([0 if p['feature']=='BID' else 1 for p in P],np.int8);timing=np.asarray([0 if p['timing']=='CURRENT_BAR_INCLUDED' else 1 for p in P],np.int8);thr=np.asarray([TH.index(p['threshold']) for p in P],np.int8);nv=np.asarray([NS.index(p['n']) for p in P],np.int8)
 labels=np.empty(len(ids),np.int32)
 for k,cc in enumerate(comps):labels[np.asarray(cc,np.int32)]=k
 return tf,fam,feat,timing,thr,nv,labels

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();passers={}
 for d in sorted(a.root.glob(f'{a.asset}_*')):
  p=d/'result.json'
  if not p.is_file():continue
  o=json.load(open(p));shard=o['shard']
  for q in o['passers']:
   sid=f"{shard}:{q['side']}:{q['id']}"
   if sid in passers:raise SystemExit('DUP '+sid)
   passers[sid]={'stable_id':sid,'metrics':q,'aliases':q.get('aliases',[])}
 shards=sorted(set(x.split(':',1)[0] for x in passers))
 for shard in shards:
  tfname,fs=shard.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);W=a.root/f'{a.asset}_{tfname}_{fs}';meta=json.load(open(W/'manifest.json'));z,A,B,pa,pb=r.base.build_bars_prep(Path(meta['cache']),tf,fs)
  try:
   OA_B=tuple(r.base.load_arr(W,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(r.base.load_arr(W,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'));step=tf*60000
   for sid in [x for x in passers if x.startswith(shard+':')]:
    m=passers[sid]['metrics'];d=m['signal_sha256'];spec=tuple(meta['by'][d]['spec']);b,s=sa.mask(pa,*A[1:],*spec);mask=b if m['side']=='BUY' else s;OA=OA_B if m['side']=='BUY' else OA_S;idx=np.flatnonzero(mask).astype(np.int64);ch=r.base.select_a(idx,OA[0],OA[1])
    if len(ch)!=int(m['n']):raise SystemExit('TRADE_COUNT_MISMATCH '+sid)
    if r.base.ledger_sha(ch,OA[0],OA[1],OA[5])!=m['ledger_sha256']:raise SystemExit('LEDGER_MISMATCH '+sid)
    sig=np.asarray(A[0][mask]+step,dtype=np.int64);ent=np.asarray(OA[0][ch],dtype=np.int64)
    if len(sig)>1 and np.any(sig[1:]<=sig[:-1]):raise SystemExit('SIG_ORDER '+sid)
    if len(ent)>1 and np.any(ent[1:]<=ent[:-1]):raise SystemExit('ENT_ORDER '+sid)
    passers[sid].update(signal_times=sig,entry_times=ent)
  finally:z.close()
 print(json.dumps({'stage':'LEDGER_PARITY_PASS','asset':a.asset,'passers':len(passers)}),flush=True)
 ids_all=sorted(passers);clusters=[];total_edges=0;local_total=0;prefix='F08NQXC' if a.asset=='NQX' else 'F08XAUC';ci=0
 for side in ('BUY','SELL'):
  ids=[x for x in ids_all if parse(x)['side']==side];sig=[passers[x]['signal_times'] for x in ids];ent=[passers[x]['entry_times'] for x in ids]
  print(json.dumps({'stage':'JACCARD_START','asset':a.asset,'side':side,'passers':len(ids)}),flush=True)
  SJ=exact_jacc_dense(sig);TJ=exact_jacc_dense(ent);G=np.sqrt(SJ*TJ);edge=(SJ>=.5)&(TJ>=.5)&(G>=.7);np.fill_diagonal(edge,False);ii,jj=np.where(np.triu(edge,1));total_edges+=len(ii)
  comps=components_union(edge);comps2=components_dfs(edge)
  if comps!=comps2:raise SystemExit('COMPONENT_PARITY_FAIL '+side)
  sf,so=flatten_sorted(sig);ef,eo=flatten_sorted(ent);ok,k,sj,tj,g=verify_edges_exact(sf,so,ef,eo,ii.astype(np.int32),jj.astype(np.int32))
  if not ok:raise SystemExit(f'EDGE_INDEPENDENT_FAIL side={side} k={k} sj={sj} tj={tj} g={g}')
  tf,fam,feat,timing,thr,nv,labels=categorical_metadata(ids,comps);lp_total,within=local_pair_stats(tf,fam,feat,timing,thr,nv,labels,len(comps));local_total+=int(lp_total)
  for comp_no,cc in enumerate(comps):
   ci+=1;cc_arr=np.asarray(cc,np.int32);lp=int(within[comp_no])
   if len(cc)==1:rep_i=cc[0];meanrep=1.0
   else:
    sub=G[np.ix_(cc,cc)].copy();np.fill_diagonal(sub,0.0);means=sub.sum(1)/(len(cc)-1);best=float(means.max());cand=[cc[k] for k,v in enumerate(means) if abs(float(v)-best)<=1e-15];rep_i=min(cand,key=lambda q:ids[q]);meanrep=best
    scores=medoid_scores_exact(sf,so,ef,eo,cc_arr);best2=float(scores.max());cand2=[cc[k] for k,v in enumerate(scores) if abs(float(v)-best2)<=1e-15];rep2=min(cand2,key=lambda q:ids[q])
    if rep2!=rep_i:raise SystemExit('MEDOID_INDEPENDENT_FAIL '+ids[rep_i]+' '+ids[rep2])
   members=[ids[k] for k in cc];typ='PLATEAU_SUPPORTED' if len(cc)>=2 and lp else ('ISOLATED_SINGLETON' if len(cc)==1 else 'MULTI_MEMBER_NONLOCAL')
   if len(cc)>1:
    sub=G[np.ix_(cc,cc)];tri=sub[np.triu_indices(len(cc),1)];meanpair=float(tri.mean());minpair=float(tri.min())
   else:meanpair=minpair=1.0
   clusters.append({'cluster_id':f'{prefix}{ci:04d}','direction':side,'size':len(cc),'type':typ,'local_neighbor_pairs':lp,'representative':ids[rep_i],'representative_mean_geometric_similarity':meanrep,'members':members,'aliases_by_member':{x:passers[x]['aliases'] for x in members},'mean_pair_geometric_similarity':meanpair,'min_pair_geometric_similarity':minpair})
  print(json.dumps({'stage':'PARTITION_DONE','asset':a.asset,'side':side,'passers':len(ids),'components':len(comps),'edges':len(ii),'local_parameter_neighbor_pairs':int(lp_total)}),flush=True)
 h=hashlib.sha256()
 for cl in clusters:h.update((cl['cluster_id']+'|'+cl['representative']+'|'+';'.join(cl['members'])+'\n').encode())
 obj={'schema':'QROS_G30_F08_NON_ECONOMIC_CLUSTERING_V121_v1','status':'PASS','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F08_VOLATILITY_CONTEXT','asset':a.asset,'scope':'DEV_2018_2019_GATE_A_PASSERS_ONLY_NO_2020_PLUS_PNL','rule_ref':'control/QROS_G30_F08_NON_ECONOMIC_CLUSTERING_BINDING_V121_v1.json','survivor_count':len(ids_all),'cluster_count':len(clusters),'buy_clusters':sum(x['direction']=='BUY' for x in clusters),'sell_clusters':sum(x['direction']=='SELL' for x in clusters),'plateau_supported_clusters':sum(x['type']=='PLATEAU_SUPPORTED' for x in clusters),'isolated_singletons':sum(x['type']=='ISOLATED_SINGLETON' for x in clusters),'multi_member_nonlocal':sum(x['type']=='MULTI_MEMBER_NONLOCAL' for x in clusters),'graph_edges':total_edges,'local_parameter_neighbor_pairs':local_total,'representatives':[x['representative'] for x in clusters],'clusters':clusters,'cluster_assignment_root_sha256':h.hexdigest(),'future_strategy_pnl_2020_plus_read':False,'representative_selection_used_economics':False,'ledger_parity_all_passers':True,'independent_component_parity':'PASS_EXACT','independent_accepted_edge_parity':'PASS_EXACT','independent_medoid_parity':'PASS_EXACT','decision':'FREEZE_ONE_REPRESENTATIVE_PER_CLUSTER_ALL_ALIASES_PRESERVED'}
 a.out.write_text(json.dumps(obj,separators=(',',':')));b=a.out.read_bytes();print(json.dumps({k:obj[k] for k in ['asset','survivor_count','cluster_count','buy_clusters','sell_clusters','plateau_supported_clusters','isolated_singletons','multi_member_nonlocal','graph_edges','local_parameter_neighbor_pairs','cluster_assignment_root_sha256']},sort_keys=True));print('bytes',len(b),'sha256',hashlib.sha256(b).hexdigest())
if __name__=='__main__':main()
