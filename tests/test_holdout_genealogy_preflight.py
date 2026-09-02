import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qros_holdout_genealogy_preflight.py"
spec = importlib.util.spec_from_file_location("qros_holdout_genealogy_preflight", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def valid_packet():
    state = {key: True for key in mod.REQUIRED_TRUE}
    state.update({key: False for key in mod.REQUIRED_FALSE})
    return {
        "request": "OPEN_CLEAN_HOLDOUT",
        "root_genealogy_id": "G_TEST_ROOT",
        "campaign_id": "QROS_TEST_CAMPAIGN",
        "requesting_frontier": "F99_TEST",
        "coverage_receipt_scope": "ROOT_GENEALOGY_COMPLETE",
        "state": state,
        "authority_refs": {
            "ontology_ref": "control/ontology.json",
            "rise_ref": "control/rise.json",
            "ontology_sufficiency_receipt_ref": "control/ontology_audit.json",
            "predevelopment_coverage_receipt_ref": "control/predev_coverage.json",
            "root_pre_holdout_coverage_receipt_ref": "control/root_coverage.json",
            "final_candidate_cohort_ref": "control/final_candidates.json",
            "execution_parity_ref": "control/parity.json",
            "holdout_gate_ref": "control/holdout_gate.json",
            "exposure_ledger_ref": "control/exposure.json",
        },
    }


class HoldoutGenealogyPreflightTests(unittest.TestCase):
    def test_complete_root_genealogy_can_authorize(self):
        receipt = mod.build_receipt(valid_packet())
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["decision"], "HOLDOUT_OPEN_AUTHORIZED")
        self.assertTrue(receipt["economic_read_authorized"])

    def test_stage_only_receipt_cannot_authorize(self):
        packet = valid_packet()
        packet["coverage_receipt_scope"] = "FRONTIER_ONLY"
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["decision"], "HOLDOUT_OPEN_FORBIDDEN")
        self.assertIn("COVERAGE_SCOPE_NOT_ROOT_GENEALOGY_COMPLETE", receipt["failures"])

    def test_open_frontier_blocks_holdout(self):
        packet = valid_packet()
        packet["state"]["any_open_eligible_frontier"] = True
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["decision"], "HOLDOUT_OPEN_FORBIDDEN")
        self.assertIn("REQUIRED_FALSE_FAILED:any_open_eligible_frontier", receipt["failures"])

    def test_prior_genealogy_exposure_blocks_clean_holdout(self):
        packet = valid_packet()
        packet["state"]["holdout_window_already_economically_exposed_for_genealogy"] = True
        packet["state"]["clean_holdout_window_verified_unexposed_for_entire_genealogy"] = False
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["decision"], "HOLDOUT_OPEN_FORBIDDEN")
        self.assertIn(
            "REQUIRED_FALSE_FAILED:holdout_window_already_economically_exposed_for_genealogy",
            receipt["failures"],
        )

    def test_missing_rise_fixed_point_blocks_holdout(self):
        packet = valid_packet()
        packet["state"]["rise_fixed_point"] = False
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("REQUIRED_TRUE_FAILED:rise_fixed_point", receipt["failures"])


if __name__ == "__main__":
    unittest.main()
