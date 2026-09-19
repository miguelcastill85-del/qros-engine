#!/usr/bin/env python3
"""Opt-in bounded control adapter. A timeout is UNKNOWN, never worker death."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile

import qros_fenced_heavy_job_supervisor_v1 as binding
import qros_heavy_job_supervisor_v3 as supervisor

SCHEMA = 'QROS_FENCED_HEAVY_JOB_SUPERVISOR_2.0_ENGINEERING_CANDIDATE'


def delegate_once(command: list[str], control_dir: Path, timeout: float = 3) -> dict:
    if not 0 < timeout <= 3:
        raise ValueError('CONTROL_TIMEOUT_MUST_BE_POSITIVE_AND_AT_MOST_3S')
    control_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='control_', dir=control_dir) as tmp:
        path = Path(tmp)
        rc, reason = supervisor.run_bounded_worker(command, path,
            {'max_runtime_seconds': timeout, 'max_log_bytes': 8192})
        if reason != 'WORKER_EXIT':
            return {'state': 'FAIL', 'action': 'CONTROL_OUTCOME_UNKNOWN_NO_RELAUNCH',
                    'reason': reason, 'worker_death_proven': False}
        try:
            lines = (path/'worker.stdout.txt').read_text().splitlines()
            result = json.loads(lines[-1])
            if not isinstance(result, dict) or result.get('state') not in {'PASS','RUNNING','BUSY','FAIL'}:
                raise ValueError('INVALID_DELEGATE_STATE')
            if (rc == 0) != (result['state'] in {'PASS','RUNNING','BUSY'}):
                raise ValueError('DELEGATE_EXIT_STATE_MISMATCH')
        except (ValueError, IndexError):
            return {'state': 'FAIL', 'action': 'CONTROL_OUTCOME_UNKNOWN_NO_RELAUNCH',
                    'reason': 'DELEGATE_OUTPUT_INVALID', 'worker_death_proven': False}
        return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--job-spec', type=Path, required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--lease', type=Path, required=True)
    ap.add_argument('--launch-grace-seconds', type=int, default=30)
    a = ap.parse_args()
    try:
        spec = supervisor.load_json(a.job_spec)
        lease = supervisor.load_json(a.lease)
        supervisor.validate_job_spec(spec)
        ok, why = binding.validate_binding(spec, lease)
        if not ok:
            result = {'state':'FAIL','action':'FENCE_BINDING_FAIL_CLOSED','reason':why}
        else:
            result = delegate_once([sys.executable, supervisor.__file__,
                '--job-spec', str(a.job_spec.resolve()), '--work-root', str(a.work_root.resolve()),
                '--launch-grace-seconds', str(a.launch_grace_seconds)],
                a.work_root / '_v3_control')
            # A changed or expired lease cannot support a PASS returned by the
            # delegate. This is local validation, not a distributed atomic CAS.
            current = supervisor.load_json(a.lease)
            valid, reason = binding.validate_binding(spec, current)
            if current != lease or not valid:
                result = {'state':'FAIL','action':'LEASE_CHANGED_OR_EXPIRED_FAIL_CLOSED',
                          'reason': reason, 'worker_death_proven':False}
        print(json.dumps({'schema':SCHEMA, **result}, sort_keys=True))
        return 0 if result['state'] in {'PASS','RUNNING','BUSY'} else 2
    except Exception as exc:
        print(json.dumps({'schema':SCHEMA,'state':'FAIL','action':'FENCED_SUPERVISOR_EXCEPTION',
                          'reason':f'{type(exc).__name__}:{exc}'},sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
