#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
SCHEMA='QROS_LEGACY_AUTHORITY_FENCE_GUARD_1.0'

def validate_cutover(cutover:dict, legacy:dict):
    req=['status','group_index','capsule_blob_sha1','legacy_job_id','legacy_job_spec_sha256','legacy_claim_token','legacy_bootstrap_birth','legacy_worker_birth','legacy_promotion_revoked','terminal_receipt_absent_at_cutover','recovery_job_id']
    miss=[k for k in req if k not in cutover]
    if miss:return False,'CUTOVER_FIELDS_MISSING:'+','.join(miss)
    if cutover['status']!='ACTIVE':return False,'CUTOVER_NOT_ACTIVE'
    if cutover['legacy_promotion_revoked'] is not True:return False,'LEGACY_PROMOTION_NOT_REVOKED'
    if cutover['terminal_receipt_absent_at_cutover'] is not True:return False,'TERMINAL_RECEIPT_ABSENCE_NOT_PROVEN'
    if legacy.get('status')!='RUNNING_ADOPTABLE':return False,'LEGACY_RECEIPT_NOT_RUNNING_ADOPTABLE'
    rt=legacy.get('runtime',{})
    checks={
      'group_index': legacy.get('subject',{}).get('structural_group_index')==cutover['group_index'],
      'legacy_job_id': rt.get('job_id')==cutover['legacy_job_id'],
      'legacy_job_spec_sha256': rt.get('job_spec_sha256')==cutover['legacy_job_spec_sha256'],
      'legacy_claim_token': rt.get('claim_token')==cutover['legacy_claim_token'],
      'legacy_bootstrap_birth': rt.get('bootstrap_birth')==cutover['legacy_bootstrap_birth'],
      'legacy_worker_birth': rt.get('worker_birth')==cutover['legacy_worker_birth'],
    }
    for k,v in checks.items():
        if not v:return False,'LEGACY_IDENTITY_MISMATCH:'+k
    if cutover['recovery_job_id']==cutover['legacy_job_id']:return False,'RECOVERY_JOB_ID_MUST_DIFFER'
    return True,'PASS'

def validate_promotion(cutover:dict, receipt:dict):
    jid=receipt.get('job_id')
    if jid==cutover.get('legacy_job_id'):
        return False,'LEGACY_JOB_PERMANENTLY_REVOKED'
    if jid!=cutover.get('recovery_job_id'):
        return False,'UNAUTHORIZED_JOB_ID'
    if receipt.get('group_index')!=cutover.get('group_index'):
        return False,'GROUP_INDEX_MISMATCH'
    if receipt.get('capsule_blob_sha1')!=cutover.get('capsule_blob_sha1'):
        return False,'CAPSULE_IDENTITY_MISMATCH'
    if receipt.get('status')!='PASS':return False,'RECEIPT_NOT_PASS'
    return True,'PASS'

def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('validate-cutover');p.add_argument('--cutover',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True)
    p=sp.add_parser('validate-promotion');p.add_argument('--cutover',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args()
    try:
      c=json.loads(a.cutover.read_text())
      if a.cmd=='validate-cutover':ok,why=validate_cutover(c,json.loads(a.legacy.read_text()))
      else:ok,why=validate_promotion(c,json.loads(a.receipt.read_text()))
      out={'schema':SCHEMA,'status':'PASS' if ok else 'FAIL_CLOSED','reason':why}
    except Exception as e:out={'schema':SCHEMA,'status':'FAIL_CLOSED','reason':f'{type(e).__name__}:{e}'}
    print(json.dumps(out,sort_keys=True));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
