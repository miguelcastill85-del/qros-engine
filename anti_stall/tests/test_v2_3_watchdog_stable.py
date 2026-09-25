"""Bounded watchdog qualification with explicit startup budget on slow Python hosts.

Legacy v2.2 tests used a 1s Python-worker wall cap: this host's Python
spawn takes >1s, so that *fixture* is not portable. Production wall caps
are unchanged; these tests qualify the same watchdog without a false timeout.
"""
import json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_progress_watchdog_v2_2 import watch

class StableWatchdog(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    @unittest.skipUnless(sys.platform.startswith('linux'),'Native sh process qualification is POSIX-only')
    def test_kills_stalled_native_worker_and_preserves_checkpoint(self):
        status=watch(self.root,['/bin/sh','-c',"printf 'frozen chunk' > partial.bin; sleep 5"],
                     'progress.json',3,.35,poll=.03)
        self.assertEqual(status,124)
        self.assertEqual((self.root/'partial.bin').read_bytes(),b'frozen chunk')
    def test_real_sha_progress_python_worker_passes_with_startup_included(self):
        worker='''import os,time,json,hashlib
for i in range(3):
 p='proof_'+str(i)+'.bin';b=('proof_'+str(i)).encode()
 open(p,'wb').write(b)
 rec={'sequence':i+1,'verified_artifacts':[{'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}]}
 tmp='progress.tmp';open(tmp,'w').write(json.dumps(rec));os.replace(tmp,'progress.json')
 time.sleep(.35)
open('final.bin','wb').write(b'worker complete')
'''
        status=watch(self.root,[sys.executable,'-c',worker],'progress.json',8,2.2,poll=.05)
        self.assertEqual(status,0)
        self.assertEqual((self.root/'final.bin').read_bytes(),b'worker complete')
if __name__=='__main__':unittest.main()
