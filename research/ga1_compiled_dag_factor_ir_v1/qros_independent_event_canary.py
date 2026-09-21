from __future__ import annotations
import numpy as np

# Deliberately scalar and dependency-free reference implementation.
def structural_states_scalar(high,low,window,tie_code):
    high=np.asarray(high,float);low=np.asarray(low,float);n=len(high);k=window//2
    sh=np.full(n,np.nan);sl=np.full(n,np.nan);hid=np.full(n,-1,dtype=np.int64);lid=np.full(n,-1,dtype=np.int64)
    last_h=np.nan;last_l=np.nan;last_hi=-1;last_li=-1
    for i in range(1,n):
        t=i-1
        if t>=window-1:
            p=t-k;okh=True;okl=True
            for q in range(t-window+1,t+1):
                if q==p:continue
                if tie_code==0:
                    if q<p:
                        okh &= high[p]>=high[q];okl &= low[p]<=low[q]
                    else:
                        okh &= high[p]>high[q];okl &= low[p]<low[q]
                else:
                    okh &= high[p]>high[q];okl &= low[p]<low[q]
            if okh:last_h=high[p];last_hi=p
            if okl:last_l=low[p];last_li=p
        sh[i]=last_h;sl[i]=last_l;hid[i]=last_hi;lid[i]=last_li
    return sh,sl,hid,lid

# Alternate implementation: evaluate every center once at its causal availability.
def structural_states_by_centers(high,low,window,tie_code):
    high=np.asarray(high,float);low=np.asarray(low,float);n=len(high);k=window//2
    hconf={};lconf={}
    for p in range(k,n-k):
        qs=[q for q in range(p-k,p+k+1) if q!=p]
        if tie_code==0:
            okh=all((high[p]>=high[q] if q<p else high[p]>high[q]) for q in qs)
            okl=all((low[p]<=low[q] if q<p else low[p]<low[q]) for q in qs)
        else:
            okh=all(high[p]>high[q] for q in qs);okl=all(low[p]<low[q] for q in qs)
        availability=p+k+1
        if availability<n:
            if okh:hconf[availability]=(p,high[p])
            if okl:lconf[availability]=(p,low[p])
    sh=np.full(n,np.nan);sl=np.full(n,np.nan);hid=np.full(n,-1,dtype=np.int64);lid=np.full(n,-1,dtype=np.int64)
    lh=np.nan;ll=np.nan;lhi=-1;lli=-1
    for i in range(n):
        if i in hconf:lhi,lh=hconf[i]
        if i in lconf:lli,ll=lconf[i]
        sh[i]=lh;sl[i]=ll;hid[i]=lhi;lid[i]=lli
    return sh,sl,hid,lid

def tick_crosses_scalar(bid,first,last,bar_high,bar_low,level,level_id,atr_prev,side,point,buffers=(0.,.05,.10,.25)):
    bid=np.asarray(bid);outs=[[] for _ in buffers]
    for bi in range(len(first)):
        lv=level[bi];a=atr_prev[bi]
        if np.isnan(lv):continue
        th=[np.nan if (z>0 and np.isnan(a)) else lv+(buffers[z]*a if side==1 else -buffers[z]*a) for z in range(len(buffers))]
        possible=any((side==1 and bar_high[bi]>x) or (side==-1 and bar_low[bi]<x) for x in th if not np.isnan(x))
        if not possible:continue
        s=int(first[bi]);e=int(last[bi]);prev=bid[s-1]*point if s>0 else bid[s]*point
        for j in range(s,e+1):
            cur=bid[j]*point
            for z,x in enumerate(th):
                if np.isnan(x):continue
                crossed=(side==1 and cur>prev and prev<=x and cur>x) or (side==-1 and cur<prev and prev>=x and cur<x)
                if crossed:outs[z].append((j,bi,int(level_id[bi])))
            prev=cur
    return outs

def tick_crosses_alt(bid,first,last,bar_high,bar_low,level,level_id,atr_prev,side,point,buffers=(0.,.05,.10,.25)):
    bid=np.asarray(bid);outs=[]
    for z,bm in enumerate(buffers):
        channel=[]
        for bi,(s,e) in enumerate(zip(first,last)):
            lv=level[bi];a=atr_prev[bi]
            if np.isnan(lv) or (z>0 and np.isnan(a)):continue
            th=lv+(bm*a if side==1 else -bm*a)
            if side==1 and not (bar_high[bi]>th):continue
            if side==-1 and not (bar_low[bi]<th):continue
            s=int(s);e=int(e);prev=bid[s-1]*point if s>0 else bid[s]*point
            for j in range(s,e+1):
                cur=bid[j]*point
                if (side==1 and cur>prev and prev<=th and cur>th) or (side==-1 and cur<prev and prev>=th and cur<th):channel.append((j,bi,int(level_id[bi])))
                prev=cur
        outs.append(channel)
    return outs
