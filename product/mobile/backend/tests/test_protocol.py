import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol import (TrustRoot, EvidenceRejected, checked_json, canonical,
                      load_verified_snapshot, sha256, verify_snapshot)


class SignatureAndAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_raw = (ROOT / 'demo/trust_root.json').read_bytes()
        cls.snap_raw = (ROOT / 'demo/signed_snapshot.json').read_bytes()
        cls.pin = (ROOT / 'demo/PUBLIC_PIN.txt').read_text().strip()
        cls.trust = TrustRoot.parse(cls.root_raw, cls.pin)
        cls.snapshot = checked_json(cls.snap_raw)

    def test_full_authentication_with_separate_keys(self):
        verified = verify_snapshot(self.snapshot, self.trust)
        self.assertEqual(verified.anchor_sha256, self.trust.anchor_sha256)
        self.assertEqual(verified.anchor_sequence, 1)
        self.assertEqual(verified.project['id'], 'DEMO-001')
        self.assertNotEqual(self.trust.witness_public_key, self.trust.receipt_public_key)

    def test_witness_signature_tamper(self):
        b = copy.deepcopy(self.snapshot)
        b['anchor']['body']['digest'] = 'b' * 64
        with self.assertRaisesRegex(EvidenceRejected, 'SIGNATURE_INVALID'):
            verify_snapshot(b, self.trust)

    def test_receipt_signature_tamper(self):
        b = copy.deepcopy(self.snapshot)
        b['receipt']['body']['project']['title'] = 'WINNER'
        with self.assertRaisesRegex(EvidenceRejected, 'SIGNATURE_INVALID'):
            verify_snapshot(b, self.trust)

    def test_signature_swapping(self):
        b = copy.deepcopy(self.snapshot)
        b['receipt']['signature_b64'] = b['anchor']['signature_b64']
        with self.assertRaisesRegex(EvidenceRejected, 'SIGNATURE_INVALID'):
            verify_snapshot(b, self.trust)

    def test_replaced_root_bytes_fail_out_of_band_pin(self):
        root = json.loads(self.root_raw)
        root['anchor_sha256'] = 'a' * 64
        with self.assertRaisesRegex(EvidenceRejected, 'UNTRUSTED_TRUST_ROOT_BYTES'):
            TrustRoot.parse(canonical(root), self.pin)

    def test_stale_anchor_pin_rejected_even_with_valid_signatures(self):
        root = json.loads(self.root_raw)
        root['anchor_sha256'] = 'a' * 64
        valid_alternative_pin = sha256(canonical(root))
        altered_trust = TrustRoot.parse(canonical(root), valid_alternative_pin)
        with self.assertRaisesRegex(EvidenceRejected, 'EXTERNAL_HEAD_ANCHOR_MISMATCH'):
            verify_snapshot(self.snapshot, altered_trust)

    def test_signature_wrong_format(self):
        b = copy.deepcopy(self.snapshot)
        b['receipt']['signature_b64'] = '********'
        with self.assertRaisesRegex(EvidenceRejected, 'BAD_SIGNATURE_ENCODING'):
            verify_snapshot(b, self.trust)

    def test_promoted_metadata_without_signature_is_rejected(self):
        b = copy.deepcopy(self.snapshot)
        b['receipt']['body']['scientific_approval'] = True
        with self.assertRaisesRegex(EvidenceRejected, 'SIGNATURE_INVALID'):
            verify_snapshot(b, self.trust)

    def test_added_actor_authority_field_not_accepted(self):
        b = copy.deepcopy(self.snapshot)
        b['receipt']['body']['actor'] = 'QROS_CORE'
        with self.assertRaisesRegex(EvidenceRejected, 'SIGNATURE_INVALID'):
            verify_snapshot(b, self.trust)

    def test_unsigned_schema_extra_field_rejected(self):
        b = copy.deepcopy(self.snapshot)
        b['attacker_override'] = 'APPROVED_FINAL'
        with self.assertRaisesRegex(EvidenceRejected, 'SNAPSHOT_SCHEMA'):
            verify_snapshot(b, self.trust)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(EvidenceRejected, 'INVALID_JSON'):
            checked_json(b'{"schema":"demo","schema":"override"}')

    def test_nan_and_oversized_payload_rejected(self):
        with self.assertRaisesRegex(EvidenceRejected, 'INVALID_JSON'):
            checked_json(b'{"x":NaN}')
        with self.assertRaisesRegex(EvidenceRejected, 'BAD_JSON_SIZE'):
            checked_json(b'x' * 65537)

    def test_symlinked_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'trust.json', Path(tmp) / 'bundle.json'
            a.symlink_to(ROOT / 'demo/trust_root.json')
            b.write_bytes(self.snap_raw)
            with self.assertRaisesRegex(EvidenceRejected, 'UNSAFE_OR_OVERSIZED_SOURCE_FILE'):
                load_verified_snapshot(a, self.pin, b)

    def test_private_signing_keys_never_shipped(self):
        names = [x.name.lower() for x in (ROOT / 'demo').iterdir()]
        self.assertFalse(any(x.endswith(('.pem', '.key', '.p12', '.pfx')) for x in names))
        self.assertEqual(len(self.trust.witness_public_key), 32)


if __name__ == '__main__':
    unittest.main()
