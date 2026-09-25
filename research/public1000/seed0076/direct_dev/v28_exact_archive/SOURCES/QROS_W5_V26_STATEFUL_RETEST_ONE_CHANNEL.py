#!/usr/bin/env python3
"""V26 bounded *non-economic* test: full-state W5 V220 code versus valid-Bid/Ask reference.
One frozen channel at a time; no reuse of already consumed base rearmed tape.
"""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,sys,time
import numpy as np,numba as nb
R=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(R))
from frozen_structural import structural_states,next_replacement_source,filter_raw_to_candidates
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);BUFF=np.array([0.,.05,.10,.25]);POINT=.01
@nb.njit(cache=True)
def forward_fill_valid(bid,ask,out):
 last=0;invalid=0
 for i in range(len(bid)):
  if bid[i]>0 and ask[i]>bid[i]:last=bid[i]
  else:invalid+=1
  out[i]=last
 return invalid
@nb.njit(cache=True)
def guarded_touch(bid,ask,first,last,ri,bi,endbar,cancel,thr,side):
 touched=False
 for b in range(bi,min(endbar,len(first))):
  j=max(first[b],ri+1) if b==bi else first[b];e=last[b] if cancel<0 else min(last[b],cancel-1)
  for k in range(j,e+1):
   if bid[k]<=0 or ask[k]<=bid[k]:continue
   p=bid[k]*POINT
   if not touched:
    if (side==1 and p<=thr) or (side==-1 and p>=thr):touched=True
   elif (side==1 and p>thr) or (side==-1 and p<thr):return k
  if cancel>=0 and last[b]>=cancel:return -1
 return -1
@nb.njit(cache=True)
def guarded_close(bid,ask,first,last,bar_close,lid,ri,bi,endbar,cancel,thr,side):
 for b in range(bi,min(endbar,len(first)-1)):
  avail=first[b+1]
  if (cancel>=0 and avail>=cancel) or lid[b+1]!=lid[bi]:return -1
  s=max(first[b],ri+1) if b==bi else first[b]
  touched=False
  for k in range(s,last[b]+1):
   if bid[k]<=0 or ask[k]<=bid[k]:continue
   p=bid[k]*POINT
   if (side==1 and p<=thr) or (side==-1 and p>=thr):touched=True;break
  c=bar_close[b]
  if touched and ((side==1 and c>thr) or (side==-1 and c<thr)):return avail
 return -1
@nb.njit(cache=True)
def guarded_return(bid,ask,first,last,start_idx,start_bar,stop_idx,level,side):
 for b in range(start_bar,len(first)):
  if stop_idx>=0 and first[b]>=stop_idx:return -1
  j=max(first[b],start_idx+1) if b==start_bar else first[b];e=last[b] if stop_idx<0 else min(last[b],stop_idx-1)
  for k in range(j,e+1):
   if bid[k]<=0 or ask[k]<=bid[k]:continue
   p=bid[k]*POINT
   if (side==1 and p<=level) or (side==-1 and p>=level):return k
 return -1
@nb.njit(cache=True)
def reference_state(bid,ask,first,last,bar_close,levels,lid,rep,atr,raw_idx,raw_bar,raw_lid,opp_idx,side,buff,retest,window):
 out=np.empty(len(raw_idx),np.int64);outbar=np.empty(len(raw_idx),np.int32)
 n=0;consumed=-999999;allowed_after=-1;pending=-1
 for z in range(len(raw_idx)):
  ri=raw_idx[z];bi=raw_bar[z];id0=raw_lid[z]
  if pending>=0 and ri<pending:continue
  if allowed_after>=0 and ri<allowed_after and id0==consumed:continue
  a=atr[bi]
  if buff and np.isnan(a):continue
  th=levels[bi]+(buff*a if side==1 else -buff*a)
  if np.isnan(th):continue
  final=ri;fb=bi
  if retest:
   replacement=rep[bi]
   oppos=np.searchsorted(opp_idx,ri,side='right');opp=opp_idx[oppos] if oppos<len(opp_idx) else -1
   cancel=replacement if opp<0 or (replacement>=0 and replacement<=opp) else opp
   endbar=min(len(first),bi+window)
   if retest==1:final=guarded_touch(bid,ask,first,last,ri,bi,endbar,cancel,th,side)
   else:final=guarded_close(bid,ask,first,last,bar_close,lid,ri,bi,endbar,cancel,th,side)
   if final<0:
    expiry=first[endbar] if endbar<len(first) else last[-1]+1
    pending=expiry if cancel<0 or expiry<=cancel else cancel
    continue
   while fb+1<len(first) and first[fb+1]<=final:fb+=1
   pending=-1
  out[n]=final;outbar[n]=fb;n+=1;consumed=id0
  replacement=rep[fb]
  returned=guarded_return(bid,ask,first,last,final,fb,replacement,levels[bi],side)
  if returned>=0 and replacement>=0:allowed_after=min(returned,replacement)
  elif returned>=0:allowed_after=returned
  elif replacement>=0:allowed_after=replacement
  else:allowed_after=last[-1]+1
 return out[:n],outbar[:n]

def main():
 p=argparse.ArgumentParser();p.add_argument('--channel',type=int,default=0);p.add_argument('--retest',type=int,default=1);p.add_argument('--window',type=int,default=1);a=p.parse_args()
 assert 0<=a.channel<8 and a.retest in (0,1,2) and a.window in (1,3,5)
 now=time.monotonic();ticks=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');bars=np.load(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy',mmap_mode='r');z=np.load(R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz');d=np.load(R/'XAUUSD_M1_VALID_INDICATORS_V24.npz')
 orig_sha='8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0';assert hashlib.sha256((R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz').read_bytes()).hexdigest()==orig_sha
 ff_path=R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin'
 if not ff_path.is_file() or ff_path.stat().st_size!=len(ticks)*4:
  tmp=ff_path.with_suffix('.bin.partial');arr=np.memmap(tmp,dtype=np.int32,mode='w+',shape=(len(ticks),));invalid=forward_fill_valid(ticks['bid'],ticks['ask'],arr);arr.flush();del arr;assert invalid==942258;os.replace(tmp,ff_path)
 bidff=np.memmap(ff_path,dtype=np.int32,mode='r',shape=(len(ticks),));first=bars['first_source_index'];last=bars['last_source_index'];close=bars['close_bid'].astype(float)*POINT
 high=bars['high_bid'].astype(float)*POINT;low=bars['low_bid'].astype(float)*POINT;sh,sl,hid,lid=structural_states(high,low,5,0);side=1 if a.channel//4==0 else -1;level=sh if side==1 else sl;ids=hid if side==1 else lid;rep=next_replacement_source(ids,first)
 ch=a.channel;chopp=(4 if side==1 else 0)+(ch%4);off=z['raw_offsets'];i=z['raw_idx'][off[ch]:off[ch+1]];bar=z['raw_bar'][off[ch]:off[ch+1]];rawid=z['raw_level_id'][off[ch]:off[ch+1]];opp=z['raw_idx'][off[chopp]:off[chopp+1]];atr=np.r_[np.nan,d['ATR14'][:-1]];buffer=float(BUFF[ch%4]);print(json.dumps({'phase':'START_ONE_CHANNEL','channel':ch,'raw':len(i),'retest':a.retest,'window':a.window,'setup_s':round(time.monotonic()-now,2)}),flush=True)
 got=filter_raw_to_candidates(bidff,first,last,low,high,close,level,ids,rep,atr,i,bar,rawid,opp,side,POINT,buffer,0,a.retest,a.window);print(json.dumps({'phase':'FROZEN_V220_FILLED_BID_FULL_REAL','accepted':len(got[0]),'seconds':round(time.monotonic()-now,2)}),flush=True)
 oracle=reference_state(ticks['bid'],ticks['ask'],first,last,close,level,ids,rep,atr,i,bar,rawid,opp,side,buffer,a.retest,a.window)
 eq=np.array_equal(got[0],oracle[0]) and np.array_equal(got[1],oracle[1]);print(json.dumps({'phase':'INDEPENDENT_REFERENCE_FULL_REAL','accepted':len(oracle[0]),'parity':eq,'seconds':round(time.monotonic()-now,2)}),flush=True)
 if not eq:
  bad=np.flatnonzero(got[0][:min(len(got[0]),len(oracle[0]))]!=oracle[0][:min(len(got[0]),len(oracle[0]))]);first_bad=int(bad[0]) if len(bad) else -1
  print(json.dumps({'status':'FAIL_CLOSED_STATEFUL_MISMATCH','first_mismatch':first_bad,'primary_count':len(got[0]),'oracle_count':len(oracle[0])}),flush=True);raise SystemExit(2)
 digest=hashlib.sha256(np.stack((got[0].astype('<i8'),got[1].astype('<i8')),axis=1).tobytes()).hexdigest()
 receipt={'schema':'QROS_W5_V26_ONE_CHANNEL_STATEFUL_RETEST_VALIDQUOTE_PARITY','status':'PASS_STATEFUL_FULL_CHANNEL' if eq else 'FAIL_CLOSED','channel':ch,'retest':a.retest,'window':a.window,'raw_events':len(i),'full_primary_count':len(got[0]),'independent_reference_count':len(oracle[0]),'trade_candidate_ids_and_bars_exact':eq,'candidate_index_bar_root_sha256':digest,'real_tape_sha256':orig_sha,'derived_bid_forward_fill_is_past_only':True,'derived_bid_full_size':ff_path.stat().st_size,'economic_results_observed':False,'holdout_open':False,'GA2_open':False,'seconds':round(time.monotonic()-now,2)}
 out=R/f'V26_REAL_FULL_STATEFUL_CH{ch}_RETEST{a.retest}_WINDOW{a.window}.json';tmp=out.with_suffix('.json.tmp');tmp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');os.replace(tmp,out)
 print(json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':main()
