from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'qros_cross_chat_resume_preflight_v237.py'
def w(root,rel,obj_or_text):
 p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if isinstance(obj_or_text,(dict,list)):p.write_text(json.dumps(obj_or_text,sort_keys=True)+'\n')
 else:p.write_text(obj_or_text)
def blob(text):
 b=text.encode();h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()
def dom(a,s,t):return {'asset':a,'side':s,'timeframe':t}
def build(root:Path):
 runners={'base_group_worker':('scripts/worker.py','worker\n'),'portable_cached_wrapper':('scripts/wrapper.py','wrapper\n'),'domain_bound_merger':('scripts/merge.py','merge\n'),'independent_merge_oracle':('scripts/oracle.py','oracle\n'),'global_maskpack_builder':('scripts/pack.py','pack\n'),'generic_maskpack_oracle':('scripts/pack_oracle.py','pack_oracle\n')};ra={}
 for k,(p,t) in runners.items():w(root,p,t);ra[k]={'path':p,'git_blob_sha1':blob(t)}
 domains=[('XAUUSD','BUY','M1','s0','c0','sem0','a0',303572),('NQX','BUY','H1','s1','c1','sem1','a1',165360),('NQX','BUY','H2','s2','c2','sem2','a2',105642),('NQX','BUY','H3','s3','c3','sem3','a3',80166),('NQX','BUY','H4','s4','c4','sem4','a4',58647)];comp=[];prom=[]
 for i,(a,s,t,sh,cr,sr,ar,dc) in enumerate(domains):
  path=f'control/c{i}.json';r={'state':'PASS','domain':dom(a,s,t),'shard_id':sh,'signal_configs':804672,'distinct_mask_classes':dc,'ordered_config_id_stream_root_sha256':cr,'semantic_class_root_sha256':sr,'full_alias_mapping_root_sha256':ar,'scientific_guards':{'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}};w(root,path,r);x={'asset':a,'side':s,'timeframe':t,'shard_id':sh,'distinct_mask_classes':dc,'ordered_config_id_stream_root_sha256':cr,'semantic_class_root_sha256':sr,'full_alias_mapping_root_sha256':ar,'completion_receipt':path};comp.append(x);prom.append({**x,'signal_configs':804672})
 auth={k:f'control/{k}.json' for k in ['machine_spec','gate_a_plan','event_ordering','pre_shard_semantics','promotion_continuity_policy','sharded_hardening_policy','derived_artifact_rematerialization','resume_integrity_incident']}
 for p in auth.values():w(root,p,{})
 auth.update({'promotion_ledger':'control/ledger.json','portable_ga1_wrapper_parity':'control/parity.json','resume_integrity_incident_closure':'control/closure.json','h4_rematerialization_reconciliation':'control/remat.json','h4_global_mask_pack':'control/pack.json','h4_storage_cleanup':'control/clean.json','h4_completion':'control/c4.json','current_config_stream_parity':'control/current.json','cross_chat_resume_preflight':'scripts/qros_cross_chat_resume_preflight_v237.py','cross_chat_resume_regression':'control/regression.json'});w(root,'scripts/qros_cross_chat_resume_preflight_v237.py',SCRIPT.read_text());w(root,'control/regression.json',{'status':'PASS'});w(root,'control/ledger.json',{'completed_and_promoted_shards':prom,'queued_shard_count':5,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False,'economic_execution_authorized':False});w(root,'control/parity.json',{'status':'PASS_BYTE_EXACT_PARITY','decision':'ADOPT_V236_FOR_DETERMINISTIC_GA1_REMATERIALIZATION_ONLY','corrected_authority':{'cached_wrapper_path':ra['portable_cached_wrapper']['path'],'cached_wrapper_git_blob_sha1':ra['portable_cached_wrapper']['git_blob_sha1'],'base_worker_path':ra['base_group_worker']['path'],'base_worker_git_blob_sha1':ra['base_group_worker']['git_blob_sha1']}});w(root,'control/closure.json',{'status':'PASS_CLOSED_FOR_GA1_RESUME'});w(root,'control/remat.json',{'status':'PASS','groups_verified':24,'v232_scientific_fields_match':True,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False});w(root,'control/pack.json',{'state':'PASS','shard_id':'s4','ordered_config_id_stream_root_sha256':'c4','semantic_class_root_sha256':'sem4','full_alias_mapping_root_sha256':'a4'});w(root,'control/clean.json',{'status':'PASS','scientific_content_changed':False,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False});current={'asset':'NQX','side':'BUY','timeframe':'M1','shard_id':'next','expected_signal_configs':804672,'expected_config_root_sha256':'nextroot'};w(root,'control/current.json',{'status':'PASS','primary_independent_root_equal':True,'domain':dom('NQX','BUY','M1'),'shard_id':'next','processed_signal_configs':804672,'ordered_config_id_stream_root_sha256':'nextroot'});target={'version':'V237','authority':auth,'runner_authority':ra,'verified_counts':{'ga1_formally_completed_shards':5,'ga1_remaining_shards':55,'shards_total':60,'first_economic_gate_queue_count':5},'completed_shards':comp,'current_shard':current,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False};w(root,'control/target.json',target);stable={'current_version':'V237','target_path':'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V237_v1.json','economic_pnl_read':False,'holdout_open':False,'ga2_open':False};w(root,'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json',stable);(root/'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V237_v1.json').write_text((root/'control/target.json').read_text());return root
def run(root):
 out=root/'out.json';p=subprocess.run([sys.executable,str(SCRIPT),'--repo-root',str(root),'--out',str(out)],capture_output=True,text=True);return p,json.loads(out.read_text())
def main():
 cases=[]
 with tempfile.TemporaryDirectory() as td:
  r=build(Path(td));p,o=run(r);assert p.returncode==0 and o['status']=='PASS';cases.append(('coherent_authority_graph','PASS','PASS'))
 with tempfile.TemporaryDirectory() as td:
  r=build(Path(td));q=r/'control/c4.json';o=json.loads(q.read_text());o['full_alias_mapping_root_sha256']='mutated';w(r,'control/c4.json',o);p,x=run(r);assert p.returncode==2 and x['status']=='FAIL';cases.append(('mutate_h4_alias_root','FAIL_CLOSED','FAIL_CLOSED'))
 with tempfile.TemporaryDirectory() as td:
  r=build(Path(td));q=r/'control/current.json';o=json.loads(q.read_text());o['ordered_config_id_stream_root_sha256']='mutated';w(r,'control/current.json',o);p,x=run(r);assert p.returncode==2 and x['status']=='FAIL';cases.append(('mutate_current_config_root','FAIL_CLOSED','FAIL_CLOSED'))
 with tempfile.TemporaryDirectory() as td:
  r=build(Path(td));(r/'scripts/wrapper.py').write_text('mutated\n');p,x=run(r);assert p.returncode==2 and x['status']=='FAIL';cases.append(('mutate_runner_blob','FAIL_CLOSED','FAIL_CLOSED'))
 print(json.dumps(cases))
if __name__=='__main__':main()
