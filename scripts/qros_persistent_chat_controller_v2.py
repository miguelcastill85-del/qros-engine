#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any
HEAD_RE=re.compile(r'^QROS_PERSISTENT_CONTROL_HEAD_V(\d+)$');QUEUE_RE=re.compile(r'^QROS_PERSISTENT_RUN_QUEUE_V(\d+)$');SHA_RE=re.compile(r'^[0-9a-f]{64}$')
SAFE_GUARDS={'holdout_open_authorized':False,'mt5_authorized':False,'live_trading_authorized':False,'single_winner_selection':False,'all_gate_passers_advance':True,'branch_exhaustion_authorized':False}
ACTIVE={'READY','CAMPAIGN_ACTIVE','IN_PROGRESS','DEVELOPMENT_RUNNING','AUTHORIZED_NOT_STARTED'}
def load(p:Path)->dict[str,Any]:
 x=json.loads(p.read_text(encoding='utf-8'))
 if not isinstance(x,dict):raise ValueError(f'{p}: root must object')
 return x
def validate_control(protocol,head,state,queue,bundle=None):
 if protocol.get('schema')!='QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_V1_2':raise ValueError('protocol schema mismatch')
 if protocol.get('status')!='ADOPTED_MANDATORY_OPERATIONAL_LAYER':raise ValueError('protocol inactive')
 hm=HEAD_RE.fullmatch(str(head.get('schema','')));qm=QUEUE_RE.fullmatch(str(queue.get('schema','')))
 if not hm or not qm:raise ValueError('versioned HEAD/RUN_QUEUE schema required')
 hv=int(hm.group(1));qv=int(qm.group(1))
 if head.get('status')!='CONTROL_AND_SCIENTIFIC_CONTINUITY_AUTHORITY':raise ValueError('HEAD not authority')
 if state.get('schema')!='QROS_PERSISTENT_EXECUTION_STATE_V1' or state.get('enabled') is not True:raise ValueError('STATE invalid/disabled')
 if state.get('holdout_opened') is not False:raise ValueError('holdout exposed')
 if state.get('protocol_ref')!='governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.2.json':raise ValueError('STATE protocol_ref drift')
 if state.get('queue_ref')!='control/persistent_execution/RUN_QUEUE.json':raise ValueError('STATE queue_ref drift')
 if queue.get('source_head_schema')!=head.get('schema'):raise ValueError('queue/head schema mismatch')
 guards=queue.get('guards',{})
 for k,v in SAFE_GUARDS.items():
  if guards.get(k) is not v:raise ValueError(f'unsafe queue guard {k}')
 gov=head.get('governance',{})
 for k,v in {'all_gate_passers_advance':True,'single_winner_selection':False,'branch_exhaustion_authorized':False,'holdout_open_authorized':False,'mt5_authorized':False}.items():
  if gov.get(k) is not v:raise ValueError(f'unsafe HEAD governance {k}')
 epochs=[head.get('control_epoch'),state.get('control_epoch'),queue.get('control_epoch')]
 if any(not isinstance(x,int) for x in epochs) or len(set(epochs))!=1:raise ValueError(f'control_epoch mismatch {epochs}')
 bundles=[head.get('control_bundle_ref'),state.get('control_bundle_ref'),queue.get('control_bundle_ref')]
 if any(not isinstance(x,str) or not x for x in bundles) or len(set(bundles))!=1:raise ValueError('control_bundle_ref mismatch')
 if bundle is not None:
  if bundle.get('schema')!='QROS_CONTROL_BUNDLE_MANIFEST_V1':raise ValueError('bundle schema mismatch')
  if bundle.get('control_epoch')!=epochs[0]:raise ValueError('bundle epoch mismatch')
  if bundle.get('bundle_ref')!=bundles[0]:raise ValueError('bundle self ref mismatch')
  if bundle.get('status')!='ACTIVE_VERIFIED':raise ValueError('bundle not active verified')
 if head.get('durability_enforcement_ref')!='governance/QROS_DURABLE_EXECUTION_AND_RECOVERY_ENFORCEMENT_v1.json':raise ValueError('HEAD durability enforcement missing')
 if state.get('durability_enforcement_ref')!=head.get('durability_enforcement_ref') or queue.get('durability_enforcement_ref')!=head.get('durability_enforcement_ref'):raise ValueError('durability enforcement ref drift')
 for item in queue.get('queue',[]):
  if not isinstance(item,dict) or not item.get('item_id') or not item.get('scope') or not item.get('status'):raise ValueError('queue item missing identity/scope/status')
  if item['status'] in ACTIVE:
   if item.get('durability_gate_status')!='PASS':raise ValueError(f"{item['item_id']}: active item without durability PASS")
   if not item.get('durability_gate_ref'):raise ValueError(f"{item['item_id']}: active item durability receipt missing")
 if head.get('scientific_head',{}).get('state')=='DEVELOPMENT_RUNNING' and queue.get('next_item'):
  ids={i.get('item_id') for i in queue.get('queue',[])}
  if queue['next_item'] not in ids:raise ValueError('next_item not in queue')
 return {'head_version':hv,'queue_version':qv,'control_epoch':epochs[0],'bundle_ref':bundles[0]}
def validate_checkpoint(cp):
 if cp.get('schema')!='QROS_DURABLE_CHECKPOINT_RECEIPT_V1':raise ValueError('checkpoint schema mismatch')
 if cp.get('status') not in {'COMPLETED','PENDING_RESUMABLE','CONTROL_CANARY'}:raise ValueError('checkpoint status invalid')
 if cp.get('holdout_exposure')!='SEALED_NO_ACCESS':raise ValueError('checkpoint holdout exposure invalid')
 if cp.get('partial_without_receipt_policy')!='QUARANTINE':raise ValueError('partial policy invalid')
 rr=cp.get('completed_ranges')
 if not isinstance(rr,list):raise ValueError('completed_ranges must list')
 last=None
 for r in rr:
  if not isinstance(r,list) or len(r)!=2 or not all(isinstance(x,int) for x in r) or r[0]>=r[1]:raise ValueError('invalid checkpoint range')
  if last is not None and r[0]!=last:raise ValueError('checkpoint ranges not contiguous')
  last=r[1]
 for name,v in cp.get('input_and_source_sha256',{}).items():
  if not isinstance(v,str) or not SHA_RE.fullmatch(v):raise ValueError(f'invalid checkpoint sha {name}')
 return {'range_end':last,'range_count':len(rr)}
def selftest():
 protocol={'schema':'QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_V1_2','status':'ADOPTED_MANDATORY_OPERATIONAL_LAYER'};ref='control/persistent_execution/CONTROL_BUNDLE_V176.json';dur='governance/QROS_DURABLE_EXECUTION_AND_RECOVERY_ENFORCEMENT_v1.json'
 head={'schema':'QROS_PERSISTENT_CONTROL_HEAD_V176','status':'CONTROL_AND_SCIENTIFIC_CONTINUITY_AUTHORITY','control_epoch':176,'control_bundle_ref':ref,'durability_enforcement_ref':dur,'governance':{'all_gate_passers_advance':True,'single_winner_selection':False,'branch_exhaustion_authorized':False,'holdout_open_authorized':False,'mt5_authorized':False},'scientific_head':{'state':'DEVELOPMENT_RUNNING'}}
 state={'schema':'QROS_PERSISTENT_EXECUTION_STATE_V1','enabled':True,'holdout_opened':False,'protocol_ref':'governance/QROS_PERSISTENT_CHAT_EXECUTION_PROTOCOL_v1.2.json','queue_ref':'control/persistent_execution/RUN_QUEUE.json','control_epoch':176,'control_bundle_ref':ref,'durability_enforcement_ref':dur}
 queue={'schema':'QROS_PERSISTENT_RUN_QUEUE_V176','source_head_schema':head['schema'],'control_epoch':176,'control_bundle_ref':ref,'durability_enforcement_ref':dur,'guards':dict(SAFE_GUARDS),'queue':[{'item_id':'X','scope':'TEST','status':'CAMPAIGN_ACTIVE','durability_gate_status':'PASS','durability_gate_ref':'r'}],'next_item':'X'}
 bundle={'schema':'QROS_CONTROL_BUNDLE_MANIFEST_V1','status':'ACTIVE_VERIFIED','control_epoch':176,'bundle_ref':ref};tests=[]
 validate_control(protocol,head,state,queue,bundle);tests.append(('PASS_VERSIONED_CONTROL',True))
 import copy
 for name,mut in [('REJECT_EPOCH_DRIFT',lambda q:q.update(control_epoch=175)),('REJECT_ACTIVE_WITHOUT_DURABILITY',lambda q:q['queue'][0].update(durability_gate_status='UNPROVEN')),('REJECT_HOLDOUT',lambda q:q['guards'].update(holdout_open_authorized=True))]:
  q=copy.deepcopy(queue);mut(q)
  try:validate_control(protocol,head,state,q,bundle);tests.append((name,False))
  except ValueError:tests.append((name,True))
 cp={'schema':'QROS_DURABLE_CHECKPOINT_RECEIPT_V1','status':'PENDING_RESUMABLE','holdout_exposure':'SEALED_NO_ACCESS','partial_without_receipt_policy':'QUARANTINE','completed_ranges':[[0,100],[100,200]],'input_and_source_sha256':{'x':'0'*64}}
 validate_checkpoint(cp);tests.append(('PASS_CHECKPOINT_CONTIGUOUS',True));bad=copy.deepcopy(cp);bad['completed_ranges']=[[0,100],[101,200]]
 try:validate_checkpoint(bad);tests.append(('REJECT_CHECKPOINT_GAP',False))
 except ValueError:tests.append(('REJECT_CHECKPOINT_GAP',True))
 return {'schema':'QROS_PERSISTENT_CHAT_CONTROLLER_V2_SELFTEST','status':'PASS' if all(p for _,p in tests) else 'FAIL','tests':[{'name':n,'pass':p} for n,p in tests]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('command',choices=['validate','checkpoint-validate','selftest']);ap.add_argument('--protocol',type=Path);ap.add_argument('--head',type=Path);ap.add_argument('--state',type=Path);ap.add_argument('--queue',type=Path);ap.add_argument('--bundle',type=Path);ap.add_argument('--checkpoint',type=Path);a=ap.parse_args()
 if a.command=='selftest':res=selftest()
 elif a.command=='checkpoint-validate':res={'schema':'QROS_CONTROLLER_V2_RESULT','status':'PASS',**validate_checkpoint(load(a.checkpoint))}
 else:res={'schema':'QROS_CONTROLLER_V2_RESULT','status':'PASS',**validate_control(load(a.protocol),load(a.head),load(a.state),load(a.queue),load(a.bundle) if a.bundle else None)}
 print(json.dumps(res,sort_keys=True,separators=(',',':')));return 0 if res['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
