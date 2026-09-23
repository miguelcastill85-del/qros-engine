import copy,hashlib,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from qros_authority_reconciler_v2_1 import reconcile,AuthorityIncident
class Reconcile(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.t.name)/'snap.json'
  self.s={'schema':'QROS_CONNECTED_AUTHORITY_SNAPSHOT_V2_1','lane':{'scope':'SEED0076_DIRECT_DEV','branch':'research/seed0076-direct-dev-backtest-20260922','branch_tree_sha':'a'*40},'drive_folder_id':'folder','baseline':{'stage':'W9','git_blob_sha1':'f'*40,'zip_sha256':'4'*64,'drive_id':'base','zip_bytes':100,'drive_connector_readback':{'id':'base','size':'100','parent_id':'folder'},'cumulative_configs':0,'cumulative_masks':0},
          'records':[{'seq':1,'stage':'W11','status':'PASS','git_blob_sha1':'b'*40,'git_path':'control/W11.json','drive_id':'w11','drive_connector_readback':{'id':'w11','size':'100','parent_id':'folder'},'zip_bytes':100,'zip_sha256':'1'*64,'new_configs':10,'new_masks':8,'cumulative_configs':10,'cumulative_masks':8,'next_action':'W13'},
                     {'seq':2,'stage':'W13','status':'PASS','git_blob_sha1':'c'*40,'git_path':'control/W13.json','drive_id':'w13','drive_connector_readback':{'id':'w13','size':'50','parent_id':'folder'},'zip_bytes':50,'zip_sha256':'2'*64,'new_configs':10,'new_masks':7,'cumulative_configs':20,'cumulative_masks':15,'next_action':'AUDIT'},
                     {'seq':3,'stage':'AUDIT','status':'PASS','git_blob_sha1':'d'*40,'git_path':'control/AUDIT.json','drive_id':'audit','drive_connector_readback':{'id':'audit','size':'20','parent_id':'folder'},'zip_bytes':20,'zip_sha256':'3'*64,'new_configs':0,'new_masks':0,'cumulative_configs':20,'cumulative_masks':15,'next_action':'W3_STRICT'}],
          'preregistered_next_action':'W3_STRICT','holdout_open':False,'new_old_shard_ga1_authorized':False}
 def tearDown(self):self.t.cleanup()
 def runr(self):
  raw=json.dumps(self.s,sort_keys=True).encode();self.path.write_bytes(raw);return reconcile(self.path,hashlib.sha256(raw).hexdigest(),'a'*40)
 def test_recover_ahead_without_rerunning_old_stage(self):self.assertEqual(self.runr()['next_automatic_action'],'W3_STRICT')
 def test_no_main_mixing(self):
  self.s['lane']['branch']='main'
  with self.assertRaisesRegex(AuthorityIncident,'WRONG_LANE'):self.runr()
 def test_no_stale_branch_tree(self):
  raw=json.dumps(self.s).encode();self.path.write_bytes(raw)
  with self.assertRaisesRegex(AuthorityIncident,'STALE_BRANCH'):reconcile(self.path,hashlib.sha256(raw).hexdigest(),'f'*40)
 def test_missing_middle_stage(self):
  self.s['records'].pop(1);self.s['records'][-1]['seq']=3
  with self.assertRaisesRegex(AuthorityIncident,'NONCONTIGUOUS'):self.runr()
 def test_counter_forgery(self):
  self.s['records'][1]['cumulative_configs']=999
  with self.assertRaisesRegex(AuthorityIncident,'COUNTER_CHAIN_BREAK'):self.runr()
 def test_drive_mismatch(self):
  self.s['records'][2]['drive_connector_readback']['size']='19'
  with self.assertRaisesRegex(AuthorityIncident,'DRIVE_METADATA_MISMATCH'):self.runr()
 def test_next_step_only_from_latest(self):
  self.s['preregistered_next_action']='W13'
  with self.assertRaisesRegex(AuthorityIncident,'NEXT_ACTION_NOT_FROM_LATEST'):self.runr()
 def test_bad_external_snapshot_pin(self):
  raw=json.dumps(self.s).encode();self.path.write_bytes(raw)
  with self.assertRaisesRegex(AuthorityIncident,'SNAPSHOT_EXTERNAL_PIN_MISMATCH'):reconcile(self.path,'0'*64,'a'*40)
if __name__=='__main__':unittest.main(verbosity=2)
