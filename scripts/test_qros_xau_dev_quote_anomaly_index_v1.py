#!/usr/bin/env python3
"""Tamper, physical-index and raw-domain regression tests (no economic data)."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import qros_xau_dev_quote_anomaly_index_v1 as m

DATA=Path('/mnt/data/qros_data_dev/quote_anomaly_index_v1')

class TestQuoteQualityIndex(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.meta=json.loads((DATA/'manifest.json').read_text())
  cls.zero=m.decode_index(DATA/'zero_spread_indices.u32le.zlib',cls.meta['artifacts']['zero_spread_indices.u32le.zlib'])
  cls.cross=m.decode_index(DATA/'crossed_quote_indices.u32le.zlib',cls.meta['artifacts']['crossed_quote_indices.u32le.zlib'])
 def test_01_counts_match_full_scan(self):
  self.assertEqual((len(self.zero),len(self.cross)),(942184,74))
  self.assertEqual(sum(x['zero'] for x in self.meta['chunk_counts']),942184)
  self.assertEqual(sum(x['crossed'] for x in self.meta['chunk_counts']),74)
 def test_02_raw_index_membership(self):
  self.assertEqual(int(self.zero[0]),1538)
  self.assertEqual(int(self.cross[0]),2151910)
  self.assertTrue(m.intersects_sorted(self.cross,2151900,2151920))
  self.assertFalse(m.intersects_sorted(self.cross,100,1000))
  self.assertFalse(m.intersects_sorted(self.cross,60000000,151382387))
 def test_03_disjoint_sorted_indices(self):
  self.assertEqual(np.intersect1d(self.zero,self.cross).size,0)
  self.assertTrue(np.all(self.zero[1:]>self.zero[:-1]))
  self.assertTrue(np.all(self.cross[1:]>self.cross[:-1]))
 def test_04_tampered_compressed_payload_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'tampered.zlib';blob=(DATA/'crossed_quote_indices.u32le.zlib').read_bytes()
   p.write_bytes(blob[:-1]+bytes([blob[-1]^1]))
   with self.assertRaisesRegex(ValueError,'INDEX_COMPRESSED_HASH_MISMATCH'):
    m.decode_index(p,self.meta['artifacts']['crossed_quote_indices.u32le.zlib'])
 def test_05_valid_binary_false_metadata_rejected(self):
  x=copy.deepcopy(self.meta['artifacts']['crossed_quote_indices.u32le.zlib']);x['raw_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'INDEX_RAW_HASH_MISMATCH'):
   m.decode_index(DATA/'crossed_quote_indices.u32le.zlib',x)
 def test_06_unsorted_or_duplicate_indices_rejected(self):
  for arr in ([2,1],[3,3]):
   with self.assertRaisesRegex(ValueError,'UNSORTED_OR_BAD_GLOBAL_INDEX'):m.checked_encoded(arr)
 def test_07_empty_window_and_overlapping_boundary(self):
  self.assertFalse(m.intersects_sorted(self.zero,1539,1539))
  self.assertTrue(m.intersects_sorted(self.zero,1538,1538))
 def test_08_never_authorizes_economic_scoring(self):
  self.assertFalse(self.meta['rules']['economic_pnl_read'])
  self.assertEqual(self.meta['rules']['mask_overlap'],'NOT_EVALUATED')
  self.assertEqual(self.meta['rules']['session_timezone'],'UNBOUND')

if __name__=='__main__':unittest.main(verbosity=2)
