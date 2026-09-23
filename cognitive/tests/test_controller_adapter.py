import json
import shutil
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from cognitive.qros_controller_adapter import inspect
ROOT=Path(__file__).resolve().parents[1]
ANCHOR='5afce6279994b8625bd79fb2d5d13924e3c561e7'
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'tests/fixtures/v191',self.root,dirs_exist_ok=True)
    def test_original_v191_validates_without_writing(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        r=inspect(self.root,ANCHOR);self.assertEqual(r['status'],'PASS');self.assertEqual(r['population'],33094)
        self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertFalse(r['lease_contract_available'])
    def test_next_preserves_original_item_and_stage(self):
        r=inspect(self.root,ANCHOR,'next');q=json.loads((self.root/v.PATHS['run_queue']).read_bytes())
        expected=next(x for x in q['queue'] if x['item_id']==q['next_item'])
        self.assertEqual(r['next_item'],expected);self.assertEqual(r['source_queue_status'],'READY_AUTHORIZED')
        self.assertNotEqual(r['next_item']['item_id'],r['stage_hint']);self.assertFalse(r['scientific_dispatch_authorized'])
    def test_every_transition_is_rejected(self):
        for action in ['claim_lease','heartbeat_lease','release_lease','checkpoint_transition','scientific_dispatch']:
            with self.subTest(action=action),self.assertRaisesRegex(v.ContractError,'V191_TRANSITION_CONTRACT_REQUIRED'):inspect(self.root,ANCHOR,action)
    def test_tampered_head_fails_closed(self):
        p=self.root/v.PATHS['head'];p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(v.ContractError,'DELEGATED_BLOB_MISMATCH'):inspect(self.root,ANCHOR)
    def test_registry_cannot_be_skipped(self):
        (self.root/'control/QROS_ACTIVE_HASH_REGISTRY_V191_v1.json').write_text('{}')
        with self.assertRaisesRegex(v.ContractError,'REGISTRY_BLOB_MISMATCH'):inspect(self.root,ANCHOR)
    def test_coherent_hashes_do_not_allow_unregistered_progress(self):
        p=self.root/v.PATHS['run_queue'];q=json.loads(p.read_bytes());q['queue'][1]['status']='COMPLETED';raw=v.canonical(q);p.write_bytes(raw)
        mf=self.root/v.MANIFEST;m=json.loads(mf.read_bytes());m['single_active_authority']['run_queue']['git_blob_sha1']=v.git_blob(raw);raw=v.canonical(m);mf.write_bytes(raw)
        with self.assertRaises(v.ContractError):inspect(self.root,v.git_blob(raw),'next')
if __name__=='__main__':unittest.main()
