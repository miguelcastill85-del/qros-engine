"""Closure regressions and release-integrity fault injection."""
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from cognitive.verify_release import verify
from cognitive.tests import test_runtime as fixtures


class ReleaseTests(unittest.TestCase):
    def test_f12_receipt_rechecks_every_observation_blob(self):
        obs = v.observe_authority(v.Snapshot(fixtures.ROOT), fixtures.ANCHOR)
        for field in ('manifest_bytes', 'head_bytes', 'state_bytes', 'queue_bytes'):
            for inspector in (v.authority_receipt, v.inspect_active_queue):
                changed = dataclasses.replace(obs, **{field: b'{}'})
                with self.subTest(field=field, inspector=inspector.__name__), self.assertRaises(v.ContractError):
                    inspector(changed)

    def test_f12_positive_inspection_and_wrong_anchor(self):
        obs = v.observe_authority(v.Snapshot(fixtures.ROOT), fixtures.ANCHOR)
        self.assertEqual(v.authority_receipt(obs)['status'], 'PASS')
        self.assertFalse(v.inspect_active_queue(obs)['dispatch_authorized'])
        with self.assertRaisesRegex(v.ContractError, 'MANIFEST_ANCHOR_MISMATCH'):
            v.authority_receipt(dataclasses.replace(obs, manifest_blob='a' * 40))
        with self.assertRaisesRegex(v.ContractError, 'INVALID_AUTHORITY_OBSERVATION'):
            v.authority_receipt(None)

    def package(self):
        temp = tempfile.TemporaryDirectory(prefix='qrcel-release-test-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'cognitive').mkdir()
        (root / 'cognitive/module.py').write_bytes(b'# synthetic only\n')
        manifest = {'schema': 'QRCEL_SOURCE_AND_ENGINEERING_EVIDENCE_MANIFEST_V1',
                    'scientific_authority': False,
                    'files_sha256': {'cognitive/module.py': v.sha256(b'# synthetic only\n')}}
        raw = v.canonical(manifest)
        (root / 'cognitive/COGNITIVE_MANIFEST.json').write_bytes(raw)
        return root, v.git_blob(raw)

    def test_release_positive_read_only(self):
        root, anchor = self.package()
        before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
        r = verify(root, anchor)
        self.assertEqual((r['status'], r['files_verified']), ('PASS', 1))
        self.assertFalse(r['scientific_dispatch_authorized'])
        self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_release_wrong_anchor(self):
        root, _ = self.package()
        with self.assertRaisesRegex(v.ContractError, 'RELEASE_ANCHOR_MISMATCH'):
            verify(root, 'a' * 40)

    def test_release_missing_or_modified_source(self):
        for value in (None, b'# changed\n'):
            root, anchor = self.package()
            p = root / 'cognitive/module.py'
            if value is None:
                p.unlink()
            else:
                p.write_bytes(value)
            with self.subTest(value=value), self.assertRaises(v.ContractError):
                verify(root, anchor)

    def test_release_unlisted_code(self):
        root, anchor = self.package()
        (root / 'cognitive/extra.py').write_bytes(b'# extra\n')
        with self.assertRaisesRegex(v.ContractError, 'RELEASE_UNLISTED_CODE'):
            verify(root, anchor)

    def test_release_symlink_rejected(self):
        root, anchor = self.package()
        (root / 'cognitive/link').symlink_to(root, target_is_directory=True)
        with self.assertRaisesRegex(v.ContractError, 'RELEASE_SYMLINK'):
            verify(root, anchor)

    def test_release_no_scientific_authority_or_outside_scope(self):
        for field, value in (('scientific_authority', True), ('files_sha256', {'control/HEAD.json': 'a' * 64})):
            root, _ = self.package()
            p = root / 'cognitive/COGNITIVE_MANIFEST.json'
            m = json.loads(p.read_bytes()); m[field] = value
            raw = v.canonical(m); p.write_bytes(raw)
            with self.subTest(field=field), self.assertRaises(v.ContractError):
                verify(root, v.git_blob(raw))
