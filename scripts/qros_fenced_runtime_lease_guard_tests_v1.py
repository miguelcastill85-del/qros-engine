#!/usr/bin/env python3
from qros_fenced_runtime_lease_guard_v1 import new_lease,validate_lease,supersede_expired,validate_worker_receipt

def main():
    l=new_lease('J',9,1,'runtime-A','2026-09-19T00:00:00Z','2026-09-19T01:00:00Z')
    cases=[]
    cases.append(validate_lease(l,'2026-09-19T00:30:00Z')==(True,'PASS'))
    cases.append(validate_lease(l,'2026-09-19T01:00:01Z')==(False,'LEASE_EXPIRED'))
    bad=dict(l);bad['fence_token']='0'*64;cases.append(validate_lease(bad,'2026-09-19T00:30:00Z')[1]=='FENCE_TOKEN_INVALID')
    n=supersede_expired(l,'runtime-B','2026-09-19T01:00:01Z','2026-09-19T02:00:00Z')
    cases.append(n['lease_epoch']==2 and n['owner_runtime_id']=='runtime-B' and n['supersedes']['lease_epoch']==1)
    r={'status':'PASS','job_id':'J','group_index':9,'lease_epoch':1,'lease_id':l['lease_id'],'fence_token':l['fence_token']}
    cases.append(validate_worker_receipt(l,r)==(True,'PASS'))
    cases.append(validate_worker_receipt(n,r)[1]=='STALE_OR_MISMATCHED_RECEIPT:lease_epoch')
    r2={'status':'PASS','job_id':'J','group_index':9,'lease_epoch':2,'lease_id':n['lease_id'],'fence_token':n['fence_token']}
    cases.append(validate_worker_receipt(n,r2)==(True,'PASS'))
    failed=dict(r2);failed['status']='FAIL';cases.append(validate_worker_receipt(n,failed)[1]=='WORKER_NOT_PASS')
    assert all(cases),cases
    print('PASS 8/8')
if __name__=='__main__':main()
