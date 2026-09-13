#!/usr/bin/env python3
"""All generated events are TEST_ONLY, never native evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from evidence_contract import RUNNER_SHA, validate, no_duplicates


def fixture():
    plan = {'schema': 'R2_TRANSCRIPT_CONTRACT_DRAFT_1', 'run_id': 'SYNTHETIC_ONLY',
            'runner_sha256': RUNNER_SHA, 'host_boot_id': 'SYNTHETIC_BOOT',
            'start_ms': 100, 'end_ms': 900, 'max_observation_lag_ms': 10,
            'logical_lock': 'r2-test.lock', 'common_path': 'C:\\TEST_ONLY\\Common',
            'lock_path': 'C:\\TEST_ONLY\\Common\\Files\\r2-test.lock',
            'file_identity': {'volume': 'SYNTHETIC_VOLUME', 'file_id': 'SYNTHETIC_FILE'},
            'roles': {}}
    packet = {k: copy.deepcopy(plan[k]) for k in ('schema', 'run_id', 'runner_sha256', 'host_boot_id')}
    packet.update(candidate_executed=False, cert=0, orders=0, roles={}, external={}, raw_trace_sha256='0'*64)
    for name, pid, tick, epoch, result in [('holder', 11, 200, 1, 'ACQUIRED'),
            ('probe', 22, 300, 1, 'DENIED_SHARING'), ('reacquire', 33, 600, 2, 'ACQUIRED')]:
        base = {'terminal_pid': pid, 'process_identity': f'TEST_PID_{pid}:CREATION_100',
                'data_path': f'C:\\TEST_ONLY\\{name}\\Data',
                'terminal_path': f'C:\\TEST_ONLY\\{name}',
                'program_path': f'C:\\TEST_ONLY\\{name}\\Experts\\Probe.ex5',
                'owner_token': f'SYNTHETIC_{name}', 'epoch': epoch, 'mql_tester': 0}
        plan['roles'][name] = copy.deepcopy(base)
        role = dict(base, run_id=plan['run_id'], host_boot_id=plan['host_boot_id'],
                    tick_ms=tick, observed_ms=tick+2, result=result)
        role.update({k: copy.deepcopy(plan[k]) for k in ('logical_lock', 'common_path', 'lock_path', 'file_identity')})
        packet['roles'][name] = role
        packet['external'][name] = dict(process_identity=base['process_identity'], process_alive=True,
            lock_path=plan['lock_path'], file_identity=copy.deepcopy(plan['file_identity']),
            desired_access='READ_WRITE', share_mode='NONE', result=result,
            observed_ms=tick+1, win32_error=32 if name=='probe' else 0)
    h = packet['roles']['holder']
    packet['release'] = {'owner_token': h['owner_token'], 'epoch': 1, 'process_identity': h['process_identity'],
                         'run_id': plan['run_id'], 'tick_ms': 500, 'external_close_ms': 500}
    packet['external']['holder_interval'] = dict(process_identity=h['process_identity'],
            file_identity=copy.deepcopy(plan['file_identity']), open_ms=200, close_ms=500, uninterrupted=True)
    return plan, packet


def set_at(packet, path, value):
    for key in path[:-1]:
        packet = packet[key]
    packet[path[-1]] = value


def main():
    plan, packet = fixture()
    good = validate(plan, packet)
    if not good['contract_consistent'] or good['r2_native_qualified']:
        raise RuntimeError('positive control must be structurally consistent and NOT certified')
    cases = [
        ('physical_namespace_distinct', ['roles','probe','lock_path'], 'D:\\TEST_ONLY\\r2-test.lock', 'PHYSICAL_NAMESPACE'),
        ('holder_early_release', ['release','tick_ms'], 250, 'HOLDER_OVERLAP'),
        ('probe_other_filename', ['roles','probe','logical_lock'], 'other.lock', 'LOCK_FILENAME'),
        ('incorrect_runid', ['roles','probe','run_id'], 'OTHER', 'RUN_ID'),
        ('stale_evidence', ['roles','probe','tick_ms'], 99, 'FRESHNESS'),
        ('impossible_timestamp', ['roles','probe','observed_ms'], 299, 'TIMESTAMP'),
        ('incorrect_pid', ['roles','probe','terminal_pid'], 999, 'PROCESS_IDENTITY'),
        ('incorrect_data_path', ['roles','probe','data_path'], 'D:\\OTHER', 'DATA_PATH'),
        ('incorrect_common_path', ['roles','probe','common_path'], 'D:\\OTHER', 'COMMON_PATH'),
        ('fake_pass_without_lock', ['roles','holder','result'], 'PASS', 'CROSS_RESULT'),
        ('release_without_ownership', ['release','owner_token'], 'INTRUDER', 'RELEASE_OWNERSHIP'),
        ('reacquire_before_release', ['roles','reacquire','tick_ms'], 400, 'TIMESTAMP'),
        ('file_id_distinct', ['roles','probe','file_identity'], {'volume':'OTHER','file_id':'OTHER'}, 'PHYSICAL_IDENTITY'),
        ('external_other_file', ['external','probe','lock_path'], 'D:\\OTHER', 'EXTERNAL_PHYSICAL_IDENTITY'),
        ('interrupted_handle', ['external','holder_interval','uninterrupted'], False, 'HANDLE_CONTINUITY'),
        ('pid_reused', ['external','probe','process_identity'], 'TEST_PID_22:CREATION_999', 'EXTERNAL_PROCESS'),
        ('access_denied_not_sharing', ['external','probe','win32_error'], 5, 'DENIAL_REASON'),
        ('runner_byte_change', ['runner_sha256'], 'f'*64, 'RUNNER_BINDING'),
        ('cert_enabled', ['cert'], 1, 'SAFETY'),
        ('candidate_executed', ['candidate_executed'], True, 'SAFETY'),
        ('boolean_release_epoch', ['release','epoch'], True, 'RELEASE_OWNERSHIP'),
        ('array_trace_hash', ['raw_trace_sha256'], ['0']*64, 'RAW_TRACE_BINDING'),
    ]
    rows=[]
    for name, path, value, reason in cases:
        mutant=copy.deepcopy(packet);set_at(mutant,path,value)
        result=validate(plan,mutant)
        if result['contract_consistent'] or result['reason'] != reason:
            raise RuntimeError((name,result,reason))
        rows.append({'mutation':name,'expected_rule':reason,'caught':True})
    # Coherent timeline mutant: no accidental timestamp rejection can mask ordering.
    mutant=copy.deepcopy(packet)
    mutant['roles']['reacquire'].update(tick_ms=400,observed_ms=402)
    mutant['external']['reacquire']['observed_ms']=401
    result=validate(plan,mutant)
    if result['reason']!='REACQUIRE_ORDER': raise RuntimeError(result)
    rows.append({'mutation':'coherent_reacquire_before_release','expected_rule':'REACQUIRE_ORDER','caught':True})
    stale_plan=copy.deepcopy(plan);mutant=copy.deepcopy(packet)
    stale_plan['roles']['reacquire']['epoch']=1
    mutant['roles']['reacquire']['epoch']=1
    result=validate(stale_plan,mutant)
    if result['reason']!='ABA':raise RuntimeError(result)
    rows.append({'mutation':'repeated_generation_in_plan_and_evidence','expected_rule':'ABA','caught':True})
    for name, mutant in [('missing_evidence',{}), ('wrong_schema_type',None)]:
        result=validate(plan,mutant)
        if result['contract_consistent']:raise RuntimeError(name)
        rows.append({'mutation':name,'expected_rule':'MALFORMED_OR_MISSING_EVIDENCE','caught':True})
    try: json.loads('{"a":1,"a":2}', object_pairs_hook=no_duplicates)
    except ValueError: rows.append({'mutation':'duplicate_json_keys','expected_rule':'DUPLICATE_JSON_KEY','caught':True})
    else: raise RuntimeError('duplicate keys accepted')
    report={'scope':'TEST_ONLY offline contract, not original R1/R2 mutation score',
            'positive_control':'coherent fabricated transcript remains NATIVE_UNVERIFIED',
            'mutations':rows,'caught':len(rows),'total':len(rows),'score':1.0,
            'native_tests_run':False,'r2_native_qualified':False,
            'validator_sha256':hashlib.sha256(Path(__file__).with_name('evidence_contract.py').read_bytes()).hexdigest()}
    Path(__file__).with_name('MUTATION_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='mutations'},indent=2))


if __name__=='__main__': main()
