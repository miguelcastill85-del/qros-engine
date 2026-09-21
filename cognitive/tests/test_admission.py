"""Real local-launcher admission, interruption and identity regression tests."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from cognitive import trusted_bootstrap as boot
from cognitive.tests.test_hardening import freeze
LAUNCHER=Path(os.environ.get('QRCEL_TEST_LAUNCHER',boot.__file__)).resolve()
class AdmissionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'cognitive').mkdir();(self.root/'cognitive/__init__.py').write_text('');self.children=[];self.addCleanup(self.cleanup)
 def cleanup(self):
  for p in self.children:
   if p.poll() is None:p.terminate()
   try:p.communicate(timeout=3)
   except subprocess.TimeoutExpired:p.kill();p.communicate(timeout=3)
 def package(self,source):
  (self.root/'cognitive/kernel.py').write_text(source);self.anchor=freeze(self.root)
 def command(self,run='test',wait=2,extra=()):
  return [sys.executable,'-I','-S','-B',str(LAUNCHER),'--repo-root',str(self.root),'--release-blob',self.anchor,'--entry','kernel','--wall','6','--admission-wait',str(wait),'--','--run-id',run,*extra]
 def start(self,run='test',wait=2):
  p=subprocess.Popen(self.command(run,wait),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={'PATH':os.defpath});self.children.append(p);return p
 def collect(self,p):
  out,err=p.communicate(timeout=8)
  try:r=json.loads(out)
  except ValueError:r={'stdout':out,'stderr':err}
  return p.returncode,r
 def wait_file(self,path,p):
  end=time.monotonic()+3
  while not path.exists() and p.poll() is None and time.monotonic()<end:time.sleep(.01)
  self.assertTrue(path.exists(),'worker did not reach boundary')
 def owner(self):
  self.pid=self.root/'pid';self.release=self.root/'release';self.package(f"import os,time\nfrom pathlib import Path\ndef main():\n Path({str(self.pid)!r}).write_text(str(os.getpid()))\n while not Path({str(self.release)!r}).exists():time.sleep(.01)\n print('{{\"status\":\"OK\"}}');return 0\n")
  p=self.start();self.wait_file(self.pid,p);return p
 def test_four_writers_never_overlap(self):
  marker=self.root/'exclusive';events=self.root/'events'
  self.package(f"import os,time\nfrom pathlib import Path\ndef main():\n fd=os.open({str(marker)!r},os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)\n with open({str(events)!r},'a') as f:f.write('enter\\n')\n time.sleep(.08)\n Path({str(marker)!r}).unlink()\n print('{{\"status\":\"OK\"}}');return 0\n")
  ps=[self.start() for _ in range(4)]
  for p in ps:self.assertEqual(self.collect(p)[0],0)
  self.assertEqual(events.read_text().splitlines(),['enter']*4)
 def test_independent_runs_do_not_share_lock(self):
  self.package(f"import argparse,time\nfrom pathlib import Path\ndef main():\n p=argparse.ArgumentParser();p.add_argument('--run-id');a,_=p.parse_known_args();base=Path({str(self.root)!r});(base/a.run_id).write_text('ready')\n end=time.monotonic()+2\n while not ((base/'A').exists() and (base/'B').exists()):\n  if time.monotonic()>end:return 9\n  time.sleep(.01)\n print('{{\"status\":\"OK\"}}');return 0\n")
  a=self.start('A');b=self.start('B');self.assertEqual(self.collect(a)[0],0);self.assertEqual(self.collect(b)[0],0)
 def test_deadline_has_no_kernel_side_effect(self):
  owner=self.owner();pid=self.pid.read_text();start=time.monotonic();code,r=self.collect(self.start(wait=.15))
  self.assertEqual(code,2);self.assertEqual(r.get('child_error'),'KERNEL_ADMISSION_TIMEOUT');self.assertTrue(r['retryable_local_admission']);self.assertLess(time.monotonic()-start,2);self.assertEqual(self.pid.read_text(),pid);self.assertFalse((self.root/'cognitive/runs').exists());self.release.touch();self.assertEqual(self.collect(owner)[0],0)
 def test_zero_wait_is_nonblocking_when_occupied(self):
  owner=self.owner();code,r=self.collect(self.start(wait=0));self.assertEqual(code,2);self.assertEqual(r.get('child_error'),'KERNEL_ADMISSION_TIMEOUT');self.release.touch();self.assertEqual(self.collect(owner)[0],0)
 def test_owner_cancellation_releases_lock_and_reaps_child(self):
  owner=self.owner();pid=int(self.pid.read_text());owner.terminate();self.assertNotEqual(self.collect(owner)[0],0);self.assertFalse(Path('/proc',str(pid)).exists());self.release.touch();self.assertEqual(self.collect(self.start())[0],0)
 def test_sigkill_worker_releases_lock(self):
  owner=self.owner();os.kill(int(self.pid.read_text()),signal.SIGKILL);self.assertNotEqual(self.collect(owner)[0],0);self.release.touch();self.assertEqual(self.collect(self.start())[0],0)
 def test_waiter_cancellation_does_not_unlock_owner(self):
  owner=self.owner();waiter=self.start();time.sleep(.1);waiter.terminate();self.assertNotEqual(self.collect(waiter)[0],0);code,r=self.collect(self.start(wait=0));self.assertEqual(r.get('child_error'),'KERNEL_ADMISSION_TIMEOUT');self.release.touch();self.assertEqual(self.collect(owner)[0],0);self.assertEqual(self.collect(self.start())[0],0)
 def test_stable_inode_survives_release(self):
  with boot.kernel_admission(self.root,'test',0):ino=(self.root/'cognitive/admission/test.lock').stat().st_ino
  with boot.kernel_admission(self.root,'test',0):self.assertEqual((self.root/'cognitive/admission/test.lock').stat().st_ino,ino)
 def test_unsafe_lock_links_and_modes_rejected(self):
  d=self.root/'cognitive/admission';d.mkdir(mode=0o700);target=self.root/'target';target.write_text('unchanged');target.chmod(0o600);p=d/'test.lock'
  for kind in ('symlink','hardlink','mode'):
   if kind=='symlink':p.symlink_to(target)
   elif kind=='hardlink':os.link(target,p)
   else:p.write_text('');p.chmod(0o644)
   with self.subTest(kind=kind),self.assertRaises((ValueError,OSError)):
    with boot.kernel_admission(self.root,'test',0):self.fail('unsafe admission accepted')
   p.unlink()
  self.assertEqual(target.read_text(),'unchanged')
 def test_unsafe_directory_rejected(self):
  d=self.root/'cognitive/admission';d.mkdir();d.chmod(0o755)
  with self.assertRaisesRegex(ValueError,'ADMISSION_DIRECTORY_UNSAFE'):
   with boot.kernel_admission(self.root,'test',0):pass
 def test_invalid_key_or_budget_has_no_lock_side_effect(self):
  for key,budget in [('../elsewhere',0),('',0),('x',-1),('x',16),('x',float('nan'))]:
   with self.subTest(key=key,budget=budget),self.assertRaises(ValueError):
    with boot.kernel_admission(self.root,key,budget):pass
  self.assertFalse((self.root/'cognitive/admission').exists())
 def test_argument_key_matches_last_exact_occurrence(self):
  self.assertEqual(boot.entry_arguments(['--run-id','A','--run-id=B'],'kernel'),'B');self.assertEqual(boot.entry_arguments(['--run-id=A'],'kernel'),'A')
  with self.assertRaisesRegex(ValueError,'KERNEL_RUN_ID_ABBREVIATION'):boot.entry_arguments(['--run-id','A','--run-i','B'],'kernel')
 def abbreviation_probe(self,field,extra,error):
  self.package(f"import argparse,json\ndef main():\n p=argparse.ArgumentParser();p.add_argument('--{field}');a,_=p.parse_known_args();print(json.dumps(vars(a)));return 0\n")
  cmd=[sys.executable,'-I','-S','-B',str(LAUNCHER),'--repo-root',str(self.root),'--release-blob',self.anchor,'--entry','kernel','--','--run-id','A',*extra]
  p=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=6);self.assertNotEqual(p.returncode,0,p.stdout);self.assertIn(error,p.stdout)
 def test_abbreviated_identity_cannot_override_root(self):self.abbreviation_probe('repo-root',['--repo-r','/other'],'ENTRY_IDENTITY_OVERRIDE')
 def test_abbreviated_run_cannot_change_lock_key(self):self.abbreviation_probe('run-id',['--run-i','B'],'KERNEL_RUN_ID_ABBREVIATION')
