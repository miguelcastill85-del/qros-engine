#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
CORE='scripts/qros_seed0076_rise_fixed_point_adversarial_v1.py'
CORE_BLOB='ea0f13b8884b22810ed1b235bede5e119e74d3cd'
PRIMARY='scripts/qros_seed0076_rise_fixed_point_revalidate_v3.py'
PRIMARY_BLOB='77368b0a683233f2d34b036919662cf98e68a133'
ORACLE='scripts/qros_seed0076_rise_fixed_point_oracle_v2.py'
ENUM_B='scripts/qros_seed_universe_enumerator_b_v3.py'
ENUM_B_BLOB='6391f0291128e97f1d905cb67c7d3c837b6927db'
def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.repo_root).resolve()
    core=root/CORE
    if not core.is_file() or blob(core)!=CORE_BLOB: raise RuntimeError('ADVERSARIAL_CORE_PIN_MISMATCH')
    if blob(root/PRIMARY)!=PRIMARY_BLOB: raise RuntimeError('PRIMARY_V3_PIN_MISMATCH')
    if blob(root/ENUM_B)!=ENUM_B_BLOB: raise RuntimeError('ENUM_B_V3_PIN_MISMATCH')
    if not (root/ORACLE).is_file(): raise RuntimeError('ORACLE_V2_MISSING')
    spec=importlib.util.spec_from_file_location('qros_rise_adv_v1',core); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    mod.PRIMARY=PRIMARY; mod.ORACLE=ORACLE; mod.ENUM_B=ENUM_B
    with tempfile.TemporaryDirectory() as td:
        inner=Path(td)/'inner.json'; old=list(sys.argv); sys.argv=[str(core),'--repo-root',str(root),'--out',str(inner)]
        try: rc=mod.main()
        finally: sys.argv=old
        if rc not in (None,0): raise RuntimeError('ADVERSARIAL_CORE_EXECUTION_FAIL')
        r=load(inner)
    if r.get('status')!='PASS': raise RuntimeError('ADVERSARIAL_CORE_NOT_PASS')
    r['schema']='QROS_SEED0076_RISE_FIXED_POINT_ADVERSARIAL_3.0'; r['adversarial_v3']={'core_path':CORE,'core_git_blob_sha1':CORE_BLOB,'primary_path':PRIMARY,'primary_git_blob_sha1':PRIMARY_BLOB,'oracle_path':ORACLE,'enumerator_b_path':ENUM_B,'enumerator_b_git_blob_sha1':ENUM_B_BLOB,'root_definition_correction_preserved':True}; r.pop('receipt_sha256',None); r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest(); Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':'PASS','cases':len(r['cases']),'receipt_sha256':r['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
