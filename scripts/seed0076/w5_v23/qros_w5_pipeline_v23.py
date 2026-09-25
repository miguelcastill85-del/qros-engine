#!/usr/bin/env python3
"""Bind exactly one W5 prereg to QROS v2.2 bounded failover, then auto-resume ready jobs.
Runs only within current invocation. Never treats synthetic PASS as market-data PASS.
"""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,shutil,sys,time,subprocess
SRC=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(SRC/'anti_stall'/'scripts'))
from qros_continuation_dispatch_v2_2 import dispatch
from qros_anti_stall_v2_1 import sha_file,blob_sha,Incident,invoke,check_bytes,load_state
ROOT_REPO='miguelcastill85-del/qros-engine'
LANE='research/seed0076-direct-dev-backtest-20260922'
BASE='6a4ce532764e685b7a264c9ccac9b7f7bf20bfd3'
ORIG_POINTER_BLOB='8370decb2c8e033c4b60662e72f03b22516ae899'
PREREG_BLOB='40275ce4fc0454759a181d9e3d7e8757630134da'
ARCHIVE_SHA='a50def21191fe6f59ac5c52a0ceda92dd4aeba7ac36a24eb4addb92377509e39'
GOLDEN='2f0a7190967cb2f4a5abefd55a9e0c5e16a5aca590ba133adb680cc765c2f94f'
BUDGET_WALL=120

def write_atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);data=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False).encode()+b'\n';tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(data);os.replace(tmp,path)
def pinned_src():
 # Corpus pins are published in signed source package. Full original V209/V220/V221 hash proof is checked again in the stage itself.
 files=['qros_w5_pre_econ_v1.py','qros_w5_source_tests_v1.py','qros_w5_mtf_causal_adapter_v1.py','qros_w5_stage_entry_v1.py','anti_stall/scripts/qros_progress_watchdog_v2_2.py']
 for path in (SRC/'legacy'/'source_pins').iterdir():
  if path.is_file():files.append('legacy/source_pins/'+path.name)
 for path in (SRC/'v209').iterdir():
  if path.name in ('FROZEN_ORIGINAL_V209_SPEC.json','BUY_CONFIG_IDS_11176.bin','SELL_CONFIG_IDS_11176.bin','PREREG_W5_ASYM_REARM0_TICK_FULL_V209.json'):
   files.append('v209/'+path.name)
 return sorted(files)
def build(base):
 base=pathlib.Path(base).resolve();base.mkdir(parents=True,exist_ok=True)
 stage=base/'W5_PRE_ECON_SYNTH';stage.mkdir(exist_ok=True)
 src_files=pinned_src();pins=[]
 for rel in src_files:
  source=SRC/rel;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  expected=sha_file(source)
  if dest.exists():
   if sha_file(dest)!=expected:raise Incident('PREEXISTING_CORPUS_BYTES_DRIFT:'+rel)
  else:shutil.copyfile(source,dest)
  pins.append({'path':rel,'bytes':dest.stat().st_size,'sha256':expected})
 authority={'repo':ROOT_REPO,'branch':LANE,'base_commit':BASE,'scientific_pointer_git_blob_sha1':ORIG_POINTER_BLOB,'prereg_git_blob_sha1':PREREG_BLOB,'prereg_archive_sha256':ARCHIVE_SHA}
 route1={'name':'FROZEN_NUMBA_AND_INDEPENDENT_ORACLES','argv':[sys.executable,'anti_stall/scripts/qros_progress_watchdog_v2_2.py','--work',str(stage),'--wall','42','--idle','28','--',sys.executable,'qros_w5_stage_entry_v1.py','--backend','numba','--out','PRE_ECON_SYNTH_RECEIPT.json']}
 route2={'name':'FROZEN_PYTHON_AND_INDEPENDENT_ORACLES','argv':[sys.executable,'anti_stall/scripts/qros_progress_watchdog_v2_2.py','--work',str(stage),'--wall','42','--idle','28','--',sys.executable,'qros_w5_stage_entry_v1.py','--backend','python','--out','PRE_ECON_SYNTH_RECEIPT.json']}
 stage_data={'id':'W5_SYNTHETIC_SOURCE_PRE_ECON','kind':'local','timeout_seconds':100,'inputs':pins,'outputs':[{'path':'PRE_ECON_SYNTH_RECEIPT.json','bytes':2108,'sha256':GOLDEN}], 'routes':[route1,route2]}
 plan={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'SEED0076_W5_ASYM_TICK_FULL_V209','authority':authority,'scientific_firewalls':{'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False},'stages':[stage_data]}
 plan_path=stage/'FROZEN_PLAN.json';fresh=json.dumps(plan,sort_keys=True,indent=2).encode()+b'\n'
 if plan_path.exists() and plan_path.read_bytes()!=fresh:raise Incident('PREEXISTING_FROZEN_PLAN_DRIFT')
 if not plan_path.exists():plan_path.write_bytes(fresh)
 # Stage 2 is external and explicitly blocked, requiring authenticated original raw-tick and cache byte checks before economic start.
 ext=base/'W5_REALDATA_EXTERNAL';ext.mkdir(exist_ok=True)
 external={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':plan['lane_id'],'authority':authority,'scientific_firewalls':plan['scientific_firewalls'],
 'stages':[{'id':'W5_REALDATA_EXACT_BYTES_AND_BROKER_CLOCK','kind':'external','anchor_git_blob_sha1':'4d582962ea40759d4245cb89aa0482b20467f6b4',
 'remote_id':'1TUXhmVS9QYwCU9xnmA7EvUIPaxfakwYm','outputs':[{'path':'W5_REALDATA_GATE_RECEIPT.json','bytes':None,'sha256':None}]}]}
 extplan=ext/'EXTERNAL_PLAN.json';extbytes=json.dumps(external,sort_keys=True,indent=2).encode()+b'\n'
 if extplan.exists() and extplan.read_bytes()!=extbytes:raise Incident('EXTERNAL_PLAN_DRIFT')
 if not extplan.exists():extplan.write_bytes(extbytes)
 jobs=[{'id':'W5_SYNTHETIC_SOURCE_PRE_ECON','work':str(stage),'plan':str(plan_path),'plan_sha256':sha_file(plan_path),'kind':'local','hard_route_seconds':120,'max_distinct_routes':2,'depends_on':[]},
 {'id':'W5_REALDATA_EXACT_BYTES_AND_BROKER_CLOCK','work':str(ext),'plan':str(extplan),'plan_sha256':sha_file(extplan),'kind':'external','hard_route_seconds':120,'max_distinct_routes':1,'depends_on':['W5_SYNTHETIC_SOURCE_PRE_ECON']}]
 queue={'schema':'QROS_BOUNDED_CONTINUATION_QUEUE_V2_2','authority':authority,'control_root':str(base/'control'),'jobs':jobs}
 qpath=base/'W5_EXACT_FROZEN_QUEUE.json';qbytes=json.dumps(queue,sort_keys=True,indent=2).encode()+b'\n'
 if qpath.exists() and qpath.read_bytes()!=qbytes:raise Incident('PREEXISTING_FROZEN_QUEUE_DRIFT')
 if not qpath.exists():qpath.write_bytes(qbytes)
 freeze={'schema':'QROS_SEED0076_W5_V23_CAMPAIGN_BOUND_QUEUE_PIN','status':'FROZEN_QUEUE_NO_ECONOMIC_EXECUTION',
         'frozen_original_pointer_blob':ORIG_POINTER_BLOB,'frozen_prereg_blob':PREREG_BLOB,'base_commit':BASE,'queue_sha256':sha_file(qpath),'local_plan_sha256':jobs[0]['plan_sha256'],
         'external_plan_sha256':jobs[1]['plan_sha256'],'expected_synthetic_receipt_sha256':GOLDEN,'source_corpus':pins,
         'raw_required_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
         'bars_required_sha256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56bbb8a71a7457f59',
         'indicator_required_sha256':'f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5',
         'realdata_mount_state':'UNVERIFIED_MUST_REHASH_BEFORE_USE','holdout_open':False,'ga2_open':False}
 fp=base/'W5_QUEUE_EXTERNAL_PIN.json'
 if fp.exists() and json.loads(fp.read_bytes())!=freeze:raise Incident('PREEXISTING_EXTERNAL_PIN_DRIFT')
 if not fp.exists():write_atomic(fp,freeze)
 return fp

def run(base,budget):
 base=pathlib.Path(base).resolve();lock=json.loads((base/'W5_QUEUE_EXTERNAL_PIN.json').read_bytes());queue_file=base/'W5_EXACT_FROZEN_QUEUE.json'
 if sha_file(queue_file)!=lock['queue_sha256']:raise Incident('EXTERNAL_QUEUE_PIN_MISMATCH')
 deadline=time.monotonic()+budget;events=[];passes=0
 while time.monotonic()<deadline:
  remaining=deadline-time.monotonic()
  if remaining<10:break
  receipt=dispatch(queue_file,lock['queue_sha256'],min(remaining,180));events.append(receipt)
  if receipt['status']!='ONE_VERIFIED_STAGE_PASS':
   interrupted=[e for e in receipt.get('events',[]) if e.get('action')=='INTERRUPTED_NEEDS_INDEPENDENT_RECOVERY']
   if interrupted:
    frozen=json.loads(queue_file.read_bytes())
    for event in interrupted:
     job=next(j for j in frozen['jobs'] if j['id']==event['job'])
     if job['kind']!='local':continue
     stage=pathlib.Path(job['work']);plan=json.loads(pathlib.Path(job['plan']).read_bytes())
     try:
      for item in plan['stages'][0]['inputs']+plan['stages'][0]['outputs']:
       check_bytes(stage,item,True)
      result=invoke(stage,job['plan'],job['plan_sha256'],'recover')
      if result['status']=='ONE_STAGE_RECOVERED':
       events.append({'status':'INDEPENDENT_PINNED_OUTPUT_RECOVERED','job':job['id'],'proof':result})
       passes+=1
       break
     except Exception as exc:
      events.append({'status':'INTERRUPTED_RECOVERY_FAIL_CLOSED','job':job['id'],'reason':str(exc)})
      continue
    else:break
    continue
   break
  passes+=1
  if passes>len(json.loads(queue_file.read_bytes())['jobs']):raise Incident('IMPOSSIBLE_PASS_COUNT')
 result={'schema':'QROS_SEED0076_W5_V23_BOUNDED_CONTINUATION_RECEIPT','status':'SYNTHETIC_GATE_PASS_DATA_EXACT_BYTES_PENDING' if passes and len(events)>1 else ('SYNTHETIC_GATE_PASS_MORE_READY_WORK' if passes else 'SAFE_DEFER'),
 'stages_promoted_this_invocation':passes,'events':events,'queue_sha256':lock['queue_sha256'],'holdout_open':False,'ga2_open':False,'PnL_read':False,
 'latest_external_gate':'EXACT_REALDATA_MOUNT_AND_BROKER_CALENDAR_REQUIRED',
 'MTF_original_v221_issue':'CORRECTED_ADAPTER_TESTED_SYNTHETICALLY_ONLY',
 'economic_gate':'CLOSED_BEFORE_REAL_TICK_AND_FILTER_PARITY'}
 write_atomic(base/'QROS_W5_CONTINUATION_RESULT.json',result);return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('verb',choices=('bootstrap','run','status'));parser.add_argument('--root',required=True);parser.add_argument('--budget',type=int,default=120)
 args=parser.parse_args()
 try:
  if args.verb=='bootstrap':print(json.dumps({'pin':str(build(args.root))}))
  elif args.verb=='run':print(json.dumps(run(args.root,args.budget),sort_keys=True))
  else:
   base=pathlib.Path(args.root);p=json.loads((base/'W5_QUEUE_EXTERNAL_PIN.json').read_bytes());print(json.dumps({'pin':p,'result':json.loads((base/'QROS_W5_CONTINUATION_RESULT.json').read_bytes()) if (base/'QROS_W5_CONTINUATION_RESULT.json').exists() else None}))
 except Exception as exc:
  print(json.dumps({'status':'FAIL_CLOSED','error':str(exc)}),file=sys.stderr);raise SystemExit(3)
if __name__=='__main__':main()
