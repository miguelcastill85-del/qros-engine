import tempfile,pathlib,unittest,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import qros_w5_realdata_preflight_v1 as m
class DataPreflight(unittest.TestCase):
 def test_exact_historical_file_absent_stops(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertRaisesRegex(ValueError,'NOT_MATERIALIZED',m.verify,pathlib.Path(td)/'not_there.bin',m.PINS['ticks'])
 def test_wrong_length_does_not_reach_memory_map(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'fake.bin';p.write_bytes(b'not really 2.57 GB');self.assertRaisesRegex(ValueError,'BYTES_MISMATCH',m.verify,p,m.PINS['ticks'])
 def test_wrong_hash_never_certifies_bars(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'fake.bin';p.write_bytes(b'a'*17)
   self.assertRaisesRegex(ValueError,'SHA256_MISMATCH',m.verify,p,{'bytes':17,'sha256':m.PINS['ticks']['sha256']})
 def test_exact_raw_shape_pin(self):self.assertEqual(m.PINS['ticks']['bytes'],m.PINS['ticks']['rows']*17)
 def test_protected_holdout_not_an_input(self):self.assertEqual(set(m.PINS),{'ticks','bars','indicators'})
if __name__=='__main__':unittest.main(verbosity=2)
