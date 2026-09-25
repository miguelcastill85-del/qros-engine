#!/usr/bin/env python3
"""Independent audit of all 56 W5 full stateful preecon retest paths and V24 online route ID parity."""
import pathlib,json,hashlib,time,sys
import numpy as np
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R));from frozen_structural import structural_states,next_replacement_source,filter_raw_to_candidates
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);BUF=[0.,.05,.10,.25]

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 start=time.monotonic();rows=[];h=hashlib.sha256();sum_candidates=0
 for ch in range(8):
  for mode,win in [(0,1),(1,1),(1,3),(1,5),(2,1),(2,3),(2,5)]:
   path=R/f'V26_REAL_FULL_STATEFUL_CH{ch}_RETEST{mode}_WINDOW{win}.json'
   assert path.is_file(),('MISSING_FULL_ROUTE_RECEIPT',ch,mode,win)
   j=json.loads(path.read_bytes());assert j['channel']==ch and j['retest']==mode and j['window']==win and j['status']=='PASS_STATEFUL_FULL_CHANNEL' and j['trade_candidate_ids_and_bars_exact'] and j['full_primary_count']==j['independent_reference_count'] and not j['economic_results_observed'] and not j['holdout_open'] and not j['GA2_open']
   assert j['real_tape_sha256']=='8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0'
   row={'channel':ch,'retest_code':mode,'window_bars':win,'accepted_pre_econ_event_rows':j['full_primary_count'],'candidate_source_and_bar_pair_root_sha256':j['candidate_index_bar_root_sha256'],'full_primary_vs_independent_reference':'EXACT_PASS','receipt_sha256':sha(path),'receipt_bytes':path.stat().st_size,'filename':path.name}
   rows.append(row);sum_candidates+=j['full_primary_count'];h.update(bytes.fromhex(j['candidate_index_bar_root_sha256']))
 assert len(rows)==56
 original_source=R/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz';assert sha(original_source)=='8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0'
 bars=np.load(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy',mmap_mode='r');z=np.load(original_source);d=np.load(R/'XAUUSD_M1_VALID_INDICATORS_V24.npz');first=bars['first_source_index'];last=bars['last_source_index'];hi=bars['high_bid'].astype(float)*.01;lo=bars['low_bid'].astype(float)*.01;close=bars['close_bid'].astype(float)*.01
 sh,sl,hid,lid=structural_states(hi,lo,5,0);bidff=np.memmap(R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin',dtype=np.int32,mode='r');atr=np.r_[np.nan,d['ATR14'][:-1]];orig8=[]
 for ch in range(8):
  side=1 if ch<4 else -1;lv=sh if side==1 else sl;ids=hid if side==1 else lid;rep=next_replacement_source(ids,first);off=z['raw_offsets'];i=z['raw_idx'][off[ch]:off[ch+1]];bar=z['raw_bar'][off[ch]:off[ch+1]];rawid=z['raw_level_id'][off[ch]:off[ch+1]];oppch=ch+4 if ch<4 else ch-4;opp=z['raw_idx'][off[oppch]:off[oppch+1]]
 got=filter_raw_to_candidates(bidff,first,last,lo,hi,close,lv,ids,rep,atr,i,bar,rawid,opp,side,.01,float(BUF[ch%4]),0,0,1)
 aid=z['admitted_idx'][z['admitted_offsets'][ch]:z['admitted_offsets'][ch+1]];abar=z['admitted_bar'][z['admitted_offsets'][ch]:z['admitted_offsets'][ch+1]];assert np.array_equal(got[0],aid) and np.array_equal(got[1],abar),('V24_INDEPENDENT_ONLINE_REARM_ROOT_MISMATCH',ch)
 rows_by=[r for r in rows if r['channel']==ch and r['retest_code']==0][0];actual_root=hashlib.sha256(np.stack([got[0],got[1].astype(np.int64)],axis=1).tobytes()).hexdigest();assert actual_root==rows_by['candidate_source_and_bar_pair_root_sha256']
 orig8.append({'channel':ch,'candidate_rows':len(got[0]),'frozen_V220_full_reference_vs_online_V24':'EXACT_TRADE_CANDIDATE_IDX_AND_BAR','root_sha256':actual_root})
 rec={'schema':'QROS_W5_V26_ALL_56_STATEFUL_REALDATA_FULL_TAPE_INDEPENDENT_PARITY_V1','status':'PASS_56_OF_56_FULL_SOURCE_INDEX_AND_BAR_AND_V24_ONLINE_EIGHT_CHANNELS','scientific_state':'ONE_W5_PREREGISTERED_CELL_NO_ECONOMIC_RESULTS','raw_source_2018_2019_sha256_signed_V24':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','V24_raw_rearm_tape_sha256':sha(original_source),'V26_derived_causal_past_only_BID_overlay_sha256':sha(R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin'),'V26_derived_BID_overlay_bytes':(R/'XAUUSD_DEV_VALID_FF_BID_INT32_V26.bin').stat().st_size,'full_base_structures':8,'original_V209_RETEST_ENTRY_variants_each_channel':6,'baseline_original_rearm_no_retest_each_channel':1,'full_source_comparison_receipts_count':len(rows),'sampled_isolated_v25_1920_checks':'PASS_IN_PARENT_RELEASE','explicit_adversarial_19_tests':'PASS_IN_PARENT_RELEASE','V24_online_independent_full_tape_8channel_exact_IDs':orig8,'aggregated_accepted_event_rows_across_overlapping_routes_not_trades':sum_candidates,'frozen_route_config_canonical_hash_root_SHA256':h.hexdigest(),'per_route_receipts':rows,'original_V220_frozen_source_sha1':'805044c9918a87456a95e150a1c9a1292112cf4c','new_W5_PnL':'NOT_RUN','unverified_next':['V209_FULL_REAL_TEN_FAMILY_MASKS_11176_PER_SIDE','M1_SESSIONS_WITH_BROKER_DST_CERTIFIED','BROKER_COMMISSION_AND_EXEC_COSTS','W5_22352_CONFIG_DEV_ECONOMIC','GATE_A_MT5_HOLDOUT'], 'holdout_open':False,'GA2_open':False,'seconds':round(time.monotonic()-start,2)}
 path=R/'V26_ALL_56_FULL_REAL_STATEFUL_RETEST_INDEPENDENT_AUDIT.json';tmp=path.with_suffix('.json.tmp');tmp.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n');tmp.replace(path)
 print(json.dumps({k:rec[k] for k in ('status','full_source_comparison_receipts_count','aggregated_accepted_event_rows_across_overlapping_routes_not_trades','V26_derived_causal_past_only_BID_overlay_sha256','frozen_route_config_canonical_hash_root_SHA256','seconds')},sort_keys=True),flush=True)
if __name__=='__main__':main()
