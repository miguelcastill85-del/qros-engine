"""Actual subprocess integration tests. Never fake PASS or touch real market data."""
import hashlib,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_anti_stall_v2_1 import Incident,sha_file,invoke,load_state,save_state,add_event
from qros_continuation_engine_v2_3 import run,checkpoint_read

AUTH={'repo':'owner/qros','branch':'research/frozen','base_commit':'a'*40}
FIRE={'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False}

class ExecutableContinuation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def job(self,name,code,depends=(),second=None,expected_output=None):
        work=self.root/name;work.mkdir();src=work/'input.bin';src.write_bytes(b'EXACT FROZEN SOURCE '+name.encode())
        outputs=[{'path':'result.bin','bytes':len(expected_output) if expected_output is not None else None,
                  'sha256':hashlib.sha256(expected_output).hexdigest() if expected_output is not None else None}]
        routes=[{'name':'primary','argv':[sys.executable,'-c',code]}]
        if second is not None:routes.append({'name':'independent_equivalent','argv':[sys.executable,'-c',second]})
        plan={'schema':'QROS_ANTI_STALL_PLAN_V2_1','lane_id':'ONE_PREREGISTERED_CAUSAL_SCOPE',
              'authority':AUTH,'scientific_firewalls':FIRE,
              'stages':[{'id':'STEP_ONE','kind':'local','timeout_seconds':4,
              'inputs':[{'path':'input.bin','bytes':src.stat().st_size,'sha256':sha_file(src)}],
              'outputs':outputs,'routes':routes}]}
        path=work/'PLAN.json';path.write_text(json.dumps(plan,sort_keys=True))
        return {'id':name,'work':str(work),'plan':str(path),'plan_sha256':sha_file(path),
                'kind':'local','hard_route_seconds':20,'max_distinct_routes':len(routes),'depends_on':list(depends)}
    def queue(self,jobs):
        q={'schema':'QROS_BOUNDED_CONTINUATION_QUEUE_V2_2','authority':AUTH,'control_root':str(self.root/'control'),'jobs':jobs}
        path=self.root/'Q.json';path.write_text(json.dumps(q,sort_keys=True));return path,sha_file(path)
    def test_real_three_dependency_steps_in_one_invocation(self):
        jobs=[self.job(x,"open('result.bin','wb').write(b'PROOF');open('executed.marker','x').write('once')",depends=([prev] if i else []))
              for i,(x,prev) in enumerate([('A',None),('B','A'),('C','B')])]
        p,h=self.queue(jobs);out=run(p,h,30,5)
        self.assertEqual(out['status'],'ALL_JOBS_VERIFIED_PASS')
        self.assertEqual(out['actually_executed_jobs'],['A','B','C'])
        self.assertEqual(out['completed_jobs'],['A','B','C'])
        self.assertEqual(run(p,h,30,5)['actually_executed_jobs'],[])
        self.assertTrue(all((self.root/x/'executed.marker').read_text()=='once' for x in ('A','B','C')))
    def test_resume_at_exact_byte_checkpoint(self):
        js=[self.job('A',"open('result.bin','wb').write(b'a')"),self.job('B',"open('result.bin','wb').write(b'b')",depends=['A'])]
        q,h=self.queue(js);r=run(q,h,30,1);self.assertEqual(r['actually_executed_jobs'],['A'])
        before=sha_file(self.root/'A'/'result.bin')
        r2=run(q,h,30,3);self.assertEqual(r2['actually_executed_jobs'],['B'])
        self.assertEqual(sha_file(self.root/'A'/'result.bin'),before)
        self.assertEqual(r2['status'],'ALL_JOBS_VERIFIED_PASS')
    def test_failed_route_automatically_switches_and_advances(self):
        bad=self.job('A',"raise SystemExit(49)",second="open('result.bin','wb').write(b'ok')")
        dep=self.job('B',"open('result.bin','wb').write(b'next')",depends=['A'])
        q,h=self.queue([bad,dep]);o=run(q,h,30,3)
        self.assertEqual(o['actually_executed_jobs'],['A','B'])
        self.assertEqual(load_state(self.root/'A')['stages'][0]['attempted_routes'],['primary','independent_equivalent'])
    def test_critical_path_failure_runs_independent_without_false_pass(self):
        bad=self.job('BAD',"raise SystemExit(9)")
        dep=self.job('DEPENDENT',"open('result.bin','wb').write(b'must not happen')",depends=['BAD'])
        safe=self.job('INDEPENDENT',"open('result.bin','wb').write(b'non economic')")
        q,h=self.queue([bad,dep,safe]);x=run(q,h,30,5)
        self.assertEqual(x['actually_executed_jobs'],['INDEPENDENT'])
        self.assertEqual(x['status'],'SAFE_DEFER_NO_ELIGIBLE_STAGE')
        self.assertFalse((self.root/'DEPENDENT'/'result.bin').exists())
        self.assertEqual(load_state(self.root/'BAD')['stages'][0]['status'],'HALTED')
    def test_tampered_closed_output_fails_closed_without_reexecution(self):
        j=self.job('A',"open('result.bin','wb').write(b'correct')")
        q,h=self.queue([j]);self.assertEqual(run(q,h,30,2)['status'],'ALL_JOBS_VERIFIED_PASS')
        (self.root/'A'/'result.bin').write_bytes(b'CORRUPT')
        with self.assertRaisesRegex(Incident,'ARTIFACT_HASH_DRIFT|ARTIFACT_SIZE_DRIFT'):run(q,h,30,2)
    def test_mutated_queue_pin_fails_before_worker(self):
        j=self.job('A',"open('result.bin','wb').write(b'bad')")
        q,h=self.queue([j]);obj=json.loads(q.read_text());obj['authority']['base_commit']='b'*40;q.write_text(json.dumps(obj))
        with self.assertRaisesRegex(Incident,'QUEUE_EXTERNAL_SHA_DRIFT'):run(q,h,30,3)
        self.assertFalse((self.root/'A'/'result.bin').exists())
    def test_verified_original_pinned_crash_recovery_no_second_execution(self):
        expected=b'EXACT OLD RESULT'
        j=self.job('A',"raise SystemExit(88)",expected_output=expected)
        q,h=self.queue([j]);invoke(j['work'],j['plan'],j['plan_sha256'],'init')
        s=load_state(self.root/'A');s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['primary']
        add_event(s,'START','STEP_ONE',route='primary');save_state(self.root/'A',s)
        (self.root/'A'/'result.bin').write_bytes(expected)
        out=run(q,h,30,3)
        self.assertEqual(out['status'],'ALL_JOBS_VERIFIED_PASS');self.assertEqual(out['actually_executed_jobs'],[])
        self.assertEqual(out['recovery'][0]['status'],'INDEPENDENTLY_PREPINNED_RECOVERED')
    def test_unpinned_interrupted_never_reruns_or_promotes(self):
        j=self.job('A',"open('result.bin','wb').write(b'NEVER')")
        q,h=self.queue([j]);invoke(j['work'],j['plan'],j['plan_sha256'],'init')
        s=load_state(self.root/'A');s['stages'][0]['status']='RUNNING';s['stages'][0]['attempted_routes']=['primary']
        add_event(s,'START','STEP_ONE',route='primary');save_state(self.root/'A',s)
        out=run(q,h,30,3)
        self.assertEqual(out['status'],'SAFE_DEFER_NO_ELIGIBLE_STAGE')
        self.assertFalse((self.root/'A'/'result.bin').exists())
        self.assertEqual(out['recovery'][0]['status'],'INTERRUPTED_UNPINNED_OUTPUTS_NO_RERUN')
    def test_existing_v21_pass_reconciled_without_rerun(self):
        j=self.job('A',"open('result.bin','wb').write(b'already done')")
        q,h=self.queue([j]);invoke(j['work'],j['plan'],j['plan_sha256'],'init')
        out=invoke(j['work'],j['plan'],j['plan_sha256'],'run')
        self.assertEqual(out['status'],'ONE_STAGE_PASS')
        x=run(q,h,30,3)
        self.assertEqual(x['status'],'ALL_JOBS_VERIFIED_PASS')
        self.assertEqual(x['actually_executed_jobs'],[])
        self.assertEqual((self.root/'A'/'result.bin').read_bytes(),b'already done')
    def test_existing_pass_input_tamper_blocks_any_new_execution(self):
        js=[self.job('A',"open('result.bin','wb').write(b'ok')"),
            self.job('B',"open('result.bin','wb').write(b'NEVER')",depends=['A'])]
        q,h=self.queue(js);out=run(q,h,30,1)
        self.assertEqual(out['actually_executed_jobs'],['A'])
        (self.root/'A'/'input.bin').write_bytes(b'CHANGED INPUT')
        with self.assertRaisesRegex(Incident,'ARTIFACT_HASH_DRIFT|ARTIFACT_SIZE_DRIFT'):run(q,h,30,2)
        self.assertFalse((self.root/'B'/'result.bin').exists())
    def test_bad_engine_checkpoint_hash_fails_closed(self):
        j=self.job('A',"open('result.bin','wb').write(b'ok')")
        q,h=self.queue([j]);run(q,h,30,2)
        cp=self.root/'control'/'QROS_CONTINUATION_ENGINE_V2_3_CHECKPOINT.json'
        obj=json.loads(cp.read_text());obj['completed_jobs']=[];cp.write_text(json.dumps(obj))
        with self.assertRaisesRegex(Incident,'ENGINE_CHECKPOINT_HASH_DRIFT'):run(q,h,30,2)

if __name__=='__main__':unittest.main(verbosity=2)
