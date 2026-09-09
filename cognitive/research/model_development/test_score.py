import importlib.util
import json
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('development_scorer',Path(__file__).with_name('score.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class ScorerTests(unittest.TestCase):
    def test_reference_fixture_is_not_model_execution(self):
        cases=s.strict(s.HERE.joinpath('CASES.json').read_bytes())['cases']
        fixture={c['id']:c['expected'] for c in cases}
        result=s.score(json.dumps(fixture).encode())
        self.assertTrue(all(r['correct'] for r in result['cases']))
        self.assertFalse(result['model_execution_verified'])
        self.assertEqual(result['parity'],'INSUFFICIENT_EVIDENCE')

    def test_bool_not_equal_to_integer_and_missing_not_dropped(self):
        result=s.score(b'{"DEV-08":{"compiled":0}}')
        self.assertEqual(len(result['cases']),12)
        self.assertTrue(all(not r['correct'] for r in result['cases']))
        self.assertTrue(next(r for r in result['cases'] if r['id']=='DEV-08')['critical_failure'])

    def test_duplicate_nonfinite_unknown_ids_rejected(self):
        for raw in (b'{"DEV-01":{},"DEV-01":{}}',b'{"DEV-01":NaN}',b'{"other":{}}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):s.score(raw)
