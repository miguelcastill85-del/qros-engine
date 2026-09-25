"""Executable fail-closed G3 source and delivery gate.

GitHub Actions verifies the same exact git commit as native/Python tests;
this gate alone does not grant branch protection or scientific authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

G3=Path(__file__).resolve().parent
REPO=G3.parents[2]
G2_PARENT='ac5bc7536ae4a977c71f443a39882efebcfd4604'
G2_MOBILE_HEAD_BLOB='dff6b0bb07b64fc8b528b0a4540dc601b8b984b3'
G2_VERIFIED_HEAD_BLOB='1e2c9c96709cd58fa4813839e9dc1e5c01654b67'
REQUIRED={
  'product/mobile/g3/oracle.py',
  'product/mobile/g3/native/executor.cpp',
  'product/mobile/g3/tests/test_execution.py',
  'product/mobile/g3/tests/fixtures/g3_synthetic_golden.txt',
  'product/mobile/g3/tests/fixtures/g3_expected_trades.txt',
  'product/mobile/g3/anti_stall_gate.py',
  'product/mobile/g3/tests/test_gate.py',
  'product/mobile/g3/G3_EXECUTION_CONTRACT.md',
  'product/mobile/governance/QROS_MOBILE_DELIVERY_ANTI_STALL_POLICY_v1.md',
  '.github/workflows/qros-mobile-g3-evidence-gate.yml',
  'product/mobile/g3/G3_SOURCE_MANIFEST.json',
  'product/mobile/g3/G3_PROGRESS_HEAD.json',
}

class GateReject(RuntimeError):pass

def deny(why:str)->None:raise GateReject('QROS_G3_GATE_FAIL_CLOSED:'+why)

def git(*args:str)->str:
  return subprocess.check_output(['git',*args],text=True,cwd=REPO,stderr=subprocess.PIPE).strip()

def verify(remote:bool=False)->dict:
  try:
    head=json.loads((G3/'G3_PROGRESS_HEAD.json').read_text())
    mf=json.loads((G3/'G3_SOURCE_MANIFEST.json').read_text())
  except (OSError,ValueError) as e:deny('MISSING_OR_CORRUPT_HEAD_OR_MANIFEST:'+str(e))
  if head.get('schema')!='QROS_MOBILE_G3_PROGRESS_HEAD_V1' or head.get('parent_exact')!=G2_PARENT:deny('BASE_HEAD_MISMATCH')
  if head.get('phase')!='G3_SYNTHETIC_PARITY_TEST_PENDING' or not head.get('next_automatic_action'):deny('FAKE_SUCCESS_OR_NO_NEXT_ACTION')
  if head.get('economic_tests')!=0 or head.get('holdout_open') is not False or head.get('ga2_open') is not False or head.get('scientific_authority') is not False:deny('SCIENCE_FIREWALL_DRIFT')
  if head.get('mobile_product_head_blob')!=G2_MOBILE_HEAD_BLOB or head.get('g2_verified_head_blob')!=G2_VERIFIED_HEAD_BLOB:deny('G2_HEAD_MISMATCH')
  expected=REQUIRED-{'product/mobile/g3/G3_PROGRESS_HEAD.json','product/mobile/g3/G3_SOURCE_MANIFEST.json'}
  if mf.get('schema')!='QROS_MOBILE_G3_SOURCE_MANIFEST_V1' or mf.get('parent_exact')!=G2_PARENT or set(mf.get('source_sha256',{}))!=expected:deny('MISSING_CODE_TEST_GATE_OR_UNEXPECTED_FILES')
  for name,sha in mf['source_sha256'].items():
    path=REPO/name
    if not path.is_file() or path.is_symlink():deny('SOURCE_MISSING_OR_SYMLINK:'+name)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:deny('SOURCE_HASH_DRIFT:'+name)
  try:
    product_hash=git('hash-object','product/mobile/MOBILE_PRODUCT_HEAD.json')
    prior_hash=git('hash-object','product/mobile/g2_verified/G2_CURRENT_HEAD.json')
  except (OSError,subprocess.CalledProcessError):
    if remote:deny('G2_BASELINE_HASH_UNAVAILABLE')
    product_hash=G2_MOBILE_HEAD_BLOB;prior_hash=G2_VERIFIED_HEAD_BLOB
  if product_hash!=G2_MOBILE_HEAD_BLOB or prior_hash!=G2_VERIFIED_HEAD_BLOB:deny('G2_BASELINE_MUTATED')
  if remote:
    try:
      changed=set(filter(None,git('diff','--name-only',G2_PARENT+'...HEAD').splitlines()))
    except subprocess.CalledProcessError:deny('DELTA_UNAVAILABLE')
    if changed!=REQUIRED:
      deny('NO_OP_OR_UNEXPECTED_DELTA:missing='+','.join(sorted(REQUIRED-changed))+';extra='+','.join(sorted(changed-REQUIRED)))
  gold=REPO/'product/mobile/g3/tests/fixtures/g3_expected_trades.txt'
  if hashlib.sha256(gold.read_bytes()).hexdigest()!='d8ce45cfa9ab8b928b714c7f7fbe7b68030372b95c2d19591f9fbfa87c369253':deny('GOLDEN_ORACLE_DRIFT')
  return {'status':'PASS_G3_SOURCE_DELTA_GATE_ONLY','mandatory_paths':len(REQUIRED),'hashed_source_files':len(expected),'remote_git_validation':remote,'next_action':head['next_automatic_action'],'scientific_gate_pass':False}

if __name__=='__main__':
  p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true');args=p.parse_args()
  try: print(json.dumps(verify(args.remote_git),indent=2,sort_keys=True))
  except GateReject as exc:raise SystemExit(str(exc))
