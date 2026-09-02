import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qros_execution_unit_binding_preflight.py"
spec = importlib.util.spec_from_file_location("qros_execution_unit_binding_preflight", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def valid_packet():
    refs = {
        "prereg_ref": "authority/prereg.json",
        "unit_contract_ref": "authority/unit.json",
        "primary_runner_ref": "authority/primary.py",
        "independent_runner_ref": "authority/independent.py",
    }
    return {
        "request": mod.REQUEST,
        "campaign_id": "QROS_TEST",
        "root_genealogy_id": "G_TEST",
        "frozen_semantics": {
            "stop_family": "ATR_FIXED",
            "atr_stop_mult": 3.0,
            "reward_r_multiple": 1.5,
        },
        "unit_contract": {
            "atr_storage_units_per_raw_quote_unit": 2.0,
            "execution_price_units_per_raw_quote_unit": 1.0,
        },
        "runner_bindings": {
            "primary": {"atr_multiplier": 3.0, "atr_divisor": 2.0, "take_r_multiple": 1.5},
            "independent": {"atr_multiplier": 3.0, "atr_divisor": 2.0, "take_r_multiple": 1.5},
        },
        "synthetic_raw_atr_quote_units": 100.0,
        "authority_refs": refs,
        "authority_sha256": {k: "0" * 64 for k in refs},
    }


class UnitBindingTests(unittest.TestCase):
    def test_double_scale_cache_divide_two_is_three_atr(self):
        receipt = mod.build_receipt(valid_packet())
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["decision"], mod.PASS_DECISION)
        self.assertAlmostEqual(receipt["derived"]["runner_results"]["primary"]["effective_atr_stop_mult"], 3.0)
        self.assertAlmostEqual(receipt["derived"]["runner_results"]["primary"]["synthetic_stop_execution_units"], 300.0)
        self.assertAlmostEqual(receipt["derived"]["runner_results"]["primary"]["synthetic_take_execution_units"], 450.0)

    def test_wrongly_declared_scale_one_exposes_apparent_one_point_five_atr(self):
        packet = valid_packet()
        packet["unit_contract"]["atr_storage_units_per_raw_quote_unit"] = 1.0
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("EFFECTIVE_STOP_MULT_MISMATCH:primary", receipt["failures"])
        self.assertAlmostEqual(receipt["derived"]["runner_results"]["primary"]["effective_atr_stop_mult"], 1.5)

    def test_wrong_divisor_exposes_six_atr(self):
        packet = valid_packet()
        packet["runner_bindings"]["primary"]["atr_divisor"] = 1.0
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("EFFECTIVE_STOP_MULT_MISMATCH:primary", receipt["failures"])
        self.assertAlmostEqual(receipt["derived"]["runner_results"]["primary"]["effective_atr_stop_mult"], 6.0)

    def test_reward_r_mismatch_fails(self):
        packet = valid_packet()
        packet["runner_bindings"]["independent"]["take_r_multiple"] = 2.0
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("REWARD_R_MISMATCH:independent", receipt["failures"])

    def test_missing_scale_fails_closed(self):
        packet = valid_packet()
        del packet["unit_contract"]["atr_storage_units_per_raw_quote_unit"]
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("INVALID_POSITIVE_NUMBER:unit_contract.atr_storage_units_per_raw_quote_unit", receipt["failures"])

    def test_primary_independent_semantic_mismatch_fails(self):
        packet = valid_packet()
        packet["runner_bindings"]["independent"]["atr_divisor"] = 4.0
        receipt = mod.build_receipt(packet)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("PRIMARY_INDEPENDENT_UNIT_SEMANTICS_MISMATCH:effective_atr_stop_mult", receipt["failures"])

    def test_sha_bound_authority_pass_and_tamper_fail(self):
        packet = valid_packet()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for key, rel in packet["authority_refs"].items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f"authority:{key}\n", encoding="utf-8")
                packet["authority_sha256"][key] = hashlib.sha256(p.read_bytes()).hexdigest()
            receipt = mod.build_receipt(packet, repo_root=root)
            self.assertEqual(receipt["status"], "PASS")
            tampered = root / packet["authority_refs"]["unit_contract_ref"]
            tampered.write_text("tampered\n", encoding="utf-8")
            receipt2 = mod.build_receipt(packet, repo_root=root)
            self.assertEqual(receipt2["status"], "FAIL")
            self.assertIn("AUTHORITY_SHA256_MISMATCH:unit_contract_ref", receipt2["failures"])


if __name__ == "__main__":
    unittest.main()
