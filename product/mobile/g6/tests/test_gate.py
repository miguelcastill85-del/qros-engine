import json,pathlib,shutil,tempfile,sys,unittest
G6=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(G6))
from anti_stall_gate import verify,GateReject,ROOT,REQUIRED
class AntistallGateTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=pathlib.Path(tmp.name)
  for p in REQUIRED:
   d=self.root/p;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,d)
 def test_exact_files_local_pass(self):
  x=verify(self.root);self.assertEqual(x['new_required_files'],18)
 def test_noop_without_native_dart_impl_is_rejected(self):
  (self.root/'product/mobile/flutter_app/lib/core/g6_signed_snapshot.dart').unlink()
  with self.assertRaisesRegex(GateReject,'SOURCE_MISSING_OR_HASH_DRIFT'):verify(self.root)
 def test_fake_approved_science_fails(self):
  p=self.root/'product/mobile/g6/G6_PROGRESS_HEAD.json';v=json.loads(p.read_text());v['holdout_open']=True;p.write_text(json.dumps(v))
  with self.assertRaisesRegex(GateReject,'SCIENTIFIC_FIREWALL_DRIFT'):verify(self.root)
 def test_frozen_python_oracle_tamper_denied(self):
  p=self.root/'product/mobile/g6/generate_signed_fixture.py';p.write_text(p.read_text()+'\n# unauthorized\n')
  with self.assertRaisesRegex(GateReject,'SOURCE_MISSING_OR_HASH_DRIFT'):verify(self.root)
 def test_remove_widget_tests_denied(self):
  (self.root/'product/mobile/flutter_app/test/g6_widget_test.dart').unlink()
  with self.assertRaisesRegex(GateReject,'SOURCE_MISSING_OR_HASH_DRIFT'):verify(self.root)
if __name__=='__main__':unittest.main()
