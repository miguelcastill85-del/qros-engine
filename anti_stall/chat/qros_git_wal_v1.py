#!/usr/bin/env python3
"""QROS Git WAL v1: deterministic fail-closed state machine for per-turn Git publication.

This is the control plane: it does NOT fabricate original V33 parity results, fetch
private market carriers, or run after a ChatGPT turn. Its commands produce byte-exact
immutable events and live-index transitions for one Git tree/commit CAS at a time.
Caller must independently obtain live branch and scientific pointer from GitHub.
"""
from __future__ import annotations
import argparse, hashlib, io, json, pathlib, re, sys, zipfile
from typing import Any

BASELINE_SHA='d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05'
PLAN_SHA='2be3c09dbcf80576125187f45ae9e7c8ce265a67bab6170a3809adb6a464dc0c'
RUNNER_SHA='d545f846a09dc2059193c5a9a6703235bf9f27554ac802eafdf4c032b5a501bf'
RAW_SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
CHANNEL_SHA={0:'196de55420e5c29f3ef776d32179842309826585e2fd7d6580fe73f95561ffa2',4:'79d30dd8c734c845025583261fd50bd88392c0ce03d21764f8d82eb4d351ea76'}
BRANCH='research/seed0076-direct-dev-backtest-20260922'
H40=re.compile(r'^[0-9a-f]{40}$');H64=re.compile(r'^[0-9a-f]{64}$')
NAME=re.compile(r'^CH([04])_([A-Za-z0-9_]+)_I(\d{3})_(\d{3})\.json$')
SCHEMA='QROS_W5_GITHUB_WAL_INDEX_V1';EV_SCHEMA='QROS_W5_GITHUB_WAL_EVENT_V1'

class Stop(ValueError):pass

def require(test,message):
    if not test:raise Stop(message)
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def gb(b:bytes)->str:return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def jsonbytes(o:dict)->bytes:return (json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def taskid(task:dict)->str:
    c=task.get('ch',task.get('channel'))
    require(c in (0,4),'INVALID_CHANNEL')
    r=task['route'];ordinals=task['ordinals']
    require(isinstance(r,str) and re.fullmatch('[A-Za-z0-9_]+',r) is not None,'BAD_ROUTE')
    require(isinstance(ordinals,list) and len(ordinals)>0 and all(type(x)==int and x>=0 for x in ordinals),'BAD_ORDINALS')
    require(ordinals==sorted(set(ordinals)),'NONMONOTONIC_OR_DUPLICATE_ORDINALS')
    return f'CH{c}_{r}_I{ordinals[0]:03d}_{ordinals[-1]:03d}.json'
def checked_source_file(path,pin):
    require(isinstance(pin,str) and H64.fullmatch(pin) is not None,'INVALID_SHA256_PIN')
    h=hashlib.sha256();length=0
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk);length+=len(chunk)
    require(h.hexdigest()==pin,'INPUT_BYTES_SHA256_DRIFT:'+str(path));return length

def audit_baseline(path:str)->dict:
    checked_source_file(path,BASELINE_SHA)
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(set(names))==len(names),'DUPLICATE_ZIP_NAMES')
        require(z.testzip() is None,'ZIP_CRC_DRIFT')
        for name in names:
            require(not name.startswith('/') and '\\' not in name and '..' not in name.split('/') and '' not in name.split('/'),'ZIP_PATH_UNSAFE')
        mraw=z.read('MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json');m=json.loads(mraw)
        entries=m['files'];require(len(entries)==len(names)-1,'MANIFEST_CARDINALITY_DRIFT')
        require(set(names)=={x['name'] for x in entries}|{'MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json'},'MANIFEST_NAME_DRIFT')
        for f in entries:
            data=z.read(f['name']);require(len(data)==f['bytes'] and sha(data)==f['sha256'],'MANIFEST_MEMBER_SHA_DRIFT:'+f['name'])
        planraw=z.read('FROZEN_PLAN/V33_FROZEN_REMAINING_ALL_MASK_PLAN.json')
        runnerraw=z.read('SOURCE/v33_run_frozen_remaining_large_mask_parity.py')
        require(sha(planraw)==PLAN_SHA and sha(runnerraw)==RUNNER_SHA,'FROZEN_PLAN_OR_RUNNER_DRIFT')
        plan=json.loads(planraw);tasks=plan['frozen_tasks'];require(len(tasks)==710,'FROZEN_TASKS_NOT_710')
        tasknames=[taskid(x) for x in tasks];require(len(tasknames)==len(set(tasknames)),'DUPLICATE_FROZEN_TASK')
        master=json.loads(z.read('MASTER/V33_PARTIAL_MASTER_RECEIPT.json'))
        require(master['completed_shards']==446 and master['pending_shards']==264,'BASELINE_COUNT_DRIFT')
        require(master['original_raw_sha256']==RAW_SHA and master['frozen_plan_sha256']==PLAN_SHA and master['source_runner_sha256']==RUNNER_SHA,'BASELINE_SOURCE_DRIFT')
        for flag in ('Gate_A_approved','holdout_open','ga2_open'):
            require(master.get(flag) is False,'BASELINE_FIREWALL_DRIFT')
        receipts={name[9:]:z.read(name) for name in names if name.startswith('RECEIPTS/')}
        require(len(receipts)==446 and len(master['receipt_byte_manifest'])==446,'BASELINE_RECEIPT_COUNT_DRIFT')
        rec_ids=set()
        for row in master['receipt_byte_manifest']:
            name=row['filename'];raw=receipts.get(name)
            require(raw is not None and sha(raw)==row['sha256'],'BASELINE_RECEIPT_SHA_DRIFT:'+name)
            o=json.loads(raw);tid=taskid(o)
            require(tid==name and tid in tasknames and tid not in rec_ids,'BASELINE_UNFROZEN_DUPLICATE_OR_NAME_DRIFT')
            require(o.get('status')=='PASS' and o.get('new_economic_PNL') is False and o['plan_SHA256']==PLAN_SHA and o['original_raw_sha256']==RAW_SHA,'BASELINE_RECEIPT_UNPROVEN')
            for flag in ('Gate_A_approved','holdout_open','ga2_open'):require(o.get(flag) is False,'BASELINE_RECEIPT_GATE_DRIFT')
            verify_receipt_full(o,name);rec_ids.add(tid)
        require(set(receipts)==rec_ids,'BASELINE_LEDGER_MEMBERSHIP_DRIFT')
        return {'baseline_sha256':BASELINE_SHA,'baseline_git_blob_sha1':gb(pathlib.Path(path).read_bytes()),'plan_sha256':PLAN_SHA,'runner_sha256':RUNNER_SHA,'raw_sha256':RAW_SHA,'verified_receipts':446,'manifest_member_count':len(entries),'tasks':tasks,'closed':rec_ids,'manifest_sha256':sha(mraw)}

def next_tasks(audit:dict,closed:set[str],n=6,channel=0)->list[str]:
    require(1<=n<=6 and channel in (0,4),'INVALID_BOUNDED_REQUEST')
    ordered=[taskid(t) for t in audit['tasks'] if t['ch']==channel and taskid(t) not in closed]
    return ordered[:n]

def check_live(pointer_bytes:bytes,pointer_sha:str,audit:dict,count:int):
    require(H40.fullmatch(pointer_sha) is not None and gb(pointer_bytes)==pointer_sha,'LIVE_POINTER_GIT_SHA1_DRIFT')
    p=json.loads(pointer_bytes)
    require(p['branch']==BRANCH and p['scientific_state']=='DEVELOPMENT_RUNNING','SCIENTIFIC_AUTHORITY_OR_STATE_DRIFT')
    require(p['v33_shards_completed']==count and p['v33_shards_remaining']==710-count,'LIVE_SCIENTIFIC_CURSOR_DRIFT')
    for flag in ('Gate_A_approved','holdout_open','ga2_open'):require(p.get(flag) is False,'LIVE_FIREWALL_DRIFT:'+flag)
    require(p['v33_original_frozen_queue_sha256']==audit['plan_sha256'],'ORIGINAL_QUEUE_DRIFT')
    return p

def bootstrap(audit:dict,pointer_bytes:bytes,pointer_sha:str)->tuple[dict,dict]:
    p=check_live(pointer_bytes,pointer_sha,audit,446)
    e={'schema':EV_SCHEMA,'seq':0,'phase':'BASELINE','parent_event_sha256':'0'*64,
       'checkpoint':446,'baseline_zip_sha256':audit['baseline_sha256'],
       'baseline_git_blob_sha1':audit['baseline_git_blob_sha1'],
       'frozen_plan_sha256':audit['plan_sha256'],
       'scientific_pointer_blob_sha1':pointer_sha,
       'scientific_target_blob_sha1':p['target_git_blob_sha1'],
       'scientific_anchor_blob_sha1':p['last_closed_remote_anchor_blob_sha1'],
       'manifest_sha256':audit['manifest_sha256'],
       'original_closed_receipts_sha256':sha(jsonbytes({'ids':sorted(audit['closed'])})),
       'economics_changed':False}
    l={'schema':SCHEMA,'version':'1.0','branch':BRANCH,'phase':'READY','generation':0,
       'event_sha256':sha(jsonbytes(e)),'baseline_zip_sha256':audit['baseline_sha256'],
       'baseline_git_blob_sha1':audit['baseline_git_blob_sha1'],
       'plan_sha256':audit['plan_sha256'],'runner_sha256':audit['runner_sha256'],
       'raw_sha256':audit['raw_sha256'],'completed':446,'remaining':264,
       'scientific_pointer_blob_sha1':pointer_sha,'active_claim':None,
       'delta_tip_sha256':audit['baseline_sha256'],'closed_delta_ids':[],
       'next_CH0':next_tasks(audit,audit['closed'],6,0),
       'next_CH4':next_tasks(audit,audit['closed'],6,4),
       'scientific_firewalls':{'Gate_A_approved':False,'holdout_open':False,'ga2_open':False},
       'git_cas':'NON_FORCE_FF_ONLY_AND_REMOTE_BLOB_READBACK'}
    return l,e

def validate_ledger(ledger:dict,event:dict,audit:dict):
    require(ledger.get('schema')==SCHEMA and event.get('schema')==EV_SCHEMA,'WAL_SCHEMA_INVALID')
    require(sha(jsonbytes(event))==ledger['event_sha256'] and ledger['generation']==event['seq'],'WAL_EVENT_HASH_OR_SEQUENCE_DRIFT')
    require(ledger['baseline_zip_sha256']==audit['baseline_sha256'] and ledger['plan_sha256']==audit['plan_sha256'] and ledger['runner_sha256']==audit['runner_sha256'],'WAL_SOURCE_DRIFT')
    require(ledger['completed']+ledger['remaining']==710 and ledger['completed']>=446,'WAL_COUNTS_DRIFT')
    all_frozen={taskid(t) for t in audit['tasks']}
    deltas=ledger.get('closed_delta_ids')
    require(isinstance(deltas,list) and len(deltas)==ledger['completed']-446 and len(set(deltas))==len(deltas) and set(deltas)<=all_frozen-audit['closed'],'WAL_DELTA_SET_INCONSISTENT')
    closed=audit['closed']|set(deltas)
    require(ledger['next_CH0']==next_tasks(audit,closed,6,0) and ledger['next_CH4']==next_tasks(audit,closed,6,4),'WAL_CURSOR_DRIFT')
    require(event.get('phase') in ('BASELINE','CLAIM','COMMIT','BLOCKED'),'WAL_EVENT_PHASE_UNRECOGNIZED')
    require((ledger['phase']=='READY') == (ledger['active_claim'] is None),'WAL_ACTIVE_CLAIM_INCONSISTENT')
    if ledger['phase']=='READY':require(event['phase'] in ('BASELINE','COMMIT'),'WAL_READY_ILLEGAL_PREDECESSOR')
    if ledger['phase']=='CLAIMED':require(event['phase']=='CLAIM' and ledger['active_claim']['task_ids']==event['task_ids'],'WAL_CLAIM_INCONSISTENT')
    if ledger['phase']=='BLOCKED':require(event['phase']=='BLOCKED','WAL_BLOCKED_INCONSISTENT')
    for flag in ledger['scientific_firewalls']:require(ledger['scientific_firewalls'][flag] is False,'WAL_FIREWALL_CHANGED')

def verified_input_manifest(audit:dict,channel:int,paths:dict)->dict:
    require(channel in (0,4),'BAD_CHANNEL')
    required={'raw_ticks':RAW_SHA,'channel_tape_zip':CHANNEL_SHA[channel]}
    require(set(paths)==set(required),'EXACT_INPUT_KEYS_REQUIRED')
    result={}
    for k,h in required.items():result[k]={'sha256':h,'bytes':checked_source_file(paths[k],h)}
    return result

def claim(ledger:dict,event:dict,audit:dict,pointer_bytes:bytes,pointer_sha:str,channel:int,paths:dict,owner:str='CHAT_TURN')->tuple[dict,dict]:
    validate_ledger(ledger,event,audit);check_live(pointer_bytes,pointer_sha,audit,ledger['completed'])
    require(ledger['scientific_pointer_blob_sha1']==pointer_sha,'WAL_LIVE_POINTER_PIN_DRIFT')
    require(ledger['phase']=='READY','ALREADY_CLAIMED_OR_BLOCKED_NO_DUPLICATE_RUN')
    tasks=next_tasks(audit,audit['closed']|set(ledger['closed_delta_ids']),6,channel)
    require(tasks,'CHANNEL_COMPLETE')
    inputs=verified_input_manifest(audit,channel,paths)
    require(re.fullmatch('[A-Za-z0-9_.-]{3,64}',owner) is not None,'INVALID_OWNER')
    work_id=sha(jsonbytes({'baseline':audit['baseline_sha256'],'plan':PLAN_SHA,'channel':channel,'tasks':tasks}))
    active={'work_id':work_id,'channel':channel,'task_ids':tasks,'inputs':inputs,'owner':owner,'claim_parent_event_sha256':ledger['event_sha256']}
    e={'schema':EV_SCHEMA,'seq':ledger['generation']+1,'phase':'CLAIM','parent_event_sha256':ledger['event_sha256'],
       'work_id':work_id,'channel':channel,'task_ids':tasks,'inputs':inputs,
       'science_pointer_sha1':pointer_sha,'economics_changed':False}
    l={**ledger,'generation':e['seq'],'phase':'CLAIMED','event_sha256':sha(jsonbytes(e)),'active_claim':active}
    return l,e

def block_claim(ledger:dict,event:dict,audit:dict,pointer_bytes:bytes,pointer_sha:str,reason:str)->tuple[dict,dict]:
    validate_ledger(ledger,event,audit)
    check_live(pointer_bytes,pointer_sha,audit,ledger['completed'])
    require(ledger['phase']=='CLAIMED' and ledger['scientific_pointer_blob_sha1']==pointer_sha,'ONLY_CURRENT_LIVE_CLAIM_CAN_BLOCK')
    require(isinstance(reason,str) and re.fullmatch('[A-Z0-9_]{6,128}',reason) is not None,'INVALID_BLOCK_REASON')
    c=ledger['active_claim']
    e={'schema':EV_SCHEMA,'seq':ledger['generation']+1,'phase':'BLOCKED','parent_event_sha256':ledger['event_sha256'],
       'work_id':c['work_id'],'task_ids':c['task_ids'],'reason':reason,
       'science_pointer_sha1':pointer_sha,'economics_changed':False}
    return {**ledger,'generation':e['seq'],'phase':'BLOCKED','event_sha256':sha(jsonbytes(e))},e

def verify_receipt_full(rec:dict,name:str):
    require(rec.get('schema')=='QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1','RECEIPT_SCHEMA_DRIFT')
    require(NAME.fullmatch(name) is not None and taskid(rec)==name,'RECEIPT_NAME_OR_TASK_DRIFT')
    tests=rec.get('tests')
    require(isinstance(tests,list) and tests and len(tests)==len(rec['ordinals'])==rec['tested_mask_occurrences'],'RECEIPT_TEST_COUNT_DRIFT')
    require([t['ordinal'] for t in tests]==rec['ordinals'] and all(t['all_rejections_equal'] is True for t in tests),'RECEIPT_REJECTION_OR_ORDINAL_MISMATCH')
    require(all(isinstance(t.get('physical_mask_id'),str) and t['physical_mask_id'] for t in tests),'RECEIPT_PHYSICAL_MASK_ID_MISSING')
    require(sum(t['independent_exact_trades'] for t in tests)==rec['independent_exact_trades'],'RECEIPT_TRADE_SUM_DRIFT')
    require(sum(t['11_fields_compared'] for t in tests)==rec['exact_fields']==11*rec['independent_exact_trades'],'RECEIPT_11_FIELDS_DRIFT')
    require(sum(t['PNL_blind_sampled_source_signals'] for t in tests)==rec['sampled_signals'],'RECEIPT_SIGNAL_SUM_DRIFT')
    for k in ('Gate_A_approved','holdout_open','ga2_open'):
        require(rec.get(k) is False,'RECEIPT_GATE_DRIFT')
    require(rec.get('new_economic_PNL') is False and rec.get('status')=='PASS','RECEIPT_NOT_VALIDATED')

def recover(ledger:dict,event:dict,audit:dict,pointer_bytes:bytes,pointer_sha:str,receipts:dict[str,bytes]|None=None)->dict:
    validate_ledger(ledger,event,audit);check_live(pointer_bytes,pointer_sha,audit,ledger['completed'])
    require(ledger['scientific_pointer_blob_sha1']==pointer_sha,'REMOTE_AUTHORITY_DRIFT_NO_RETRY')
    if ledger['phase']=='READY':return {'status':'SKIP_VERIFIED_CLOSED_WORK','next_CH0':ledger['next_CH0'],'next_CH4':ledger['next_CH4'],'completed':ledger['completed']}
    claim=ledger['active_claim'];receipts=receipts or {}
    if ledger['phase']=='BLOCKED' and set(receipts)!=set(claim['task_ids']):
        return {'status':'BLOCKED_DEPENDENCY_NO_IMPLICIT_RETRY','work_id':claim['work_id'],'found':len(receipts)}
    if set(receipts)!=set(claim['task_ids']):return {'status':'CLAIM_INCOMPLETE_DO_NOT_RERUN','work_id':claim['work_id'],'found':len(receipts),'expected':len(claim['task_ids'])}
    for name,raw in receipts.items():
        rec=json.loads(raw);verify_receipt_full(rec,name);require(taskid(rec)==name and rec.get('status')=='PASS' and rec.get('new_economic_PNL') is False,'RECOVERY_RECEIPT_NOT_VALID:'+name)
        require(rec.get('plan_SHA256')==PLAN_SHA and rec.get('original_raw_sha256')==RAW_SHA,'RECOVERY_RECEIPT_SOURCE_DRIFT')
        for flag in ('Gate_A_approved','holdout_open','ga2_open'):require(rec.get(flag) is False,'RECOVERY_GATE_DRIFT')
    return {'status':'PREPARE_ATTEST_NO_RECOMPUTATION','work_id':claim['work_id'],'receipt_sha256':{k:sha(v) for k,v in receipts.items()}}

def commit_proposal(ledger:dict,event:dict,audit:dict,pointer_bytes:bytes,pointer_sha:str,receipts:dict[str,bytes],delta_bytes:bytes,prior_delta_sha256:str,new_pointer_bytes:bytes,new_pointer_sha:str)->tuple[dict,dict]:
    recover_status=recover(ledger,event,audit,pointer_bytes,pointer_sha,receipts)
    require(recover_status['status']=='PREPARE_ATTEST_NO_RECOMPUTATION','CANNOT_PROMOTE_INCOMPLETE_CLAIM')
    d=json.loads(delta_bytes);c=ledger['active_claim']
    require(d['schema']=='QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1' and d['parent_sha256']==prior_delta_sha256 and d['previous_count']==ledger['completed'],'DELTA_PARENT_OR_COUNT_DRIFT')
    require(d['new_count']==ledger['completed']+len(c['task_ids']) and d['frozen_plan_sha256']==PLAN_SHA,'DELTA_SCOPE_DRIFT')
    require(d.get('no_new_PnL') is True and all(d.get(k) is False for k in ('Gate_A_approved','holdout_open','ga2_open')),'DELTA_PNL_FIREWALL')
    require(prior_delta_sha256==ledger['delta_tip_sha256'],'WAL_DELTA_HEAD_NOT_CURRENT')
    oldp=json.loads(pointer_bytes);newp=check_live(new_pointer_bytes,new_pointer_sha,audit,d['new_count'])
    require(new_pointer_sha!=pointer_sha and newp['target']!=oldp['target'] and newp['last_closed_remote_anchor_path']!=oldp['last_closed_remote_anchor_path'],'NEW_POINTER_REUSES_STALE_HANDOFF_OR_ANCHOR')
    require(H40.fullmatch(newp['target_git_blob_sha1']) is not None and H40.fullmatch(newp['last_closed_remote_anchor_blob_sha1']) is not None,'NEW_POINTER_UNPINNED_EVIDENCE')
    require({row['name'] for row in d['receipts']}==set(c['task_ids']),'DELTA_TASKS_DIFFER_FROM_CLAIM')
    import base64
    for row in d['receipts']:
        raw=base64.b64decode(row['b64'],validate=True)
        require(sha(raw)==row['sha256'] and len(raw)==row['bytes'] and raw==receipts[row['name']],'DELTA_RECEIPT_BYTES_DRIFT')
    e={'schema':EV_SCHEMA,'seq':ledger['generation']+1,'phase':'COMMIT','parent_event_sha256':ledger['event_sha256'],
       'work_id':c['work_id'],'task_ids':c['task_ids'],'prior_delta_sha256':prior_delta_sha256,
       'new_delta_sha256':sha(delta_bytes),'new_delta_git_blob_sha1':gb(delta_bytes),
       'from':ledger['completed'],'to':d['new_count'],'scientific_pointer_before_sha1':pointer_sha,
       'git_atomic_publish_required':True,'scientific_pointer_after_sha1':new_pointer_sha,'new_target_sha1':newp['target_git_blob_sha1'],'new_anchor_sha1':newp['last_closed_remote_anchor_blob_sha1'],'economics_changed':False}
    # Only a *proposal*: caller MUST create delta, immutable anchor+handoff and
    # pointer+ledger together in a non-force Git commit, and read back all blobs.
    closed=set(audit['closed'])|set(ledger['closed_delta_ids'])|set(c['task_ids'])
    l={**ledger,'generation':e['seq'],'event_sha256':sha(jsonbytes(e)),'phase':'READY',
       'active_claim':None,'completed':d['new_count'],'remaining':710-d['new_count'],
       'delta_tip_sha256':sha(delta_bytes),'scientific_pointer_blob_sha1':new_pointer_sha,'closed_delta_ids':ledger['closed_delta_ids']+c['task_ids'],
       'next_CH0':next_tasks(audit,closed,6,0),'next_CH4':next_tasks(audit,closed,6,4)}
    return l,e

def audit_events(events:list[dict],index:dict,audit:dict):
    require(events and events[0]['phase']=='BASELINE' and events[0]['seq']==0,'FIRST_EVENT_NOT_BASELINE')
    prev='0'*64;last_phase=None;last_claim=None;seen=set();count=446
    for i,e in enumerate(events):
        require(e['seq']==i and e['parent_event_sha256']==prev,'EVENT_CHAIN_BROKEN')
        require(e['schema']==EV_SCHEMA and e['phase'] in ('BASELINE','CLAIM','COMMIT','BLOCKED'),'EVENT_SCHEMA_DRIFT')
        if i==0:require(e['checkpoint']==446 and e['baseline_zip_sha256']==BASELINE_SHA,'BASELINE_EVENT_DRIFT')
        elif e['phase']=='CLAIM':
            require(last_phase in ('BASELINE','COMMIT') and 1<=len(e['task_ids'])<=6 and not(set(e['task_ids'])&seen),'EVENT_CLAIM_NOT_FRESH')
            last_claim=e
        elif e['phase']=='COMMIT':
            require(last_phase in ('CLAIM','BLOCKED') and last_claim is not None and e['work_id']==last_claim['work_id'] and e['task_ids']==last_claim['task_ids'],'EVENT_COMMIT_WITHOUT_CLAIM')
            require(e['from']==count and e['to']==count+len(e['task_ids']) and e['prior_delta_sha256']!=e['new_delta_sha256'],'EVENT_COMMIT_COUNT_OR_CHAIN_DRIFT')
            count=e['to'];seen.update(e['task_ids'])
        else:require(last_phase=='CLAIM' and e['work_id']==last_claim['work_id'],'BLOCKED_WITHOUT_CLAIM')
        prev=sha(jsonbytes(e));last_phase=e['phase']
    require(count==index['completed'] and set(index['closed_delta_ids'])==seen,'EVENTS_DO_NOT_RECONCILE_LEDGER')
    require(prev==index['event_sha256'] and index['generation']==len(events)-1,'LEDGER_HEAD_OR_SEQUENCE_MISMATCH')
    validate_ledger(index,events[-1],audit)
    return {'status':'WAL_EVENT_CHAIN_PASS','event_count':len(events),'tip_sha256':prev,'phase':index['phase'],'completed':index['completed']}

def read_receipt_dir(folder,task_ids):
    root=pathlib.Path(folder)
    require(root.is_dir(),'RECEIPT_DIRECTORY_MISSING')
    allowed=set(task_ids)
    found={}
    for p in root.glob('CH[04]_*.json'):
        require(p.name in allowed,'UNCLAIMED_RECEIPT_IN_STAGE:'+p.name)
        found[p.name]=p.read_bytes()
    return found

def write_stage(folder,ledger,event,status,expected_branch_tip):
    """Prepare byte-exact Git inputs. Only a remote atomic Git commit makes them real."""
    require(H40.fullmatch(expected_branch_tip) is not None,'EXPECTED_GIT_BRANCH_TIP_REQUIRED')
    dest=pathlib.Path(folder);dest.mkdir(parents=True,exist_ok=True)
    indexbytes=jsonbytes(ledger);eventbytes=jsonbytes(event)
    (dest/'index.json').write_bytes(indexbytes)
    (dest/'event.json').write_bytes(eventbytes)
    eventname=f"{event['seq']:06d}_{event['phase']}.json"
    packet={'schema':'QROS_W5_WAL_ATOMIC_GIT_PUBLICATION_PACKET_V1',
            'status':'PREPARED_ONLY_NOT_REMOTELY_COMMITTED','expected_branch_tip':expected_branch_tip,
            'index_path':'control/QROS_W5_V33_GIT_WAL_CURRENT.json',
            'event_path':'research/public1000/seed0076/direct_dev/v33_git_native_evidence/wal/events/'+eventname,
            'index_git_blob_sha1':gb(indexbytes),'event_git_blob_sha1':gb(eventbytes),
            'index_sha256':sha(indexbytes),'event_sha256':sha(eventbytes),
            'scientific_pointer_sha1':ledger['scientific_pointer_blob_sha1'],
            'ready_for_next_compute':False,
            'instruction':'CREATE_GIT_BLOBS_VERIFY_REMOTE_BYTES_COMMIT_BOTH_IN_ONE_NONFORCED_BRANCH_CAS_AND_READBACK; ONLY_THEN_CHANGE_STATUS'}
    (dest/'PUBLISH_PACKET.json').write_bytes(jsonbytes(packet))
    return packet

def main(argv=None):
    ap=argparse.ArgumentParser(description='QROS Git WAL; no unattended Android daemon, no scientific Gate A promotion')
    ap.add_argument('--baseline',required=True)
    sp=ap.add_subparsers(dest='command',required=True)
    def pointer_options(parser):
        parser.add_argument('--pointer',required=True);parser.add_argument('--pointer-blob-sha1',required=True)
    def current_options(parser):
        pointer_options(parser);parser.add_argument('--ledger',required=True);parser.add_argument('--last-event',required=True)
    init=sp.add_parser('bootstrap');pointer_options(init);init.add_argument('--out',required=True);init.add_argument('--expected-branch-tip',required=True)
    peek=sp.add_parser('next');current_options(peek)
    cl=sp.add_parser('claim');current_options(cl);cl.add_argument('--channel',type=int,choices=[0,4],required=True)
    cl.add_argument('--raw-ticks',required=True);cl.add_argument('--channel-zip',required=True);cl.add_argument('--owner',default='CHAT_TURN')
    cl.add_argument('--out',required=True);cl.add_argument('--expected-branch-tip',required=True)
    rc=sp.add_parser('recover');current_options(rc);rc.add_argument('--receipt-dir',required=True)
    block=sp.add_parser('block');current_options(block);block.add_argument('--reason',required=True);block.add_argument('--out',required=True);block.add_argument('--expected-branch-tip',required=True)
    cm=sp.add_parser('propose-commit');current_options(cm);cm.add_argument('--receipt-dir',required=True);cm.add_argument('--delta',required=True)
    cm.add_argument('--new-pointer',required=True);cm.add_argument('--new-pointer-blob-sha1',required=True)
    cm.add_argument('--out',required=True);cm.add_argument('--expected-branch-tip',required=True)
    verify=sp.add_parser('audit');verify.add_argument('--ledger',required=True);verify.add_argument('--events-dir',required=True)
    a=ap.parse_args(argv)
    try:
        baseline=audit_baseline(a.baseline)
        if a.command=='bootstrap':
            p=pathlib.Path(a.pointer).read_bytes();ledger,event=bootstrap(baseline,p,a.pointer_blob_sha1)
            o=write_stage(a.out,ledger,event,'BASELINE',a.expected_branch_tip)
        elif a.command=='audit':
            ledger=json.loads(pathlib.Path(a.ledger).read_bytes())
            events=[json.loads(p.read_bytes()) for p in sorted(pathlib.Path(a.events_dir).glob('*.json'))]
            o=audit_events(events,ledger,baseline)
        else:
            ledger=json.loads(pathlib.Path(a.ledger).read_bytes());event=json.loads(pathlib.Path(a.last_event).read_bytes())
            p=pathlib.Path(a.pointer).read_bytes();ps=a.pointer_blob_sha1
            if a.command=='next':
                validate_ledger(ledger,event,baseline);check_live(p,ps,baseline,ledger['completed'])
                require(ledger['scientific_pointer_blob_sha1']==ps,'STALE_SCIENTIFIC_POINTER')
                o=recover(ledger,event,baseline,p,ps)
            elif a.command=='claim':
                l,e=claim(ledger,event,baseline,p,ps,a.channel,{'raw_ticks':a.raw_ticks,'channel_tape_zip':a.channel_zip},a.owner)
                o=write_stage(a.out,l,e,'CLAIM',a.expected_branch_tip)
            elif a.command=='recover':
                receipts=read_receipt_dir(a.receipt_dir,ledger['active_claim']['task_ids']) if ledger['active_claim'] else {}
                o=recover(ledger,event,baseline,p,ps,receipts)
            elif a.command=='block':
                l,e=block_claim(ledger,event,baseline,p,ps,a.reason)
                o=write_stage(a.out,l,e,'BLOCKED',a.expected_branch_tip)
            else:
                c=ledger['active_claim'];require(c is not None,'NO_ACTIVE_CLAIM')
                receipts=read_receipt_dir(a.receipt_dir,c['task_ids'])
                nb=pathlib.Path(a.new_pointer).read_bytes();delta=pathlib.Path(a.delta).read_bytes()
                l,e=commit_proposal(ledger,event,baseline,p,ps,receipts,delta,ledger['delta_tip_sha256'],nb,a.new_pointer_blob_sha1)
                o=write_stage(a.out,l,e,'COMMIT',a.expected_branch_tip)
                o['required_atomic_files']=['Git delta bytes','immutable scientific anchor','immutable scientific handoff','updated scientific pointer','WAL index','new COMMIT event']
                o['scientific_promotion']='PENDING_UNTIL_REMOTE_GIT_CAS_AND_READBACK'
        print(json.dumps(o,sort_keys=True));return 0
    except (Stop,KeyError,ValueError,TypeError,FileNotFoundError,zipfile.BadZipFile,NotADirectoryError) as ex:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(ex)},sort_keys=True),file=sys.stderr);return 3
if __name__=='__main__':raise SystemExit(main())
