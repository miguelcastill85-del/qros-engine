#!/usr/bin/env python3
"""TEST_ONLY adversarial regression suite; no market data or scientific promotion."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MODULE = os.environ.get('QROS_TEST_SUPERVISOR', 'qros_heavy_job_supervisor_v3')
s = importlib.import_module(MODULE)


class SupervisorRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = {'schema': 'QROS_HEAVY_JOB_SPEC_1.0', 'job_id': 'synthetic',
                     'command': [sys.executable, '-c', 'pass'], 'max_attempts': 1,
                     'max_runtime_seconds': 0.3, 'max_log_bytes': 4096,
                     'expected_receipt': {'status': 'PASS'}}
        self.spec_path = self.root / 'spec.json'
        self.spec_path.write_text(json.dumps(self.spec))
        self.job = self.root / 'jobs' / 'synthetic'
        self.job.mkdir(parents=True)

    def receipt(self, directory):
        directory.mkdir(exist_ok=True)
        payload = b'TEST_ONLY_EXACT_OUTPUT\n'
        (directory / 'artifact.bin').write_bytes(payload)
        rec = {'status': 'PASS', 'artifacts': [{'path': 'artifact.bin',
               'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]}
        s.atomic_write_json(directory / 'worker_receipt.json', rec)
        return rec

    def call(self):
        return s.controller(Path(s.__file__), self.spec_path, self.root / 'jobs', 0)

    def test_done_rejects_changed_spec(self):
        done = self.job / 'done'
        self.receipt(done)
        s.atomic_write_json(done / 'supervisor_receipt.json', {
            'job_id': 'synthetic', 'spec_sha256': '0' * 64,
            'worker_receipt_sha256': s.sha256_file(done / 'worker_receipt.json')})
        self.assertEqual(self.call()['state'], 'FAIL')

    def test_done_requires_supervisor_provenance(self):
        self.receipt(self.job / 'done')
        self.assertEqual(self.call()['state'], 'FAIL')

    def test_done_rejects_rewritten_receipt(self):
        done = self.job / 'done'
        self.receipt(done)
        s.atomic_write_json(done / 'supervisor_receipt.json', {
            'job_id': 'synthetic', 'spec_sha256': s.validate_job_spec(self.spec),
            'worker_receipt_sha256': '0' * 64})
        self.assertEqual(self.call()['state'], 'FAIL')

    def test_artifact_symlink_is_rejected(self):
        attempt = self.job / 'attempt_01'
        self.receipt(attempt)
        external = self.root / 'outside.bin'
        (attempt / 'artifact.bin').replace(external)
        (attempt / 'artifact.bin').symlink_to(external)
        self.assertFalse(s.validate_receipt(attempt, self.spec)[0])

    def test_foreign_runtime_cannot_trigger_retry(self):
        self.spec['max_attempts'] = 2
        self.spec_path.write_text(json.dumps(self.spec))
        claim = s.make_claim(self.job, self.spec, s.validate_job_spec(self.spec), 1)
        attempt = self.job / claim['attempt_dir']
        s.atomic_write_json(attempt / 'identity.json', {
            'claim_token': claim['claim_token'], 'command_sha256': claim['command_sha256'],
            'bootstrap_pid': 999999999, 'bootstrap_birth': 'linux:foreign-boot:1'})
        with patch.object(s, 'spawn_bootstrap', return_value=123) as launch:
            result = self.call()
        self.assertFalse(launch.called, result)
        self.assertEqual(result['state'], 'FAIL')

    def test_unknown_launch_is_not_death_proof(self):
        self.spec['max_attempts'] = 2
        self.spec_path.write_text(json.dumps(self.spec))
        claim = s.make_claim(self.job, self.spec, s.validate_job_spec(self.spec), 1)
        claim['created_at'] = '2000-01-01T00:00:00Z'
        s.atomic_write_json(self.job / 'current_claim.json', claim)
        with patch.object(s, 'spawn_bootstrap', return_value=123) as launch:
            result = self.call()
        self.assertFalse(launch.called, result)

    def test_hung_worker_has_deadline(self):
        self.spec['command'] = [sys.executable, '-c', 'import time; time.sleep(60)']
        claim = s.make_claim(self.job, self.spec, s.validate_job_spec(self.spec), 1)
        proc = subprocess.Popen([sys.executable, s.__file__, '--bootstrap',
            '--job-dir', str(self.job), '--claim-token', claim['claim_token']],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.fail('worker still alive beyond the configured deadline')
            ex = s.load_json(self.job / 'attempt_01' / 'exit.json')
            self.assertEqual(ex['reason'], 'WORKER_RUNTIME_LIMIT')
            self.assertNotEqual(ex['returncode'], 0)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=2)

    def test_log_flood_is_bounded_and_fails(self):
        attempt = self.job / 'attempt_01'
        attempt.mkdir()
        rc, reason = s.run_bounded_worker([sys.executable, '-c',
            'import os; os.write(1,b"x"*1000000)'], attempt, self.spec)
        self.assertEqual(reason, 'WORKER_LOG_LIMIT')
        self.assertNotEqual(rc, 0)
        self.assertLessEqual(sum((attempt / name).stat().st_size for name in
            ('worker.stdout.txt','worker.stderr.txt')), self.spec['max_log_bytes'])

    def test_descendant_holding_pipes_cannot_freeze_bootstrap(self):
        attempt = self.job / 'attempt_01'
        attempt.mkdir()
        rc, reason = s.run_bounded_worker([sys.executable, '-c',
            'import os,time; pid=os.fork(); time.sleep(60) if pid==0 else None'],
            attempt, self.spec)
        self.assertEqual((rc, reason), (124, 'WORKER_RUNTIME_LIMIT'))

    def test_matching_done_reuses_without_launch(self):
        done = self.job / 'done'
        self.receipt(done)
        s.atomic_write_json(done / 'supervisor_receipt.json', {
            'job_id': 'synthetic', 'spec_sha256': s.validate_job_spec(self.spec),
            'worker_receipt_sha256': s.sha256_file(done / 'worker_receipt.json')})
        with patch.object(s, 'spawn_bootstrap') as launch:
            self.assertEqual(self.call()['action'], 'REUSE_VALID_DONE')
        self.assertFalse(launch.called)

    def test_lock_contention_and_release(self):
        first = s.acquire_controller_lock(self.job)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(s.acquire_controller_lock(self.job))
        finally:
            s.release_controller_lock(first)
        second = s.acquire_controller_lock(self.job)
        self.assertIsNotNone(second)
        s.release_controller_lock(second)

    def test_lock_released_by_kernel_after_owner_death(self):
        ready = self.root / 'ready'
        code = ('import pathlib,sys,time;sys.path.insert(0,sys.argv[1]);'
                'import qros_heavy_job_supervisor_v3 as s;'
                'fd=s.acquire_controller_lock(pathlib.Path(sys.argv[2]));'
                'pathlib.Path(sys.argv[3]).write_text(str(fd));time.sleep(60)')
        p = subprocess.Popen([sys.executable, '-c', code, str(Path(s.__file__).parent),
                              str(self.job), str(ready)])
        try:
            deadline = time.monotonic() + 2
            while not ready.exists() and time.monotonic() < deadline:time.sleep(.01)
            self.assertTrue(ready.exists())
            self.assertIsNone(s.acquire_controller_lock(self.job))
        finally:
            p.kill(); p.wait(timeout=2)
        recovered = s.acquire_controller_lock(self.job)
        self.assertIsNotNone(recovered)
        s.release_controller_lock(recovered)

    def test_nonfinite_budgets_are_rejected(self):
        for value in (None, 0, -1, True, float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                s.validate_job_spec(dict(self.spec,max_runtime_seconds=value))

    def test_worker_secrets_not_inherited(self):
        with patch.dict(os.environ, {'QROS_TEST_SECRET':'TEST_ONLY'}):
            self.assertNotIn('QROS_TEST_SECRET', s.worker_env())

    def test_unknown_birth_is_not_dead(self):
        self.assertEqual(s.process_status(999999999, None), 'UNKNOWN')

    def test_timeout_cannot_promote_valid_early_output(self):
        claim=s.make_claim(self.job,self.spec,s.validate_job_spec(self.spec),1)
        attempt=self.job/claim['attempt_dir']
        self.receipt(attempt)
        birth=s.process_birth(os.getpid())
        s.atomic_write_json(attempt/'identity.json',{
            'claim_token':claim['claim_token'],'command_sha256':claim['command_sha256'],
            'bootstrap_pid':999999999,'bootstrap_birth':birth})
        s.atomic_write_json(attempt/'exit.json',{
            'claim_token':claim['claim_token'],'returncode':124,'reason':'WORKER_RUNTIME_LIMIT'})
        self.assertEqual(self.call()['state'],'FAIL')
        self.assertFalse((self.job/'done').exists())

    def test_symlink_in_parent_of_artifact_is_rejected(self):
        attempt=self.job/'attempt_01'
        rec=self.receipt(attempt)
        external=self.root/'external'
        external.mkdir()
        (attempt/'artifact.bin').replace(external/'artifact.bin')
        (attempt/'sub').symlink_to(external,target_is_directory=True)
        rec['artifacts'][0]['path']='sub/artifact.bin'
        s.atomic_write_json(attempt/'worker_receipt.json',rec)
        self.assertFalse(s.validate_receipt(attempt,self.spec)[0])

    def test_malformed_artifact_fails_closed(self):
        attempt = self.job / 'attempt_01'
        attempt.mkdir()
        s.atomic_write_json(attempt/'worker_receipt.json', {'status':'PASS','artifacts':[None]})
        self.assertFalse(s.validate_receipt(attempt,self.spec)[0])

    def test_duplicate_bootstrap_launches_one_worker(self):
        marker=self.root/'starts'
        self.spec['command']=[sys.executable,'-c',
            'import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);'
            'p.open("a").write("start\\n");time.sleep(.4)',str(marker)]
        self.spec['max_runtime_seconds']=2
        claim=s.make_claim(self.job,self.spec,s.validate_job_spec(self.spec),1)
        argv=[sys.executable,s.__file__,'--bootstrap','--job-dir',str(self.job),
              '--claim-token',claim['claim_token']]
        p=subprocess.Popen(argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+2
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(marker.exists())
            second=subprocess.run(argv,timeout=2,capture_output=True)
            self.assertEqual(second.returncode,96)
            self.assertEqual(p.wait(timeout=2),0)
            third=subprocess.run(argv,timeout=2,capture_output=True)
            self.assertEqual(third.returncode,96)
            self.assertEqual(marker.read_text().splitlines(),['start'])
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=2)

    def test_full_lifecycle_output_matches_baseline(self):
        # Same input-free TEST_ONLY workload under both controllers. This proves
        # supervisor transparency, not trading-engine or real market parity.
        import qros_heavy_job_supervisor_v1 as old
        cmd=[sys.executable,'-c',
             'import pathlib,json,hashlib,sys; p=pathlib.Path(sys.argv[1]);'
             'b=b"TEST_ONLY_EXACT_OUTPUT\\n"; (p/"artifact.bin").write_bytes(b);'
             '(p/"worker_receipt.json").write_text(json.dumps({"status":"PASS",'
             '"artifacts":[{"path":"artifact.bin","bytes":len(b),'
             '"sha256":hashlib.sha256(b).hexdigest()}]},sort_keys=True))',
             '{attempt_dir}']
        spec=dict(self.spec,command=cmd,max_runtime_seconds=2)
        self.spec_path.write_text(json.dumps(spec))
        hashes=[]
        for module in (old,s):
            root=self.root/module.__name__
            deadline=time.monotonic()+4
            while True:
                result=module.controller(Path(module.__file__),self.spec_path,root,1)
                if result['state']=='PASS':break
                self.assertNotEqual(result['state'],'FAIL',result)
                self.assertLess(time.monotonic(),deadline,result)
                time.sleep(.02)
            done=root/spec['job_id']/'done'
            hashes.append([s.sha256_file(done/name) for name in ('artifact.bin','worker_receipt.json')])
            self.assertEqual(module.controller(Path(module.__file__),self.spec_path,root,1)['action'], 'REUSE_VALID_DONE')
        self.assertEqual(hashes[0],hashes[1])



if __name__ == '__main__':
    unittest.main(verbosity=2)
