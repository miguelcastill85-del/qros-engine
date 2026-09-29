"""Verify recovered immutable CI ZIP bytes and the G5 cryptographic contract."""
import base64, copy, hashlib, io, json, pathlib, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent / 'g4'), str(ROOT.parent / 'g5')]
from proof_gateway import VerifiedSnapshot
from witness import Head
from data_audit import canonical

raw = base64.b64decode((ROOT / 'receipts/CI_36298699641.zip.base64').read_text().strip(), validate=True)
digest = hashlib.sha256(raw).hexdigest()
assert digest == 'bb2f50aaf53df31962b366fc816dc827744c25f0ae7bc9da468c49155b4c9a92'
assert len(raw) == 11942
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    receipt = json.loads(z.read('CI_RECEIPT.json'))
    assert receipt['source_commit'] == 'f1187a66035698ee9b2eda6e2d0a1aa3828735c2'
    assert receipt['run_id'] == '36298699641'
    assert len(z.namelist()) == 8
    assert set(z.namelist()) == set(receipt['files_sha256']) | {'CI_RECEIPT.json'}
    for name, expected in receipt['files_sha256'].items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected, name
    fixture = json.loads(z.read('parity_fixture.json'))
    payload = fixture['payload']
    assert z.read('worker_snapshot.json') == canonical(payload)
    assert hashlib.sha256(canonical(payload)).hexdigest() == fixture['canonical_payload_sha256']

def verify(p):
    return VerifiedSnapshot.construct(
        tenant='tenant_A', project='project_A', campaign='campaign_A',
        audit_receipt=p['audit_receipt'], signed_witness_event=p['witness_event'],
        witness_public_key=base64.b64decode(fixture['public_key_b64']),
        witness_id='g9_backend_test_only', known_prior_head=Head(0, '0' * 64))

assert verify(payload).witness_head.sha256 == payload['head']['sha256']
for mutation in ('signature', 'tenant', 'audit'):
    p = copy.deepcopy(payload)
    if mutation == 'signature':
        p['witness_event']['signature_b64'] = base64.b64encode(bytes(64)).decode()
    elif mutation == 'tenant':
        p['witness_event']['body']['tenant'] = 'tenant_B'
    else:
        p['audit_receipt']['rows'] = 999
    try:
        verify(p)
    except ValueError:
        pass
    else:
        raise AssertionError(mutation)
print(json.dumps({'status': 'PASS', 'archive_sha256': digest, 'archive_bytes': len(raw),
                  'member_hashes_verified': 7, 'positive_crypto': 1, 'negative_crypto': 3,
                  'external_custody': 'NOT_DEPLOYED'}, sort_keys=True))
