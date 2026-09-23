"""Adversarial tests: independent Meta-Audit imported separately from runner."""
import copy,hashlib,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_anti_stall_v2_1 import invoke,canonical,sha_file,blob_sha,signed,load_state,save_state,add_event,Incident
from qros_meta_audit_v2_1 import audit,AuditError,encode,hexsha

class TestV21(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.worker=self.root/'worker.py';self.worker.write_text("from pathlib import Path\np=Path('count.txt')\np.write_text(str(int(p.read_text())+1 if p.exists() else 1))\nPath('out.txt').write_text('OK')\n")
        (self.root/'archive.zip').write_bytes(b'ZIP_BYTES_EXAMPLE')
        self.anchor={'schema':'QROS_EXTERNAL_OUTPUT_ANCHOR_V1','lane_id':'SEED0076','stage_id':'DRIVE_SAVE','remote_id':'DRIVE_TEST_ID',
                     'outputs':[{'path':'archive.zip','bytes':17,'sha256':sha_file(self.root/'archive.zip')}]}
        self.anchor_path=self.root/'anchor.json';self.anchor_path.write_bytes(encode(self.anchor))
        self.git_sha=blob_sha(self.anchor_path.read_bytes())
        self.plan={
            'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'SEED0076',
            'authority':{'repo':'miguelcastill85-del/qros-engine','branch':'research/seed0076-direct-dev-backtest-20260922','base_commit':'f'*40},
            'scientific_firewalls':{'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False},
            'stages':[
                {'id':'LOCAL_BUILD','kind':'local','timeout_seconds':5,
                 'inputs':[{'path':'worker.py','sha256':sha_file(self.worker),'bytes':self.worker.stat().st_size}],
                 'routes':[{'name':'primary','argv':[sys.executable,'worker.py']}],
                 'outputs':[{'path':'out.txt','bytes':2,'sha256':hashlib.sha256(b'OK').hexdigest()}]},
                {'id':'DRIVE_SAVE','kind':'external','remote_id':'DRIVE_TEST_ID','anchor_git_blob_sha1':self.git_sha,
                 'outputs':[{'path':'archive.zip','bytes':17,'sha256':sha_file(self.root/'archive.zip')}]}
            ]}
        self.plan_path=self.root/'PLAN.json';self.set_plan(self.plan)
        self.proof=self.root/'proof.json';self.proof.write_text(json.dumps({'source':'GOOGLE_DRIVE_CONNECTED_READBACK','verified_remote_readback':True,'remote_id':'DRIVE_TEST_ID','file_name':'archive.zip','bytes':17}))
        self.snaps={'DRIVE_SAVE':{'id':'DRIVE_TEST_ID','title':'archive.zip','size':'17'}}
    def tearDown(self):self.tmp.cleanup()
    def set_plan(self,p):self.plan_path.write_bytes(encode(p));self.pin=sha_file(self.plan_path)
    def call(self,verb,**kw):return invoke(self.root,self.plan_path,self.pin,verb,**kw)
    def local(self):self.call('init');return self.call('run')
    def attest(self):return self.call('attest',proof_path=self.proof,anchor_path=self.anchor_path,anchor_git_blob=self.git_sha)
    def meta(self,state_pin=None,anchors=True,snaps=True):return audit(self.root,self.plan_path,self.pin,remote_state_sha256=state_pin,
                                git_anchors={'DRIVE_SAVE':str(self.anchor_path)} if anchors else None,drive_snapshots=self.snaps if snaps else None)
    def test_01_complete_end_to_end(self):
        self.assertEqual(self.local()['status'],'ONE_STAGE_PASS')
        self.assertEqual(self.call('run')['status'],'EXTERNAL_NEEDS_GIT_ANCHOR_AND_DRIVE_READBACK')
        self.assertEqual(self.attest()['status'],'ONE_EXTERNAL_STAGE_PASS')
        self.assertEqual(self.call('run')['status'],'DONE_NOOP')
        external=sha_file(self.root/'QROS_ANTI_STALL_STATE_V2_1.json')
        self.assertEqual(self.meta(state_pin=external)['status'],'PASS')
        self.assertEqual(self.meta(state_pin=external)['passed_stages'],['LOCAL_BUILD','DRIVE_SAVE'])
    def test_02_resume_does_not_repeat_completed_build(self):
        self.local();self.assertEqual((self.root/'count.txt').read_text(),'1')
        self.assertEqual(self.call('init')['status'],'ALREADY_INITIALIZED')
        self.call('status');self.call('run');self.assertEqual((self.root/'count.txt').read_text(),'1')
    def test_03_no_pipeline_loop_retry_absent_alternate(self):
        self.worker.write_text("raise RuntimeError('BOOM')\n")
        self.plan['stages'][0]['inputs']=[{'path':'worker.py','sha256':sha_file(self.worker),'bytes':self.worker.stat().st_size}];self.set_plan(self.plan)
        self.call('init');self.assertEqual(self.call('run')['status'],'HALTED_NO_FROZEN_ROUTE')
        for _ in range(3):self.assertEqual(self.call('run')['status'],'HALTED')
        self.assertFalse((self.root/'count.txt').exists())
    def test_04_frozen_fallback_only_once(self):
        self.plan['stages'][0]['routes']=[{'name':'broken','argv':[sys.executable,'-c','raise Exception()']},
            {'name':'equivalent','argv':[sys.executable,'worker.py']}]
        self.set_plan(self.plan);self.call('init')
        self.assertEqual(self.call('run')['status'],'FAILED_ROUTE_SWITCH_REQUIRED')
        self.assertEqual(self.call('run')['status'],'ONE_STAGE_PASS')
        self.assertEqual((self.root/'count.txt').read_text(),'1')
        self.assertEqual(len(load_state(self.root)['stages'][0]['attempted_routes']),2)
    def test_05_frozen_plan_byte_change_is_rejected(self):
        self.call('init');self.plan_path.write_bytes(self.plan_path.read_bytes()+b'\n')
        with self.assertRaisesRegex(Incident,'FROZEN_PLAN_EXTERNAL_PIN_MISMATCH'):self.call('status')
    def test_06_output_tamper_is_rejected(self):
        self.local();(self.root/'out.txt').write_text('FAKE')
        with self.assertRaisesRegex(Incident,'ARTIFACT_SIZE_DRIFT'):self.call('status')
    def test_07_input_runner_tamper_rejected_even_if_output_unchanged(self):
        self.local();self.worker.write_text('print(123)')
        with self.assertRaisesRegex(AuditError,'INPUT_OR_RUNNER_DRIFT'):self.meta()
    def test_07b_runner_also_rejects_modified_closed_code(self):
        self.local();self.worker.write_text('print(123)')
        with self.assertRaisesRegex(Incident,'ARTIFACT_SIZE_DRIFT'):self.call('status')
    def test_08_consistent_fake_receipt_and_data_fails_with_external_state_pin(self):
        self.local();self.attest();pin=sha_file(self.root/'QROS_ANTI_STALL_STATE_V2_1.json')
        (self.root/'out.txt').write_bytes(b'FAKE')
        s=load_state(self.root);s['stages'][0]['outputs'][0]={'path':'out.txt','bytes':4,'sha256':sha_file(self.root/'out.txt')};save_state(self.root,s)
        with self.assertRaisesRegex(AuditError,'CHECKPOINT_REMOTE_PIN_FAIL'):self.meta(state_pin=pin)
    def test_09_self_hash_alone_is_not_immutable(self):
        self.local();self.attest();p=self.root/'QROS_ANTI_STALL_STATE_V2_1.json';original=sha_file(p)
        s=load_state(self.root);s['events'][0]['details']['comment']='forged';save_state(self.root,s)
        with self.assertRaisesRegex(AuditError,'CHECKPOINT_REMOTE_PIN_FAIL'):self.meta(state_pin=original)
    def test_10_anchor_tamper_is_rejected(self):
        self.local();self.attest();self.anchor['outputs'][0]['sha256']='0'*64;self.anchor_path.write_bytes(encode(self.anchor))
        with self.assertRaisesRegex(AuditError,'EXTERNAL_GIT_BLOB_DRIFT'):self.meta()
    def test_11_matching_fake_output_and_self_receipt_cannot_replace_anchor(self):
        self.local();self.attest();(self.root/'archive.zip').write_bytes(b'FORGED_BYTES______')
        s=load_state(self.root);s['stages'][1]['outputs'][0]={'path':'archive.zip','bytes':18,'sha256':sha_file(self.root/'archive.zip')};save_state(self.root,s)
        with self.assertRaisesRegex(AuditError,'OUTPUT_NOT_MATCHING_FROZEN_PLAN'):self.meta()
    def test_12_missing_drive_readback_is_fail_closed(self):
        self.local();self.proof.write_text(json.dumps({'verified_remote_readback':True,'remote_id':'DRIVE_TEST_ID','file_name':'archive.zip','bytes':17}))
        with self.assertRaisesRegex(Incident,'NO_CONNECTED_DRIVE_READBACK'):self.attest()
    def test_13_wrong_anchor_git_pin_is_rejected(self):
        self.local()
        with self.assertRaisesRegex(Incident,'UNPINNED_EXTERNAL_GIT_ANCHOR'):self.call('attest',proof_path=self.proof,anchor_path=self.anchor_path,anchor_git_blob='a'*40)
    def test_14_remote_anchor_requires_independent_meta_audit(self):
        self.local();self.attest()
        with self.assertRaisesRegex(AuditError,'EXTERNAL_GIT_BLOB_NOT_SUPPLIED'):self.meta(anchors=False)
        with self.assertRaisesRegex(AuditError,'CONNECTED_DRIVE_SNAPSHOT_NOT_SUPPLIED'):self.meta(snaps=False)
    def test_15_state_firewall_forgery_caught(self):
        self.call('init');s=load_state(self.root);s['scientific_firewalls']['holdout_open']=True;save_state(self.root,s)
        with self.assertRaisesRegex(Incident,'FIREWALL_DRIFT'):self.call('status')
        with self.assertRaisesRegex(AuditError,'SCIENTIFIC_FIREWALL_OPEN'):self.meta()
    def test_16_branch_authority_forgery_caught(self):
        self.call('init');s=load_state(self.root);s['authority']['branch']='main';save_state(self.root,s)
        with self.assertRaisesRegex(Incident,'AUTHORITY_MIXING'):self.call('status')
        with self.assertRaisesRegex(AuditError,'CROSS_LANE_AUTHORITY_MIXING'):self.meta()
    def test_17_duplicate_stage_rejected(self):
        self.plan['stages'][1]['id']='LOCAL_BUILD';self.set_plan(self.plan)
        with self.assertRaisesRegex(Incident,'STAGE_ID_INVALID_OR_DUPLICATE'):self.call('init')
    def test_18_path_symlink_escape(self):
        (self.root/'evil').symlink_to(pathlib.Path('/etc'))
        self.plan['stages'][0]['outputs']=[{'path':'evil/passwd','sha256':None,'bytes':None}];self.set_plan(self.plan)
        with self.assertRaisesRegex(Incident,'ARTIFACT_PATH_ESCAPE'):self.call('init')
    def test_19_no_implicit_rerun_after_crash_with_expected_hash(self):
        self.call('init');s=load_state(self.root);s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['primary'];add_event(s,'START','LOCAL_BUILD',route='primary');save_state(self.root,s)
        self.assertEqual(self.call('run')['status'],'INTERRUPTED_FAIL_CLOSED_USE_RECOVER')
        (self.root/'out.txt').write_bytes(b'OK')
        self.assertEqual(self.call('recover')['status'],'ONE_STAGE_RECOVERED')
        self.assertFalse((self.root/'count.txt').exists())
    def test_20_no_crash_recovery_without_frozen_expected_hash(self):
        self.plan['stages'][0]['outputs'][0]['sha256']=None;self.set_plan(self.plan);self.call('init')
        s=load_state(self.root);s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['primary'];add_event(s,'START','LOCAL_BUILD',route='primary');save_state(self.root,s)
        (self.root/'out.txt').write_bytes(b'OK')
        with self.assertRaisesRegex(Incident,'EXPECTED_OUTPUT_HASH_REQUIRED'):self.call('recover')
    def test_21_no_fabricated_progress_before_real_outputs(self):
        self.call('init');self.assertEqual(self.meta()['passed_stages'],[])
        self.assertEqual(self.call('status')['cursor'],0)
        self.assertEqual(self.meta()['status'],'TECHNICAL_PASS_NOT_FINAL')
    def test_22_remote_state_pin_requires_exact_raw_bytes(self):
        self.local();self.attest();s=self.root/'QROS_ANTI_STALL_STATE_V2_1.json';pin=sha_file(s)
        s.write_bytes(s.read_bytes()+b'\n')
        with self.assertRaisesRegex(AuditError,'CHECKPOINT_REMOTE_PIN_FAIL'):self.meta(state_pin=pin)
    def test_23_no_two_stages_same_output(self):
        self.plan['stages'][1]['outputs']=[{'path':'out.txt','bytes':2,'sha256':hashlib.sha256(b'OK').hexdigest()}];self.set_plan(self.plan)
        with self.assertRaisesRegex(Incident,'OUTPUT_PATH_REUSED_ACROSS_STAGES'):self.call('init')
    def test_24_no_novel_route_from_runtime(self):
        self.call('init')
        with self.assertRaisesRegex(Incident,'ROUTE_NOT_FROZEN'):self.call('run',route_name='UNRECORDED')
        self.assertEqual(self.call('run')['status'],'ONE_STAGE_PASS')
    def test_25_evidence_can_be_reverified_after_state_unchanged(self):
        self.local();self.attest();pin=sha_file(self.root/'QROS_ANTI_STALL_STATE_V2_1.json')
        self.assertEqual(self.meta(state_pin=pin),self.meta(state_pin=pin))
    def test_26_consistent_fake_event_hash_detected_by_event_semantics(self):
        self.local();self.attest();s=load_state(self.root)
        s['events']=[e for e in s['events'] if e['kind']!='PASS']
        prev='0'*64
        for i,e in enumerate(s['events'],1):
            e['sequence']=i;e['previous_sha256']=prev;e['event_sha256']=hexsha(encode({k:v for k,v in e.items() if k!='event_sha256'}));prev=e['event_sha256']
        save_state(self.root,s)
        with self.assertRaisesRegex(AuditError,'STAGE_PASS_EVENT_MISMATCH'):self.meta()
if __name__=='__main__':unittest.main(verbosity=2)
