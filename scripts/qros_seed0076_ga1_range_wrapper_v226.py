from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import numba as nb

V225_PATH=Path('/mnt/data/qros_v220/qros_seed0076_ga1_cached_wrapper_v225.py')
s=importlib.util.spec_from_file_location('qros_v225',V225_PATH);v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
w=v.w
RANGE=None; BID=None; POINT=None

@nb.njit(cache=True)
def _first_query(bid,bmin,bmax,bs,lo,hi,thr,point,mode):
    n=len(bid)
    if lo<0:lo=0
    if hi>=n:hi=n-1
    if lo>hi:return -1
    while lo<=hi and lo%bs!=0:
        x=bid[lo]*point
        if (mode==0 and x<=thr) or (mode==1 and x>=thr) or (mode==2 and x<thr) or (mode==3 and x>thr):return lo
        lo+=1
    while lo+bs-1<=hi:
        b=lo//bs
        possible=(bmin[b]*point<=thr) if mode==0 else ((bmax[b]*point>=thr) if mode==1 else ((bmin[b]*point<thr) if mode==2 else (bmax[b]*point>thr)))
        if possible:
            end=lo+bs
            for j in range(lo,end):
                x=bid[j]*point
                if (mode==0 and x<=thr) or (mode==1 and x>=thr) or (mode==2 and x<thr) or (mode==3 and x>thr):return j
        lo+=bs
    while lo<=hi:
        x=bid[lo]*point
        if (mode==0 and x<=thr) or (mode==1 and x>=thr) or (mode==2 and x<thr) or (mode==3 and x>thr):return lo
        lo+=1
    return -1

@nb.njit(cache=True)
def _fast_filter(bid,bmin,bmax,bs,first,last,bar_low,bar_high,bar_close,level,level_id,next_repl,atr_prev,raw_idx,raw_bar,raw_lid,opp_idx,side,point,buffer_mult,rearm_code,retest_code,retest_window):
    out=np.empty(len(raw_idx),np.int64);out_bar=np.empty(len(raw_idx),np.int32);n=0
    consumed_id=-999999;allowed_after=-1;pending_block_until=-1;opp_pos=0
    for z in range(len(raw_idx)):
        ri=raw_idx[z];bi=raw_bar[z];lid=raw_lid[z]
        if pending_block_until>=0 and ri<pending_block_until:continue
        if rearm_code==0:
            if allowed_after>=0 and ri<allowed_after and lid==consumed_id:continue
        else:
            if lid==consumed_id:continue
        a=atr_prev[bi]
        if buffer_mult!=0.0 and np.isnan(a):continue
        thr=level[bi]+(buffer_mult*a if side==1 else -buffer_mult*a)
        if np.isnan(thr):continue
        final_idx=ri;final_bar=bi
        if retest_code!=0:
            rep=next_repl[bi]
            while opp_pos<len(opp_idx) and opp_idx[opp_pos]<=ri:opp_pos+=1
            opp=opp_idx[opp_pos] if opp_pos<len(opp_idx) else -1
            cancel=-1
            if rep>=0:cancel=rep
            if opp>=0 and (cancel<0 or opp<cancel):cancel=opp
            endbar=min(len(first),bi+retest_window)
            if retest_code==1:
                if endbar<=bi:final_idx=-1
                else:
                    hi=last[endbar-1]
                    if cancel>=0 and cancel-1<hi:hi=cancel-1
                    touch=_first_query(bid,bmin,bmax,bs,ri+1,hi,thr,point,0 if side==1 else 1)
                    if touch<0:final_idx=-1
                    else:final_idx=_first_query(bid,bmin,bmax,bs,touch+1,hi,thr,point,3 if side==1 else 2)
            else:
                nbar=min(endbar,len(first)-1);current_level=level_id[bi];final_idx=-1
                for bj in range(bi,nbar):
                    avail=first[bj+1]
                    if cancel>=0 and avail>=cancel:break
                    if level_id[bj+1]!=current_level:break
                    touched=False
                    if bj==bi:
                        touched=_first_query(bid,bmin,bmax,bs,ri+1,last[bj],thr,point,0 if side==1 else 1)>=0
                    else:
                        touched=(bar_low[bj]<=thr) if side==1 else (bar_high[bj]>=thr)
                    if touched and ((side==1 and bar_close[bj]>thr) or (side==-1 and bar_close[bj]<thr)):
                        final_idx=avail;break
            if final_idx<0:
                expiry=first[endbar] if endbar<len(first) else last[-1]+1
                pending_block_until=expiry
                if cancel>=0 and cancel<pending_block_until:pending_block_until=cancel
                continue
            fb=bi
            while fb+1<len(first) and first[fb+1]<=final_idx:fb+=1
            final_bar=fb;pending_block_until=-1
        out[n]=final_idx;out_bar[n]=final_bar;n+=1;consumed_id=lid
        if rearm_code==0:
            rep=next_repl[final_bar];hi=(rep-1) if rep>=0 else last[-1]
            ret=_first_query(bid,bmin,bmax,bs,final_idx+1,hi,level[bi],point,0 if side==1 else 1)
            if ret>=0 and rep>=0:allowed_after=min(ret,rep)
            elif ret>=0:allowed_after=ret
            elif rep>=0:allowed_after=rep
            else:allowed_after=last[-1]+1
        else:allowed_after=-1
    return out[:n],out_bar[:n]

def patched_filter(bid,first,last,bar_low,bar_high,bar_close,level,level_id,next_repl,atr_prev,raw_idx,raw_bar,raw_lid,opp_idx,side,point,buffer_mult,rearm_code,retest_code,retest_window):
    return _fast_filter(bid,RANGE['block_min'],RANGE['block_max'],int(RANGE['block_size'][0]),first,last,bar_low,bar_high,bar_close,level,level_id,next_repl,atr_prev,raw_idx,raw_bar,raw_lid,opp_idx,side,point,buffer_mult,rearm_code,retest_code,retest_window)

def main():
    global RANGE
    ap=argparse.ArgumentParser();ap.add_argument('--tick-range-index',required=True);ap.add_argument('--tick-raw-cache',required=True);ap.add_argument('--shard-json',required=True);ap.add_argument('--spec',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--ticks',required=True);ap.add_argument('--bar-root',required=True);ap.add_argument('--ind-root',required=True);ap.add_argument('--point',type=float,required=True);ap.add_argument('--expected-config-root');ap.add_argument('--only-group-index',type=int)
    a=ap.parse_args();RANGE=np.load(a.tick_range_index,mmap_mode='r',allow_pickle=False);v.CACHE=np.load(a.tick_raw_cache,mmap_mode='r',allow_pickle=False);w.build_structural_cache=v.patched_build;w.raw_cache_for=v.patched_raw;w.filter_raw_to_candidates=patched_filter
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);shard=json.loads(Path(a.shard_json).read_text());d=shard['descriptor']
    res=w.process(shard,a.spec,a.ticks,a.bar_root,a.ind_root,a.point,out,a.expected_config_root,None,a.only_group_index);expected=33528 if a.only_group_index is not None else d['signal_configs'];status='PASS' if res['input_config_count']==expected else 'FAIL'
    receipt={'schema':'QROS_SEED0076_GA1_SHARD_WORKER_RECEIPT_1.0','status':status,'shard_id':shard['shard_id'],'descriptor_sha256':shard['descriptor_sha256'],'domain':{'asset':d['asset'],'side':d['side'],'timeframe':d['timeframe']},'processed_signal_configs':res['input_config_count'],'distinct_mask_class_count':res['distinct_mask_class_count'],'duplicate_config_count':res['duplicate_config_count'],'zero_event_class_alias_count':res['zero_event_class_alias_count'],'zero_event_representative_config_id':res['zero_event_representative_config_id'],'class_root_sha256':res['class_root_sha256'],'semantic_class_root_sha256':res['semantic_class_root_sha256'],'full_alias_mapping_root_sha256':res['full_alias_mapping_root_sha256'],'ordered_config_id_stream_root_sha256':res['ordered_config_id_stream_root_sha256'],'metrics':res['metrics'],'elapsed_seconds':res['elapsed_seconds'],'artifacts':res['artifacts'],'economic_pnl_read':False,'holdout_open':False,'worker_semantics':'V223 exact worker + V225 raw-cross cache + V226 exact range-query acceleration; event semantics unchanged','parent_worker_git_blob_sha1':v.EXPECTED_GIT_BLOB,'tick_raw_cache_sha256':hashlib.sha256(Path(a.tick_raw_cache).read_bytes()).hexdigest(),'tick_range_index_sha256':hashlib.sha256(Path(a.tick_range_index).read_bytes()).hexdigest()}
    raw=w.canonical(receipt);receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest();Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':status,'processed':receipt['processed_signal_configs'],'distinct':receipt['distinct_mask_class_count'],'duplicates':receipt['duplicate_config_count'],'semantic_root':receipt['semantic_class_root_sha256'],'physical_root':receipt['class_root_sha256'],'elapsed':receipt['elapsed_seconds']}));return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
