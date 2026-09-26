"""G7 mandatory source-delta and exact immutable G6 identity gate.

Cannot mark engineering PASS alone. CI tests and exact APK attestation are separate
required steps. An unchanged or report-only delivery is rejected by diff policy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
G6='cf3eb9f095bd82ecab58b2b2684da5e25827c8f1'
G6_PRODUCT_BLOB='37349209f57a51f4760c831868e89ea10497e854'
G6_VERIFIED_BLOB='cefbe41887d4ff686557ac11036267ef2bbef0e3'
REQUIRED={
    '.github/workflows/qros-mobile-g7-security-gate.yml',
    'product/mobile/g7/G7_PROGRESS_HEAD.json',
    'product/mobile/g7/G7_SECURITY_AND_DEVICE_RUNBOOK.md',
    'product/mobile/g7/G7_SOURCE_MANIFEST.json',
    'product/mobile/g7/G7_SOURCE_MANIFEST_V2.json',
    'product/mobile/g7/G7_SOURCE_MANIFEST_V3.json',
    'product/mobile/g7/G7_CI_INCIDENT_DEBUG_SIGNER_CLASSIFIER_20260925.json',
    'product/mobile/g7/G7_CI_INCIDENT_APKSIGNER_CERT_20260925.json',
    'product/mobile/g7/android_device_gate.py',
    'product/mobile/g7/oidc_canary.py',
    'product/mobile/g7/progress_gate.py',
    'product/mobile/g7/release_gate.py',
    'product/mobile/g7/witness_custody.py',
    'product/mobile/g7/tests/test_security.py',
    'product/mobile/g7/tests/test_device_release.py',
    'product/mobile/g7/tests/test_gate.py'
}

class GateDeny(ValueError): pass

def deny(msg: str): raise GateDeny('QROS_G7_PROGRESS_DENY:'+msg)

def git(*args: str)->str:
    try:return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.PIPE,text=True).strip()
    except (OSError,subprocess.CalledProcessError):deny('GIT_AUTHORITY_UNAVAILABLE')

def check(*,remote_git: bool=False)->dict:
    try:
        mf=json.loads((HERE/'G7_SOURCE_MANIFEST_V3.json').read_text())
        state=json.loads((HERE/'G7_PROGRESS_HEAD.json').read_text())
    except (OSError,ValueError):deny('MISSING_MANIFEST_OR_CHECKPOINT')
    if mf.get('schema')!='QROS_MOBILE_G7_SOURCE_MANIFEST_V3' or mf.get('g6_verified_parent_commit')!=G6:
        deny('PARENT_MANIFEST_MISMATCH')
    if state.get('schema')!='QROS_MOBILE_G7_PROGRESS_HEAD_V1' or state.get('parent_verified_commit')!=G6 or state.get('status')!='DEVELOPMENT_RUNNING':
        deny('STATE_OR_PARENT_MISMATCH')
    if state.get('economic_backtests')!=0 or state.get('holdout_open') is not False or state.get('ga2_open') is not False or state.get('release_signed') is not False:
        deny('FAKED_SCIENTIFIC_OR_RELEASE_SUCCESS')
    sha=mf.get('source_sha256')
    if type(sha) is not dict or set(sha)!=(REQUIRED-{'product/mobile/g7/G7_PROGRESS_HEAD.json','product/mobile/g7/G7_SOURCE_MANIFEST.json','product/mobile/g7/G7_SOURCE_MANIFEST_V2.json','product/mobile/g7/G7_SOURCE_MANIFEST_V3.json'}):
        deny('EXACT_SOURCE_LIST_REQUIRED')
    for name,want in sha.items():
        p=ROOT/name
        if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:
            deny('SOURCE_CHANGED_OR_MISSING:'+name)
    if remote_git:
        if git('hash-object','product/mobile/MOBILE_PRODUCT_HEAD.json')!=G6_PRODUCT_BLOB or \
           git('hash-object','product/mobile/g6_verified/G6_CURRENT_HEAD.json')!=G6_VERIFIED_BLOB:
            deny('VERIFIED_G6_BLOB_MUTATED')
        changed=set(filter(None,git('diff','--name-only',G6+'..HEAD').splitlines()))
        if changed!=REQUIRED:
            deny('NOOP_OR_UNAUTHORIZED_DELTA:missing='+','.join(sorted(REQUIRED-changed))+';extra='+','.join(sorted(changed-REQUIRED)))
    return {'status':'PASS_G7_SOURCE_INTEGRITY_TEST_ONLY',
            'exact_new_paths':len(REQUIRED),'sha256_pinned_source_files':len(sha),
            'remote_git':remote_git,'scientific_authority':False,
            'physical_android_install':'NOT_RUN','external_witness':'NOT_DEPLOYED',
            'next_automatic_action':state['next_automatic_action']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true');a=p.parse_args()
    try:print(json.dumps(check(remote_git=a.remote_git),sort_keys=True,indent=2))
    except GateDeny as exc:raise SystemExit(str(exc))
if __name__=='__main__':main()
