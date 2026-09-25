#!/usr/bin/env python3
"""Materialize only previously verified V26 56 W5 candidate source-index/bar routes.
No research gates, execution prices, PnL, risk or holdout are computed.
Each channel is a resumable SHA-verified shard; no recomputation of valid shards.
"""
import argparse,hashlib,json,os,pathlib,sys,time
import numpy as np
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from frozen_structural import structural_states,next_replacement_source,filter_raw_to_candidates
TAPE_SHA='8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0';FF_SHA='8ec526363c850496b8d2aa8ed6b0993a3186abbbd8f59394beff28d1a5a98448';BARS_SHA='8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13';IND_SHA='8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6'
MODES=((0,1),(1,1),(1,3),(1,5),(2,1),(2,3),(2,5))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def atomic(data,p):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');os.replace(tmp,p)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--first-channel',type=int,default=0);ap.add_argument('--last-channel',type=int,default=8);a=ap.parse_args();assert 0<=a.first_channel<a.last_channel<=8
 started=time.monotonic();rawpaths={'tape':R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz','ff':R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin','bars':R/'XAUUSD_M1_VALID_BID_BARS_V24.npy','ind':R/'XAUUSD_M1_VALID_INDICATORS_V24.npz'}
 for key,expected in [('tape',TAPE_SHA),('ff',FF_SHA),('bars',BARS_SHA),('ind',IND_SHA)]:
  actual=sha(rawpaths[key]);assert actual==expected,(key,actual,expected)
 bars=np.load(rawpaths['bars'],mmap_mode='r');tape=np.load(rawpaths['tape']);d=np.load(rawpaths['ind']);bidff=np.memmap(rawpaths['ff'],dtype='<i4',mode='r');first=bars['first_source_index'];last=bars['last_source_index'];high=bars['high_bid'].astype(float)*.01;low=bars['low_bid'].astype(float)*.01;close=bars['close_bid'].astype(float)*.01;sh,sl,hid,lid=structural_states(high,low,5,0);atr=np.r_[np.nan,d['ATR14'][:-1]];buff=(0.,.05,.10,.25)
 progress=R/'V26_MATERIALIZATION_PROGRESS.json';seen=[]
 for ch in range(a.first_channel,a.last_channel):
  out=R/f'W5_V26_VERIFIED_FULL_CANDIDATES_CH{ch}.npz';receipt=R/f'V26_CANDIDATE_MATERIALIZED_CH{ch}.json'
  if out.exists() and receipt.exists():
   j=json.loads(receipt.read_bytes());
   if j['archive_sha256']==sha(out) and j['parent_real_tape_sha256']==TAPE_SHA and len(j['routes'])==7:
    print(json.dumps({'channel':ch,'status':'SKIP_EXISTING_BYTES_AND_SHA_VERIFIED','size':out.stat().st_size}),flush=True);seen.append({'path':out.name,'bytes':out.stat().st_size,'sha256':j['archive_sha256']});continue
  side=1 if ch<4 else -1;level=sh if side==1 else sl;ids=hid if side==1 else lid;rep=next_replacement_source(ids,first);off=tape['raw_offsets'];raw_idx=tape['raw_idx'][off[ch]:off[ch+1]];raw_bar=tape['raw_bar'][off[ch]:off[ch+1]];raw_lid=tape['raw_level_id'][off[ch]:off[ch+1]];oppch=ch+4 if ch<4 else ch-4;opp=tape['raw_idx'][off[oppch]:off[oppch+1]];arrays={};routes=[]
  for mode,win in MODES:
   original=filter_raw_to_candidates(bidff,first,last,low,high,close,level,ids,rep,atr,raw_idx,raw_bar,raw_lid,opp,side,.01,buff[ch%4],0,mode,win)
   pinned=R/f'V26_REAL_FULL_STATEFUL_CH{ch}_RETEST{mode}_WINDOW{win}.json';j=json.loads(pinned.read_bytes());assert j['status']=='PASS_STATEFUL_FULL_CHANNEL' and j['trade_candidate_ids_and_bars_exact']
   thisroot=hashlib.sha256(np.stack([original[0],original[1].astype(np.int64)],axis=1).tobytes()).hexdigest();assert thisroot==j['candidate_index_bar_root_sha256'] and len(original[0])==j['full_primary_count'],('BINARY_DATA_NOT_IDENTICAL_TO_FROZEN_SUCCESS_RECEIPT',ch,mode,win)
   key=f'r{mode}_w{win}';arrays[key+'_source_idx']=original[0].copy();arrays[key+'_bar']=original[1].copy();routes.append({'retest_code':mode,'window':win,'rows':len(original[0]),'candidate_id_and_bar_root_sha256':thisroot,'receipt_SHA256':sha(pinned)})
  tmp=out.with_suffix('.npz.partial');f=tmp.open('wb');np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno());f.close();os.replace(tmp,out)
  receipt_data={'schema':'QROS_W5_V26_ONE_CHANNEL_MATERIALIZED_EXACT_CANDIDATE_SHARD_V1','channel':ch,'status':'PASS_REPRODUCED_FROM_VERIFIED_FULL_STATEFUL_7_OF_7','parent_real_tape_sha256':TAPE_SHA,'bid_ff_sha256':FF_SHA,'valid_M1_bar_sha256':BARS_SHA,'valid_M1_indicator_sha256':IND_SHA,'routes':routes,'archive_bytes':out.stat().st_size,'archive_sha256':sha(out),'PnL_read':False,'holdout_open':False,'GA2_open':False}
  atomic(receipt_data,receipt);seen.append({'path':out.name,'bytes':out.stat().st_size,'sha256':receipt_data['archive_sha256']})
  atomic({'schema':'QROS_W5_V26_RESUMABLE_CANDIDATE_MATERIALIZER_PROGRESS','sequence':len(seen),'verified_artifacts':seen,'last_channel_done':ch,'elapsed_seconds':round(time.monotonic()-started,2)},progress)
  print(json.dumps({'channel':ch,'status':'PASS_MATERIALIZED_ALL_SEVEN_ROUTE_ARRAYS','archive_bytes':out.stat().st_size,'archive_sha256':receipt_data['archive_sha256'],'seconds':round(time.monotonic()-started,2)}),flush=True)
if __name__=='__main__':main()
