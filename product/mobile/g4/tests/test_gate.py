"""Test that anti-stall rejects missing evidence, mutated source and fabricated PASS."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

G4=Path(__file__).resolve().parents[1]
REPO=G4.parents[2]
sys.path.insert(0,str(G4))
from anti_stall_gate import verify, GateReject

class AntistallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='qros_g4_antistall_')
        self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)
        manifest=json.loads((G4/'G4_SOURCE_MANIFEST_V2.json').read_text())
        for name in (*manifest['source_sha256'].keys(),
                     'product/mobile/g4/G4_SOURCE_MANIFEST.json',
                     'product/mobile/g4/G4_SOURCE_MANIFEST_V2.json',
                     'product/mobile/g4/G4_PROGRESS_HEAD.json'):
            source=REPO/name
            dest=self.repo/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)

    def test_exact_unmodified_source_gate_local(self):
        result=verify(repo=self.repo,remote=False)
        self.assertEqual(result['hashed_source_files'],9)
        self.assertEqual(result['required_new_files'],12)
        self.assertFalse(result['scientific_gate_pass'])

    def test_missing_test_file_is_not_an_advancement(self):
        (self.repo/'product/mobile/g4/tests/test_g4.py').unlink()
        with self.assertRaisesRegex(GateReject,'MISSING_OR_LINKED_SOURCE'):
            verify(repo=self.repo)

    def test_mutated_code_fails_even_if_narrative_claims_success(self):
        path=self.repo/'product/mobile/g4/witness.py'
        path.write_text(path.read_text()+'\n# unauthorized drift\n')
        with self.assertRaisesRegex(GateReject,'SOURCE_SHA256_DRIFT'):
            verify(repo=self.repo)

    def test_fake_scientific_authority_fails_closed(self):
        path=self.repo/'product/mobile/g4/G4_PROGRESS_HEAD.json'
        x=json.loads(path.read_text());x['scientific_authority']=True
        path.write_text(json.dumps(x))
        with self.assertRaisesRegex(GateReject,'SCIENTIFIC_FIREWALL_CHANGED'):
            verify(repo=self.repo)

    def test_progress_cannot_claim_PASS_before_remote_ci(self):
        path=self.repo/'product/mobile/g4/G4_PROGRESS_HEAD.json'
        x=json.loads(path.read_text());x['phase']='PASS_ENGINEERING_TEST_ONLY'
        path.write_text(json.dumps(x))
        with self.assertRaisesRegex(GateReject,'FAKE_PASS_OR_NO_NEXT_ACTION'):
            verify(repo=self.repo)

    def test_noop_empty_manifest_fails_closed(self):
        path=self.repo/'product/mobile/g4/G4_SOURCE_MANIFEST_V2.json'
        x=json.loads(path.read_text());x['source_sha256']={}
        path.write_text(json.dumps(x))
        with self.assertRaisesRegex(GateReject,'INCOMPLETE_CODE_TEST_AND_WORKFLOW_CENSUS'):
            verify(repo=self.repo)

if __name__=='__main__':unittest.main()
