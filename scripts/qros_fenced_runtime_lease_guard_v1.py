#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, uuid
from pathlib import Path
SCHEMA='QROS_FENCED_RUNTIME_LEASE_GUARD_1.0'

def parse_ts(s:str)->dt.datetime:
    x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('NAIVE_TIMESTAMP')
    return x.astimezone(dt.timezone.utc)

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def token(lease): return hashlib.sha256(canonical({k:lease[k] for k in ['job_id','group_index','lease_epoch','owner_runtime_id','lease_id']})).hexdigest()

def validate_lease(lease:dict, now:str|None=None):
    req={'schema','job_id','group_index','lease_epoch','lease_id','owner_runtime_id','issued_at','expires_at','state','fence_token'}
    miss=req-set(lease)
    if miss:return False,'LEASE_FIELDS_MISSING:'+','.join(sorted(miss))
    if lease['state']!='ACTIVE':return False,'LEASE_NOT_ACTIVE'
    if int(lease['lease_epoch'])<1:return False,'LEASE_EPOCH_INVALID'
    if lease['fence_token']!=token(lease):return False,'FENCE_TOKEN_INVALID'
    t=parse_ts(now) if now else dt.datetime.now(dt.timezone.utc)
    if t>parse_ts(lease['expires_at']):return False,'LEASE_EXPIRED'
    return True,'PASS'

def new_lease(job_id:str,group_index:int,epoch:int,runtime_id:str,issued_at:str,expires_at:str,supersedes:dict|None=None):
    x={'schema':'QROS_FENCED_RUNTIME_LEASE_1.0','job_id':job_id,'group_index':int(group_index),'lease_epoch':int(epoch),'lease_id':uuid.uuid4().hex,'owner_runtime_id':runtime_id,'issued_at':issued_at,'expires_at':expires_at,'state':'ACTIVE'}
    if supersedes:x['supersedes']=supersedes
    x['fence_token']=token(x);return x

def supersede_expired(old:dict,new_runtime_id:str,issued_at:str,expires_at:str):
    ok,why=validate_lease(old,now=issued_at)
    if ok:raise RuntimeError('OLD_LEASE_NOT_EXPIRED')
    if why!='LEASE_EXPIRED':raise RuntimeError('OLD_LEASE_INVALID:'+why)
    return new_lease(old['job_id'],old['group_index'],int(old['lease_epoch'])+1,new_runtime_id,issued_at,expires_at,{'lease_id':old['lease_id'],'lease_epoch':old['lease_epoch'],'fence_token':old['fence_token'],'reason':'EXPIRED_AND_FENCED'})

def validate_worker_receipt(lease:dict,receipt:dict):
    for k in ['job_id','group_index','lease_epoch','lease_id','fence_token']:
        if receipt.get(k)!=lease.get(k):return False,'STALE_OR_MISMATCHED_RECEIPT:'+k
    if receipt.get('status')!='PASS':return False,'WORKER_NOT_PASS'
    return True,'PASS'

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('validate');p.add_argument('--lease',type=Path,required=True);p.add_argument('--now')
    p=sub.add_parser('validate-receipt');p.add_argument('--lease',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args()
    try:
        l=json.loads(a.lease.read_text())
        if a.cmd=='validate':ok,why=validate_lease(l,a.now)
        else:ok,why=validate_worker_receipt(l,json.loads(a.receipt.read_text()))
        out={'schema':SCHEMA,'status':'PASS' if ok else 'FAIL_CLOSED','reason':why}
    except Exception as e:out={'schema':SCHEMA,'status':'FAIL_CLOSED','reason':f'{type(e).__name__}:{e}'}
    print(json.dumps(out,sort_keys=True));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
