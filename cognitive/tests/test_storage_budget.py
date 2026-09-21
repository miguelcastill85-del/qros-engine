"""Resource envelope compatibility, using real isolated bounded children."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from cognitive import trusted_bootstrap as boot
from cognitive.tests.test_hardening import freeze

class StorageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'cognitive').mkdir();(self.root/'cognitive/__init__.py').write_text('')
    def launch(self,entry,source):
        (self.root/'cognitive'/f'{entry}.py').write_text(source);anchor=freeze(self.root)
        return subprocess.run([sys.executable,'-I','-S','-B',boot.__file__,'--repo-root',str(self.root),'--release-blob',anchor,'--entry',entry],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=6,env={'PATH':os.defpath})
    def test_kernel_can_write_two_mib(self):
        target=self.root/'data.bin'
        p=self.launch('kernel',f"from pathlib import Path\ndef main():\n Path({str(target)!r}).write_bytes(b'x'*(2*1024*1024)); print('{{\"status\":\"ok\"}}');return 0\n")
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(target.stat().st_size,2*1024*1024)
    def test_session_stays_bounded_to_one_mib(self):
        target=self.root/'data.bin'
        p=self.launch('session',f"from pathlib import Path\ndef main():\n Path({str(target)!r}).write_bytes(b'x'*(2*1024*1024));return 0\n")
        self.assertNotEqual(p.returncode,0);self.assertLessEqual(target.stat().st_size,1024*1024)
    def test_kernel_output_acceptance_stays_one_mib(self):
        p=self.launch('kernel',"def main():\n print('x'*(2*1024*1024));return 0\n")
        self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['error'],'OUTPUT_LIMIT')
