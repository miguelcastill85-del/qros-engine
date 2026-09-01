from __future__ import annotations
import json,hashlib,sys,time
from pathlib import Path
import numpy as np
import qros_g30_dual_runner_v58 as q

def load_reps(path):
    d=json.load(open(path)); out=[]
    for c in d['representatives']:
        rep=c['representative']; shard,side,key=rep.split(':',2); tf,fs=shard.split('_',1); timing,thr,fam,n=key.split('|')
        out.append((c['cluster'],tf,fs,side,timing,float(thr),fam,int(n),rep))
    return out

def year_numeric(ts_ms):
    # Numeric calendar encoded by frozen source-clock timestamps; this does not reinterpret the source as UTC.
    import datetime
    return datetime.datetime.fromtimestamp(int(ts_ms)/1000,datetime.timezone.utc).year

def pf(a):
    gp=float(a[a>0].sum()); gl=float(-a[a<0].sum())
    if gl==0: return None if gp==0 else float('inf')
    return gp/gl

def metrics(mask,bucket,step,out,mm,start_ms,end_ms):
    # stage membership is by causal signal close time, not entry time
    stage=(bucket+step>=start_ms)&(bucket+step<end_ms)
    chosen=q.select_mask(mask&stage,out[2],out[3])
    eti,xti,et,xt,rr,dist,actual,hk=out
    r=actual[chosen]; d=dist[chosen]
    if len(chosen):
        se=mm['ask'][eti[chosen]].astype(float)-mm['bid'][eti[chosen]].astype(float)
        sx=mm['ask'][xti[chosen]].astype(float)-mm['bid'][xti[chosen]].astype(float)
        cons=r-0.5*(se+sx)/d; sev=r-(se+sx)/d
    else: cons=sev=r.copy()
    years=np.array([year_numeric(t) for t in et[chosen]],int) if len(chosen) else np.array([],int)
    annual={str(y):float(r[years==y].sum()) for y in sorted(set(years.tolist()))}
    h=hashlib.sha256()
    for a,b,v in zip(et[chosen],xt[chosen],r):
        h.update(np.int64(a).tobytes()); h.update(np.int64(b).tobytes()); h.update(np.float64(v).tobytes())
    return {'n':int(len(chosen)),'net_r_central':float(r.sum()),'net_r_conservative':float(cons.sum()),'net_r_severe':float(sev.sum()),'pf_central':pf(r),'pf_conservative':pf(cons),'pf_severe':pf(sev),'annual_net_r_central':annual,'ledger_sha256':h.hexdigest()}

def run(src,cache,candidates,start_ms,end_ms,outpath,label):
    t=time.time(); reps=load_reps(candidates); mm=np.memmap(src,dtype=q.DT,mode='r'); z=np.load(cache)
    eb,ebh,ebl,eah,eal,first,last=[z[k] for k in ['eb','ebh','ebl','eah','eal','first','last']]
    groups={}
    for r in reps: groups.setdefault((r[1],r[2]),[]).append(r)
    A={}; B={}; parity=[]
    for (tf,fs), rs in groups.items():
        print('group',tf,fs,len(rs),flush=True)
        ba,oa,ha,la,ca=q.aggregate_from_m1(z,tf,fs)
        bb,ob,hb,lb,cb=q.build_target_bars_direct(mm['ts'],mm['bid'],mm['ask'],q.TFM[tf]*60000,fs=='MID')
        if not all(np.array_equal(x,y) for x,y in zip((ba,oa,ha,la,ca),(bb,ob,hb,lb,cb)): raise SystemExit('BAR_PARITY_FAIL '+tf+'_'+fs)
        atrA=q.atr_vec(ha,la,ca); atrB=q.atr_loop(hb,lb,cb)
        if not np.allclose(atrA,atrB,equal_nan=True,rtol=0,atol=1e-12): raise SystemExit('ATR_PARITY_FAIL '+tf+'_'+fs)
        outA={}; outB={}
        for sd in sorted(set(r[3] for r in rs)):
            code=1 if sd=='BUY' else -1; step=q.TFM[tf]*60000
            outA[sd]=q.outcomes_A(mm['ts'],mm['bid'],mm['ask'],ba,atrA,step,eb,ebh,ebl,eah,eal,first,last,code)
            outB[sd]=q.outcomes_B(mm['ts'],mm['bid'],mm['ask'],bb,atrB,step,eb,ebh,ebl,eah,eal,first,last,code)
            for ix in [0,1,2,3,6]:
                if not np.array_equal(outA[sd][ix],outB[sd][ix]): raise SystemExit(f'OUTCOME_PARITY_FAIL {tf}_{fs}_{sd}_{ix}')
        for r in rs:
            cid,tf,fs,sd,timing,thr,fam,n,stable=r; step=q.TFM[tf]*60000
            _,ma=q.signal_mask_A(ba,oa,ha,la,ca,timing,thr,fam,n,sd); _,mb=q.signal_mask_B(bb,ob,hb,lb,cb,timing,thr,fam,n,sd)
            if not np.array_equal(ma,mb): raise SystemExit('SIGNAL_PARITY_FAIL '+stable)
            ra=metrics(ma,ba,step,outA[sd],mm,start_ms,end_ms); rb=metrics(mb,bb,step,outB[sd],mm,start_ms,end_ms)
            exact=ra==rb
            if not exact: raise SystemExit('TRADE_METRIC_PARITY_FAIL '+stable)
            A[cid]={'stable_id':stable,**ra}; B[cid]={'stable_id':stable,**rb}; parity.append({'cluster':cid,'stable_id':stable,'parity':True,'ledger_sha256':ra['ledger_sha256'],'n':ra['n']})
    obj={'schema':'QROS_G30_FIRST_AVAILABLE_DUAL_STAGE_RUNNER_V60_OUTPUT_v1','label':label,'stage_start_ms':int(start_ms),'stage_end_ms_exclusive':int(end_ms),'source_records':int(len(mm)),'candidates':len(reps),'parity_all':all(x['parity'] for x in parity),'primary':A,'independent':B,'parity':parity,'elapsed_sec':time.time()-t}
    Path(outpath).write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8'); print(json.dumps({'label':label,'candidates':len(reps),'parity_all':obj['parity_all'],'elapsed_sec':obj['elapsed_sec'],'sha256':hashlib.sha256(Path(outpath).read_bytes()).hexdigest()}))
if __name__=='__main__': run(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),Path(sys.argv[6]),sys.argv[7])
