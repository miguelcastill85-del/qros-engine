"""Adversarial independent Python G1 oracle tests. No market data or PnL."""
import json
import pathlib
import sys
import unittest

backend=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(backend))
from universe_contract import derive_oracle, make_blueprint, enumerate_toy_ids, UniverseReject

fixture=json.loads((backend.parent/'flutter_app/test/fixtures/universe_oracle.json').read_text())

class UniverseContractTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads(json.dumps(fixture['raw_input']))

    def test_independent_oracle_matches_frozen_fixture(self):
        self.assertEqual(derive_oracle(self.raw),fixture['oracle'])
        self.assertEqual(fixture['oracle']['raw_births'],144)

    def test_permutation_invariant(self):
        original=derive_oracle(self.raw)
        for field in ('sides','timeframes','lookback_bars','confirmation_bars','stop_ratios','maximum_holding_bars'):
            self.raw[field].reverse()
        self.assertEqual(derive_oracle(self.raw),original)

    def test_complete_distinct_toy_census(self):
        ids=enumerate_toy_ids(make_blueprint(self.raw))
        self.assertEqual(len(ids),144)
        self.assertEqual(len(set(ids)),144)
        self.assertTrue(all(x.startswith('SIM_XAUUSD|') for x in ids))

    def test_single_side_exact_half(self):
        self.raw['sides']=['BUY']
        self.assertEqual(derive_oracle(self.raw)['raw_births'],72)
        self.assertNotEqual(derive_oracle(self.raw)['canonical_sha256'],fixture['oracle']['canonical_sha256'])

    def test_no_reinterpretation_of_future_bar(self):
        self.raw['observability']='BAR_ZERO_CURRENT'
        with self.assertRaisesRegex(UniverseReject,'FUTURE_OR_UNFINALIZED_BAR'):make_blueprint(self.raw)

    def test_no_live_broker_data(self):
        self.raw['symbol']='XAUUSD'
        with self.assertRaisesRegex(UniverseReject,'SYMBOL_NOT_SYNTHETIC'):make_blueprint(self.raw)

    def test_reject_unknown_fields_actor_escalation(self):
        self.raw['actor']='QROS_CORE'
        with self.assertRaisesRegex(UniverseReject,'BLUEPRINT_SCHEMA'):make_blueprint(self.raw)

    def test_duplicate_genotypes_not_silently_accepted(self):
        self.raw['sides']=['BUY','BUY']
        with self.assertRaisesRegex(UniverseReject,'DUPLICATE_SIDES'):make_blueprint(self.raw)

    def test_invalid_rational_grid(self):
        self.raw['stop_ratios']=['1.01']
        with self.assertRaisesRegex(UniverseReject,'INVALID_STOP_RATIOS'):make_blueprint(self.raw)

    def test_reject_empty_parameter_axis(self):
        self.raw['confirmation_bars']=[]
        with self.assertRaisesRegex(UniverseReject,'EMPTY_CONFIRMATION_BARS'):make_blueprint(self.raw)

    def test_overnight_policy_fail_closed(self):
        self.raw['overnight_allowed']=True
        with self.assertRaisesRegex(UniverseReject,'EXECUTION_POLICY_DRIFT'):make_blueprint(self.raw)

    def test_boolean_instead_of_three_invalid(self):
        self.raw['max_entries_per_day']=True
        with self.assertRaisesRegex(UniverseReject,'EXECUTION_POLICY_DRIFT'):make_blueprint(self.raw)

    def test_data_and_scientific_gates_remain_closed(self):
        obj=make_blueprint(self.raw)
        self.assertFalse(obj['holdout_open'])
        self.assertFalse(obj['scientific_authority'])
        self.assertEqual(obj['constraints']['buy_entry'],'ASK')
        self.assertEqual(obj['constraints']['sell_entry'],'BID')
        self.assertEqual(obj['constraints']['ambiguous_sl_tp'],'STOP_FIRST')

    def test_existing_cpp_contract_names_reused(self):
        cpp=pathlib.Path(__file__).resolve().parents[4]/'include/qros/research_contract.hpp'
        # CI repo root differs from arbitrary local package; use C++ source if present.
        repo=pathlib.Path(__file__).resolve().parents[4]
        cpp=repo/'include/qros/research_contract.hpp'
        if not cpp.exists():
            self.skipTest('Exact source contract pin enforced in GitHub workflow')
        body=cpp.read_text()
        for field in ('search_space_sha256','multiplicity_n_tests','holdout_partition_id',
                      'data_authority_id','program_sha256','execution_policy_sha256'):
            self.assertIn(field,body)

if __name__=='__main__':unittest.main()
