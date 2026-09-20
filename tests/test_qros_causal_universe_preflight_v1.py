#!/usr/bin/env python3
import copy, importlib.util, pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("preflight", ROOT / "scripts" / "qros_causal_universe_preflight_v1.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

BASE = {
 "scientific_state":"PREREGISTERED_NO_RESULTS",
 "economic_firewall":{"economic_pnl_read":False,"holdout_open":False,"ga2_open":False,"economic_scoring_authorized":False},
 "causal_hypothesis":{"mechanism_id":"FAILED_AUCTION_REJECTION","genealogy_id":"TEST_GENEALOGY","mechanism_fingerprint":"sha256:test","observable_before_entry":True},
 "bar_clock":{"timezone_authority":"BROKER_AUTH","session_calendar":"SESSION_AUTH","bar_origin":"BROKER_SESSION_ANCHORED","dst_policy":"EXPLICIT","partial_bar_policy":"DISALLOW_UNLESS_EXPLICIT"},
 "features":[
   {"feature_id":"range_high","source_timeframe":"M15","availability":"CLOSED_BAR","closed_bar_offset":1,"depends_on":["bid","ask"],"uses_future_data":False},
   {"feature_id":"reclaim_tick","source_timeframe":"TICK","availability":"CURRENT_TICK_CAUSAL","closed_bar_offset":0,"depends_on":["bid","ask"],"uses_future_data":False}
 ],
 "universe":{
   "parameter_axes":{"sweep_points":[1,2,3],"reclaim_ticks":[1,2],"context":["OFF","EMA_ORDER"]},
   "expected_raw_count":12,
   "interaction_depth":2,
   "interaction_depth_rationale":"Two operators are causally complementary; no third operator is needed for the mechanism.",
   "parameter_neighborhood_preregistered":True,
   "semantic_normalization_exact_only":True,
   "near_duplicate_reduces_n_tests":False
 },
 "genealogy_collision":{"mechanism_fingerprint_required":True,"exact_event_mask_collision_check_pre_pnl":True,"collision_changes_genealogy_without_new_preregistration":False},
 "parity":{"independent_enumerator_required":True,"independent_signal_oracle_required":True,"independent_execution_oracle_required":True,"primary_and_oracle_source_must_differ":True},
 "multiplicity":{"n_tests_authority":"FROZEN_GLOBAL_EXACT_HYPOTHESIS_COUNT","campaign_level_null_calibration_required":True,"cross_shard_duplicate_policy":"GLOBAL_EXACT_MASK_ALIAS"},
 "external_oracle":{"consumes_frozen_anchors_for_execution":True,"may_generate_candidates":False,"may_select_candidates":False}
}

def codes(doc):
    return {x["code"] for x in mod.validate(doc)["errors"]}

class PreflightTests(unittest.TestCase):
    def test_valid_pass(self):
        self.assertEqual(mod.validate(copy.deepcopy(BASE))["status"],"PASS")
    def test_closed_bar_offset(self):
        d=copy.deepcopy(BASE); d["features"][0]["closed_bar_offset"]=0
        self.assertIn("LOOKAHEAD_CLOSED_BAR_OFFSET",codes(d))
    def test_explicit_future(self):
        d=copy.deepcopy(BASE); d["features"][0]["uses_future_data"]=True
        self.assertIn("LOOKAHEAD_EXPLICIT",codes(d))
    def test_bar_origin_required(self):
        d=copy.deepcopy(BASE); d["bar_clock"]["bar_origin"]=""
        self.assertIn("BAR_CLOCK_BINDING_MISSING",codes(d))
    def test_economic_firewall(self):
        d=copy.deepcopy(BASE); d["economic_firewall"]["economic_pnl_read"]=True
        self.assertIn("ECONOMIC_FIREWALL_OPEN",codes(d))
    def test_universe_count(self):
        d=copy.deepcopy(BASE); d["universe"]["expected_raw_count"]=11
        self.assertIn("UNIVERSE_COUNT_MISMATCH",codes(d))
    def test_neighborhood_freeze(self):
        d=copy.deepcopy(BASE); d["universe"]["parameter_neighborhood_preregistered"]=False
        self.assertIn("PARAMETER_NEIGHBORHOOD_NOT_FROZEN",codes(d))
    def test_near_duplicate_cannot_reduce_ntests(self):
        d=copy.deepcopy(BASE); d["universe"]["near_duplicate_reduces_n_tests"]=True
        self.assertIn("NEAR_DUPLICATE_NTESTS_LEAK",codes(d))
    def test_genealogy_collision_gate(self):
        d=copy.deepcopy(BASE); d["genealogy_collision"]["exact_event_mask_collision_check_pre_pnl"]=False
        self.assertIn("CROSS_GENEALOGY_COLLISION_UNCHECKED",codes(d))
    def test_signal_oracle_required(self):
        d=copy.deepcopy(BASE); d["parity"]["independent_signal_oracle_required"]=False
        self.assertIn("PARITY_REQUIREMENT_MISSING",codes(d))
    def test_sources_must_differ(self):
        d=copy.deepcopy(BASE); d["parity"]["primary_and_oracle_source_must_differ"]=False
        self.assertIn("PARITY_NOT_INDEPENDENT",codes(d))
    def test_global_null_calibration(self):
        d=copy.deepcopy(BASE); d["multiplicity"]["campaign_level_null_calibration_required"]=False
        self.assertIn("GLOBAL_NULL_CALIBRATION_MISSING",codes(d))
    def test_external_cannot_generate(self):
        d=copy.deepcopy(BASE); d["external_oracle"]["may_generate_candidates"]=True
        self.assertIn("EXTERNAL_CANDIDATE_GENERATION_FORBIDDEN",codes(d))
    def test_external_cannot_select(self):
        d=copy.deepcopy(BASE); d["external_oracle"]["may_select_candidates"]=True
        self.assertIn("EXTERNAL_CANDIDATE_SELECTION_FORBIDDEN",codes(d))

if __name__=="__main__":
    unittest.main()
