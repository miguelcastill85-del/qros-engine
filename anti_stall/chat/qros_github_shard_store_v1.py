#!/usr/bin/env python3
"""QROS W5: Git-native, append-only, six-shard checkpoints and fail-closed replay.

No network dependency: each ChatGPT turn may fetch exact GitHub blobs through the
GitHub connector and hand them to this independently executable validator.
No economics, alpha-selection, holdout or replay against raw market ticks here.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, pathlib, re, sys, zipfile
SHA64=re.compile(r'[0-9a-f]{64}\Z')
ROUTE_FILE=re.compile(r'CH([04])_([A-Za-z0-9_]+)_I(\d{3})_(\d{3})\.json\Z')
class Stop(RuntimeError):pass
def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def gb(raw:bytes)->str:return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
def fail(condition,msg):
    if not condition:raise Stop(msg)
def exact_file(path,expected):
    fail(isinstance(expected,str) and SHA64.fullmatch(expected),'BAD_EXPECTED_SHA')
    b=pathlib.Path(path).read_bytes();fail(sha(b)==expected,'FILE_SHA_DRIFT:'+str(path));return b
def safe_name(n):
    fail(isinstance(n,str) and n and not n.startswith('/') and '\\' not in n and
         all(x not in ('','.','..') for x in n.split('/')),'UNSAFE_NAME');return n
def decode_zip_bytes(blob,expected_sha):
    fail(sha(blob)==expected_sha,'ZIP_SHA_DRIFT')
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist();fail(len(names)==len(set(names)),'DUPLICATE_ZIP_MEMBER');[safe_name(n) for n in names]
        fail(z.testzip() is None,'ZIP_CRC_DRIFT')
        mb=z.read('MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json');m=json.loads(mb)
        entries=m['files'];check_names={x['name'] for x in entries}
        fail(len(entries)==len(check_names)==len(names)-1 and set(names)==check_names|{'MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json'},'ZIP_MEMBERS_OR_MANIFEST_DRIFT')
        for x in entries:
            safe_name(x['name']);raw=z.read(x['name']);fail(len(raw)==x['bytes'] and sha(raw)==x['sha256'],'ZIP_MEMBER_SHA_DRIFT:'+x['name'])
        master=json.loads(z.read('MASTER/V33_PARTIAL_MASTER_RECEIPT.json'))
        receipts={name[len('RECEIPTS/'):]:z.read(name) for name in names if name.startswith('RECEIPTS/')}
        assert_master(master,receipts,z.read('FROZEN_PLAN/V33_FROZEN_REMAINING_ALL_MASK_PLAN.json'),z.read('SOURCE/v33_run_frozen_remaining_large_mask_parity.py'))
        return {'master':master,'receipts':receipts,'plan':json.loads(z.read('FROZEN_PLAN/V33_FROZEN_REMAINING_ALL_MASK_PLAN.json')),'zip_sha256':expected_sha,'git_blob_sha1':gb(blob),'manifest_members':len(entries),'snapshot_manifest_sha256':sha(mb)}
def assert_master(master,receipts,plan_raw,runner_raw):
    count=master['completed_shards'];total=master['planned_shards']
    fail(total==710 and count==len(receipts) and master['pending_shards']==total-count,'SHARD_COUNT_DRIFT')
    fail(master['frozen_plan_sha256']==sha(plan_raw) and master['source_runner_sha256']==sha(runner_raw),'FROZEN_CODE_OR_PLAN_DRIFT')
    for flag in ('Gate_A_approved','holdout_open','ga2_open','historical_account_commission_certified','historical_symbol_special_hours_certified'):
        fail(master.get(flag) is False,'GATE_DRIFT:'+flag)
    fail(master.get('no_new_PnL') is True,'NEW_PNL_UNAUTHORIZED')
    frozen=json.loads(plan_raw);fail(len(frozen['frozen_tasks'])==710,'FROZEN_TASK_COUNT_DRIFT')
    ledger=master['receipt_byte_manifest'];fail(len(ledger)==len(receipts),'LEDGER_COUNT_DRIFT')
    taskids={task_id(t) for t in frozen['frozen_tasks']}
    seen=set()
    for item in ledger:
        name=item['filename'];safe_name(name)
        fail(name not in seen and name in receipts,'MISSING_OR_DUPLICATE_RECEIPT');seen.add(name)
        raw=receipts[name];fail(sha(raw)==item['sha256'],'RECEIPT_SHA_DRIFT:'+name)
        rec=json.loads(raw)
        fail(rec.get('status')=='PASS' and rec.get('new_economic_PNL') is False,'RECEIPT_NOT_PASS')
        fail(task_id(rec) in taskids,'UNFROZEN_TASK:'+name)
        fail(rec.get('plan_SHA256')==master['frozen_plan_sha256'] and rec.get('original_raw_sha256')==master['original_raw_sha256'],'RECEIPT_SOURCE_DRIFT')
        assert_receipt_tests(rec,name)
        for flag in ('Gate_A_approved','holdout_open','ga2_open'):
            fail(rec.get(flag) is False,'RECEIPT_GATE_DRIFT:'+flag)
    records=[json.loads(v) for v in receipts.values()]
    from collections import Counter
    fail({str(k):v for k,v in Counter(r['channel'] for r in records).items()}==master['by_channel_complete'],'CHANNEL_SUM_DRIFT')
    for k,detail in [('identical_independent_trades_new','independent_exact_trades'),('matching_independent_fields_new','exact_fields'),('sampled_source_signals_new','sampled_signals'),('mask_occurrences_covered_new','tested_mask_occurrences')]:
        fail(master[k]==sum(r[detail] for r in records),'AGGREGATE_SUM_DRIFT:'+k)
    zero=sorted([ [r['channel'],r['route'],t['ordinal']] for r in records for t in r['tests'] if t['zero_signal_mask'] ])
    fail(sorted(master['zero_signal_original_masks_new'])==zero,'ZERO_SIGNAL_LEDGER_DRIFT')
def assert_receipt_tests(rec,name):
    fail(rec.get('schema')=='QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1','RECEIPT_SCHEMA_DRIFT')
    m=ROUTE_FILE.fullmatch(name);fail(m is not None,'RECEIPT_FILENAME_INVALID')
    fail(int(m.group(1))==rec['channel'] and m.group(2)==rec['route'] and int(m.group(3))==rec['ordinals'][0] and int(m.group(4))==rec['ordinals'][-1],'RECEIPT_FILENAME_ID_DRIFT')
    tests=rec.get('tests',[])
    fail(len(tests)==len(rec['ordinals'])==rec['tested_mask_occurrences'] and len(tests)>0,'TESTS_MISSING')
    fail(sorted(t['ordinal'] for t in tests)==rec['ordinals'],'TEST_ORDINAL_DRIFT')
    fail(all(t['all_rejections_equal'] is True for t in tests),'INDEPENDENT_REJECTION_MISMATCH')
    fail(sum(t['independent_exact_trades'] for t in tests)==rec['independent_exact_trades'] and sum(t['11_fields_compared'] for t in tests)==rec['exact_fields'],'TRADE_FIELD_SUM_DRIFT')
    fail(rec['exact_fields']==11*rec['independent_exact_trades'] and sum(t['PNL_blind_sampled_source_signals'] for t in tests)==rec['sampled_signals'],'INDEPENDENT_FIELDS_OR_SIGNALS_DRIFT')
def task_id(row):return (row['ch'] if 'ch' in row else row['channel'],row['route'],tuple(row['ordinals']))
def next_tasks(plan,completed):
    return {str(c):next(({'ch':t['ch'],'route':t['route'],'ordinals':t['ordinals']} for t in plan['frozen_tasks'] if t['ch']==c and task_id(t) not in completed),None) for c in (0,4)}
def verify_baseline(path,sha_expected):
    b=exact_file(path,sha_expected);x=decode_zip_bytes(b,sha_expected)
    return {'status':'GIT_NATIVE_BASELINE_BYTE_VERIFIED','completed':len(x['receipts']),'remaining':710-len(x['receipts']),'zip_sha256':x['zip_sha256'],'git_blob_sha1':x['git_blob_sha1'],'snapshot_manifest_sha256':x['snapshot_manifest_sha256'],'next':next_tasks(x['plan'],{task_id(json.loads(v)) for v in x['receipts'].values()})}
def restore_ascii_parts(folder,parts_index,expected_sha):
    idx=json.loads(pathlib.Path(parts_index).read_bytes());fail(idx['schema']=='QROS_W5_GITHUB_ASCII_TRANSPORT_V1','TRANSPORT_SCHEMA')
    pieces=idx['parts'];fail(len(pieces)>0 and [p['ordinal'] for p in pieces]==list(range(len(pieces))),'MISSING_PART')
    raw=[]
    for p in pieces:
        path=safe_name(p['path']);buf=(pathlib.Path(folder)/path).read_bytes()
        fail(gb(buf)==p['git_blob_sha1'] and sha(buf)==p['sha256'],'GIT_ASCII_PART_DRIFT:'+path)
        try:chunk=buf.decode('ascii')
        except UnicodeDecodeError:raise Stop('NOT_ASCII_GIT_PART')
        fail(len(chunk)==p['b64_characters'] and re.fullmatch('[A-Za-z0-9+/=]+',chunk) is not None,'BAD_BASE64_PART')
        raw.append(chunk)
    try:zipbytes=base64.b64decode(''.join(raw),validate=True)
    except Exception as e:raise Stop('GITHUB_PART_BASE64_CORRUPTED') from e
    fail(sha(zipbytes)==expected_sha and gb(zipbytes)==idx['source_git_blob_sha1'],'GIT_RECONSTRUCTION_MISMATCH')
    return zipbytes
def load_chain(baseline_blob,baseline_sha,delta_files):
    base=decode_zip_bytes(baseline_blob,baseline_sha);rec={k:v for k,v in base['receipts'].items()}
    complete={task_id(json.loads(v)) for v in rec.values()};plan=base['plan'];last_sha=baseline_sha
    for f in delta_files:
        raw=pathlib.Path(f).read_bytes();d=json.loads(raw)
        fail(d.get('schema')=='QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1','DELTA_SCHEMA')
        fail(d['parent_sha256']==last_sha and d['previous_count']==len(rec),'DELTA_CHAIN_BROKEN')
        fail(d['frozen_plan_sha256']==base['master']['frozen_plan_sha256'],'DELTA_PLAN_DRIFT')
        fail(1<=len(d['receipts'])<=6,'UNSAFE_DELTA_SIZE')
        frozen={task_id(t) for t in plan['frozen_tasks']}
        for row in d['receipts']:
            name=safe_name(row['name']);fail('/' not in name and name not in rec,'DUPLICATE_OR_UNSAFE_DELTA_RECEIPT')
            data=base64.b64decode(row['b64'],validate=True);fail(sha(data)==row['sha256'] and len(data)==row['bytes'],'DELTA_RECEIPT_SHA_DRIFT')
            obj=json.loads(data);tid=task_id(obj)
            fail(tid in frozen and tid not in complete,'DUPLICATE_OR_UNFROZEN_TASK')
            fail(obj.get('status')=='PASS' and obj.get('new_economic_PNL') is False and obj.get('plan_SHA256')==base['master']['frozen_plan_sha256'] and obj.get('original_raw_sha256')==base['master']['original_raw_sha256'],'DELTA_RECEIPT_INVALID')
            for k in ('holdout_open','ga2_open','Gate_A_approved'):fail(obj.get(k) is False,'DELTA_GATE_DRIFT')
            assert_receipt_tests(obj,name)
            rec[name]=data;complete.add(tid)
        fail(d['new_count']==len(rec) and d['new_count']<=710,'DELTA_COUNT_INVALID')
        last_sha=sha(raw)
    return {'status':'GITHUB_CHAIN_RECONSTRUCTED_SHA_VERIFIED','completed':len(rec),'pending':710-len(rec),'tip_sha256':last_sha,'next':next_tasks(plan,complete)}
def build_delta(baseline_zip,baseline_sha,previous_deltas,new_dir,out,max_new=6):
    base=decode_zip_bytes(exact_file(baseline_zip,baseline_sha),baseline_sha)
    curr=load_chain(exact_file(baseline_zip,baseline_sha),baseline_sha,previous_deltas)
    known={task_id(json.loads(v)) for v in base['receipts'].values()};known_names=set(base['receipts'])
    for f in previous_deltas:
        d=json.loads(pathlib.Path(f).read_bytes())
        for x in d['receipts']:known.add(task_id(json.loads(base64.b64decode(x['b64']))));known_names.add(x['name'])
    frozen={task_id(t) for t in base['plan']['frozen_tasks']};new=[]
    for path in sorted(pathlib.Path(new_dir).glob('*.json')):
        safe_name(path.name);b=path.read_bytes();obj=json.loads(b);tid=task_id(obj)
        fail(path.name not in known_names and tid in frozen and tid not in known,'NONNEW_OR_UNFROZEN_TASK')
        fail(obj.get('status')=='PASS' and obj.get('new_economic_PNL') is False and obj.get('plan_SHA256')==base['master']['frozen_plan_sha256'] and obj.get('original_raw_sha256')==base['master']['original_raw_sha256'],'INVALID_NEW_RECEIPT')
        for flag in ('holdout_open','ga2_open','Gate_A_approved'):fail(obj.get(flag) is False,'NEW_GATE_DRIFT')
        assert_receipt_tests(obj,path.name)
        new.append({'name':path.name,'bytes':len(b),'sha256':sha(b),'b64':base64.b64encode(b).decode('ascii')})
    fail(1<=len(new)<=max_new<=6,'MAX_SIX_DELTA_RECEIPTS')
    fail(curr['completed']+len(new)<=710,'DELTA_OVERFLOW')
    d={'schema':'QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1','parent_sha256':curr['tip_sha256'],'previous_count':curr['completed'],'new_count':curr['completed']+len(new),'frozen_plan_sha256':base['master']['frozen_plan_sha256'],'receipts':new,'no_new_PnL':True,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'verification_contract':'UPLOAD_BLOB_READBACK_COMPARE_SHA256_AND_GIT_BLOB_SHA1_THEN_CAS_PROMOTE_POINTER'}
    raw=(json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode();pathlib.Path(out).write_bytes(raw)
    check=load_chain(exact_file(baseline_zip,baseline_sha),baseline_sha,[*previous_deltas,out]);return {**check,'new':len(new),'delta_sha256':sha(raw),'delta_git_blob_sha1':gb(raw),'delta_bytes':len(raw)}
def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='command',required=True)
    q=sp.add_parser('verify-baseline');q.add_argument('--zip',required=True);q.add_argument('--sha256',required=True)
    q=sp.add_parser('restore-ascii');q.add_argument('--folder',required=True);q.add_argument('--index',required=True);q.add_argument('--out',required=True);q.add_argument('--sha256',required=True)
    q=sp.add_parser('verify-chain');q.add_argument('--zip',required=True);q.add_argument('--sha256',required=True);q.add_argument('--delta',action='append',default=[])
    q=sp.add_parser('build-delta');q.add_argument('--zip',required=True);q.add_argument('--sha256',required=True);q.add_argument('--previous-delta',action='append',default=[]);q.add_argument('--new-dir',required=True);q.add_argument('--out',required=True)
    a=ap.parse_args()
    try:
        if a.command=='verify-baseline':o=verify_baseline(a.zip,a.sha256)
        elif a.command=='restore-ascii':
            b=restore_ascii_parts(a.folder,a.index,a.sha256);pathlib.Path(a.out).write_bytes(b);o=verify_baseline(a.out,a.sha256)
        elif a.command=='verify-chain':o=load_chain(exact_file(a.zip,a.sha256),a.sha256,a.delta)
        else:o=build_delta(a.zip,a.sha256,a.previous_delta,a.new_dir,a.out)
        print(json.dumps(o,sort_keys=True,ensure_ascii=False));return 0
    except (Stop,KeyError,ValueError,TypeError,IndexError,FileNotFoundError,zipfile.BadZipFile) as e:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(e)},sort_keys=True),file=sys.stderr);return 3
if __name__=='__main__':sys.exit(main())
