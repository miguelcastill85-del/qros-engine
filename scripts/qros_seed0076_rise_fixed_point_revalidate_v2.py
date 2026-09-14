#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path

CORE='scripts/qros_seed0076_rise_fixed_point_revalidate_v1.py'
CORE_BLOB='6b4470582cfcd73acb088f58114edf9ba480f757'
STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
EXPECTED_ACTIVE='control/QROS_DETERMINISTIC_KERNEL_V251_ACTIVE_EXECUTION_VALIDATION_PASS_20260914_v1.json'

def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p:Path): return json.loads(p.read_text(encoding='utf-8'))
def fail(code,detail=''):
    raise RuntimeError(code if not detail else f'{code}:{detail}')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.repo_root).resolve()
    core=root/CORE
    if not core.is_file(): fail('CORE_MISSING',CORE)
    got=blob(core)
    if got!=CORE_BLOB: fail('CORE_PIN_MISMATCH',f'{got}!={CORE_BLOB}')
    stable=load(root/STABLE); node=stable.get('active_execution_validation_receipt')
    if not isinstance(node,dict): fail('DYNAMIC_ACTIVE_RECEIPT_NODE')
    rel,want=node.get('path'),node.get('git_blob_sha1')
    if rel!=EXPECTED_ACTIVE: fail('DYNAMIC_ACTIVE_RECEIPT_PATH',str(rel))
    if not isinstance(want,str) or len(want)!=40: fail('DYNAMIC_ACTIVE_RECEIPT_HASH')
    p=root/rel
    if not p.is_file(): fail('DYNAMIC_ACTIVE_RECEIPT_MISSING')
    actual=blob(p)
    if actual!=want: fail('DYNAMIC_ACTIVE_RECEIPT_PIN_MISMATCH',f'{actual}!={want}')
    spec=importlib.util.spec_from_file_location('qros_rise_core_v1',core); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    mod.PINS[mod.ACTIVE_EXEC]=want
    with tempfile.TemporaryDirectory() as td:
        inner=Path(td)/'inner.json'; old=list(sys.argv); sys.argv=[str(core),'--repo-root',str(root),'--out',str(inner)]
        try: rc=mod.main()
        finally: sys.argv=old
        if rc not in (None,0): fail('CORE_EXECUTION_FAIL',str(rc))
        r=load(inner)
    if r.get('status')!='PASS' or r.get('post_expansion_rise_fixed_point') is not True: fail('CORE_RESULT_NOT_PASS')
    r['schema']='QROS_SEED0076_POST_EXPANSION_RISE_FIXED_POINT_REVALIDATION_2.0'
    r['validator_v2']={'core_path':CORE,'core_git_blob_sha1':CORE_BLOB,'active_execution_receipt_path':rel,'active_execution_receipt_git_blob_sha1':want,'authority_pin_mode':'DERIVED_FROM_STABLE_POINTER_AND_BYTE_VERIFIED'}
    r.pop('receipt_sha256',None); r['receipt_sha256']=mod.sha(r)
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','decision':r['decision'],'receipt_sha256':r['receipt_sha256'],'active_execution_receipt_git_blob_sha1':want},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
