"""Adversarial fixtures never use historical PnL or simulate real parity evidence."""
import base64, copy, hashlib, json, pathlib, sys, tempfile, time, unittest
HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(HERE))
import qros_fast_frontier_v2 as f
BASE=pathlib.Path('/mnt/data/w5_v33_446_library_readback/QROS_W5_V33_VERIFIED_446_OF_710_MASK_PARITY_SHARDS_20260925.zip')

class FastFrontierTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.frontier,cls.index,cls.real_receipt=f.audit_baseline(BASE)
  cls.f_raw=f.canon(cls.frontier);cls.f_git=f.git_blob(cls.f_raw);cls.idx_raw=f.canon(cls.index)
  cls.sample=cls.frontier['next_by_channel']['0'][0]
  cls.sample2=cls.frontier['next_by_channel']['0'][1]
 @classmethod
 def sample_receipt(cls,t):
  # SYNTHETIC fixtures only, never promoted into the scientific branch.
  return f.canon({'schema':'QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1','channel':t['ch'],'route':t['route'],'ordinals':t['ordinals'],'tested_mask_occurrences':len(t['ordinals']),'tests':[{'ordinal':x,'zero_signal_mask':True,'all_rejections_equal':True,'independent_exact_trades':0,'11_fields_compared':0,'PNL_blind_sampled_source_signals':0} for x in t['ordinals']],'plan_SHA256':f.ORIGINAL_PLAN_SHA,'original_raw_sha256':f.ORIGINAL_RAW_SHA,'status':'PASS','new_economic_PNL':False,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'independent_exact_trades':0,'exact_fields':0,'sampled_signals':0})
 @classmethod
 def name(cls,t):return 'CH%d_%s_I%03d_%03d.json'%(t['ch'],t['route'],t['ordinals'][0],t['ordinals'][-1])
 @classmethod
 def advance(cls,n=1):
  ts=cls.frontier['next_by_channel']['0'][:n]
  return f.build_advance(cls.f_raw,cls.f_git,cls.idx_raw,{cls.name(t):cls.sample_receipt(t) for t in ts},'DELTA_0001.json')
 @classmethod
 def mock_authority(cls,frontier_raw,frontier_git,target=b'{"t":1}\n',anchor=b'{"a":1}\n'):
  front=json.loads(frontier_raw)
  pointer={'schema':f.POINTER_SCHEMA,'target_git_blob_sha1':f.git_blob(target),'last_closed_remote_anchor_blob_sha1':f.git_blob(anchor),'v33_shards_completed':front['completed'],'fast_frontier_v2':{'git_blob_sha1':frontier_git,'sequence':front['sequence'],'ledger_root_sha256':front['ledger_root_sha256']},'Gate_A_approved':False,'holdout_open':False,'ga2_open':False}
  return f.canon(pointer),target,anchor
 def test_01_cold_archive_sha_blob_and_full_452_member_proof(self):
  self.assertEqual(self.real_receipt['status'],'BASELINE_446_FULL_REHASH_PASS');self.assertEqual(self.real_receipt['manifest_members'],452)
 def test_02_710_unique_ids_and_446_bit_count(self):
  self.assertEqual(len({f.task_key(t) for t in self.index['tasks']}),710);self.assertEqual(f.bits(f.bitraw(self.frontier['bitmap_b64'])),446)
 def test_03_frontier_sha_immutable(self):self.assertEqual(self.f_git,'4717379067d5226bc3d760c7b9877a444affab20')
 def test_04_initial_check_without_baseline_transfer(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git)
  out=f.fast_resume(p,f.git_blob(p),self.f_raw,self.f_git,t,f.git_blob(t),a,f.git_blob(a),idx_raw=self.idx_raw)
  self.assertFalse(out['full_zip_transfer_required']);self.assertEqual(out['prior_receipts_replayed_in_this_check'],0);self.assertEqual(out['verified_completed'],446)
 def test_05_fast_check_without_optional_index(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git)
  self.assertEqual(f.fast_resume(p,f.git_blob(p),self.f_raw,self.f_git,t,f.git_blob(t),a,f.git_blob(a))['verified_completed'],446)
 def test_06_previous_git_pointer_tamper_refused(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git)
  with self.assertRaisesRegex(f.Refuse,'LIVE_POINTER'):f.fast_resume(p+b' ',f.git_blob(p),self.f_raw,self.f_git,t,f.git_blob(t),a,f.git_blob(a))
 def test_07_stale_current_science_count_refused(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git);obj=json.loads(p);obj['v33_shards_completed']=447;p=f.canon(obj)
  with self.assertRaisesRegex(f.Refuse,'COUNT'):f.fast_resume(p,f.git_blob(p),self.f_raw,self.f_git,t,f.git_blob(t),a,f.git_blob(a))
 def test_08_corrupted_frontier_bitmap_refused(self):
  v=copy.deepcopy(self.frontier);v['bitmap_b64']=base64.b64encode(b'\x00'*89).decode()
  with self.assertRaisesRegex(f.Refuse,'COUNT'):f.check_frontier(v,self.index)
 def test_09_forbidden_gate_refused(self):
  v=copy.deepcopy(self.frontier);v['holdout_open']=True
  with self.assertRaisesRegex(f.Refuse,'GUARD'):f.check_frontier(v)
 def test_10_frozen_index_edit_refused(self):
  v=copy.deepcopy(self.index);v['tasks'][0]['route']='injected'
  with self.assertRaisesRegex(f.Refuse,'INDEX_PIN'):f.check_frontier(self.frontier,v)
 def test_11_1_to_6_fixture_delta_accepts_and_full_local_loop(self):
  nf,delta,proof=self.advance(6);n=json.loads(nf);self.assertEqual(n['completed'],452);self.assertEqual(proof['new'],6)
  self.assertEqual(f.check_delta(delta,n)['previous_count'],446)
  p,t,a=self.mock_authority(nf,f.git_blob(nf))
  out=f.fast_resume(p,f.git_blob(p),nf,f.git_blob(nf),t,f.git_blob(t),a,f.git_blob(a),latest_delta_raw=delta,idx_raw=self.idx_raw)
  self.assertEqual(out['latest_delta_receipts_rehashed'],6);self.assertEqual(out['prior_receipts_replayed_in_this_check'],0)
 def test_12_duplicate_fixture_task_refused(self):
  raw=self.sample_receipt(self.sample);nm=self.name(self.sample)
  with self.assertRaisesRegex(f.Refuse,'NEW_TASK_ALREADY_COMPLETE'):
   ff,dd,proof=self.advance(1);f.build_advance(ff,f.git_blob(ff),self.idx_raw,{nm:raw},'DELTA_0002.json')
 def test_13_skip_out_of_order_fixture_refused(self):
  with self.assertRaisesRegex(f.Refuse,'NONCONTIGUOUS'):
   t=self.sample2;f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(t):self.sample_receipt(t)},'DELTA_0001.json')
 def test_14_seventh_unpublished_fixture_refused(self):
  t=self.frontier['next_by_channel']['0'];seven=t+[next(x for x in self.index['tasks'] if x['ch']==0 and f.task_key(x) not in {f.task_key(y) for y in t} and not f.isset(f.bitraw(self.frontier['bitmap_b64']),self.index['tasks'].index(x))) ]
  with self.assertRaisesRegex(f.Refuse,'MAX_SIX'):
   f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(y):self.sample_receipt(y) for y in seven},'DELTA_0001.json')
 def test_15_mixed_channels_fixture_refused(self):
  t=self.frontier['next_by_channel']['4'][0]
  with self.assertRaisesRegex(f.Refuse,'MIXED_CHANNELS'):
   f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(x):self.sample_receipt(x) for x in (self.sample,t)},'DELTA_0001.json')
 def test_16_new_receipt_falsified_11_fields_refused(self):
  raw=json.loads(self.sample_receipt(self.sample));raw['exact_fields']=11
  with self.assertRaisesRegex(f.Refuse,'FIELDS_SUM'):
   f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(self.sample):f.canon(raw)},'DELTA_0001.json')
 def test_17_tampered_latest_delta_refused(self):
  nf,delta,_=self.advance(1);n=json.loads(nf);d=json.loads(delta);d['previous_bitmap_sha256']='0'*64
  with self.assertRaisesRegex(f.Refuse,'LATEST_DELTA_HASH'):f.check_delta(f.canon(d),n)
 def test_18_even_refreshed_delta_hash_cannot_hide_wrong_prev_bitmap(self):
  nf,delta,_=self.advance(1);n=json.loads(nf);d=json.loads(delta);d['previous_bitmap_sha256']='0'*64;b=f.canon(d);n['latest_delta_sha256']=f.digest(b);n['latest_delta_git_blob_sha1']=f.git_blob(b)
  with self.assertRaisesRegex(f.Refuse,'PREVIOUS_BITMAP'):f.check_delta(b,n)
 def test_19_changed_pinned_target_blob_refused(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git)
  with self.assertRaisesRegex(f.Refuse,'HANDOFF'):f.fast_resume(p,f.git_blob(p),self.f_raw,self.f_git,t+b' ',f.git_blob(t),a,f.git_blob(a))
 def test_20_resume_two_generations_only_rehash_latest_delta(self):
  f1,d1,_=self.advance(1);n1=json.loads(f1);next_task=n1['next_by_channel']['0'][0]
  f2,d2,_=f.build_advance(f1,f.git_blob(f1),self.idx_raw,{self.name(next_task):self.sample_receipt(next_task)},'DELTA_0002.json')
  p,t,a=self.mock_authority(f2,f.git_blob(f2));o=f.fast_resume(p,f.git_blob(p),f2,f.git_blob(f2),t,f.git_blob(t),a,f.git_blob(a),latest_delta_raw=d2)
  self.assertEqual((o['sequence'],o['verified_completed'],o['latest_delta_receipts_rehashed'],o['prior_receipts_replayed_in_this_check']),(2,448,1,0))
 def test_21_latest_delta_payload_tamper_with_stale_digest_refused(self):
  nf,d,_=self.advance(1);z=bytearray(d);z[-2]=ord(' ')
  with self.assertRaisesRegex(f.Refuse,'LATEST_DELTA_HASH'):f.check_delta(bytes(z),json.loads(nf))
 def test_22_duplicate_zero_signal_test_order_refused(self):
  r=json.loads(self.sample_receipt(self.sample));r['tests'][0]['ordinal']=r['tests'][1]['ordinal']
  with self.assertRaisesRegex(f.Refuse,'TEST_ORDINAL'):
   f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(self.sample):f.canon(r)},'DELTA_0001.json')
 def test_23_exact_existing_plan_and_raw_PIN_required(self):
  r=json.loads(self.sample_receipt(self.sample));r['plan_SHA256']='0'*64
  with self.assertRaisesRegex(f.Refuse,'SOURCE_DRIFT'):
   f.build_advance(self.f_raw,self.f_git,self.idx_raw,{self.name(self.sample):f.canon(r)},'DELTA_0001.json')
 def test_24_performance_benchmark_under_local_CPU_only(self):
  p,t,a=self.mock_authority(self.f_raw,self.f_git)
  begin=time.perf_counter()
  for _ in range(50):f.fast_resume(p,f.git_blob(p),self.f_raw,self.f_git,t,f.git_blob(t),a,f.git_blob(a))
  duration=time.perf_counter()-begin
  print('LOCAL_FAST_50_TURNS_SECONDS',round(duration,5))
  self.assertLess(duration,5)

 def test_25_twenty_batch_reaudit_required_and_certification_opens_next_cycle(self):
  with tempfile.TemporaryDirectory() as tmp:
   cur=self.f_raw;files=[]
   for n in range(1,21):
    x=json.loads(cur)['next_by_channel']['0'][0]
    f2,delta,_=f.build_advance(cur,f.git_blob(cur),self.idx_raw,{self.name(x):self.sample_receipt(x)},'DELTA_%04d.json'%n)
    path=pathlib.Path(tmp)/('DELTA_%04d.json'%n);path.write_bytes(delta);files.append(path);cur=f2
   self.assertEqual(json.loads(cur)['completed'],466)
   x=json.loads(cur)['next_by_channel']['0'][0]
   with self.assertRaisesRegex(f.Refuse,'FULL_REAUDIT_REQUIRED'):
    f.build_advance(cur,f.git_blob(cur),self.idx_raw,{self.name(x):self.sample_receipt(x)},'DELTA_0021.json')
   proof=f.replay_full_audit(BASE,files,cur,f.git_blob(cur))
   self.assertEqual(proof['delta_files_rehashed'],20)
   certified=f.certify_full_audit(cur,f.git_blob(cur),f.canon(proof),f.git_blob(f.canon(proof)))
   advanced,_,z=f.build_advance(certified,f.git_blob(certified),self.idx_raw,{self.name(x):self.sample_receipt(x)},'DELTA_0021.json')
   self.assertEqual(z['total'],467)
   self.assertEqual(json.loads(advanced)['full_audit_history'][0]['sequence'],20)
 def test_26_reaudit_bad_historic_certificate_refused(self):
  v=copy.deepcopy(self.frontier);v['full_audit_history']=[{'sequence':20,'receipt_git_blob_sha1':'a'*40}]
  raw=f.canon(v)
  with self.assertRaisesRegex(f.Refuse,'HISTORIC_REAUDIT_CERTIFICATES_MISSING'):
   f.replay_full_audit(BASE,[],raw,f.git_blob(raw))

if __name__=='__main__':unittest.main(verbosity=2)
