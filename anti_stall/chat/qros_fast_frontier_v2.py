#!/usr/bin/env python3
"""QROS Fast Frontier v2: cold full audit once; O(1) Git-native chat-turn resume.

A fast frontier is a SHA-pinned MATERIALIZED VIEW of an independently audited
append-only receipt history. It is not a new source of science or a signature.
The authenticated Git branch and an atomic non-forced Git commit provide authority.
This module never executes a backtest and never reads economic PnL.
"""
from __future__ import annotations
import argparse, base64, hashlib, io, json, pathlib, re, sys, zipfile

SCHEMA="QROS_W5_FAST_FRONTIER_V2"
INDEX_SCHEMA="QROS_W5_FAST_FROZEN_TASK_INDEX_V2"
DELTA_SCHEMA="QROS_W5_FAST_DELTA_V2"
POINTER_SCHEMA="QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF_POINTER_V1"
H40=re.compile(r"[0-9a-f]{40}\Z")
H64=re.compile(r"[0-9a-f]{64}\Z")
RECEIPT_RE=re.compile(r"CH([04])_([A-Za-z0-9_]+)_I(\d{3})_(\d{3})\.json\Z")
BASELINE_ZIP_SHA="d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05"
BASELINE_GIT_SHA="688ec3fa2123ec9df900c41487e4f6298b4ceea5"
ORIGINAL_PLAN_SHA="2be3c09dbcf80576125187f45ae9e7c8ce265a67bab6170a3809adb6a464dc0c"
ORIGINAL_RUNNER_SHA="d545f846a09dc2059193c5a9a6703235bf9f27554ac802eafdf4c032b5a501bf"
ORIGINAL_RAW_SHA="3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53"
BASELINE_COUNT=446
TOTAL=710
MAX_DELTA=6
BOOT_LEDGER=hashlib.sha256(b"QROS_W5_FAST_LEDGER_V2\x00").digest()
class Refuse(RuntimeError): pass

def require(b,why):
    if not b:raise Refuse(why)
def digest(b):return hashlib.sha256(b).hexdigest()
def git_blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def canon(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def exact(b,expected_sha,why):
    require(isinstance(expected_sha,str) and bool(H40.fullmatch(expected_sha)) and git_blob(b)==expected_sha,why)
    return b

def task_key(t):return (t['ch'] if 'ch' in t else t['channel'],t['route'],tuple(t['ordinals']))
def identity(t):return {'ch':task_key(t)[0],'route':task_key(t)[1],'ordinals':list(task_key(t)[2])}
def bits(bs):return sum(x.bit_count() for x in bs)
def mark(bs,i):bs[i//8]|=1<<(i%8)
def isset(bs,i):return bool(bs[i//8]&(1<<(i%8)))
def bitraw(b64):
    require(isinstance(b64,str),'INVALID_BITMAP_TYPE')
    try:b=base64.b64decode(b64,validate=True)
    except Exception as e:raise Refuse('INVALID_BITMAP_BASE64') from e
    require(len(b)==(TOTAL+7)//8,'INVALID_BITMAP_SIZE')
    require(b[-1] >> (TOTAL%8)==0,'INVALID_BITMAP_UNUSED_BITS')
    return bytearray(b)
def bitb64(b):return base64.b64encode(bytes(b)).decode('ascii')
def step(root,idx,name,sha):return hashlib.sha256(root+idx.to_bytes(2,'big')+name.encode('utf-8')+bytes.fromhex(sha)).digest()
def next_by_channel(idx,bitmap):
    return {str(ch):[{'task_index':i,**t} for i,t in enumerate(idx) if t['ch']==ch and not isset(bitmap,i)][:MAX_DELTA] for ch in (0,4)}
def guards(obj,prefix):
    for flag in ('Gate_A_approved','holdout_open','ga2_open'):
        require(obj.get(flag) is False,prefix+'_GUARD_'+flag)

def assert_receipt(name,raw,expected,plan_sha=ORIGINAL_PLAN_SHA,raw_sha=ORIGINAL_RAW_SHA):
    require(bool(RECEIPT_RE.fullmatch(name)),'RECEIPT_NAME_INVALID')
    try:r=json.loads(raw)
    except Exception as e:raise Refuse('RECEIPT_JSON') from e
    require(r.get('schema')=='QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1','WRONG_RECEIPT_SCHEMA')
    require(task_key(r)==task_key(expected),'UNFROZEN_TASK_IDENTITY')
    match=RECEIPT_RE.fullmatch(name)
    require(int(match[1])==expected['ch'] and match[2]==expected['route'] and int(match[3])==expected['ordinals'][0] and int(match[4])==expected['ordinals'][-1],'RECEIPT_FILENAME_DRIFT')
    require(r.get('status')=='PASS' and r.get('new_economic_PNL') is False,'RECEIPT_NOT_VALIDATED')
    require(r.get('plan_SHA256')==plan_sha and r.get('original_raw_sha256')==raw_sha,'RECEIPT_SOURCE_DRIFT')
    guards(r,'RECEIPT')
    tests=r.get('tests')
    require(isinstance(tests,list) and len(tests)==len(expected['ordinals']) and r.get('tested_mask_occurrences')==len(tests),'RECEIPT_TEST_COUNT')
    require([t['ordinal'] for t in tests]==expected['ordinals'],'RECEIPT_TEST_ORDINAL')
    require(all(t.get('all_rejections_equal') is True for t in tests),'RECEIPT_PARITY_MISMATCH')
    require(sum(t['independent_exact_trades'] for t in tests)==r['independent_exact_trades'],'RECEIPT_TRADES_SUM')
    require(sum(t['11_fields_compared'] for t in tests)==r['exact_fields']==11*r['independent_exact_trades'],'RECEIPT_FIELDS_SUM')
    require(sum(t['PNL_blind_sampled_source_signals'] for t in tests)==r['sampled_signals'],'RECEIPT_SIGNALS_SUM')
    return r

def audit_baseline(path):
    blob=pathlib.Path(path).read_bytes()
    require(digest(blob)==BASELINE_ZIP_SHA and git_blob(blob)==BASELINE_GIT_SHA,'BASELINE_GIT_SHA_AND_SHA256_FAIL')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist();require(len(names)==len(set(names)) and z.testzip() is None,'BASELINE_ZIP_CRC_OR_DUPLICATE')
        manifest=json.loads(z.read('MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json'))
        table={x['name']:x for x in manifest['files']}
        require(len(table)==len(manifest['files'])==len(names)-1,'BASELINE_MANIFEST_COUNT')
        require(set(names)==set(table)|{'MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json'},'BASELINE_MEMBER_MISSING')
        for name,record in table.items():
            raw=z.read(name)
            require(len(raw)==record['bytes'] and digest(raw)==record['sha256'],'BASELINE_MEMBER_SHA:'+name)
        plan=z.read('FROZEN_PLAN/V33_FROZEN_REMAINING_ALL_MASK_PLAN.json')
        runner=z.read('SOURCE/v33_run_frozen_remaining_large_mask_parity.py')
        require(digest(plan)==ORIGINAL_PLAN_SHA and digest(runner)==ORIGINAL_RUNNER_SHA,'FROZEN_PLAN_OR_RUNNER_DRIFT')
        frozen=json.loads(plan)['frozen_tasks']
        require(len(frozen)==TOTAL,'WRONG_ORIGINAL_TASK_COUNT')
        identities=[identity(t) for t in frozen];lookup={task_key(t):i for i,t in enumerate(identities)}
        require(len(lookup)==TOTAL,'DUPLICATE_ORIGINAL_TASK_ID')
        master=json.loads(z.read('MASTER/V33_PARTIAL_MASTER_RECEIPT.json'))
        require(master['completed_shards']==BASELINE_COUNT and master['planned_shards']==TOTAL,'WRONG_BASELINE_COUNT')
        require(master['frozen_plan_sha256']==ORIGINAL_PLAN_SHA and master['source_runner_sha256']==ORIGINAL_RUNNER_SHA and master['original_raw_sha256']==ORIGINAL_RAW_SHA,'BASELINE_SOURCE_MISMATCH')
        guards(master,'BASELINE');require(master['no_new_PnL'] is True,'BASELINE_NEW_PNL')
        ledger=master['receipt_byte_manifest'];require(len(ledger)==BASELINE_COUNT,'BASELINE_LEDGER_COUNT')
        receipts={item['filename']:z.read('RECEIPTS/'+item['filename']) for item in ledger}
        checked=[];seen=set();bitmap=bytearray((TOTAL+7)//8)
        for item in ledger:
            raw=receipts[item['filename']]
            require(digest(raw)==item['sha256'],'BASELINE_RECEIPT_SHA')
            obj=json.loads(raw);tid=task_key(obj)
            require(tid in lookup,'BASELINE_UNFROZEN_TASK')
            idx=lookup[tid];require(idx not in seen,'BASELINE_DUPLICATE_TASK');seen.add(idx)
            assert_receipt(item['filename'],raw,identities[idx])
            mark(bitmap,idx);checked.append((idx,item['filename'],item['sha256']))
        require(bits(bitmap)==BASELINE_COUNT,'BASELINE_BITMAP_COUNT')
        from collections import Counter
        cnt=Counter(json.loads(v)['channel'] for v in receipts.values())
        require({str(ch):cnt[ch] for ch in (0,4)}=={str(k):v for k,v in master['by_channel_complete'].items()},'BASELINE_CHANNEL_COUNT')
        root=BOOT_LEDGER
        for idx,name,hs in sorted(checked):root=step(root,idx,name,hs)
        idx_doc={'schema':INDEX_SCHEMA,'baseline_archive_sha256':BASELINE_ZIP_SHA,'original_plan_sha256':ORIGINAL_PLAN_SHA,'original_runner_sha256':ORIGINAL_RUNNER_SHA,'original_raw_sha256':ORIGINAL_RAW_SHA,'tasks':identities}
        ib=canon(idx_doc)
        frontier={'schema':SCHEMA,'sequence':0,'baseline_git_blob_sha1':BASELINE_GIT_SHA,'baseline_sha256':BASELINE_ZIP_SHA,'original_plan_sha256':ORIGINAL_PLAN_SHA,'original_runner_sha256':ORIGINAL_RUNNER_SHA,'original_raw_sha256':ORIGINAL_RAW_SHA,'plan_index_sha256':digest(ib),'plan_index_git_blob_sha1':git_blob(ib),'completed':BASELINE_COUNT,'remaining':TOTAL-BASELINE_COUNT,'bitmap_b64':bitb64(bitmap),'channels':{str(ch):cnt[ch] for ch in (0,4)},'ledger_root_sha256':root.hex(),'previous_frontier_git_blob_sha1':None,'previous_ledger_root_sha256':None,'latest_delta_path':None,'latest_delta_git_blob_sha1':None,'latest_delta_sha256':None,'next_by_channel':next_by_channel(identities,bitmap),'baseline_receipts_sha_verified':BASELINE_COUNT,'baseline_manifest_members_sha_verified':len(table),'periodic_full_reaudit_due_at_sequence':20,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'historical_account_commission_certified':False,'historical_symbol_special_hours_certified':False,'new_economic_PNL':False}
        return frontier,idx_doc,{'status':'BASELINE_446_FULL_REHASH_PASS','baseline_zip_sha256':BASELINE_ZIP_SHA,'baseline_git_blob_sha1':BASELINE_GIT_SHA,'baseline_receipts':BASELINE_COUNT,'manifest_members':len(table),'frozen_tasks':len(identities),'ledger_root_sha256':root.hex(),'frozen_index_sha256':digest(ib)}

def check_frontier(frontier,index=None):
    require(frontier.get('schema')==SCHEMA,'FRONTIER_SCHEMA')
    require(frontier.get('baseline_git_blob_sha1')==BASELINE_GIT_SHA and frontier.get('baseline_sha256')==BASELINE_ZIP_SHA,'BASELINE_PIN_DRIFT')
    require(frontier.get('original_plan_sha256')==ORIGINAL_PLAN_SHA and frontier.get('original_runner_sha256')==ORIGINAL_RUNNER_SHA and frontier.get('original_raw_sha256')==ORIGINAL_RAW_SHA,'ORIGINAL_SOURCE_DRIFT')
    guards(frontier,'FRONTIER')
    require(frontier.get('new_economic_PNL') is False and frontier.get('historical_account_commission_certified') is False and frontier.get('historical_symbol_special_hours_certified') is False,'FORBIDDEN_SCIENTIFIC_PROMOTION')
    sequence=frontier.get('sequence');require(type(sequence) is int and 0<=sequence<=TOTAL-BASELINE_COUNT,'BAD_SEQUENCE')
    bitmap=bitraw(frontier['bitmap_b64']);n=bits(bitmap)
    require(n==frontier.get('completed') and n+frontier.get('remaining',-1)==TOTAL and n>=BASELINE_COUNT,'FRONTIER_BITMAP_COUNT_MISMATCH')
    chan=frontier.get('channels');require(type(chan) is dict and set(chan)=={'0','4'} and sum(chan.values())==n,'CHANNEL_COUNT_DRIFT')
    require(bool(H64.fullmatch(frontier.get('ledger_root_sha256',''))),'BAD_LEDGER_ROOT')
    for ch in ('0','4'):
        rows=frontier.get('next_by_channel',{}).get(ch)
        require(isinstance(rows,list) and len(rows)<=MAX_DELTA,'BAD_NEXT_CURSOR')
        require(len({row['task_index'] for row in rows})==len(rows) and all(0<=row['task_index']<TOTAL and not isset(bitmap,row['task_index']) and row['ch']==int(ch) for row in rows),'NEXT_CURSOR_BITMASK_DRIFT')
    if sequence==0:
        require(n==BASELINE_COUNT and frontier.get('latest_delta_path') is None and frontier.get('previous_frontier_git_blob_sha1') is None,'BAD_BOOTSTRAP_FRONTIER')
    else:
        require(bool(H40.fullmatch(frontier.get('latest_delta_git_blob_sha1',''))) and bool(H40.fullmatch(frontier.get('previous_frontier_git_blob_sha1',''))) and bool(H64.fullmatch(frontier.get('latest_delta_sha256',''))) and bool(H64.fullmatch(frontier.get('previous_ledger_root_sha256',''))),'BAD_DELTA_FRONTIER_PINS')
    if index is not None:
        require(index.get('schema')==INDEX_SCHEMA and len(index.get('tasks',[]))==TOTAL,'INVALID_TASK_INDEX')
        idx=canon(index)
        require(digest(idx)==frontier['plan_index_sha256'] and git_blob(idx)==frontier['plan_index_git_blob_sha1'],'TASK_INDEX_PIN_DRIFT')
        nxt=next_by_channel(index['tasks'],bitmap)
        require(frontier['next_by_channel']==nxt,'NEXT_CURSOR_TAMPERED')
        cc={str(ch):sum(isset(bitmap,i) for i,t in enumerate(index['tasks']) if t['ch']==ch) for ch in (0,4)}
        require(cc==chan,'CHANNEL_BITMAP_COUNT_MISMATCH')
    return bitmap

def check_delta(delta_raw,frontier):
    require(frontier['sequence']>0,'BASELINE_HAS_NO_DELTA')
    require(digest(delta_raw)==frontier['latest_delta_sha256'] and git_blob(delta_raw)==frontier['latest_delta_git_blob_sha1'],'LATEST_DELTA_HASH_DRIFT')
    d=json.loads(delta_raw);require(d['schema']==DELTA_SCHEMA,'DELTA_SCHEMA')
    require(d['sequence']==frontier['sequence'] and d['previous_frontier_git_blob_sha1']==frontier['previous_frontier_git_blob_sha1'] and d['previous_ledger_root_sha256']==frontier['previous_ledger_root_sha256'] and d['new_ledger_root_sha256']==frontier['ledger_root_sha256'],'DELTA_HEAD_CHAIN_DRIFT')
    require(d['new_count']==frontier['completed'] and d['previous_count']+len(d['receipts'])==d['new_count'],'DELTA_COUNT_DRIFT')
    require(d['original_plan_sha256']==ORIGINAL_PLAN_SHA and d['original_raw_sha256']==ORIGINAL_RAW_SHA,'DELTA_ORIGINAL_AUTHORITY_DRIFT')
    require(1<=len(d['receipts'])<=MAX_DELTA,'DELTA_SIZE_DRIFT')
    bs=bitraw(frontier['bitmap_b64']);require(digest(bytes(bs))==d['post_bitmap_sha256'],'BITMAP_DELTA_DRIFT')
    root=bytes.fromhex(d['previous_ledger_root_sha256']);ids=[]
    for item in d['receipts']:
        require(bool(H64.fullmatch(item['sha256'])) and item['bytes']>=0,'DELTA_RECEIPT_DESCRIPTOR_INVALID')
        b=base64.b64decode(item['b64'],validate=True)
        require(len(b)==item['bytes'] and digest(b)==item['sha256'],'LATEST_RECEIPT_SHA_DRIFT')
        require(0<=item['task_index']<TOTAL and item['task_index'] not in ids and isset(bs,item['task_index']),'LATEST_RECEIPT_BITMAP_ID_DRIFT')
        rid=json.loads(b)
        require(RECEIPT_RE.fullmatch(item['name']) is not None and task_key(rid)==(rid['channel'],rid['route'],tuple(rid['ordinals'])),'DELTA_RECEIPT_IDENTITY_INVALID')
        require(rid['Gate_A_approved'] is False and rid['holdout_open'] is False and rid['ga2_open'] is False and rid['new_economic_PNL'] is False,'DELTA_GATE_CHANGE')
        ids.append(item['task_index'])
        root=step(root,item['task_index'],item['name'],item['sha256'])
    require(ids==sorted(ids) and root.hex()==frontier['ledger_root_sha256'],'LATEST_LEDGER_ROOT_INVALID')
    previous=bytearray(bs)
    for i in ids:previous[i//8]&=~(1<<(i%8)) & 255
    require(bits(previous)==d['previous_count'] and digest(bytes(previous))==d['previous_bitmap_sha256'],'DELTA_PREVIOUS_BITMAP_DRIFT')
    require({str(ch):frontier['channels'][str(ch)]-sum(json.loads(base64.b64decode(x['b64']))['channel']==ch for x in d['receipts']) for ch in (0,4)}==d['previous_channels'],'DELTA_CHANNEL_DRIFT')
    require(d['Gate_A_approved'] is False and d['holdout_open'] is False and d['ga2_open'] is False and d['new_economic_PNL'] is False,'DELTA_SCIENTIFIC_GATE')
    return d

def fast_resume(pointer_raw,pointer_git_sha,frontier_raw,frontier_git_sha,target_raw,target_git_sha,anchor_raw,anchor_git_sha,latest_delta_raw=None,idx_raw=None):
    for b,s,n in [(pointer_raw,pointer_git_sha,'LIVE_POINTER'),(frontier_raw,frontier_git_sha,'FAST_FRONTIER'),(target_raw,target_git_sha,'HANDOFF'),(anchor_raw,anchor_git_sha,'ANCHOR')]:exact(b,s,n+'_GIT_BLOB_MISMATCH')
    p=json.loads(pointer_raw);require(p['schema']==POINTER_SCHEMA,'LIVE_POINTER_SCHEMA')
    guards(p,'LIVE_POINTER');require(p.get('v33_shards_completed')==json.loads(frontier_raw).get('completed'),'LIVE_POINTER_FRONTIER_COUNT_DRIFT')
    ff=p.get('fast_frontier_v2');require(isinstance(ff,dict),'FAST_FRONTIER_NOT_ACTIVE')
    require(ff['git_blob_sha1']==frontier_git_sha and ff['sequence']==json.loads(frontier_raw)['sequence'] and ff['ledger_root_sha256']==json.loads(frontier_raw)['ledger_root_sha256'],'POINTER_FRONTIER_SHA_OR_ROOT_MISMATCH')
    require(p['target_git_blob_sha1']==target_git_sha and p['last_closed_remote_anchor_blob_sha1']==anchor_git_sha,'LIVE_TARGET_ANCHOR_MISMATCH')
    f=json.loads(frontier_raw);index=json.loads(idx_raw) if idx_raw else None
    if idx_raw is not None:exact(idx_raw,f['plan_index_git_blob_sha1'],'PLAN_INDEX_GIT_SHA_DRIFT')
    check_frontier(f,index)
    if f['sequence']>0:
        require(latest_delta_raw is not None,'LATEST_DELTA_REQUIRED')
        check_delta(latest_delta_raw,f)
    else:require(latest_delta_raw is None,'UNEXPECTED_BOOTSTRAP_DELTA')
    return {'status':'FAST_GIT_NATIVE_RESUME_PASS','verified_completed':f['completed'],'remaining':f['remaining'],'sequence':f['sequence'],'ledger_root_sha256':f['ledger_root_sha256'],'next':f['next_by_channel'],'full_zip_transfer_required':False,'prior_receipts_replayed_in_this_check':0,'latest_delta_receipts_rehashed':0 if latest_delta_raw is None else len(json.loads(latest_delta_raw)['receipts']),'periodic_full_reaudit_due':f['sequence']>=f['periodic_full_reaudit_due_at_sequence']}

def build_advance(frontier_raw,frontier_git_sha,idx_raw,raw_new:dict[str,bytes],delta_path:str):
    exact(frontier_raw,frontier_git_sha,'PREVIOUS_FRONTIER_GIT_SHA_DRIFT')
    prior=json.loads(frontier_raw);index=json.loads(idx_raw);bs=check_frontier(prior,index)
    require(prior['sequence']<prior['periodic_full_reaudit_due_at_sequence'],'FULL_REAUDIT_REQUIRED_BEFORE_NEXT_PROMOTION')
    require(1<=len(raw_new)<=MAX_DELTA,'MAX_SIX_NEW_RECEIPTS')
    table={task_key(t):i for i,t in enumerate(index['tasks'])};added=[]
    for name,b in raw_new.items():
        require(RECEIPT_RE.fullmatch(name) is not None,'INVALID_NEW_RECEIPT_FILENAME')
        r=json.loads(b);tid=task_key(r)
        require(tid in table,'NEW_UNFROZEN_TASK');i=table[tid];require(not isset(bs,i),'NEW_TASK_ALREADY_COMPLETE')
        assert_receipt(name,b,index['tasks'][i]);added.append((i,name,b,r))
    added.sort();require(len({z[0] for z in added})==len(added),'DUPLICATE_TASK_INDEX')
    require(len({z[3]['channel'] for z in added})==1,'MIXED_CHANNELS_IN_SINGLE_BATCH')
    ch=added[0][3]['channel'];next_idxs=[i for i,t in enumerate(index['tasks']) if t['ch']==ch and not isset(bs,i)][:len(added)]
    require([x[0] for x in added]==next_idxs,'NONCONTIGUOUS_NOT_NEXT_FROZEN_TASK')
    root=bytes.fromhex(prior['ledger_root_sha256']);entries=[]
    for i,name,b,r in added:
        mark(bs,i);root=step(root,i,name,digest(b))
        entries.append({'task_index':i,'name':name,'sha256':digest(b),'bytes':len(b),'b64':base64.b64encode(b).decode('ascii')})
    d={'schema':DELTA_SCHEMA,'sequence':prior['sequence']+1,'previous_frontier_git_blob_sha1':frontier_git_sha,'previous_ledger_root_sha256':prior['ledger_root_sha256'],'new_ledger_root_sha256':root.hex(),'previous_count':prior['completed'],'new_count':prior['completed']+len(added),'previous_channels':prior['channels'],'original_plan_sha256':ORIGINAL_PLAN_SHA,'original_raw_sha256':ORIGINAL_RAW_SHA,'previous_bitmap_sha256':digest(bytes(bitraw(prior['bitmap_b64']))),'post_bitmap_sha256':digest(bytes(bs)),'receipts':entries,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'new_economic_PNL':False}
    delta=canon(d);require(delta_path.endswith('.json') and '/' not in delta_path,'DELTA_BASENAME_ONLY')
    f={**prior,'sequence':d['sequence'],'completed':d['new_count'],'remaining':TOTAL-d['new_count'],'bitmap_b64':bitb64(bs),'channels':{**prior['channels'],str(ch):prior['channels'][str(ch)]+len(added)},'ledger_root_sha256':root.hex(),'previous_frontier_git_blob_sha1':frontier_git_sha,'previous_ledger_root_sha256':prior['ledger_root_sha256'],'latest_delta_path':delta_path,'latest_delta_git_blob_sha1':git_blob(delta),'latest_delta_sha256':digest(delta),'next_by_channel':next_by_channel(index['tasks'],bs)}
    check_frontier(f,index);check_delta(delta,f)
    return canon(f),delta,{'status':'SIX_SHARD_OR_FEWER_FAST_ADVANCE_CHECK_PASS','new':len(added),'total':f['completed'],'remaining':f['remaining'],'frontier_blob_sha1':git_blob(canon(f)),'delta_blob_sha1':git_blob(delta),'delta_sha256':digest(delta)}

def replay_full_audit(baseline_zip,ordered_delta_paths,frontier_raw,frontier_sha,previous_audit_receipts=None):
    """Cold audit after 20 publishes: reverify full baseline + ALL deltas.

    This deliberately costs O(total history), but runs periodically, not per chat.
    It does NOT replay market ticks, PnL, MT5, or any scientific economic gate.
    """
    exact(frontier_raw,frontier_sha,'RE_AUDIT_FRONTIER_GIT_SHA')
    expected=json.loads(frontier_raw);check_frontier(expected)
    baseline,index,_=audit_baseline(baseline_zip)
    fraw=canon(baseline);idxraw=canon(index)
    previous_audit_receipts=previous_audit_receipts or []
    historical=expected.get('full_audit_history',[])
    require(len(previous_audit_receipts)==len(historical),'HISTORIC_REAUDIT_CERTIFICATES_MISSING')
    cert_by_seq={}
    for record,content in zip(historical,previous_audit_receipts):
        exact(content,record['receipt_git_blob_sha1'],'HISTORIC_REAUDIT_CERT_GIT_SHA')
        require(record['sequence'] not in cert_by_seq,'DUPLICATE_REAUDIT_CERTIFICATE')
        cert_by_seq[record['sequence']]=content
    for i,path in enumerate(ordered_delta_paths,1):
        raw=pathlib.Path(path).read_bytes();d=json.loads(raw)
        require(d['sequence']==i and d['previous_frontier_git_blob_sha1']==git_blob(fraw),'AUDIT_DELTA_PARENT_DRIFT')
        new={row['name']:base64.b64decode(row['b64'],validate=True) for row in d['receipts']}
        newer,regenerated,_=build_advance(fraw,git_blob(fraw),idxraw,new,pathlib.Path(path).name)
        require(regenerated==raw,'FULL_AUDIT_DELTA_BYTERAW_DRIFT')
        fraw=newer
        if i in cert_by_seq:
            cert=cert_by_seq[i]
            fraw=certify_full_audit(fraw,git_blob(fraw),cert,git_blob(cert))
    built=json.loads(fraw)
    for k in ('schema','sequence','completed','remaining','bitmap_b64','channels','ledger_root_sha256','latest_delta_git_blob_sha1','latest_delta_sha256','next_by_channel'):
        require(built[k]==expected[k],'FULL_REAUDIT_FRONTIER_CONFLICT:'+k)
    require(len(ordered_delta_paths)==expected['sequence'],'FULL_REAUDIT_INCOMPLETE_HISTORY')
    require(built.get('full_audit_history',[])==expected.get('full_audit_history',[]),'FULL_REAUDIT_HISTORY_DRIFT')
    return {'schema':'QROS_W5_FAST_FRONTIER_FULL_REAUDIT_V2','status':'ALL_BASELINE_AND_ALL_DELTA_RECEIPTS_REVERIFIED','sequence':expected['sequence'],'completed':expected['completed'],'baseline_receipts_rehashed':BASELINE_COUNT,'delta_files_rehashed':len(ordered_delta_paths),'ledger_root_sha256':built['ledger_root_sha256'],'previous_frontier_git_blob_sha1':frontier_sha,'next_full_audit_at_sequence':expected['sequence']+20,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'new_economic_PNL':False}

def certify_full_audit(frontier_raw,frontier_sha,audit_receipt_raw,audit_receipt_git_sha):
    exact(frontier_raw,frontier_sha,'AUDIT_SOURCE_FRONTIER_SHA')
    exact(audit_receipt_raw,audit_receipt_git_sha,'AUDIT_RECEIPT_GIT_BLOB_SHA')
    prior=json.loads(frontier_raw);audit=json.loads(audit_receipt_raw)
    require(audit['schema']=='QROS_W5_FAST_FRONTIER_FULL_REAUDIT_V2' and audit['status']=='ALL_BASELINE_AND_ALL_DELTA_RECEIPTS_REVERIFIED','UNVERIFIED_FULL_AUDIT')
    require(prior['sequence']==audit['sequence'] and prior['completed']==audit['completed'] and prior['ledger_root_sha256']==audit['ledger_root_sha256'] and frontier_sha==audit['previous_frontier_git_blob_sha1'],'FULL_AUDIT_NOT_CURRENT')
    require(prior['sequence']>=prior['periodic_full_reaudit_due_at_sequence'],'FULL_AUDIT_NOT_DUE')
    require(audit['next_full_audit_at_sequence']==prior['sequence']+20 and audit['baseline_receipts_rehashed']==BASELINE_COUNT and audit['delta_files_rehashed']==prior['sequence'],'BAD_REAUDIT_CERT_DETAILS')
    previous=prior.get('full_audit_history',[])
    require(not previous or previous[-1]['sequence']<prior['sequence'],'DUPLICATE_FULL_AUDIT_CERT')
    next_one={**prior,'periodic_full_reaudit_due_at_sequence':audit['next_full_audit_at_sequence'],'full_reaudit_receipt_git_blob_sha1':audit_receipt_git_sha,'full_reaudit_certified_at_sequence':prior['sequence'],'full_audit_history':[ *previous, {'sequence':prior['sequence'],'receipt_git_blob_sha1':audit_receipt_git_sha} ]}
    check_frontier(next_one)
    return canon(next_one)

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    cold=sub.add_parser('bootstrap');cold.add_argument('--baseline',required=True);cold.add_argument('--out-frontier',required=True);cold.add_argument('--out-index',required=True)
    chk=sub.add_parser('check');chk.add_argument('--pointer',required=True);chk.add_argument('--pointer-sha',required=True);chk.add_argument('--frontier',required=True);chk.add_argument('--frontier-sha',required=True);chk.add_argument('--target',required=True);chk.add_argument('--target-sha',required=True);chk.add_argument('--anchor',required=True);chk.add_argument('--anchor-sha',required=True);chk.add_argument('--latest-delta');chk.add_argument('--index')
    adv=sub.add_parser('advance');adv.add_argument('--frontier',required=True);adv.add_argument('--frontier-sha',required=True);adv.add_argument('--index',required=True);adv.add_argument('--new-dir',required=True);adv.add_argument('--delta-basename',required=True);adv.add_argument('--out-frontier',required=True);adv.add_argument('--out-delta',required=True)
    a=ap.parse_args()
    try:
        if a.cmd=='bootstrap':
            f,idx,result=audit_baseline(a.baseline);pathlib.Path(a.out_frontier).write_bytes(canon(f));pathlib.Path(a.out_index).write_bytes(canon(idx));result['frontier_git_blob_sha1']=git_blob(canon(f));result['index_git_blob_sha1']=git_blob(canon(idx))
        elif a.cmd=='check':
            read=lambda p:pathlib.Path(p).read_bytes()
            result=fast_resume(read(a.pointer),a.pointer_sha,read(a.frontier),a.frontier_sha,read(a.target),a.target_sha,read(a.anchor),a.anchor_sha,read(a.latest_delta) if a.latest_delta else None,read(a.index) if a.index else None)
        else:
            new={x.name:x.read_bytes() for x in pathlib.Path(a.new_dir).glob('*.json')}
            f,d,result=build_advance(pathlib.Path(a.frontier).read_bytes(),a.frontier_sha,pathlib.Path(a.index).read_bytes(),new,a.delta_basename)
            pathlib.Path(a.out_frontier).write_bytes(f);pathlib.Path(a.out_delta).write_bytes(d)
        print(json.dumps(result,sort_keys=True,ensure_ascii=False));return 0
    except (Refuse,KeyError,ValueError,TypeError,IndexError,OSError,zipfile.BadZipFile,zipfile.LargeZipFile) as e:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(e)},sort_keys=True),file=sys.stderr);return 3
if __name__=='__main__':sys.exit(main())
