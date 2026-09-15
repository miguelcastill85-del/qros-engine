#!/usr/bin/env python3
import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.qros_first_gate_scorer_v1 import (
    CAMPAIGN,
    ScorerError,
    apply_benjamini_yekutieli,
    hac_one_sided_positive_mean,
    score_document,
)


class FirstGateScorerTests(unittest.TestCase):
    def setUp(self):
        start = date(2020, 1, 1)
        self.dates = [(start + timedelta(days=i)).isoformat() for i in range(40)]

    def _trade(self, i, r=1.0):
        ts = 1_600_000_000_000 + i * 60_000
        return {
            "trade_id": f"T{i:03d}",
            "dev_date": self.dates[i],
            "entry_ts_ms": ts,
            "exit_ts_ms": ts + 30_000,
            "r": r,
        }

    def _doc(self):
        return {
            "schema": "QROS_FIRST_GATE_CANONICAL_MASK_OBSERVATIONS_1.0",
            "campaign": CAMPAIGN,
            "ticket_id": "synthetic-ticket",
            "shard_id": "synthetic-shard",
            "eligible_dev_dates": self.dates,
            "expected_distinct_mask_classes": 2,
            "canonical_masks": [
                {
                    "signal_config_id": "CFG_A",
                    "event_mask_sha256": "a" * 64,
                    "zero_event_class": False,
                    "trades": [self._trade(i, 1.0) for i in range(30)],
                },
                {
                    "signal_config_id": "CFG_ZERO",
                    "event_mask_sha256": "b" * 64,
                    "zero_event_class": True,
                    "trades": [],
                },
            ],
        }

    def test_hac_degenerate_variance_forces_p_one(self):
        h = hac_one_sided_positive_mean([1.0] * 40)
        self.assertEqual(h.raw_p, 1.0)
        self.assertEqual(h.se, 0.0)

    def test_by_rejects_only_smallest_p(self):
        rows = [
            {"signal_config_id": "B", "raw_p": 1.0},
            {"signal_config_id": "A", "raw_p": 1e-9},
            {"signal_config_id": "C", "raw_p": 0.5},
        ]
        k = apply_benjamini_yekutieli(rows)
        self.assertEqual(k, 1)
        status = {r["signal_config_id"]: r["by_rejected"] for r in rows}
        self.assertEqual(status, {"A": True, "B": False, "C": False})

    def test_positive_synthetic_mask_survives_and_zero_never_survives(self):
        out = score_document(self._doc())
        self.assertEqual(out["shard_decision"], "PASS_FIRST_GATE")
        self.assertEqual(out["survivor_count"], 1)
        rows = {r["signal_config_id"]: r for r in out["results"]}
        self.assertTrue(rows["CFG_A"]["candidate_survives"])
        self.assertFalse(rows["CFG_ZERO"]["candidate_survives"])
        self.assertEqual(rows["CFG_ZERO"]["raw_p"], 1.0)
        self.assertEqual(rows["CFG_A"]["trades"], 30)
        self.assertGreater(rows["CFG_A"]["net_R"], 0.0)

    def test_less_than_30_trades_forces_p_one(self):
        doc = self._doc()
        doc["canonical_masks"][0]["trades"] = [self._trade(i, 1.0) for i in range(29)]
        out = score_document(doc)
        rows = {r["signal_config_id"]: r for r in out["results"]}
        self.assertEqual(rows["CFG_A"]["raw_p"], 1.0)
        self.assertFalse(rows["CFG_A"]["candidate_survives"])
        self.assertEqual(out["shard_decision"], "REJECTED_FIRST_GATE")

    def test_output_is_deterministic_under_mask_input_order(self):
        a = self._doc()
        b = copy.deepcopy(a)
        b["canonical_masks"].reverse()
        self.assertEqual(score_document(a), score_document(b))

    def test_expected_mask_count_mismatch_fails_closed(self):
        doc = self._doc()
        doc["expected_distinct_mask_classes"] = 3
        with self.assertRaises(ScorerError):
            score_document(doc)

    def test_duplicate_event_mask_fails_closed(self):
        doc = self._doc()
        doc["canonical_masks"][1]["event_mask_sha256"] = "a" * 64
        with self.assertRaises(ScorerError):
            score_document(doc)


if __name__ == "__main__":
    unittest.main()
