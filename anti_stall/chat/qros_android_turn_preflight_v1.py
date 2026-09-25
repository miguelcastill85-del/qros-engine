#!/usr/bin/env python3
"""QROS Android chat turn: verify externally retrieved live Git blob bytes.

This is an in-chat preflight, not a background daemon, scheduler or broker adapter.
The calling chat MUST independently fetch current blobs from GitHub; local files
alone can never prove a branch tip is current. No economic data is read here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

H40 = re.compile(r"[0-9a-f]{40}\Z")
SAFE = re.compile(r"[A-Za-z0-9_./-]+\Z")

class FailClosed(Exception):
    pass

def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode('ascii') + b"\x00" + raw).hexdigest()

def exact(path: str, expected: str, description: str) -> dict:
    if not H40.fullmatch(expected):
        raise FailClosed("INVALID_EXTERNAL_GIT_BLOB_PIN:" + description)
    raw = pathlib.Path(path).read_bytes()
    actual = git_blob(raw)
    if actual != expected:
        raise FailClosed("LIVE_GIT_BLOB_MISMATCH:" + description)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError,UnicodeDecodeError) as exc:
        raise FailClosed("BAD_JSON:" + description) from exc

def git_path(value: str) -> str:
    if not isinstance(value, str) or not SAFE.fullmatch(value) or value.startswith('/') or any(s in ('', '.', '..') for s in value.split('/')):
        raise FailClosed('UNSAFE_REPOSITORY_PATH')
    return value

def preflight(governance_file: str, governance_sha: str, policy_file: str,
              pointer_file: str, pointer_sha: str, target_file: str,
              anchor_file: str, expected_branch: str) -> dict:
    gov=exact(governance_file,governance_sha,'MAIN_GOVERNANCE')
    if gov.get('version') != '2.4':
        raise FailClosed('UNEXPECTED_GOVERNANCE_VERSION')
    cfg=gov.get('chat_turn_protocol')
    if not isinstance(cfg,dict) or cfg.get('mode')!='CHAT_TURN_ONLY':
        raise FailClosed('CHAT_PROTOCOL_NOT_ACTIVE_ON_MAIN')
    policy_sha=cfg.get('git_blob_sha1','')
    policy=exact(policy_file,policy_sha,'CHAT_POLICY')
    if policy.get('schema')!='QROS_ANDROID_CHAT_TURN_ANTISTALL_V1' or policy.get('mode')!='CHAT_TURN_ONLY':
        raise FailClosed('CHAT_POLICY_SCHEMA_INVALID')
    p=exact(pointer_file,pointer_sha,'LIVE_SCIENTIFIC_POINTER')
    if p.get('branch')!=expected_branch or expected_branch!=policy['scientific_branch']:
        raise FailClosed('SCIENTIFIC_BRANCH_MISMATCH')
    if p.get('schema')!='QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF_POINTER_V1':
        raise FailClosed('UNKNOWN_SCIENTIFIC_POINTER_SCHEMA')
    target=git_path(p.get('target'))
    anchor=git_path(p.get('last_closed_remote_anchor_path'))
    # Require caller-supplied absolute source identities to match the actual live
    # pointer paths, rather than searching for a similarly named file.
    if pathlib.Path(target_file).name!=pathlib.PurePosixPath(target).name or pathlib.Path(anchor_file).name!=pathlib.PurePosixPath(anchor).name:
        raise FailClosed('EXACT_TARGET_OR_ANCHOR_PATH_MISMATCH')
    exact(target_file,p.get('target_git_blob_sha1',''),'SCIENTIFIC_HANDOFF')
    exact(anchor_file,p.get('last_closed_remote_anchor_blob_sha1',''),'SCIENTIFIC_ANCHOR')
    for flag in ('holdout_open','ga2_open','Gate_A_approved'):
        if p.get(flag) is not False:
            raise FailClosed('SCIENTIFIC_FIREWALL_NOT_FROZEN:'+flag)
    if p.get('pending_configurations_preregistered_not_executed') is None:
        raise FailClosed('MISSING_EXECUTION_CURSOR')
    if p.get('pending_configurations_preregistered_not_executed') != 0:
        raise FailClosed('UNRECONCILED_ECONOMIC_SCOPE')
    if not p.get('last_closed') or not p.get('next_action'):
        raise FailClosed('MISSING_CHECKPOINT_OR_NEXT_ACTION')
    return {
        'schema':'QROS_CHAT_TURN_PREFLIGHT_RESULT_V1',
        'status':'VERIFIED_NEXT_TURN_ACTION_READY',
        'execution_mode':'SYNCHRONOUS_IN_THIS_CHAT_ONLY',
        'authority':{'main_governance_blob':governance_sha,
                     'chat_policy_blob':policy_sha,
                     'scientific_pointer_blob':pointer_sha,
                     'scientific_target_blob':p['target_git_blob_sha1'],
                     'scientific_anchor_blob':p['last_closed_remote_anchor_blob_sha1'],
                     'branch':expected_branch},
        'last_closed':p['last_closed'],
        'next_action':p['next_action'],
        'pending':p.get('pending'),
        'scientific_firewalls':{'holdout_open':False,'ga2_open':False,'Gate_A_approved':False},
        'unattended_execution':'NOT_SUPPORTED_IN_CHAT',
        'post_action':'Re-fetch live Git pointer, validate delta, persist immutable proof plus CAS handoff/pointer before claiming stage PASS; stop on drift.'
    }

def main():
    ap=argparse.ArgumentParser()
    for name in ('governance-file','governance-sha','policy-file','pointer-file','pointer-sha','target-file','anchor-file','expected-branch'):
        ap.add_argument('--'+name,required=True)
    ap.add_argument('--receipt-file')
    a=ap.parse_args()
    try:
        out=preflight(a.governance_file,a.governance_sha,a.policy_file,a.pointer_file,a.pointer_sha,a.target_file,a.anchor_file,a.expected_branch)
        if a.receipt_file:
            dest=pathlib.Path(a.receipt_file)
            dest.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=dest.parent,prefix=dest.name+'.',delete=False) as f:
                tmp=f.name
                json.dump(out,f,sort_keys=True,indent=2,ensure_ascii=False)
                f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
        print(json.dumps(out,sort_keys=True,ensure_ascii=False))
    except (FailClosed, OSError, TypeError, KeyError, ValueError) as exc:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(exc)},sort_keys=True),file=sys.stderr)
        return 3
    return 0
if __name__=='__main__':raise SystemExit(main())
