"""Executable anti-stall delivery gate for QROS Mobile G2 source and PR CI.

This gate CANNOT force an assistant to keep running after a turn ends. It CAN
fail any G2 PR/engineering promotion lacking exact code, tests, receipts and
an identified next action, independently of the assistant's self-report.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

G2 = pathlib.Path(__file__).resolve().parent
REPO=G2.parents[2]
FROZEN_G1_PARENT='6a878ed10e26c616d6f326563ff3fa24bfdc7f3b'
FROZEN_G1_PRODUCT_HEAD_BLOB='1a684a92fe65d1d53aeaabe5ddaf803c6710beef'
FROZEN_G1_FIXTURE_SHA256='97c59cef0c5cce67332a312bd0f5aad5eb7f7509e9b62a90f334165b34a32c6b'
REQUIRED={
 'product/mobile/g2/native/enumerator.cpp',
 'product/mobile/g2/shard_engine.py',
 'product/mobile/g2/tests/test_g2.py',
 'product/mobile/g2/benchmark_structural.py',
 'product/mobile/g2/anti_stall_gate.py',
 'product/mobile/g2/run_once.py',
 'product/mobile/g2/tests/test_gate.py',
 'product/mobile/g2/G2_ANTI_STALL_CONTROL.md',
 '.github/workflows/qros-mobile-g2-progress-gate.yml',
 'product/mobile/g2/G2_PROGRESS_HEAD.json',
 'product/mobile/g2/G2_SOURCE_MANIFEST.json',
}


def fail(msg: str) -> None:
    raise SystemExit('QROS_ANTI_STALL_GATE_FAIL_CLOSED:'+msg)


def git(*cmd: str) -> str:
    return subprocess.check_output(['git',*cmd],cwd=REPO,text=True,stderr=subprocess.PIPE).strip()


def gate(remote: bool) -> dict:
    ptr_path=G2/'G2_PROGRESS_HEAD.json'
    manifest_path=G2/'G2_SOURCE_MANIFEST.json'
    try:
        ptr=json.loads(ptr_path.read_text())
        manifest=json.loads(manifest_path.read_text())
    except (OSError,ValueError) as exc:
        fail('MISSING_OR_CORRUPT_POINTER_OR_MANIFEST:'+str(exc))
    if ptr.get('schema')!='QROS_MOBILE_G2_PROGRESS_HEAD_V1' or ptr.get('source_parent_exact')!=FROZEN_G1_PARENT:
        fail('AUTHORITY_NOT_EXACT')
    if ptr.get('status')!='DEVELOPMENT_RUNNING' or ptr.get('scientific_result_claimed') is not False:
        fail('INVALID_PRE_CI_STATE')
    if not ptr.get('next_automatic_action') or ptr.get('last_completed_gate')!='ANDROID_G1_ENGINEERING_PASS':
        fail('NO_RESUMABLE_DELTA')
    if ptr.get('holdout_open') is not False or ptr.get('ga2_open') is not False or ptr.get('pnl_tests')!=0:
        fail('SCIENCE_FIREWALL_DRIFT')
    if ptr.get('g1_product_head_blob')!=FROZEN_G1_PRODUCT_HEAD_BLOB:
        fail('G1_PRODUCT_POINTER_DRIFT')
    if manifest.get('schema')!='QROS_MOBILE_G2_SOURCE_MANIFEST_V1':
        fail('MANIFEST_SCHEMA')
    if set(manifest.get('source_file_sha256',{})) != (REQUIRED - {'product/mobile/g2/G2_PROGRESS_HEAD.json','product/mobile/g2/G2_SOURCE_MANIFEST.json'}):
        fail('MANDATORY_CODE_TEST_CI_MISSING')
    for name,expected in manifest['source_file_sha256'].items():
        path=REPO/name
        if not path.is_file() or path.is_symlink():fail('SOURCE_MISSING_OR_SYMLINK:'+name)
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected:fail('SOURCE_HASH_DRIFT:'+name)
    fixture=REPO/'product/mobile/flutter_app/test/fixtures/universe_oracle.json'
    if hashlib.sha256(fixture.read_bytes()).hexdigest()!=FROZEN_G1_FIXTURE_SHA256:
        fail('G1_ORACLE_CONTAMINATED')
    try:
        product_head=git('hash-object','product/mobile/MOBILE_PRODUCT_HEAD.json')
    except (OSError,subprocess.CalledProcessError):
        # Locally compare against exact frozen content only when a real git checkout is available.
        if remote:fail('G1_HEAD_READBACK_MISSING')
        product_head=None
    if product_head is not None and product_head!=FROZEN_G1_PRODUCT_HEAD_BLOB:
        fail('G1_HEAD_REWRITTEN')
    if remote:
        try:
            files=git('diff','--name-only',FROZEN_G1_PARENT+'...HEAD').splitlines()
        except subprocess.CalledProcessError:
            fail('REPO_DELTA_UNAVAILABLE')
        changed=set(files)
        if changed != REQUIRED:
            missing = REQUIRED-changed
            unexpected = changed-REQUIRED
            fail('G2_DELTA_EXACT_SET_MISMATCH:missing=' + ','.join(sorted(missing)) +
                 ';unexpected=' + ','.join(sorted(unexpected)))
    return dict(status='PASS_SOURCE_INTEGRITY_AND_DELTA_ONLY',code_sha_count=len(manifest['source_file_sha256']),
                required_new_paths=len(REQUIRED),remote_git_evidence=remote,
                next_action=ptr['next_automatic_action'],scientific_gate_pass=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true')
    args=p.parse_args()
    print(json.dumps(gate(args.remote_git),sort_keys=True,indent=2))
