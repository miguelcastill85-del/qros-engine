#!/usr/bin/env python3
"""Isolated adversarial clock tests. Never writes or modifies source science bytes."""
import hashlib
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
import qros_seed0076_xau_clock_audit_v1 as x

B=Path('/mnt/data/qros_bar_cache/XAUUSD_M1_BID_BARS.npy')
T=Path('/mnt/data/qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin')
A=Path('/mnt/data/qros_seed0076_delta_20260922/XAU_QUOTE_ANOMALY_DIRECT_BAR_MEMBERSHIP_17TF.npz')

class FrozenClockAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=x.audit(B,T,A,include_data_hash=False)
        cls.v=cls.report['verified']
    def test_01_byte_boundaries_exact(self):
        self.assertTrue(self.v['tick_source_index_contiguous_all_bars'])
        self.assertTrue(self.v['tick_to_bar_boundary_all_bars'])
        self.assertEqual(self.v['m1_bars'],681772)
    def test_02_timezone_winter_2018(self):
        z=x.server_clock_resolve(datetime(2018,3,9,12))
        self.assertEqual(z['server_utc_offset_hours'],2)
        self.assertTrue(z['ny_civil'].startswith('2018-03-09T05:00'))
    def test_03_timezone_summer_2018(self):
        z=x.server_clock_resolve(datetime(2018,3,12,12))
        self.assertEqual(z['server_utc_offset_hours'],3)
    def test_04_DST_november_2018(self):
        self.assertEqual(x.server_clock_resolve(datetime(2018,11,2,12))['server_utc_offset_hours'],3)
        self.assertEqual(x.server_clock_resolve(datetime(2018,11,5,12))['server_utc_offset_hours'],2)
    def test_05_four_real_transitions(self):
        d=self.v['four_dst_witnesses'];self.assertEqual(len(d),4)
        self.assertEqual([a['before']['server_utc_offset_hours'] for a in d],[2,3,2,3])
        self.assertEqual([a['after']['server_utc_offset_hours'] for a in d],[3,2,3,2])
    def test_06_london_dst_mismatch_does_not_change_us_server(self):
        # London switched on 2018-10-28; US DST ended 2018-11-04.
        self.assertEqual(x.server_clock_resolve(datetime(2018,10,29,12))['server_utc_offset_hours'],3)
    def test_07_preopen_exact_28_quarantined(self):
        self.assertEqual(self.v['out_of_frozen_XAU_1801_NY_window_M1_bars'],28)
        self.assertTrue(self.v['all_out_of_window_bars_at_source_server_0100'])
        self.assertTrue(self.v['early_first_server_label'].startswith('2018-01-26'))
        self.assertTrue(self.v['early_last_server_label'].startswith('2018-03-07'))
    def test_08_early_anomaly_is_not_global_rejection(self):
        self.assertEqual(self.v['early_source_ticks_in_28_bars'],1742)
        self.assertEqual(self.v['early_M1_bars_directly_crossed'],0)
        self.assertEqual(self.v['early_M1_bars_directly_zero_spread'],1)
        self.assertGreater(self.v['m1_bars']-28,681000)
    def test_09_source_data_is_economically_sealed(self):
        self.assertEqual(self.report['scientific_state'],'PREREGISTERED_NO_RESULTS')
        self.assertFalse(self.report['economic_pnl_read'])
        self.assertFalse(self.report['holdout_open'])
        self.assertFalse(self.report['production_grant'])
    def test_10_bad_bar_sha_fails_closed_even_same_schema(self):
        with patch.dict(x.FROZEN,{'bar_sha256':'0'*64}):
            with self.assertRaisesRegex(x.AuditError,'BAR_SHA256_DRIFT'):
                x.audit(B,T,A,include_data_hash=False)
    def test_11_bad_anomaly_sha_fails_closed(self):
        with patch.dict(x.FROZEN,{'anomaly_index_sha256':'0'*64}):
            with self.assertRaisesRegex(x.AuditError,'ANOMALY_SHA256_DRIFT'):
                x.audit(B,T,A,include_data_hash=False)
    def test_12_invalid_datetime_rejected_by_zone_roundtrip(self):
        # Sunday DST spring gap: 02:30 America/New_York civil never existed.
        # Darwinex has no market data in that weekend; synthetic invalid label rejected.
        with self.assertRaisesRegex(x.AuditError,'NY_WALL_ROUNDTRIP_FAIL'):
            x.server_clock_resolve(datetime(2018,3,11,9,30)) # server minus 7h = NY 02:30
    def test_13_no_lagging_future_in_clock_transform(self):
        t=datetime(2018,3,12,12)
        a=x.server_clock_resolve(t)
        # Adding future day labels has no input into resolving an earlier label.
        future=x.server_clock_resolve(t+timedelta(days=30))
        self.assertEqual(x.server_clock_resolve(t),a)
        self.assertNotEqual(future['ny_civil'],a['ny_civil'])
    def test_14_frozen_binding_ids_present(self):
        self.assertEqual(x.FROZEN['clock_policy_git_blob_sha1'],'c16d561b66a51d3735960470ba893e53e6913d40')
        self.assertEqual(x.FROZEN['session_policy_git_blob_sha1'],'e841166c558c93a15fef16f174e55449b1f8164d')

if __name__=='__main__':unittest.main(verbosity=2)
