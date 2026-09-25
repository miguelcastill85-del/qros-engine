#!/usr/bin/env python3
"""Independent read-back audit, ID parity, explicit exposure warning. No strategy selection."""
from __future__ import annotations
from pathlib import Path
import json,hashlib,os,math,csv,statistics
R=Path(__file__).resolve().parent
PIN={'BUY':'0dbaf56a5a8f0b1fce3b4c92fc44f0fc6146a237e9f23eaf6da75e4be82eecb5','SELL':'d2a130f42f4ab077437fe237363b863bf49c3631c2b9e482aa2121d93c9cc47b'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def atomic_json(p,x):
 t=p.with_suffix(p.suffix+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n');os.replace(t,p)
expected=json.load(open(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'));assert expected['semantic_configs_total']==22352
masks={};sem={'BUY':{},'SELL':{}};manifests=[];fail=[]
for ch in range(8):
 side='BUY' if ch<4 else 'SELL';src=R/f'V27_FULL10_PRE_ECON_CH{ch}';dst=R/f'V28_EXPOSED_DEV_SPREAD_ONLY_CH{ch}';m=json.load(open(dst/'ALL_ECONOMIC_ROUTES_MANIFEST.json'));s=json.load(open(src/'ALL_ROUTES_MANIFEST.json'))
 assert m['status']=='PASS_EXPLORATORY_DEV_SPREAD_INCLUDED_BROKER_COST_UNCERTIFIED' and m['source_full10_manifest_SHA256']==sha(src/'ALL_ROUTES_MANIFEST.json')
 assert m['semantic_configs']==s['packages'] and len(m['route_receipts'])==len(s['routes'])
 cids=set();physical_count_before=len(masks)
 for row in m['route_receipts']:
  key=row['route'];rr=dst/f'{key}_ECON_RECEIPT.json';receipt=json.load(open(rr));assert sha(rr)==row['receipt_sha256'] and receipt['route']==key and receipt['semantic_packages']==row['semantic_packages']
  for a in receipt['artifacts']:
   p=dst/a['name'];assert sha(p)==a['sha256'] and p.stat().st_size==a['bytes']
  phys=[json.loads(line) for line in (dst/f'{key}_ECON_PHYSICAL.jsonl').read_text().splitlines()];ss=[json.loads(line) for line in (dst/f'{key}_ECON_SEMANTIC.jsonl').read_text().splitlines()];source_phys=[json.loads(line) for line in (src/f'{key}_PHYSICAL.jsonl').read_text().splitlines()];source_sem=[json.loads(line) for line in (src/f'{key}_SEMANTIC.jsonl').read_text().splitlines()]
  assert len(phys)==len(source_phys)==receipt['physical_mask_occurrences'] and len(ss)==len(source_sem)==receipt['semantic_packages']
  for p,v in zip(phys,source_phys):
   pid=p['physical_mask_id'];assert pid==v['physical_mask_id'] and p['candidate_root_sha256']==v['candidate_root_sha256'] and p['side']==side
   metric=p['metrics'];assert metric['signal_count']==v['accepted_signal_count'] and metric['status'] in ('EXPLORATORY_DEV_ONLY_BROKER_COST_UNCERTIFIED','NO_SIGNALS')
   assert isinstance(metric['trades'],int) and metric['trades']>=0 and sum(metric['rejections'][:6])+metric['trades']<=metric['signal_count']
   assert metric['hypothetical_roundtrip_cost_5pts_R']<=metric['hypothetical_roundtrip_cost_2pts_R']+1e-7<=metric['gross_spread_only_R']+1e-7
   assert metric['DD_R']>=0 and math.isfinite(metric['gross_spread_only_R']) and math.isfinite(metric['DD_R'])
   if metric['trades']:
    assert metric['stops']+metric['flat_exits']==metric['trades']
    assert metric['years']['2018']['trades']+metric['years']['2019']['trades']==metric['trades']
    assert abs(sum(y['spread_only_R'] for y in metric['years'].values())-metric['gross_spread_only_R'])<1e-7
   if pid in masks:assert masks[pid]['metrics']==metric and masks[pid]['side']==side,('NON_IDEMPOTENT_SAME_MASK',pid)
   else:masks[pid]={'metrics':metric,'side':side}
  for a,b in zip(ss,source_sem):
   assert a['config_id']==b['config_id'] and a['config_index']==b['config_index'] and a['physical_mask_id']==b['physical_mask_id'] and a['channel']==ch
   i=a['config_index'];assert i not in sem[side],('DUPLICATE_SEMANTIC_ECONOMIC_CONFIG',side,i)
   sem[side][i]=a;assert a['physical_mask_id'] in masks;cids.add(i)
 assert len(cids)==m['semantic_configs'];manifests.append({'channel':ch,'side':side,'semantic_configs':len(cids),'unique_physical_new':len(masks)-physical_count_before,'SHA256':sha(dst/'ALL_ECONOMIC_ROUTES_MANIFEST.json'),'verified_route_receipts':len(m['route_receipts'])})
for side in PIN:
 assert set(sem[side])==set(range(11176))
 h=hashlib.sha256()
 for i in range(11176):h.update(bytes.fromhex(sem[side][i]['config_id']))
 assert h.hexdigest()==PIN[side]
h=hashlib.sha256()
for side in ('BUY','SELL'):
 for i in range(11176):h.update(bytes.fromhex(sem[side][i]['config_id']))
assert h.hexdigest()==expected['expected_full_original_ID_stream_SHA256']
assert len(masks)==expected['unique_physical_masks_across_all_routes']==14459 and sum(z['semantic_configs'] for z in manifests)==22352
counts={}
for side in ('BUY','SELL'):
 all_side=[row['metrics'] for row in masks.values() if row['side']==side]
 counts[side]={'semantic_configs_executed':11176,'unique_physical_masks':len(all_side),'zero_signals':sum(x['status']=='NO_SIGNALS' for x in all_side),'nonzero_signals_no_executed_trades':sum(x['signal_count']>0 and x['trades']==0 for x in all_side),'unique_masks_with_executed_trades':sum(x['trades']>0 for x in all_side),'commission_or_calendar_certified':False}
# Trade metrics per original semantic ID: no outcome optimization or selection, no USD conversions.
p=R/'V28_ALL_22352_EXPOSED_DEV_EXPLORATORY_COMPLETE_RESULTS.jsonl';tmp=p.with_suffix('.jsonl.partial')
with tmp.open('w') as f:
 for side in ('BUY','SELL'):
  for i in range(11176):
   x=sem[side][i];row={'config_index':i,'side':side,'semantic_config_id':x['config_id'],'physical_mask_id':x['physical_mask_id'],'channel':x['channel'],'route':x['route'],'metric_scope':'EXPOSED_DEV_2018_2019_SPREAD_INCLUDED_BROKER_COST_NOT_CERTIFIED','metrics':masks[x['physical_mask_id']]['metrics']}
   f.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
 f.flush();os.fsync(f.fileno())
os.replace(tmp,p)
r={'schema':'QROS_W5_V28_COMPLETE_22352_EXPOSED_DEV_ECONOMICS_INDEPENDENT_BYTE_AND_ID_AUDIT_V1','status':'PASS_COMPLETE_22352_EXPLORATORY_ONLY','original_semantic_ID_stream_SHA256':h.hexdigest(),'total_semantic_configs':22352,'total_distinct_physical_masks':14459,'raw_source_SHA256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','independent_full10_masks_root_SHA256':sha(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'),'execution_frozen_pre_PnL_SHA256':sha(R/'V28_EXPLORATORY_ECONOMIC_EXECUTION_FROZEN_BEFORE_PNL.json'),'source_code_frozen_pre_PnL_SHA256':sha(R/'V28_EXACT_ECONOMIC_RUNNER_CODE_PRE_PNL_FREEZE.json'),'real_independent_four_strata_canary_SHA256':sha(R/'V28_INDEPENDENT_EXANTE_STRATIFIED_REAL_TICK_TRADE_CANARY_RECEIPT.json'),'verified_economic_route_shards':sum(x['verified_route_receipts'] for x in manifests),'channels':manifests,'side_coverage':counts,'all_22352_semantic_result_rows_SHA256':sha(p),'all_22352_semantic_result_rows_bytes':p.stat().st_size,'only_exploratory_dev_2018_2019':True,'holdout_open':False,'GA2_open':False,'Gate_A_approved':False,'historical_broker_calendar_certified':False,'broker_commission_certified':False,'MT5_parity_pending':True,'not_portfolio_PnL':True,'no_new_alpha_approved':True}
out=R/'V28_INDEPENDENT_COMPLETE_EXPOSED_DEV_ECONOMIC_BYTE_ID_AUDIT.json';atomic_json(out,r)
print(json.dumps({'result':r['status'],'rows':r['total_semantic_configs'],'physical':r['total_distinct_physical_masks'],'verified_economic_route_shards':r['verified_economic_route_shards'],'side_coverage':counts,'results_sha256':r['all_22352_semantic_result_rows_SHA256'],'audit_receipt_sha256':sha(out)}))
