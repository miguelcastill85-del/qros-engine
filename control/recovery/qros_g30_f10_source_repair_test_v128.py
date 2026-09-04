from pathlib import Path
import tempfile
import numpy as np
import qros_g30_f10_tick_count_builder_v128 as B
import qros_g30_f10_transactional_v128 as R
def main():
 with tempfile.TemporaryDirectory() as td:
  d=Path(td);n=1800;mb=np.int64(1514764800000)+np.arange(n,dtype=np.int64)*60000
  rows=[];expected=np.zeros(n,np.int64)
  for i,t in enumerate(mb):
   for k in range(1+(i%4)):
    bid=100000+i%37+k;ask=bid+(0 if (i+k)%13==0 else 2)
    rows.append((t+1000+k*10000,bid,ask,0));expected[i]+=1
   if i%101==0:rows.append((t+59000,100010,100009,0))
  raw=np.array(rows,dtype=B.DT);src=d/'dev.bin';raw.tofile(src)
  close=100000+np.cumsum(np.where(np.arange(n)%11<6,1,-1));open_=np.r_[close[0],close[:-1]];high=np.maximum(open_,close)+2;low=np.minimum(open_,close)-2
  bo=open_*2;bh=high*2;bl=low*2;bc=close*2;mo=bo+2;mh=bh+2;ml=bl+2;mc=bc+2
  ix=np.flatnonzero(raw['ask']>raw['bid']);eb=(raw['ts'][ix]//60000)*60000;st=np.r_[0,np.flatnonzero(eb[1:]!=eb[:-1])+1];en=np.r_[st[1:],len(eb)]
  first=ix[st];last=ix[en-1];bid=raw['bid'][ix];ask=raw['ask'][ix]
  cache=d/'bars.npz';np.savez(cache,mb=mb,bo=bo,bh=bh,bl=bl,bc=bc,mo=mo,mh=mh,ml=ml,mc=mc,eb=eb[st],ebh=np.maximum.reduceat(bid,st),ebl=np.minimum.reduceat(bid,st),eah=np.maximum.reduceat(ask,st),eal=np.minimum.reduceat(ask,st),first=first,last=last)
  counts,crossed=B.build_counts(src,cache,257)
  assert crossed==sum(i%101==0 for i in range(n));assert np.array_equal(counts,expected)
  tick=d/'tick.npy';np.save(tick,counts,allow_pickle=False)
  for tf in (1,5,10,15,30,60):
   for side in ('BID','MID'):
    z,A,C,pa,pb=R.build_bars_prep(cache,tick,tf,side)
    try:
     assert len(A[0])==len(C[0]);assert set(pa['contexts'])==set(pb['contexts'])
     for k in pa['contexts']:assert np.array_equal(pa['contexts'][k],pb['contexts'][k])
    finally:z.close()
 print('PASS_F10_SOURCE_REPAIR_V128')
if __name__=='__main__':main()
