#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research" / "g32" / "qros_g32_universe.py"
ONTOLOGY_PATH = ROOT / "control" / "G32_UNIVERSE_ONTOLOGY_V2.json"

spec = importlib.util.spec_from_file_location("qros_g32_universe", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class G32UniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ontology = module.read_ontology(ONTOLOGY_PATH)
        cls.a_rows = list(module.enumerate_signal_a(cls.ontology))
        cls.b_rows = list(module.enumerate_signal_b(cls.ontology))
        cls.a_ids = {x[0] for x in cls.a_rows}
        cls.b_ids = {x[0] for x in cls.b_rows}

    def test_ontology_guards_results_and_holdout(self) -> None:
        self.assertFalse(self.ontology["results_seen"])
        self.assertFalse(self.ontology["market_data_read_for_design"])
        self.assertFalse(self.ontology["holdout_opened"])

    def test_valid_alpha_pairs_exact(self) -> None:
        pairs = module.valid_alpha_pairs(self.ontology)
        self.assertEqual(len(pairs), 19)
        self.assertIn((500000, 50000), pairs)
        self.assertNotIn((200000, 200000), pairs)
        self.assertTrue(all(0 < slow < fast <= 1_000_000 for fast, slow in pairs))

    def test_family_expansion_independent_exact_set(self) -> None:
        a = {(family, module.canonical_bytes(params)) for family, params in module.family_variants_a(self.ontology)}
        b = {(family, module.canonical_bytes(params)) for family, params in module.family_variants_b(self.ontology)}
        self.assertEqual(len(a), 48)
        self.assertEqual(a, b)

    def test_signal_cardinality_and_no_duplicate_ids(self) -> None:
        self.assertEqual(len(self.a_rows), 700416)
        self.assertEqual(len(self.a_ids), 700416)
        self.assertEqual(len(self.b_rows), 700416)
        self.assertEqual(len(self.b_ids), 700416)

    def test_exact_signal_set_parity(self) -> None:
        self.assertEqual(self.a_ids.symmetric_difference(self.b_ids), set())
        self.assertEqual(module.sorted_root(self.a_ids), "5d78fb75b54b2ff61b95c0917c1760d08da9ce1c55092793fa5917f7824bb7aa")

    def test_phase_semantics_cannot_alias(self) -> None:
        base = {
            "schema": module.SIGNAL_SCHEMA,
            "asset": "NQX",
            "side": "BUY",
            "timeframe_seconds": 300,
            "feature_quote_side": "BID",
            "price_transform": "HL2",
            "fast_limit_ppm": 500000,
            "slow_limit_ppm": 50000,
            "gap_state_policy": "RESET_STATE_AND_REWARM",
            "family_id": "F01_ROOT_FRESH_CROSS",
            "family_parameters": {},
        }
        public = dict(base, phase_estimator="PUBLIC_LITERAL_RATIO_BRANCH")
        descendant = dict(base, phase_estimator="EHLERS_ATAN2_DEGREES_DESCENDANT")
        self.assertNotEqual(module.object_id("g32s_", public), module.object_id("g32s_", descendant))

    def test_canonicalization_independent_of_key_order(self) -> None:
        a = {"z": 1, "a": "á", "nested": {"b": 2, "a": 1}}
        b = {"nested": {"a": 1, "b": 2}, "a": "a\u0301", "z": 1}
        self.assertEqual(module.canonical_bytes(a), module.canonical_bytes(b))

    def test_separate_profile_universes(self) -> None:
        management_a = set(module.enumerate_management(self.ontology))
        management_b = set(module.enumerate_management(self.ontology, reverse=True))
        stress_a = set(module.enumerate_stress(self.ontology))
        stress_b = set(module.enumerate_stress(self.ontology, reverse=True))
        self.assertEqual(management_a, management_b)
        self.assertEqual(len(management_a), 144)
        self.assertEqual(stress_a, stress_b)
        self.assertEqual(len(stress_a), 15)
        self.assertEqual(len(module.enumerate_execution(self.ontology)), 1)

    def test_shards_cover_exact_signal_set(self) -> None:
        manifest = module.shard_manifest(self.a_ids)
        self.assertEqual(len(manifest["shards"]), 256)
        self.assertEqual(sum(x["count"] for x in manifest["shards"]), 700416)
        self.assertEqual({x["prefix"] for x in manifest["shards"]}, {f"{i:02x}" for i in range(256)})

    def test_full_receipt_stays_non_economic(self) -> None:
        receipt, _, coverage = module.build_receipts(ONTOLOGY_PATH)
        self.assertEqual(receipt["status"], "PASS_NO_RESULTS")
        self.assertFalse(receipt["market_data_read"])
        self.assertFalse(receipt["pnl_read"])
        self.assertFalse(receipt["holdout_opened"])
        self.assertEqual(receipt["signal_universe"]["symmetric_difference_count"], 0)
        self.assertFalse(coverage["branch_exhausted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
