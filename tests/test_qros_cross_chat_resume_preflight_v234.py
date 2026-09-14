#!/usr/bin/env python3
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path

def write(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o))
def gblob(b):h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()
def build(root):
 scripts=root/'scripts';scripts.mkdir(parents=True,exist_ok=True);(scripts/'w1.py').write_text('x=1\n');(scripts/'w2.py').write_text('x=2\n')
 b1=(scripts/'w1.py').read_bytes();b2=(scripts/'w2.py').read_bytes()
 for p in ['machine.json','gate.json','event.json','pre.json','policy.json','hard.json','resume_reg.json','xau.json']:write(root/p,{})
 stable={'current_version':'V1','target_path':'control/target.json','hardening_policy':'hard.json','promotion_ledger':'control/ledger.json','rematerialization_manifest':'control/remat.json','economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
 auth={'machine_spec':'machine.json','gate_a_plan':'gate.json','event_ordering':'event.json','pre_shard_semantics':'pre.json','promotion_ledger':'control/ledger.json','promotion_continuity_policy':'policy.json','sharded_hardening_policy':'hard.json','derived_artifact_rematerialization':'control/remat.json','portable_ga1_wrapper_parity':'control/parity.json','cross_chat_resume_regression':'resume_reg.json','xau_v228_rebinding_parity':'xau.json','h4_group_checkpoint':'control/cp.json'}
 target={'version':'V1','authority':auth,'verified_counts':{'ga1_formally_completed_shards':1,'first_economic_gate_queue_count':1},'completed_shards':[{'asset':'NQX','side':'BUY','timeframe':'H1','shard_id':'sid1','distinct_mask_classes':10,'ordered_config_id_stream_root_sha256':'cfg1','semantic_class_root_sha256':'sem1','full_alias_mapping_root_sha256':'alias1','completion_receipt':'control/comp.json'}],'current_shard':{'asset':'NQX','side':'BUY','timeframe':'H4','shard_id':'sid4','expected_config_root_sha256':'cfg4','groups_pass':24,'groups_total':24,'group_receipts_root_sha256':'gr4'},'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
 ledger={'completed_and_promoted_shards':[{'asset':'NQX','side':'BUY','timeframe':'H1','shard_id':'sid1','distinct_mask_classes':10,'ordered_config_id_stream_root_sha256':'cfg1','semantic_class_root_sha256':'sem1','full_alias_mapping_root_sha256':'alias1','completion_receipt':'control/comp.json'}],'queued_shard_count':1,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
 comp={'domain':{'asset':'NQX','side':'BUY','timeframe':'H1'},'shard_id':'sid1','processed_signal_configs':804672,'distinct_mask_class_count':10,'ordered_config_id_stream_root_sha256':'cfg1','semantic_class_root_sha256':'sem1','full_alias_mapping_root_sha256':'alias1','scientific_guards':{'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}}
 cp={'asset':'NQX','side':'BUY','timeframe':'H4','shard_id':'sid4','expected_config_root_sha256':'cfg4','groups_pass':24,'groups_total':24,'processed_signal_configs':804672,'group_receipts_root_sha256':'gr4'}
 remat={'completed_shards':[{'domain':'NQX/BUY/H1'}],'scientific_guards':{'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}}
 parity={'status':'PASS_BYTE_EXACT_PARITY','portable_authorities':{'cached_wrapper_path':'scripts/w1.py','cached_wrapper_git_blob_sha1':gblob(b1),'tree_wrapper_path':'scripts/w2.py','tree_wrapper_git_blob_sha1':gblob(b2)}}
 for n,o in [('QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json',stable),('target.json',target),('ledger.json',ledger),('comp.json',comp),('cp.json',cp),('remat.json',remat),('parity.json',parity)]:write(root/'control'/n,o)

def run(script,root,name):
 out=root/name;cp=subprocess.run([sys.executable,str(script),'--repo-root',str(root),'--out',str(out)],capture_output=True,text=True);return cp,json.loads(out.read_text())
def main():
 script=Path(__file__).resolve().parents[1]/'scripts'/'qros_cross_chat_resume_preflight_v234.py'
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);build(root);cp,r=run(script,root,'pass.json');assert cp.returncode==0 and r['status']=='PASS',(cp.stdout,r)
  p=root/'control/ledger.json';x=json.loads(p.read_text());x['completed_and_promoted_shards'][0]['full_alias_mapping_root_sha256']='BAD';write(p,x);cp,r=run(script,root,'fail_alias.json');assert cp.returncode==2 and any(e.startswith('ALIAS_ROOT_') for e in r['errors']),r
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);build(root);(root/'hard.json').unlink();cp,r=run(script,root,'fail_missing.json');assert cp.returncode==2 and any('AUTHORITY_EXISTS_SHARDED_HARDENING_POLICY' in e for e in r['errors']),r
 print('PASS v234 positive + alias-root mutation + missing-hardening negative regressions')
if __name__=='__main__':main()
