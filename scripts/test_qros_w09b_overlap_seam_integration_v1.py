#!/usr/bin/env python3
"""Red-team synthetic tests of byte-pinned W09B normalizers at the overlap seam."""
import copy
import shutil
import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import qros_w09b_overlap_seam_integration_v1 as m

class TestW09BOverlapIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="w09b-overlap-")
        cls.root=Path(cls.tmp.name)
        cls.receipt=m.run(cls.root)
        cls.rows=m.fetch_rows(cls.root/"primary")
        cls.scenarios=m.make_fixture()
        cls.by_id={r["scenario_id"]:r for r in cls.rows}
        cls.raw_by_id={r["scenario_id"]:r for r in cls.scenarios}
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_01_exact_source_git_blobs(self):
        self.assertEqual(len(m.verify_exact_source()),5)
        self.assertEqual(m.primary.core.CONTRACT_BLOB,m.CONTRACT)
        self.assertEqual(m.oracle.core.EXPECTED_CONTRACT,m.CONTRACT)
    def test_02_original_normalizers_byte_exact(self):
        a=(self.root/"primary"/"normalized_trades.jsonl").read_bytes()
        b=(self.root/"oracle"/"normalized_trades.jsonl").read_bytes()
        self.assertEqual(a,b)
        self.assertEqual(m.sha(a),self.receipt["normalizer_trades_sha256"])
        self.assertEqual(len(self.rows),13)
    def test_03_overlap_full_chain_admission(self):
        self.assertEqual(self.receipt["admitted_scenario_ids"],["B0","B4","C0","E0","S0","S2"])
        self.assertEqual(self.receipt["rejected_count"],7)
        self.assertFalse(self.receipt["economic_pnl_read"])
        self.assertFalse(self.receipt["production_grant"])
    def test_04_bid_ask_gap_and_stop_priority(self):
        b=self.by_id["B0"];s=self.by_id["S0"]
        self.assertEqual((b["entry_price"],b["exit_price"],b["exit_reason"]),("100.7","98","STOP"))
        self.assertEqual((s["entry_price"],s["exit_price"],s["R"],s["exit_reason"]),("103","105.2","-2.2","STOP"))
    def test_05_equal_timestamp_physical_sequence(self):
        row=self.by_id["E0"]
        self.assertEqual((row["entry_timestamp"],row["entry_price"]),(50,"100.2"))
        side={x["scenario_id"]:x for x in map(json.loads,(self.root/"synthetic_provenance_sidecar.jsonl").read_text().splitlines())}
        self.assertEqual((side["E0"]["entry_carrier_sequence"],side["E0"]["exit_carrier_sequence"]),(10,15))
        switched=copy.deepcopy(self.raw_by_id["E0"])
        first,second=switched["ticks"][9],switched["ticks"][10]
        first["bid"],second["bid"]=second["bid"],first["bid"]
        first["ask"],second["ask"]=second["ask"],first["ask"]
        a=m.primary.core.execute(switched);b=m.oracle.core.normalize_scenario(switched)
        self.assertEqual(a,b);self.assertEqual(a["entry_price"],"101")
    def test_06_future_perturbation_after_close(self):
        for r in self.scenarios:
            altered=copy.deepcopy(r)
            altered["ticks"][-1].update(bid="0.1",ask="0.2")
            self.assertEqual(m.primary.core.execute(r),m.primary.core.execute(altered),r["scenario_id"])
            self.assertEqual(m.oracle.core.normalize_scenario(r),m.oracle.core.normalize_scenario(altered))
    def test_07_future_perturbation_after_stop(self):
        r=copy.deepcopy(self.raw_by_id["S0"])
        b=m.primary.core.execute(r)
        for q in r["ticks"]:
            if q["timestamp"]>25:q.update(bid="150",ask="150.2")
        self.assertEqual(m.primary.core.execute(r),b)
        self.assertEqual(m.oracle.core.normalize_scenario(r),b)
    def test_08_bool_tick_shared_false_pass_and_guard(self):
        r=copy.deepcopy(self.raw_by_id["B0"]);r["ticks"][0]["carrier_sequence"]=True
        self.assertEqual(m.primary.core.execute(r),m.oracle.core.normalize_scenario(r))
        with self.assertRaisesRegex(ValueError,"BOOL_OR_INVALID_TICK_carrier_sequence"):
            m.validate_synthetic_fixture([r])
    def test_09_bool_trigger_shared_false_pass_and_guard(self):
        r=copy.deepcopy(self.raw_by_id["B0"])
        r["event_anchor"].update(entry_trigger_timestamp=True,signal_observable_timestamp=0)
        self.assertEqual(m.primary.core.execute(r),m.oracle.core.normalize_scenario(r))
        with self.assertRaisesRegex(ValueError,"BOOL_OR_INVALID_ANCHOR_TIMESTAMP"):
            m.validate_synthetic_fixture([r])
    def test_10_signal_timestamp_tie_requires_sequence(self):
        r=copy.deepcopy(self.raw_by_id["E0"]);r["event_anchor"]["signal_observable_timestamp"]=50
        a=m.primary.core.execute(r);b=m.oracle.core.normalize_scenario(r)
        self.assertEqual(a,b)
        with self.assertRaisesRegex(ValueError,"SIGNAL_SEQUENCE_REQUIRED_FOR_TIMESTAMP_TIE"):
            m.provenance_sidecar([a],[r])
    def test_11_later_signal_sequence_refused(self):
        r=copy.deepcopy(self.raw_by_id["E0"]);r["event_anchor"].update(signal_observable_timestamp=50,synthetic_signal_available_after_sequence=11)
        self.assertEqual(m.primary.core.execute(r),m.oracle.core.normalize_scenario(r))
        with self.assertRaisesRegex(ValueError,"SIGNAL_AVAILABLE_AFTER_OR_AT_ENTRY_QUOTE"):
            m.provenance_sidecar([m.primary.core.execute(r)],[r])
    def test_12_prior_signal_sequence_accepted_as_synthetic(self):
        r=copy.deepcopy(self.raw_by_id["E0"]);r["event_anchor"].update(signal_observable_timestamp=50,synthetic_signal_available_after_sequence=9)
        self.assertEqual(m.provenance_sidecar([m.primary.core.execute(r)],[r])[0]["signal_available_after_sequence"],9)
    def test_13_raw_tick_tamper_detected_by_sidecar(self):
        r=copy.deepcopy(self.raw_by_id["S0"])
        r["ticks"][5].update(bid="103",ask="103.2") # At original STOP tick: tamper to valid non-stop quote.
        with self.assertRaisesRegex(ValueError,"NORMALIZER_FIELD_MISMATCH_exit_timestamp"):
            m.provenance_sidecar([self.by_id["S0"]],[r])
    def test_14_wrong_quote_spread_guard(self):
        r=copy.deepcopy(self.raw_by_id["B0"]);r["ticks"][1]["ask"]="90"
        for fn,error in [(m.primary.core.execute,m.primary.core.ExecutionError),(m.oracle.core.normalize_scenario,m.oracle.core.OracleFailure)]:
            with self.assertRaises(error):fn(r)
    def test_15_duplicate_sequence_guard(self):
        r=copy.deepcopy(self.raw_by_id["B0"]);r["ticks"][1]["carrier_sequence"]=1
        for fn,error in [(m.primary.core.execute,m.primary.core.ExecutionError),(m.oracle.core.normalize_scenario,m.oracle.core.OracleFailure)]:
            with self.assertRaises(error):fn(r)
    def test_16_broker_date_cannot_be_inferred(self):
        r=copy.deepcopy(self.raw_by_id["B0"]);r["event_anchor"]["synthetic_broker_trading_date"]="bogus"
        with self.assertRaisesRegex(ValueError,"SYNTHETIC_BROKER_DATE_INVALID"):
            m.provenance_sidecar([self.by_id["B0"]],[r])
        # Distinct offsets near NY DST change: examples, NOT proof of Darwinex timezone.
        z=ZoneInfo("America/New_York")
        a=datetime(2025,3,9,6,59,tzinfo=timezone.utc).astimezone(z)
        b=datetime(2025,3,9,7,1,tzinfo=timezone.utc).astimezone(z)
        self.assertNotEqual(a.utcoffset(),b.utcoffset())
    def test_17_equal_trigger_overlap_no_reentry(self):
        a,r=m.overlap.admit_normalized_events(self.rows)
        d={x["scenario_id"]:x for x in r}
        self.assertEqual(d["B3"]["active_exit_timestamp"],35)
        self.assertEqual(d["S1"]["active_exit_timestamp"],25)
    def test_18_provenance_input_hash_changes_after_future_mutation(self):
        r=copy.deepcopy(self.raw_by_id["B0"]);base=m.provenance_sidecar([self.by_id["B0"]],[r])[0]
        r["ticks"][-1].update(bid="0.2",ask="0.4")
        new=m.provenance_sidecar([self.by_id["B0"]],[r])[0]
        self.assertNotEqual(base["source_scenario_sha256"],new["source_scenario_sha256"])
        self.assertEqual(base["entry_carrier_sequence"],new["entry_carrier_sequence"])
    def test_19_same_tick_entry_exit_semantics_underdetermined(self):
        r=m.event("LAST_TICK",trigger=100,stop="95",close=100)
        a=m.primary.core.execute(r);b=m.oracle.core.normalize_scenario(r)
        self.assertEqual(a,b)
        self.assertEqual((a["entry_timestamp"],a["exit_timestamp"],a["exit_reason"]),(100,100,"SAME_DAY"))
        side=m.provenance_sidecar([a],[r])[0]
        self.assertEqual(side["entry_carrier_sequence"],side["exit_carrier_sequence"])
    def test_20_stop_immediate_at_entry_tick_requires_broker_validation(self):
        r=m.event("STOP_ON_ENTRY",trigger=10,stop="100.6",close=100)
        a=m.primary.core.execute(r);b=m.oracle.core.normalize_scenario(r)
        self.assertEqual(a,b)
        self.assertEqual((a["entry_timestamp"],a["exit_timestamp"],a["exit_reason"]),(10,10,"STOP"))
        self.assertEqual(a["R"],"-2") # Entry 100.7, exit Bid 100.5, risk 0.1.
        side=m.provenance_sidecar([a],[r])[0]
        self.assertEqual(side["entry_carrier_sequence"],side["exit_carrier_sequence"])
    def test_21_zero_spread_not_automatically_trusted(self):
        r=m.event("ZERO_SPREAD",trigger=10,stop="90",close=100)
        for q in r["ticks"]:q["ask"]=q["bid"]
        a=m.primary.core.execute(r);b=m.oracle.core.normalize_scenario(r)
        self.assertEqual(a,b)
        self.assertTrue(all(Decimal(t["bid"])==Decimal(t["ask"]) for t in r["ticks"]))
        # Existing contract permits zero-spread ticks; source provenance must classify them.

    def test_22_git_blob_source_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="source-tamper-") as temp:
            d=Path(temp)
            for name in m.verify_exact_source():
                shutil.copy2(Path(m.__file__).resolve().parent/name,d/name)
            (d/"qros_first_gate_execution_normalizer_primary_v1.py").write_bytes(
                (d/"qros_first_gate_execution_normalizer_primary_v1.py").read_bytes()+b"# tamper\n")
            previous=m.__file__
            try:
                m.__file__=str(d/"qros_w09b_overlap_seam_integration_v1.py")
                with self.assertRaisesRegex(ValueError,"EXECUTED_SOURCE_BLOB_DRIFT"):
                    m.verify_exact_source()
            finally:m.__file__=previous
    def test_23_unmodified_w09b_production_mode_remains_closed(self):
        fake={"schema":"QROS_FIRST_GATE_EXECUTION_SYNTHETIC_FIXTURE_1.0",
              "mode":"PRODUCTION","campaign":m.overlap.CAMPAIGN,
              "execution_contract_git_blob_sha1":m.CONTRACT,"synthetic_fixture":False}
        with self.assertRaises(m.primary.core.ExecutionError):m.primary.core.validate_manifest(fake)
        with self.assertRaises(m.oracle.core.OracleFailure):m.oracle.core.header_ok(fake)

if __name__=='__main__':unittest.main(verbosity=2)
