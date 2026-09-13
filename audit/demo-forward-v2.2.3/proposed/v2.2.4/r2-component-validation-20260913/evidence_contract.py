#!/usr/bin/env python3
"""Additional schema/relationship checks; never certifies native R2.

The historical validator is preserved byte-for-byte in legacy_evidence_contract.py.
Input plans are checked too: equality with a malformed plan is not evidence.
This is an offline engineering component, not a qualifier release.
"""
import argparse
import hashlib
import json
import ntpath
from pathlib import Path
import legacy_evidence_contract as legacy

RUNNER_SHA = legacy.RUNNER_SHA
no_duplicates = legacy.no_duplicates


def need(condition, code):
    if not condition:
        raise ValueError(code)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def integer(value, minimum=0):
    return type(value) is int and minimum <= value < 2**63


def localpath(value):
    need(text(value), 'EMPTY_PATH')
    drive, tail = ntpath.splitdrive(value)
    need(len(drive) == 2 and drive[0].isalpha() and drive[1] == ':'
         and tail.startswith('\\') and ':' not in tail and '/' not in value,
         'LOCAL_DRIVE_ABSOLUTE_PATH_REQUIRED')
    parts = tail.split('\\')[1:]
    need(all(x and x not in ('.', '..') and x.rstrip(' .') == x for x in parts),
         'AMBIGUOUS_PATH')
    need(not any(any(c in x for c in '<>"|?*') or
                 any(ord(c) < 32 for c in x) for x in parts), 'AMBIGUOUS_PATH')
    return ntpath.normcase(value)


def identity(value):
    need(type(value) is dict and set(value) == {'volume', 'file_id'}
         and text(value['volume']) and text(value['file_id']), 'FILE_IDENTITY_SCHEMA')


def strict(plan, packet):
    for x in (plan, packet):
        need(text(x['run_id']) and text(x['host_boot_id']), 'RUN_BOOT_SCHEMA')
    need(set(plan['roles']) == {'holder', 'probe', 'reacquire'}, 'PLAN_ROLES_SCHEMA')
    identity(plan['file_identity'])
    need(text(plan['logical_lock']) and ntpath.basename(plan['logical_lock']) == plan['logical_lock']
         and not any(c in plan['logical_lock'] for c in ':/*?'), 'LOGICAL_LOCK_SCHEMA')
    need(localpath(plan['lock_path']) == localpath(ntpath.join(
        plan['common_path'], 'Files', plan['logical_lock'])), 'LOCK_PATH_DERIVATION')
    tokens = []
    processes = []
    for name in ('holder', 'probe', 'reacquire'):
        expected = plan['roles'][name]
        role = packet['roles'][name]
        witness = packet['external'][name]
        for r in (expected, role):
            need(integer(r['terminal_pid'], 1) and r['terminal_pid'] <= 0xffffffff,
                 'PID_SCHEMA')
            need(text(r['process_identity']), 'PROCESS_SCHEMA')
            need(text(r['owner_token']), 'TOKEN_SCHEMA')
            need(integer(r['epoch'], 1), 'EPOCH_SCHEMA')
            need(type(r['mql_tester']) is int and r['mql_tester'] in (0, 1), 'MODE_SCHEMA')
            for key in ('data_path', 'terminal_path', 'program_path'):
                localpath(r[key])
        for key in ('common_path', 'lock_path'):
            localpath(role[key])
        identity(role['file_identity'])
        identity(witness['file_identity'])
        need(type(witness['win32_error']) is int and witness['win32_error'] ==
             (32 if name == 'probe' else 0), 'WIN32_OUTCOME_SCHEMA')
        need(integer(role['tick_ms']) and integer(role['observed_ms']) and
             integer(witness['observed_ms']), 'NATIVE_CLOCK_SCHEMA')
        tokens.append(expected['owner_token'])
        processes.append(expected['process_identity'])
    need(len(set(tokens)) == 3, 'ROLE_TOKEN_REUSE')
    need(len(set(processes)) == 3, 'PROCESS_GENERATION_REUSE')
    need(plan['roles']['holder']['epoch'] == plan['roles']['probe']['epoch'], 'PROBE_EPOCH')
    interval = packet['external']['holder_interval']
    identity(interval['file_identity'])
    need(integer(interval['open_ms']) and integer(interval['close_ms'])
         and integer(packet['release']['external_close_ms']), 'HANDLE_CLOCK_SCHEMA')
    need(packet['external']['holder']['observed_ms'] <
         packet['roles']['probe']['tick_ms'], 'READY_OBSERVED_BEFORE_PROBE')


def validate(plan, packet):
    result = legacy.validate(plan, packet)
    if not result['contract_consistent']:
        return result
    try:
        strict(plan, packet)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result.update(contract_consistent=False, decision='REJECTED',
                      reason=str(exc) if type(exc) is ValueError else 'STRICT_SCHEMA')
    result['scope'] = 'offline schema and consistency; no raw trace attestation or native qualification'
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--packet', required=True)
    args = ap.parse_args()
    try:
        a, b = Path(args.plan).read_bytes(), Path(args.packet).read_bytes()
        result = validate(json.loads(a, object_pairs_hook=no_duplicates),
                          json.loads(b, object_pairs_hook=no_duplicates))
        result['input_sha256'] = [hashlib.sha256(v).hexdigest() for v in (a, b)]
    except (OSError, ValueError) as exc:
        result = {'decision': 'REJECTED', 'reason': type(exc).__name__,
                  'r2_native_qualified': False, 'candidate_execution_allowed': False,
                  'certificate_issued': False}
    print(json.dumps(result, indent=2))
    return 3 if result.get('contract_consistent') else 2


if __name__ == '__main__':
    raise SystemExit(main())
