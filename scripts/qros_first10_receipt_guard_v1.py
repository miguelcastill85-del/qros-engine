#!/usr/bin/env python3
"""Seed0076: strict, read-only execution receipt and authority guard.

A PASS from this guard is NOT a scientific gate pass and never permits deployment.
Only the exact 10-shard research scope is recognized. No economic outputs are read.
Python standard library only. Designed to execute before the existing W09 scorer.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

SCOPE_BLOB = "ab31ded2702f57b54eebc052f1c8aa2737cf2479"
POINTER_BLOB = "5a88937d571e4bcc938c9ce71570092e0abfae6d"
MAIN_COMMIT = "f2a513c56e297b5ec72db07568c71c12d65a638d"
XAU_DEV_SHA = "3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53"
NQX_DEV_SHA = "451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"
# This branch has NOT issued a production grant. Do not silently manufacture one.
PRODUCTION_GRANT_BLOB = None

class PreflightError(ValueError):
    pass

def require(condition, error):
    if not condition:
        raise PreflightError(error)

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def git_blob(path):
    raw = Path(path).read_bytes()
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def json_file(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def verify_authority(scope_path, pointer_path, pins=(SCOPE_BLOB, POINTER_BLOB)):
    require(git_blob(scope_path) == pins[0], 'SCOPE_BYTES_DRIFT')
    require(git_blob(pointer_path) == pins[1], 'POINTER_BYTES_DRIFT')
    s, p = json_file(scope_path), json_file(pointer_path)
    require(s.get('campaign') == CAMPAIGN and p.get('campaign') == CAMPAIGN, 'CAMPAIGN_MISMATCH')
    require(s.get('source_main_commit') == MAIN_COMMIT and s.get('base_frontier_version') == 'V259', 'SCOPE_AUTHORITY_MISMATCH')
    require(s.get('base_pointer_blob_sha1') == pins[1], 'SCOPE_POINTER_CONFLICT')
    require(p.get('current_version') == 'V259' and p.get('scientific_state') == 'PREREGISTERED_NO_RESULTS', 'POINTER_STATE_DRIFT')
    require(p.get('verified_counts', {}).get('ga1_formally_completed_shards') == 10, 'STRUCTURAL_COUNT_DRIFT')
    require(p.get('economic_pnl_read') is False and p.get('holdout_open') is False, 'EXPOSURE_STATE_CONFLICT')
    shards = s.get('shards')
    require(isinstance(shards, list) and [x.get('ordinal') for x in shards] == list(range(1, 11)), 'SCOPE_FIFO_DRIFT')
    require(sum(x['expected_signal_configs'] for x in shards) == 8046720, 'SCOPE_CONFIG_DRIFT')
    require(sum(x['distinct_mask_classes'] for x in shards) == 2065443, 'SCOPE_MASK_DRIFT')
    return s, p

def inside_regular_file(root, relative):
    require(isinstance(relative, str) and relative and '\\' not in relative, 'INVALID_RECEIPT_PATH')
    require(not os.path.isabs(relative) and '..' not in Path(relative).parts, 'RECEIPT_PATH_TRAVERSAL')
    root = Path(root).resolve(strict=True)
    target = (root / relative).resolve(strict=True)
    require(target.is_relative_to(root) and target.is_file(), 'RECEIPT_ESCAPES_ROOT')
    return target

def verify_execution_receipt(manifest, receipt_root, *, scope_shard=None):
    """Validate actual bytes and domain, not a manifest's unverified PASS claim."""
    require(manifest.get('mode') == 'PRODUCTION', 'NOT_PRODUCTION_INPUT')
    require(manifest.get('execution_parity_pass') is True, 'NO_EXECUTION_PARITY')
    ref = manifest.get('trade_by_trade_execution_receipt')
    require(isinstance(ref, dict) and isinstance(ref.get('sha256'), str) and len(ref['sha256']) == 64, 'RECEIPT_REF_INVALID')
    try:
        rp = inside_regular_file(receipt_root, ref.get('path'))
    except (FileNotFoundError, OSError):
        raise PreflightError('RECEIPT_MISSING')
    require(sha256_file(rp) == ref['sha256'], 'RECEIPT_BYTES_MISMATCH')
    r = json_file(rp)
    require(r.get('status') == 'PASS' and r.get('synthetic_only') is False and r.get('mode') == 'PRODUCTION', 'SYNTHETIC_OR_INVALID_RECEIPT')
    require(r.get('independent_generator_parity') is True, 'INDEPENDENT_GENERATOR_NOT_PROVED')
    require(r.get('trade_by_trade_parity') is True, 'TRADE_PARITY_NOT_PROVED')
    require(isinstance(r.get('oracle_receipt_sha256'), str) and len(r['oracle_receipt_sha256']) == 64, 'ORACLE_BYTES_UNBOUND')
    try:
        oracle_path = inside_regular_file(receipt_root, r.get('oracle_receipt_path'))
    except (FileNotFoundError, OSError):
        raise PreflightError('ORACLE_RECEIPT_MISSING')
    require(sha256_file(oracle_path) == r['oracle_receipt_sha256'], 'ORACLE_RECEIPT_BYTES_MISMATCH')
    oracle = json_file(oracle_path)
    require(oracle.get('status') == 'PASS' and oracle.get('implementation') == 'INDEPENDENT_EVENT_GENERATOR', 'ORACLE_NOT_INDEPENDENT_GENERATOR')
    require(isinstance(r.get('producer_generator_code_sha256'), str) and len(r['producer_generator_code_sha256']) == 64, 'PRODUCER_CODE_UNBOUND')
    require(isinstance(oracle.get('generator_code_sha256'), str) and len(oracle['generator_code_sha256']) == 64
            and oracle['generator_code_sha256'] != r['producer_generator_code_sha256'], 'ORACLE_SHARES_PRODUCER_CODE')
    require(oracle.get('dev_sha256') == r.get('dev_sha256') and oracle.get('maskpack_sha256') == r.get('maskpack_sha256')
            and oracle.get('trade_by_trade_parity') is True, 'ORACLE_DOMAIN_OR_PARITY_MISMATCH')
    require(r.get('dev_sha256') in (XAU_DEV_SHA, NQX_DEV_SHA), 'DEV_NOT_FROZEN')
    require(isinstance(r.get('maskpack_sha256'), str) and len(r['maskpack_sha256']) == 64, 'MASKPACK_UNBOUND')
    require(isinstance(r.get('trades_sha256'), str) and len(r['trades_sha256']) == 64, 'TRADES_UNBOUND')
    # A correct SHA string in an attestation cannot substitute for its actual bytes.
    for filename_key, digest_key, missing in (
        ('dev_path', 'dev_sha256', 'DEV_CARRIER_MISSING'),
        ('maskpack_path', 'maskpack_sha256', 'MASKPACK_MISSING'),
        ('trades_path', 'trades_sha256', 'EXECUTED_TRADES_MISSING'),
    ):
        try:
            artifact_path = inside_regular_file(receipt_root, r.get(filename_key))
        except (FileNotFoundError, OSError):
            raise PreflightError(missing)
        require(sha256_file(artifact_path) == r[digest_key], digest_key.upper() + '_BYTES_MISMATCH')
    if scope_shard is not None:
        require(r['dev_sha256'] == (XAU_DEV_SHA if scope_shard['asset'] == 'XAUUSD' else NQX_DEV_SHA), 'DEV_DOMAIN_MISMATCH')
        require(r.get('semantic_class_root_sha256') == scope_shard['semantic_class_root_sha256'], 'MASK_CLASS_ROOT_MISMATCH')
        require(r.get('alias_root_sha256') == scope_shard['alias_root_sha256'], 'ALIAS_ROOT_MISMATCH')
    return r

def audit_one_shard(scope_shard, manifest=None, receipt_root=None):
    missing = []
    if manifest is None:
        missing.append('EXECUTION_MANIFEST_NOT_RECOVERED')
    else:
        if not receipt_root:
            missing.append('EXECUTION_RECEIPT_ROOT_NOT_RECOVERED')
        else:
            try:
                verify_execution_receipt(manifest, receipt_root, scope_shard=scope_shard)
            except (PreflightError, OSError, json.JSONDecodeError) as exc:
                missing.append(str(exc))
    if PRODUCTION_GRANT_BLOB is None:
        missing.append('PRODUCTION_GRANT_NOT_FROZEN')
    return {'shard': scope_shard['ordinal'], 'domain': '/'.join([scope_shard['asset'], scope_shard['side'], scope_shard['timeframe']]),
            'readiness': 'STAGED_NOT_ECONOMICALLY_AUTHORIZED' if missing else 'PREFLIGHT_ONLY_NO_SCIENTIFIC_PASS', 'blockers': missing}

def self_test():
    import shutil
    cases = []
    def check(name, func, error):
        try:
            func()
        except PreflightError as exc:
            require(str(exc) == error, 'TEST_WRONG_ERROR_' + name + ':' + str(exc))
            cases.append(name)
        else:
            raise AssertionError('FALSE_PASS_' + name)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        r = {'status':'PASS', 'synthetic_only':True, 'mode':'SYNTHETIC_VALIDATION'}
        (root/'r.json').write_text(json.dumps(r))
        m = {'mode':'PRODUCTION','execution_parity_pass':True,'trade_by_trade_execution_receipt':{'path':'r.json','sha256':sha256_file(root/'r.json')}}
        check('synthetic_receipt', lambda:verify_execution_receipt(m, root), 'SYNTHETIC_OR_INVALID_RECEIPT')
        m['trade_by_trade_execution_receipt']['sha256'] = '0'*64
        check('receipt_tamper', lambda:verify_execution_receipt(m,root), 'RECEIPT_BYTES_MISMATCH')
        m['trade_by_trade_execution_receipt']['path'] = '../r.json'
        check('path_escape', lambda:verify_execution_receipt(m,root), 'RECEIPT_PATH_TRAVERSAL')
        m['trade_by_trade_execution_receipt']['path'] = 'missing.json'
        check('missing_receipt', lambda:verify_execution_receipt(m,root), 'RECEIPT_MISSING')
        (root/'outside').mkdir()
        (root/'outside'/'x').write_text('ok')
        (root/'link').symlink_to('/etc/hosts')
        m['trade_by_trade_execution_receipt']['path'] = 'link'
        check('symlink_escape', lambda:verify_execution_receipt(m,root), 'RECEIPT_ESCAPES_ROOT')
        s = {'ordinal':1,'asset':'XAUUSD','side':'BUY','timeframe':'M1'}
        state=audit_one_shard(s)
        require('PRODUCTION_GRANT_NOT_FROZEN' in state['blockers'] and state['readiness']=='STAGED_NOT_ECONOMICALLY_AUTHORIZED', 'GRANT_FALSE_PASS')
        cases.append('missing_input_is_not_economic_rejection')
        # A perfectly plausible synthetic forged PASS must still fail on generator proof.
        r = {'status':'PASS','synthetic_only':False,'mode':'PRODUCTION','dev_sha256':XAU_DEV_SHA,'maskpack_sha256':'1'*64,'trades_sha256':'2'*64,
             'independent_generator_parity':False,'trade_by_trade_parity':True,'oracle_receipt_sha256':'3'*64}
        (root/'r.json').write_text(json.dumps(r));m['trade_by_trade_execution_receipt']={'path':'r.json','sha256':sha256_file(root/'r.json')}
        check('forged_reducer_parity', lambda:verify_execution_receipt(m,root), 'INDEPENDENT_GENERATOR_NOT_PROVED')
        r['independent_generator_parity']=True
        (root/'r.json').write_text(json.dumps(r)); m['trade_by_trade_execution_receipt']['sha256']=sha256_file(root/'r.json')
        check('forged_oracle_hash_without_bytes', lambda:verify_execution_receipt(m,root), 'INVALID_RECEIPT_PATH')
        oracle={'status':'PASS','implementation':'INDEPENDENT_EVENT_GENERATOR','generator_code_sha256':'4'*64,
                'dev_sha256':XAU_DEV_SHA,'maskpack_sha256':'1'*64,'trade_by_trade_parity':True}
        (root/'o.json').write_text(json.dumps(oracle));r['oracle_receipt_path']='o.json';r['oracle_receipt_sha256']=sha256_file(root/'o.json')
        r['producer_generator_code_sha256']='4'*64
        (root/'r.json').write_text(json.dumps(r));m['trade_by_trade_execution_receipt']['sha256']=sha256_file(root/'r.json')
        check('false_independence_shared_code', lambda:verify_execution_receipt(m,root), 'ORACLE_SHARES_PRODUCER_CODE')
    return {'status':'PASS','tests_passed':len(cases),'cases':cases,'economic_pnl_read':False}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--self-test', action='store_true')
    a.add_argument('--scope'); a.add_argument('--pointer')
    a.add_argument('--manifest'); a.add_argument('--receipt-root')
    args=a.parse_args()
    try:
        if args.self_test: print(json.dumps(self_test(),sort_keys=True));return
        require(args.scope and args.pointer,'AUTHORITY_FILES_REQUIRED')
        s,_=verify_authority(args.scope,args.pointer)
        m=json_file(args.manifest) if args.manifest else None
        result={'schema':'QROS_FIRST10_READ_ONLY_PREFLIGHT_1.0','scope_verified':True,'scientific_state':'PREREGISTERED_NO_RESULTS',
                'shards':[audit_one_shard(x,m if x['ordinal']==1 else None,args.receipt_root) for x in s['shards']]}
        print(json.dumps(result,sort_keys=True))
    except (PreflightError,OSError,json.JSONDecodeError) as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)}));raise SystemExit(2)
if __name__=='__main__':main()
