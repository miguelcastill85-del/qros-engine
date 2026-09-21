from __future__ import annotations
import numpy as np

REARM_CODES = {
    "RETURN_INSIDE_OR_LEVEL_REPLACED": 0,
    "LEVEL_REPLACED_ONLY": 1,
    "ONE_SIGNAL_PER_LEVEL": 2,
}
TRANSFORMS = (
    ("OFF", 0, 0),
    ("TOUCH_RECLAIM_W1", 1, 1),
    ("TOUCH_RECLAIM_W3", 1, 3),
    ("TOUCH_RECLAIM_W5", 1, 5),
    ("CLOSE_RECLAIM_W1", 2, 1),
    ("CLOSE_RECLAIM_W3", 2, 3),
    ("CLOSE_RECLAIM_W5", 2, 5),
)

def _bar_for(first, idx, start=0):
    return max(start, int(np.searchsorted(first, idx, side="right") - 1))

def next_replacement_source_scalar(level_id, first):
    out = np.full(len(level_id), -1, dtype=np.int64)
    for i in range(len(level_id)):
        j=i+1
        while j < len(level_id) and level_id[j] == level_id[i]:
            j += 1
        if j < len(level_id):
            out[i] = int(first[j])
    return out

def raw_breaks(fx, side, buffer_mult, trigger):
    point=fx["point"]; first=fx["first"]; last=fx["last"]; bid=fx["bid"]
    level=fx["level"]; lid=fx["level_id"]; atr=fx["atr_prev"]
    rows=[]
    if trigger == "TICK_BREAK":
        for bi,(s,e) in enumerate(zip(first,last)):
            if buffer_mult and np.isnan(atr[bi]): continue
            th=level[bi]+(buffer_mult*atr[bi] if side==1 else -buffer_mult*atr[bi])
            prev=bid[s-1]*point if s>0 else bid[s]*point
            for k in range(int(s),int(e)+1):
                cur=bid[k]*point
                cross=(side==1 and cur>prev and prev<=th and cur>th) or (side==-1 and cur<prev and prev>=th and cur<th)
                if cross: rows.append((k,bi,int(lid[bi])))
                prev=cur
    elif trigger == "CLOSE_BREAK":
        c=fx["bar_close"]
        for t in range(1,len(c)-1):
            bi=t+1
            if buffer_mult and np.isnan(atr[bi]): continue
            th=level[bi]+(buffer_mult*atr[bi] if side==1 else -buffer_mult*atr[bi])
            cross=(side==1 and c[t-1]<=th and c[t]>th) or (side==-1 and c[t-1]>=th and c[t]<th)
            if cross: rows.append((int(first[bi]),bi,int(lid[bi])))
    else:
        raise ValueError("TRIGGER_INVALID")
    return rows

def _first_return(fx,start_idx,start_bar,stop_idx,boundary,side):
    for k in range(start_idx+1,len(fx["bid"])):
        if stop_idx>=0 and k>=stop_idx:return -1
        bi=_bar_for(fx["first"],k,start_bar)
        if bi>=len(fx["last"]) or k>fx["last"][bi]:continue
        p=fx["bid"][k]*fx["point"]
        if (side==1 and p<=boundary) or (side==-1 and p>=boundary):return k
    return -1

def _touch_reclaim(fx,start_idx,start_bar,endbar,cancel,thr,side):
    first=fx["first"];last=fx["last"];bid=fx["bid"];point=fx["point"]
    end_idx=int(first[endbar]) if endbar<len(first) else int(last[-1]+1)
    stop=min(end_idx,cancel if cancel>=0 else end_idx)
    touched=False
    for k in range(start_idx+1,min(stop,len(bid))):
        if _bar_for(first,k,start_bar)>=endbar:break
        p=bid[k]*point
        if not touched:
            if (side==1 and p<=thr) or (side==-1 and p>=thr):touched=True
        elif (side==1 and p>thr) or (side==-1 and p<thr):
            return k
    return -1

def _close_reclaim(fx,start_idx,start_bar,endbar,cancel,thr,side):
    first=fx["first"];last=fx["last"];bid=fx["bid"];point=fx["point"];lid=fx["level_id"]
    current=lid[start_bar]
    for bi in range(start_bar,min(endbar,len(first)-1)):
        avail=int(first[bi+1])
        if cancel>=0 and avail>=cancel:return -1
        if lid[bi+1]!=current:return -1
        if bi==start_bar:
            vals=bid[max(int(first[bi]),start_idx+1):int(last[bi])+1]*point
            touched=bool(len(vals) and (np.min(vals)<=thr if side==1 else np.max(vals)>=thr))
        else:
            touched=bool(fx["bar_low"][bi]<=thr if side==1 else fx["bar_high"][bi]>=thr)
        if touched and ((side==1 and fx["bar_close"][bi]>thr) or (side==-1 and fx["bar_close"][bi]<thr)):
            return avail
    return -1

def oracle_filter(fx,raw_idx,raw_bar,raw_lid,opp_idx,side,buffer_mult,rearm_code,retest_code,retest_window,trace=False):
    out=[];bars=[];last_consumed=None;eligible_at=-1;blocked_until=-1
    opp=list(map(int,opp_idx))
    tr={k:0 for k in ("raw","pending_skip","rearm_skip","touch_success","close_success","retest_fail","cancel_replacement","cancel_opposite","return_rearm","replacement_rearm","accepted")}
    for ri,bi,lid in zip(map(int,raw_idx),map(int,raw_bar),map(int,raw_lid)):
        tr["raw"]+=1
        if blocked_until>=0 and ri<blocked_until:
            tr["pending_skip"]+=1;continue
        if last_consumed==lid:
            if rearm_code==0 and eligible_at>=0 and ri<eligible_at:
                tr["rearm_skip"]+=1;continue
            if rearm_code in (1,2):
                tr["rearm_skip"]+=1;continue
        a=fx["atr_prev"][bi]
        if buffer_mult and np.isnan(a):continue
        thr=fx["level"][bi]+(buffer_mult*a if side==1 else -buffer_mult*a)
        if np.isnan(thr):continue
        final=ri;fb=bi
        if retest_code:
            replacement=int(fx["next_repl"][bi])
            future_opp=next((x for x in opp if x>ri),-1)
            cuts=[x for x in (replacement,future_opp) if x>=0]
            cancel=min(cuts) if cuts else -1
            if cancel==replacement and replacement>=0:tr["cancel_replacement"]+=1
            if cancel==future_opp and future_opp>=0:tr["cancel_opposite"]+=1
            endbar=min(len(fx["first"]),bi+retest_window)
            final=_touch_reclaim(fx,ri,bi,endbar,cancel,thr,side) if retest_code==1 else _close_reclaim(fx,ri,bi,endbar,cancel,thr,side)
            if final<0:
                tr["retest_fail"]+=1
                expiry=int(fx["first"][endbar]) if endbar<len(fx["first"]) else int(fx["last"][-1]+1)
                blocked_until=min(x for x in (expiry,cancel) if x>=0)
                continue
            tr["touch_success" if retest_code==1 else "close_success"]+=1
            fb=_bar_for(fx["first"],final,bi);blocked_until=-1
        out.append(final);bars.append(fb);tr["accepted"]+=1;last_consumed=lid
        if rearm_code==0:
            replacement=int(fx["next_repl"][fb])
            ret=_first_return(fx,final,fb,replacement,float(fx["level"][bi]),side)
            if ret>=0:tr["return_rearm"]+=1
            if replacement>=0:tr["replacement_rearm"]+=1
            options=[x for x in (ret,replacement) if x>=0]
            eligible_at=min(options) if options else int(fx["last"][-1]+1)
        else:
            eligible_at=-1
    result=(np.asarray(out,dtype=np.int64),np.asarray(bars,dtype=np.int32))
    return result+(tr,) if trace else result

def make_fixture(seed=7600763,nb=40,per=8):
    rng=np.random.default_rng(seed)
    first=np.arange(nb,dtype=np.int64)*per;last=first+per-1
    level=(100.0+np.sin(np.arange(nb)*0.7)*0.25).astype(np.float64)
    level_id=np.repeat(np.arange((nb+5)//6,dtype=np.int64)+100,6)[:nb]
    point=0.01;bid=np.empty(nb*per,dtype=np.int64)
    pattern=np.array([-3,-1,2,4,-2,-4,1,3],dtype=np.int64)
    for bi in range(nb):
        center=int(round(level[bi]/point))
        bid[bi*per:(bi+1)*per]=center+pattern+rng.integers(-1,2,per,dtype=np.int64)
    bar_low=np.array([bid[s:e+1].min()*point for s,e in zip(first,last)])
    bar_high=np.array([bid[s:e+1].max()*point for s,e in zip(first,last)])
    bar_close=np.array([bid[e]*point for e in last])
    atr_prev=np.full(nb,0.12,dtype=np.float64)
    next_repl=next_replacement_source_scalar(level_id,first)
    return {"bid":bid,"first":first,"last":last,"bar_low":bar_low,"bar_high":bar_high,"bar_close":bar_close,"level":level,"level_id":level_id,"atr_prev":atr_prev,"next_repl":next_repl,"point":point}

def perturb_after(fx,cutoff):
    out={k:(v.copy() if isinstance(v,np.ndarray) else v) for k,v in fx.items()}
    idx=np.arange(cutoff+1,len(out["bid"]))
    if len(idx):
        out["bid"][idx]+=np.where(np.arange(len(idx))%2==0,37,-31).astype(np.int64)
    out["bar_low"]=np.array([out["bid"][s:e+1].min()*out["point"] for s,e in zip(out["first"],out["last"])])
    out["bar_high"]=np.array([out["bid"][s:e+1].max()*out["point"] for s,e in zip(out["first"],out["last"])])
    out["bar_close"]=np.array([out["bid"][e]*out["point"] for e in out["last"]])
    return out
