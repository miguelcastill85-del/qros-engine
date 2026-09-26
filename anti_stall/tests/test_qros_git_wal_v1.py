"""Adversarial, synthetic-only state transitions plus real original W5 446-byte audit.
No synthetic worker receipt may be published as an actual market validation.
"""
import base64,copy,hashlib,json,os,pathlib,sys,tempfile,unittest,zipfile
from unittest import mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'chat'))
import qros_git_wal_v1 as w
import qros_github_atomic_transport_v1 as t
BASE='/mnt/data/w5_v33/QROS_W5_V33_VERIFIED_446_OF_710_MASK_PARITY_SHARDS_20260925.zip'

def ptr(count=446):
    p={'branch':w.BRANCH,'scientific_state':'DEVELOPMENT_RUNNING','v33_shards_completed':count,'v33_shards_remaining':710-count,
       'v33_original_frozen_queue_sha256':w.PLAN_SHA,'target':'control/OLD.json' if count==446 else 'control/NEW.json',
       'target_git_blob_sha1':'a'*40 if count==446 else 'c'*40,
       'last_closed_remote_anchor_path':'control/OLD_ANCHOR.json' if count==446 else 'control/NEW_ANCHOR.json',
       'last_closed_remote_anchor_blob_sha1':'b'*40 if count==446 else 'd'*40,
       'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'new_W5_economic_results':'COMPLETE_EXPOSED_DEV_EXPLORATORY_ONLY'}
    b=w.jsonbytes(p);return b,w.gb(b)

def fake_receipts(audit,tasks):
    """Synthetic deliberately fabricated proof of format only, never scientific evidence."""
    found={}
    for name in tasks:
        task=next(t for t in audit['tasks'] if w.taskid(t)==name)
        ordinal=task['ordinals']
        tests=[{'ordinal':i,'physical_mask_id':'SYNTHETIC_FIXTURE_NOT_MARKET_EVIDENCE',
                'all_rejections_equal':True,'independent_exact_trades':1,'11_fields_compared':11,
                'PNL_blind_sampled_source_signals':1,'zero_signal_mask':False} for i in ordinal]
        rec={'schema':'QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1',
             'channel':task['ch'],'route':task['route'],'ordinals':ordinal,'tested_mask_occurrences':len(ordinal),
             'tests':tests,'sampled_signals':len(ordinal),'independent_exact_trades':len(ordinal),'exact_fields':11*len(ordinal),
             'status':'PASS','new_economic_PNL':False,'plan_SHA256':w.PLAN_SHA,'original_raw_sha256':w.RAW_SHA,
             'Gate_A_approved':False,'holdout_open':False,'ga2_open':False}
        found[name]=w.jsonbytes(rec)
    return found

class WALTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=w.audit_baseline(BASE);cls.pb,cls.ps=ptr()
        cls.idx,cls.ev=w.bootstrap(cls.audit,cls.pb,cls.ps)
    def claim(self,channel=0):
        with mock.patch.object(w,'verified_input_manifest',return_value={'raw_ticks':{'bytes':2573500596,'sha256':w.RAW_SHA},'channel_tape_zip':{'sha256':w.CHANNEL_SHA[channel],'bytes':1}}):
            return w.claim(self.idx,self.ev,self.audit,self.pb,self.ps,channel,{},owner='SYNTHETIC_TEST')
    def test_01_real_original_baseline_full_sha(self):
        self.assertEqual((self.audit['verified_receipts'],self.audit['manifest_member_count'],len(self.audit['tasks'])),(446,452,710))
        self.assertEqual(self.audit['baseline_git_blob_sha1'],'688ec3fa2123ec9df900c41487e4f6298b4ceea5')
    def test_02_noncontiguous_exante_indices_supported(self):
        self.assertGreater(sum(1 for a in self.audit['tasks'] if a['ordinals']!=list(range(a['ordinals'][0],a['ordinals'][-1]+1))),100)
    def test_03_frozen_next_real_channel(self):
        self.assertEqual(self.idx['next_CH0'][0],'CH0_r0_w1_batch015_I143_162.json')
        self.assertEqual(self.idx['next_CH4'][0],'CH4_r0_w1_batch017_I204_223.json')
    def test_04_bootstrap_event_chain(self):
        self.assertEqual(w.audit_events([self.ev],self.idx,self.audit)['status'],'WAL_EVENT_CHAIN_PASS')
    def test_05_live_pointer_corruption(self):
        with self.assertRaisesRegex(w.Stop,'LIVE_POINTER_GIT_SHA1_DRIFT'):w.bootstrap(self.audit,self.pb+b'!',self.ps)
    def test_06_live_gate_open(self):
        o=json.loads(self.pb);o['holdout_open']=True;b=w.jsonbytes(o)
        with self.assertRaisesRegex(w.Stop,'LIVE_FIREWALL_DRIFT'):w.bootstrap(self.audit,b,w.gb(b))
    def test_07_input_missing_fails_before_claim(self):
        with self.assertRaises(FileNotFoundError):w.claim(self.idx,self.ev,self.audit,self.pb,self.ps,0,{'raw_ticks':'/impossible','channel_tape_zip':'/impossible'})
    def test_08_exact_input_sha_fail(self):
        with tempfile.TemporaryDirectory() as d:
            f=pathlib.Path(d)/'raw';f.write_bytes(b'drift')
            with self.assertRaisesRegex(w.Stop,'INPUT_BYTES_SHA256_DRIFT'):w.verified_input_manifest(self.audit,0,{'raw_ticks':str(f),'channel_tape_zip':str(f)})
    def test_09_claim_bounded_six(self):
        l,e=self.claim();self.assertEqual(len(e['task_ids']),6);self.assertEqual(l['phase'],'CLAIMED')
    def test_10_duplicate_claim_fails(self):
        l,e=self.claim()
        with mock.patch.object(w,'verified_input_manifest',return_value={}):
            with self.assertRaisesRegex(w.Stop,'ALREADY_CLAIMED'):w.claim(l,e,self.audit,self.pb,self.ps,0,{})
    def test_11_claim_pointer_drift_fails(self):
        with self.assertRaisesRegex(w.Stop,'LIVE_POINTER_GIT_SHA1_DRIFT'):w.claim(self.idx,self.ev,self.audit,self.pb,w.gb(self.pb+b'!'),0,{})
    def test_12_interrupted_claim_no_blind_retry(self):
        l,e=self.claim();out=w.recover(l,e,self.audit,self.pb,self.ps)
        self.assertEqual(out['status'],'CLAIM_INCOMPLETE_DO_NOT_RERUN')
    def test_13_orphan_partial_receipts_do_not_count(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);recs.pop(e['task_ids'][0]);out=w.recover(l,e,self.audit,self.pb,self.ps,recs)
        self.assertEqual(out['status'],'CLAIM_INCOMPLETE_DO_NOT_RERUN')
    def test_14_complete_verified_bytes_resume_without_reexecution(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);out=w.recover(l,e,self.audit,self.pb,self.ps,recs)
        self.assertEqual(out['status'],'PREPARE_ATTEST_NO_RECOMPUTATION')
    def test_15_tampered_receipt_field_fails(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);obj=json.loads(recs[e['task_ids'][0]]);obj['exact_fields']+=1;recs[e['task_ids'][0]]=w.jsonbytes(obj)
        with self.assertRaisesRegex(w.Stop,'RECEIPT_11_FIELDS_DRIFT'):w.recover(l,e,self.audit,self.pb,self.ps,recs)
    def test_16_blocked_preserves_work_identity(self):
        l,e=self.claim();bl,be=w.block_claim(l,e,self.audit,self.pb,self.ps,'ORIGINAL_RAW_SOURCE_ABSENT')
        self.assertEqual(w.recover(bl,be,self.audit,self.pb,self.ps)['status'],'BLOCKED_DEPENDENCY_NO_IMPLICIT_RETRY')
        self.assertEqual(w.audit_events([self.ev,e,be],bl,self.audit)['phase'],'BLOCKED')
    def test_17_blocked_full_receipts_can_resume_without_rerun(self):
        l,e=self.claim();bl,be=w.block_claim(l,e,self.audit,self.pb,self.ps,'ORIGINAL_TAPE_ABSENT')
        recs=fake_receipts(self.audit,e['task_ids']);self.assertEqual(w.recover(bl,be,self.audit,self.pb,self.ps,recs)['status'],'PREPARE_ATTEST_NO_RECOMPUTATION')
    def test_18_incorrect_event_chain_fails(self):
        bad=copy.deepcopy(self.ev);bad['checkpoint']=445
        with self.assertRaisesRegex(w.Stop,'EVENT_CHAIN_BROKEN|LEDGER_HEAD_OR_SEQUENCE_MISMATCH|BASELINE_EVENT_DRIFT'):w.audit_events([bad],self.idx,self.audit)
    def test_19_delta_complete_valid_synthetic_transition(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);nb,ns=ptr(452)
        d={'schema':'QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1','parent_sha256':w.BASELINE_SHA,'previous_count':446,'new_count':452,
           'frozen_plan_sha256':w.PLAN_SHA,'no_new_PnL':True,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,
           'receipts':[{'name':k,'bytes':len(v),'sha256':w.sha(v),'b64':base64.b64encode(v).decode()} for k,v in recs.items()]}
        nl,ne=w.commit_proposal(l,e,self.audit,self.pb,self.ps,recs,w.jsonbytes(d),w.BASELINE_SHA,nb,ns)
        self.assertEqual((nl['completed'],nl['remaining'],nl['phase']),(452,258,'READY'))
        self.assertEqual(w.audit_events([self.ev,e,ne],nl,self.audit)['status'],'WAL_EVENT_CHAIN_PASS')
        self.assertEqual(nl['next_CH0'][0],w.next_tasks(self.audit,self.audit['closed']|set(e['task_ids']),6,0)[0])
    def test_35_fast_frontier_stale_projection_fails_on_commit(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);nb,ns=ptr(452)
        new=json.loads(nb);new['fast_frontier_v2']={'completed':446,'remaining':264,'git_blob_sha1':'f'*40};nb=w.jsonbytes(new);ns=w.gb(nb)
        d={'schema':'QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1','parent_sha256':w.BASELINE_SHA,'previous_count':446,'new_count':452,
           'frozen_plan_sha256':w.PLAN_SHA,'no_new_PnL':True,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,
           'receipts':[{'name':k,'bytes':len(v),'sha256':w.sha(v),'b64':base64.b64encode(v).decode()} for k,v in recs.items()]}
        with self.assertRaisesRegex(w.Stop,'FAST_FRONTIER_PROJECTION_STALE'):
            w.commit_proposal(l,e,self.audit,self.pb,self.ps,recs,w.jsonbytes(d),w.BASELINE_SHA,nb,ns)
    def test_20_delta_stale_parent_fails(self):
        l,e=self.claim();recs=fake_receipts(self.audit,e['task_ids']);nb,ns=ptr(452)
        d={'schema':'QROS_W5_GITHUB_APPEND_ONLY_DELTA_V1','parent_sha256':'0'*64,'previous_count':446,'new_count':452,'frozen_plan_sha256':w.PLAN_SHA,'receipts':[]}
        with self.assertRaisesRegex(w.Stop,'DELTA_PARENT_OR_COUNT_DRIFT'):w.commit_proposal(l,e,self.audit,self.pb,self.ps,recs,w.jsonbytes(d),w.BASELINE_SHA,nb,ns)
    def test_21_uncommitted_stage_does_not_change_live_count(self):
        l,e=self.claim();self.assertEqual(l['completed'],446);self.assertEqual(l['remaining'],264)
    def test_22_real_baseline_mutated_copy_fails(self):
        with tempfile.TemporaryDirectory() as d:
            f=pathlib.Path(d)/'fake.zip';f.write_bytes(pathlib.Path(BASE).read_bytes()+b'x')
            with self.assertRaisesRegex(w.Stop,'INPUT_BYTES_SHA256_DRIFT'):w.audit_baseline(str(f))

class ReconcileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=w.audit_baseline(BASE)
        cls.old,cls.oldsha=ptr()
        cls.ledger,cls.event=w.bootstrap(cls.audit,cls.old,cls.oldsha)
        new=json.loads(cls.old)
        new['fast_frontier_v2']={'completed':446,'remaining':264,'git_blob_sha1':'f'*40,'ledger_root_sha256':'a'*64}
        new['anti_stall_recovery']='FAST_FRONTIER_EQUIVALENT_METADATA_ONLY'
        cls.new=w.jsonbytes(new);cls.newsha=w.gb(cls.new)
    def test_29_equivalent_fast_frontier_reconciles_without_new_science(self):
        l,e=w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,self.new,self.newsha,'9'*40)
        self.assertEqual((l['completed'],l['remaining'],l['phase']),(446,264,'READY'))
        self.assertEqual(l['scientific_pointer_blob_sha1'],self.newsha)
        self.assertEqual(w.audit_events([self.event,e],l,self.audit)['status'],'WAL_EVENT_CHAIN_PASS')
    def test_30_economic_field_drift_rejected(self):
        x=json.loads(self.new);x['Gate_A_approved']=True;b=w.jsonbytes(x)
        with self.assertRaisesRegex(w.Stop,'LIVE_FIREWALL_DRIFT'):w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,b,w.gb(b),'9'*40)
    def test_31_unknown_field_drift_rejected(self):
        x=json.loads(self.new);x['unapproved_extra']='write';b=w.jsonbytes(x)
        with self.assertRaisesRegex(w.Stop,'UNKNOWN_FIELD_DRIFT'):w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,b,w.gb(b),'9'*40)
    def test_32_frontier_count_drift_rejected(self):
        x=json.loads(self.new);x['fast_frontier_v2']['completed']=445;b=w.jsonbytes(x)
        with self.assertRaisesRegex(w.Stop,'FAST_FRONTIER_UNPINNED_OR_COUNT_DRIFT'):w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,b,w.gb(b),'9'*40)
    def test_33_reconcile_does_not_repeat_when_pointer_unchanged(self):
        with self.assertRaisesRegex(w.Stop,'NO_ACTUAL_POINTER_CHANGE'):w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,self.old,self.oldsha,'9'*40)
    def test_34_reconciliation_event_old_pointer_tamper(self):
        l,e=w.reconcile_orthogonal(self.ledger,self.event,self.audit,self.old,self.oldsha,self.new,self.newsha,'9'*40)
        e['pointer_before_sha1']='1'*40;l['event_sha256']=w.sha(w.jsonbytes(e))
        with self.assertRaisesRegex(w.Stop,'UNSAFE_RECONCILIATION_EVENT'):w.audit_events([self.event,e],l,self.audit)

class FakeAPI:
    def __init__(self):
        self.branch_tip='0'*40;self.data={'control/pointer.json':b'old'};self.blobs={};self.calls=0;self.race=False;self.mutate_readback=False
    def head(self,b):
        self.calls+=1
        if self.race and self.calls>=2:return 'f'*40
        return self.branch_tip
    def commit(self,sha):return {'tree':{'sha':'1'*40}}
    def create_blob(self,b):
        h=t.git_sha(b);self.blobs[h]=b;return h
    def blob(self,h):
        b=self.blobs[h];return {'sha':h,'encoding':'base64','content':base64.b64encode(b'CORRUPT' if self.mutate_readback else b).decode()}
    def create_tree(self,base,elements):self.last_elements=elements;return '2'*40
    def create_commit(self,tree,parent,message):return '3'*40
    def move_ref(self,branch,commit):self.branch_tip=commit;self.data.update({p:self.blobs[entry['sha']] for entry in self.last_elements for p in [entry['path']]})
    def fetch_path(self,b,p):
        if p not in self.data:raise t.CASStop('GITHUB_HTTP_404:GET:'+p)
        return t.git_sha(self.data[p])

class TransportTests(unittest.TestCase):
    def test_23_atomic_multi_file_commit(self):
        api=FakeAPI();o=t.AtomicCAS(api,'research/test').publish('0'*40,{'control/pointer.json':b'new','events/000001.json':b'claim'},'test',{'control/pointer.json':t.git_sha(b'old'),'events/000001.json':None})
        self.assertEqual(o['status'],'ATOMIC_GIT_CAS_REMOTE_READBACK_PASS');self.assertEqual(api.branch_tip,'3'*40)
    def test_24_concurrent_writer_blocks_nonforce(self):
        api=FakeAPI();api.race=True
        with self.assertRaisesRegex(t.CASStop,'BRANCH_DRIFT_BEFORE_TREE'):t.AtomicCAS(api,'research/test').publish('0'*40,{'e.json':b'a'},'test')
        self.assertEqual(api.branch_tip,'0'*40)
    def test_25_remote_readback_tamper(self):
        api=FakeAPI();api.mutate_readback=True
        with self.assertRaisesRegex(t.CASStop,'REMOTE_BLOB_READBACK_FAILED'):t.AtomicCAS(api,'research/test').publish('0'*40,{'e.json':b'a'},'test')
    def test_26_immutable_path_collision(self):
        api=FakeAPI()
        with self.assertRaisesRegex(t.CASStop,'IMMUTABLE_PATH_ALREADY_EXISTS'):t.AtomicCAS(api,'research/test').publish('0'*40,{'control/pointer.json':b'a'},'test',{'control/pointer.json':None})
    def test_27_unsafe_path_traversal(self):
        with self.assertRaisesRegex(t.CASStop,'UNSAFE_GIT_PATH'):t.AtomicCAS(FakeAPI(),'research/test').publish('0'*40,{'../evil':b'a'},'test')
    def test_28_old_tip_fails(self):
        with self.assertRaisesRegex(t.CASStop,'BRANCH_TIP_CHANGED_BEFORE_UPLOAD'):t.AtomicCAS(FakeAPI(),'research/test').publish('a'*40,{'a':b'1'},'test')

if __name__=='__main__':unittest.main(verbosity=2)
