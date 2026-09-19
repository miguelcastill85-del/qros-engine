#!/usr/bin/env python3
from qros_cross_runtime_claim_guard_v1 import validate

def rec(status='RUNNING_ADOPTABLE',bb='linux:aaa:1',wb='linux:aaa:2',attempt=1,token='t'):
    return {'status':status,'runtime':{'bootstrap_birth':bb,'worker_birth':wb,'attempt':attempt,'claim_token':token}}

def main():
    cases=[]
    cases.append(validate(rec(),boot_id='aaa')['status']=='PASS')
    x=validate(rec(),boot_id='bbb');cases.append(x['status']=='FAIL_CLOSED' and x['reason']=='FOREIGN_RUNTIME_IDENTITY_UNVERIFIABLE' and x['death_proven'] is False and x['relaunch_allowed'] is False)
    cases.append(validate(rec(status='PASS'),boot_id='aaa')['reason']=='RECEIPT_NOT_RUNNING_ADOPTABLE')
    cases.append(validate(rec(wb='linux:bbb:2'),boot_id='aaa')['reason']=='PROCESS_BIRTH_SCOPE_INCONSISTENT')
    cases.append(validate(rec(bb='bad'),boot_id='aaa')['reason']=='PROCESS_BIRTH_SCOPE_UNREADABLE')
    cases.append(validate(rec(token=''),boot_id='aaa')['reason']=='DURABLE_CLAIM_IDENTITY_INCOMPLETE')
    assert all(cases),cases
    print('PASS 6/6')
if __name__=='__main__':main()
