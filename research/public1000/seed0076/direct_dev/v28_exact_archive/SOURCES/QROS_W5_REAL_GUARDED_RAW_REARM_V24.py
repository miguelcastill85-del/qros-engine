#!/usr/bin/env python3
"""QROS W5 valid-quote full DEV raw TICK_BREAK and rearm=0 tapes.
Standalone pre-economic carrier: never reads PnL, management, holdout, GA2.
Independent offline oracle verifies whole candidate streams and Python raw oracle checks real samples.
"""
import os,sys,time,json,hashlib,pathlib,argparse
import numpy as np,numba as nb
r=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924');sys.path.insert(0,str(r));sys.path.insert(0,str(pathlib.Path('/mnt/data/qros_nonstall_v23/work')))
from frozen_structural import structural_states,next_replacement_source
from qros_w5_pre_econ_v1 import guarded_raw_oracle
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);BUFF=np.array([0.,.05,.10,.25],np.float64)
@nb.njit(cache=True)
def engine(bid,ask,first,last,sh,sl,hid,lid,atr,buff,point,raw_counts,admit_counts,do_fill,rawoff,admitoff,rawidx,rawbar,rawlid,admitidx,admitbar,admitlid):
 rawpos=rawoff.copy();admitpos=admitoff.copy();num_raw=np.zeros(8,np.int64);num_admit=np.zeros(8,np.int64);consumed=np.full(8,-100,np.int64);armed=np.ones(8,np.bool_);oldlevels=np.empty(8,np.float64)
 previous=0.;has_prev=False;invalid=0
 for bi in range(len(first)):
  levels=np.array([sh[bi],sl[bi]],np.float64);ids=np.array([hid[bi],lid[bi]],np.int64);a=atr[bi]
  for sidei in range(2):
   for z in range(4):
    ch=sidei*4+z
    if consumed[ch]!=ids[sidei]:armed[ch]=True
  for j in range(first[bi],last[bi]+1):
   if bid[j]<=0 or ask[j]<=bid[j]:invalid+=1;continue
   cur=bid[j]*point
   for si in range(2):
    level=levels[si];sid=ids[si]
    if np.isnan(level) or sid<0:continue
    for z in range(4):
     ch=si*4+z
     if not armed[ch] and consumed[ch]==sid:
      if (si==0 and cur<=oldlevels[ch]) or (si==1 and cur>=oldlevels[ch]):armed[ch]=True
     if not has_prev or (z>0 and np.isnan(a)):continue
     th=level+(buff[z]*a if si==0 else -buff[z]*a)
     cross=(previous<=th and cur>th) if si==0 else (previous>=th and cur<th)
     if cross:
      num_raw[ch]+=1
      if do_fill:
       p=rawpos[ch];rawidx[p]=j;rawbar[p]=bi;rawlid[p]=sid;rawpos[ch]=p+1
      if armed[ch] or consumed[ch]!=sid:
       num_admit[ch]+=1
       if do_fill:
        p=admitpos[ch];admitidx[p]=j;admitbar[p]=bi;admitlid[p]=sid;admitpos[ch]=p+1
       consumed[ch]=sid;oldlevels[ch]=level;armed[ch]=False
   previous=cur;has_prev=True
 if do_fill:
  for ch in range(8):
   if num_raw[ch]!=raw_counts[ch] or num_admit[ch]!=admit_counts[ch]:raise ValueError('COUNT_FILL_NONDETERMINISM')
 return num_raw,num_admit,invalid
@nb.njit(cache=True)
def independent_offline(bid,ask,raw_idx,raw_lid,first,rep,level,point,side):
 out=np.empty(len(raw_idx),np.int64);n=0;i=0;total=len(bid)
 while i<len(raw_idx):
  j=raw_idx[i];out[n]=j;n+=1;lid=raw_lid[i]
  bi=np.searchsorted(first,j,side='right')-1
  stop=rep[bi] if rep[bi]>=0 else total
  lv=level[bi];ret=total
  for k in range(j+1,stop):
   if bid[k]<=0 or ask[k]<=bid[k]:continue
   p=bid[k]*point
   if (side==1 and p<=lv) or (side==-1 and p>=lv):ret=k;break
  allowed=min(ret,stop)
  i+=1
  while i<len(raw_idx) and raw_lid[i]==lid and raw_idx[i]<allowed:i+=1
 return out[:n]
def fhash(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(8_388_608),b''):h.update(x)
 return h.hexdigest()
def atomic(o,path):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n');os.replace(tmp,path)
def main():
 t0=time.monotonic();tick=np.memmap(r/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');bars=np.load(r/'XAUUSD_M1_VALID_BID_BARS_V24.npy',mmap_mode='r',allow_pickle=False)
 with np.load(r/'XAUUSD_M1_VALID_INDICATORS_V24.npz',allow_pickle=False) as d:atr=np.r_[np.nan,d['ATR14'][:-1]]
 high=bars['high_bid'].astype(np.float64)*.01;low=bars['low_bid'].astype(np.float64)*.01
 sh,sl,hid,lid=structural_states(high,low,5,0);first=bars['first_source_index'];last=bars['last_source_index']
 zero=np.zeros(9,np.int64);dummy=np.empty(0,np.int64);dummybar=np.empty(0,np.int32)
 cu,ca,invalid=engine(tick['bid'],tick['ask'],first,last,sh,sl,hid,lid,atr,BUFF,.01,zero[:8],zero[:8],False,zero,zero,dummy,dummybar,dummy,dummy,dummybar,dummy)
 original_bars=np.load(r/'XAUUSD_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
 clean_buckets=np.asarray(bars['bucket_ms']);missing=~np.isin(original_bars['bucket_ms'],clean_buckets);dropped_invalid_only=int(np.sum(original_bars['last_source_index'][missing]-original_bars['first_source_index'][missing]+1))
 assert np.count_nonzero(missing)==27 and dropped_invalid_only==70 and invalid+dropped_invalid_only==942184+74,('INVALID_QUOTE_COUNT',invalid,dropped_invalid_only)
 audit1={'schema':'QROS_W5_V24_REAL_GUARDED_TICK_REARM_COUNTS','status':'REAL_TICK_ALL_CHANNELS_COUNTS','count_raw_BUY':cu[:4].tolist(),'count_raw_SELL':cu[4:].tolist(),'count_rearmed_BUY':ca[:4].tolist(),'count_rearmed_SELL':ca[4:].tolist(),'invalid_quotes_excluded_in_nonempty_valid_bars':int(invalid),'invalid_quotes_in_27_removed_bars':dropped_invalid_only,'data_clean_bar_sha256':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13','data_clean_ind_sha256':'8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6','elapsed_seconds':round(time.monotonic()-t0,3),'PnL_read':False,'holdout_open':False}
 atomic(audit1,r/'V24_REAL_GUARDED_COUNTS_CHECKPOINT.json');print(json.dumps({'phase':'FULL_REAL_COUNTS','raw':cu.tolist(),'admitted':ca.tolist(),'seconds':audit1['elapsed_seconds']}),flush=True)
 roff=np.empty(9,np.int64);aoff=np.empty(9,np.int64);roff[0]=0;aoff[0]=0
 for ch in range(8):roff[ch+1]=roff[ch]+cu[ch];aoff[ch+1]=aoff[ch]+ca[ch]
 ri=np.empty(roff[-1],np.int64);rb=np.empty(roff[-1],np.int32);rl=np.empty(roff[-1],np.int64)
 ai=np.empty(aoff[-1],np.int64);ab=np.empty(aoff[-1],np.int32);al=np.empty(aoff[-1],np.int64)
 cu2,ca2,invalid2=engine(tick['bid'],tick['ask'],first,last,sh,sl,hid,lid,atr,BUFF,.01,cu,ca,True,roff[:-1],aoff[:-1],ri,rb,rl,ai,ab,al)
 assert np.array_equal(cu,cu2) and np.array_equal(ca,ca2) and invalid2==invalid
 # Independent full tape offline rearm parity (different algorithm; scans only causal valid ticks).
 rep1=next_replacement_source(hid,first);rep2=next_replacement_source(lid,first);oracle={}
 for ch in range(8):
  si=ch//4;start=roff[ch];end=roff[ch+1];aa=aoff[ch];bb=aoff[ch+1]
  expected=independent_offline(tick['bid'],tick['ask'],ri[start:end],rl[start:end],first,rep1 if si==0 else rep2,sh if si==0 else sl,.01,1 if si==0 else -1)
  # If offline variant does not agree, stop before any economic results.
  assert np.array_equal(expected,ai[aa:bb]),('OFFLINE_REARM_PARITY_FAILED',ch,len(expected),bb-aa)
  oracle[str(ch)]={'raw_rows':int(end-start),'admitted_rows':int(bb-aa),'independent_offline_rearm':'PASS'}
 # Independent Python reference on deterministic stratified real windows: compare every raw tick event inside window excluding warm-up bar.
 sample_bars=np.unique(np.clip(np.r_[np.linspace(200,len(first)-200,18,dtype=np.int64),np.random.default_rng(20260924).choice(np.arange(200,len(first)-200),size=12,replace=False)],200,len(first)-200));checked=0;sample_rows=0
 for base in sample_bars:
  endbar=min(len(first),int(base)+12);sub_first=first[base:endbar]-first[base];sub_last=last[base:endbar]-first[base]
  if sub_last[-1]-sub_first[0]>18000:continue  # bounded independent reference
  bid=tick['bid'][first[base]:last[endbar-1]+1].copy();ask=tick['ask'][first[base]:last[endbar-1]+1].copy()
  for si,(lv,ids) in enumerate(((sh,hid),(sl,lid))):
   ref=guarded_raw_oracle(bid,ask,sub_first,sub_last,lv[base:endbar],ids[base:endbar],atr[base:endbar],1 if si==0 else -1,.01)
   for z in range(4):
    ch=si*4+z;aa=roff[ch];bb=roff[ch+1]
    loidx=np.searchsorted(ri[aa:bb],first[base+1],side='left')+aa;hiidx=np.searchsorted(ri[aa:bb],last[endbar-1]+1,side='left')+aa
    got=list(zip(ri[loidx:hiidx].tolist(),rb[loidx:hiidx].tolist(),rl[loidx:hiidx].tolist()))
    exp=[(int(j+first[base]),int(b+base),int(l)) for j,b,l in ref[z] if b>=1]
    assert got==exp,('INDEPENDENT_REAL_PYTHON_RAW_PARITY',si,z,int(base),len(got),len(exp))
    checked+=1;sample_rows+=len(got)
 out=r/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz';tmp=out.with_suffix('.npz.tmp')
 with tmp.open('wb') as f:
  np.savez_compressed(f,raw_offsets=roff,raw_idx=ri,raw_bar=rb,raw_level_id=rl,admitted_offsets=aoff,admitted_idx=ai,admitted_bar=ab,admitted_level_id=al,fractal_window=np.array([5],np.int32),buffers=BUFF)
  f.flush();os.fsync(f.fileno())
 os.replace(tmp,out)
 receipt={'schema':'QROS_W5_V24_FULL_REAL_TICK_GUARDED_RAW_AND_REARM0_PARITY','status':'PASS_REAL_FULL_TICK_RAW_AND_REARM0_EIGHT_CHANNELS','raw_tick_rows':len(tick),'real_M1_sanitized_bars':len(bars),'original_frozen_V220_sha1':'805044c9918a87456a95e150a1c9a1292112cf4c','quote_invalid_excluded_total':int(invalid+dropped_invalid_only),'quote_invalid_in_27_removed_bars':dropped_invalid_only,'per_channel_oracle':oracle,'independent_python_real_window_checks':checked,'python_reference_real_sample_events':sample_rows,'independent_python_real_sample_window_count':len(sample_bars),'raw_counts_by_channel':cu.tolist(),'rearm_counts_by_channel':ca.tolist(),'tape_archive_sha256':fhash(out),'tape_archive_bytes':out.stat().st_size,'data_source_raw_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','data_source_valid_bar_sha256':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13','data_source_valid_ind_sha256':'8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6','scope':'PRE_ECON_FULL_TICK_RAW_BUFFER_AND_REARM0_ONLY; RETEST_AND_ALL_10_FAMILY_STILL_PENDING','broker_DST_certified':False,'broker_commission_certified':False,'economic_run_authorized':False,'PnL_read':False,'holdout_open':False,'GA2_open':False,'elapsed_seconds':round(time.monotonic()-t0,2)}
 atomic(receipt,r/'V24_REAL_GUARDED_TICK_RAW_AND_REARM0_ORACLE_RECEIPT.json');print(json.dumps({k:receipt[k] for k in ('status','raw_counts_by_channel','rearm_counts_by_channel','independent_python_real_window_checks','python_reference_real_sample_events','tape_archive_sha256','tape_archive_bytes','elapsed_seconds')},sort_keys=True),flush=True)
if __name__=='__main__': main()
