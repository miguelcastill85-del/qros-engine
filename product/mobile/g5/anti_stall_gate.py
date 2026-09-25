"""Fail-closed G5 signed-demo TLS source/evidence gate. Does not itself enforce branch protection."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

REPO=Path(__file__).resolve().parents[3]
G5=REPO/'product/mobile/g5'
PARENT='58b00efa53ff58b36216764c2c813f4a022a09a4'
G4_PRODUCT_HEAD='bebeca3f38d3116066516609205795eb3ed91c23'
G4_CURRENT_HEAD='bea1c0366bcde2b43f99188f52c2390351f7557d'
G4_VERIFIED_RECEIPT='dae2569d405eefd52fcb6fc941282765add66aa2'
G4_SOURCE_MANIFEST_V2='5e6e2ba5b4a076f8675b8b5917e0eb683451f78e'
G4_DATA_AUDIT='f1f5ae7003d53616c1b2079c24a2e64a1a1b345f'
G4_WITNESS='c153e28e5b3a5104f5d22158f0149995b1f05f38'
REQUIRED={
    'product/mobile/g5/proof_gateway.py',
    'product/mobile/g5/integration.py',
    'product/mobile/g5/tests/test_gateway.py',
    'product/mobile/g5/tests/test_gate.py',
    'product/mobile/g5/anti_stall_gate.py',
    'product/mobile/g5/G5_SECURITY_CONTRACT.md',
    '.github/workflows/qros-mobile-g5-tenant-https-gate.yml',
    'product/mobile/g5/G5_PROGRESS_HEAD.json',
    'product/mobile/g5/G5_SOURCE_MANIFEST.json',
}

class GateReject(RuntimeError):pass

def deny(code:str)->None:raise GateReject('QROS_G5_FAIL_CLOSED:'+code)

def git(root:Path,*args:str)->str:
    try:return subprocess.check_output(['git',*args],text=True,cwd=root,stderr=subprocess.PIPE).strip()
    except (OSError,subprocess.CalledProcessError) as e:deny('GIT_AUTHORITY_UNAVAILABLE:'+':'.join(args)+':'+str(e))

def verify(root:Path=REPO,remote:bool=False)->dict[str,Any]:
    g5=root/'product/mobile/g5'
    try:
        head=json.loads((g5/'G5_PROGRESS_HEAD.json').read_text())
        manifest=json.loads((g5/'G5_SOURCE_MANIFEST.json').read_text())
    except (OSError,ValueError):deny('HEAD_OR_MANIFEST_MISSING')
    if head.get('schema')!='QROS_MOBILE_G5_PROGRESS_HEAD_V1' or head.get('source_parent_exact')!=PARENT or head.get('mobile_g4_head_git_blob_sha1')!=G4_PRODUCT_HEAD:
        deny('PARENT_HEAD_DRIFT')
    if head.get('phase')!='G5_SYNTHETIC_TLS_LOCAL_PAIRING_CI_PENDING' or not head.get('next_automatic_action') or head.get('status')!='DEVELOPMENT_RUNNING':
        deny('FAKE_SUCCESS_OR_MISSING_NEXT_ACTION')
    if head.get('economic_tests')!=0 or head.get('holdout_open') is not False or head.get('ga2_open') is not False or head.get('scientific_authority') is not False:
        deny('SCIENTIFIC_PERMISSION_DRIFT')
    hashed=REQUIRED-{'product/mobile/g5/G5_PROGRESS_HEAD.json','product/mobile/g5/G5_SOURCE_MANIFEST.json'}
    if manifest.get('schema')!='QROS_MOBILE_G5_SOURCE_MANIFEST_V1' or manifest.get('parent_exact')!=PARENT or set(manifest.get('source_sha256',{}))!=hashed:
        deny('SOURCE_TEST_AND_CI_CENSUS_MISMATCH')
    for name,expected in manifest['source_sha256'].items():
        path=root/name
        if not path.is_file() or path.is_symlink():deny('SOURCE_MISSING_OR_LINKED:'+name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:deny('SOURCE_SHA256_DRIFT:'+name)
    if remote:
        targets=[('product/mobile/MOBILE_PRODUCT_HEAD.json',G4_PRODUCT_HEAD),
                 ('product/mobile/g4_verified/G4_CURRENT_HEAD.json',G4_CURRENT_HEAD),
                 ('product/mobile/receipts/QROS_MOBILE_G4_VERIFIED_ENGINEERING_PASS_20260925.json',G4_VERIFIED_RECEIPT),
                 ('product/mobile/g4/G4_SOURCE_MANIFEST_V2.json',G4_SOURCE_MANIFEST_V2),
                 ('product/mobile/g4/data_audit.py',G4_DATA_AUDIT),
                 ('product/mobile/g4/witness.py',G4_WITNESS)]
        for path,pin in targets:
            if git(root,'hash-object',path)!=pin:deny('PRIOR_VERIFIED_BYTES_MUTATED:'+path)
        if git(root,'rev-parse',PARENT)!=PARENT:deny('PARENT_NOT_FOUND')
        delta=set(filter(None,git(root,'diff','--name-only',PARENT+'...HEAD').splitlines()))
        if delta!=REQUIRED:
            deny('NO_OP_OR_UNEXPECTED_DELTA:missing='+','.join(sorted(REQUIRED-delta))+';extra='+','.join(sorted(delta-REQUIRED)))
    return {'status':'PASS_G5_SOURCE_DELTA_TEST_ONLY','source_files_hashed':len(hashed),
            'exact_new_files':len(REQUIRED),'parent':PARENT,'remote_git':remote,
            'scientific_gate_pass':False,'next_automatic_action':head['next_automatic_action']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true')
    x=p.parse_args()
    try:print(json.dumps(verify(remote=x.remote_git),indent=2,sort_keys=True))
    except GateReject as e:raise SystemExit(str(e))
