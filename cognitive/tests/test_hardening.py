"""Adversarial regressions for Q01-Q05. Synthetic data, no external dispatch."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cognitive import runtime as v, session, kernel
from cognitive.verify_release import verify
from cognitive.evaluation import BenchmarkLedger
from cognitive.tests.test_kernel import plan
from cognitive.tests import test_runtime as fixtures

ROOT=Path(__file__).resolve().parents[2]

def freeze(root):
    raw=v.canonical({'schema':'QRCEL_SOURCE_AND_ENGINEERING_EVIDENCE_MANIFEST_V1','scientific_authority':False,'files_sha256':{p.relative_to(root).as_posix():v.sha256(p.read_bytes()) for p in root.rglob('*') if p.is_file() and p.name!='COGNITIVE_MANIFEST.json'}})
    (root/'cognitive/COGNITIVE_MANIFEST.json').write_bytes(raw)
    return v.git_blob(raw)

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'cognitive').mkdir()
    def session_package(self):
        for f in ['ACTIVATION.json','COGNITIVE_STATE.json']:shutil.copyfile(ROOT/'cognitive'/f,self.root/'cognitive'/f)
        for f in ['prompts','tests/fixtures/v191']:shutil.copytree(ROOT/'cognitive'/f,self.root/'cognitive'/f)
        return freeze(self.root)
    def kernel(self,run='test',**kw):
        for path in [v.MANIFEST,*v.PATHS.values()]:
            p=self.root/path;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes((fixtures.AUTHORITY_ROOT/path).read_bytes())
        p=plan();obj=kernel.Kernel(self.root,p,v.sha256(v.canonical(p)),fixtures.ANCHOR,run,**kw);self.addCleanup(obj.close);return obj
    def test_q01_unlisted_bytecode_rejected(self):
        (self.root/'cognitive/__init__.py').write_text('');anchor=freeze(self.root)
        p=self.root/'cognitive/__pycache__';p.mkdir();(p/'x.cpython-312.pyc').write_bytes(b'UNTRUSTED')
        with self.assertRaisesRegex(v.ContractError,'RELEASE_UNLISTED_CODE'):verify(self.root,anchor)
    def test_q02_consumes_verified_prompt_bytes(self):
        anchor=self.session_package();p=self.root/'cognitive/prompts/TOOL_POLICY.md';expected=p.read_text()
        def mutate(*a,**kw):
            result=verify(*a,**kw);p.write_text('UNVERIFIED PROMPT');return result
        with patch.object(session,'verify',mutate):r=session.start(self.root,anchor,'synthetic')
        self.assertEqual(next(m['text'] for m in r['modules'] if m['id']=='TOOL_POLICY'),expected)
    def test_q03_coherent_state_rewrite_rejected(self):
        obj=self.kernel();obj.run();raw=v.canonical({'fraction':'999'});sha=v.sha256(raw)
        obj.db.execute('UPDATE completed SET output=?,digest=? WHERE id=?',(raw,sha,'A'))
        previous=None
        for seq,b in obj.db.execute('SELECT seq,payload FROM events ORDER BY seq').fetchall():
            row=v.parse_json(b);row['previous']=previous
            if row['event']['type']=='COMPLETE' and row['event']['task_id']=='A':row['event']['output_sha256']=sha
            data=v.canonical(row);previous=v.sha256(data);obj.db.execute('UPDATE events SET payload=?,digest=? WHERE seq=?',(data,previous,seq))
        with self.assertRaisesRegex(v.ContractError,'PERSISTED_RESULT_SEMANTIC_MISMATCH'):obj.run()
    def test_q04_extreme_exponent_rejected_before_work(self):
        code="import resource; resource.setrlimit(resource.RLIMIT_CPU,(1,1)); resource.setrlimit(resource.RLIMIT_AS,(128*1024*1024,)*2); from cognitive.runtime import rational,ContractError\ntry: rational('1e100000000')\nexcept ContractError as e: print(e.code)"
        p=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1'},stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=4)
        self.assertEqual(p.returncode,0);self.assertIn('DIMENSION_RESOURCE_LIMIT',p.stdout)
    def test_q05_parent_symlink_rejected(self):
        target=self.root/'target';target.mkdir();link=self.root/'link';link.symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(v.ContractError,'BENCHMARK_LEDGER_SYMLINK'):
            db=BenchmarkLedger(link/'ledger.sqlite');db.close()


class ExtendedHardeningTests(unittest.TestCase):
    setUp=HardeningTests.setUp
    session_package=HardeningTests.session_package
    kernel=HardeningTests.kernel
    def test_configuration_swap_cannot_grant_authority(self):
        anchor=self.session_package();p=self.root/'cognitive/ACTIVATION.json'
        def mutate(*a,**kw):
            r=verify(*a,**kw);p.write_bytes(v.canonical({'schema':'QRCEL_SESSION_ACTIVATION_V1','scientific_dispatch':True}));return r
        with patch.object(session,'verify',mutate):r=session.start(self.root,anchor,'synthetic')
        self.assertFalse(r['scientific_dispatch_authorized'])
    def test_external_anchor_detects_valid_but_older_database(self):
        obj=self.kernel();obj.run();anchor=obj.resume_anchor()
        obj.db.execute('DELETE FROM completed');obj.db.execute('DELETE FROM events');obj.expected_resume_anchor=anchor
        with self.assertRaisesRegex(v.ContractError,'STATE_ROLLBACK_DETECTED'):obj.run()
    def test_external_anchor_detects_rewritten_history_with_correct_outputs(self):
        obj=self.kernel();obj.run();obj.expected_resume_anchor=obj.resume_anchor();previous=None
        for seq,b in obj.db.execute('SELECT seq,payload FROM events ORDER BY seq').fetchall():
            row=v.parse_json(b);row['previous']=previous
            if row['event']['type']=='START':row['event']['capability']['observed_at_ns']+=1
            raw=v.canonical(row);previous=v.sha256(raw);obj.db.execute('UPDATE events SET payload=?,digest=? WHERE seq=?',(raw,previous,seq))
        with self.assertRaisesRegex(v.ContractError,'STATE_HISTORY_REWRITTEN'):obj.run()
    def test_external_anchor_survives_legitimate_resume(self):
        obj=self.kernel();first=obj.run();anchor=obj.resume_anchor();other=self.kernel(expected_resume_anchor=anchor)
        r=other.run();self.assertEqual(r['newly_completed'],0);self.assertEqual(r['checkpoint_sha256'],first['checkpoint_sha256']);self.assertEqual(r['history_authentication'],'EXTERNAL_PREFIX_VERIFIED')
    def test_resume_without_anchor_does_not_claim_authenticated_history(self):
        obj=self.kernel();self.assertEqual(obj.run()['history_authentication'],'UNATTESTED_LOCAL_HISTORY')
    def test_rational_limits_and_exact_normal_values(self):
        from fractions import Fraction
        for value in ['3','3/2',' 1.5 ','.25','1e8','1e-8','1e256','1e-256']:
            self.assertEqual(v.rational(value),Fraction(value))
        for value in ['1e-100000000','1'*257,2**2049]:
            with self.assertRaisesRegex(v.ContractError,'DIMENSION_RESOURCE_LIMIT'):v.rational(value)
        for value in [False,1.5,'nan','1/0','0','-3']:
            with self.assertRaises(v.ContractError):v.rational(value)
    def test_auxiliary_sqlite_symlink_rejected(self):
        target=self.root/'other';target.write_text('untouched')
        (self.root/'ledger.sqlite-wal').symlink_to(target)
        with self.assertRaisesRegex(v.ContractError,'BENCHMARK_LEDGER_SYMLINK'):BenchmarkLedger(self.root/'ledger.sqlite')
        self.assertEqual(target.read_text(),'untouched')
    def test_parent_rename_does_not_redirect_open(self):
        import sqlite3
        parent=self.root/'parent';parent.mkdir();other=self.root/'other';other.mkdir();moved=self.root/'moved'
        real=sqlite3.connect
        def swap(*a,**kw):
            parent.rename(moved);parent.symlink_to(other,target_is_directory=True);return real(*a,**kw)
        with patch('cognitive.evaluation.sqlite3.connect',swap):db=BenchmarkLedger(parent/'ledger.sqlite')
        try:db.register('root')
        finally:db.close()
        self.assertTrue((moved/'ledger.sqlite').exists());self.assertFalse((other/'ledger.sqlite').exists())
    def test_native_extension_and_pth_rejected(self):
        (self.root/'cognitive/__init__.py').write_text('');anchor=freeze(self.root)
        for name in ['evil.so','evil.pth','evil.pyc']:
            path=self.root/'cognitive'/name;path.write_bytes(b'not executable')
            with self.assertRaisesRegex(v.ContractError,'RELEASE_UNLISTED_CODE'):verify(self.root,anchor)
            path.unlink()
