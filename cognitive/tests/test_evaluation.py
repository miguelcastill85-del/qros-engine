"""Synthetic gate regressions; no model or sealed results are created."""
import copy
import math
import tempfile
import unittest
from pathlib import Path
from cognitive import evaluation as e
from cognitive import runtime as v

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'benchmark.sqlite'
        self.ledger=e.BenchmarkLedger(self.path);self.addCleanup(self.ledger.close)
        self.ledger.register('root');self.ledger.register('child','root');self.ledger.register('sibling','root')
        self.protocol={'schema':'QRCEL_PAIRED_BOUNDED_PROTOCOL_V1','dimensions':{x:0.05 for x in e.DIMENSIONS},'alpha':0.05,'fixed_n':50,'sampling_unit':'INDEPENDENT_TASK_CLUSTER'}
        self.data={'schema':'QRCEL_SUBMITTED_PAIRED_SCORES_V1','rows':[{'cluster_id':str(i),'candidate':{d:1 for d in e.DIMENSIONS},'reference':{d:0 for d in e.DIMENSIONS}} for i in range(50)],'hard_vetoes':[]}

    def score(self):return e.paired_statistics(v.canonical(self.data),self.protocol,v.sha256(v.canonical(self.protocol)))

    def test_absence_does_not_certify_sealed(self):
        self.assertEqual(self.ledger.status('child','a'*64),'NO_RECORDED_EXPOSURE_NOT_SEALED_CERTIFICATION')

    def test_exposure_propagates_to_root_siblings_and_future_versions(self):
        self.ledger.expose('child','a'*64,'b'*64);self.ledger.register('future','sibling')
        for family in ('root','child','sibling','future'):self.assertEqual(self.ledger.status(family,'a'*64),'EXPOSED')

    def test_exposure_is_durable_and_idempotent(self):
        self.ledger.expose('child','a'*64,'b'*64);self.ledger.expose('child','a'*64,'c'*64)
        other=e.BenchmarkLedger(self.path)
        try:
            self.assertEqual(other.status('sibling','a'*64),'EXPOSED')
            self.assertEqual(other.db.execute('SELECT COUNT(*) FROM exposure').fetchone()[0],1)
        finally:other.close()

    def test_reparenting_cannot_launder_exposure(self):
        self.ledger.expose('child','a'*64,'b'*64)
        with self.assertRaisesRegex(v.ContractError,'FAMILY_PARENT_IMMUTABLE'):self.ledger.register('child')

    def test_unknown_parent_and_cycle_rejected(self):
        with self.assertRaisesRegex(v.ContractError,'UNKNOWN_PARENT'):self.ledger.register('a','missing')
        with self.assertRaisesRegex(v.ContractError,'FAMILY_CYCLE'):self.ledger.register('a','a')

    def test_statistics_never_attest_model_execution_or_promote(self):
        r=self.score();self.assertTrue(r['conditional_all_dimensions_pass'])
        self.assertEqual(r['parity'],'INSUFFICIENT_EVIDENCE');self.assertFalse(r['promotion_authorized'])
        self.assertFalse(r['model_execution_verified'])

    def test_interval_satisfies_preregistered_family_tail_bound(self):
        r=self.score();radius=1-r['dimensions']['CORRECTNESS']['lower']
        bound=2*len(e.DIMENSIONS)*math.exp(-50*radius*radius/2)
        self.assertAlmostEqual(bound,self.protocol['alpha'],places=12)

    def test_single_critical_dimension_cannot_be_compensated(self):
        for row in self.data['rows']:row['candidate']['CAUSAL_REASONING']=0;row['reference']['CAUSAL_REASONING']=1
        r=self.score();self.assertFalse(r['conditional_all_dimensions_pass']);self.assertFalse(r['dimensions']['CAUSAL_REASONING']['conditional_noninferiority'])

    def test_hard_veto_dominates_all_scores(self):
        self.data['hard_vetoes']=['FABRICATED_EXECUTION'];self.assertFalse(self.score()['conditional_all_dimensions_pass'])

    def test_fixed_n_and_cluster_dedup_prevent_pseudoreplication(self):
        self.data['rows'][1]['cluster_id']='0'
        with self.assertRaisesRegex(v.ContractError,'DUPLICATE_OR_INVALID_CLUSTER'):self.score()
        self.data['rows'].pop()
        with self.assertRaisesRegex(v.ContractError,'FIXED_N_MISMATCH'):self.score()

    def test_changed_protocol_anchor_and_missing_dimension_rejected(self):
        with self.assertRaisesRegex(v.ContractError,'PROTOCOL_ANCHOR_MISMATCH'):e.paired_statistics(v.canonical(self.data),self.protocol,'a'*64)
        del self.protocol['dimensions']['CONTINUITY']
        with self.assertRaisesRegex(v.ContractError,'DIMENSION_COVERAGE'):self.score()

    def test_invalid_bool_scores_rejected(self):
        self.data['rows'][0]['candidate']['CORRECTNESS']=True
        with self.assertRaisesRegex(v.ContractError,'SCORE_RANGE'):self.score()

    def test_all_claimed_passes_are_still_not_promotion(self):
        receipts={g:{'artifact_sha256':'a'*64,'claimed_result':'PASS','scope':'TEST_ONLY'} for g in e.GATES}
        r=e.promotion_inventory(receipts)
        self.assertEqual(r['decision'],'PROMOTION_NOT_AUTHORIZED')
        self.assertTrue(all(x['status']=='SUBMITTED_UNATTESTED' for x in r['gates'].values()))

    def test_missing_gates_explicit(self):
        r=e.promotion_inventory({});self.assertEqual(len(r['gates']),len(e.GATES))
        self.assertTrue(all(x['status']=='MISSING_EVIDENCE' for x in r['gates'].values()))

if __name__=='__main__':unittest.main()
