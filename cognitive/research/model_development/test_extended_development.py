"""Adversarial scorer checks; cases remain exposed DEVELOPMENT data."""
import copy
import unittest
from .extended_development import HERE,schedule_valid,score
from cognitive.runtime import canonical,parse_json

class ExtendedScorerTests(unittest.TestCase):
    def setUp(self):
        self.gold={c['id']:c['expected'] for c in parse_json((HERE/'CASES.json').read_bytes())['cases']}

    def test_other_optimum_accepted(self):
        alternative={'start':{'A':0,'B':0,'C':3,'D':5,'E':2,'F':7,'G':10},'makespan':11}
        self.assertNotEqual(alternative,self.gold['EXT-02'])
        self.assertTrue(schedule_valid(alternative))

    def test_processor_overload_rejected(self):
        response=copy.deepcopy(self.gold['EXT-02'])
        response['start']['D']=3
        self.assertFalse(schedule_valid(response))

    def test_dependency_violation_rejected(self):
        response=copy.deepcopy(self.gold['EXT-02'])
        response['start']['F']=6
        self.assertFalse(schedule_valid(response))

    def test_bool_does_not_pass_as_integer(self):
        response=copy.deepcopy(self.gold['EXT-02'])
        response['start']['A']=False
        self.assertFalse(schedule_valid(response))
        self.gold['EXT-06']['run_D_now']=1
        row=score(canonical(self.gold))['rows'][-1]
        self.assertFalse(row['correct'])
        self.assertTrue(row['critical_failure'])

    def test_abstention_is_missing_and_critical_failure(self):
        del self.gold['EXT-04']
        row=next(r for r in score(canonical(self.gold))['rows'] if r['id']=='EXT-04')
        self.assertTrue(row['missing'])
        self.assertTrue(row['critical_failure'])

    def test_unrecognized_id_rejected(self):
        self.gold['OTHER']={}
        with self.assertRaises(ValueError):score(canonical(self.gold))

    def test_observed_response_files_are_scored_individually(self):
        for label in ('SOL','ASTRA'):
            response=(HERE/(label+'_RAW_RESPONSE.json')).read_bytes()
            self.assertEqual(score(response),parse_json((HERE/(label+'_SCORE.json')).read_bytes()))

if __name__=='__main__':unittest.main()
