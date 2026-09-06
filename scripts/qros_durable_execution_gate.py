#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, py_compile, tempfile
from pathlib import Path
from typing import Any

SHA256_LEN=64

def load(p: Path)->dict[str,Any]:
    x=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(x,dict): raise ValueError('manifest root must be object')
    return x

def sha256(p: Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def req_sha(v:str,name:str):
    if not isinstance(v,str) or len(v)!=SHA256_LEN or any(c not in '0123456789abcdef' for c in v):
        raise ValueError(f'{name} must be lowercase SHA-256')

def verify_component(root:Path,c:dict[str,Any])->dict[str,Any]:
    for k in ('role','path','sha256','required'):
        if k not in c: raise ValueError(f'component missing {k}')
    req_sha(c['sha256'],f"component {c['path']} sha256")
    p=(root/c['path']).resolve()
    if not str(p).startswith(str(root.resolve())): raise ValueError('unsafe component path')
    if not p.exists():
        if c['required']: raise ValueError(f'missing required component {c["path"]}')
        return {'path':c['path'],'status':'OPTIONAL_MISSING'}
    if not p.is_file(): raise ValueError(f'component is not file {c["path"]}')
    got=sha256(p)
    if got!=c['sha256']: raise ValueError(f'hash mismatch {c["path"]}: {got}')
    if 'size' in c and int(c['size'])!=p.stat().st_size: raise ValueError(f'size mismatch {c["path"]}')
    if c.get('python_compile'):
        with tempfile.TemporaryDirectory() as td:
            py_compile.compile(str(p),cfile=str(Path(td)/'x.pyc'),doraise=True)
    return {'path':c['path'],'status':'PASS','sha256':got,'size':p.stat().st_size}

def verify_manifest(m:dict[str,Any],root:Path)->dict[str,Any]:
    if m.get('schema')!='QROS_DURABLE_EXECUTION_MANIFEST_V1': raise ValueError('unexpected manifest schema')
    if m.get('status') not in {'CANDIDATE','FROZEN','ACTIVE'}: raise ValueError('invalid manifest status')
    if m.get('production_use') is not True: raise ValueError('production_use must be true')
    if m.get('holdout_opened') is not False: raise ValueError('holdout must remain closed')
    comps=m.get('components')
    if not isinstance(comps,list) or not comps: raise ValueError('components must be non-empty list')
    paths=[c.get('path') for c in comps]
    if len(paths)!=len(set(paths)): raise ValueError('duplicate component path')
    results=[verify_component(root,c) for c in comps]
    derived=m.get('derived_execution',{})
    if derived.get('is_accelerator'):
        eq=derived.get('equivalence')
        if not isinstance(eq,dict) or eq.get('status')!='PASS_EXACT': raise ValueError('accelerator requires PASS_EXACT equivalence')
        req_sha(eq.get('reference_runner_sha256',''),'reference_runner_sha256')
        if int(eq.get('comparisons',0))<1: raise ValueError('accelerator equivalence comparisons missing')
        if int(eq.get('mismatches',-1))!=0: raise ValueError('accelerator equivalence mismatch')
        if not eq.get('receipt_ref'): raise ValueError('accelerator equivalence receipt_ref required')
    remat=m.get('rematerialization')
    if remat:
        if remat.get('deterministic') is not True: raise ValueError('rematerialization must be deterministic')
        if not remat.get('expected_outputs'): raise ValueError('rematerialization expected_outputs required')
        for out in remat['expected_outputs']:
            req_sha(out['sha256'],f"expected output {out.get('name','?')}")
            if int(out.get('count',1))<1: raise ValueError('expected output count invalid')
    cp=m.get('checkpoint_contract',{})
    if cp:
        required={'receipt_required','partial_without_receipt','range_semantics','tail_policy','uid_policy'}
        if required-set(cp): raise ValueError('checkpoint_contract incomplete')
        if cp['receipt_required'] is not True: raise ValueError('checkpoint receipt must be required')
        if cp['partial_without_receipt']!='QUARANTINE': raise ValueError('partial without receipt must quarantine')
        if cp['tail_policy']!='TRUNCATE_TO_LAST_COMMITTED_RANGE_THEN_VALIDATE': raise ValueError('unsafe tail policy')
        if cp['uid_policy']!='DETERMINISTIC_FIRST_OCCURRENCE_CONTIGUOUS_NO_AUTOINCREMENT': raise ValueError('unsafe uid policy')
    return {'schema':'QROS_DURABLE_EXECUTION_GATE_RESULT_V1','status':'PASS','artifact_id':m.get('artifact_id'),'component_count':len(results),'components':results,'holdout_opened':False}

def selftest()->dict[str,Any]:
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); (r/'runner.py').write_text('x=1\n',encoding='utf-8'); (r/'cache.bin').write_bytes(b'abc')
        base={'schema':'QROS_DURABLE_EXECUTION_MANIFEST_V1','status':'FROZEN','artifact_id':'SELFTEST','production_use':True,'holdout_opened':False,'components':[{'role':'RUNNER','path':'runner.py','sha256':sha256(r/'runner.py'),'size':4,'required':True,'python_compile':True},{'role':'CACHE','path':'cache.bin','sha256':sha256(r/'cache.bin'),'size':3,'required':True}],'derived_execution':{'is_accelerator':True,'equivalence':{'status':'PASS_EXACT','reference_runner_sha256':'0'*64,'comparisons':100,'mismatches':0,'receipt_ref':'selftest'}},'checkpoint_contract':{'receipt_required':True,'partial_without_receipt':'QUARANTINE','range_semantics':'HALF_OPEN_CONTIGUOUS_NO_OVERLAP','tail_policy':'TRUNCATE_TO_LAST_COMMITTED_RANGE_THEN_VALIDATE','uid_policy':'DETERMINISTIC_FIRST_OCCURRENCE_CONTIGUOUS_NO_AUTOINCREMENT'}}
        tests=[]
        verify_manifest(base,r); tests.append(('PASS_VALID_MANIFEST',True))
        bad=json.loads(json.dumps(base));bad['components'][1]['sha256']='1'*64
        try:verify_manifest(bad,r);tests.append(('REJECT_HASH_MISMATCH',False))
        except ValueError:tests.append(('REJECT_HASH_MISMATCH',True))
        bad=json.loads(json.dumps(base));bad['derived_execution']['equivalence']['status']='UNPROVEN'
        try:verify_manifest(bad,r);tests.append(('REJECT_UNPROVEN_ACCELERATOR',False))
        except ValueError:tests.append(('REJECT_UNPROVEN_ACCELERATOR',True))
        bad=json.loads(json.dumps(base));bad['checkpoint_contract']['partial_without_receipt']='ACCEPT'
        try:verify_manifest(bad,r);tests.append(('REJECT_UNRECEIPTED_PARTIAL',False))
        except ValueError:tests.append(('REJECT_UNRECEIPTED_PARTIAL',True))
        bad=json.loads(json.dumps(base));bad['components'][0]['path']='missing.py'
        try:verify_manifest(bad,r);tests.append(('REJECT_MISSING_REQUIRED',False))
        except ValueError:tests.append(('REJECT_MISSING_REQUIRED',True))
        return {'schema':'QROS_DURABLE_EXECUTION_GATE_SELFTEST_V1','status':'PASS' if all(x[1] for x in tests) else 'FAIL','tests':[{'name':a,'pass':b} for a,b in tests]}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['verify','selftest']);ap.add_argument('--manifest',type=Path);ap.add_argument('--root',type=Path,default=Path('.'));a=ap.parse_args()
    res=selftest() if a.command=='selftest' else verify_manifest(load(a.manifest),a.root)
    print(json.dumps(res,sort_keys=True,separators=(',',':')));return 0 if res.get('status')=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
