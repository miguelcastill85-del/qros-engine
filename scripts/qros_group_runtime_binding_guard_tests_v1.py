import json,tempfile
from pathlib import Path
import qros_group_runtime_binding_guard_v1 as g

def mk(td,n=8):
 td=Path(td);tag=f'GROUP{n:02d}';caps=td/'cap.json';wrap=td/f'run_group{n:02d}_wrapper.py';job=td/'job.json'
 c={'subject':{'structural_group_index':n},'pass_criteria':{'structural_group_index':n,'processed_signal_configs':33528,'ordered_config_id_stream_root_sha256':'r'},'terminal_receipt_path':f'control/X_{tag}_SEMANTIC_RECEIPT.json','preconditions':{'previous_group_receipt':{'path':f'control/X_GROUP{n-1:02d}_SEMANTIC_RECEIPT.json','status':'PASS'}}}
 w=f"x=['--structural-group-index','{n}']; req={{'structural_group_index':{n}}}; wr={{'schema':'QROS_W09C_{tag}_WRAPPER_RECEIPT_1.0','structural_group_index':{n}}}"
 j={'job_id':f'J_{tag}','command':['python',str(wrap)],'expected_receipt':{'schema':f'QROS_W09C_{tag}_WRAPPER_RECEIPT_1.0','status':'PASS','structural_group_index':n,'processed_signal_configs':33528,'ordered_config_id_stream_root_sha256':'r','economic_pnl_read':False,'holdout_open':False}}
 caps.write_text(json.dumps(c));wrap.write_text(w);job.write_text(json.dumps(j));return caps,wrap,job

def should_fail(mut):
 with tempfile.TemporaryDirectory() as td:
  c,w,j=mk(td);mut(c,w,j)
  try:g.validate(c,w,j)
  except RuntimeError:return True
  return False

def run():
 tests=[]
 with tempfile.TemporaryDirectory() as td:
  c,w,j=mk(td);assert g.validate(c,w,j)['status']=='PASS';tests.append('baseline_pass')
 assert should_fail(lambda c,w,j: j.write_text(j.read_text().replace('GROUP08_WRAPPER','GROUP07_WRAPPER')));tests.append('job_schema_mismatch')
 assert should_fail(lambda c,w,j: j.write_text(j.read_text().replace('"structural_group_index": 8','"structural_group_index": 7')));tests.append('job_index_mismatch')
 assert should_fail(lambda c,w,j: w.write_text(w.read_text().replace("GROUP08_WRAPPER","GROUP07_WRAPPER")));tests.append('wrapper_schema_mismatch')
 assert should_fail(lambda c,w,j: w.write_text(w.read_text().replace("'8'","'7'",1)));tests.append('wrapper_cli_mismatch')
 assert should_fail(lambda c,w,j: w.write_text(w.read_text().replace("'structural_group_index':8","'structural_group_index':7",1)));tests.append('wrapper_dict_mismatch')
 assert should_fail(lambda c,w,j: c.write_text(c.read_text().replace('GROUP07_SEMANTIC','GROUP06_SEMANTIC')));tests.append('previous_group_mismatch')
 assert should_fail(lambda c,w,j: c.write_text(c.read_text().replace('GROUP08_SEMANTIC','GROUP09_SEMANTIC')));tests.append('terminal_path_mismatch')
 assert should_fail(lambda c,w,j: j.write_text(j.read_text().replace('J_GROUP08','J_GROUP09')));tests.append('job_id_mismatch')
 assert should_fail(lambda c,w,j: j.write_text(j.read_text().replace('"economic_pnl_read": false','"economic_pnl_read": true')));tests.append('pnl_firewall')
 print(json.dumps({'status':'PASS','count':len(tests),'tests':tests},sort_keys=True))
if __name__=='__main__':run()
