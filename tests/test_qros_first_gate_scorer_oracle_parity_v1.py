#!/usr/bin/env python3
import ast
import copy
import math
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.qros_first_gate_scorer_v1 import ScorerError, score_document
from scripts.qros_first_gate_scorer_oracle_v2 import OracleError, oracle_score_document

TICKET = "3c4acd2b22daf849e0dd4f3b5bffb327058aa92f3cb63a3902e06f605bf10854"
CAMPAIGN = "PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"


class OracleParityTests(unittest.TestCase):
    def setUp(self):
        start = date(2021, 1, 1)
        self.dates = [(start + timedelta(days=i)).isoformat() for i in range(80)]

    def trade(self, prefix, i, r, day=None, exit_shift=0):
        idx = i if day is None else day
        ts = 1_610_000_000_000 + i * 120_000
        return {
            "trade_id": f"{prefix}_{i:04d}",
            "dev_date": self.dates[idx],
            "entry_ts_ms": ts,
            "exit_ts_ms": ts + 60_000 + exit_shift,
            "r": r,
        }

    def base_doc(self):
        positive = [self.trade("A", i, 1.0 if i % 5 else -0.2, day=i) for i in range(36)]
        weak = [self.trade("B", i, 0.15 if i % 2 else -0.2, day=(i * 2) % 60) for i in range(32)]
        return {
            "schema": "QROS_FIRST_GATE_CANONICAL_MASK_OBSERVATIONS_1.0",
            "campaign": CAMPAIGN,
            "ticket_id": TICKET,
            "shard_id": "synthetic-v253-parity",
            "eligible_dev_dates": self.dates,
            "expected_distinct_mask_classes": 3,
            "canonical_masks": [
                {
                    "signal_config_id": "CFG_A",
                    "event_mask_sha256": "a" * 64,
                    "zero_event_class": False,
                    "trades": positive,
                },
                {
                    "signal_config_id": "CFG_B",
                    "event_mask_sha256": "b" * 64,
                    "zero_event_class": False,
                    "trades": weak,
                },
                {
                    "signal_config_id": "CFG_ZERO",
                    "event_mask_sha256": "c" * 64,
                    "zero_event_class": True,
                    "trades": [],
                },
            ],
        }

    def assert_deep_parity(self, a, b, path="root"):
        self.assertEqual(type(a), type(b), path)
        if isinstance(a, dict):
            self.assertEqual(set(a), set(b), path)
            for key in sorted(a):
                self.assert_deep_parity(a[key], b[key], f"{path}.{key}")
        elif isinstance(a, list):
            self.assertEqual(len(a), len(b), path)
            for i, (x, y) in enumerate(zip(a, b)):
                self.assert_deep_parity(x, y, f"{path}[{i}]")
        elif isinstance(a, float):
            if math.isfinite(a) and math.isfinite(b):
                self.assertTrue(math.isclose(a, b, rel_tol=1e-13, abs_tol=1e-13), f"{path}: {a} != {b}")
            else:
                self.assertEqual(a, b, path)
        else:
            self.assertEqual(a, b, path)

    def parity(self, doc):
        primary = score_document(copy.deepcopy(doc))
        oracle = oracle_score_document(copy.deepcopy(doc))
        self.assertEqual(primary["shard_decision"], oracle["shard_decision"])
        self.assertEqual(primary["survivor_count"], oracle["survivor_count"])
        self.assertEqual(
            [r["signal_config_id"] for r in primary["results"]],
            [r["signal_config_id"] for r in oracle["results"]],
        )
        self.assert_deep_parity(primary, oracle)
        return primary, oracle

    def test_oracle_source_has_no_primary_import(self):
        source_path = ROOT / "scripts/qros_first_gate_scorer_oracle_v2.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any("qros_first_gate_scorer_v1" in name for name in imported))

    def test_full_row_by_row_parity_mixed_masks(self):
        self.parity(self.base_doc())

    def test_parity_under_mask_order_permutation(self):
        doc = self.base_doc()
        doc["canonical_masks"] = list(reversed(doc["canonical_masks"]))
        self.parity(doc)

    def test_less_than_30_trade_rule_parity(self):
        doc = self.base_doc()
        doc["canonical_masks"][0]["trades"] = doc["canonical_masks"][0]["trades"][:29]
        primary, _ = self.parity(doc)
        row = {r["signal_config_id"]: r for r in primary["results"]}["CFG_A"]
        self.assertEqual(row["raw_p"], 1.0)
        self.assertFalse(row["candidate_survives"])

    def test_all_negative_shard_rejected_parity(self):
        doc = self.base_doc()
        for mask in doc["canonical_masks"]:
            if not mask["zero_event_class"]:
                for trade in mask["trades"]:
                    trade["r"] = -abs(float(trade["r"]))
        primary, _ = self.parity(doc)
        self.assertEqual(primary["shard_decision"], "REJECTED_FIRST_GATE")
        self.assertEqual(primary["survivor_count"], 0)

    def test_multiple_trades_same_day_and_exit_order_parity(self):
        doc = self.base_doc()
        trades = []
        for i in range(40):
            trades.append(self.trade("C", i, 0.4 if i % 3 else -0.15, day=i // 2, exit_shift=(40 - i)))
        doc["canonical_masks"][0]["trades"] = trades
        self.parity(doc)

    def test_expected_count_mismatch_fails_closed_both(self):
        doc = self.base_doc()
        doc["expected_distinct_mask_classes"] = 4
        with self.assertRaises(ScorerError):
            score_document(copy.deepcopy(doc))
        with self.assertRaises(OracleError):
            oracle_score_document(copy.deepcopy(doc))

    def test_duplicate_mask_sha_fails_closed_both(self):
        doc = self.base_doc()
        doc["canonical_masks"][1]["event_mask_sha256"] = "a" * 64
        with self.assertRaises(ScorerError):
            score_document(copy.deepcopy(doc))
        with self.assertRaises(OracleError):
            oracle_score_document(copy.deepcopy(doc))

    def test_trade_outside_dev_axis_fails_closed_both(self):
        doc = self.base_doc()
        doc["canonical_masks"][0]["trades"][0]["dev_date"] = "2099-01-01"
        with self.assertRaises(ScorerError):
            score_document(copy.deepcopy(doc))
        with self.assertRaises(OracleError):
            oracle_score_document(copy.deepcopy(doc))

    def test_zero_event_with_trade_fails_closed_both(self):
        doc = self.base_doc()
        doc["canonical_masks"][2]["trades"] = [self.trade("Z", 0, 0.0)]
        with self.assertRaises(ScorerError):
            score_document(copy.deepcopy(doc))
        with self.assertRaises(OracleError):
            oracle_score_document(copy.deepcopy(doc))


if __name__ == "__main__":
    unittest.main()
