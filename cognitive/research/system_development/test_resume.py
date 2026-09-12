"""Real trusted-worker interruption and resume; synthetic engineering, no model calls."""
import json
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from .run import run,PROJECT,HERE
from .recover import recover

AUTHORITY=PROJECT/'cognitive/tests/fixtures/v191'
ANCHOR='5afce6279994b8625bd79fb2d5d13924e3c561e7'
class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.protocol=json.loads((HERE/'PREREGISTRATION.json').read_bytes())
        self.protocol['source_sha256']={p:v.sha256((PROJECT/p).read_bytes()) for p in self.protocol['source_sha256']}
        self.prereg=self.root/'prereg.json';self.prereg.write_bytes(v.canonical(self.protocol))
        self.raw=(HERE/'sol_001/RAW_RESPONSE.json').read_bytes()
    def start(self,count=1):
        out=self.root/'first';run(self.raw,AUTHORITY,ANCHOR,self.prereg,out,'SYNTHETIC_REPLAY_REGRESSION',stop_after=count)
        return out,v.sha256((out/'PARTIAL_RESULTS.json').read_bytes())
    def test_actual_episode_resume_preserves_closed_receipts(self):
        first,sha=self.start(2);old=(first/'PARTIAL_RESULTS.json').read_bytes()
        receipt=recover(first,sha,self.prereg,partial=True)
        self.assertEqual(receipt['episodes_revalidated'],2);self.assertEqual(len(receipt['remaining_episodes']),13)
        out=self.root/'second';result=run(self.raw,AUTHORITY,ANCHOR,self.prereg,out,'SYNTHETIC_REPLAY_REGRESSION',first,sha)
        self.assertEqual(result['correct'],15);self.assertEqual(result['records'][:2],json.loads(old)['records'])
        self.assertEqual((first/'PARTIAL_RESULTS.json').read_bytes(),old)
        complete=recover(out,v.sha256((out/'RESULTS.json').read_bytes()),self.prereg)
        self.assertEqual(complete['episodes_revalidated'],15)
        # Simulate crash after final partial checkpoint but before RESULTS publication.
        fullsha=v.sha256((out/'PARTIAL_RESULTS.json').read_bytes());last=self.root/'third'
        final=run(self.raw,AUTHORITY,ANCHOR,self.prereg,last,'SYNTHETIC_REPLAY_REGRESSION',out,fullsha)
        self.assertEqual(final['records'],result['records'])
    def test_missing_external_anchor_rejected_before_new_directory(self):
        out=self.root/'bad'
        with self.assertRaisesRegex(v.ContractError,'RESUME_ANCHOR_REQUIRED'):
            run(self.raw,AUTHORITY,ANCHOR,self.prereg,out,'TEST',resume=self.root)
        self.assertFalse(out.exists())
    def test_reordered_partial_is_not_a_valid_prefix(self):
        first,sha=self.start(2);p=first/'PARTIAL_RESULTS.json';obj=json.loads(p.read_bytes());obj['records'].reverse();p.write_bytes(v.canonical(obj))
        with self.assertRaisesRegex(v.ContractError,'EPISODE_PREFIX'):
            recover(first,v.sha256(p.read_bytes()),self.prereg,partial=True)
    def test_legacy_unbound_partial_is_rejected(self):
        first,sha=self.start();p=first/'PARTIAL_RESULTS.json';obj=json.loads(p.read_bytes());p.write_bytes(v.canonical({'records':obj['records']}))
        with self.assertRaisesRegex(v.ContractError,'RESULT_SCHEMA_OR_STATUS'):
            recover(first,v.sha256(p.read_bytes()),self.prereg,partial=True)
    def test_changed_response_cannot_resume_closed_episodes(self):
        first,sha=self.start();out=self.root/'changed'
        with self.assertRaisesRegex(v.ContractError,'RESUME_RESPONSE_CHANGED'):
            run(self.raw+b' ',AUTHORITY,ANCHOR,self.prereg,out,'TEST',first,sha)
        self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
