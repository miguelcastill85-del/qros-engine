#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path

CORE='scripts/qros_seed0076_rise_fixed_point_oracle_v1.py'
CORE_BLOB='c1ba9b79a99fccb1e8459a10a77d88a04c28053a'
B_V3='scripts/qros_seed_universe_enumerator_b_v3.py'
B_V3_BLOB='6391f0291128e97f1d905cb67c7d3c837b6927db'

def blob(p:Path):
    b=p.read_bytes(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--primary',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); root=Path(a.repo_root).resolve()
    core=root/CORE; b3=root/B_V3
    if not core.is_file() or blob(core)!=CORE_BLOB: raise RuntimeError('ORACLE_CORE_PIN_MISMATCH')
    if not b3.is_file() or blob(b3)!=B_V3_BLOB: raise RuntimeError('ORACLE_ENUM_B_V3_PIN_MISMATCH')
    spec=importlib.util.spec_from_file_location('qros_rise_oracle_v1',core); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod); mod.ENUM_B=B_V3
    with tempfile.TemporaryDirectory() as td:
        inner=Path(td)/'inner.json'; old=list(sys.argv); sys.argv=[str(core),'--repo-root',str(root),'--primary',str(Path(a.primary).resolve()),'--out',str(inner)]
        try: rc=mod.main()
        finally: sys.argv=old
        if rc not in (None,0): raise RuntimeError('ORACLE_CORE_EXECUTION_FAIL')
        r=load(inner)
    if r.get('status')!='PASS': raise RuntimeError('ORACLE_CORE_NOT_PASS')
    r['schema']='QROS_SEED0076_RISE_FIXED_POINT_ORACLE_2.0'
    r['oracle_v2']={'core_path':CORE,'core_git_blob_sha1':CORE_BLOB,'enumerator_b_path':B_V3,'enumerator_b_git_blob_sha1':B_V3_BLOB,'independent_implementation':True}
    r.pop('receipt_sha256',None); r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest(); Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':'PASS','receipt_sha256':r['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
