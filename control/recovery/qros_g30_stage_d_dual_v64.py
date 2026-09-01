from __future__ import annotations
import numpy as np, json, hashlib, time, os
from numba import njit
from pathlib import Path

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
RAW=Path('/mnt/data/NQX_PACKED17_ROWS_400000000_559817686.bin')
OUT=Path('/mnt/data/G30V59C015_STAGE_D_2025_2026_DUAL.json')
STEP=600_000
DAY=86_400_000
STAGE_START=1735689600000
YEAR2026=1767225600000
STAGE_END=1785143472710

@njit(cache=True)
def count_bars(ts,bid,ask):
    n=0; last=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i] < bid[i]: continue
        b=(ts[i]//STEP)*STEP
        if b!=last:
            n+=1; last=b
    return n

@njit(cache=True)
def build_bars_A(ts,bid,ask):
    n=count_bars(ts,bid,ask)
    bu=np.empty(n,np.int64); op=np.empty(n,np.int64); hi=np.empty(n,np.int64); lo=np.empty(n,np.int64); cl=np.empty(n,np.int64)
    k=-1; last=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i] < bid[i]: continue
        b=(ts[i]//STEP)*STEP; x=np.int64(bid[i])+np.int64(ask[i])
        if b!=last:
            k+=1; last=b; bu[k]=b; op[k]=x; hi[k]=x; lo[k]=x; cl[k]=x
        else:
            if x>hi[k]: hi[k]=x
            if x<lo[k]: lo[k]=x
            cl[k]=x
    return bu,op,hi,lo,cl

def build_bars_B(mm, block=2_000_000):
    buckets=[]; opens=[]; highs=[]; lows=[]; closes=[]
    carry=None
    for s in range(0,len(mm),block):
        a=mm[s:min(len(mm),s+block)]
        valid=a['ask']>=a['bid']
        if not np.any(valid): continue
        ts=a['ts'][valid]; x=a['bid'][valid].astype(np.int64)+a['ask'][valid].astype(np.int64)
        b=(ts//STEP)*STEP
        st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]; en=np.r_[st[1:],len(b)]
        bb=b[st]; oo=x[st]; hh=np.maximum.reduceat(x,st); ll=np.minimum.reduceat(x,st); cc=x[en-1]
        for j in range(len(bb)):
            rec=(int(bb[j]),int(oo[j]),int(hh[j]),int(ll[j]),int(cc[j]))
            if carry is not None and rec[0]==carry[0]:
                carry=(carry[0],carry[1],max(carry[2],rec[2]),min(carry[3],rec[3]),rec[4])
            else:
                if carry is not None:
                    buckets.append(carry[0]); opens.append(carry[1]); highs.append(carry[2]); lows.append(carry[3]); closes.append(carry[4])
                carry=rec
    if carry is not None:
        buckets.append(carry[0]); opens.append(carry[1]); highs.append(carry[2]); lows.append(carry[3]); closes.append(carry[4])
    return tuple(np.asarray(x,dtype=np.int64) for x in (buckets,opens,highs,lows,closes))

def atr_A(h,l,c):
    h=h.astype(float); l=l.astype(float); c=c.astype(float)
    pc=np.r_[np.nan,c[:-1]]
    tr=np.fmax(h-l,np.fmax(np.abs(h-pc),np.abs(l-pc)))
    cs=np.cumsum(np.nan_to_num(tr)); out=np.full(len(c),np.nan)
    out[13:]=(cs[13:]-np.r_[0.0,cs[:-14]])/14.0
    return out

@njit(cache=True)
def atr_B(h,l,c):
    n=len(c); out=np.full(n,np.nan); tr=np.empty(n,np.float64); roll=0.0
    for i in range(n):
        v=float(h[i]-l[i])
        if i>0:
            x=abs(float(h[i]-c[i-1])); y=abs(float(l[i]-c[i-1]))
            if x>v: v=x
            if y>v: v=y
        tr[i]=v; roll+=v
        if i>=14: roll-=tr[i-14]
        if i>=13: out[i]=roll/14.0
    return out

def signal_A(b,h,l,c,atr):
    pred=np.zeros(len(c),bool)
    cw=np.lib.stride_tricks.sliding_window_view(c,4)
    pred[3:]=np.all(np.diff(cw,axis=1)<0,axis=1)
    denom=np.r_[np.nan,atr[:-1]]
    ratio=np.divide(h-l,denom,out=np.full(len(c),np.nan),where=np.isfinite(denom)&(denom>0))
    weekday=((b//DAY+3)%7)<5
    close_t=b+STEP
    return pred & (ratio>=3.5) & weekday & (close_t>=STAGE_START) & (close_t<STAGE_END)

@njit(cache=True)
def signal_B(b,h,l,c,atr):
    out=np.zeros(len(c),np.bool_)
    for i in range(3,len(c)):
        ct=b[i]+STEP
        if ct<STAGE_START or ct>=STAGE_END: continue
        if ((b[i]//DAY+3)%7)>=5: continue
        d=atr[i-1]
        if not np.isfinite(d) or d<=0: continue
        if (h[i]-l[i])/d < 3.5: continue
        if not (c[i-3]>c[i-2] and c[i-2]>c[i-1] and c[i-1]>c[i]): continue
        out[i]=True
    return out

@njit(cache=True)
def lb(a,x):
    lo=0; hi=len(a)
    while lo<hi:
        m=(lo+hi)//2
        if a[m]<x: lo=m+1
        else: hi=m
    return lo

@njit(cache=True)
def potentials_A(ts,bid,ask,bucket,atr,sig_idx):
    n=len(sig_idx)
    et=np.full(n,-1,np.int64); xt=np.full(n,-1,np.int64)
    ei=np.full(n,-1,np.int64); xi=np.full(n,-1,np.int64)
    rr=np.zeros(n,np.float64); dist=np.zeros(n,np.float64)
    for q in range(n):
        bi=sig_idx[q]; sc=bucket[bi]+STEP; dl=sc+20*STEP; de=((sc//DAY)+1)*DAY
        if dl>de: dl=de
        j=lb(ts,sc)
        while j<len(ts) and ts[j]<dl and ask[j]<=bid[j]: j+=1
        if j>=len(ts) or ts[j]>=dl: continue
        entry=bid[j]; d=1.5*atr[bi]; stop=entry+d; take=entry-1.5*d
        et[q]=ts[j]; ei[q]=j; dist[q]=d
        last_exec=j; done=False; k=j
        while k<len(ts) and ts[k]<dl:
            if ask[k]>bid[k]:
                last_exec=k; px=ask[k]
                if px>=stop:
                    xi[q]=k; xt[q]=ts[k]; rr[q]=(entry-px)/d; done=True; break
                if px<=take:
                    xi[q]=k; xt[q]=ts[k]; rr[q]=(entry-px)/d; done=True; break
            k+=1
        if not done:
            xi[q]=last_exec; xt[q]=ts[last_exec]; rr[q]=(entry-ask[last_exec])/d
    return et,xt,ei,xi,rr,dist

@njit(cache=True)
def upper_ge(a,x):
    left=0; right=len(a)-1; ans=len(a)
    while left<=right:
        mid=(left+right)//2
        if a[mid]>=x:
            ans=mid; right=mid-1
        else:
            left=mid+1
    return ans

@njit(cache=True)
def potentials_B(ts,bid,ask,bucket,atr,sig_idx):
    n=len(sig_idx)
    et=np.full(n,-1,np.int64); xt=np.full(n,-1,np.int64)
    ei=np.full(n,-1,np.int64); xi=np.full(n,-1,np.int64)
    r=np.zeros(n,np.float64); ds=np.zeros(n,np.float64)
    for z in range(n):
        i=sig_idx[z]; start=bucket[i]+STEP; end=start+12_000_000; eod=((start//DAY)+1)*DAY
        if end>eod: end=eod
        p=upper_ge(ts,start)
        while p<len(ts):
            if ts[p]>=end: break
            if ask[p]>bid[p]: break
            p+=1
        if p>=len(ts) or ts[p]>=end: continue
        ep=bid[p]; d=atr[i]*3.0/2.0; ds[z]=d; sl=ep+d; tp=ep-1.5*d
        et[z]=ts[p]; ei[z]=p
        last=p
        for j in range(p,len(ts)):
            if ts[j]>=end: break
            if ask[j]<=bid[j]: continue
            last=j; px=ask[j]
            if px>=sl:
                xi[z]=j; xt[z]=ts[j]; r[z]=(ep-px)/d; break
            elif px<=tp:
                xi[z]=j; xt[z]=ts[j]; r[z]=(ep-px)/d; break
        if xt[z]<0:
            xi[z]=last; xt[z]=ts[last]; r[z]=(ep-ask[last])/d
    return et,xt,ei,xi,r,ds

@njit(cache=True)
def select_positions(et,xt):
    out=np.empty(len(et),np.int64); k=0; prev=np.int64(-1)
    for i in range(len(et)):
        if et[i]<0 or et[i]<=prev: continue
        out[k]=i; k+=1; prev=xt[i]
    return out[:k]

def pf(x):
    gp=float(x[x>0].sum()); gl=float(-x[x<0].sum())
    if gl==0: return float('inf') if gp>0 else None
    return gp/gl

def ledger(mm,pot,chosen,sig_idx,bucket):
    et,xt,ei,xi,r,d=pot
    spread_e=mm['ask'][ei[chosen]].astype(float)-mm['bid'][ei[chosen]].astype(float)
    spread_x=mm['ask'][xi[chosen]].astype(float)-mm['bid'][xi[chosen]].astype(float)
    rc=r[chosen]; dd=d[chosen]
    cons=rc-0.5*(spread_e+spread_x)/dd
    sev=rc-(spread_e+spread_x)/dd
    years=np.where(et[chosen]<YEAR2026,2025,2026)
    trades=[]; h=hashlib.sha256()
    for m,idx in enumerate(chosen):
        rec={'signal_close_ts':int(bucket[sig_idx[idx]]+STEP),'entry_ts':int(et[idx]),'exit_ts':int(xt[idx]),'entry_index_suffix':int(ei[idx]),'exit_index_suffix':int(xi[idx]),'r_central':float(rc[m]),'r_conservative':float(cons[m]),'r_severe':float(sev[m]),'distance_packed_points':float(dd[m]),'entry_spread_packed_points':float(spread_e[m]),'exit_spread_packed_points':float(spread_x[m]),'source_clock_year':int(years[m])}
        trades.append(rec)
        h.update(np.int64(rec['entry_ts']).tobytes()); h.update(np.int64(rec['exit_ts']).tobytes()); h.update(np.float64(rec['r_central']).tobytes())
    return trades,{'n':len(trades),'net_r_central':float(rc.sum()),'net_r_conservative':float(cons.sum()),'net_r_severe':float(sev.sum()),'pf_central':pf(rc),'pf_conservative':pf(cons),'pf_severe':pf(sev),'annual_net_r_central':{'2025':float(rc[years==2025].sum()),'2026':float(rc[years==2026].sum())},'ledger_sha256':h.hexdigest()}

def main():
    t=time.time(); mm=np.memmap(RAW,dtype=DT,mode='r')
    assert len(mm)==159_817_687
    ba=build_bars_A(mm['ts'],mm['bid'],mm['ask'])
    bb=build_bars_B(mm)
    assert all(np.array_equal(x,y) for x,y in zip(ba,bb)), 'BAR_PARITY_FAIL'
    b,o,h,l,c=ba
    aa=atr_A(h,l,c); ab=atr_B(h,l,c)
    assert np.allclose(aa,ab,equal_nan=True,rtol=0,atol=1e-12), 'ATR_PARITY_FAIL'
    ma=signal_A(b,h,l,c,aa); mb=signal_B(b,h,l,c,ab)
    assert np.array_equal(ma,mb), 'SIGNAL_PARITY_FAIL'
    ids=np.flatnonzero(ma).astype(np.int64)
    pa=potentials_A(mm['ts'],mm['bid'],mm['ask'],b,aa,ids)
    pb=potentials_B(mm['ts'],mm['bid'],mm['ask'],b,ab,ids)
    for x,y,name in zip(pa,pb,['entry_ts','exit_ts','entry_idx','exit_idx','r','dist']):
        if name in ('r','dist'):
            assert np.array_equal(x,y), f'POTENTIAL_{name}_PARITY_FAIL max={np.max(np.abs(x-y))}'
        else:
            assert np.array_equal(x,y), f'POTENTIAL_{name}_PARITY_FAIL'
    ca=select_positions(pa[0],pa[1]); cb=select_positions(pb[0],pb[1])
    assert np.array_equal(ca,cb), 'SELECT_PARITY_FAIL'
    trades,met=ledger(mm,pa,ca,ids,b)
    gate={'minimum_trades':10,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'net_positive_all_costs':True,'year_2025_positive':True}
    checks={'minimum_trades':met['n']>=10,'pf_central':met['pf_central'] is not None and met['pf_central']>=1.20,'pf_conservative':met['pf_conservative'] is not None and met['pf_conservative']>=1.10,'pf_severe':met['pf_severe'] is not None and met['pf_severe']>=1.00,'net_central_positive':met['net_r_central']>0,'net_conservative_positive':met['net_r_conservative']>0,'net_severe_positive':met['net_r_severe']>0,'year_2025_positive':met['annual_net_r_central']['2025']>0,'dual_parity':True}
    obj={'schema':'QROS_G30_STAGE_D_DUAL_LOCAL_v1','candidate':'G30V59C015','stable_id':'M10_MID:SELL:LAGGED_ONE_BAR_PRE_SHOCK|3.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3','source_suffix':str(RAW),'source_suffix_records':len(mm),'stage':'2025_THROUGH_2026_07_27_PARTIAL','bars':len(b),'signals_stage':len(ids),'parity_all':True,'metrics':met,'gate':gate,'checks':checks,'pass':all(checks.values()),'trades':trades,'elapsed_sec':time.time()-t}
    OUT.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    print(json.dumps({'bars':len(b),'signals':len(ids),'selected_trades':met['n'],'parity_all':True,'metrics':met,'checks':checks,'pass':obj['pass'],'elapsed_sec':obj['elapsed_sec'],'output_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()},sort_keys=True))
if __name__=='__main__': main()
