from __future__ import annotations
import json, hashlib, sys, time
from pathlib import Path
import numpy as np
import qros_g30_dual_core_v60 as q
import qros_g30_stage_wrapper_v60 as w

def run(src, cache, candidates, start_ms, end_ms, tf, fs, outpath, label):
    t=time.time()
    reps=[r for r in w.load_reps(candidates) if r[1]==tf and r[2]==fs]
    if not reps:
        raise SystemExit(f'NO_CANDIDATES_FOR_GROUP {tf}_{fs}')
    mm=np.memmap(src,dtype=q.DT,mode='r')
    z=np.load(cache)
    eb,ebh,ebl,eah,eal,first,last=[z[k] for k in ['eb','ebh','ebl','eah','eal','first','last']]
    ba,oa,ha,la,ca=q.aggregate_from_m1(z,tf,fs)
    step=q.TFM[tf]*60000
    bb,ob,hb,lb,cb=q.build_target_bars_direct(mm['ts'],mm['bid'],mm['ask'],step,fs=='MID')
    if not all(np.array_equal(x,y) for x,y in zip((ba,oa,ha,la,ca),(bb,ob,hb,lb,cb))):
        raise SystemExit('BAR_PARITY_FAIL '+tf+'_'+fs)
    atrA=q.atr_vec(ha,la,ca); atrB=q.atr_loop(hb,lb,cb)
    if not np.allclose(atrA,atrB,equal_nan=True,rtol=0,atol=1e-12):
        raise SystemExit('ATR_PARITY_FAIL '+tf+'_'+fs)
    outA={}; outB={}
    for sd in sorted(set(r[3] for r in reps)):
        code=1 if sd=='BUY' else -1
        outA[sd]=q.outcomes_A(mm['ts'],mm['bid'],mm['ask'],ba,atrA,step,eb,ebh,ebl,eah,eal,first,last,code)
        outB[sd]=q.outcomes_B(mm['ts'],mm['bid'],mm['ask'],bb,atrB,step,eb,ebh,ebl,eah,eal,first,last,code)
        for ix in [0,1,2,3,6]:
            if not np.array_equal(outA[sd][ix],outB[sd][ix]):
                raise SystemExit(f'OUTCOME_PARITY_FAIL {tf}_{fs}_{sd}_{ix}')
    A={}; B={}; parity=[]
    for r in reps:
        cid,_,_,sd,timing,thr,fam,n,stable=r
        _,ma=q.signal_mask_A(ba,oa,ha,la,ca,timing,thr,fam,n,sd)
        _,mb=q.signal_mask_B(bb,ob,hb,lb,cb,timing,thr,fam,n,sd)
        if not np.array_equal(ma,mb):
            raise SystemExit('SIGNAL_PARITY_FAIL '+stable)
        ra=w.metrics(ma,ba,step,outA[sd],mm,start_ms,end_ms)
        rb=w.metrics(mb,bb,step,outB[sd],mm,start_ms,end_ms)
        if ra!=rb:
            raise SystemExit('TRADE_METRIC_PARITY_FAIL '+stable)
        A[cid]={'stable_id':stable,**ra}; B[cid]={'stable_id':stable,**rb}
        parity.append({'cluster':cid,'stable_id':stable,'parity':True,'ledger_sha256':ra['ledger_sha256'],'n':ra['n']})
    obj={'schema':'QROS_G30_STAGE_GROUP_V62_OUTPUT_v1','label':label,'group':f'{tf}_{fs}',
         'stage_start_ms':int(start_ms),'stage_end_ms_exclusive':int(end_ms),'source_records':int(len(mm)),
         'candidates':len(reps),'parity_all':all(x['parity'] for x in parity),'primary':A,'independent':B,
         'parity':parity,'elapsed_sec':time.time()-t}
    Path(outpath).write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    print(json.dumps({'group':obj['group'],'candidates':len(reps),'parity_all':obj['parity_all'],
                      'elapsed_sec':obj['elapsed_sec'],'sha256':hashlib.sha256(Path(outpath).read_bytes()).hexdigest()},sort_keys=True))

if __name__=='__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),sys.argv[6],sys.argv[7],Path(sys.argv[8]),sys.argv[9])
