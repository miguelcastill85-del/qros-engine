"""G4 one-shot independent entitlement -> licensed synthetic audit -> signed witness readback.
No broker data, no API deployment, no private key files, no financial results.
"""
from __future__ import annotations
import base64
import json
from pathlib import Path
import tempfile
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from data_audit import audit, canonical, digest
from witness import GENESIS, LocalTestWitnessStore, WitnessVerifier


def run() -> dict:
    issuer = Ed25519PrivateKey.generate()
    writer = Ed25519PrivateKey.generate()
    raw_rows = [
       {"local_time":"2026-09-25T09:30:00.000", "utc_offset_minutes":-240,
        "fold":0, "bid_u":100, "ask_u":102, "session":1, "session_end":False},
       {"local_time":"2026-09-25T09:30:01.000", "utc_offset_minutes":-240,
        "fold":0, "bid_u":101, "ask_u":103, "session":1, "session_end":True},
    ]
    raw=b''.join(canonical(x)+b'\n' for x in raw_rows)
    spec={"schema":"QROS_G4_DATA_SPEC_TEST_V1", "symbol":"SIM_XAUUSD",
          "source_sha256":digest(raw), "broker_timezone":"America/New_York",
          "max_gap_ms":60000,"max_rows":100,"source_class":"SYNTHETIC_ONLY"}
    ent_body={"schema":"QROS_G4_SIGNED_ENTITLEMENT_TEST_V1", "issuer":"TEST_ISSUER",
              "tenant":"tenant_A", "source_sha256":digest(raw), "source_id":"SIM_XAUUSD_S1",
              "license_id":"SYNTHETIC_LICENSE_001", "purpose":"SYNTHETIC_SECURITY_TEST",
              "expires_utc":"2027-09-25T00:00:00Z", "redistribution":False,
              "source_class":"SYNTHETIC_ONLY"}
    entitlement={"body":ent_body,"signature_b64":base64.b64encode(issuer.sign(canonical(ent_body))).decode()}
    pubkey=issuer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    report=audit(raw,spec,entitlement,trusted_issuer_public_key=pubkey,
                 authenticated_tenant="tenant_A",purpose="SYNTHETIC_SECURITY_TEST",
                 current_utc="2026-09-25T14:00:00Z")
    assert report['execution_eligible'] and report['economic_tests']==0
    subject=digest(canonical(report))
    with tempfile.TemporaryDirectory(prefix='qros_g4_separate_witness_') as root:
        store=LocalTestWitnessStore(Path(root)/'witness_trust_store',writer,'DEMO_WITNESS')
        head,signed=store.append(prior=GENESIS,tenant='tenant_A',campaign='g4_demo',
                                  subject_sha256=subject,created_utc='2026-09-25T14:00:00Z',
                                  audit_receipt=report)
        client=WitnessVerifier(store.public_key,'DEMO_WITNESS')
        assert client.verify_known_head(signed,known=GENESIS,tenant='tenant_A',campaign='g4_demo')==head
        assert store.inspect()==head
    return {"schema":"QROS_G4_SYNTHETIC_INTEGRATION_RECEIPT_V1",
            "status":"PASS_LOCAL_SEPARATE_TRUST_STORE_TEST_ONLY", "rows":len(raw_rows),
            "raw_source_sha256":digest(raw),"audit_receipt_sha256":subject,
            "signed_witness_sequence":head.sequence,"signed_witness_body_sha256":head.sha256,
            "independently_pinned_writer_pub_sha256":digest(store.public_key),
            "license_redistribution":False,"licensed_purpose":"SYNTHETIC_SECURITY_TEST",
            "economic_backtests":0,"holdout_open":False,"ga2_open":False,
            "independent_operational_custody":"NOT_DEPLOYED",
            "external_dynamic_witness":"LOCAL_TWO_TRUST_DOMAINS_ONLY_NOT_PRODUCTION",
            "public_tls":"NOT_DEPLOYED","user_device":"NOT_TESTED",
            "signing_private_keys_written_to_disk":False}

if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True,indent=2))
