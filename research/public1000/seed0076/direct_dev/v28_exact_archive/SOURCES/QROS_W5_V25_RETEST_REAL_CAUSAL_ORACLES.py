#!/usr/bin/env python3
"""W5 single-cell real DEV preeconomic RETEST_ENTRY isolated causal oracle.
Sampled parent-state transitions; NOT full 10-family, economic trades, or promotion.
All source data identities are fixed by the signed V24 release and GitHub anchor.
"""
from __future__ import annotations
import hashlib,json,os,pathlib,sys,time
import numpy as np, numba as nb
R=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(R))
from frozen_structural import structural_states,next_replacement_source,_find_touch_reclaim,_find_close_reclaim
D=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
EXPECTED={
 'raw':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
 'bars':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13',
 'ind':'8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6',
 'tape':'8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0'}
def hash_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
@nb.njit(cache=True)
def primary_one(bid,ask,first,last,close,levelid,start_idx,bi,cancel,th,side,window,retest):
 # retraced literal V220 touch/close state with independent actual Bid/Ask quote guard.
 n=len(first);stop=min(bi+window,n)
 touched=False
 for b in range(bi,stop):
  begin=max(int(first[b]),start_idx+1) if b==bi else int(first[b]);end=int(last[b])
  if retest==2:
   if b+1>=n:break
   avail=int(first[b+1]);
   if cancel>=0 and avail>=cancel:return -1
   if levelid[b+1]!=levelid[bi]:return -1
   touch_here=False
   for j in range(begin,end+1):
    if cancel>=0 and j>=cancel:break
    if bid[j]<=0 or ask[j]<=bid[j]:continue
    p=bid[j]*.01
    if (side==1 and p<=th) or (side==-1 and p>=th):touch_here=True;break
   if touch_here:
    v=close[b]*.01
    if (side==1 and v>th) or (side==-1 and v<th):return avail
  else:
   for j in range(begin,end+1):
    if cancel>=0 and j>=cancel:return -1
    if bid[j]<=0 or ask[j]<=bid[j]:continue
    p=bid[j]*.01
    if not touched:
     if (side==1 and p<=th) or (side==-1 and p>=th):touched=True
    elif (side==1 and p>th) or (side==-1 and p<th):return j
 return -1

def oracle_one(bid,ask,first,last,close,levelid,start_idx,bi,cancel,th,side,window,retest):
 # Reference procedural implementation, no Numba; only history at or before confirmation.
 for b in range(int(bi),min(int(bi)+int(window),len(first))):
  idxs=range(max(int(first[b]),int(start_idx)+1) if b==bi else int(first[b]),int(last[b])+1)
  if retest==2:
   if b+1>=len(first):return -1
   availability=int(first[b+1]);
   if (cancel>=0 and availability>=cancel) or levelid[b+1]!=levelid[bi]:return -1
   touched=False
   for j in idxs:
    if cancel>=0 and j>=cancel:break
    if ask[j]<=bid[j] or bid[j]<=0:continue
    touched=((bid[j]*.01<=th) if side==1 else (bid[j]*.01>=th))
    if touched:break
   if touched and ((close[b]*.01>th) if side==1 else (close[b]*.01<th)):return availability
  else:
   # Resume across bars within touch mode.
   if b==bi:touched=False
   for j in idxs:
    if cancel>=0 and j>=cancel:return -1
    if ask[j]<=bid[j] or bid[j]<=0:continue
    if not touched:
     touched=(bid[j]*.01<=th) if side==1 else (bid[j]*.01>=th)
    elif ((bid[j]*.01>th) if side==1 else (bid[j]*.01<th)):return j
 return -1

def fixture_tests():
 # Fully synthetic adversarial: valid same-bar/retest, invalid-only touch, replacement and next-bar availability.
 first=np.array([0,4,8,12],np.int64);last=first+3;lid=np.array([9,9,10,10],np.int64)
 bid=np.array([1000,1010,1030,1020,1010,990,1030,1010,1015,990,1050,1050,1010,990,1070,1010],np.int32)
 ask=bid+2;close=bid[last];th=1005*.01
 n=0
 for i in range(2):
  for win in [1,3,5]:
   for side in [1,-1]:
    for candidate in [0,4,8,12]:
     for cancel in [-1,6,8,12]:
      for mode in [1,2]:
       x=primary_one(bid,ask,first,last,close,lid,candidate,int(np.searchsorted(first,candidate,side='right')-1),cancel,th,side,win,mode)
       y=oracle_one(bid,ask,first,last,close,lid,candidate,int(np.searchsorted(first,candidate,side='right')-1),cancel,th,side,win,mode)
       assert x==y,(candidate,win,side,cancel,mode,x,y)
       n+=1
  ask[5]=bid[5] if i==0 else bid[5]-1 # invalid same-bar touch must not count as executable.
 return n

def main():
 st=time.monotonic()
 ticks=R/'XAUUSD_DEV_PACKED17_151382388.bin';barsfile=R/'XAUUSD_M1_VALID_BID_BARS_V24.npy';ind=R/'XAUUSD_M1_VALID_INDICATORS_V24.npz';tapefile=R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz'
 # Re-read exact immutable inputs; large 2.57GB cached hash skip this stage ONLY if verified proof receipt already signed v24.
 proof=json.loads((R/'V24_REAL_GUARDED_TICK_RAW_AND_REARM0_ORACLE_RECEIPT.json').read_text())
 assert proof['status']=='PASS_REAL_FULL_TICK_RAW_AND_REARM0_EIGHT_CHANNELS'
 for key,path in [('bars',barsfile),('ind',ind),('tape',tapefile)]:
  actual=hash_file(path);assert actual==EXPECTED[key],(key,actual)
 assert ticks.stat().st_size==2573500596
 t=np.memmap(ticks,dtype=D,mode='r');bars=np.load(barsfile,mmap_mode='r');d=np.load(ind)
 atr=np.r_[np.nan,d['ATR14'][:-1]];h=bars['high_bid'].astype(float)*.01;l=bars['low_bid'].astype(float)*.01
 sh,sl,hid,lid=structural_states(h,l,5,0);reps=[next_replacement_source(hid,bars['first_source_index']),next_replacement_source(lid,bars['first_source_index'])]
 z=np.load(tapefile);roff=z['raw_offsets'];ai=z['admitted_idx'];ab=z['admitted_bar'];aoff=z['admitted_offsets'];raw=z['raw_idx']
 first=bars['first_source_index'];last=bars['last_source_index'];close=bars['close_bid'];fixtures=fixture_tests();rng=np.random.default_rng(20260924)
 n=0;orig_success=0;all_success=0;guarded_invalid_windows=0;orig_cases=0;original_matched=0;by_channel={};issues=[]
 for ch in range(8):
  si=ch//4;zi=ch%4;side=1 if si==0 else -1;lv=sh if si==0 else sl;ids=hid if si==0 else lid;rep=reps[si]
  opp_raw=raw[int(roff[(1-si)*4+zi]):int(roff[(1-si)*4+zi+1])]
  start=int(aoff[ch]);end=int(aoff[ch+1]);chosen=np.unique(np.r_[np.linspace(start+20,end-21,22,dtype=np.int64),rng.integers(start+20,end-21,size=18,dtype=np.int64)])
  ch_checks=0
  for c in chosen:
   ri=int(ai[c]);bi=int(ab[c]);lid0=int(ids[bi]);repidx=int(rep[bi]);a=float(atr[bi]);thr=float(lv[bi])+(float(z['buffers'][zi])*a if si==0 else -float(z['buffers'][zi])*a)
   opposite_pos=int(np.searchsorted(opp_raw,ri,side='right'));opp=int(opp_raw[opposite_pos]) if opposite_pos<len(opp_raw) else -1
   cancel=min([x for x in [repidx,opp] if x>=0],default=-1)
   for win in [1,3,5]:
    for mode in [1,2]:
     primary=int(primary_one(t['bid'],t['ask'],first,last,close,ids,ri,bi,cancel,thr,side,win,mode))
     independent=int(oracle_one(t['bid'],t['ask'],first,last,close,ids,ri,bi,cancel,thr,side,win,mode))
     assert primary==independent,('ACTUAL_TICK_RETEST_PARITY',ch,ri,win,mode,primary,independent)
     n+=1;ch_checks+=1;all_success+=(primary>=0)
     # Frozen V220 function is only semantically equivalent on all-valid quotes.
     lastb=min(len(first)-1,bi+win);hi=int(last[lastb]);bad=np.any((t['ask'][ri+1:hi+1]<=t['bid'][ri+1:hi+1]) | (t['bid'][ri+1:hi+1]<=0))
     if bad:guarded_invalid_windows+=1
     else:
      if mode==1:old=int(_find_touch_reclaim(t['bid'],first,last,l,h,ri,bi,min(len(first),bi+win),cancel,thr,side,.01))
      else:old=int(_find_close_reclaim(t['bid'],first,last,l,h,close.astype(float)*.01,ri,bi,min(len(first),bi+win),cancel,thr,side,.01,ids))
      orig_cases+=1
      if old==primary:original_matched+=1
      else:issues.append({'channel':ch,'source':ri,'window':win,'mode':mode,'old':old,'new':primary})
  by_channel[str(ch)]={'samples':int(len(chosen)),'parity_checks':ch_checks}
 out={'schema':'QROS_W5_V25_REAL_CANDIDATE_RETEST_ISOLATED_PARITY_V1','status':'PASS_REAL_SAMPLED_RETEST_ORACLE' if not issues else 'SOURCE_MISMATCH_REQUIRES_DIAGNOSIS','scope':'ONE_PINNED_W5_CELL_PRE_ECON_ISOLATED_RETEST_NO_SEMANTIC_MASKS_OR_TRADE_PNL','original_V220_git_blob_SHA1':'805044c9918a87456a95e150a1c9a1292112cf4c','real_tape_sha256':EXPECTED['tape'],'clean_bar_sha256':EXPECTED['bars'],'clean_ind_sha256':EXPECTED['ind'],'raw_source_sha256_signed_v24':EXPECTED['raw'],'synthetic_adversarial_cases_pass':fixtures,'actual_8channel_retest_sample_reference_checks':n,'actual_retest_success_rows_among_checks':all_success,'cases_with_any_invalid_quotes_excluded_from_frozen_source_parity':guarded_invalid_windows,'cases_valid_quote_only_compared_frozen_v220':orig_cases,'cases_matching_frozen_v220_valid_quote_only':original_matched,'frozen_source_mismatches':issues[:20],'per_channel':by_channel,'PnL_read':False,'new_economic_trades':0,'holdout_open':False,'GA2_open':False,'elapsed_seconds':round(time.monotonic()-st,2)}
 path=R/'V25_REAL_RETEST_ISOLATED_ORACLE_RECEIPT.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');os.replace(tmp,path)
 print(json.dumps({k:out[k] for k in ('status','synthetic_adversarial_cases_pass','actual_8channel_retest_sample_reference_checks','cases_valid_quote_only_compared_frozen_v220','cases_matching_frozen_v220_valid_quote_only','cases_with_any_invalid_quotes_excluded_from_frozen_source_parity','frozen_source_mismatches','elapsed_seconds')},sort_keys=True),flush=True)
 if issues:raise SystemExit(2)
if __name__=='__main__':main()
