"""Independent vectorized mathematical reference for ONE_SIGNAL_PER_LEVEL CLOSE_BREAK M1.
Not a reference for TICK, RETEST, other timeframes or management profiles.
"""
import sys,json,hashlib,numpy as np
from pathlib import Path
sys.path.insert(0,'/mnt/data/seed0076_direct_dev')
from seed0076_direct_dev_backtest_v1 import fractal_levels,close_break_signals,ROOT

def independent_fractal3(high,low):
    n=len(high);p=np.arange(1,n-2,dtype=np.int64);i=p+2
    hit_hi=(high[p]>=high[p-1])&(high[p]>high[p+1])
    hit_lo=(low[p]<=low[p-1])&(low[p]<low[p+1])
    vhi=np.full(n,-1,np.int64);vlo=np.full(n,-1,np.int64)
    vhi[i[hit_hi]]=p[hit_hi];vlo[i[hit_lo]]=p[hit_lo]
    hid=np.maximum.accumulate(vhi);lid=np.maximum.accumulate(vlo)
    h=np.full(n,np.nan,np.float64);l=np.full(n,np.nan,np.float64)
    h[hid>=0]=high[hid[hid>=0]];l[lid>=0]=low[lid[lid>=0]]
    return h,l,hid,lid

def independent_signals(close,first,sh,sl,hid,lid,ef,em,es,side):
    n=len(close);bi=np.arange(2,n,dtype=np.int64);t=bi-1
    level=sh[bi] if side==1 else sl[bi]
    opp=sl[bi] if side==1 else sh[bi]
    lid0=hid[bi] if side==1 else lid[bi]
    if side==1:
        crosses=(close[t-1]<=level)&(close[t]>level)
        trends=(ef[t]>em[t])&(em[t]>es[t])
    else:
        crosses=(close[t-1]>=level)&(close[t]<level)
        trends=(ef[t]<em[t])&(em[t]<es[t])
    v=crosses&np.isfinite(level)&np.isfinite(opp)&(lid0>=0)
    # Determine FIRST raw crossing for each source-level identity BEFORE applying EMA filter.
    raw_idx=np.flatnonzero(v)
    _,raw_first=np.unique(lid0[raw_idx],return_index=True)
    take=raw_idx[np.sort(raw_first)]
    filtered=take[trends[take]]
    return first[bi[filtered]].astype(np.int64), opp[filtered].astype(np.int32)

def run():
    bars=np.load(ROOT/'bars_full/XAUUSD_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
    d=np.load(ROOT/'indicators_full/XAUUSD_M1_INDICATORS.npz',allow_pickle=False)
    h,l,hid,lid=independent_fractal3(bars['high_bid'],bars['low_bid'])
    hh,ll,hiid,liid=fractal_levels(bars['high_bid'].astype(np.float64),bars['low_bid'].astype(np.float64),3,0)
    invariant={
       'fractal_high_equal':bool(np.array_equal(h,hh,equal_nan=True)),
       'fractal_low_equal':bool(np.array_equal(l,ll,equal_nan=True)),
       'high_ids_equal':bool(np.array_equal(hid,hiid)),
       'low_ids_equal':bool(np.array_equal(lid,liid))}
    detail={}
    for side,name in [(1,'BUY'),(-1,'SELL')]:
        ref,rs=independent_signals(bars['close_bid'],bars['first_source_index'],h,l,hid,lid,d['EMA9'],d['EMA20'],d['EMA50'],side)
        got,gs=close_break_signals(bars['close_bid'],bars['first_source_index'],hh,ll,hiid,liid,d['EMA9'],d['EMA20'],d['EMA50'],side)
        same=np.array_equal(ref,got) and np.array_equal(rs,gs)
        invariant[name+'_event_tape_equal']=bool(same)
        detail[name]={'signals':len(ref),'first_source_tick':int(ref[0]) if len(ref) else None,'event_tape_sha256':hashlib.sha256(np.stack((ref,rs),axis=1).astype('<i8').tobytes()).hexdigest(),'earliest_mismatch':next((k for k in range(min(len(ref),len(got))) if ref[k]!=got[k] or rs[k]!=gs[k]),None)}
    result={'schema':'SEED0076_DIRECT_M1_INDEPENDENT_EVENT_ORACLE_v1','scope':'XAUUSD M1 2018-2019, fractal window3, source-asym ties, one per level close-break, EMA9/20/50','independent_algorithm':'vectorized 3-bar shifted comparisons + cumulative last available fractal; first raw breakout per level BEFORE trend filter','shared_dependencies':'same canonical bars/indicators and source input. Not independent tick decoder or quote execution oracle.','invariants':invariant,'detail':detail,'status':'PASS' if all(invariant.values()) else 'FAIL','holdout_open':False}
    out=ROOT/'run_v2'/'independent_event_oracle.json';out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'invariants':invariant,'detail':detail},sort_keys=True))
    if result['status']!='PASS':raise RuntimeError('INDEPENDENT_ORACLE_MISMATCH')
if __name__=='__main__':run()
