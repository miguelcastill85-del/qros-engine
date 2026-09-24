import hashlib,json,os,pathlib,sys,tempfile,time,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_progress_watchdog_v2_2 import watch,verified_progress
from qros_continuation_dispatch_v2_2 import dispatch
from qros_anti_stall_v2_1 import Incident,sha_file,invoke

AUTH={'repo':'owner/repo','branch':'research/frozen','base_commit':'b'*40}
LOCK={'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False}
class StrictNonstall(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def job(self,name,routes,depends=(),timeout=1):
  work=self.root/name;work.mkdir();src=work/'data.dat';src.write_text('frozen input')
  plan={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'SAME_CAUSAL_LANE','authority':AUTH,'scientific_firewalls':LOCK,
   'stages':[{'id':'ONE_STAGE','kind':'local','timeout_seconds':timeout,
      'inputs':[{'path':'data.dat','bytes':src.stat().st_size,'sha256':sha_file(src)}],
      'outputs':[{'path':'result.dat','sha256':None,'bytes':None}],
      'routes':[{'name':x[0],'argv':[sys.executable,'-c',x[1]]} for x in routes]}]}
  path=work/'PLAN.json';path.write_text(json.dumps(plan,sort_keys=True))
  return {'id':name,'work':str(work),'plan':str(path),'plan_sha256':sha_file(path),
    'kind':'local','hard_route_seconds':20,'max_distinct_routes':len(routes),'depends_on':list(depends)}
 def queue(self,jobs):
  obj={'schema':'QROS_BOUNDED_CONTINUATION_QUEUE_V2_2','authority':AUTH,'control_root':str(self.root/'control'),'jobs':jobs}
  p=self.root/'QUEUE.json';p.write_text(json.dumps(obj,sort_keys=True));return p,sha_file(p)
 def test_automatic_switch_to_frozen_equivalent_route(self):
  j=self.job('FIRST',[('frozen_primary',"open('attempted','w').write('primary');raise SystemExit(27)"),
       ('frozen_equivalent',"open('result.dat','w').write('verified output');open('alt','w').write('1')")])
  p,h=self.queue([j]);r=dispatch(p,h,8)
  self.assertEqual(r['status'],'ONE_VERIFIED_STAGE_PASS');self.assertEqual(r['job'],'FIRST')
  self.assertEqual([x['action'] for x in r['events'] if 'details' in x],['FAILED_ROUTE_SWITCH_REQUIRED','ONE_STAGE_PASS'])
  self.assertEqual((pathlib.Path(j['work'])/'result.dat').read_text(),'verified output')
  self.assertEqual(invoke(j['work'],j['plan'],j['plan_sha256'],'status')['stages'][0]['attempted_routes'],['frozen_primary','frozen_equivalent'])
  r2=dispatch(p,h,8);self.assertEqual(r2['status'],'NO_STAGE_PROMOTED_SAFE_DEFER')
  self.assertEqual((pathlib.Path(j['work'])/'alt').read_text(),'1')
 def test_blocked_critical_path_moves_to_independent_verified_job(self):
  blocked=self.job('BLOCKED',[('only_route',"raise SystemExit(31)")]);dependent=self.job('DEPENDENT',[('should_never_start',"open('result.dat','w').write('oops')")],depends=['BLOCKED'])
  independent=self.job('INDEPENDENT',[('safe_non_economic',"open('result.dat','w').write('safe pass')")])
  q,h=self.queue([blocked,dependent,independent]);r=dispatch(q,h,9)
  self.assertEqual(r['status'],'ONE_VERIFIED_STAGE_PASS');self.assertEqual(r['job'],'INDEPENDENT')
  self.assertEqual([x['action'] for x in r['events']],['INITIALIZED','HALTED_NO_FROZEN_ROUTE','DEPENDENCY_BLOCKED_SAFE_SKIP','INITIALIZED','ONE_STAGE_PASS'])
  self.assertFalse((pathlib.Path(dependent['work'])/'result.dat').exists())
  self.assertEqual((pathlib.Path(independent['work'])/'result.dat').read_text(),'safe pass')
  self.assertEqual(invoke(blocked['work'],blocked['plan'],blocked['plan_sha256'],'run')['status'],'HALTED')
 def test_external_pin_and_authority_fail_closed(self):
  job=self.job('SINGLE',[('safe',"open('result.dat','w').write('pass')")]);p,h=self.queue([job]);
  with self.assertRaisesRegex(Incident,'QUEUE_EXTERNAL_SHA_DRIFT'):dispatch(p,'0'*64,5)
  x=json.loads(p.read_text());x['authority']['branch']='main';p.write_text(json.dumps(x))
  with self.assertRaisesRegex(Incident,'LANE_AUTHORITY_MIXING'):dispatch(p,sha_file(p),5)
  self.assertFalse((pathlib.Path(job['work'])/'result.dat').exists())
 def test_per_route_hard_cap_enforced_before_launch(self):
  j=self.job('LONG',[('bad',"open('result.dat','w').write('unexpected')")],timeout=25);q,h=self.queue([j]);
  with self.assertRaisesRegex(Incident,'FROZEN_ROUTE_TIMEOUT_EXCEEDS_HARD_BUDGET'):dispatch(q,h,30)
  self.assertFalse((pathlib.Path(j['work'])/'result.dat').exists())
 def test_idle_watchdog_kills_worker_and_keeps_partial_bytes(self):
  r=watch(self.root,[sys.executable,'-c',"open('partial.dat','w').write('reusable checkpoint');import time;time.sleep(5)"], 'progress.json',2,.24,poll=.03)
  self.assertEqual(r,124);self.assertEqual((self.root/'partial.dat').read_text(),'reusable checkpoint')
 def test_valid_shard_bytes_reset_idle_budget(self):
  script="""import time,json,hashlib,os
for n in range(1,4):
 time.sleep(.16);p='shard_'+str(n)+'.bin';b=('shard_'+str(n)).encode();open(p,'wb').write(b)
 x={'sequence':n,'verified_artifacts':[{'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}]}
 tmp='progress.tmp';open(tmp,'w').write(json.dumps(x));os.replace(tmp,'progress.json')
time.sleep(.05);open('final.dat','w').write('done')
"""
  r=watch(self.root,[sys.executable,'-c',script],'progress.json',2,.29,poll=.02)
  self.assertEqual(r,0);self.assertEqual((self.root/'final.dat').read_text(),'done')
 def test_fake_heartbeat_without_new_bytes_does_not_reset_idle(self):
  script="""import time,json,hashlib,os
p='shard.bin';b=b'unchanged';open(p,'wb').write(b)
for n in range(1,12):
 x={'sequence':n,'verified_artifacts':[{'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}]}
 tmp='progress.tmp';open(tmp,'w').write(json.dumps(x));os.replace(tmp,'progress.json');time.sleep(.10)
"""
  start=time.monotonic();r=watch(self.root,[sys.executable,'-c',script],'progress.json',2,.30,poll=.02)
  self.assertEqual(r,124);self.assertLess(time.monotonic()-start,1.0)
 def test_tampered_progress_sha_does_not_extend_deadline(self):
  script="""import time,json,os
open('shard.bin','wb').write(b'bytes')
for n in range(1,6):
 tmp='progress.tmp';open(tmp,'w').write(json.dumps({'sequence':n,'verified_artifacts':[{'path':'shard.bin','bytes':5,'sha256':'0'*64}]}));os.replace(tmp,'progress.json');time.sleep(.2)
"""
  r=watch(self.root,[sys.executable,'-c',script],'progress.json',2,.25,poll=.02)
  self.assertEqual(r,124)
if __name__=='__main__':unittest.main(verbosity=2)
