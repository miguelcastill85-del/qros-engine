"""Adversarial G4 synthetic-only licensed-data and local witness tests."""
from __future__ import annotations
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from data_audit import AuditReject, audit, canonical, digest, strict_json, validate_entitlement
from witness import GENESIS, Head, LocalTestWitnessStore, WitnessVerifier


def keybytes(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def row(t, bid, ask, *, session=1, end=False, offset=-240, fold=0):
    return {"local_time":t, "utc_offset_minutes":offset, "fold":fold, "bid_u":bid,
            "ask_u":ask, "session":session, "session_end":end}


def raw_rows(rows):
    return b''.join(canonical(x) + b'\n' for x in rows)


def entitlement(key, raw, *, tenant='tenant_A', purpose='SYNTHETIC_SECURITY_TEST',
                expiry='2027-09-25T00:00:00Z', source='SYNTHETIC_ONLY', redistribute=False):
    body={"schema":"QROS_G4_SIGNED_ENTITLEMENT_TEST_V1", "issuer":"TEST_ISSUER",
          "tenant":tenant, "source_sha256":digest(raw), "source_id":"SIM_XAUUSD_S1",
          "license_id":"SYNTHETIC_LICENSE_001", "purpose":purpose, "expires_utc":expiry,
          "redistribution":redistribute, "source_class":source}
    return {"body":body,"signature_b64":base64.b64encode(key.sign(canonical(body))).decode()}

class LicenseAndDataAuditTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.good=[row('2026-09-25T09:30:00.000',100,102),
                   row('2026-09-25T09:30:01.000',101,103),
                   row('2026-09-25T09:30:02.000',102,104,end=True)]
        self.raw=raw_rows(self.good)
        self.spec={"schema":"QROS_G4_DATA_SPEC_TEST_V1", "symbol":"SIM_XAUUSD",
                   "source_sha256":digest(self.raw),"broker_timezone":"America/New_York",
                   "max_gap_ms":60000,"max_rows":100,"source_class":"SYNTHETIC_ONLY"}
        self.license=entitlement(self.key,self.raw)

    def go(self,raw=None,spec=None,license=None,tenant='tenant_A',purpose='SYNTHETIC_SECURITY_TEST'):
        return audit(self.raw if raw is None else raw,self.spec if spec is None else spec,
                     self.license if license is None else license,
                     trusted_issuer_public_key=keybytes(self.key),
                     authenticated_tenant=tenant,purpose=purpose,
                     current_utc='2026-09-25T14:00:00Z')

    def mutate_rows(self,rows):
        raw=raw_rows(rows)
        spec=dict(self.spec,source_sha256=digest(raw))
        return self.go(raw=raw,spec=spec,license=entitlement(self.key,raw))

    def test_valid_synthetic_source_no_economics(self):
        result=self.go()
        self.assertEqual(result['rows'],3)
        self.assertTrue(result['execution_eligible'])
        self.assertEqual(result['economic_tests'],0)
        self.assertFalse(result['holdout_open'])
        self.assertEqual(result['source_sha256'],digest(self.raw))
        self.assertEqual(result['imputation'],'NONE')

    def test_zero_spread_preserved_and_execution_quarantined(self):
        rows=list(self.good);rows[1]=row('2026-09-25T09:30:01.000',101,101)
        result=self.mutate_rows(rows)
        self.assertEqual(result['diagnostics']['zero_spread_preserved'],1)
        self.assertFalse(result['execution_eligible'])

    def test_crossed_spread_preserved_and_execution_quarantined(self):
        rows=list(self.good);rows[1]=row('2026-09-25T09:30:01.000',104,103)
        result=self.mutate_rows(rows)
        self.assertEqual(result['diagnostics']['crossed_spread_preserved'],1)
        self.assertFalse(result['execution_eligible'])

    def test_source_bytes_hash_must_match(self):
        with self.assertRaisesRegex(AuditReject,'RAW_SOURCE_HASH_MISMATCH'):
            self.go(raw=self.raw+b' ')

    def test_tenant_auth_context_not_claimed_in_payload(self):
        with self.assertRaisesRegex(AuditReject,'CROSS_TENANT'):
            self.go(tenant='tenant_B')

    def test_unpinned_or_wrong_license_signer(self):
        with self.assertRaisesRegex(AuditReject,'ENTITLEMENT_SIGNATURE_INVALID'):
            self.go(license=entitlement(Ed25519PrivateKey.generate(),self.raw))

    def test_tampered_license_rights(self):
        license=json.loads(json.dumps(self.license));license['body']['redistribution']=True
        with self.assertRaisesRegex(AuditReject,'RIGHTS_OR_SOURCE_CLASS'):
            self.go(license=license)
        license=json.loads(json.dumps(self.license));license['body']['source_id']='FORGED'
        with self.assertRaisesRegex(AuditReject,'ENTITLEMENT_SIGNATURE_INVALID'):
            self.go(license=license)

    def test_expired_license(self):
        with self.assertRaisesRegex(AuditReject,'LICENSE_EXPIRED'):
            self.go(license=entitlement(self.key,self.raw,expiry='2026-09-25T13:59:59Z'))

    def test_production_purpose_cannot_relabel_synthetic(self):
        with self.assertRaisesRegex(AuditReject,'UNLICENSED_PURPOSE'):
            self.go(purpose='RESEARCH_PRIVATE')
        with self.assertRaisesRegex(AuditReject,'SYNTHETIC_CANNOT_BECOME_LIVE'):
            self.go(license=entitlement(self.key,self.raw,purpose='RESEARCH_PRIVATE'),
                    purpose='RESEARCH_PRIVATE')

    def test_malicious_json_duplicates_nan_infinite(self):
        with self.assertRaisesRegex(AuditReject,'DUPLICATE_JSON_KEY'):
            strict_json(b'{"a":1,"a":2}')
        for value in (b'NaN',b'Infinity',b'-Infinity'):
            with self.subTest(value=value),self.assertRaises(AuditReject):
                strict_json(b'{"a":'+value+b'}')

    def test_duplicate_utc_and_backwards(self):
        rows=list(self.good);rows[1]=row('2026-09-25T09:30:00.000',101,103)
        with self.assertRaisesRegex(AuditReject,'DUPLICATE_OR_OUT_OF_ORDER_UTC'):
            self.mutate_rows(rows)
        rows=list(self.good);rows[1]=row('2026-09-25T09:29:59.000',101,103)
        with self.assertRaisesRegex(AuditReject,'DUPLICATE_OR_OUT_OF_ORDER_UTC'):
            self.mutate_rows(rows)

    def test_invented_timezone_and_utc_fallback_rejected(self):
        for name in ('GMT_BROKER_FAKE','UTC'):
            with self.subTest(tz=name),self.assertRaises(AuditReject):
                self.go(spec=dict(self.spec,broker_timezone=name))

    def test_wrong_dst_offset_rejected(self):
        rows=list(self.good);rows[0]=row('2026-09-25T09:30:00.000',100,102,offset=-300)
        with self.assertRaisesRegex(AuditReject,'TIMEZONE_OFFSET_MISMATCH'):
            self.mutate_rows(rows)

    def test_nonexistent_spring_dst_time_rejected(self):
        rows=[row('2026-03-08T02:30:00.000',100,102,offset=-300,end=True)]
        with self.assertRaisesRegex(AuditReject,'NONEXISTENT_OR_AMBIGUOUS_LOCAL_TIME'):
            self.mutate_rows(rows)

    def test_ambiguous_fall_dst_requires_explicit_fold(self):
        rows=[row('2026-11-01T01:30:00.000',100,102,end=True,offset=-300,fold=1)]
        result=self.mutate_rows(rows)
        self.assertEqual(result['rows'],1)
        with self.assertRaisesRegex(AuditReject,'TIMEZONE_OFFSET_MISMATCH'):
            self.mutate_rows([row('2026-11-01T01:30:00.000',100,102,end=True,offset=-300,fold=0)])

    def test_fold_one_on_unambiguous_time_rejected(self):
        rows=[row('2026-09-25T09:30:00.000',100,102,fold=1,end=True)]
        with self.assertRaisesRegex(AuditReject,'UNNECESSARY_FOLD_ONE'):
            self.mutate_rows(rows)

    def test_session_boundaries_preserved(self):
        rows=[row('2026-09-25T09:30:00.000',100,102,end=True),
              row('2026-09-25T09:35:00.000',105,107,session=2,end=True)]
        result=self.mutate_rows(rows)
        self.assertEqual(result['diagnostics']['session_transitions'],1)
        self.assertEqual(result['diagnostics']['large_gaps'],1)

    def test_session_cross_without_explicit_end_rejected(self):
        rows=[self.good[0],row('2026-09-25T09:30:01.000',100,102,session=2,end=True)]
        with self.assertRaisesRegex(AuditReject,'SESSION_BOUNDARY_OR_ORDER'):
            self.mutate_rows(rows)

    def test_missing_final_session_end_rejected(self):
        with self.assertRaisesRegex(AuditReject,'UNSEALED_LAST_SESSION'):
            self.mutate_rows([self.good[0]])

    def test_timestamps_cannot_be_bool_or_repainted(self):
        rows=list(self.good);rows[1]=dict(rows[1],utc_offset_minutes=True)
        with self.assertRaisesRegex(AuditReject,'DST_FOLD_OR_OFFSET_REQUIRED'):
            self.mutate_rows(rows)

    def test_source_size_and_unknown_row_fields_fail_closed(self):
        with self.assertRaisesRegex(AuditReject,'RAW_NEWLINE_OR_ROW_LIMIT'):
            self.go(raw=self.raw[:-1],spec=dict(self.spec,source_sha256=digest(self.raw[:-1])),
                    license=entitlement(self.key,self.raw[:-1]))
        rows=[dict(self.good[0],QROS_CORE=True)]
        with self.assertRaisesRegex(AuditReject,'SCHEMA_ROW'):
            self.mutate_rows(rows)

    def test_limited_licenses_are_not_redistributable(self):
        with self.assertRaisesRegex(AuditReject,'RIGHTS_OR_SOURCE_CLASS'):
            self.go(license=entitlement(self.key,self.raw,redistribute=True))

class SeparateWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='qros_g4_witness_')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'trust_store'
        self.key=Ed25519PrivateKey.generate()
        self.store=LocalTestWitnessStore(self.root,self.key,'WITNESS_DEMO_A')
        self.subject=digest(b'SYNTHETIC_AUDIT_ONLY')
        self.time='2026-09-25T14:00:00Z'

    def append(self, **kwargs):
        params=dict(prior=self.store.inspect(),tenant='tenant_A',campaign='demo_c1',
                    subject_sha256=self.subject,created_utc=self.time)
        params.update(kwargs)
        return self.store.append(**params)

    def test_genesis_and_signed_monotonic_chain(self):
        self.assertEqual(self.store.inspect(),GENESIS)
        first,event=self.append()
        self.assertEqual(first.sequence,1)
        self.assertEqual(self.store.inspect(),first)
        second,event2=self.append(created_utc='2026-09-25T14:00:01Z')
        self.assertEqual(second.sequence,2)
        self.assertEqual(event2['body']['previous_sha256'],first.sha256)
        self.assertNotEqual(second.sha256,first.sha256)

    def test_out_of_band_pinned_verifier(self):
        first,event=self.append()
        verify=WitnessVerifier(self.store.public_key,'WITNESS_DEMO_A')
        self.assertEqual(verify.verify_known_head(event,known=GENESIS,tenant='tenant_A',campaign='demo_c1'),first)

    def test_replayed_response_rejected_after_pinning(self):
        first,event=self.append()
        with self.assertRaisesRegex(AuditReject,'SEQUENCE_REPLAY_OR_FORK'):
            self.store.verifier.verify_known_head(event,known=first,tenant='tenant_A',campaign='demo_c1')

    def test_forged_signer_or_root_rejected(self):
        _,event=self.append()
        rogue=WitnessVerifier(keybytes(Ed25519PrivateKey.generate()),'WITNESS_DEMO_A')
        with self.assertRaisesRegex(AuditReject,'WITNESS_SIGNATURE_INVALID'):
            rogue.verify_known_head(event,known=GENESIS,tenant='tenant_A',campaign='demo_c1')
        wrong=WitnessVerifier(self.store.public_key,'WRONG_ID')
        with self.assertRaisesRegex(AuditReject,'WITNESS_ID_MISMATCH'):
            wrong.verify_known_head(event,known=GENESIS,tenant='tenant_A',campaign='demo_c1')

    def test_mutated_signed_body_rejected(self):
        _,event=self.append()
        evil=json.loads(json.dumps(event));evil['body']['subject_sha256']=digest(b'altered')
        with self.assertRaisesRegex(AuditReject,'WITNESS_SIGNATURE_INVALID'):
            self.store.verifier.verify_known_head(evil,known=GENESIS,tenant='tenant_A',campaign='demo_c1')

    def test_cross_tenant_and_campaign_rejected(self):
        _,event=self.append()
        for tenant,campaign in [('tenant_B','demo_c1'),('tenant_A','demo_c2')]:
            with self.subTest(tenant=tenant,campaign=campaign),self.assertRaisesRegex(AuditReject,'CROSS_TENANT_OR_CAMPAIGN'):
                self.store.verifier.verify_known_head(event,known=GENESIS,tenant=tenant,campaign=campaign)

    def test_stale_CAS_and_no_duplicate_append(self):
        self.append()
        with self.assertRaisesRegex(AuditReject,'EXTERNAL_WITNESS_CAS_CONFLICT'):
            self.append(prior=GENESIS)
        self.assertEqual(self.store.inspect().sequence,1)

    def test_truncated_log_fails_closed(self):
        self.append()
        with self.store.log.open('ab') as f:f.write(b'{"uncommitted":')
        with self.assertRaisesRegex(AuditReject,'TRUNCATED_WITNESS_LOG'):
            self.store.inspect()

    def test_tampered_log_fails_closed(self):
        self.append()
        raw=self.store.log.read_bytes().replace(self.subject.encode(),digest(b'EVIL').encode())
        self.store.log.write_bytes(raw)
        with self.assertRaisesRegex(AuditReject,'WITNESS_SIGNATURE_INVALID'):
            self.store.inspect()

    def test_deleted_tail_detected_against_externally_known_head(self):
        first,_=self.append()
        second,event=self.append(created_utc='2026-09-25T14:00:01Z')
        self.store.log.write_bytes(self.store.log.read_bytes().splitlines(keepends=True)[0])
        self.assertEqual(self.store.inspect(),first)
        # Signed historical head alone cannot prove freshness: external client pin is mandatory.
        self.assertNotEqual(self.store.inspect(),second)
        with self.assertRaisesRegex(AuditReject,'SEQUENCE_REPLAY_OR_FORK'):
            self.store.verifier.verify_known_head(event,known=second,tenant='tenant_A',campaign='demo_c1')

    def test_symlink_witness_file_rejected(self):
        fake=self.root/'attacker'
        fake.write_text('evil')
        self.store.log.symlink_to(fake)
        with self.assertRaisesRegex(AuditReject,'WITNESS_FILE_ACCESS_FAIL_CLOSED'):
            self.store.inspect()

    def test_symlink_directory_rejected(self):
        link=Path(self.tmp.name)/'link'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(AuditReject,'SYMLINK_WITNESS_DIRECTORY'):
            LocalTestWitnessStore(link,self.key,'WITNESS_DEMO_A')

    def test_timestamp_rollback_rejected(self):
        self.append()
        with self.assertRaisesRegex(AuditReject,'WITNESS_TIMESTAMP_ROLLBACK'):
            self.append(created_utc='2026-09-25T13:59:59Z')

    def test_quarantined_audit_is_not_anchored_as_executable(self):
        report={"schema":"QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1", "tenant":"tenant_A", "execution_eligible":False}
        with self.assertRaisesRegex(AuditReject,'UNVERIFIED_OR_QUARANTINED_AUDIT_ANCHOR'):
            self.append(subject_sha256=digest(canonical(report)),audit_receipt=report)

    def test_valid_tenant_scoped_audit_can_be_anchored(self):
        report={"schema":"QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1", "tenant":"tenant_A", "execution_eligible":True,
                "economic_tests":0,"holdout_open":False,"ga2_open":False}
        head,_=self.append(subject_sha256=digest(canonical(report)),audit_receipt=report)
        self.assertEqual(head.sequence,1)

    def test_crash_after_append_fsync_recovers_by_log_replay_without_duplicate(self):
        rawkey=self.key.private_bytes(serialization.Encoding.Raw,
                  serialization.PrivateFormat.Raw,serialization.NoEncryption()).hex()
        code='''from witness import LocalTestWitnessStore,GENESIS
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pathlib import Path
import sys
s=LocalTestWitnessStore(Path(sys.argv[1]),Ed25519PrivateKey.from_private_bytes(bytes.fromhex(sys.argv[2])), 'WITNESS_DEMO_A')
s.append(prior=GENESIS,tenant='tenant_A',campaign='demo_c1',subject_sha256=sys.argv[3],created_utc='2026-09-25T14:00:00Z')'''
        env=dict(os.environ, QROS_G4_TEST_KILL_AFTER_FSYNC='1', PYTHONPATH=str(ROOT))
        p=subprocess.run([sys.executable,'-c',code,str(self.root),rawkey,self.subject],env=env,capture_output=True)
        self.assertEqual(p.returncode,83,p.stderr.decode())
        self.assertEqual(self.store.inspect().sequence,1)
        with self.assertRaisesRegex(AuditReject,'EXTERNAL_WITNESS_CAS_CONFLICT'):
            self.append(prior=GENESIS)
        self.assertEqual(self.store.inspect().sequence,1)

    def test_concurrent_writers_CAS_exact_one_success(self):
        def attempt():
            try:
                self.append(prior=GENESIS)
                return 'success'
            except AuditReject as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _: attempt(),range(2)))
        self.assertEqual(outcomes.count('success'),1,outcomes)
        self.assertTrue(any('EXTERNAL_WITNESS_CAS_CONFLICT' in x for x in outcomes))
        self.assertEqual(self.store.inspect().sequence,1)

if __name__=='__main__':
    unittest.main()
