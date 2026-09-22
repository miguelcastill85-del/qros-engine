#!/usr/bin/env python3
"""Synthetic read-only tests: missing inputs are explicit, no PnL/gate changes."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import qros_seed0076_xau_group00_preflight_v1 as q
ROOT=Path('/mnt/data')
class Group00Preflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=q.verify(base=ROOT,source=ROOT/'qros_group00_frozen_source',check_heavy=False)
    def test_descriptor_frozen_and_hash(self):
        d=q.build_descriptor();self.assertEqual(d['descriptor_sha256'],q.FROZEN['shard_id'])
    def test_full_carriers_present(self):
        self.assertEqual(self.report['verified_cache_files'],34)
        self.assertEqual(len({x['tf'] for x in self.report['verified_caches']}),17)
    def test_only_missing_code_not_missing_data(self):
        self.assertEqual(self.report['local_admission'],'INPUT_CARRIERS_PASS_SOURCE_CODE_CLOSURE_MISSING')
        self.assertEqual(len(self.report['missing_source_closure']),6)
    def test_group00_expected(self):
        self.assertEqual(q.FROZEN['group_configs'],33528)
        self.assertEqual(q.FROZEN['group_local_distinct']+q.FROZEN['group_local_duplicates'],33528)
    def test_mutated_descriptor_fails(self):
        with patch.dict(q.FROZEN,{'shard_id':'0'*64}):
            with self.assertRaisesRegex(q.PreflightError,'FROZEN_SHARD_ID_MISMATCH'):q.build_descriptor()
    def test_corrupted_present_worker_fails(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'qros_seed0076_ga1_shard_worker_v223.py').write_text('fake\n')
            with self.assertRaisesRegex(q.PreflightError,'GIT_SOURCE_BLOB_DRIFT'):
                q.verify(base=ROOT,source=td,check_heavy=False)
    def test_missing_dev_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(q.PreflightError,'XAU_DEV_MISSING_OR_SIZE_DRIFT'):
                q.verify(base=td,source=td,check_heavy=False)
    def test_missing_spec_is_explicit(self):
        self.assertIn('QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json',
                      [x['file'] for x in self.report['missing_source_closure']])
    def test_frozen_clock_guard(self):
        self.assertIn('quarantine 28 early 2018',self.report['clock_warning'])
    def test_conservative_compression_gate(self):
        self.assertIn('uncompressed group00 SHA256',self.report['admission_after_group_replay'])
    def test_no_pnl_and_no_shard11(self):
        self.assertFalse(self.report['economic_pnl_read']);self.assertFalse(self.report['holdout_open']);self.assertFalse(self.report['shard11_open'])
    def test_frozen_raw_group_sha(self):
        self.assertEqual(q.FROZEN['group_original_delta_u32_sha256'],'ff55eb32bddddff384736644888aff775c760b2e9f79c72d7ce328cf6b9c03cd')
if __name__=='__main__':unittest.main(verbosity=2)
