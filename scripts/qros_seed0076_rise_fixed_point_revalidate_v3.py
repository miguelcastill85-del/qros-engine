#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path

CORE='scripts/qros_seed0076_rise_fixed_point_revalidate_v1.py'
CORE_BLOB='6b4470582cfcd73acb088f58114edf9ba480f757'
B_V2='scripts/qros_seed_universe_enumerator_b_v2.py'
B_V3='scripts/qros_seed_universe_enumerator_b_v3.py'
B_V3_BLOB='6391f0291128e97f1d905cb67c7d3c837b6927db'
STABLE='control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json'
CORRECTION='control/QROS_SEED0076_ENUMERATOR_B_ROOT_DEFINITION_CORRECTION_20260914_v1.json'
EXPECTED_ACTIVE='control/QROS_DETERMINISTIC_KERNEL_V251_ACTIVE_EXECUTION_VALIDATION_PASS_20260914_v1.json'
EXPECTED_ACTION='RECOVER_OR_REVALIDATE_RISE_FIXED_POINT_NO_PNL'

def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p:Path): return json.loads(p.read_text(encoding='utf-8'))
def fail(code,detail=''): raise RuntimeError(code if not detail else f'{code}:{detail}')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.repo_root).resolve()
    core=root/CORE
    if not core.is_file() or blob(core)!=CORE_BLOB: fail('CORE_PIN_MISMATCH')
    b3=root/B_V3
    if not b3.is_file() or blob(b3)!=B_V3_BLOB: fail('ENUM_B_V3_PIN_MISMATCH')
    correction=root/CORRECTION
    if not correction.is_file(): fail('CORRECTION_RECEIPT_MISSING')
    stable=load(root/STABLE)
    if stable.get('machine_action_type')!=EXPECTED_ACTION: fail('ACTION_TYPE')
    if stable.get('economic_pnl_read') is not False or stable.get('ga2_open') is not False or stable.get('holdout_open') is not False: fail('ECONOMIC_FIREWALL')
    node=stable.get('active_execution_validation_receipt')
    if not isinstance(node,dict): fail('ACTIVE_RECEIPT_NODE')
    rel,want=node.get('path'),node.get('git_blob_sha1')
    if rel!=EXPECTED_ACTIVE: fail('ACTIVE_RECEIPT_PATH',str(rel))
    p=root/rel
    if not p.is_file(): fail('ACTIVE_RECEIPT_MISSING')
    got=blob(p)
    if got!=want: fail('ACTIVE_RECEIPT_PIN_MISMATCH',f'{got}!={want}')
    spec=importlib.util.spec_from_file_location('qros_rise_core_v1',core); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    mod.PINS[mod.ACTIVE_EXEC]=want
    old_enum_b=mod.ENUM_B
    mod.PINS.pop(old_enum_b,None)
    mod.ENUM_B=B_V3
    mod.PINS[B_V3]=B_V3_BLOB
    with tempfile.TemporaryDirectory() as td:
        inner=Path(td)/'inner.json'; old=list(sys.argv); sys.argv=[str(core),'--repo-root',str(root),'--out',str(inner)]
        try: rc=mod.main()
        finally: sys.argv=old
        if rc not in (None,0): fail('CORE_EXECUTION_FAIL',str(rc))
        r=load(inner)
    if r.get('status')!='PASS' or r.get('post_expansion_rise_fixed_point') is not True: fail('CORE_RESULT_NOT_PASS')
    if r.get('enumerator_a',{}).get('base_tuple_root_sha256')!=r.get('enumerator_b',{}).get('base_tuple_root_sha256'): fail('ROOT_PARITY_BASE')
    if r.get('enumerator_a',{}).get('filter_package_root_sha256')!=r.get('enumerator_b',{}).get('filter_package_root_sha256'): fail('ROOT_PARITY_FILTER')
    if r.get('enumerator_a',{}).get('management_root_sha256')!=r.get('enumerator_b',{}).get('management_root_sha256'): fail('ROOT_PARITY_MANAGEMENT')
    r['schema']='QROS_SEED0076_POST_EXPANSION_RISE_FIXED_POINT_REVALIDATION_3.0'
    r['validator_v3']={
      'core_path':CORE,'core_git_blob_sha1':CORE_BLOB,
      'enumerator_b_path':B_V3,'enumerator_b_git_blob_sha1':B_V3_BLOB,
      'active_execution_receipt_path':rel,'active_execution_receipt_git_blob_sha1':want,
      'correction_receipt_path':CORRECTION,
      'authority_pin_mode':'STABLE_POINTER_DYNAMIC_ACTIVE_RECEIPT_PLUS_PINNED_CORRECTED_ENUMERATOR',
      'scientific_universe_changed':False
    }
    r.pop('receipt_sha256',None); r['receipt_sha256']=mod.sha(r)
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','decision':r['decision'],'receipt_sha256':r['receipt_sha256'],'signal_universe_root_sha256':r['signal_universe_root_sha256'],'ontology_root_sha256':r['ontology_root_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
