"""Negative-control tests of delivery gate: detect no-op and forged progress."""
from __future__ import annotations
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

G2 = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(G2))
import anti_stall_gate as gate_mod


class NoProgressIsNotPass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='qros-antistall-')
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.g2 = self.root / 'product/mobile/g2'
        self.g2.mkdir(parents=True)
        src_ptr = G2 / 'G2_PROGRESS_HEAD.json'
        src_manifest = G2 / 'G2_SOURCE_MANIFEST.json'
        for source in (src_ptr, src_manifest):
            shutil.copyfile(source, self.g2 / source.name)
        manifest = json.loads(src_manifest.read_text())
        for name in manifest['source_file_sha256']:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(gate_mod.REPO/name, target)
        fixture = self.root/'product/mobile/flutter_app/test/fixtures/universe_oracle.json'
        fixture.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gate_mod.REPO/'product/mobile/flutter_app/test/fixtures/universe_oracle.json', fixture)
        self.g2_mock=patch.object(gate_mod, 'G2', self.g2)
        self.repo_mock=patch.object(gate_mod, 'REPO', self.root)
        self.g2_mock.start(); self.repo_mock.start()
        self.addCleanup(self.g2_mock.stop); self.addCleanup(self.repo_mock.stop)

    def _mock_git(self, *, diff=None, head=None):
        if diff is None:diff='\n'.join(sorted(gate_mod.REQUIRED))
        if head is None:head=gate_mod.FROZEN_G1_PRODUCT_HEAD_BLOB
        def fake_git(*parts):
            if parts[0]=='hash-object':return head
            if parts[0]=='diff':return diff
            raise RuntimeError('NO_UNEXPECTED_GIT_CALL')
        return patch.object(gate_mod,'git', fake_git)

    def test_valid_local_source_integrity_and_delta(self):
        with self._mock_git():
            self.assertTrue(gate_mod.gate(True)['remote_git_evidence'])

    def test_no_code_delta_fails_independently_of_checkpoint_claims(self):
        with self._mock_git(diff=''):
            with self.assertRaisesRegex(SystemExit, 'G2_DELTA_EXACT_SET_MISMATCH'):
                gate_mod.gate(True)

    def test_unexpected_baseline_file_modification_fails(self):
        extra='product/mobile/MOBILE_PRODUCT_HEAD.json'
        with self._mock_git(diff='\n'.join(sorted(gate_mod.REQUIRED | {extra}))):
            with self.assertRaisesRegex(SystemExit, 'unexpected=.*MOBILE_PRODUCT_HEAD'):
                gate_mod.gate(True)

    def test_modified_gate_code_fails_source_hash_check(self):
        p=self.root/'product/mobile/g2/anti_stall_gate.py'
        p.write_bytes(p.read_bytes()+b'\n# tampered\n')
        with self._mock_git():
            with self.assertRaisesRegex(SystemExit, 'SOURCE_HASH_DRIFT'):
                gate_mod.gate(True)

    def test_forged_scientific_approval_rejected(self):
        p=self.g2/'G2_PROGRESS_HEAD.json'
        doc=json.loads(p.read_text()); doc['scientific_result_claimed']=True
        p.write_text(json.dumps(doc)+'\n')
        with self._mock_git():
            with self.assertRaisesRegex(SystemExit,'INVALID_PRE_CI_STATE'):
                gate_mod.gate(True)

    def test_missing_native_enumerator_rejected(self):
        (self.root/'product/mobile/g2/native/enumerator.cpp').unlink()
        with self._mock_git():
            with self.assertRaisesRegex(SystemExit,'SOURCE_MISSING_OR_SYMLINK'):
                gate_mod.gate(True)

    def test_base_product_pointer_drift_rejected(self):
        with self._mock_git(head='f'*40):
            with self.assertRaisesRegex(SystemExit, 'G1_HEAD_REWRITTEN'):
                gate_mod.gate(True)


if __name__=='__main__':unittest.main()
