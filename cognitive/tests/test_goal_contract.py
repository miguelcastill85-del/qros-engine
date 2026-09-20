"""Requirement omission, substitution, dependency, depth and resume regressions."""
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from cognitive import runtime as v,goal_contract as g,kernel as k
from cognitive.tests import test_hardening as fixtures
from cognitive.tests.test_kernel import plan

def goal(p):
    return {'schema':g.SCHEMA,'scope':'EXPLICIT_LOCAL_REQUIREMENTS_ONLY','goal_id':'AUDIT-FINITE-GOAL',
            'description':'Synthetic explicit requirements; not completeness of an arbitrary user request',
            'requirements':[{'id':'R-'+t['task_id'],'operation':t['operation'],'inputs_sha256':t['inputs_sha256'],
                'parent_ids':['R-'+x for x in t['parent_ids']],'minimum_risk':t['risk']} for t in p['tasks']]}

class GoalTests(unittest.TestCase):
    setUp=fixtures.HardeningTests.setUp
    kernel=fixtures.HardeningTests.kernel
    def objects(self):
        p=plan();c=goal(p);m={'R-'+t['task_id']:t['task_id'] for t in p['tasks']};return p,c,m
    def test_complete_finite_requirements_bound(self):
        p,c,m=self.objects();r=g.bind(c,v.sha256(v.canonical(c)),p,m);self.assertEqual(r['requirement_count'],4);self.assertFalse(r['natural_language_adequacy_verified'])
    def test_missing_requirement_rejected(self):
        p,c,m=self.objects();m.pop('R-D')
        with self.assertRaisesRegex(v.ContractError,'GOAL_MAPPING_COVERAGE'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_one_task_cannot_count_twice(self):
        p,c,m=self.objects();m['R-D']='A'
        with self.assertRaisesRegex(v.ContractError,'GOAL_WITNESS_REUSED'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_extra_plan_task_not_silently_ignored(self):
        p,c,m=self.objects();t=copy.deepcopy(p['tasks'][0]);t['task_id']='EXTRA';p['tasks'].append(t)
        with self.assertRaisesRegex(v.ContractError,'GOAL_TASK_COVERAGE'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_substituted_predicate_rejected(self):
        p,c,m=self.objects();p['tasks'][0]['inputs_sha256']='a'*64
        with self.assertRaisesRegex(v.ContractError,'GOAL_PREDICATE_MISMATCH'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_lost_dependency_rejected(self):
        p,c,m=self.objects();p['tasks'][1]['parent_ids']=[]
        with self.assertRaisesRegex(v.ContractError,'GOAL_DEPENDENCY_MISMATCH'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_depth_cannot_be_downgraded(self):
        p,c,m=self.objects();p['tasks'][2]['risk']='LOW'
        with self.assertRaisesRegex(v.ContractError,'GOAL_DEPTH_DOWNGRADE'):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_changed_description_rejected_by_external_hash(self):
        p,c,m=self.objects();h=v.sha256(v.canonical(c));c['description']='Changed objective'
        with self.assertRaisesRegex(v.ContractError,'GOAL_ANCHOR_MISMATCH'):g.bind(c,h,p,m)
    def test_partial_completion_keeps_missing_requirements(self):
        p,c,m=self.objects();b=g.bind(c,v.sha256(v.canonical(c)),p,m);r=g.completion(b,{'A':{}})
        self.assertEqual(r['status'],'EXPLICIT_REQUIREMENTS_PENDING');self.assertEqual(len(r['pending']),3)
    def test_kernel_enforces_contract_and_returns_scoped_completion(self):
        p,c,m=self.objects();obj=self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m);r=obj.run()
        self.assertEqual(r['goal_completion']['status'],'EXPLICIT_REQUIREMENTS_SATISFIED');self.assertFalse(r['goal_completion']['natural_language_adequacy_verified'])
    def test_kernel_rejects_missing_mapping_before_store(self):
        p,c,m=self.objects();m.pop('R-D')
        with self.assertRaisesRegex(v.ContractError,'GOAL_MAPPING_COVERAGE'):self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m)
        self.assertFalse((self.root/'cognitive/runs').exists())
    def test_in_memory_goal_mutation_blocks_resume(self):
        p,c,m=self.objects();obj=self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m);obj.run();obj.goal_contract['description']='changed'
        with self.assertRaisesRegex(v.ContractError,'GOAL_ANCHOR_MISMATCH'):obj.run()
    def test_changed_goal_cannot_reuse_previous_database(self):
        p,c,m=self.objects();obj=self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m);obj.run();c['description']='different'
        with self.assertRaisesRegex(v.ContractError,'RUN_BINDING_MISMATCH'):self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m)
    def test_caller_mutation_does_not_change_frozen_goal(self):
        p,c,m=self.objects();obj=self.kernel(goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m);c['requirements'].clear();m.clear()
        self.assertEqual(obj.run()['goal_completion']['status'],'EXPLICIT_REQUIREMENTS_SATISFIED')
    def test_uncontracted_goal_does_not_claim_complete(self):
        self.assertEqual(self.kernel().run()['goal_completion']['status'],'NO_EXPLICIT_GOAL_CONTRACT')
    def test_cycle_in_requirements_rejected(self):
        p,c,m=self.objects();c['requirements'][0]['parent_ids']=['R-B']
        with self.assertRaises(v.ContractError):g.bind(c,v.sha256(v.canonical(c)),p,m)
    def test_scientific_requirement_remains_pending(self):
        from cognitive.tests import test_runtime as authority
        self.kernel(run='setup');p,c,m=self.objects();p['tasks'][0]['risk']='SCIENTIFIC';c=goal(p)
        obj=k.Kernel(self.root,p,v.sha256(v.canonical(p)),authority.ANCHOR,'blocked',
                     goal_contract=c,goal_sha256=v.sha256(v.canonical(c)),goal_mapping=m)
        try:r=obj.run()
        finally:obj.close()
        self.assertEqual(r['status'],'BLOCKED');self.assertIn('R-A',r['goal_completion']['pending']);self.assertFalse(r['scientific_effect_authorized'])
    def test_goal_preserved_in_fresh_process_restore(self):
        from cognitive.tests import test_runtime as authority
        p,c,m=self.objects();h=v.sha256(v.canonical(c));obj=self.kernel(goal_contract=c,goal_sha256=h,goal_mapping=m);first=obj.run()
        capsule={'plan':p,'goal':c,'mapping':m,'anchor':first['resume_anchor']}
        (self.root/'capsule.json').write_bytes(v.canonical(capsule))
        code='''import json,sys
from pathlib import Path
from cognitive import kernel as k,runtime as v
root=Path(sys.argv[1]);x=v.parse_json((root/'capsule.json').read_bytes())
obj=k.Kernel(root,x['plan'],v.sha256(v.canonical(x['plan'])),sys.argv[2],'fresh',x['anchor'],goal_contract=x['goal'],goal_sha256=sys.argv[3],goal_mapping=x['mapping'])
try:
 obj.restore((root/'cognitive/runs/test/checkpoint.json').read_bytes(),sys.argv[4]);print(json.dumps(obj.run()))
finally:obj.close()
'''
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.root),authority.ANCHOR,h,first['checkpoint_sha256']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5,env={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).resolve().parents[2]),'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(result.returncode,0,result.stderr);second=json.loads(result.stdout)
        self.assertEqual(second['newly_completed'],0);self.assertEqual(second['checkpoint_sha256'],first['checkpoint_sha256']);self.assertEqual(second['goal_completion'],first['goal_completion'])

if __name__=='__main__':unittest.main()
