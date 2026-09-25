"""v2.4 independent validation: genuine git origin and subprocess workers, no broker data."""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

SCRIPTS=pathlib.Path(__file__).resolve().parents[1]/'scripts'
EXAMPLES=pathlib.Path(__file__).resolve().parents[1]/'examples'
sys.path.insert(0,str(SCRIPTS));sys.path.insert(0,str(EXAMPLES))
from qros_anti_stall_v2_1 import Incident, sha_file
from qros_continuation_service_v2_4 import (run_service,verify_live_authority,git_blob,
    origin_matches,safe_repo_path)
from qros_v23_actual_execution_canary import fixture

AUTH={'repo':'fixture/not-a-live-repository','branch':'synthetic-only','base_commit':'1'*40}
POINTER='control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json'


def git(cwd,*args):
    p=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,text=True,timeout=10)
    if p.returncode:raise RuntimeError(f'{args} failed: {p.stderr[:300]}')
    return p.stdout.strip()


class LocalOriginFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.tmp.name)
        self.bare=self.base/'origin.git';self.work=self.base/'checkout'
        subprocess.run(['git','init','--bare','-q',str(self.bare)],check=True,timeout=10)
        subprocess.run(['git','init','-q',str(self.work)],check=True,timeout=10)
        git(self.work,'config','user.name','QROS synthetic');git(self.work,'config','user.email','fixture@invalid.example')
        git(self.work,'remote','add','origin',str(self.bare))
        self.target='control/EXACT_HANDOFF.json';self.anchor='control/EXACT_ANCHOR.json'
        (self.work/'control').mkdir()
        (self.work/self.anchor).write_text('{"schema":"SYNTHETIC_ANCHOR"}\n')
        self.anchor_sha=git_blob((self.work/self.anchor).read_bytes())
        (self.work/self.target).write_text(json.dumps({'authority':{'branch':AUTH['branch']},'schema':'SYNTHETIC_HANDOFF'})+'\n')
        self.target_sha=git_blob((self.work/self.target).read_bytes())
        self.ptr={'branch':AUTH['branch'],'holdout_open':False,'ga2_open':False,
                  'Gate_A_approved':False,'target':self.target,'target_git_blob_sha1':self.target_sha,
                  'last_closed_remote_anchor_path':self.anchor,
                  'last_closed_remote_anchor_blob_sha1':self.anchor_sha}
        self._commit_pointer()
        git(self.work,'checkout','-b',AUTH['branch']);git(self.work,'push','-q','origin',AUTH['branch'])
        self.commit=git(self.work,'rev-parse','HEAD');self.authority={**AUTH,'base_commit':self.commit}
        self.q={'authority':self.authority}
    def tearDown(self):self.tmp.cleanup()
    def _commit_pointer(self):
        (self.work/POINTER).write_text(json.dumps(self.ptr,sort_keys=True)+'\n')
        git(self.work,'add','.');git(self.work,'commit','-q','-m','frozen synthetic authority')
        self.pointer_sha=git_blob((self.work/POINTER).read_bytes())
    def advance_pointer(self):
        self._commit_pointer();git(self.work,'push','-q','origin',AUTH['branch'])
    def verify(self,expected=None):
        return verify_live_authority(str(self.work),self.q,expected or self.pointer_sha,POINTER,fixture=True)
    def test_real_git_fetch_and_target_and_anchor_sha(self):
        r=self.verify()
        self.assertEqual(r['pointer_sha1'],self.pointer_sha)
        self.assertEqual(r['handoff_sha1'],self.target_sha)
        self.assertEqual(r['anchor_sha1'],self.anchor_sha)
    def test_fresh_live_pointer_change_causes_fail_closed(self):
        prev=self.pointer_sha;self.ptr['last_closed']='new independent authority';self.advance_pointer()
        with self.assertRaisesRegex(Incident,'LIVE_SCIENTIFIC_POINTER_ADVANCED'):
            self.verify(prev)
    def test_target_byte_change_without_pointer_cannot_pass(self):
        (self.work/self.target).write_text('{"authority":{"branch":"synthetic-only"},"tampered":true}\n')
        git(self.work,'add','.');git(self.work,'commit','-q','-m','target tamper')
        git(self.work,'push','-q','origin',AUTH['branch'])
        with self.assertRaisesRegex(Incident,'LIVE_HANDOFF_TARGET_BLOB_MISMATCH'):
            self.verify()
    def test_reopened_holdout_rejected_even_if_pointer_newly_pinned(self):
        self.ptr['holdout_open']=True;self.advance_pointer()
        with self.assertRaisesRegex(Incident,'SCIENTIFIC_FIREWALL'):
            self.verify()
    def test_origin_mismatch_fails_before_fetch(self):
        with self.assertRaisesRegex(Incident,'AUTHORITY_ORIGIN_REPOSITORY_MISMATCH'):
            verify_live_authority(str(self.work),self.q,self.pointer_sha,POINTER,fixture=False)
    def test_wrong_ancestry_fails_before_execution(self):
        self.q['authority']['base_commit']='f'*40
        with self.assertRaisesRegex(Incident,'AUTHORITY_GIT_COMMAND_FAILED'):
            self.verify()


class ServiceIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_real_three_processes_across_multiple_cycles_and_exact_resume(self):
        queue,sha=fixture(self.root)
        result=run_service(str(queue),sha,None,None,None,max_cycles=5,wall_seconds=85,
                           cycle_seconds=24,stages_per_cycle=1,synthetic_fixture=True)
        self.assertEqual(result['status'],'ALL_VERIFIED_EXECUTION_COMPLETE')
        self.assertEqual(result['cycles'],3)
        self.assertEqual(result['actually_executed_jobs'],['SOURCE_CHECK','REPLAY_PARITY','FREEZE_RECEIPT'])
        self.assertEqual(result['last_cycle']['verified_pending'],{})
        h={k:sha_file(self.root/k/'result.bin') for k in result['actually_executed_jobs']}
        reentry=run_service(str(queue),sha,None,None,None,max_cycles=2,wall_seconds=20,
                            cycle_seconds=15,stages_per_cycle=2,synthetic_fixture=True)
        self.assertEqual(reentry['status'],'ALL_VERIFIED_EXECUTION_COMPLETE')
        self.assertEqual(reentry['actually_executed_jobs'],[])
        self.assertEqual(h,{k:sha_file(self.root/k/'result.bin') for k in h})
    def test_remote_unavailable_never_starts_worker(self):
        queue,sha=fixture(self.root)
        checker=Mock(side_effect=Incident('AUTHORITY_GIT_UNAVAILABLE_OR_TIMEOUT'))
        worker=Mock()
        with self.assertRaisesRegex(Incident,'AUTHORITY_GIT_UNAVAILABLE_OR_TIMEOUT'):
            run_service(str(queue),sha,'/fake','control/pointer.json','a'*40,
                        max_cycles=2,wall_seconds=20,cycle_seconds=15,stages_per_cycle=1,
                        synthetic_fixture=False,execution=worker,authority_checker=checker)
        worker.assert_not_called()
        self.assertFalse((self.root/'SOURCE_CHECK'/'result.bin').exists())

    def test_real_queue_cannot_use_fixture_bypass(self):
        queue,sha=fixture(self.root)
        obj=json.loads(queue.read_text());obj['authority']['repo']='miguelcastill85-del/qros-engine'
        queue.write_text(json.dumps(obj,sort_keys=True));sha=sha_file(queue)
        with self.assertRaisesRegex(Incident,'FIXTURE_MODE_FORBIDDEN'):
            run_service(str(queue),sha,None,None,None,synthetic_fixture=True)
    def test_real_queue_requires_remote_proof_before_any_execution(self):
        queue,sha=fixture(self.root)
        obj=json.loads(queue.read_text());obj['authority']['repo']='miguelcastill85-del/qros-engine'
        queue.write_text(json.dumps(obj,sort_keys=True));sha=sha_file(queue)
        with self.assertRaisesRegex(Incident,'AUTHENTICATED_REMOTE_SOURCE_REQUIRED'):
            run_service(str(queue),sha,None,None,None,synthetic_fixture=False)
        self.assertFalse((self.root/'SOURCE_CHECK'/'result.bin').exists())
    def test_remote_change_after_executing_cycle_blocks_additional_cycles(self):
        queue,sha=fixture(self.root)
        checks=iter([{'pointer_sha1':'a'*40},{'pointer_sha1':'b'*40}]);fake=Mock(side_effect=lambda *a:next(checks))
        with self.assertRaisesRegex(Incident,'REMOTE_AUTHORITY_CHANGED_DURING_EXECUTION'):
            run_service(str(queue),sha,'/fake','control/pointer.json','a'*40,max_cycles=5,
                        wall_seconds=20,cycle_seconds=15,stages_per_cycle=1,
                        synthetic_fixture=False,authority_checker=fake)
        self.assertTrue((self.root/'SOURCE_CHECK'/'result.bin').exists())
        self.assertFalse((self.root/'REPLAY_PARITY'/'result.bin').exists())
        self.assertEqual(fake.call_count,2)
    def test_external_dependency_deferred_not_false_completed(self):
        queue,sha=fixture(self.root)
        obj=json.loads(queue.read_text());obj['jobs'][0]['kind']='external'
        queue.write_text(json.dumps(obj,sort_keys=True));sha=sha_file(queue)
        # Frozen plan still says local -> reject changing queue without changing frozen plan.
        with self.assertRaisesRegex(Incident,'JOB_KIND_DRIFT'):
            run_service(str(queue),sha,None,None,None,synthetic_fixture=True)
    def test_budget_and_no_change_semantics(self):
        queue,sha=fixture(self.root)
        with self.assertRaisesRegex(Incident,'UNSAFE_SERVICE_BUDGET'):
            run_service(str(queue),sha,None,None,None,wall_seconds=9,synthetic_fixture=True)
    def test_frozen_queue_tamper_blocks_worker(self):
        queue,sha=fixture(self.root)
        q=json.loads(queue.read_text());q['jobs'][0]['max_distinct_routes']=2
        queue.write_text(json.dumps(q))
        with self.assertRaisesRegex(Incident,'QUEUE_EXTERNAL_SHA_DRIFT'):
            run_service(str(queue),sha,None,None,None,synthetic_fixture=True)
        self.assertFalse((self.root/'SOURCE_CHECK'/'result.bin').exists())
    def test_path_and_origin_string_safety(self):
        for item in ('../control/ROOT','control/../ROOT','/control/ROOT','C:\\secret','control/x y'):
            with self.assertRaises(Incident):safe_repo_path(item)
        self.assertFalse(origin_matches('https://attacker.invalid/owner/repo.git','owner/repo'))
        self.assertFalse(origin_matches('https://github.com/owner/repo.git?token=abc','owner/repo'))
        self.assertTrue(origin_matches('git@github.com:owner/repo.git','owner/repo'))

if __name__=='__main__':unittest.main(verbosity=2)
