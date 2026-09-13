#!/usr/bin/env python3
"""Offline R2 transcript consistency only. NEVER issues native qualification.

An independent native collector and raw trace verification remain mandatory.
Even a fully fabricated but consistent transcript cannot get an R2 PASS here.
Only Python standard library; no process launch, network, MT5 or trading access.
"""
import argparse
import hashlib
import json
import ntpath
from pathlib import Path

RUNNER_SHA = '17be652ebb5c3745590ceae798a02d136285a2c8dc1c3645f2be578dfa8d8375'


class Rejected(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Rejected(code)


def winpath(value):
    require(isinstance(value, str) and bool(value), 'PATH_SCHEMA')
    require(ntpath.isabs(value) and '..' not in value.replace('/', '\\').split('\\'), 'PATH_SCHEMA')
    # Text normalization is NOT file identity; volume/file ID required separately.
    return ntpath.normcase(ntpath.normpath(value))


def number(value):
    return type(value) is int and value >= 0


def consistent(plan, packet):
    require(plan['schema'] == packet['schema'] == 'R2_TRANSCRIPT_CONTRACT_DRAFT_1', 'SCHEMA')
    require(packet['run_id'] == plan['run_id'], 'RUN_ID')
    require(packet['runner_sha256'] == plan['runner_sha256'] == RUNNER_SHA, 'RUNNER_BINDING')
    require(packet['candidate_executed'] is False and packet['cert'] == 0
            and type(packet['cert']) is int and packet['orders'] == 0
            and type(packet['orders']) is int, 'SAFETY')
    require(packet['host_boot_id'] == plan['host_boot_id'], 'HOST_BOOT')
    start, end = plan['start_ms'], plan['end_ms']
    require(number(start) and number(end) and start < end, 'CLOCK_SCHEMA')
    require(number(plan['max_observation_lag_ms']), 'CLOCK_SCHEMA')
    require(set(packet['roles']) == {'holder', 'probe', 'reacquire'}, 'ROLES')
    expected = plan['roles']
    require(expected['holder']['process_identity'] != expected['probe']['process_identity'], 'TWO_PROCESSES')
    require(expected['holder']['terminal_pid'] != expected['probe']['terminal_pid'], 'TWO_TERMINALS')
    expected_path = winpath(plan['lock_path'])
    for name, role in packet['roles'].items():
        require(role['run_id'] == plan['run_id'], 'RUN_ID')
        require(role['host_boot_id'] == plan['host_boot_id'], 'HOST_BOOT')
        require(role['logical_lock'] == plan['logical_lock'], 'LOCK_FILENAME')
        require(winpath(role['common_path']) == winpath(plan['common_path']), 'COMMON_PATH')
        require(winpath(role['data_path']) == winpath(expected[name]['data_path']), 'DATA_PATH')
        require(winpath(role['terminal_path']) == winpath(expected[name]['terminal_path']), 'TERMINAL_PATH')
        require(winpath(role['program_path']) == winpath(expected[name]['program_path']), 'PROGRAM_PATH')
        require(type(role['mql_tester']) is int and role['mql_tester'] == expected[name]['mql_tester'], 'RUNTIME_MODE')
        require(role['process_identity'] == expected[name]['process_identity']
                and type(role['terminal_pid']) is int
                and role['terminal_pid'] == expected[name]['terminal_pid'], 'PROCESS_IDENTITY')
        require(role['owner_token'] == expected[name]['owner_token'], 'OWNER_TOKEN')
        require(type(role['epoch']) is int and role['epoch'] == expected[name]['epoch'], 'EPOCH')
        require(winpath(role['lock_path']) == expected_path, 'PHYSICAL_NAMESPACE')
        require(role['file_identity'] == plan['file_identity'], 'PHYSICAL_IDENTITY')
        require(number(role['tick_ms']) and start <= role['tick_ms'] <= end, 'FRESHNESS')
        require(number(role['observed_ms']) and role['tick_ms'] <= role['observed_ms'] <= end
                and role['observed_ms']-role['tick_ms'] <= plan['max_observation_lag_ms'], 'TIMESTAMP')
        x = packet['external'][name]
        require(x['process_identity'] == role['process_identity'] and x['process_alive'] is True,
                'EXTERNAL_PROCESS')
        require(winpath(x['lock_path']) == expected_path and x['file_identity'] == role['file_identity'],
                'EXTERNAL_PHYSICAL_IDENTITY')
        require(x['desired_access'] == 'READ_WRITE' and x['share_mode'] == 'NONE', 'OPEN_SEMANTICS')
        require(x['result'] == role['result'], 'CROSS_RESULT')
        require(number(x['observed_ms']) and role['tick_ms'] <= x['observed_ms'] <= role['observed_ms'],
                'EXTERNAL_TIME')
    h, p, r = (packet['roles'][n] for n in ('holder', 'probe', 'reacquire'))
    require(h['result'] == 'ACQUIRED' and p['result'] == 'DENIED_SHARING'
            and r['result'] == 'ACQUIRED', 'FENCE_OUTCOMES')
    require(packet['external']['probe']['win32_error'] == 32, 'DENIAL_REASON')
    release = packet['release']
    require(release['owner_token'] == h['owner_token'] and type(release['epoch']) is int and release['epoch'] == h['epoch']
            and release['process_identity'] == h['process_identity'], 'RELEASE_OWNERSHIP')
    require(release['run_id'] == plan['run_id'], 'RUN_ID')
    require(number(release['tick_ms']) and start <= release['tick_ms'] <= end, 'RELEASE_TIME')
    require(h['tick_ms'] < p['tick_ms'] <= p['observed_ms'] < release['tick_ms'], 'HOLDER_OVERLAP')
    require(release['tick_ms'] < r['tick_ms'], 'REACQUIRE_ORDER')
    require(release['external_close_ms'] == release['tick_ms'], 'RELEASE_CROSS_CHECK')
    require(r['epoch'] > h['epoch'] and r['owner_token'] != h['owner_token'], 'ABA')
    witness = packet['external']['holder_interval']
    require(witness['process_identity'] == h['process_identity']
            and witness['file_identity'] == plan['file_identity'], 'HANDLE_WITNESS')
    require(witness['open_ms'] == h['tick_ms'] and witness['close_ms'] == release['tick_ms']
            and witness['uninterrupted'] is True, 'HANDLE_CONTINUITY')
    # A raw trace hash is a content binding, NOT authentication of its producer.
    require(isinstance(packet['raw_trace_sha256'], str) and len(packet['raw_trace_sha256']) == 64
            and all(c in '0123456789abcdef' for c in packet['raw_trace_sha256']), 'RAW_TRACE_BINDING')


def validate(plan, packet):
    try:
        consistent(plan, packet)
    except Rejected as exc:
        reason = str(exc)
    except (KeyError, TypeError, ValueError, AttributeError):
        reason = 'MALFORMED_OR_MISSING_EVIDENCE'
    else:
        reason = None
    return {'contract_consistent': reason is None, 'reason': reason,
            'decision': 'TRANSCRIPT_CONSISTENT_NATIVE_UNVERIFIED' if reason is None else 'REJECTED',
            'r2_native_qualified': False, 'candidate_execution_allowed': False,
            'certificate_issued': False,
            'scope': 'offline structural consistency; not raw trace or native collector attestation'}


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('DUPLICATE_JSON_KEY')
        out[key] = value
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--packet', required=True)
    args = parser.parse_args()
    try:
        a, b = Path(args.plan).read_bytes(), Path(args.packet).read_bytes()
        result = validate(json.loads(a, object_pairs_hook=no_duplicates),
                          json.loads(b, object_pairs_hook=no_duplicates))
        result['input_sha256'] = [hashlib.sha256(v).hexdigest() for v in (a, b)]
    except (OSError, ValueError) as exc:
        result = {'decision': 'REJECTED', 'reason': type(exc).__name__,
                  'r2_native_qualified': False, 'candidate_execution_allowed': False}
    print(json.dumps(result, indent=2))
    # Deliberately never return qualification success. 3 = coherent but unqualified.
    return 3 if result.get('contract_consistent') else 2


if __name__ == '__main__':
    raise SystemExit(main())
