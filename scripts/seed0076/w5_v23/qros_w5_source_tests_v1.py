import hashlib,json,pathlib,sys,unittest,tempfile
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from qros_w5_pre_econ_v1 import check_source,loadmodule,SOURCES,V209,oracle_fractal,guarded_raw_oracle,valid_quote,valid_tick_tests,check_mtf,verify_ids,sha,blob
from qros_w5_mtf_causal_adapter_v1 import causal_context_index,causal_gate_context_class,causal_mtf_eval
class W5SourceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.orig=loadmodule('frozen_structural',SOURCES/'qros_seed0076_structural_v220.py')
  cls.v221=loadmodule('frozen_gates',SOURCES/'qros_seed0076_gate_engine_v221.py')
 def test_official_pins(self):self.assertEqual(len(check_source()[0]),4)
 def test_prereg_one_cell(self):
  p=check_source()[1];self.assertEqual(p['campaign_id'],'QROS_WEB_SEED0076_XAUUSD_M1_W5_ASYM_REARM0_TICK_FULL_V209_20260924')
 def test_all_11176_package_ids(self):self.assertEqual(verify_ids()['ids_each_side'],{'BUY':11176,'SELL':11176})
 def test_primary_independent_synthetic_oracles(self):self.assertEqual(valid_tick_tests(self.orig)['rearm_buy_sell'],'PASS')
 def test_v221_mtf_delay_reproduced(self):self.assertEqual(check_mtf(self.v221)['original_v221_mtf_at_exact_completion'],'ONE_COMPLETED_BAR_LATE')
 def test_corrected_mtf_boundary(self):
  b=np.array([(10,),(60,),(115,),(170,)],dtype=[('first_source_index','<i8')]);ts=np.array([9,10,59,60,61,114,115,169,170,171]);self.assertEqual(causal_context_index(b,ts).tolist(),[-1,-1,-1,0,0,0,1,1,2,2])
 def test_mtf_random_no_future(self):
  rng=np.random.default_rng(7606)
  for _ in range(25):
   first=np.cumsum(rng.integers(1,60,20)).astype(np.int64)
   bars=np.zeros(len(first),dtype=[('first_source_index','<i8')]);bars['first_source_index']=first
   signal=np.sort(rng.integers(0,int(first[-1])+100,size=200));indexes=causal_context_index(bars,signal)
   for t,idx in zip(signal,indexes):
    if idx>=0:self.assertLessEqual(first[idx+1],t)
    self.assertLess(idx,len(first)-1)
 def test_mtf_invalid_monotonic_rejected(self):
  bars=np.array([(10,),(10,),(30,)],dtype=[('first_source_index','<i8')]);self.assertRaisesRegex(ValueError,'NON_MONOTONIC',causal_context_index,bars,[15])
 def test_corrected_adapter_is_not_mutation(self):
  cls=causal_gate_context_class(self.v221);self.assertTrue(issubclass(cls,self.v221.GateContext));self.assertIsNot(cls,self.v221.GateContext)
 def test_gate_mtf_rsi_buy_sell(self):
  b=np.zeros(4,dtype=[('first_source_index','<i8')]);b['first_source_index']=[10,60,110,160]
  values={'RSI14':np.array([55.,45.,65.,35.])}
  loader=lambda tf:(b,values)
  for side,expected in [('BUY',[False,True,True,False,False,True]),('SELL',[False,False,False,True,True,False])]:
   got=causal_mtf_eval(self.v221,loader,'M1',np.array([59,60,109,110,159,160]),side,{'rule':'NEXT_HIGHER_RSI_DIRECTIONAL_50'})
   self.assertEqual(got.tolist(),expected)
 def test_zero_crossed_nonpositive_quotes(self):
  b=np.array([100,101,102,103,104],np.int64);a=np.array([101,101,101,105,-1],np.int64)
  self.assertEqual(valid_quote(b,a).tolist(),[True,False,False,True,False])
 def test_invalid_bid_ask_event_filtered(self):
  b=np.array([99,101,99,101,99,101],np.int64);a=np.array([101,101,101,101,100,103],np.int64)
  events=guarded_raw_oracle(b,a,np.array([0]),np.array([5]),np.array([100.]),np.array([7]),np.array([1.]),1,1.)
  self.assertEqual([e[0] for e in events[0]],[5])
 def test_invalid_crossed_event_filtered_sell(self):
  b=np.array([102,99,101,99],np.int64);a=np.array([103,98,102,100],np.int64)
  events=guarded_raw_oracle(b,a,np.array([0]),np.array([3]),np.array([100.]),np.array([7]),np.array([1.]),-1,1.)
  self.assertEqual([e[0] for e in events[0]],[3])
 def test_fractal_equal_right_rejected(self):
  h=np.array([1,3,5,2,5,1,2],float);l=-h;obs=oracle_fractal(h,l,5)
  self.assertNotEqual(obs[2][5],2) # later equal right neighbor invalidates center
 def test_fractal_prefix_one_bar_delay(self):
  h=np.array([1,2,8,2,1,4,2],float);l=-h
  sh,sl,hi,li=oracle_fractal(h,l,5);self.assertEqual(hi[4],-1);self.assertEqual(hi[5],2)
 def test_frozen_source_tamper_detected(self):
  p=SOURCES/'qros_seed0076_structural_v220.py';data=p.read_bytes();self.assertEqual(blob(data),'805044c9918a87456a95e150a1c9a1292112cf4c');self.assertNotEqual(blob(data+b'\n#tampered'),'805044c9918a87456a95e150a1c9a1292112cf4c')
 def test_no_holdout_gate(self):self.assertFalse(check_source()[1]['scientific_firewalls']['holdout_open'])
 def test_no_ga2_gate(self):self.assertFalse(check_source()[1]['scientific_firewalls']['GA2_open'])
 def test_original_v221_gate_context_not_full_ten(self):
  import inspect
  src=inspect.getsource(self.v221.GateContext.eval_family)
  self.assertNotIn("family=='RETEST_ENTRY'",src)
  self.assertNotIn("family=='BREAKOUT_BUFFER'",src)
 def test_both_missing_families_are_pretrigger_overlays(self):
  p=check_source()[1];self.assertIn('raw_trigger',p['causal_contract']);self.assertIn('retest',p['causal_contract']);self.assertIn('BREAKOUT_BUFFER',p['expected_original_V209_filter_families'])
 def test_config_id_stream_no_buy_sell_alias(self):
  a=(V209/'BUY_CONFIG_IDS_11176.bin').read_bytes();b=(V209/'SELL_CONFIG_IDS_11176.bin').read_bytes();self.assertFalse(set(a[i:i+32] for i in range(0,len(a),32))&set(b[i:i+32] for i in range(0,len(b),32)))
if __name__=='__main__':unittest.main(verbosity=2)
