"""TEST_ONLY: coherent forgeries against the preserved and hardened validators."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import evidence_contract as fixed
import legacy_evidence_contract as old

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('historical_tests', ROOT.parent /
    'r2-autonomous-audit-20260913/test_evidence_contract.py')
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)


def everywhere(p, e, key, value):
    def walk(x):
        if isinstance(x, dict):
            for k in list(x):
                if k == key:
                    x[k] = copy.deepcopy(value)
                else:
                    walk(x[k])
    walk(p)
    walk(e)


def run():
    p, e = historical.fixture()
    assert fixed.validate(p, e)['contract_consistent']
    # Re-run the existing 27 cases against the new entrypoint in a temporary
    # directory so the historical MUTATION_REPORT is never overwritten.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='qros-contract-') as t:
        historical.__file__ = str(Path(t) / 'test_evidence_contract.py')
        (Path(t) / 'evidence_contract.py').write_bytes((ROOT / 'evidence_contract.py').read_bytes())
        historical.validate = fixed.validate
        historical.main()
        inherited = json.loads((Path(t) / 'MUTATION_REPORT.json').read_text())
    cases = [
        ('null_physical_identity', 'file_identity', None),
        ('empty_physical_identity', 'file_identity', {}),
        ('blank_file_id', 'file_identity', {'volume': 'V', 'file_id': ''}),
        ('blank_volume', 'file_identity', {'volume': '', 'file_id': 'F'}),
        ('null_run', 'run_id', None),
        ('blank_boot', 'host_boot_id', ' '),
        ('empty_process_identity', 'process_identity', ''),
        ('invalid_runtime_mode', 'mql_tester', 9),
        ('ambiguous_local_path', 'data_path', 'C:\\TEST_ONLY\\alias.'),
    ]
    rows = []
    for name, key, value in cases:
        p, e = historical.fixture()
        everywhere(p, e, key, value)
        rows.append(check(name, p, e))
    for name, field, val in [('negative_pid', 'terminal_pid', -1),
                             ('zero_pid', 'terminal_pid', 0),
                             ('null_owner_token', 'owner_token', None)]:
        p, e = historical.fixture()
        p['roles']['holder'][field] = e['roles']['holder'][field] = val
        if field == 'owner_token':
            e['release'][field] = val
        rows.append(check(name, p, e))
    p, e = historical.fixture()
    everywhere(p, e, 'lock_path', 'C:\\OTHER\\same.lock')
    rows.append(check('coherent_wrong_lock_derivation', p, e))
    p, e = historical.fixture()
    e['external']['holder']['win32_error'] = 5
    rows.append(check('acquired_with_access_denied_error', p, e))
    p, e = historical.fixture()
    e['external']['probe']['win32_error'] = 32.0
    rows.append(check('float_win32_error', p, e))
    p, e = historical.fixture()
    p['roles']['probe']['epoch'] = e['roles']['probe']['epoch'] = 7
    rows.append(check('probe_wrong_generation', p, e))
    p, e = historical.fixture()
    p['roles']['probe']['owner_token'] = e['roles']['probe']['owner_token'] = e['roles']['holder']['owner_token']
    rows.append(check('probe_reuses_owner_nonce', p, e))
    report = {'scope': 'TEST_ONLY offline validator; not MT5 or PowerShell',
              'inherited_cases_caught': inherited['caught'],
              'inherited_cases_total': inherited['total'],
              'additional_cases': rows, 'additional_caught': len(rows),
              'additional_total': len(rows),
              'legacy_false_acceptances': sum(x['legacy_accepted'] for x in rows),
              'r2_native_qualified': False, 'native_tests_run': False,
              'validator_sha256': hashlib.sha256((ROOT/'evidence_contract.py').read_bytes()).hexdigest()}
    (ROOT / 'MUTATION_REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'additional_cases'}, indent=2))


def check(name, plan, packet):
    before, after = old.validate(plan, packet), fixed.validate(plan, packet)
    assert not after['contract_consistent'], (name, after)
    assert after['r2_native_qualified'] is False
    return {'mutation': name, 'legacy_accepted': before['contract_consistent'],
            'caught': True, 'reason': after['reason']}


if __name__ == '__main__':
    run()
