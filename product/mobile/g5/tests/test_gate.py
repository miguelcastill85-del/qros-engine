"""G5 anti-stall must reject tampered code, missing tests or fabricated approval."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
G5=Path(__file__).resolve().parents[1]
REPO=G5.parents[2]
sys.path.insert(0,str(G5))
from anti_stall_gate import GateReject,verify

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='qros_g5_gate_');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        manifest=json.loads((G5/'G5_SOURCE_MANIFEST.json').read_text())
        for path in [*manifest['source_sha256'],'product/mobile/g5/G5_SOURCE_MANIFEST.json',
                     'product/mobile/g5/G5_PROGRESS_HEAD.json']:
            dest=self.root/path;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(REPO/path,dest)

    def test_clean_source_gate(self):
        x=verify(root=self.root)
        self.assertEqual(x['exact_new_files'],9)
        self.assertEqual(x['source_files_hashed'],7)
        self.assertFalse(x['scientific_gate_pass'])

    def test_missing_test_cannot_be_marked_complete(self):
        (self.root/'product/mobile/g5/tests/test_gateway.py').unlink()
        with self.assertRaisesRegex(GateReject,'SOURCE_MISSING_OR_LINKED'):
            verify(root=self.root)

    def test_modified_gateway_blocked(self):
        p=self.root/'product/mobile/g5/proof_gateway.py'
        p.write_text(p.read_text()+'\n# unauthorized mutation\n')
        with self.assertRaisesRegex(GateReject,'SOURCE_SHA256_DRIFT'):
            verify(root=self.root)

    def test_noop_manifest_blocked(self):
        p=self.root/'product/mobile/g5/G5_SOURCE_MANIFEST.json'
        d=json.loads(p.read_text());d['source_sha256']={}
        p.write_text(json.dumps(d))
        with self.assertRaisesRegex(GateReject,'SOURCE_TEST_AND_CI_CENSUS_MISMATCH'):
            verify(root=self.root)

    def test_fake_holdout_authority_and_pass_blocked(self):
        p=self.root/'product/mobile/g5/G5_PROGRESS_HEAD.json'
        d=json.loads(p.read_text());d['holdout_open']=True
        p.write_text(json.dumps(d))
        with self.assertRaisesRegex(GateReject,'SCIENTIFIC_PERMISSION_DRIFT'):
            verify(root=self.root)
        d['holdout_open']=False;d['phase']='APPROVED_FINAL'
        p.write_text(json.dumps(d))
        with self.assertRaisesRegex(GateReject,'FAKE_SUCCESS_OR_MISSING_NEXT_ACTION'):
            verify(root=self.root)

if __name__=='__main__':unittest.main()
