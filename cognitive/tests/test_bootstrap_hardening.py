"""Real isolated launcher, resource and cancellation integration tests."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from cognitive.tests.test_hardening import freeze
from cognitive import trusted_bootstrap as boot

LAUNCHER=Path(boot.__file__).resolve()

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'cognitive').mkdir();(self.root/'cognitive/__init__.py').write_text('')
    def package(self,source):
        (self.root/'cognitive/session.py').write_text(source);return freeze(self.root)
    def command(self,anchor,*extra):
        return [sys.executable,'-I','-S','-B',str(LAUNCHER),'--repo-root',str(self.root),'--release-blob',anchor,*extra]
    def run_child(self,anchor,*extra):
        return subprocess.run(self.command(anchor,*extra),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=6,env={'PATH':os.defpath,'PYTHONPATH':'/invalid-untrusted-path'})
    def test_real_isolated_entry_uses_pinned_source(self):
        a=self.package("def main():\n print('{\"status\":\"EXPECTED\"}');return 0\n")
        p=self.run_child(a);self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(json.loads(p.stdout)['status'],'EXPECTED')
    def test_real_entry_rejects_added_matching_bytecode(self):
        import marshal,struct
        a=self.package("def main():\n print('EXPECTED');return 0\n");p=self.root/'cognitive/session.py'
        cache=Path(importlib.util.cache_from_source(str(p)));cache.parent.mkdir()
        cache.write_bytes(importlib.util.MAGIC_NUMBER+struct.pack('<III',0,int(p.stat().st_mtime),p.stat().st_size)+marshal.dumps(compile("def main():\n print('POISON');return 0\n",str(p),'exec')))
        result=self.run_child(a);self.assertNotEqual(result.returncode,0);self.assertIn('RELEASE_UNLISTED_CODE',result.stdout);self.assertNotIn('POISON',result.stdout)
    def test_loader_ignores_source_swap_after_capture(self):
        a=self.package("MARKER='VERIFIED'\n");files=boot.capture(self.root,a)
        (self.root/'cognitive/session.py').write_text("MARKER='SWAPPED'\n")
        module=types.ModuleType('cognitive.session');boot.VerifiedImporter(self.root,files).exec_module(module)
        self.assertEqual(module.MARKER,'VERIFIED')
    def test_loader_rejects_unverified_module(self):
        a=self.package('');finder=boot.VerifiedImporter(self.root,boot.capture(self.root,a))
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_IMPORT'):finder.find_spec('cognitive.missing')
    def test_namespace_exists_only_for_verified_descendants(self):
        finder=boot.VerifiedImporter(self.root,{'cognitive/tests/fixture.py':b'VALUE=1'})
        spec=finder.find_spec('cognitive.tests');self.assertIsNotNone(spec.submodule_search_locations)
        module=types.ModuleType('cognitive.tests');finder.exec_module(module);self.assertEqual(module.__path__,[])
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_IMPORT'):finder.find_spec('cognitive.tests.other')
    def test_wall_deadline_terminates_worker(self):
        a=self.package('import time\ndef main():\n time.sleep(20)\n')
        p=self.run_child(a,'--wall','1');self.assertEqual(p.returncode,124);self.assertEqual(json.loads(p.stdout)['error'],'WALL_BUDGET_EXCEEDED')
    def test_memory_allocation_is_bounded(self):
        a=self.package('def main():\n value=bytearray(512*1024*1024);return 0\n')
        p=self.run_child(a,'--memory-mib','64');self.assertNotEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout)['status'],'FAIL_CLOSED')
    def test_identity_override_is_rejected(self):
        a=self.package('def main():return 0\n')
        p=self.run_child(a,'--','--repo-root','/other');self.assertNotEqual(p.returncode,0);self.assertIn('ENTRY_IDENTITY_OVERRIDE',p.stdout)
    def test_cancellation_reaps_worker(self):
        marker=self.root/'pid.txt'
        a=self.package('import os,time\nfrom pathlib import Path\ndef main():\n Path('+repr(str(marker))+').write_text(str(os.getpid()))\n time.sleep(20)\n')
        p=subprocess.Popen(self.command(a),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            end=time.monotonic()+3
            while not marker.exists() and p.poll() is None and time.monotonic()<end:time.sleep(.01)
            self.assertTrue(marker.exists());pid=int(marker.read_text());p.terminate();out,err=p.communicate(timeout=3)
            self.assertNotEqual(p.returncode,0);self.assertIn('SUPERVISOR_CANCELLED',out)
            self.assertFalse((Path('/proc')/str(pid)).exists())
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)

if __name__=='__main__':unittest.main()
