#!/usr/bin/env python3
"""QROS v2.4: bounded *actual* multi-cycle execution on an authenticated host.

It invokes the existing v2.3 engine; it does not reimplement frozen scientific
work or infer economic approvals. Production requires fresh authenticated git
readback of the current scientific pointer AND its target before/after a cycle.
A test fixture bypass is accepted only for an explicit fixture/* repository.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

from qros_anti_stall_v2_1 import Incident, atomic_json, canonical, digest
from qros_continuation_dispatch_v2_2 import queue_load
from qros_continuation_engine_v2_3 import run as engine_run

SCHEMA = 'QROS_BOUND_AUTHENTICATED_CONTINUATION_SERVICE_V2_4'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
BRANCH = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,200}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def safe_repo_path(name: str) -> str:
    if not isinstance(name, str) or '\\' in name or '\0' in name or not name:
        raise Incident('UNSAFE_REMOTE_POINTER_PATH')
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')):
        raise Incident('UNSAFE_REMOTE_POINTER_PATH')
    if len(name) > 230 or not all(re.fullmatch('[a-zA-Z0-9_.-]+', p) for p in name.split('/')):
        raise Incident('UNSAFE_REMOTE_POINTER_PATH')
    return name


def origin_matches(url: str, expected_repo: str, fixture: bool = False) -> bool:
    if fixture and expected_repo.startswith('fixture/'):
        return bool(url)
    if not REPO.fullmatch(expected_repo):
        return False
    if url.startswith('git@github.com:'):
        path = url[len('git@github.com:'):]
    elif url.startswith('ssh://git@github.com/'):
        path = url[len('ssh://git@github.com/'):]
    else:
        s = urlsplit(url)
        if s.scheme != 'https' or s.hostname != 'github.com' or s.username or s.password or s.port or s.query or s.fragment:
            return False
        path = s.path.lstrip('/')
    return path.removesuffix('.git').rstrip('/') == expected_repo


def cmd_git(repo_dir: Path, *args: str, timeout: int = 25, deadline: float | None = None) -> bytes:
    if deadline is not None:
        timeout=min(timeout,deadline-time.monotonic())
        if timeout < 0.10:raise Incident('REMOTE_AUTHORITY_PROBE_TIME_BUDGET_EXHAUSTED')
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
    try:
        proc = subprocess.run(['git','-C',str(repo_dir),*args],capture_output=True,timeout=timeout,check=False,env=env)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Incident('AUTHORITY_GIT_UNAVAILABLE_OR_TIMEOUT') from exc
    if proc.returncode != 0:
        # Git stderr can include credential-bearing URLs; do not log it.
        raise Incident('AUTHORITY_GIT_COMMAND_FAILED:' + args[0])
    return proc.stdout.strip() if args[0] not in ('show',) else proc.stdout


def verify_live_authority(repo_dir: str, q: dict, expected_pointer_sha: str,
                          pointer_path: str, fixture: bool = False,
                          deadline: float | None = None) -> dict:
    """Fetch live branch; check origin, ancestry, pointer + referenced target Git blobs.

    A queue can execute only while *the exact signed-off pointer* stays current;
    newer remote science requires a new authorized queue, never a silent rebase.
    """
    deadline=min(deadline if deadline is not None else float('inf'),time.monotonic()+70)
    authority = q['authority']
    branch = authority['branch']
    if not BRANCH.fullmatch(branch) or '..' in branch or branch.endswith(('/', '.')) or branch.startswith('-'):
        raise Incident('INVALID_FROZEN_BRANCH')
    if not HEX40.fullmatch(authority['base_commit']) or not HEX40.fullmatch(expected_pointer_sha):
        raise Incident('INVALID_EXTERNAL_AUTHORITY_PIN')
    pp = safe_repo_path(pointer_path)
    repo_path = Path(repo_dir).resolve(strict=True)
    remote = cmd_git(repo_path,'remote','get-url','origin',deadline=deadline).decode('utf8').strip()
    if not origin_matches(remote,authority['repo'],fixture):
        raise Incident('AUTHORITY_ORIGIN_REPOSITORY_MISMATCH')
    cmd_git(repo_path,'fetch','--no-tags','origin','refs/heads/'+branch,timeout=35,deadline=deadline)
    tip = cmd_git(repo_path,'rev-parse','FETCH_HEAD',deadline=deadline).decode('ascii').strip()
    if not HEX40.fullmatch(tip):raise Incident('UNBOUND_REMOTE_TIP')
    cmd_git(repo_path,'merge-base','--is-ancestor',authority['base_commit'],tip,deadline=deadline)
    raw = cmd_git(repo_path,'show','FETCH_HEAD:'+pp,deadline=deadline)
    sha = git_blob(raw)
    if sha != expected_pointer_sha:
        raise Incident('LIVE_SCIENTIFIC_POINTER_ADVANCED_STOP_AND_RECONCILE')
    try: pointer=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as exc:raise Incident('LIVE_SCIENTIFIC_POINTER_MALFORMED') from exc
    if pointer.get('branch') != branch or pointer.get('holdout_open') is not False or pointer.get('ga2_open') is not False:
        raise Incident('LIVE_SCIENTIFIC_FIREWALL_OR_BRANCH_DRIFT')
    if pointer.get('Gate_A_approved') is not False:
        raise Incident('GATE_A_STATUS_CHANGED_REQUIRE_EXPLICIT_QUEUE')
    target = safe_repo_path(pointer.get('target',''))
    target_sha = pointer.get('target_git_blob_sha1')
    if not isinstance(target_sha,str) or not HEX40.fullmatch(target_sha):
        raise Incident('UNPINNED_LIVE_HANDOFF_TARGET')
    target_bytes=cmd_git(repo_path,'show','FETCH_HEAD:'+target,deadline=deadline)
    if git_blob(target_bytes)!=target_sha:
        raise Incident('LIVE_HANDOFF_TARGET_BLOB_MISMATCH')
    try: handoff=json.loads(target_bytes)
    except (ValueError,UnicodeDecodeError) as exc:raise Incident('LIVE_HANDOFF_MALFORMED') from exc
    # A signed pointer can move to a new, unrelated lane; binding both layer
    # names to this queue prevents a seemingly successful but orphaned run.
    if handoff.get('authority',{}).get('branch',branch)!=branch:
        raise Incident('LIVE_HANDOFF_BRANCH_MISMATCH')
    anchor_path = pointer.get('last_closed_remote_anchor_path')
    anchor_sha = pointer.get('last_closed_remote_anchor_blob_sha1')
    if anchor_path or anchor_sha:
        if not isinstance(anchor_sha,str) or not HEX40.fullmatch(anchor_sha):
            raise Incident('UNPINNED_LIVE_ANCHOR')
        actual = git_blob(cmd_git(repo_path,'show','FETCH_HEAD:'+safe_repo_path(anchor_path),deadline=deadline))
        if actual != anchor_sha: raise Incident('LIVE_REMOTE_ANCHOR_BLOB_MISMATCH')
    return {'remote_tip':tip,'pointer_sha1':sha,'handoff_sha1':target_sha,
            'anchor_sha1':anchor_sha,'branch':branch,'repo':authority['repo']}


def validate_fixture(q: dict, fixture: bool) -> None:
    if fixture and (q['authority']['repo']!='fixture/not-a-live-repository' or
                    q['authority']['branch']!='synthetic-only'):
        raise Incident('SYNTHETIC_FIXTURE_MODE_FORBIDDEN_ON_REAL_REPOSITORY')


def run_service(queue: str, queue_sha: str, repo_dir: str|None,
                pointer_path: str|None, pointer_sha: str|None,
                max_cycles: int = 20, wall_seconds: float = 21600,
                cycle_seconds: float = 180, stages_per_cycle: int = 5,
                synthetic_fixture: bool = False, execution: object = engine_run,
                authority_checker: object = verify_live_authority) -> dict:
    if not (1<=max_cycles<=1000 and 10<=wall_seconds<=86400 and
            5<=cycle_seconds<=1800 and 1<=stages_per_cycle<=100):
        raise Incident('UNSAFE_SERVICE_BUDGET')
    q=queue_load(queue,queue_sha);validate_fixture(q,synthetic_fixture)
    if not synthetic_fixture and (not repo_dir or not pointer_path or not pointer_sha):
        raise Incident('AUTHENTICATED_REMOTE_SOURCE_REQUIRED_FOR_REAL_QUEUE')
    start=time.monotonic();deadline=start+wall_seconds;records=[]
    def checked_authority():
        if authority_checker is verify_live_authority:
            return authority_checker(repo_dir,q,pointer_sha,pointer_path,deadline=deadline)
        return authority_checker(repo_dir,q,pointer_sha,pointer_path)
    # v2.3's per-queue mutex protects all local subprocess executions; this
    # service does not hold a second lock across network calls or sleeps.
    for cycle in range(max_cycles):
        remaining=deadline-time.monotonic()
        if remaining < 5: status='SERVICE_BUDGET_CHECKPOINTED';break
        pre=None
        if not synthetic_fixture:
            pre=checked_authority()
            remaining=deadline-time.monotonic()
            if remaining<5:status='SERVICE_BUDGET_CHECKPOINTED';break
        budget=min(cycle_seconds,remaining)
        result=execution(queue,queue_sha,max(5,budget),stages_per_cycle)
        if not synthetic_fixture:
            post=checked_authority()
            if post!=pre:
                raise Incident('REMOTE_AUTHORITY_CHANGED_DURING_EXECUTION_FREEZE_OUTPUTS')
        executed=result['actually_executed_jobs']
        records.append({'cycle':cycle+1,'executed':executed,'status':result['status'],
                        'checkpoint_sha256':result['durable_checkpoint_sha256'],
                        'verified_completed':result['completed_jobs'],
                        'verified_pending':result['pending_jobs'],
                        'remote_authority':pre})
        if result['status']=='ALL_JOBS_VERIFIED_PASS':status='ALL_VERIFIED_EXECUTION_COMPLETE';break
        if result['status']=='SAFE_DEFER_NO_ELIGIBLE_STAGE':
            status='SCIENTIFIC_OR_INFRASTRUCTURE_DEPENDENCY_SAFE_DEFER';break
        if not executed:status='NO_VERIFIED_PROGRESS_SAFE_EXIT';break
        # Successful cycles do not need a human to invoke the next one.
    else:status='MAX_VERIFIED_CYCLES_CHECKPOINTED'
    return {'schema':SCHEMA,'status':status,'queue_sha256':queue_sha,
            'cycles':len(records),'actually_executed_jobs':[j for r in records for j in r['executed']],
            'last_cycle':records[-1] if records else None,
            'execution_log':records,'elapsed_seconds':round(time.monotonic()-start,3),
            'scientific_firewalls':{'holdout_open':False,'ga2_open':False,
                                    'economic_approval_inferred':False}}


def main() -> int:
    p=argparse.ArgumentParser(description='QROS v2.4: executable resumable bounded control plane, NEVER a scientific gate')
    p.add_argument('--queue',required=True);p.add_argument('--expected-queue-sha256',required=True)
    p.add_argument('--git-dir');p.add_argument('--pointer-path');p.add_argument('--expected-live-pointer-sha1')
    p.add_argument('--max-cycles',type=int,default=20);p.add_argument('--wall-seconds',type=float,default=21600)
    p.add_argument('--cycle-seconds',type=float,default=180);p.add_argument('--stages-per-cycle',type=int,default=5)
    p.add_argument('--synthetic-fixture',action='store_true')
    a=p.parse_args()
    try:
        r=run_service(a.queue,a.expected_queue_sha256,a.git_dir,a.pointer_path,a.expected_live_pointer_sha1,
                      a.max_cycles,a.wall_seconds,a.cycle_seconds,a.stages_per_cycle,a.synthetic_fixture)
        print(json.dumps(r,sort_keys=True,ensure_ascii=False),flush=True)
        return 0 if r['status']=='ALL_VERIFIED_EXECUTION_COMPLETE' else 20
    except (Incident,OSError,ValueError,KeyError) as ex:
        print(json.dumps({'schema':SCHEMA,'status':'FAIL_CLOSED','reason':str(ex)}),file=sys.stderr,flush=True)
        return 3
if __name__=='__main__':raise SystemExit(main())
