from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
import numba as nb
from qros_seed0076_structural_v220 import structural_states

TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
BUFFERS=np.array([0.0,0.05,0.10,0.25],dtype=np.float64)
TIE_NAMES=('SOURCE_ASYMMETRIC','STRICT_ALL_NEIGHBORS')

@nb.njit(cache=True)
def _lower_bound(a,n,x):
    lo=0; hi=n
    while lo<hi:
        m=(lo+hi)//2
        if a[m] < x: lo=m+1
        else: hi=m
    return lo

@nb.njit(cache=True)
def _upper_bound(a,n,x):
    lo=0; hi=n
    while lo<hi:
        m=(lo+hi)//2
        if a[m] <= x: lo=m+1
        else: hi=m
    return lo

@nb.njit(cache=True)
def _sort_pairs(vals,chans,n):
    for i in range(1,n):
        v=vals[i]; c=chans[i]; j=i-1
        while j>=0 and vals[j] > v:
            vals[j+1]=vals[j]; chans[j+1]=chans[j]; j-=1
        vals[j+1]=v; chans[j+1]=c

@nb.njit(cache=True)
def count_all(bid,first,last,up_thr,down_thr,point):
    cu=np.zeros(48,np.int64); cd=np.zeros(48,np.int64)
    uv=np.empty(48,np.float64); uc=np.empty(48,np.int32)
    dv=np.empty(48,np.float64); dc=np.empty(48,np.int32)
    for bi in range(len(first)):
        nu=0; nd=0
        for s in range(12):
            for z in range(4):
                v=up_thr[bi,s,z]
                if not np.isnan(v): uv[nu]=v; uc[nu]=s*4+z; nu+=1
                v=down_thr[bi,s,z]
                if not np.isnan(v): dv[nd]=v; dc[nd]=s*4+z; nd+=1
        _sort_pairs(uv,uc,nu); _sort_pairs(dv,dc,nd)
        sidx=first[bi]; eidx=last[bi]
        prev=bid[sidx-1]*point if sidx>0 else bid[sidx]*point
        for j in range(sidx,eidx+1):
            cur=bid[j]*point
            if cur>prev and nu:
                a=_lower_bound(uv,nu,prev); b=_lower_bound(uv,nu,cur)
                for q in range(a,b): cu[uc[q]]+=1
            elif cur<prev and nd:
                a=_upper_bound(dv,nd,cur); b=_upper_bound(dv,nd,prev)
                for q in range(a,b): cd[dc[q]]+=1
            prev=cur
    return cu,cd

@nb.njit(cache=True)
def fill_all(bid,first,last,up_thr,down_thr,up_lid,down_lid,point,cu,cd):
    uoff=np.empty(49,np.int64);doff=np.empty(49,np.int64);uoff[0]=0;doff[0]=0
    for i in range(48):uoff[i+1]=uoff[i]+cu[i];doff[i+1]=doff[i]+cd[i]
    ui=np.empty(uoff[-1],np.int64);ub=np.empty(uoff[-1],np.int32);ul=np.empty(uoff[-1],np.int64)
    di=np.empty(doff[-1],np.int64);db=np.empty(doff[-1],np.int32);dl=np.empty(doff[-1],np.int64)
    upos=uoff[:-1].copy();dpos=doff[:-1].copy()
    uv=np.empty(48,np.float64);uc=np.empty(48,np.int32);dv=np.empty(48,np.float64);dc=np.empty(48,np.int32)
    for bi in range(len(first)):
        nu=0;nd=0
        for st in range(12):
            for z in range(4):
                v=up_thr[bi,st,z]
                if not np.isnan(v):uv[nu]=v;uc[nu]=st*4+z;nu+=1
                v=down_thr[bi,st,z]
                if not np.isnan(v):dv[nd]=v;dc[nd]=st*4+z;nd+=1
        _sort_pairs(uv,uc,nu);_sort_pairs(dv,dc,nd)
        sidx=first[bi];eidx=last[bi]
        prev=bid[sidx-1]*point if sidx>0 else bid[sidx]*point
        for j in range(sidx,eidx+1):
            cur=bid[j]*point
            if cur>prev and nu:
                a=_lower_bound(uv,nu,prev);b=_lower_bound(uv,nu,cur)
                for q in range(a,b):
                    ch=uc[q];p=upos[ch];ui[p]=j;ub[p]=bi;ul[p]=up_lid[bi,ch//4];upos[ch]+=1
            elif cur<prev and nd:
                a=_upper_bound(dv,nd,cur);b=_upper_bound(dv,nd,prev)
                for q in range(a,b):
                    ch=dc[q];p=dpos[ch];di[p]=j;db[p]=bi;dl[p]=down_lid[bi,ch//4];dpos[ch]+=1
            prev=cur
    return uoff,ui,ub,ul,doff,di,db,dl

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def build(ticks_path,bars_path,ind_path,point,out_path,receipt_path):
    t0=time.time();ticks=np.memmap(ticks_path,dtype=TICK_DTYPE,mode='r');bars=np.load(bars_path,mmap_mode='r',allow_pickle=False);z=np.load(ind_path,allow_pickle=False)
    atrprev=np.r_[np.nan,z['ATR14'][:-1]]; h=bars['high_bid'].astype(np.float64)*point;l=bars['low_bid'].astype(np.float64)*point
    windows=[11,11,13,13,3,3,5,5,7,7,9,9]; ties=[0,1]*6
    up_thr=np.empty((len(bars),12,4),np.float64);down_thr=np.empty_like(up_thr);up_lid=np.empty((len(bars),12),np.int64);down_lid=np.empty_like(up_lid)
    for si,(w,tie) in enumerate(zip(windows,ties)):
        sh,sl,hid,lid=structural_states(h,l,w,tie);up_lid[:,si]=hid;down_lid[:,si]=lid
        for zz,bm in enumerate(BUFFERS):
            up_thr[:,si,zz]=sh + bm*atrprev
            down_thr[:,si,zz]=sl - bm*atrprev
            if zz>0:
                bad=np.isnan(atrprev);up_thr[bad,si,zz]=np.nan;down_thr[bad,si,zz]=np.nan
    cu,cd=count_all(ticks['bid'],bars['first_source_index'],bars['last_source_index'],up_thr,down_thr,point)
    vals=fill_all(ticks['bid'],bars['first_source_index'],bars['last_source_index'],up_thr,down_thr,up_lid,down_lid,point,cu,cd)
    uoff,ui,ub,ul,doff,di,db,dl=vals
    np.savez(out_path,windows=np.asarray(windows,np.int32),ties=np.asarray(ties,np.int8),buffers=BUFFERS,up_offsets=uoff,up_idx=ui,up_bar=ub,up_lid=ul,down_offsets=doff,down_idx=di,down_bar=db,down_lid=dl)
    rec={'schema':'QROS_SEED0076_TICK_RAW_SHARED_CACHE_1.0','status':'PASS','asset_bars':Path(bars_path).name,'ticks':Path(ticks_path).name,'point':point,'structures':12,'buffers':4,'up_event_total':int(len(ui)),'down_event_total':int(len(di)),'channel_counts_up':cu.tolist(),'channel_counts_down':cd.tolist(),'cache_bytes':Path(out_path).stat().st_size,'cache_sha256':sha256_file(out_path),'elapsed_seconds':round(time.time()-t0,6),'economic_pnl_read':False,'holdout_open':False}
    Path(receipt_path).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps(rec))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ticks',required=True);ap.add_argument('--bars',required=True);ap.add_argument('--ind',required=True);ap.add_argument('--point',type=float,required=True);ap.add_argument('--out',required=True);ap.add_argument('--receipt',required=True);a=ap.parse_args();build(a.ticks,a.bars,a.ind,a.point,a.out,a.receipt)
if __name__=='__main__':main()
