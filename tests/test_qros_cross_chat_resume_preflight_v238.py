from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'qros_cross_chat_resume_preflight_v238.py'
def w(root,rel,obj_or_text):
 p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj_or_text,sort_keys=True)+'\n' if isinstance(obj_or_text,(dict,list)) else obj_or_text)
def blob(text):
 b=text.encode();h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()
def D(a,s,t):return {'asset':a,'side':s,'timeframe':t}
def build(root):
 runners={'base_group_worker':('scripts/worker.py','worker\n'),'portable_cached_wrapper':('scripts/wrapper.py','wrapper\n'),'domain_bound_merger':('scripts/merge.py','merge\n'),'independent_merge_oracle':('scripts/oracle.py','oracle\n'),'global_maskpack_builder':('scripts/pack.py','pack\n'),'generic_maskpack_oracle':('scripts/packoracle.py','packoracle\n')};ra={}
 for k,(p,t) in runners.items():w(root,p,t);ra[k]={'path':p,'git_blob_sha1':blob(t)}
 ds=[('XAUUSD','BUY','M1','s0','c0','m0','a0',303572),('NQX','BUY','H1','s1','c1','m1','a1',165360),('NQX','BUY','H2','s2','c2','m2','a2',105642),('NQX','BUY','H3','s3','c3','m3','a3',80166),('NQX','BUY','H4','s4','c4','m4','a4',58647),('NQX','BUY','M1','s5','c5','m5','a5',317112)]
 comp=[];prom=[]
 for i,(a,s,t,sh,cr,sr,ar,dc) in enumerate(ds):
  path=f'control/c{i}.json';rec={'state':'PASS','domain':D(a,s,t),'shard_id':sh,'signal_configs':804672,'distinct_mask_classes':dc,'ordered_config_id_stream_root_sha256':cr,'semantic_class_root_sha256':sr,'full_alias_mapping_root_sha256':ar,'scientific_guards':{'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}};w(root,path,rec);row={'asset':a,'side':s,'timeframe':t,'shard_id':sh,'distinct_mask_classes':dc,'ordered_config_id_stream_root_sha256':cr,'semantic_class_root_sha256':sr,'full_alias_mapping_root_sha256':ar,'completion_receipt':path};comp.append(row);prom.append({**row,'signal_configs':804672})
 auth={k:f'control/{k}.json' for k in ['machine_spec','gate_a_plan','event_ordering','pre_shard_semantics','promotion_continuity_policy','sharded_hardening_policy','derived_artifact_rematerialization']}
 for p in auth.values():w(root,p,{})
 auth.update({'promotion_ledger':'control/ledger.json','portable_ga1_wrapper_parity':'control/parity.json','resume_integrity_incident_closure':'control/closure.json','m1_groups_complete':'control/groups.json','m1_global_mask_pack':'control/pack.json','m1_global_pack_compaction':'control/pc.json','m1_group_mask_compaction':'control/gc.json','m1_storage_cleanup':'control/clean.json','m1_completion':'control/c5.json','current_config_stream_parity':'control/current.json','cross_chat_resume_preflight':'scripts/qros_cross_chat_resume_preflight_v238.py','cross_chat_resume_regression':'control/regression.json'})
 w(root,'scripts/qros_cross_chat_resume_preflight_v238.py',SCRIPT.read_text());w(root,'control/regression.json',{'status':'PASS'});w(root,'control/ledger.json',{'completed_and_promoted_shards':prom,'queued_shard_count':6,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False,'economic_execution_authorized':False});w(root,'control/parity.json',{'status':'PASS_BYTE_EXACT_PARITY'});w(root,'control/closure.json',{'status':'PASS_CLOSED_FOR_GA1_RESUME'});w(root,'control/groups.json',{'status':'PASS'});w(root,'control/pack.json',{'state':'PASS','shard_id':'s5','ordered_config_id_stream_root_sha256':'c5','semantic_class_root_sha256':'m5','full_alias_mapping_root_sha256':'a5'});w(root,'control/pc.json',{'status':'PASS','scientific_content_changed':False,'compressed_pack':{'identity_verified':True}});w(root,'control/gc.json',{'status':'PASS','groups':24,'identity_verified_24_of_24':True});w(root,'control/clean.json',{'status':'PASS','scientific_content_changed':False,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False});cur={'asset':'NQX','side':'BUY','timeframe':'M10','shard_id':'next','expected_signal_configs':804672,'expected_config_root_sha256':'nextroot'};w(root,'control/current.json',{'status':'PASS','primary_independent_root_equal':True,'domain':D('NQX','BUY','M10'),'shard_id':'next','processed_signal_configs':804672,'ordered_config_id_stream_root_sha256':'nextroot'});target={'version':'V238','authority':auth,'runner_authority':ra,'verified_counts':{'ga1_formally_completed_shards':6,'ga1_remaining_shards':54,'shards_total':60,'first_economic_gate_queue_count':6},'completed_shards':comp,'current_shard':cur,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False};w(root,'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V238_v1.json',target);w(root,'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json',{'current_version':'V238','target_path':'control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER_V238_v1.json','economic_pnl_read':False,'holdout_open':False,'ga2_open':False});return root
def run(root):
 out=root/'out.json';p=subprocess.run([sys.executable,str(SCRIPT),'--repo-root',str(root),'--out',str(out)],capture_output=True,text=True);return p,json.loads(out.read_text())
def mutate(path,key,val):
 o=json.loads(path.read_text());o[key]=val;w(path.parent,path.name,o)
cases=[]
with tempfile.TemporaryDirectory() as td:
 r=build(Path(td));p,o=run(r);assert p.returncode==0 and o['status']=='PASS';cases.append(['coherent_graph','PASS'])
with tempfile.TemporaryDirectory() as td:
 r=build(Path(td));mutate(r/'control/c5.json','full_alias_mapping_root_sha256','bad');p,o=run(r);assert p.returncode==2 and o['status']=='FAIL';cases.append(['mutate_m1_alias_root','FAIL_CLOSED'])
with tempfile.TemporaryDirectory() as td:
 r=build(Path(td));mutate(r/'control/current.json','ordered_config_id_stream_root_sha256','bad');p,o=run(r);assert p.returncode==2 and o['status']=='FAIL';cases.append(['mutate_m10_config_root','FAIL_CLOSED'])
with tempfile.TemporaryDirectory() as td:
 r=build(Path(td));(r/'scripts/wrapper.py').write_text('mutated\n');p,o=run(r);assert p.returncode==2 and o['status']=='FAIL';cases.append(['mutate_runner_blob','FAIL_CLOSED'])
with tempfile.TemporaryDirectory() as td:
 r=build(Path(td));mutate(r/'control/ledger.json','queued_shard_count',5);p,o=run(r);assert p.returncode==2 and o['status']=='FAIL';cases.append(['mutate_ledger_count','FAIL_CLOSED'])
print(json.dumps(cases))
