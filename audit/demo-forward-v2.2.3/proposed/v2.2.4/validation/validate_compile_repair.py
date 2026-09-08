#!/usr/bin/env python3
"""Offline source/evidence regression for the two-declaration C3 compile repair.

This does not replace the missing original Candidate 3 offline/model harnesses,
execute MQL/EX5, simulate a broker, or close any native safety/parity gate.
Run from any directory. --out must name a new directory.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
FINAL = BASE.parent / 'final'
AUTHORITY = BASE / 'authority'
EXEC = 'MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5'
BUS = 'MQL5/Include/QROS_DEMO_BUS_v2_2_4.mqh'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def functions(text):
    # Preserve offsets while masking braces in comments/string literals.
    masked = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                    lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)
    result = {}
    pattern = r'^\w+\s+(\w+)\([^;{}]*\)\s*\{'
    for m in re.finditer(pattern, masked, re.M):
        depth, i = 1, m.end()
        while depth and i < len(masked):
            depth += (masked[i] == '{') - (masked[i] == '}')
            i += 1
        if depth or m[1] in result:
            raise ValueError('Ambiguous/unbalanced function: ' + m[1])
        result[m[1]] = dict(line=text.count('\n', 0, m.start()) + 1,
                            sha256=sha(text[m.start():i].encode()), text=text[m.start():i])
    return result


def normalize_emitter(text, module):
    # Exact reviewed infrastructure additions from the frozen v223 -> C3 diff.
    # No generic removal of statements, alpha functions or input parameters.
    text = re.sub(r'^#property version[^\n]*\n', '', text, flags=re.M)
    text = text.replace('#include <QROS_DEMO_BUS_v2_2_4.mqh>', '#include <QROS_DEMO_BUS_v2.mqh>')
    token = {'XAU': '224101', 'NQX': '224102', 'DIV3': '224103'}[module]
    text = text.replace(f'const long QROS_V224_EMITTER_SOURCE_TOKEN={token};\n', '')
    label = {'XAU': 'QROS XAU', 'NQX': 'QROS NQX', 'DIV3': '[DIV3]'}[module]
    additions = [
        f'      if(!QrosBusProducerInit(QROS_MOD_{module})){{Print("{label} producer fencing failed");return INIT_FAILED;}}\n',
        f'      if(!QrosGvSetChecked(QrosBusKey(QROS_MOD_{module},"SOURCE_TOKEN"),(double)QROS_V224_EMITTER_SOURCE_TOKEN)){{QrosBusProducerRelease();return INIT_FAILED;}}\n',
        '      QrosBusProducerRelease();\n',
    ]
    tick = 't' if module == 'XAU' else 'tick'
    watermark = f'if(!MQLInfoInteger(MQL_TESTER)) QrosBusWatermark(QROS_MOD_{module},{tick}.time_msc);'
    if module == 'NQX':
        text = text.replace(watermark, '')
    else:
        additions.append('   ' + watermark + '\n')
    for addition in additions:
        text = text.replace(addition, '')
    if module == 'DIV3':
        text = text.replace('"Q24.3.INIT_TOTAL"', '"QDB1.3.INIT_TOTAL"')
        text = text.replace('"Q24.3.INIT_DONE"', '"QDB1.3.INIT_DONE"')
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(name, passed, detail=None):
        checks.append(dict(id=name, status='PASS' if passed else 'FAIL', detail=detail))

    frozen = read_json(BASE.parents[2] / 'FROZEN_SOURCE_RECEIPT.json')
    for row in frozen['files']:
        data = (AUTHORITY / 'v223' / row['path']).read_bytes()
        check('frozen_v223_authority::' + row['path'],
              sha(data) == row['sha256'] and len(data) == row['bytes'])

    original_manifest = read_json(AUTHORITY / 'candidate3/PACKAGE_MANIFEST.json')
    final_manifest = read_json(FINAL / 'PACKAGE_MANIFEST.json')
    check('eight_source_inventory', set(final_manifest['expected_sources']) == set(original_manifest['expected_sources'])
          and len(final_manifest['expected_sources']) == 8)
    for rel, expected in original_manifest['expected_sources'].items():
        original = (AUTHORITY / 'candidate3' / rel).read_bytes()
        current = (FINAL / rel).read_bytes()
        check('original_authority::' + rel, sha(original) == expected)
        check('final_manifest::' + rel, sha(current) == final_manifest['expected_sources'][rel])
        if rel != EXEC:
            check('unchanged_component::' + rel, original == current)

    before = (AUTHORITY / 'candidate3' / EXEC).read_bytes()
    after = (FINAL / EXEC).read_bytes()
    expected_after = before
    for name in (b'QROS_INTENT_SLOTS', b'QROS_MGMT_SLOTS'):
        old = b'const int ' + name + b'=32;'
        new = b'#define ' + name + b' 32'
        check('fixed_capacity_32::' + name.decode(), before.count(old) == 1 and after.count(new) == 1)
        expected_after = expected_after.replace(old, new)
    check('only_two_declarations_changed', after == expected_after)
    e_before, e_after = functions(before.decode()), functions(after.decode())
    check('all_executor_functions_preserved', e_before == e_after, {'functions': len(e_after)})
    (args.out / 'EXECUTOR_REPAIR.diff').write_text(''.join(difflib.unified_diff(
        before.decode().splitlines(True), after.decode().splitlines(True),
        fromfile='Candidate3_original_executor', tofile='Candidate3_corrected_executor')), encoding='utf-8')

    b_before = functions((AUTHORITY / 'candidate3' / BUS).read_text())
    b_after = functions((FINAL / BUS).read_text())
    f_map = {
        'F01': ['ReserveIntent', 'ReconcileIntent', 'ReservedRiskUsd', 'ActiveIntentOnAsset', 'ReservedEntrySlotsToday'],
        'F02': ['TryMgmtIntent', 'SaveMgmt', 'CancelWorkingOrder'],
        'F03': ['OnTimer', 'OnTick', 'SetEntryFault', 'SetMgmtFault'],
        'F04': ['LoadPersistentState', 'RecoverUnknownBrokerInventory', 'UpdateRecoveryLock'],
        'F05': ['RebuildDailyCount', 'CountedOrderContains'],
        'F06': ['FinalTradeSessionEndSec', 'SessionEntrySafe', 'EnsureNoOvernightIntents'],
        'F07': ['bus:QrosBusPublish', 'bus:QrosBusRead'],
        'F08': ['AcquireInstanceFence', 'bus:QrosBusProducerInit', 'bus:QrosBusAcquirePublishLock'],
        'F09': ['GvSet', 'PollBus', 'bus:QrosGvSetChecked'],
        'F10': ['CohortReady', 'SortPending', 'CancelPendingEntriesForModule'],
        'F11': ['EventAgeSafe', 'IntentId', 'FindIntentById'],
        'F12': ['ReservedRiskUsd', 'IntentResidualRiskUsd', 'CheckPostFillRisk'],
        'F13': ['FreshExecutableTick', 'ContinuousSafetyGate', 'EntryTradeGate'],
        'F14': ['RuntimeCertified', 'ProducersHealthyAndBound', 'InvalidateCert'],
        'F15': ['CurrentOffsetSec', 'ContinuousSafetyGate', 'RequireRecert'],
        'F16': ['OpenAppendLedger', 'LogRow', 'OnInit'],
        'F17': ['ExactLongForDouble', 'GvGetExactLong', 'bus:QrosBusExactInteger'],
        'F18': ['BarriersTradableBuy', 'ProtectionAtLeastRequestedBuy', 'SendEntry'],
    }
    findings = []
    for fid, names in f_map.items():
        rows = []
        for name in names:
            is_bus = name.startswith('bus:')
            key = name.removeprefix('bus:')
            old, new = (b_before, b_after) if is_bus else (e_before, e_after)
            entry = new.get(key, {})
            rows.append(dict(function=key, file=BUS if is_bus else EXEC,
                             line=entry.get('line'), sha256=entry.get('sha256'),
                             identical_to_original_candidate3=key in old and old[key] == entry))
        passed = all(r['identical_to_original_candidate3'] for r in rows)
        check(fid + '_source_corrections_preserved', passed)
        findings.append(dict(id=fid, status='PRESERVED_SOURCE_ONLY' if passed else 'FAIL', functions=rows,
                             native_adversarial_validation='PENDING'))
    (args.out / 'F01_F18_PRESERVATION.json').write_text(json.dumps(findings, indent=2) + '\n')

    pairs = [
        ('XAU', 'QROS_XAU_M1_DEMO_EMITTER_v2.mq5', 'QROS_XAU_M1_DEMO_EMITTER_v2_2_4.mq5'),
        ('NQX', 'QROS_NQX_17_31_DEMO_EMITTER_v2.mq5', 'QROS_NQX_17_31_DEMO_EMITTER_v2_2_4.mq5'),
        ('DIV3', 'QROS_DIV3_R3_DEMO_EMITTER_v2_1.mq5', 'QROS_DIV3_R3_DEMO_EMITTER_v2_2_4.mq5'),
    ]
    for module, old_name, new_name in pairs:
        old = (AUTHORITY / 'v223/MQL5/Experts' / old_name).read_text()
        new = (FINAL / 'MQL5/Experts' / new_name).read_text()
        check('frozen_emitter_alpha_preserved::' + module,
              normalize_emitter(old, module) == normalize_emitter(new, module),
              {'method': 'Full source equality after only the explicitly reviewed infrastructure changes.',
               'native_trade_parity': 'PENDING'})
        (args.out / (module + '_V223_TO_C3.diff')).write_text(''.join(difflib.unified_diff(
            old.splitlines(True), new.splitlines(True), fromfile=old_name, tofile=new_name)), encoding='utf-8')

    text = after.decode()
    all_mql = '\n'.join(p.read_text() for p in (FINAL / 'MQL5').rglob('*') if p.suffix in ('.mq5', '.mqh'))
    check('Q24_isolation', 'QDB1.EXEC.' not in all_mql and 'QDB1.3.INIT_' not in all_mql and '"Q24.EXEC.CERT"' in text)
    check('arm_token_preserved', 'QROS_DEMO_ARM_v224_8af000_2d6ebd' in text)
    check('risk_limits_preserved', all(x in text for x in [
        'InpRiskPctBalance=0.50;', 'InpMaxReservedRiskPct=1.00;', 'InpMaxNewEntriesPerServerDay=3;']))
    check('session_gate_still_fail_closed', 'InpSessionCloseLeadSec=0;' in text)
    log_root = BASE / 'evidence'
    for phase in ('original_failure', 'reproduced_failure'):
        log = (log_root / phase / 'COMPILE_LOGS' / (Path(EXEC).name + '.log')).read_text(encoding='utf-16')
        errors = re.findall(r'\((\d+),(\d+)\) : error (\d+): ([^\r\n]+)', log)
        check('exact_native_failure::' + phase, errors == [
            ('145', '21', '203', 'invalid index value'), ('146', '22', '203', 'invalid index value')])
    compile_rows = read_json(log_root / 'corrected_compile/COMPILE_RESULTS.json')
    targets = {Path(p).name for p in final_manifest['expected_sources'] if p.endswith('.mq5')}
    check('six_native_targets', {r['name'] for r in compile_rows} == targets and len(compile_rows) == 6)
    for row in compile_rows:
        raw = (log_root / 'corrected_compile/COMPILE_LOGS' / (row['name'] + '.log')).read_bytes()
        log = raw.decode('utf-16')
        check('native_0_0::' + row['name'], sha(raw) == row['log_sha256'] and
              bool(re.search(r'Result:\s*0 errors,\s*0 warnings', log)) and not re.search(r': error \d+:', log))
    ex5_rows = read_json(log_root / 'corrected_compile/EX5_HASHES.json')
    check('six_ex5_inventory', {r['name'] for r in ex5_rows} == {p.replace('.mq5', '.ex5') for p in targets})
    for row in ex5_rows:
        matches = list((FINAL / 'MQL5').rglob(row['name']))
        check('compiled_ex5::' + row['name'], len(matches) == 1 and sha(matches[0].read_bytes()) == row['sha256']
              and matches[0].stat().st_size == row['bytes'])

    # Deliberately report missing historical harnesses as BLOCKED, never replay their PASS receipts.
    historical = read_json(AUTHORITY / 'candidate3_historical_tests/QROS_V224_CANDIDATE3_STATIC_AUDIT.json')
    required = ['run_v224_candidate3_offline.py', 'run_v224_candidate3_static_audit.py', 'run_v224_safety_model.py']
    missing = []
    for name in required:
        expected = historical['files']['AUTHORITY/' + name]['sha256']
        matches = list(AUTHORITY.rglob(name))
        exact = any(sha(p.read_bytes()) == expected for p in matches)
        missing.append(dict(name=name, expected_sha256=expected,
                            status='AVAILABLE_NOT_RERUN' if exact else 'BLOCKED_MISSING_EXACT_HARNESS'))
    summary = dict(PASS=sum(r['status'] == 'PASS' for r in checks), FAIL=sum(r['status'] == 'FAIL' for r in checks), TOTAL=len(checks))
    result = dict(schema='QROS_V224_C3_COMPILE_REPAIR_OFFLINE_REGRESSION_1.0',
                  classification='SOURCE_AND_NATIVE_COMPILE_EVIDENCE_REGRESSION_NOT_NATIVE_RUNTIME',
                  summary=summary, checks=checks, original_candidate3_suite_rerun=missing,
                  historical_receipts_reused_as_current_pass=False)
    (args.out / 'REPAIR_REGRESSION_RESULTS.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(summary))
    print('Original Candidate 3 offline/static/model reruns: BLOCKED_MISSING_EXACT_HARNESS')
    return 1 if summary['FAIL'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
