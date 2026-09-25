from __future__ import annotations
import base64, hashlib, json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SEED=bytes.fromhex('1f'*32)
ZERO='0'*64

def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def sha(b): return hashlib.sha256(b).hexdigest()

def build():
    key=Ed25519PrivateKey.from_private_bytes(SEED)
    pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    audit={
      'schema':'QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1','classification':'TEST_ONLY_NO_SCIENTIFIC_AUTHORITY',
      'tenant':'tenant_A','source_id':'g6_fixture','source_sha256':sha(b'G6_SYNTHETIC_SOURCE\n'),
      'license_id':'license_fixture','source_class':'SYNTHETIC_ONLY','broker_timezone':'America/New_York','rows':2,
      'diagnostics':{'zero_spread_preserved':0,'crossed_spread_preserved':0,'large_gaps':0,'session_transitions':0,'invalid_execution_quotes':0},
      'execution_eligible':True,'imputation':'NONE','economic_tests':0,'holdout_open':False,'ga2_open':False,
      'audit_spec_sha256':sha(b'G6_SYNTHETIC_SPEC')}
    body={'schema':'QROS_G4_WITNESS_TEST_V1','witness_id':'witness_fixture','sequence':1,'previous_sha256':ZERO,
          'tenant':'tenant_A','campaign':'campaign_A','subject_sha256':sha(canonical(audit)),
          'created_utc':'2026-09-25T12:00:00Z','classification':'TEST_ONLY_SYNTHETIC'}
    event={'body':body,'signature_b64':base64.b64encode(key.sign(canonical(body))).decode()}
    head={'sequence':1,'sha256':sha(canonical(body))}
    payload={'schema':'QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1','source_class':'SYNTHETIC_ONLY','scientific_approval':False,
             'tenant':'tenant_A','project':'project_A','campaign':'campaign_A','audit_receipt':audit,'witness_event':event,'head':head,
             'external_independent_custody':'NOT_DEPLOYED','economic_backtests':0,'holdout_open':False,'ga2_open':False}
    return {'schema':'QROS_G6_DART_PYTHON_PARITY_FIXTURE_V1','public_key_b64':base64.b64encode(pub).decode(),
            'witness_id':'witness_fixture','known_prior_head':{'sequence':0,'sha256':ZERO},'payload':payload,
            'canonical_payload_sha256':sha(canonical(payload))}

if __name__=='__main__':
    p=Path(__file__).parent/'tests/fixtures/g5_signed_snapshot_fixture.json'
    p.write_text(json.dumps(build(),indent=2,sort_keys=True)+'\n')
    print(p)
