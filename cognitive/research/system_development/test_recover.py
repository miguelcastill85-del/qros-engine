import json
import shutil
import tempfile
import unittest
from pathlib import Path
from cognitive import runtime as v
from .recover import recover

HERE=Path(__file__).resolve().parent
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        for name in ('RESULTS.json','RAW_RESPONSE.json','PLAN.json'):shutil.copyfile(HERE/'sol_001'/name,self.path/name)
        self.anchor=v.sha256((self.path/'RESULTS.json').read_bytes())
    def check(self):return recover(self.path,self.anchor,HERE/'PREREGISTRATION.json')
    def mutate(self,edit,reanchor=False):
        p=self.path/'RESULTS.json';value=json.loads(p.read_bytes());edit(value);p.write_bytes(v.canonical(value))
        if reanchor:self.anchor=v.sha256(p.read_bytes())
    def test_clean_copy_reused_without_execution(self):
        r=self.check();self.assertEqual(r['new_interpreter_operations'],0);self.assertEqual(r['episodes_revalidated'],15)
    def test_external_anchor_rejects_changed_receipt(self):
        self.mutate(lambda x:x.update(route='ALTERED'))
        with self.assertRaises(v.ContractError):self.check()
    def test_raw_model_program_change_rejected(self):
        p=self.path/'RAW_RESPONSE.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(v.ContractError):self.check()
    def test_duplicate_episode_not_complete_coverage(self):
        self.mutate(lambda x:x['records'].__setitem__(1,x['records'][0]),True)
        with self.assertRaises(v.ContractError):self.check()
    def test_forged_pass_cannot_hide_wrong_error(self):
        def edit(x):
            row=x['records'][-1];answer={'status':'FAIL_CLOSED','error':'OTHER'};row['final_answer']=answer;row['attempts'][-1]['stdout']=json.dumps(answer)
        self.mutate(edit,True)
        with self.assertRaises(v.ContractError):self.check()
    def test_interruption_claim_requires_exit_evidence(self):
        self.mutate(lambda x:x['records'][3]['attempts'][0].update(exit_code=0),True)
        with self.assertRaises(v.ContractError):self.check()
    def test_unknown_or_forbidden_operation_rejected(self):
        self.mutate(lambda x:x['records'][0]['host_operation_trace'][0].update(task_id='S'),True)
        with self.assertRaises(v.ContractError):self.check()

if __name__=='__main__':unittest.main()
