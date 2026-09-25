from __future__ import annotations
import numpy as np, numba as nb

@nb.njit(cache=True)
def structural_states(high,low,window,tie_code):
    n=len(high);k=window//2
    sh=np.empty(n,np.float64);sl=np.empty(n,np.float64);hid=np.empty(n,np.int64);lid=np.empty(n,np.int64)
    sh[:]=np.nan;sl[:]=np.nan;hid[:]=-1;lid[:]=-1
    last_h=np.nan;last_l=np.nan;last_hi=-1;last_li=-1
    # state at start of bar i includes confirmations through i-1
    for i in range(1,n):
        t=i-1
        if t>=window-1:
            p=t-k;okh=True;okl=True
            for q in range(t-window+1,t+1):
                if q==p: continue
                if tie_code==0: # source asymmetric: >= older, > newer high; <= older, < newer low
                    if q<p:
                        if high[p] < high[q]: okh=False
                        if low[p] > low[q]: okl=False
                    else:
                        if high[p] <= high[q]: okh=False
                        if low[p] >= low[q]: okl=False
                else:
                    if high[p] <= high[q]: okh=False
                    if low[p] >= low[q]: okl=False
            if okh: last_h=high[p];last_hi=p
            if okl: last_l=low[p];last_li=p
        sh[i]=last_h;sl[i]=last_l;hid[i]=last_hi;lid[i]=last_li
    return sh,sl,hid,lid

@nb.njit(cache=True)
def box_history4(sh,sl,hid,lid):
    n=len(sh);out=np.empty((n,4),np.float64);out[:]=np.nan
    hist=np.empty(4,np.float64);hist[:]=np.nan;have=0;prev_h=-2;prev_l=-2
    for i in range(n):
        if hid[i]>=0 and lid[i]>=0:
            changed=(hid[i]!=prev_h or lid[i]!=prev_l)
            if changed:
                w=abs(sh[i]-sl[i])
                if have<4:
                    hist[have]=w;have+=1
                else:
                    hist[0]=hist[1];hist[1]=hist[2];hist[2]=hist[3];hist[3]=w
                prev_h=hid[i];prev_l=lid[i]
            # newest right aligned
            for j in range(4): out[i,j]=np.nan
            for j in range(have): out[i,4-have+j]=hist[j]
    return out

@nb.njit(cache=True)
def _count_tick_crosses_four(bid,first,last,bar_high,bar_low,level,atr_prev,side,point,buffers):
    counts=np.zeros(4,np.int64)
    for i in range(len(first)):
        lv=level[i];a=atr_prev[i]
        if np.isnan(lv):continue
        th=np.empty(4,np.float64)
        for z in range(4):
            if z>0 and np.isnan(a): th[z]=np.nan
            else: th[z]=lv + (buffers[z]*a if side==1 else -buffers[z]*a)
        # skip bar if impossible for every valid threshold
        possible=False
        for z in range(4):
            if np.isnan(th[z]):continue
            if (side==1 and bar_high[i]>th[z]) or (side==-1 and bar_low[i]<th[z]):possible=True;break
        if not possible:continue
        s=first[i];e=last[i];prev=bid[s-1]*point if s>0 else bid[s]*point
        for j in range(s,e+1):
            cur=bid[j]*point
            if side==1:
                if cur>prev:
                    for z in range(4):
                        if not np.isnan(th[z]) and prev<=th[z] and cur>th[z]:counts[z]+=1
            else:
                if cur<prev:
                    for z in range(4):
                        if not np.isnan(th[z]) and prev>=th[z] and cur<th[z]:counts[z]+=1
            prev=cur
    return counts

@nb.njit(cache=True)
def _fill_tick_crosses_four(bid,first,last,bar_high,bar_low,level,level_id,atr_prev,side,point,buffers,counts):
    o0=np.empty(counts[0],np.int64);o1=np.empty(counts[1],np.int64);o2=np.empty(counts[2],np.int64);o3=np.empty(counts[3],np.int64)
    b0=np.empty(counts[0],np.int32);b1=np.empty(counts[1],np.int32);b2=np.empty(counts[2],np.int32);b3=np.empty(counts[3],np.int32)
    l0=np.empty(counts[0],np.int64);l1=np.empty(counts[1],np.int64);l2=np.empty(counts[2],np.int64);l3=np.empty(counts[3],np.int64)
    pos=np.zeros(4,np.int64)
    for i in range(len(first)):
        lv=level[i];a=atr_prev[i]
        if np.isnan(lv):continue
        th=np.empty(4,np.float64)
        for z in range(4): th[z]=np.nan if (z>0 and np.isnan(a)) else lv+(buffers[z]*a if side==1 else -buffers[z]*a)
        possible=False
        for z in range(4):
            if np.isnan(th[z]):continue
            if (side==1 and bar_high[i]>th[z]) or (side==-1 and bar_low[i]<th[z]):possible=True;break
        if not possible:continue
        s=first[i];e=last[i];prev=bid[s-1]*point if s>0 else bid[s]*point
        for j in range(s,e+1):
            cur=bid[j]*point
            if side==1 and cur>prev:
                for z in range(4):
                    if not np.isnan(th[z]) and prev<=th[z] and cur>th[z]:
                        p=pos[z]
                        if z==0:o0[p]=j;b0[p]=i;l0[p]=level_id[i]
                        elif z==1:o1[p]=j;b1[p]=i;l1[p]=level_id[i]
                        elif z==2:o2[p]=j;b2[p]=i;l2[p]=level_id[i]
                        else:o3[p]=j;b3[p]=i;l3[p]=level_id[i]
                        pos[z]+=1
            elif side==-1 and cur<prev:
                for z in range(4):
                    if not np.isnan(th[z]) and prev>=th[z] and cur<th[z]:
                        p=pos[z]
                        if z==0:o0[p]=j;b0[p]=i;l0[p]=level_id[i]
                        elif z==1:o1[p]=j;b1[p]=i;l1[p]=level_id[i]
                        elif z==2:o2[p]=j;b2[p]=i;l2[p]=level_id[i]
                        else:o3[p]=j;b3[p]=i;l3[p]=level_id[i]
                        pos[z]+=1
            prev=cur
    return (o0,b0,l0,o1,b1,l1,o2,b2,l2,o3,b3,l3)

def raw_tick_crosses_four(bid,first,last,bar_high,bar_low,level,level_id,atr_prev,side,point,buffers=np.array([0,.05,.10,.25])):
    counts=_count_tick_crosses_four(bid,first,last,bar_high,bar_low,level,atr_prev,side,point,buffers)
    vals=_fill_tick_crosses_four(bid,first,last,bar_high,bar_low,level,level_id,atr_prev,side,point,buffers,counts)
    return counts,[(vals[i*3],vals[i*3+1],vals[i*3+2]) for i in range(4)]

@nb.njit(cache=True)
def next_replacement_source(level_id, first_source):
    n=len(level_id); out=np.empty(n,np.int64); out[:]=-1
    i=0
    while i<n:
        lid=level_id[i]; j=i+1
        while j<n and level_id[j]==lid: j+=1
        nxt=first_source[j] if j<n else -1
        for q in range(i,j): out[q]=nxt
        i=j
    return out

@nb.njit(cache=True)
def _find_first_return(bid, valid_quote, first, last, bar_low, bar_high, start_idx, start_bar, stop_idx, level, side, point):
    nbar=len(first)
    for bi in range(start_bar,nbar):
        s=first[bi];e=last[bi]
        if e<=start_idx: continue
        if stop_idx>=0 and s>=stop_idx: return -1
        if side==1:
            if bar_low[bi]>level: continue
        else:
            if bar_high[bi]<level: continue
        j=max(s,start_idx+1); je=e if stop_idx<0 else min(e,stop_idx-1)
        for k in range(j,je+1):
            if valid_quote[k]==0: continue
            p=bid[k]*point
            if (side==1 and p<=level) or (side==-1 and p>=level): return k
    return -1

@nb.njit(cache=True)
def _find_touch_reclaim(bid,first,last,bar_low,bar_high,start_idx,start_bar,end_bar_exclusive,cancel_idx,thr,side,point):
    touched=False; touch_idx=-1
    nbar=min(end_bar_exclusive,len(first))
    for bi in range(start_bar,nbar):
        s=first[bi];e=last[bi]
        if cancel_idx>=0 and s>=cancel_idx:return -1
        j=max(s,start_idx+1) if bi==start_bar else s
        je=e if cancel_idx<0 else min(e,cancel_idx-1)
        if j>je: continue
        if not touched:
            if side==1 and bar_low[bi]>thr: continue
            if side==-1 and bar_high[bi]<thr: continue
            for k in range(j,je+1):
                p=bid[k]*point
                if (side==1 and p<=thr) or (side==-1 and p>=thr): touched=True;touch_idx=k;j=k+1;break
            if not touched: continue
        # seek reclaim after touch
        if side==1 and bar_high[bi]<=thr: continue
        if side==-1 and bar_low[bi]>=thr: continue
        for k in range(j,je+1):
            p=bid[k]*point
            if (side==1 and p>thr) or (side==-1 and p<thr): return k
    return -1

@nb.njit(cache=True)
def _find_close_reclaim(bid,valid_quote,first,last,first_executable,bar_low,bar_high,bar_close,start_idx,start_bar,end_bar_exclusive,cancel_idx,thr,side,point,level_id):
    nbar=min(end_bar_exclusive,len(first)-1) # need next bar first tick for availability
    current_level=level_id[start_bar]
    for bi in range(start_bar,nbar):
        avail=first_executable[bi+1]
        if cancel_idx>=0 and avail>=cancel_idx:return -1
        # structural replacement at this availability cancels before reclaim
        if level_id[bi+1]!=current_level:return -1
        touched=False
        if bi==start_bar:
            j=max(first[bi],start_idx+1);e=last[bi]
            if j<=e:
                for k in range(j,e+1):
                    if valid_quote[k]==0: continue
                    p=bid[k]*point
                    if (side==1 and p<=thr) or (side==-1 and p>=thr): touched=True;break
        else:
            touched=(bar_low[bi]<=thr) if side==1 else (bar_high[bi]>=thr)
        if touched:
            if (side==1 and bar_close[bi]>thr) or (side==-1 and bar_close[bi]<thr): return avail
    return -1

@nb.njit(cache=True)
def filter_raw_to_candidates(bid,valid_quote,first,last,first_executable,bar_low,bar_high,bar_close,level,level_id,next_repl,atr_prev,raw_idx,raw_bar,raw_lid,opp_idx,side,point,buffer_mult,rearm_code,retest_code,retest_window):
    # rearm_code:0 return_inside_or_replaced,1 level_replaced_only,2 one_signal_per_level
    # V27 provenance-only fix: CLOSE_RECLAIM availability is the first actually executable quote of the next quote-valid M1 bar. Original V220 source frozen separately.
    # retest_code:0 off,1 touch,2 close
    out=np.empty(len(raw_idx),np.int64);out_bar=np.empty(len(raw_idx),np.int32);n=0
    consumed_id=-999999; allowed_after=-1; pending_block_until=-1
    opp_pos=0
    for z in range(len(raw_idx)):
        ri=raw_idx[z];bi=raw_bar[z];lid=raw_lid[z]
        if pending_block_until>=0 and ri<pending_block_until: continue
        if rearm_code==0:
            if allowed_after>=0 and ri<allowed_after and lid==consumed_id: continue
        else:
            if lid==consumed_id: continue
        # threshold known at breakout bar start
        a=atr_prev[bi]
        if buffer_mult!=0.0 and np.isnan(a): continue
        thr=level[bi]+(buffer_mult*a if side==1 else -buffer_mult*a)
        if np.isnan(thr): continue
        final_idx=ri;final_bar=bi
        if retest_code!=0:
            rep=next_repl[bi]
            while opp_pos<len(opp_idx) and opp_idx[opp_pos]<=ri: opp_pos+=1
            opp=opp_idx[opp_pos] if opp_pos<len(opp_idx) else -1
            cancel=-1
            if rep>=0:cancel=rep
            if opp>=0 and (cancel<0 or opp<cancel):cancel=opp
            endbar=min(len(first),bi+retest_window)
            if retest_code==1:
                final_idx=_find_touch_reclaim(bid,first,last,bar_low,bar_high,ri,bi,endbar,cancel,thr,side,point)
            else:
                final_idx=_find_close_reclaim(bid,valid_quote,first,last,first_executable,bar_low,bar_high,bar_close,ri,bi,endbar,cancel,thr,side,point,level_id)
            if final_idx<0:
                # Pending blocks same-level new breakouts until earliest cancel or window expiry.
                expiry=first[endbar] if endbar<len(first) else last[-1]+1
                pending_block_until=expiry
                if cancel>=0 and cancel<pending_block_until:pending_block_until=cancel
                continue
            # map final source index to bar by monotonic first-source indices; windows <=5 => small scan
            fb=bi
            while fb+1<len(first) and first[fb+1]<=final_idx:fb+=1
            final_bar=fb
            pending_block_until=-1
        out[n]=final_idx;out_bar[n]=final_bar;n+=1
        consumed_id=lid
        if rearm_code==0:
            rep=next_repl[final_bar]
            ret=_find_first_return(bid,valid_quote,first,last,bar_low,bar_high,final_idx,final_bar,rep,level[bi],side,point)
            if ret>=0 and rep>=0:allowed_after=min(ret,rep)
            elif ret>=0:allowed_after=ret
            elif rep>=0:allowed_after=rep
            else:allowed_after=last[-1]+1
        else:
            allowed_after=-1
    return out[:n],out_bar[:n]

@nb.njit(cache=True)
def raw_close_crosses_four(first,close,level_start,level_id_start,atr,side,buffers=np.array([0.0,.05,.10,.25])):
    # completed bar t is evaluated after structural update from t; availability is first tick of t+1.
    counts=np.zeros(4,np.int64)
    n=len(close)
    for t in range(1,n-1):
        bi=t+1;lv=level_start[bi];a=atr[t]
        if np.isnan(lv):continue
        prev=close[t-1];cur=close[t]
        for z in range(4):
            if z>0 and np.isnan(a):continue
            th=lv+(buffers[z]*a if side==1 else -buffers[z]*a)
            if (side==1 and prev<=th and cur>th) or (side==-1 and prev>=th and cur<th):counts[z]+=1
    outs=[np.empty(counts[z],np.int64) for z in range(4)];bars=[np.empty(counts[z],np.int32) for z in range(4)];lids=[np.empty(counts[z],np.int64) for z in range(4)];pos=np.zeros(4,np.int64)
    for t in range(1,n-1):
        bi=t+1;lv=level_start[bi];a=atr[t]
        if np.isnan(lv):continue
        prev=close[t-1];cur=close[t]
        for z in range(4):
            if z>0 and np.isnan(a):continue
            th=lv+(buffers[z]*a if side==1 else -buffers[z]*a)
            if (side==1 and prev<=th and cur>th) or (side==-1 and prev>=th and cur<th):
                p=pos[z];outs[z][p]=first[bi];bars[z][p]=bi;lids[z][p]=level_id_start[bi];pos[z]+=1
    return counts,outs,bars,lids
