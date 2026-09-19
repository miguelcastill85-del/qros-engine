#!/usr/bin/env python3
from qros_fenced_runtime_lease_guard_v1 import new_lease
from qros_fenced_heavy_job_supervisor_v1 import validate_binding

def spec(l):
    return {'job_id':l['job_id'],'expected_receipt':{'structural_group_index':l['group_index'],'lease_epoch':l['lease_epoch'],'lease_id':l['lease_id'],'fence_token':l['fence_token']}}

def main():
    l=new_lease('J10',10,3,'runtime-A','2026-09-19T00:00:00Z','2026-09-19T01:00:00Z')
    s=spec(l); cases=[]
    cases.append(validate_binding(s,l,'2026-09-19T00:30:00Z')==(True,'PASS'))
    x=spec(l);x['job_id']='JX';cases.append(validate_binding(x,l,'2026-09-19T00:30:00Z')[1]=='JOB_ID_LEASE_MISMATCH')
    x=spec(l);x['expected_receipt']['structural_group_index']=11;cases.append(validate_binding(x,l,'2026-09-19T00:30:00Z')[1]=='GROUP_INDEX_LEASE_MISMATCH')
    for k in ['lease_epoch','lease_id','fence_token']:
        x=spec(l);x['expected_receipt'][k]='bad' if k!='lease_epoch' else 99
        cases.append(validate_binding(x,l,'2026-09-19T00:30:00Z')[1]=='EXPECTED_RECEIPT_FENCE_MISMATCH:'+k)
    cases.append(validate_binding(s,l,'2026-09-19T01:00:01Z')[1]=='LEASE_EXPIRED')
    x=spec(l);x['expected_receipt']=None;cases.append(validate_binding(x,l,'2026-09-19T00:30:00Z')[1]=='EXPECTED_RECEIPT_INVALID')
    assert all(cases),cases
    print('PASS 8/8')
if __name__=='__main__':main()
