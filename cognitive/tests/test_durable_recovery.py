"""Fresh-process recovery with externally pinned checkpoint and ledger anchor."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from cognitive.tests.test_kernel import plan
from cognitive.tests import test_runtime as fixtures
ROOT=Path(__file__).resolve().parents[2]
WORKER='''import json,sys
from pathlib import Path
from cognitive import kernel as k,runtime as v
root=Path(sys.argv[1]);p=v.parse_json((root/'plan.json').read_bytes())
anchor=None if sys.argv[2]=='new' else v.parse_json((root/'anchor.json').read_bytes())
obj=k.Kernel(root,p,v.sha256(v.canonical(p)),sys.argv[3],'run',expected_resume_anchor=anchor)
try:
 if sys.argv[2]=='restore':obj.restore((root/'input_checkpoint.json').read_bytes(),sys.argv[4])
 r=obj.run();print(json.dumps(r))
finally:obj.close()
'''
class DurableRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def make(self,name):
        root=self.root/name;root.mkdir();(root/'cognitive').mkdir()
        for p in [v.MANIFEST,*v.PATHS.values()]:
            out=root/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((fixtures.AUTHORITY_ROOT/p).read_bytes())
        (root/'plan.json').write_bytes(v.canonical(plan()));return root
    def child(self,root,mode,expected=''):
        return subprocess.run([sys.executable,'-B','-c',WORKER,str(root),mode,fixtures.ANCHOR,expected],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5,env={'PATH':os.defpath,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'})
    def test_new_runtime_restores_without_duplicate_dispatch(self):
        first=self.make('first');p=self.child(first,'new');self.assertEqual(p.returncode,0,p.stderr);a=json.loads(p.stdout)
        second=self.make('second');(second/'anchor.json').write_bytes(v.canonical(a['resume_anchor']))
        cp=(first/'cognitive/runs/run/checkpoint.json').read_bytes();self.assertEqual(v.sha256(cp),a['checkpoint_sha256'])
        (second/'input_checkpoint.json').write_bytes(cp)
        p=self.child(second,'restore',a['checkpoint_sha256']);self.assertEqual(p.returncode,0,p.stderr);b=json.loads(p.stdout)
        self.assertEqual(b['newly_completed'],0);self.assertEqual(b['checkpoint_sha256'],a['checkpoint_sha256'])
        self.assertEqual(b['history_authentication'],'EXTERNAL_PREFIX_VERIFIED');self.assertNotEqual(a['capability']['session_id'],b['capability']['session_id'])
        self.assertFalse(b['capability']['inheritable']);self.assertGreater(b['semantic_revalidations_this_instance'],0)
    def test_wrong_external_checkpoint_hash_fails_closed(self):
        first=self.make('first');p=self.child(first,'new');self.assertEqual(p.returncode,0);a=json.loads(p.stdout)
        second=self.make('second');(second/'anchor.json').write_bytes(v.canonical(a['resume_anchor']))
        (second/'input_checkpoint.json').write_bytes((first/'cognitive/runs/run/checkpoint.json').read_bytes())
        p=self.child(second,'restore','0'*64);self.assertNotEqual(p.returncode,0);self.assertIn('CHECKPOINT_ANCHOR_MISMATCH',p.stderr)
        self.assertFalse((second/'cognitive/runs/run/checkpoint.json').exists())
if __name__=='__main__':unittest.main()
