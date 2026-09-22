import json
import datetime as dt
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest

from qros_fenced_heavy_job_supervisor_v2 import delegate_once
import qros_fenced_runtime_lease_guard_v1 as fence


class BoundedControlTests(unittest.TestCase):
    def call(self, code, timeout=.2):
        with tempfile.TemporaryDirectory() as tmp:
            return delegate_once([sys.executable,'-c',code],Path(tmp),timeout)

    def test_hung_control_preserves_unknown_outcome(self):
        start=time.monotonic()
        result=self.call('import time; time.sleep(60)')
        self.assertEqual(result['action'],'CONTROL_OUTCOME_UNKNOWN_NO_RELAUNCH')
        self.assertFalse(result['worker_death_proven'])
        self.assertLess(time.monotonic()-start,2)

    def test_control_output_flood_is_bounded(self):
        result=self.call('import os;os.write(1,b"x"*1000000)')
        self.assertEqual(result['reason'],'WORKER_LOG_LIMIT')

    def test_valid_running_response(self):
        result=self.call('print(\'{"state":"RUNNING","action":"ADOPT_LIVE_PROCESS"}\')')
        self.assertEqual(result['state'],'RUNNING')

    def test_invalid_response_cannot_trigger_retry(self):
        result=self.call('print("invalid")')
        self.assertEqual(result['action'],'CONTROL_OUTCOME_UNKNOWN_NO_RELAUNCH')

    def test_failed_exit_cannot_claim_pass(self):
        result=self.call('print(\'{"state":"PASS"}\');raise SystemExit(1)')
        self.assertEqual(result['reason'],'DELEGATE_OUTPUT_INVALID')

    def test_cli_launch_and_reuse_with_bound_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);now=dt.datetime.now(dt.timezone.utc)
            lease=fence.new_lease('test_fenced',0,1,'TEST_ONLY',
                now.isoformat(),(now+dt.timedelta(hours=1)).isoformat())
            expected={'status':'PASS','structural_group_index':0,
                **{k:lease[k] for k in ('lease_epoch','lease_id','fence_token')}}
            spec={'schema':'QROS_HEAVY_JOB_SPEC_1.0','job_id':'test_fenced',
                'max_attempts':1,'max_runtime_seconds':2,'max_log_bytes':4096,
                'artifacts_required':False,'expected_receipt':expected,
                'command':[sys.executable,'-c',
                    'import pathlib,sys;pathlib.Path(sys.argv[1]).write_text(sys.argv[2])',
                    '{receipt}',json.dumps(expected)]}
            (root/'spec.json').write_text(json.dumps(spec));(root/'lease.json').write_text(json.dumps(lease))
            argv=[sys.executable,str(Path(__file__).with_name('qros_fenced_heavy_job_supervisor_v2.py')),
                '--job-spec',str(root/'spec.json'),'--lease',str(root/'lease.json'),
                '--work-root',str(root/'jobs')]
            deadline=time.monotonic()+5
            while True:
                p=subprocess.run(argv,capture_output=True,text=True,timeout=5)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                result=json.loads(p.stdout)
                if result['state']=='PASS':break
                self.assertLess(time.monotonic(),deadline)
                time.sleep(.02)
            reused=subprocess.run(argv,capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(reused.stdout)['action'],'REUSE_VALID_DONE')
            self.assertFalse((root/'jobs'/'test_fenced'/'attempt_02').exists())


if __name__ == '__main__':unittest.main(verbosity=2)
