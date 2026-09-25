"""Deterministic TEST-ONLY G5 wire fixture; never use seeds for real trust roots.

The private seeds are in this CI-only generator and never in mobile assets. Each
fixture is derived through the frozen G4 auditor and G5 snapshot constructor.
"""
from __future__ import annotations
import base64, hashlib, json, pathlib, sys
HERE=pathlib.Path(__file__).resolve().parent
MOBILE=HERE.parent
sys.path.insert(0,str(MOBILE/'g4'))
sys.path.insert(0,str(MOBILE/'g5'))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from data_audit import audit,canonical,digest
from witness import GENESIS
from proof_gateway import VerifiedSnapshot,StrictHttpsDemoClient

TENANT='tenant_G6';PROJECT='project_G6';CAMPAIGN='campaign_G6';WITNESS='G6_SYNTHETIC_WITNESS'
ROW={'local_time':'2026-09-25T09:30:00.000','utc_offset_minutes':-240,'fold':0,
     'bid_u':100,'ask_u':102,'session':1,'session_end':True}
ISSUER_SEED=bytes(range(32))
WITNESS_SEED=bytes(range(32,64))

def generate():
    raw=canonical(ROW)+b'\n'
    source_sha=digest(raw)
    spec={'schema':'QROS_G4_DATA_SPEC_TEST_V1','symbol':'SIM_XAUUSD',
          'source_sha256':source_sha,'broker_timezone':'America/New_York',
          'max_gap_ms':60000,'max_rows':10,'source_class':'SYNTHETIC_ONLY'}
    issuer=Ed25519PrivateKey.from_private_bytes(ISSUER_SEED)
    license_body={'schema':'QROS_G4_SIGNED_ENTITLEMENT_TEST_V1','issuer':'G6_TEST_ISSUER',
                  'tenant':TENANT,'source_sha256':source_sha,'source_id':'SYNTHETIC_G6',
                  'license_id':'G6_TEST_ONLY','purpose':'SYNTHETIC_SECURITY_TEST',
                  'expires_utc':'2027-09-25T00:00:00Z','redistribution':False,
                  'source_class':'SYNTHETIC_ONLY'}
    entitlement={'body':license_body,'signature_b64':base64.b64encode(issuer.sign(canonical(license_body))).decode()}
    issuer_pub=issuer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    audit_receipt=audit(raw,spec,entitlement,trusted_issuer_public_key=issuer_pub,
                        authenticated_tenant=TENANT,purpose='SYNTHETIC_SECURITY_TEST',
                        current_utc='2026-09-25T14:00:00Z')
    signer=Ed25519PrivateKey.from_private_bytes(WITNESS_SEED)
    public=signer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    body={'schema':'QROS_G4_WITNESS_TEST_V1','witness_id':WITNESS,
          'sequence':1,'previous_sha256':GENESIS.sha256,'tenant':TENANT,
          'campaign':CAMPAIGN,'subject_sha256':digest(canonical(audit_receipt)),
          'created_utc':'2026-09-25T14:00:00Z','classification':'TEST_ONLY_SYNTHETIC'}
    event={'body':body,'signature_b64':base64.b64encode(signer.sign(canonical(body))).decode()}
    snapshot=VerifiedSnapshot.construct(tenant=TENANT,project=PROJECT,campaign=CAMPAIGN,
             audit_receipt=audit_receipt,signed_witness_event=event,witness_public_key=public,
             witness_id=WITNESS,known_prior_head=GENESIS).public_payload()
    canonical_snapshot=canonical(snapshot)
    trust={'schema':'QROS_G6_OFFLINE_TRUST_FIXTURE_V1','classification':'SYNTHETIC_ONLY',
           'tenant':TENANT,'project':PROJECT,'campaign':CAMPAIGN,'witness_id':WITNESS,
           'witness_public_b64':base64.b64encode(public).decode(),
           'expected_audit_sha256':digest(canonical(audit_receipt)),
           'expected_head_sha256':digest(canonical(body)),'sequence':1,
           'snapshot_wire_sha256':digest(canonical_snapshot),
           'production_trust_root':False,'economic_backtests':0}
    return canonical_snapshot, canonical(trust),snapshot,trust

def freeze():
    snapshot,trust,_,_=generate()
    paths=[MOBILE/'flutter_app/assets/g6_signed_snapshot.json',
           MOBILE/'flutter_app/assets/g6_offline_trust.json']
    for path,raw in zip(paths,[snapshot,trust]):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw+b'\n')
    return {str(p.relative_to(MOBILE.parent.parent)):digest(p.read_bytes()) for p in paths}

if __name__=='__main__':
    print(json.dumps(freeze(),sort_keys=True))
