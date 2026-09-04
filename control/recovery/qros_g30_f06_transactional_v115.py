#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f05_transactional_v114 as base
import qros_g30_f06_signal_primary_v115 as sa
import qros_g30_f06_signal_independent_v115 as sb

base.sa=sa;base.sb=sb;base.EXPECTED_RAW=1026

def specs():
 for wick in sa.WICK:
  for timing in sa.TIM:
   for t in sa.TH:
    for fam in sa.FAMS:
     for n in sa.NS:yield (wick,timing,t,fam,n)
    yield (wick,timing,t,'SHOCK_BAR_BODY_DIRECTION_ONLY',1)
def spec_key(sp):
 wick,timing,t,fam,n=sp
 return f'{wick}|{timing}|{t:g}|{fam}|{n}'
base.specs=specs;base.spec_key=spec_key

def prepare(a):return base.prepare(a)
def score(a):return base.score(a)
def merge(a):
 root=a.work;meta=json.loads((root/'manifest.json').read_text());chunks=[json.loads(Path(p).read_text()) for p in a.chunks];chunks.sort(key=lambda x:x['start']);cur=0;records=[];passers=[]
 for c in chunks:
  if c['start']!=cur:raise SystemExit(f'CHUNK_GAP expected={cur} got={c["start"]}')
  cur=c['end'];records.extend(c['records']);passers.extend(c['passers'])
 if cur!=meta['unique_masks']:raise SystemExit(f'INCOMPLETE {cur}/{meta["unique_masks"]}')
 obj={'schema':'QROS_G30_F06_GATE_A_SHARD_V115_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F06_WICK','asset':meta['asset'],'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':meta['shard'],'bars':meta['bars'],'raw_identities':meta['raw_identities'],'unique_masks':meta['unique_masks'],'exact_alias_count':meta['exact_alias_count'],'evaluated_configurations':len(records),'bar_digest':meta['bar_digest'],'raw_identity_sequence_sha256':meta['raw_identity_sequence_sha256'],'unique_mask_set_sha256':meta['unique_mask_set_sha256'],'union_buy':meta['union_buy'],'union_sell':meta['union_sell'],'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','signal_atr':{'period':14,'smoothing':'SMA_TR','reference_timing':['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']},'wick_filter':['MAX_OPPOSING_WICK_50PCT_RANGE','MAX_OPPOSING_WICK_33PCT_RANGE','MAX_OPPOSING_WICK_20PCT_RANGE'],'management':{'stop_atr_period':14,'stop_atr_smoothing':'SMA_TR','atr_stop_mult':3.0,'reward_r_multiple':1.5,'time_stop_bars':20},'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
 a.out.write_text(json.dumps(base.safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['asset','shard','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','signal_parity','trade_parity']},sort_keys=True),flush=True)

def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
 p=sub.add_parser('prepare');p.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);p.add_argument('--feature-side',choices=['BID','MID'],required=True);p.add_argument('--work',type=Path,required=True)
 p=sub.add_parser('score');p.add_argument('--work',type=Path,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--out',type=Path,required=True)
 p=sub.add_parser('merge');p.add_argument('--work',type=Path,required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();{'prepare':prepare,'score':score,'merge':merge}[a.cmd](a)
if __name__=='__main__':main()
