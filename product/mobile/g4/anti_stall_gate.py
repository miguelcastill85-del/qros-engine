"""G4 mechanically rejects narrative-only delivery, missing code or evidence drift.
This is a CI-gated contract, NOT proof of GitHub branch-protection or a production witness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PARENT = '0b529a2624fd43794cbe2185702f2bac7d3b209e'
MOBILE_V6_BLOB = '619565d1668243d3cc289c730a61340105c9417f'
G3_VERIFIED_BLOB = '55eac915ee9026ee5e84dfebbd51e9daa8dae86b'
SCIENCE_MAIN_BLOB = '5a88937d571e4bcc938c9ce71570092e0abfae6d'
REQUIRED = {
  'product/mobile/g4/data_audit.py',
  'product/mobile/g4/witness.py',
  'product/mobile/g4/integration.py',
  'product/mobile/g4/tests/test_g4.py',
  'product/mobile/g4/tests/test_gate.py',
  'product/mobile/g4/anti_stall_gate.py',
  'product/mobile/g4/G4_SECURITY_CONTRACT.md',
  '.github/workflows/qros-mobile-g4-trust-gate.yml',
  'product/mobile/g4/G4_SOURCE_MANIFEST.json',
  'product/mobile/g4/G4_PROGRESS_HEAD.json',
}

class GateReject(RuntimeError):
    pass

def fail(name: str) -> None:
    raise GateReject('QROS_G4_ANTI_STALL_FAIL_CLOSED:'+name)

def git(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(['git',*args],text=True,cwd=repo,stderr=subprocess.PIPE).strip()
    except (OSError,subprocess.CalledProcessError):
        fail('GIT_AUTHORITY_UNAVAILABLE')

def verify(*, repo: Path = ROOT, remote: bool = False) -> dict[str, Any]:
    try:
        h=json.loads((repo/'product/mobile/g4/G4_PROGRESS_HEAD.json').read_text())
        m=json.loads((repo/'product/mobile/g4/G4_SOURCE_MANIFEST.json').read_text())
    except (OSError,ValueError):
        fail('MISSING_OR_INVALID_HEAD_MANIFEST')
    if h.get('schema')!='QROS_MOBILE_G4_PROGRESS_HEAD_V1' or h.get('source_parent_exact')!=PARENT:
        fail('AUTHORITY_HEAD_DRIFT')
    if h.get('phase')!='G4_LICENSED_AUDIT_LOCAL_WITNESS_CI_PENDING' or not h.get('next_automatic_action'):
        fail('FAKE_PASS_OR_NO_NEXT_ACTION')
    if h.get('economic_backtests')!=0 or h.get('holdout_open') is not False or h.get('ga2_open') is not False or h.get('scientific_authority') is not False:
        fail('SCIENTIFIC_FIREWALL_CHANGED')
    if h.get('mobile_product_head_blob')!=MOBILE_V6_BLOB or h.get('g3_verified_head_blob')!=G3_VERIFIED_BLOB or h.get('science_main_pointer_blob')!=SCIENCE_MAIN_BLOB:
        fail('PINNED_SOURCE_AUTHORITY_CHANGED')
    hashed=REQUIRED-{'product/mobile/g4/G4_PROGRESS_HEAD.json','product/mobile/g4/G4_SOURCE_MANIFEST.json'}
    if m.get('schema')!='QROS_MOBILE_G4_SOURCE_MANIFEST_V1' or m.get('exact_parent_commit')!=PARENT or set(m.get('source_sha256',{}))!=hashed:
        fail('INCOMPLETE_CODE_TEST_AND_WORKFLOW_CENSUS')
    if m.get('economic_backtests')!=0 or m.get('raw_broker_data') is not False:
        fail('UNAUTHORIZED_SOURCE_CLASS')
    for name,expected in m['source_sha256'].items():
        path=repo/name
        if not path.is_file() or path.is_symlink():
            fail('MISSING_OR_LINKED_SOURCE:'+name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            fail('SOURCE_SHA256_DRIFT:'+name)
    if remote:
        if git(repo, 'rev-parse',PARENT)!=PARENT:
            fail('PARENT_GIT_OBJECT_MISSING')
        if git(repo,'hash-object','product/mobile/MOBILE_PRODUCT_HEAD.json')!=MOBILE_V6_BLOB:
            fail('G3_PRODUCT_HEAD_MUTATED')
        if git(repo,'hash-object','product/mobile/g3_verified/G3_CURRENT_HEAD.json')!=G3_VERIFIED_BLOB:
            fail('G3_VERIFIED_HEAD_MUTATED')
        if git(repo,'hash-object','control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json')!=SCIENCE_MAIN_BLOB:
            fail('SCIENTIFIC_MAIN_POINTER_MUTATED')
        delta=set(filter(None,git(repo,'diff','--name-only',PARENT+'...HEAD').splitlines()))
        if delta!=REQUIRED:
            fail('NO_OP_OR_UNEXPECTED_DELTA:missing='+','.join(sorted(REQUIRED-delta))+';extra='+','.join(sorted(delta-REQUIRED)))
    return {'status':'PASS_G4_MECHANICAL_SOURCE_AND_DELTA_GATE_ONLY',
            'required_new_files':len(REQUIRED),'hashed_source_files':len(hashed),
            'base_exact_commit':PARENT,'remote_git_exact':remote,
            'scientific_gate_pass':False, 'next_action':h['next_automatic_action']}

if __name__=='__main__':
    args=argparse.ArgumentParser()
    args.add_argument('--remote-git',action='store_true')
    v=args.parse_args()
    try:
        print(json.dumps(verify(remote=v.remote_git),indent=2,sort_keys=True))
    except GateReject as e:
        raise SystemExit(str(e))
