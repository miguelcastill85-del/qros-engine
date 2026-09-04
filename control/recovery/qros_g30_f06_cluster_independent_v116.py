#!/usr/bin/env python3
import argparse,json,math,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f06_transactional_v115 as r
import qros_g30_f06_signal_independent_v115 as sb

def jac(a,b):
 u=len(a|b)
 return 1.0 if u==0 else len(a&b)/u

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset');ap.add_argument('--root',type=Path);ap.add_argument('--primary',type=Path);a=ap.parse_args()
 passers={}
 for p in sorted((a.root/'results').glob(f'{a.asset}_*.json')):
  o=json.load(open(p)); sh=o['shard']
  for q in o['passers']:passers[f"{sh}:{q['side']}:{q['id']}"]={'m':q}
 for sh in sorted(set(x.split(':',1)[0] for x in passers)):
  tfname,fs=sh.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);W=a.root/'work'/f'{a.asset}_{tfname}_{fs}';meta=json.load(open(W/'manifest.json'))
  z=np.load(meta['cache']);mb=z['mb'];ks=('bo','bh','bl','bc') if fs=='BID' else ('mo','mh','ml','mc');B=sb.bars(mb,*[z[k] for k in ks],tf);pb=sb.prepare(*B);step=tf*60000
  OB=tuple(r.load_arr(W,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OS=tuple(r.load_arr(W,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'))
  for sid in [x for x in passers if x.startswith(sh+':')]:
   m=passers[sid]['m'];spec=tuple(meta['by'][m['signal_sha256']]['spec']);b,s=sb.mask(pb,*B[1:],*spec);mask=b if m['side']=='BUY' else s;O=OB if m['side']=='BUY' else OS
   ids=np.flatnonzero(mask).astype(np.int64);ch=r.select_b(ids,O[0],O[1])
   if len(ch)!=m['n'] or r.ledger_sha(ch,O[0],O[1],O[5])!=m['ledger_sha256']:raise SystemExit('LEDGER_PARITY_FAIL '+sid)
   passers[sid]['sig']=set(map(int,(B[0][mask]+step).tolist()));passers[sid]['ent']=set(map(int,O[0][ch].tolist()))
  z.close()
 ids=sorted(passers);idx={x:i for i,x in enumerate(ids)};parent=list(range(len(ids)));rank=[0]*len(ids);sim={}
 def find(x):
  while parent[x]!=x:
   parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(x,y):
  x=find(x);y=find(y)
  if x==y:return
  if rank[x]<rank[y]:x,y=y,x
  parent[y]=x
  if rank[x]==rank[y]:rank[x]+=1
 for i,x in enumerate(ids):
  sx=x.split(':',2)[1]
  for y in ids[i+1:]:
   if sx!=y.split(':',2)[1]:continue
   sj=jac(passers[x]['sig'],passers[y]['sig']);tj=jac(passers[x]['ent'],passers[y]['ent']);g=math.sqrt(sj*tj);sim[(x,y)]=g
   if sj>=.5 and tj>=.5 and g>=.7:union(i,idx[y])
 groups={}
 for x in ids:groups.setdefault(find(idx[x]),[]).append(x)
 comps=sorted([sorted(v) for v in groups.values()],key=lambda q:q[0])
 reps=[]
 for cc in comps:
  if len(cc)==1:reps.append(cc[0]);continue
  means={}
  for x in cc:
   s=0.;n=0
   for y in cc:
    if x==y:continue
    k=(x,y) if x<y else (y,x);s+=sim[k];n+=1
   means[x]=s/n
  best=max(means.values());reps.append(sorted(x for x,v in means.items() if abs(v-best)<=1e-15)[0])
 p=json.load(open(a.primary));pc=[c['members'] for c in p['clusters']];pr=[c['representative'] for c in p['clusters']]
 if comps!=pc:raise SystemExit('COMPONENT_MISMATCH')
 if reps!=pr:raise SystemExit('MEDOID_MISMATCH')
 print(json.dumps({'asset':a.asset,'status':'PASS_EXACT','survivors':len(ids),'clusters':len(comps),'representatives':len(reps)}))
if __name__=='__main__':main()
