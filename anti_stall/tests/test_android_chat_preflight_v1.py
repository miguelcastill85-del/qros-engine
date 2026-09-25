import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('qros_android_preflight',HERE/'chat'/'qros_android_turn_preflight_v1.py')
pre=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pre)
PROJECT=pathlib.Path(__file__).resolve().parents[2]
POLICY=json.loads((PROJECT/'governance'/'QROS_ANDROID_CHAT_TURN_ANTISTALL_V1.json').read_text(encoding='utf-8'))

class ChatPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.pol=self.save('policy.json',POLICY)
        self.gov={'version':'2.4','chat_turn_protocol':{'mode':'CHAT_TURN_ONLY','git_blob_sha1':pre.git_blob(self.pol.read_bytes()),'path':'governance/QROS_ANDROID_CHAT_TURN_ANTISTALL_V1.json'}}
        self.g=self.save('g.json',self.gov)
        self.t=self.save('HANDOFF_v1.json',{'state':'DEVELOPMENT_RUNNING','last_closed':'V33'})
        self.a=self.save('ANCHOR_v1.json',{'status':'PASS','scope':'261'})
        self.pobj={'schema':'QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF_POINTER_V1',
                   'branch':POLICY['scientific_branch'],'target':'control/HANDOFF_v1.json','target_git_blob_sha1':pre.git_blob(self.t.read_bytes()),
                   'last_closed_remote_anchor_path':'control/ANCHOR_v1.json','last_closed_remote_anchor_blob_sha1':pre.git_blob(self.a.read_bytes()),
                   'last_closed':'V33_261_OF_710', 'next_action':'Do exactly original shard 262',
                   'pending_configurations_preregistered_not_executed':0,'holdout_open':False,'ga2_open':False,'Gate_A_approved':False}
        self.p=self.save('pointer.json',self.pobj)

    def save(self,name,obj):
        path=self.root/name;path.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
        return path
    def run_check(self):
        return pre.preflight(str(self.g),pre.git_blob(self.g.read_bytes()),str(self.pol),str(self.p),pre.git_blob(self.p.read_bytes()),str(self.t),str(self.a),POLICY['scientific_branch'])
    def fail(self,fragment):
        with self.assertRaises(pre.FailClosed) as ctx:self.run_check()
        self.assertIn(fragment,str(ctx.exception))

    def test_real_validation_fixture_succeeds(self):
        out=self.run_check()
        self.assertEqual(out['status'],'VERIFIED_NEXT_TURN_ACTION_READY')
        self.assertEqual(out['next_action'],'Do exactly original shard 262')
        self.assertEqual(out['execution_mode'],'SYNCHRONOUS_IN_THIS_CHAT_ONLY')
    def test_same_input_deterministic_no_duplicate_mutation(self):
        before={p:p.read_bytes() for p in (self.g,self.pol,self.p,self.t,self.a)}
        self.assertEqual(self.run_check(),self.run_check())
        self.assertEqual(before,{p:p.read_bytes() for p in before})
    def test_governance_pin_mismatch(self):
        self.g.write_text(self.g.read_text()+' ')
        with self.assertRaises(pre.FailClosed):pre.preflight(str(self.g),self.gov['chat_turn_protocol']['git_blob_sha1'],str(self.pol),str(self.p),pre.git_blob(self.p.read_bytes()),str(self.t),str(self.a),POLICY['scientific_branch'])
    def test_policy_mutation_rejected(self):
        self.pol.write_bytes(self.pol.read_bytes()+b' ')
        self.fail('CHAT_POLICY')
    def test_live_pointer_changes_after_independent_pin_rejected(self):
        fixed=pre.git_blob(self.p.read_bytes());self.pobj['next_action']='different'
        self.save('pointer.json',self.pobj)
        with self.assertRaises(pre.FailClosed) as ctx:pre.preflight(str(self.g),pre.git_blob(self.g.read_bytes()),str(self.pol),str(self.p),fixed,str(self.t),str(self.a),POLICY['scientific_branch'])
        self.assertIn('LIVE_SCIENTIFIC_POINTER',str(ctx.exception))
    def test_wrong_target_bytes_rejected(self):
        self.t.write_bytes(self.t.read_bytes()+b'\n')
        self.fail('SCIENTIFIC_HANDOFF')
    def test_wrong_anchor_bytes_rejected(self):
        self.a.write_bytes(self.a.read_bytes()+b'\n')
        self.fail('SCIENTIFIC_ANCHOR')
    def test_target_path_substitution_rejected(self):
        self.pobj['target']='control/OTHER.json';self.save('pointer.json',self.pobj)
        self.fail('EXACT_TARGET_OR_ANCHOR_PATH_MISMATCH')
    def test_escape_path_rejected(self):
        self.pobj['target']='../HANDOFF_v1.json';self.save('pointer.json',self.pobj)
        self.fail('UNSAFE_REPOSITORY_PATH')
    def test_holdout_open_rejected(self):
        self.pobj['holdout_open']=True;self.save('pointer.json',self.pobj)
        self.fail('SCIENTIFIC_FIREWALL')
    def test_ga2_open_rejected(self):
        self.pobj['ga2_open']=True;self.save('pointer.json',self.pobj)
        self.fail('SCIENTIFIC_FIREWALL')
    def test_gate_a_open_rejected(self):
        self.pobj['Gate_A_approved']=True;self.save('pointer.json',self.pobj)
        self.fail('SCIENTIFIC_FIREWALL')
    def test_missing_completed_cursor_rejected(self):
        self.pobj['pending_configurations_preregistered_not_executed']=42;self.save('pointer.json',self.pobj)
        self.fail('UNRECONCILED_ECONOMIC_SCOPE')
    def test_missing_next_action_rejected(self):
        self.pobj.pop('next_action');self.save('pointer.json',self.pobj)
        self.fail('MISSING_CHECKPOINT_OR_NEXT_ACTION')
    def test_wrong_branch_rejected(self):
        self.pobj['branch']='main';self.save('pointer.json',self.pobj)
        self.fail('SCIENTIFIC_BRANCH_MISMATCH')

if __name__=='__main__':unittest.main()
