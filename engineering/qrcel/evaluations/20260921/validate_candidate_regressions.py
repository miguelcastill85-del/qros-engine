"""Targeted unchanged supervisor regressions plus candidate boundary checks."""
import json,pathlib,shutil,sys,tempfile,types,unittest
E=pathlib.Path(__file__).resolve().parent;S=E/'verified_release'
h=types.ModuleType('op');h.__file__=str(E/'validate_operational.py');exec(compile(pathlib.Path(h.__file__).read_bytes(),h.__file__,'exec'),h.__dict__)
k,v=h.load(S)
from cognitive.tests.test_bootstrap_hardening import BootstrapTests
from cognitive.tests.test_hardening import freeze
from cognitive import trusted_bootstrap as boot
import cognitive.tests.test_bootstrap_hardening as existing
with tempfile.TemporaryDirectory(prefix='qrcel-supervisor-regression-') as td:
 path=pathlib.Path(td)/'trusted_bootstrap.py'
 original=(S/'cognitive/trusted_bootstrap.py').read_text()
 path.write_text(original.replace('resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,)*2)',"resource.setrlimit(resource.RLIMIT_FSIZE,((8 if args.entry == 'kernel' else 1)*1024*1024,)*2)"))
 # Existing loader tests exercise unchanged captured importer; process tests launch candidate file.
 existing.LAUNCHER=path
 class Boundaries(unittest.TestCase):
  def setUp(self):
   self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);(self.root/'cognitive').mkdir();(self.root/'cognitive/__init__.py').write_text('')
  def run_entry(self,entry,source):
   (self.root/'cognitive'/f'{entry}.py').write_text(source);blob=freeze(self.root)
   return h.run_command([sys.executable,'-I','-S','-B',str(path),'--repo-root',str(self.root),'--release-blob',blob,'--entry',entry],6)
  def test_kernel_file_2_mib_with_small_receipt(self):
   f=self.root/'data.bin';r=self.run_entry('kernel',f"from pathlib import Path\ndef main():\n Path({str(f)!r}).write_bytes(b'x'*(2*1024*1024)); print('{{\"status\":\"ok\"}}'); return 0\n")
   self.assertEqual(r['exit'],0,r);self.assertEqual(f.stat().st_size,2*1024*1024)
  def test_session_file_budget_stays_one_mib(self):
   f=self.root/'data.bin';r=self.run_entry('session',f"from pathlib import Path\ndef main():\n Path({str(f)!r}).write_bytes(b'x'*(2*1024*1024)); return 0\n")
   self.assertNotEqual(r['exit'],0,r);self.assertLessEqual(f.stat().st_size,1024*1024)
  def test_kernel_output_acceptance_stays_one_mib(self):
   r=self.run_entry('kernel',"def main():\n print('x'*(2*1024*1024));return 0\n")
   self.assertEqual(r['exit'],2,r);self.assertEqual(r['json']['error'],'OUTPUT_LIMIT')
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(BootstrapTests),unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 receipt={'scope':'CANDIDATE_SUPERVISOR_ONLY','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'pass':result.wasSuccessful(),'active_release_changed':False,'new_cases':3,'existing_affected_regressions':9}
 (E/'CANDIDATE_REGRESSION_RECEIPT.json').write_bytes(h.canonical(receipt))
 raise SystemExit(0 if result.wasSuccessful() else 1)
