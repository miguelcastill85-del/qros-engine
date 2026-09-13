"""Deterministic control-flow model; not PowerShell or MT5 execution."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'sources/001978_QUALIFY_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v1.ps1'
EXPECTED = '85ea6cd4da259cee65a2aec7aa3e0a497db260b4462bb144e072265b0527a0ca'


def legacy(snapshots, wanted):
    for snapshot in snapshots:
        if snapshot is not None:
            return next((r for r in snapshot if r['test_id'] == wanted), None)
    return None


def corrected(snapshots, wanted, expected=None):
    for snapshot in snapshots:
        if snapshot is None:
            continue
        rows = [r for r in snapshot if r.get('test_id') == wanted]
        if len(rows) > 1:
            return 'DUPLICATE'
        if rows:
            row = rows[0]
            if any(row.get(k) != v for k, v in (expected or {}).items()):
                return 'BINDING'
            if row.get('status') not in ('PASS', 'FAIL'):
                return 'STATUS'
            return row['status']
    return 'TIMEOUT'


def main():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise RuntimeError('SOURCE_IDENTITY')
    source = raw.decode('utf-8-sig')
    if 'foreach($r in @(Read-Rows $f $ms))' not in source:
        raise RuntimeError('LEGACY_CONTROL_FLOW_CHANGED')
    probe = [{'test_id': 'R2T_FENCE_PROBE', 'status': 'PASS'}]
    wanted = 'R2T_FENCE_REACQUIRE'
    fresh = [{'test_id': wanted, 'status': 'PASS'}]
    fail = [{'test_id': wanted, 'status': 'FAIL'}]
    cases = [
        ('stale_probe_then_reacquire', [probe, fresh], None, 'PASS'),
        ('missing_then_reacquire', [None, fresh], None, 'PASS'),
        ('empty_closed_then_reacquire', [[], fresh], None, 'PASS'),
        ('stale_probe_forever', [probe, probe], None, 'TIMEOUT'),
        ('genuine_failure_not_rescued', [fail, fresh], None, 'FAIL'),
        ('duplicate_stage', [fresh + fresh], None, 'DUPLICATE'),
        ('wrong_run_id', [fresh], {'run_id': 'new'}, 'BINDING'),
        ('bound_run_id', [[dict(fresh[0], run_id='new')]], {'run_id': 'new'}, 'PASS'),
        ('invalid_status', [[{'test_id': wanted, 'status': 'OK'}]], None, 'STATUS'),
        ('wrong_role_filename_effect', [probe], None, 'TIMEOUT'),
        ('wrong_pid', [[dict(fresh[0], pid='21')]], {'pid': '22'}, 'BINDING'),
        ('stale_same_stage_token', [[dict(fresh[0], token='old')]], {'token': 'new'}, 'BINDING'),
    ]
    results = []
    for name, snapshots, expected, target in cases:
        actual = corrected(snapshots, wanted, expected)
        results.append({'test': name, 'expected': target, 'actual': actual, 'pass': actual == target})
    reproduced = legacy([probe, fresh], wanted) is None
    report = {'scope': 'Python control-flow model, not PowerShell/native execution',
              'source_sha256': EXPECTED, 'legacy_false_negative_reproduced': reproduced,
              'regressions_pass': sum(r['pass'] for r in results), 'regressions_total': len(results),
              'tests': results, 'powershell_executed': False, 'r2_native_qualified': False}
    (ROOT / 'REGRESSION_REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'tests'}, indent=2))
    if not reproduced or not all(r['pass'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
