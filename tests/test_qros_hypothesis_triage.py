#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "research" / "public_hypotheses" / "qros_hypothesis_triage.py"
if not MODULE_PATH.exists():
    MODULE_PATH = ROOT.parent / "qros_hypothesis_triage.py"
spec = importlib.util.spec_from_file_location("qros_hypothesis_triage", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class PublicHypothesisTriageTests(unittest.TestCase):
    def test_futures_metadata_is_not_future_lookahead(self) -> None:
        code = 'exchanges: [{"eid":"Futures_Binance"}]\nstrategy.entry("L", strategy.long)'
        self.assertNotIn("FUTURE_OR_OFFSET_REVIEW", module.code_flags(code))

    def test_actual_future_or_offset_is_flagged(self) -> None:
        self.assertIn("FUTURE_OR_OFFSET_REVIEW", module.code_flags("plot(x, offset=-1)"))
        self.assertIn("FUTURE_OR_OFFSET_REVIEW", module.code_flags("future value"))

    def test_public_entry_without_exit_is_flagged(self) -> None:
        self.assertIn("NO_EXPLICIT_EXIT_CALL", module.code_flags('strategy.entry("L", strategy.long)'))

    def test_magic_channel_override_binds_g31(self) -> None:
        override = module.MANUAL_OVERRIDES["FMZ:458067"]
        self.assertEqual(override["classification"], "COVERED_G31_ICHIMOKU")

    def test_mama_override_accepts_hypothesis_not_public_runner(self) -> None:
        override = module.MANUAL_OVERRIDES["FMZ:430662"]
        self.assertEqual(override["review"], "PASS_ROOT_HYPOTHESIS_WITH_HARDENING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
