"""Tests that prevent G3 from self-certifying without code, tests and evidence."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

G3=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(G3))
import anti_stall_gate as gate

class DeliveryEnforcementTests(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    assert (G3/'G3_SOURCE_MANIFEST.json').exists(),'SOURCE_FREEZE_MISSING'

  def test_full_local_source_gate(self):
    self.assertEqual(gate.verify(remote=False)['mandatory_paths'],12)

  def test_noop_or_partial_commit_fails(self):
    def fake(*args):
      if args[0]=='hash-object':
        return gate.G2_MOBILE_HEAD_BLOB if args[1].endswith('MOBILE_PRODUCT_HEAD.json') else gate.G2_VERIFIED_HEAD_BLOB
      return ''
    with patch.object(gate,'git',side_effect=fake),self.assertRaisesRegex(gate.GateReject,'NO_OP_OR_UNEXPECTED_DELTA'):
      gate.verify(remote=True)

  def test_extra_source_file_fails_scope(self):
    def fake(*args):
      if args[0]=='hash-object':
        return gate.G2_MOBILE_HEAD_BLOB if args[1].endswith('MOBILE_PRODUCT_HEAD.json') else gate.G2_VERIFIED_HEAD_BLOB
      return '\n'.join(sorted(gate.REQUIRED|{'control/HEAD.json'}))
    with patch.object(gate,'git',side_effect=fake),self.assertRaisesRegex(gate.GateReject,'NO_OP_OR_UNEXPECTED_DELTA'):
      gate.verify(remote=True)

  def test_forged_scientific_promotion_rejected(self):
    original=json.loads((G3/'G3_PROGRESS_HEAD.json').read_text())
    with tempfile.TemporaryDirectory() as tmp:
      p=Path(tmp)/'G3_PROGRESS_HEAD.json';p.write_text(json.dumps({**original,'scientific_authority':True}))
      (Path(tmp)/'G3_SOURCE_MANIFEST.json').write_bytes((G3/'G3_SOURCE_MANIFEST.json').read_bytes())
      with patch.object(gate,'G3',Path(tmp)),self.assertRaisesRegex(gate.GateReject,'SCIENCE_FIREWALL_DRIFT'):
        gate.verify()

  def test_missing_progress_next_action_rejected(self):
    original=json.loads((G3/'G3_PROGRESS_HEAD.json').read_text())
    with tempfile.TemporaryDirectory() as tmp:
      p=Path(tmp)/'G3_PROGRESS_HEAD.json';p.write_text(json.dumps({**original,'next_automatic_action':''}))
      (Path(tmp)/'G3_SOURCE_MANIFEST.json').write_bytes((G3/'G3_SOURCE_MANIFEST.json').read_bytes())
      with patch.object(gate,'G3',Path(tmp)),self.assertRaisesRegex(gate.GateReject,'FAKE_SUCCESS_OR_NO_NEXT_ACTION'):
        gate.verify()

  def test_manifest_code_hash_tamper_rejected(self):
    manifest=json.loads((G3/'G3_SOURCE_MANIFEST.json').read_text())
    original=gate.REPO
    with tempfile.TemporaryDirectory() as tmp:
      fake=Path(tmp)
      for rel in manifest['source_sha256']:
        p=fake/rel;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((original/rel).read_bytes())
      q=fake/'product/mobile/g3/oracle.py';q.write_text(q.read_text()+'\n# TAMPERED\n')
      with patch.object(gate,'REPO',fake),self.assertRaisesRegex(gate.GateReject,'SOURCE_HASH_DRIFT'):
        gate.verify(remote=False)

  def test_unprotected_baseline_drift_is_detected(self):
    def fake(*args):
      if args[0]=='hash-object' and args[1].endswith('MOBILE_PRODUCT_HEAD.json'):return '0'*40
      if args[0]=='hash-object':return gate.G2_VERIFIED_HEAD_BLOB
      return '\n'.join(sorted(gate.REQUIRED))
    with patch.object(gate,'git',side_effect=fake),self.assertRaisesRegex(gate.GateReject,'G2_BASELINE_MUTATED'):
      gate.verify(remote=True)

  def test_missing_native_or_test_source_rejected(self):
    mf=json.loads((G3/'G3_SOURCE_MANIFEST.json').read_text())
    for name in ('product/mobile/g3/native/executor.cpp','product/mobile/g3/tests/test_execution.py'):
      draft=json.loads(json.dumps(mf));del draft['source_sha256'][name]
      with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/'G3_SOURCE_MANIFEST.json').write_text(json.dumps(draft))
        (p/'G3_PROGRESS_HEAD.json').write_bytes((G3/'G3_PROGRESS_HEAD.json').read_bytes())
        with patch.object(gate,'G3',p),self.assertRaisesRegex(gate.GateReject,'MISSING_CODE_TEST_GATE_OR_UNEXPECTED_FILES'):
          gate.verify()

if __name__=='__main__':unittest.main()
