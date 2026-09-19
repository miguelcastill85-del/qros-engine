#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
SCHEMA='QROS_CROSS_RUNTIME_ACTIVE_CLAIM_GUARD_1.0'
BOOT=Path('/proc/sys/kernel/random/boot_id')

def local_boot_id():
    if not BOOT.is_file(): return None
    x=BOOT.read_text(encoding='utf-8').strip()
    return x or None

def birth_boot_id(birth):
    if not isinstance(birth,str): return None
    m=re.fullmatch(r'linux:([^:]+):([^:]+)',birth)
    return m.group(1) if m else None

def validate(receipt:dict, boot_id:str|None=None):
    if receipt.get('status')!='RUNNING_ADOPTABLE':
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'RECEIPT_NOT_RUNNING_ADOPTABLE'}
    rt=receipt.get('runtime')
    if not isinstance(rt,dict):
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'RUNTIME_IDENTITY_MISSING'}
    if int(rt.get('attempt',-1))<1 or not rt.get('claim_token'):
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'DURABLE_CLAIM_IDENTITY_INCOMPLETE'}
    boots=[birth_boot_id(rt.get('bootstrap_birth')),birth_boot_id(rt.get('worker_birth'))]
    if any(x is None for x in boots):
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'PROCESS_BIRTH_SCOPE_UNREADABLE'}
    if len(set(boots))!=1:
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'PROCESS_BIRTH_SCOPE_INCONSISTENT'}
    here=boot_id if boot_id is not None else local_boot_id()
    if not here:
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'LOCAL_BOOT_ID_UNAVAILABLE'}
    remote=boots[0]
    if remote!=here:
        return {'schema':SCHEMA,'status':'FAIL_CLOSED','reason':'FOREIGN_RUNTIME_IDENTITY_UNVERIFIABLE','original_boot_id':remote,'local_boot_id':here,'death_proven':False,'relaunch_allowed':False}
    return {'schema':SCHEMA,'status':'PASS','reason':'SAME_RUNTIME_SCOPE','boot_id':here,'death_proven':False,'relaunch_allowed':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--running-receipt',type=Path,required=True);a=ap.parse_args()
    try:r=json.loads(a.running_receipt.read_text(encoding='utf-8'));out=validate(r)
    except Exception as e:out={'schema':SCHEMA,'status':'FAIL_CLOSED','reason':f'{type(e).__name__}:{e}'}
    print(json.dumps(out,sort_keys=True));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
