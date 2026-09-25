import json,sys,pathlib,tempfile,unittest,subprocess,shutil,hashlib,time
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from qros_w5_pipeline_v23 import build,run,GOLDEN,ORIG_POINTER_BLOB,SRC
sys.path.insert(0,str(ROOT/'anti_stall'/'scripts'))
from qros_anti_stall_v2_1 import sha_file,invoke,load_state,save_state,add_event,check_bytes,Incident
from qros_continuation_dispatch_v2_2 import queue_load
class W5PipelineTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.pin=build(self.root)
 def tearDown(self):self.tmp.cleanup()
 def test_externally_pinned_queue(self):
  z=json.loads(self.pin.read_bytes());q=queue_load(self.root/'W5_EXACT_FROZEN_QUEUE.json',z['queue_sha256']);self.assertEqual(len(q['jobs']),2)
 def test_expected_source_lock(self):
  z=json.loads(self.pin.read_bytes());self.assertEqual(z['frozen_original_pointer_blob'],ORIG_POINTER_BLOB);self.assertEqual(z['expected_synthetic_receipt_sha256'],GOLDEN)
 def test_historical_data_absent_does_not_promote(self):
  r=run(self.root,110);self.assertEqual(r['status'],'SYNTHETIC_GATE_PASS_DATA_EXACT_BYTES_PENDING');self.assertEqual(r['stages_promoted_this_invocation'],1)
  self.assertEqual(r['events'][1]['events'][-1]['action'],'EXTERNAL_PROOF_REQUIRED_SAFE_SKIP')
 def test_second_run_does_not_rerun_completed_gate(self):
  x=run(self.root,110);p=self.root/'W5_PRE_ECON_SYNTH'/'QROS_ANTI_STALL_STATE_V2_1.json';first=load_state(p.parent)
  z=run(self.root,15);second=load_state(p.parent)
  self.assertEqual(z['stages_promoted_this_invocation'],0);self.assertEqual(first['self_sha256'],second['self_sha256'])
 def test_immutability_fails_on_mutated_queue(self):
  p=self.root/'W5_EXACT_FROZEN_QUEUE.json';p.write_bytes(p.read_bytes()+b'\n')
  self.assertRaisesRegex(Incident,'QUEUE_PIN_MISMATCH',run,self.root,10)
 def test_immutable_corpus_fails_on_mutated_source(self):
  p=self.root/'W5_PRE_ECON_SYNTH'/'qros_w5_pre_econ_v1.py';p.write_bytes(p.read_bytes()+b'\n#tamper\n')
  self.assertRaises(Incident,run,self.root,110)
 def test_rebootstrap_cannot_replace_frozen_source(self):
  p=self.root/'W5_PRE_ECON_SYNTH'/'qros_w5_pre_econ_v1.py';p.write_bytes(p.read_bytes()+b'\n#tamper\n')
  self.assertRaisesRegex(Incident,'PREEXISTING_CORPUS_BYTES_DRIFT',build,self.root)
 def test_rebootstrap_is_idempotent(self):
  old=json.loads(self.pin.read_bytes());build(self.root);self.assertEqual(json.loads(self.pin.read_bytes()),old)
 def test_frozen_alternate_after_first_route_fails(self):
  p=self.root/'W5_PRE_ECON_SYNTH'/'FROZEN_PLAN.json';obj=json.loads(p.read_bytes());obj['stages'][0]['routes'][0]['argv']=[sys.executable,'-c','raise SystemExit(55)'];p.write_bytes((json.dumps(obj,sort_keys=True,indent=2)+'\n').encode());new_sha=sha_file(p)
  qpath=self.root/'W5_EXACT_FROZEN_QUEUE.json';q=json.loads(qpath.read_bytes());q['jobs'][0]['plan_sha256']=new_sha;qpath.write_bytes((json.dumps(q,sort_keys=True,indent=2)+'\n').encode())
  pin=json.loads(self.pin.read_bytes());pin['local_plan_sha256']=new_sha;pin['queue_sha256']=sha_file(qpath);self.pin.write_bytes((json.dumps(pin,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode())
  res=run(self.root,110);acts=[t['action'] for t in res['events'][0]['events']]
  self.assertEqual(acts,['INITIALIZED','FAILED_ROUTE_SWITCH_REQUIRED','ONE_STAGE_PASS']);self.assertEqual(res['stages_promoted_this_invocation'],1)
 def test_interrupted_with_exact_output_recovers_without_recompute(self):
  q=json.loads((self.root/'W5_EXACT_FROZEN_QUEUE.json').read_bytes());j=q['jobs'][0];work=pathlib.Path(j['work'])
  invoke(work,j['plan'],j['plan_sha256'],'init')
  s=load_state(work);s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['FROZEN_NUMBA_AND_INDEPENDENT_ORACLES'];add_event(s,'START','W5_SYNTHETIC_SOURCE_PRE_ECON',route='FROZEN_NUMBA_AND_INDEPENDENT_ORACLES');save_state(work,s)
  shutil.copyfile(ROOT/'PRE_ECON_SYNTH_RECEIPT.json',work/'PRE_ECON_SYNTH_RECEIPT.json')
  assert sha_file(work/'PRE_ECON_SYNTH_RECEIPT.json')==GOLDEN
  r=run(self.root,15);self.assertIn('INDEPENDENT_PINNED_OUTPUT_RECOVERED',[x['status'] for x in r['events']]);self.assertEqual(r['stages_promoted_this_invocation'],1)
 def test_interrupted_with_wrong_output_does_not_relaunch(self):
  q=json.loads((self.root/'W5_EXACT_FROZEN_QUEUE.json').read_bytes());j=q['jobs'][0];work=pathlib.Path(j['work'])
  invoke(work,j['plan'],j['plan_sha256'],'init');s=load_state(work);s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['FROZEN_NUMBA_AND_INDEPENDENT_ORACLES'];add_event(s,'START','W5_SYNTHETIC_SOURCE_PRE_ECON',route='FROZEN_NUMBA_AND_INDEPENDENT_ORACLES');save_state(work,s)
  (work/'PRE_ECON_SYNTH_RECEIPT.json').write_text('BAD OUTPUT')
  r=run(self.root,15);self.assertIn('INTERRUPTED_RECOVERY_FAIL_CLOSED',[x['status'] for x in r['events']]);self.assertEqual(r['stages_promoted_this_invocation'],0);self.assertEqual(load_state(work)['stages'][0]['status'],'RUNNING')
 def test_approval_firewalls_never_inferred(self):
  r=run(self.root,110);self.assertFalse(r['holdout_open']);self.assertFalse(r['ga2_open']);self.assertFalse(r['PnL_read']);self.assertEqual(r['economic_gate'],'CLOSED_BEFORE_REAL_TICK_AND_FILTER_PARITY')
if __name__=='__main__':unittest.main(verbosity=2)
