import copy
import unittest
from cognitive import runtime as v
from .protocol import adapt,fixture,grade,grade_failure,expected_outputs

class ProtocolTests(unittest.TestCase):
    def test_unrelated_failure_is_not_successful_fault_detection(self):
        self.assertFalse(grade_failure('AUTHORITY_MISMATCH',2,{'status':'FAIL_CLOSED','error':'OUTPUT_INTEGRITY_FAILED'}))
        self.assertFalse(grade_failure('OUTPUT_CORRUPTION',2,{'status':'FAIL_CLOSED','error':'SOURCE_MISSING'}))
        self.assertTrue(grade_failure('AUTHORITY_MISMATCH',2,{'status':'FAIL_CLOSED','error':'DELEGATED_BLOB_MISMATCH'}))

    def test_valid_program_and_alternative_graph_order(self):
        program=fixture();program['tasks'][5]['inputs']['nodes'].reverse()
        self.assertEqual(len(adapt(v.canonical(program))['tasks']),7)

    def test_injection_cannot_downgrade_scientific_marker(self):
        program=fixture();program['tasks'][-1]['risk']='LOW'
        with self.assertRaises(v.ContractError):adapt(v.canonical(program))

    def test_omitted_branch_rejected(self):
        program=fixture();program['tasks'].pop(1)
        with self.assertRaises(v.ContractError):adapt(v.canonical(program))

    def test_invented_hash_field_rejected(self):
        program=fixture();program['tasks'][0]['inputs_sha256']='0'*64
        with self.assertRaises(v.ContractError):adapt(v.canonical(program))

    def test_unsafe_operation_rejected(self):
        program=fixture();program['tasks'][0]['operation']='EXEC_PYTHON'
        with self.assertRaises(v.ContractError):adapt(v.canonical(program))

    def test_valid_result_does_not_override_blocked_marker(self):
        answer={'status':'BLOCKED','blocked':['S'],'errors':[],'outputs':{**expected_outputs(),'G':{'order':['B','D','A','C','T']}}}
        self.assertTrue(grade(answer))
        answer['outputs']['S']={'fraction':'1'}
        self.assertFalse(grade(answer))

    def test_oracle_rejects_double_counted_diamond(self):
        answer={'status':'BLOCKED','blocked':['S'],'errors':[],'outputs':{**expected_outputs(),'G':{'order':['A','B','C','D','T']}}}
        answer['outputs']['T']=copy.deepcopy(answer['outputs']['A'])
        self.assertFalse(grade(answer))

if __name__=='__main__':unittest.main()
