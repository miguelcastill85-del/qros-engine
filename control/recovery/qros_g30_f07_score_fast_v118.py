#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import qros_g30_f07_transactional_v117 as f07
base=f07.base; sa=f07.sa

def score(work:Path,start:int,end:int,out:Path):
 meta=json.loads((work/'manifest.json').read_text());order=meta['order'];end=min(end,len(order))
 if start<0 or start>=end:raise SystemExit('BAD_RANGE')
 mm=np.memmap(meta['src'],dtype=base.DT,mode='r');z=np.load(meta['cache'])
 try:
  mb=z['mb'];ks=('bo','bh','bl','bc') if meta['feature_side']=='BID' else ('mo','mh','ml','mc');A=sa.bars(mb,*[z[k] for k in ks],meta['tf'])
  if base.digest_arrays(A)!=meta['bar_digest']:raise SystemExit('BAR_DIGEST_MISMATCH')
  pa=sa.prepare(*A)
  OA_B=tuple(base.load_arr(work,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(base.load_arr(work,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'));recs=[];passers=[]
  for i in range(start,end):
   d=order[i];m=meta['by'][d];sp=tuple(m['spec']);b,s=sa.mask(pa,*A[1:],*sp)
   if base.mask_digest(b,s)!=d:raise SystemExit('PRIMARY_REPLAY_SIGNAL_DIGEST_FAIL '+m['key'])
   for side,mask,OA in [('BUY',b,OA_B),('SELL',s,OA_S)]:
    ids=np.flatnonzero(mask).astype(np.int64);chA=base.select_a(ids,OA[0],OA[1]);chB=base.select_b(ids,OA[0],OA[1])
    if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+m['key']+' '+side)
    rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    y18=float(rr[et<base.CUT_2019].sum());y19=float(rr[et>=base.CUT_2019].sum());pfc=base.pf(rr);pfk=base.pf(cons);pfs=base.pf(sev);passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
    rec={'id':m['key'],'aliases':m['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':base.ledger_sha(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)};recs.append(rec)
    if passed:passers.append(rec)
  obj={'start':start,'end':end,'records':recs,'passers':passers};out.write_text(json.dumps(base.safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'start':start,'end':end,'records':len(recs),'passers':len(passers)},sort_keys=True),flush=True)
 finally:z.close()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--start',type=int,required=True);ap.add_argument('--end',type=int,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();score(a.work,a.start,a.end,a.out)
if __name__=='__main__':main()
