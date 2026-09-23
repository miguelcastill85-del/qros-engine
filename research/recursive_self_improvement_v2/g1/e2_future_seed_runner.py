#!/usr/bin/env python3
"""RSI-G1 E2: frozen 56-case synthetic structural diagnostic, future NIST pulse only.

Public beacon randomness only seeds TEST FIXTURES: never generate real signing keys.
Results cannot establish an independent custodian, actual provider model identity, or efficacy.
"""
import argparse
import base64
import copy
import datetime as dt
import hashlib
import importlib
import json
import pathlib
import struct
import sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

PINNED_SOURCE = {
    'evidence_guard.py': '62b7a3417359d86c7d4fa781dfeb25a6969d00354c0a42bb0b1abeea0a28a76f',
    'test_evidence_guard.py': '9163c046a8cf30b691952123181e45437c5249989e054c87031f21d7416c2855',
}
PREREG_CANONICAL_SHA256 = '1d979331b4dd4ec762a1cfc940259081744787e54195409002a83df776abcffe'
REMOTE_PREREG_GIT_BLOB_SHA1 = 'a9d4b52e6cc1ce7191cc7f2fb2a048020b3aecc7'
TARGET = '2026-09-23T02:00:00.000Z'
CERT_PIN = '87f27f431da3f584af6007fe045df13aaa81d831f335b6ee73f6334768f32d3ae10491e669b93a43e548b20370a6526c3def99643c25d8ad7bf5df95a3c2b45d'
FAMILIES = ('positive_signed', 'missing_snapshot', 'alias_snapshot', 'snapshot_drift',
            'toolset_mismatch', 'resource_overrun', 'signature_tamper', 'untrusted_signer',
            'shared_signer', 'trust_root_tamper', 'exposed_corpus', 'duplicate_run_id',
            'protocol_tamper', 'missing_custodian')
EXPECTED = (None, 'MISSING_ACTUAL_SNAPSHOT_ID', 'MISSING_ACTUAL_SNAPSHOT_ID', 'SNAPSHOT_DRIFT',
            'ENVIRONMENT_DRIFT', 'RESOURCE_CAP_EXCEEDED', 'SIGNATURE_INVALID',
            'SIGNATURE_INVALID', 'SHARED_SIGNER', 'TRUST_ROOT_PIN_MISMATCH',
            'EXPOSED_OR_UNPROVEN', 'DUPLICATE_RUN_ID', 'PROTOCOL_PIN_MISMATCH', 'BUNDLE_SCHEMA')


def digest(b):
    return hashlib.sha256(b).hexdigest()


def need(ok, msg):
    if not ok:
        raise RuntimeError('FAIL_CLOSED:' + msg)


def u32(n):
    need(type(n) is int and 0 <= n < 2**32, 'UINT32')
    return struct.pack('>I', n)


def u64(n):
    need(type(n) is int and 0 <= n < 2**64, 'UINT64')
    return struct.pack('>Q', n)


def length_prefixed(b):
    return u32(len(b)) + b


def fromhex(s):
    need(type(s) is str and len(s) % 2 == 0, 'HEX_FIELD')
    return bytes.fromhex(s)


def signature_input(p):
    # Reference binary encoding, independently reconstructed from public NIST v2 format.
    e = p['external']
    parts = [length_prefixed(p['uri'].encode('utf8')),
             length_prefixed(p['version'].encode('utf8')),
             u32(p['cipherSuite']), u32(p['period']),
             length_prefixed(fromhex(p['certificateId'])),
             u64(p['chainIndex']), u64(p['pulseIndex']),
             length_prefixed(p['timeStamp'].encode('utf8')),
             length_prefixed(fromhex(p['localRandomValue'])),
             length_prefixed(fromhex(e['sourceId'])), u32(e['statusCode']),
             length_prefixed(fromhex(e['value']))]
    need([x['type'] for x in p['listValues']] ==
         ['previous', 'hour', 'day', 'month', 'year'], 'LIST_VALUE_ORDER')
    parts.extend(length_prefixed(fromhex(x['value'])) for x in p['listValues'])
    parts.extend([length_prefixed(fromhex(p['precommitmentValue'])), u32(p['statusCode'])])
    return b''.join(parts)


def verify_signed_pulse(p, certificate_bytes, target=TARGET, certificate_pin=CERT_PIN):
    need(p['timeStamp'] == target, 'WRONG_OR_REPLACED_PULSE')
    need(p['chainIndex'] == 2 and p['period'] == 60000 and
         p['cipherSuite'] == 0 and p['statusCode'] == 0 and p['pulseIndex'] > 0,
         'PULSE_FORMAT_OR_STATUS')
    need(p['uri'] == f"https://beacon.nist.gov/beacon/2.0/chain/2/pulse/{p['pulseIndex']}",
         'PULSE_URI')
    try:
        cert = x509.load_pem_x509_certificate(certificate_bytes)
    except ValueError:
        cert = x509.load_der_x509_certificate(certificate_bytes)
    der = cert.public_bytes(serialization.Encoding.DER)
    actual_pin = hashlib.sha512(der).hexdigest()
    need(actual_pin == certificate_pin and p['certificateId'].lower() == certificate_pin,
         'CERTIFICATE_PIN_MISMATCH')
    signed = signature_input(p)
    signature = fromhex(p['signatureValue'])
    try:
        cert.public_key().verify(signature, signed, padding.PKCS1v15(), hashes.SHA512())
    except Exception as exc:
        raise RuntimeError('FAIL_CLOSED:NIST_SIGNATURE_INVALID') from exc
    need(hashlib.sha512(signed + signature).hexdigest() == p['outputValue'].lower(),
         'NIST_OUTPUT_HASH_MISMATCH')
    need(len(fromhex(p['outputValue'])) == 64, 'NIST_OUTPUT_LENGTH')
    return p['outputValue'].lower()


def fixed_cases(output, source_dir):
    source_dir = pathlib.Path(source_dir).resolve()
    for name, expected in PINNED_SOURCE.items():
        need(digest((source_dir/name).read_bytes()) == expected, 'SOURCE_DRIFT_' + name)
    sys.path.insert(0, str(source_dir))
    for name in ('evidence_guard', 'test_evidence_guard'):
        if name in sys.modules:
            del sys.modules[name]
    guard = importlib.import_module('evidence_guard')
    tests = importlib.import_module('test_evidence_guard')
    results = []
    for family_index, family in enumerate(FAMILIES):
        for replicate in range(4):
            material = hashlib.sha256(
                b'QROS-RSI-G1-E2-V1' + bytes.fromhex(output) +
                family_index.to_bytes(2, 'big') + replicate.to_bytes(2, 'big')).digest()
            def private(label):
                return ed25519.Ed25519PrivateKey.from_private_bytes(
                    hashlib.sha256(material + label.encode()).digest())
            case = tests.ContractTests(methodName='test_01_positive_signed_synthetic_only')
            case.setUp()
            case.runner, case.custodian = private('runner'), private('custodian')
            case.trust = {'runner_ed25519': tests.pub(case.runner),
                          'custodian_ed25519': tests.pub(case.custodian)}
            case.rebuild()
            good = case.check()
            need(good['runner_signed'] == 6 and not good['scientific_promotion_authorized'],
                 'INVALID_POSITIVE_FIXTURE')
            idx = int.from_bytes(hashlib.sha256(material + b'index').digest(), 'big') % 6
            receipts = case.bundle['runner_receipts']
            if family == 'missing_snapshot':
                receipts[idx]['payload']['model_snapshot_id'] = ''
                case.resign_runner(idx)
            elif family == 'alias_snapshot':
                receipts[idx]['payload']['model_snapshot_id'] = receipts[idx]['payload']['requested_route']
                case.resign_runner(idx)
            elif family == 'snapshot_drift':
                eligible = [i for i, r in enumerate(receipts) if r['payload']['arm'].startswith('SOL_')]
                i = eligible[idx % len(eligible)]
                receipts[i]['payload']['model_snapshot_id'] = 'snapshot-sol-external-drift-v' + str(replicate)
                case.resign_runner(i)
            elif family == 'toolset_mismatch':
                receipts[idx]['payload']['toolset_sha256'] = digest(material)
                case.resign_runner(idx)
            elif family == 'resource_overrun':
                receipts[idx]['payload']['usage']['max_tool_calls'] = 9 + replicate
                case.resign_runner(idx)
            elif family == 'signature_tamper':
                receipts[idx]['payload']['model_snapshot_id'] = 'forged-provider-snapshot-' + str(replicate)
            elif family == 'untrusted_signer':
                receipts[idx] = tests.sign(private('untrusted'), receipts[idx]['payload'])
            elif family == 'shared_signer':
                case.trust['custodian_ed25519'] = case.trust['runner_ed25519']
                case.trust_pin = guard.sha(case.trust)
            elif family == 'trust_root_tamper':
                case.trust['runner_ed25519'] = tests.pub(private('untrusted'))
            elif family == 'exposed_corpus':
                case.bundle['custodian_receipt']['payload']['access_state'] = 'EXPOSED'
                case.resign_custody()
            elif family == 'duplicate_run_id':
                i = (idx + 1) % 6
                receipts[i]['payload']['run_id'] = receipts[idx]['payload']['run_id']
                case.resign_runner(i)
            elif family == 'protocol_tamper':
                case.bundle['protocol']['resource_caps']['max_tool_calls'] = 100 + replicate
            elif family == 'missing_custodian':
                del case.bundle['custodian_receipt']
            observed = None
            try:
                v = case.check()
                if family == 'positive_signed':
                    need(not v['model_improvement_demonstrated'] and
                         not v['independent_organizational_custody_verified'] and
                         not v['scientific_promotion_authorized'], 'POSITIVE_PROMOTION_LEAK')
            except guard.InvalidEvidence as exc:
                observed = str(exc)
            results.append({'family': family, 'replicate': replicate,
                            'expected': EXPECTED[family_index], 'observed': observed,
                            'pass': observed == EXPECTED[family_index]})
    return results


def selftest(source):
    # Artificial pre-pulse smoke run, excluded permanently from the 56 external cases.
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SYNTHETIC TEST ONLY')])
    c = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
         .public_key(key.public_key()).serial_number(7)
         .not_valid_before(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc))
         .not_valid_after(dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc))
         .sign(key, hashes.SHA512()))
    der = c.public_bytes(serialization.Encoding.DER)
    fake_pin = hashlib.sha512(der).hexdigest()
    p = {'uri': 'https://beacon.nist.gov/beacon/2.0/chain/2/pulse/1',
         'version': '2.0', 'cipherSuite': 0, 'period': 60000, 'certificateId': fake_pin,
         'chainIndex': 2, 'pulseIndex': 1, 'timeStamp': TARGET,
         'localRandomValue': '22'*64,
         'external': {'sourceId':'00'*64, 'statusCode':0, 'value':'00'*64},
         'listValues':[{'type':x,'value':'00'*64} for x in ('previous','hour','day','month','year')],
         'precommitmentValue':'11'*64,'statusCode':0}
    raw = signature_input(p)
    sig = key.sign(raw, padding.PKCS1v15(), hashes.SHA512())
    p['signatureValue'] = sig.hex()
    p['outputValue'] = hashlib.sha512(raw + sig).hexdigest()
    need(verify_signed_pulse(p, der, certificate_pin=fake_pin) == p['outputValue'], 'SYNTHETIC_SIGNED_FIXTURE')
    bad = copy.deepcopy(p)
    bad['outputValue'] = '00'*64
    try:
        verify_signed_pulse(bad, der, certificate_pin=fake_pin)
        raise RuntimeError('FAIL_CLOSED:TAMPERED_OUTPUT_ACCEPTED')
    except RuntimeError as exc:
        need(str(exc).endswith('NIST_OUTPUT_HASH_MISMATCH'), 'TAMPERED_OUTPUT_WRONG_REASON')
    cases = fixed_cases('11'*64, source)
    need(len(cases) == 56 and all(x['pass'] for x in cases), 'DRY_RUN_56_FAILURE')
    print(json.dumps({'mode':'SYNTHETIC_PRE_FREEZE_SMOKE_ONLY', 'signed_mock_pulse':'PASS',
                      'tampered_mock_pulse':'REJECTED','cases':len(cases),'passed':sum(x['pass'] for x in cases),
                      'actual_NIST_verified':False,'external_case_results':False},sort_keys=True))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir', required=True)
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--pulse-json')
    ap.add_argument('--certificate')
    ap.add_argument('--output')
    ap.add_argument('--selftest', action='store_true')
    a=ap.parse_args()
    pre=pathlib.Path(a.prereg).read_bytes()
    p=json.loads(pre)
    pre_canonical=json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    need(digest(pre_canonical)==PREREG_CANONICAL_SHA256,'PREREG_CANONICAL_DRIFT')
    need(p['external_seed']['exact_target_timestamp_utc']==TARGET and
         p['frozen_cases']['fixed_n']==56 and p['decision']=='PREREGISTERED_NO_RESULTS',
         'PREREG_PROTOCOL_DRIFT')
    if a.selftest:
        selftest(a.source_dir)
        return
    need(a.pulse_json and a.certificate and a.output,'ACTUAL_PULSE_INPUTS_MISSING')
    pulse=json.loads(pathlib.Path(a.pulse_json).read_bytes())['pulse']
    output=verify_signed_pulse(pulse,pathlib.Path(a.certificate).read_bytes())
    cases=fixed_cases(output,a.source_dir)
    report={'schema':'QROS_RSI_G1_E2_TEMPORAL_SYNTHETIC_RESULT_v1.0',
            'status':'PASS_56_OF_56' if all(x['pass'] for x in cases) else 'FAIL_CLOSED',
            'nist_chain_index':2,'nist_pulse_timestamp_utc':TARGET,
            'nist_pulse_index':pulse['pulseIndex'],'nist_output_sha512':output,
            'nist_certificate_sha512_der':CERT_PIN,
            'preregistration_canonical_sha256':PREREG_CANONICAL_SHA256,
            'preregistration_remote_git_blob_sha1':REMOTE_PREREG_GIT_BLOB_SHA1,
            'results':cases,'total':len(cases),'passed':sum(x['pass'] for x in cases),
            'organizational_independence_verified':False,'model_improvement_demonstrated':False,
            'scientific_promotion_authorized':False,'case_status':'SYNTHETIC_DIAGNOSTIC_EXPOSED'}
    pathlib.Path(a.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(report['status'], report['passed'], report['total'])
    need(report['status']=='PASS_56_OF_56','FUTURE_DIAGNOSTIC_FAILURE')


if __name__=='__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, ImportError) as exc:
        print('E2_FAIL_CLOSED',repr(exc),file=sys.stderr)
        sys.exit(1)
