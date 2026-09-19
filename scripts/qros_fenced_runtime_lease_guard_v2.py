#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, uuid
from pathlib import Path
SCHEMA='QROS_FENCED_RUNTIME_LEASE_GUARD_2.0'

def parse_ts(s):
 x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
 if x.tzinfo is None:raise ValueError('NAIVE_TIMESTAMP')
 return x.astimezone(dt.timezone.utc)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def token(l):return hashlib.sha256(canonical({k:l[k] for k in ['job_id','group_index','lease_epoch','owner_runtime_id','lease_id']})).hexdigest()
def validate_lease(l,now=None):
 req={'schema','job_id','group_index','lease_epoch','lease_id','owner_runtime_id','issued_at','expires_at','state','fence_token'}
 miss=req-set(l)
 if miss:return False,'LEASE_FIELDS_MISSING:'+','.join(sorted(miss))
 if l['state']!='ACTIVE':return False,'LEASE_NOT_ACTIVE'
 if int(l['lease_epoch'])<1:return False,'LEASE_EPOCH_INVALID'
 if l['fence_token']!=token(l):return False,'FENCE_TOKEN_INVALID'
 t=parse_ts(now) if now else dt.datetime.now(dt.timezone.utc)
 if t>parse_ts(l['expires_at']):return False,'LEASE_EXPIRED'
 return True,'PASS'
def new_lease(job_id,group_index,epoch,runtime_id,issued_at,expires_at,supersedes=None):
 x={'schema':'QROS_FENCED_RUNTIME_LEASE_2.0','job_id':job_id,'group_index':int(group_index),'lease_epoch':int(epoch),'lease_id':uuid.uuid4().hex,'owner_runtime_id':runtime_id,'issued_at':issued_at,'expires_at':expires_at,'state':'ACTIVE'}
 if supersedes:x['supersedes']=supersedes
 x['fence_token']=token(x);return x
def supersede_for_migration(old,new_runtime_id,issued_at,expires_at,cutover):
 ok,why=validate_lease(old,now=issued_at)
 if not ok and why!='LEASE_EXPIRED':raise RuntimeError('OLD_LEASE_INVALID:'+why)
 req={'status','old_lease_id','old_lease_epoch','old_fence_token','old_epoch_promotion_revoked','scientific_unit_same','new_epoch'}
 if req-set(cutover):raise RuntimeError('CUTOVER_FIELDS_MISSING')
 if cutover['status']!='AUTHORIZED_MIGRATION_CUTOVER':raise RuntimeError('CUTOVER_NOT_AUTHORIZED')
 if cutover['old_lease_id']!=old['lease_id'] or int(cutover['old_lease_epoch'])!=int(old['lease_epoch']) or cutover['old_fence_token']!=old['fence_token']:raise RuntimeError('CUTOVER_OLD_LEASE_MISMATCH')
 if cutover['old_epoch_promotion_revoked'] is not True:raise RuntimeError('OLD_EPOCH_NOT_REVOKED')
 if cutover['scientific_unit_same'] is not True:raise RuntimeError('SCIENTIFIC_UNIT_CHANGED')
 if int(cutover['new_epoch'])!=int(old['lease_epoch'])+1:raise RuntimeError('NEW_EPOCH_NOT_MONOTONIC')
 return new_lease(old['job_id'],old['group_index'],cutover['new_epoch'],new_runtime_id,issued_at,expires_at,{'lease_id':old['lease_id'],'lease_epoch':old['lease_epoch'],'fence_token':old['fence_token'],'reason':'MIGRATION_FENCED_NO_DEATH_CLAIM'})
def validate_worker_receipt(current,receipt):
 for k in ['job_id','group_index','lease_epoch','lease_id','fence_token']:
  if receipt.get(k)!=current.get(k):return False,'STALE_OR_MISMATCHED_RECEIPT:'+k
 if receipt.get('status')!='PASS':return False,'WORKER_NOT_PASS'
 return True,'PASS'
def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
 p=sp.add_parser('validate');p.add_argument('--lease',type=Path,required=True);p.add_argument('--now')
 p=sp.add_parser('validate-receipt');p.add_argument('--lease',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
 a=ap.parse_args();l=json.loads(a.lease.read_text());ok,why=(validate_lease(l,a.now) if a.cmd=='validate' else validate_worker_receipt(l,json.loads(a.receipt.read_text())));print(json.dumps({'schema':SCHEMA,'status':'PASS' if ok else 'FAIL_CLOSED','reason':why},sort_keys=True));return 0 if ok else 2
if __name__=='__main__':raise SystemExit(main())
