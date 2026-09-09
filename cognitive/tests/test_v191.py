"""V191 observed-contract regressions, not scientific evidence or live authority."""
import json
import shutil
import sqlite3
import threading
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from cognitive import kernel as k
from cognitive.shadow import run as shadow

FIXTURE=Path(__file__).parent/'fixtures/v191'
ANCHOR='5afce6279994b8625bd79fb2d5d13924e3c561e7'

class V191Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);shutil.copytree(FIXTURE,self.root,dirs_exist_ok=True)
        self.anchor=ANCHOR

    def mutate(self,role,fn):
        path=self.root/v.PATHS[role];doc=json.loads(path.read_bytes());fn(doc);b=v.canonical(doc);path.write_bytes(b)
        mf=self.root/v.MANIFEST;m=json.loads(mf.read_bytes());m['single_active_authority'][role]['git_blob_sha1']=v.git_blob(b)
        b=v.canonical(m);mf.write_bytes(b);self.anchor=v.git_blob(b)

    def queue(self):return v.inspect_active_queue(v.observe_authority(v.Snapshot(self.root),self.anchor))

    def test_observed_shadow_preserves_stage_subtask_and_no_dispatch(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=shadow(self.root,self.anchor)
        self.assertEqual(result['control_bootstrap']['status'],'PASS')
        self.assertEqual(result['queue']['next_item_hint'],'G30-OBS-STAGE-B-F03-RECONFIRM')
        self.assertEqual(result['queue']['stage_hint'],'G30-OBS-STAGE-B-2020_2021')
        self.assertEqual(result['queue']['input_population'],33094)
        self.assertFalse(result['dispatch_authorized'])
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_missing_delegation_remains_rejected(self):
        self.mutate('head',lambda d:d.pop('scientific_execution_authorization_source'))
        with self.assertRaisesRegex(v.ContractError,'AUTHORIZATION_SOURCE_MISMATCH'):self.queue()

    def test_representatives_cannot_replace_full_population(self):
        self.mutate('state',lambda d:d.update(input_population=2471))
        with self.assertRaisesRegex(v.ContractError,'V191_POPULATION_MISMATCH'):self.queue()

    def test_changed_frontier_count_rejected(self):
        self.mutate('run_queue',lambda d:d['queue'][3].update(input_population=1092))
        with self.assertRaisesRegex(v.ContractError,'V191_POPULATION_MISMATCH'):self.queue()

    def test_f13_recovery_guard_rejected(self):
        self.mutate('run_queue',lambda d:d['guards'].update(f13_recovery_authorized=True))
        with self.assertRaisesRegex(v.ContractError,'QUEUE_GUARD_MISMATCH'):self.queue()

    def test_holdout_open_guard_rejected(self):
        self.mutate('run_queue',lambda d:d['guards'].update(stage_c_2022_2024_strategy_pnl_authorized=True))
        with self.assertRaisesRegex(v.ContractError,'QUEUE_GUARD_MISMATCH'):self.queue()

    def test_exposed_history_cannot_be_relabelled_clean(self):
        self.mutate('head',lambda d:d['scientific_state'].update(historical_validation_class='CLEAN_HOLDOUT'))
        with self.assertRaisesRegex(v.ContractError,'V191_EXPOSURE_MISMATCH'):self.queue()

    def test_unregistered_queue_progress_fails_closed(self):
        self.mutate('run_queue',lambda d:d['queue'][1].update(status='COMPLETE'))
        with self.assertRaisesRegex(v.ContractError,'V191_QUEUE_CONTRACT_MISMATCH'):self.queue()

    def test_duplicate_frontier_cannot_drop_population(self):
        self.mutate('run_queue',lambda d:d['queue'].__setitem__(2,d['queue'][1]))
        with self.assertRaisesRegex(v.ContractError,'V191_QUEUE_CONTRACT_MISMATCH'):self.queue()

    def test_legacy_mutation_rejected(self):
        (self.root/'control/RUN_QUEUE_v3.json').write_text('{}')
        with self.assertRaisesRegex(v.ContractError,'LEGACY_BLOB_MISMATCH'):shadow(self.root,self.anchor)

    def test_registry_mutation_rejected(self):
        (self.root/'control/QROS_ACTIVE_HASH_REGISTRY_V191_v1.json').write_text('{}')
        with self.assertRaisesRegex(v.ContractError,'REGISTRY_BLOB_MISMATCH'):shadow(self.root,self.anchor)

    def test_inherited_registry_mutation_rejected(self):
        (self.root/'control/QROS_ACTIVE_HASH_REGISTRY_V190_v1.json').write_text('{}')
        with self.assertRaisesRegex(v.ContractError,'INHERITED_REGISTRY_BLOB_MISMATCH'):shadow(self.root,self.anchor)

    def test_v191_kernel_runs_and_resumes_without_duplicate_effects(self):
        (self.root/'cognitive').mkdir()
        plan=json.loads((Path(__file__).parents[1]/'kernel_specs/EXAMPLE_PLAN.json').read_bytes())
        sha=v.sha256(v.canonical(plan))
        first=k.Kernel(self.root,plan,sha,self.anchor,'v191_test')
        try:
            first.run();checkpoint=(first.directory/'checkpoint.json').read_bytes()
        finally:first.close()
        second=k.Kernel(self.root,plan,sha,self.anchor,'v191_test')
        try:
            result=second.run();self.assertEqual(result['newly_completed'],0)
            self.assertEqual(checkpoint,(second.directory/'checkpoint.json').read_bytes())
        finally:second.close()

    def test_real_sqlite_startup_lock_is_retried_then_succeeds(self):
        path=self.root/'lock.sqlite';owner=sqlite3.connect(path,isolation_level=None,check_same_thread=False)
        owner.execute('CREATE TABLE test(x)');owner.execute('BEGIN IMMEDIATE')
        timer=threading.Timer(0.15,owner.commit);timer.start()
        try:
            db=k.open_store(path)
            try:self.assertEqual(db.execute('PRAGMA journal_mode').fetchone(),('wal',))
            finally:db.close()
        finally:timer.join();owner.close()

    def test_persistent_sqlite_startup_lock_is_bounded(self):
        path=self.root/'locked.sqlite';owner=sqlite3.connect(path,isolation_level=None)
        owner.execute('CREATE TABLE test(x)');owner.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaisesRegex(v.ContractError,'STORE_STARTUP_BUSY'):k.open_store(path,0.05)
        finally:owner.rollback();owner.close()

    def test_corrupt_sqlite_is_not_retried_as_contention(self):
        path=self.root/'bad.sqlite';path.write_bytes(b'invalid sqlite database')
        with self.assertRaises(sqlite3.DatabaseError):k.open_store(path)

    def test_kernel_cannot_skip_declared_legacy_validation(self):
        (self.root/'cognitive').mkdir()
        (self.root/'control/RUN_QUEUE_v3.json').write_text('{}')
        plan=json.loads((Path(__file__).parents[1]/'kernel_specs/EXAMPLE_PLAN.json').read_bytes())
        with self.assertRaisesRegex(v.ContractError,'LEGACY_BLOB_MISMATCH'):
            k.Kernel(self.root,plan,v.sha256(v.canonical(plan)),self.anchor,'bad_legacy')

if __name__=='__main__':unittest.main()
