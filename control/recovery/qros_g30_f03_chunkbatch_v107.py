#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import qros_g30_f03_gate_a_v97 as g
import qros_g30_f03_signal_primary_v97 as sa
import qros_g30_f03_signal_independent_v97 as sb
import qros_g30_f03_gate_a_fastscore_v101 as v101
import qros_g30_f03_transactional_v104 as v104

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--start',type=int,required=True);ap.add_argument('--end',type=int,required=True);ap.add_argument('--chunk-size',type=int,default=100);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args()
 root=a.work;meta=json.loads((root/'manifest.json').read_text());order=meta['order'];end=min(a.end,len(order));a.out_dir.mkdir(parents=True,exist_ok=True)
 if a.start<0 or a.start>=end:raise SystemExit('BAD_RANGE')
 mm=np.memmap(meta['src'],dtype=g.DT,mode='r');z,A,B,pa,pb=v104.build_bars_prep(Path(meta['cache']),meta['tf'],meta['feature_side'])
 try:
  OA_B=tuple(v104.load_arr(root,'B_'+x) for x in ('et','xt','ei','xi','dist','rr'));OA_S=tuple(v104.load_arr(root,'S_'+x) for x in ('et','xt','ei','xi','dist','rr'))
  s=a.start
  while s<end:
   e=min(s+a.chunk_size,end);recs=[];passers=[]
   for i in range(s,e):
    d=order[i];m=meta['by'][d];sp=tuple(m['spec']);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
    if not np.array_equal(bA,bB) or not np.array_equal(sA,sB) or g.mask_digest(bA,sA)!=d or g.mask_digest(bB,sB)!=d:raise SystemExit('REPLAY_SIGNAL_PARITY_FAIL '+m['key'])
    for side,mask,OA in [('BUY',bA,OA_B),('SELL',sA,OA_S)]:
     ids=np.flatnonzero(mask).astype(np.int64);chA=v101.select_idx_A(ids,OA[0],OA[1]);chB=v101.select_idx_B(ids,OA[0],OA[1])
     if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+m['key']+' '+side)
     rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
     if len(chA):
      spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
     else:cons=rr.copy();sev=rr.copy()
     y18=float(rr[et<g.CUT_2019].sum());y19=float(rr[et>=g.CUT_2019].sum());pfc=g.pf(rr);pfk=g.pf(cons);pfs=g.pf(sev);passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
     rec={'id':m['key'],'aliases':m['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':v101.ledger_sha_fast(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)};recs.append(rec)
     if passed:passers.append(rec)
   out={'start':s,'end':e,'records':recs,'passers':passers};p=a.out_dir/f'{s}_{e}.json';p.write_text(json.dumps(g.safe(out),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'start':s,'end':e,'records':len(recs),'passers':len(passers)},sort_keys=True),flush=True);s=e
 finally:z.close()
if __name__=='__main__':main()
