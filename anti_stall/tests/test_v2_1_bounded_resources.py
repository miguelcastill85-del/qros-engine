import hashlib,json,os,pathlib,subprocess,sys,tempfile,time,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_anti_stall_v2_1 import invoke,sha_file,Incident
class BoundedResources(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.t.name);self.script=self.root/'long_task.py';self.script.write_text('import time\ntime.sleep(4)\n')
  self.p=self.root/'PLAN.json';self.plan={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'BOUND_TEST','authority':{'repo':'org/repo','branch':'research/lane','base_commit':'f'*40},'scientific_firewalls':{'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False},'stages':[{'id':'LONG_TASK','kind':'local','timeout_seconds':1,'inputs':[{'path':'long_task.py','bytes':self.script.stat().st_size,'sha256':sha_file(self.script)}],'outputs':[{'path':'output.bin','sha256':None,'bytes':None}],'routes':[{'name':'primary','argv':[sys.executable,'long_task.py']}]}]}
  self.p.write_text(json.dumps(self.plan));self.pin=sha_file(self.p)
 def tearDown(self):self.t.cleanup()
 def test_timeout_terminates_without_automatic_retries(self):
  invoke(self.root,self.p,self.pin,'init');before=time.monotonic();r=invoke(self.root,self.p,self.pin,'run')
  self.assertEqual(r['status'],'HALTED_NO_FROZEN_ROUTE');self.assertIn('EXECUTION_TIMEOUT_PROCESS_TREE_TERMINATED',r['error'])
  self.assertLess(time.monotonic()-before,3.5)
  self.assertEqual(invoke(self.root,self.p,self.pin,'run')['status'],'HALTED')
 def test_bounded_parallel_lock_contention(self):
  if sys.platform.startswith('win'):self.skipTest('POSIX interprocess lock fixture; Windows locking separate certification required')
  child=subprocess.Popen([sys.executable,'-c',"import fcntl,pathlib,time,sys\np=pathlib.Path(sys.argv[1]);f=p.open('a+b');fcntl.flock(f,fcntl.LOCK_EX);pathlib.Path(sys.argv[2]).write_text('READY');time.sleep(2)",str(self.root/'.qros_anti_stall.lock'),str(self.root/'ready')])
  try:
   start=time.monotonic()
   while not (self.root/'ready').exists():
    if time.monotonic()-start>1:raise RuntimeError('LOCK_FIXTURE_DID_NOT_START')
    time.sleep(.02)
   old=os.environ.get('QROS_LOCK_TIMEOUT_SECONDS');os.environ['QROS_LOCK_TIMEOUT_SECONDS']='0.25'
   try:
    with self.assertRaisesRegex(Incident,'LOCK_CONTENTION_BOUNDED_EXIT'):invoke(self.root,self.p,self.pin,'init')
   finally:
    if old is None:os.environ.pop('QROS_LOCK_TIMEOUT_SECONDS',None)
    else:os.environ['QROS_LOCK_TIMEOUT_SECONDS']=old
   self.assertLess(time.monotonic()-start,1.5)
  finally:child.terminate();child.wait(timeout=3)
if __name__=='__main__':unittest.main(verbosity=2)
