import copy
import unittest
from cognitive import runtime as v
from .preflight import check,ARMS

def fixture():
    return {'schema':'QRCEL_MATCHED_TREATMENT_PROTOCOL_V1','sealed':False,'arms':[{'id':name,'requested_route':'gpt-5.6-sol' if name.startswith('SOL_') else 'gpt-6-astra','task_set_sha256':'a'*64,'scorer_sha256':'b'*64,'toolset_sha256':'c'*64,'data_access_sha256':'d'*64,'prompt_sha256':'e'*64,'resource_envelope':{'max_tool_calls':8,'max_output_tokens':4000,'max_wall_seconds':120}} for name in sorted(ARMS)]}
class PreflightTests(unittest.TestCase):
    def test_matched_protocol_not_a_parity_result(self):
        p=fixture();r=check(p,v.sha256(v.canonical(p)));self.assertFalse(r['parity_claim_allowed']);self.assertFalse(r['full_current_qros_comparison'])
    def test_each_resource_or_access_mismatch_rejected(self):
        for key in ['task_set_sha256','scorer_sha256','toolset_sha256','data_access_sha256']:
            p=fixture();p['arms'][1][key]='f'*64
            with self.subTest(key=key),self.assertRaises(v.ContractError):check(p,v.sha256(v.canonical(p)))
        p=fixture();p['arms'][0]['resource_envelope']['max_tool_calls']+=1
        with self.assertRaises(v.ContractError):check(p,v.sha256(v.canonical(p)))
    def test_provider_context_mismatch_rejected(self):
        p=fixture();p['arms'][0]['prompt_sha256']='f'*64
        with self.assertRaisesRegex(v.ContractError,'UNMATCHED_MODEL_CONTEXT'):check(p,v.sha256(v.canonical(p)))
    def test_duplicate_arm_rejected(self):
        p=fixture();p['arms'][0]=copy.deepcopy(p['arms'][1])
        with self.assertRaisesRegex(v.ContractError,'ARM_IDENTITIES'):check(p,v.sha256(v.canonical(p)))
    def test_forged_expected_hash_rejected(self):
        with self.assertRaisesRegex(v.ContractError,'PROTOCOL_ANCHOR_MISMATCH'):check(fixture(),'f'*64)
    def test_development_cannot_be_promoted_by_flag(self):
        p=fixture()
        with self.assertRaisesRegex(v.ContractError,'CONFIRMATORY_EVIDENCE_NOT_ESTABLISHED'):check(p,v.sha256(v.canonical(p)),True)
    def test_sealed_label_not_available_for_exposed_cases(self):
        p=fixture();p['sealed']=True
        with self.assertRaisesRegex(v.ContractError,'SEALED_REQUIRES'):check(p,v.sha256(v.canonical(p)))
    def test_boolean_resource_cap_rejected(self):
        p=fixture();p['arms'][0]['resource_envelope']['max_tool_calls']=True
        with self.assertRaisesRegex(v.ContractError,'RESOURCE_VALUES'):check(p,v.sha256(v.canonical(p)))
if __name__=='__main__':unittest.main()
