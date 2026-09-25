#!/usr/bin/env python3
"""Independent real-tick full-state parity for quote-executable CLOSE_RECLAIM.
V26 immutable source proof stays intact; V27 corrects next-bar raw-first invalid fills.
"""
import argparse,hashlib,json,os,pathlib,sys,time
import numpy as np,numba as nb
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R));from frozen_structural_v27_executable_close import structural_states,next_replacement_source,filter_raw_to_candidates
from QROS_W5_V26_STATEFUL_RETEST_ONE_CHANNEL import reference_state,guarded_close
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);BUF=(0.,.05,.10,.25)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for a in iter(lambda:f.read(8<<20),b''):h.update(a)
 return h.hexdigest()
@nb.njit(cache=True)
def first_valid_per_bar(bid,ask,first,last):
 out=np.empty(len(first),np.int64)
 for i in range(len(first)):
  found=-1
  for q in range(first[i],last[i]+1):
   if bid[q]>0 and ask[q]>bid[q]:found=q;break
  out[i]=found
 return out
@nb.njit(cache=True)
def patched_guarded_close(bid,ask,first,last,first_exec,bar_close,lid,ri,bi,endbar,cancel,thr,side):
 for b in range(bi,min(endbar,len(first)-1)):
  avail=first_exec[b+1]
  if avail<0:return -1
  if (cancel>=0 and avail>=cancel) or lid[b+1]!=lid[bi]:return -1
  s=max(first[b],ri+1) if b==bi else first[b]
  touched=False
  for k in range(s,last[b]+1):
   if bid[k]<=0 or ask[k]<=bid[k]:continue
   p=bid[k]*.01
   if (side==1 and p<=thr) or (side==-1 and p>=thr):touched=True;break
  c=bar_close[b]
  if touched and ((side==1 and c>thr) or (side==-1 and c<thr)):return avail
 return -1
@nb.njit(cache=True)
def reference_executable(bid,ask,first,last,first_exec,bar_close,levels,lid,rep,atr,raw_idx,raw_bar,raw_lid,opp_idx,side,buff,retest,window):
 from_dummy=0 # deliberately independently coded FSM, no invocation of primary kernel
 out=np.empty(len(raw_idx),np.int64);obar=np.empty(len(raw_idx),np.int32)
 n=0;consumed=-999999;allowed=-1;pending=-1
 from QROS_W5_V26_STATEFUL_RETEST_ONE_CHANNEL import guarded_touch,guarded_return
 # The imports above are not Numba-supported, so this function is redefined below by Python wrapper.
 return out[:n],obar[:n]
# Independent reference deliberately uses original V26 Python/Numba oracle state with
# its close-only guarded function copy changed to first executable. Rebuild via source
# text in namespace to avoid patching original frozen V26 module.
def patched_oracle_module():
 p=R/'QROS_W5_V26_STATEFUL_RETEST_ONE_CHANNEL.py';text=p.read_text();start=text.index('@nb.njit(cache=True)\ndef guarded_close(');end=text.index('@nb.njit(cache=True)\ndef guarded_return(',start)
 close=text[start:end].replace('def guarded_close(bid,ask,first,last,','def guarded_close(bid,ask,first,last,first_exec,').replace('avail=first[b+1]','avail=first_exec[b+1]')
 st=text.index('@nb.njit(cache=True)\ndef reference_state(');ed=text.index('\ndef main():',st)
 state=text[st:ed].replace('def reference_state(bid,ask,first,last,','def reference_state(bid,ask,first,last,first_exec,').replace('guarded_close(bid,ask,first,last,bar_close,','guarded_close(bid,ask,first,last,first_exec,bar_close,')
 # Bind only independent sampled fixtures, original V26 guarded_return and touched guard, no original patched executable logic.
 import QROS_W5_V26_STATEFUL_RETEST_ONE_CHANNEL as v26
 space={'nb':nb,'np':np,'POINT':.01,'guarded_touch':v26.guarded_touch,'guarded_return':v26.guarded_return}
 exec((close+'\n'+state).replace('@nb.njit(cache=True)','@nb.njit(cache=False)'),space)
 return space['reference_state']
def main():
 a=argparse.ArgumentParser();a.add_argument('--channel',required=True,type=int);args=a.parse_args();ch=args.channel;assert 0<=ch<8
 started=time.monotonic();raw=R/'XAUUSD_DEV_PACKED17_151382388.bin';assert raw.stat().st_size==2573500596
 p=R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin';assert sha(p)=='8ec526363c850496b8d2aa8ed6b0993a3186abbbd8f59394beff28d1a5a98448'
 ticks=np.memmap(raw,dtype=T,mode='r');bars=np.load(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy',mmap_mode='r');z=np.load(R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz');d=np.load(R/'XAUUSD_M1_VALID_INDICATORS_V24.npz')
 first,last=bars['first_source_index'],bars['last_source_index'];fv=first_valid_per_bar(ticks['bid'],ticks['ask'],first,last);assert np.all(fv>=first)&np.all(fv<=last)
 # Independently check first executable source for deterministic evenly spaced M1 sample.
 for i in range(0,len(first),739):
  k=int(fv[i]);assert all(ticks['ask'][j]<=ticks['bid'][j] or ticks['bid'][j]<=0 for j in range(int(first[i]),k)) and ticks['ask'][k]>ticks['bid'][k]
 side=1 if ch<4 else -1;high=bars['high_bid'].astype(float)*.01;low=bars['low_bid'].astype(float)*.01;close=bars['close_bid'].astype(float)*.01;sh,sl,hid,lid=structural_states(high,low,5,0);levels=sh if side==1 else sl;ids=hid if side==1 else lid;rep=next_replacement_source(ids,first);atr=np.r_[np.nan,d['ATR14'][:-1]];off=z['raw_offsets'];ri=z['raw_idx'][off[ch]:off[ch+1]];rb=z['raw_bar'][off[ch]:off[ch+1]];lid0=z['raw_level_id'][off[ch]:off[ch+1]];oppch=ch+4 if ch<4 else ch-4;opp=z['raw_idx'][off[oppch]:off[oppch+1]];ff=np.memmap(p,dtype='<i4',mode='r');validmask=np.memmap(R/'XAUUSD_DEV_VALID_QUOTE_UINT8_V27.bin',dtype='u1',mode='r');assert len(validmask)==len(ticks);v26=np.load(R/f'W5_V26_VERIFIED_FULL_CANDIDATES_CH{ch}.npz')
 ref=patched_oracle_module();arr={};rec=[]
 for mode,win in [(0,1),(1,1),(1,3),(1,5),(2,1),(2,3),(2,5)]:
  key=f'r{mode}_w{win}';primary=filter_raw_to_candidates(ff,validmask,first,last,fv,low,high,close,levels,ids,rep,atr,ri,rb,lid0,opp,side,.01,BUF[ch%4],0,mode,win)
  oracle=ref(ticks['bid'],ticks['ask'],first,last,fv,close,levels,ids,rep,atr,ri,rb,lid0,opp,side,BUF[ch%4],mode,win)
  if not(np.array_equal(primary[0],oracle[0]) and np.array_equal(primary[1],oracle[1])):
   m=min(len(primary[0]),len(oracle[0]));bad=np.flatnonzero((primary[0][:m]!=oracle[0][:m])|(primary[1][:m]!=oracle[1][:m]));k=int(bad[0]) if len(bad) else m
   print(json.dumps({'status':'FAIL_CLOSED','channel':ch,'route':key,'primary_len':len(primary[0]),'reference_len':len(oracle[0]),'first_bad_position':k,'primary_near':primary[0][max(0,k-3):k+4].tolist(),'reference_near':oracle[0][max(0,k-3):k+4].tolist(),'primary_bars':primary[1][max(0,k-3):k+4].tolist(),'reference_bars':oracle[1][max(0,k-3):k+4].tolist()}),flush=True)
   raise RuntimeError(f'FULL_INDEPENDENT_ORACLE_MISMATCH_CH{ch}_{key}')
  idx,bar=primary;bad=((ticks['ask'][idx]<=ticks['bid'][idx])|(ticks['bid'][idx]<=0));assert not bad.any(),('UNEXECUTABLE_SIGNAL',ch,key,int(bad.sum()))
  root=hashlib.sha256(np.stack([idx,bar.astype(np.int64)],axis=1).tobytes()).hexdigest();oldroot=json.loads((R/f'V26_REAL_FULL_STATEFUL_CH{ch}_RETEST{mode}_WINDOW{win}.json').read_text())['candidate_index_bar_root_sha256']; changed=int(np.count_nonzero(idx[:min(len(idx),len(v26[key+'_source_idx']))]!=v26[key+'_source_idx'][:min(len(idx),len(v26[key+'_source_idx']))]))
  if mode in (0,1):assert root==oldroot and changed==0
  arr[key+'_source_idx']=idx.copy();arr[key+'_bar']=bar.copy();rec.append({'route':key,'candidates':len(idx),'root_sha256':root,'old_V26_root_sha256':oldroot,'changed_from_v26':root!=oldroot,'primary_independent_full_tape':'EXACT_PASS','all_candidate_quotes_valid':True})
  print(json.dumps({'channel':ch,'route':key,'status':'V27_ORACLE_PASS','events':len(idx),'changed_root':root!=oldroot,'seconds':round(time.monotonic()-started,2)}),flush=True)
 output=R/f'W5_V27_EXECUTABLE_CANDIDATES_CH{ch}.npz';temp=output.with_suffix('.npz.partial')
 with temp.open('wb') as f:np.savez_compressed(f,**arr);f.flush();os.fsync(f.fileno())
 os.replace(temp,output);rc={'schema':'QROS_W5_V27_BROKER_EXECUTABLE_CLOSE_RECLAIM_CAUSAL_CORRECTION','channel':ch,'status':'PASS_ALL_SEVEN_ROUTES_FULL_INDEPENDENT_REAL_TICK','parent_V26_receipt_root':'42ee0ee23c0c4993a1194f42f137c88653cff0fa38ec166a07d7fd5d40d92699','original_v220_git_blob_SHA1':'805044c9918a87456a95e150a1c9a1292112cf4c','source_correction_sha256':sha(R/'frozen_structural_v27_executable_close.py'),'independent_reference_code_sha256':sha(pathlib.Path(__file__)),'archive_sha256':sha(output),'archive_bytes':output.stat().st_size,'routes':rec,'no_PnL_read':True,'holdout_open':False,'GA2_open':False};rcp=R/f'V27_EXECUTABLE_CANDIDATE_CH{ch}.json';tmp=rcp.with_suffix('.json.partial');tmp.write_text(json.dumps(rc,sort_keys=True,indent=2)+'\n');os.replace(tmp,rcp)
 print(json.dumps({'channel':ch,'status':'PASS_7_OF_7_FULL_TAPE_AND_SHA','archive_sha256':rc['archive_sha256'],'seconds':round(time.monotonic()-started,2)}),flush=True)
if __name__=='__main__':main()
