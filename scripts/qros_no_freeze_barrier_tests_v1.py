import json, os, sys, tempfile, time
from pathlib import Path
import qros_no_freeze_barrier_v1 as b

def wr(p,s):p.write_text(s,encoding='utf-8')
def supervisor_script(mode,sleep=0):
 return f'''import argparse,json,time,os
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--job-spec');ap.add_argument('--work-root');ap.add_argument('--launch-grace-seconds');a=ap.parse_args();spec=json.loads(Path(a.job_spec).read_text());root=Path(a.work_root);job=root/spec["job_id"];job.mkdir(parents=True,exist_ok=True)
mode={mode!r}
if mode=="running":
 (job/"current_claim.json").write_text(json.dumps({{"job_id":spec["job_id"],"spec_sha256":"x"}})); print(json.dumps({{"state":"RUNNING","action":"LAUNCHED"}}))
elif mode=="pass": print(json.dumps({{"state":"PASS","action":"PROMOTE_ATOMIC_DONE"}}))
elif mode=="fail": print(json.dumps({{"state":"FAIL","action":"RETRY_BUDGET_EXHAUSTED"}}))
elif mode=="noclaim": print(json.dumps({{"state":"RUNNING","action":"LAUNCHED"}}))
elif mode=="badjson": print("not-json")
elif mode=="silent": pass
elif mode=="sleep": time.sleep({sleep}); print(json.dumps({{"state":"RUNNING","action":"LAUNCHED"}}))
'''

def mk(td,mode='running',sleep=0):
 td=Path(td);spec=td/'spec.json';sup=td/'sup.py';state=td/'state.json';root=td/'jobs';root.mkdir()
 wr(spec,json.dumps({'schema':'X','job_id':'J','command':['x'],'expected_receipt':{}},sort_keys=True))
 wr(sup,supervisor_script(mode,sleep)); b.init_state(state,spec,root,sup);return spec,sup,state,root

def run():
 tests=[]
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'running');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='RUNNING_ADOPTABLE';assert b.close_check(state)['status']=='RUNNING_ADOPTABLE';tests.append('running_adoptable')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'pass');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='PASS';tests.append('pass_terminal')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'fail');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED';tests.append('fail_closed')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'noclaim');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED' and s['failure_reason']=='RUNNING_WITHOUT_DURABLE_CLAIM';tests.append('running_requires_claim')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'badjson');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED';tests.append('bad_json_closed')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'silent');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED';tests.append('silent_closed')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'sleep',2);t=time.monotonic();s=b.probe(state,spec,root,sup,.15,True);elapsed=time.monotonic()-t;assert s['status']=='FAIL_CLOSED' and elapsed<.8;tests.append('hard_nonblocking_timeout')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'running');d=json.loads(spec.read_text());d['command']=['changed'];spec.write_text(json.dumps(d,sort_keys=True));s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED' and 'JOB_SPEC_DRIFT' in s['failure_reason'];tests.append('spec_drift_closed')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'running');sup.write_text(sup.read_text()+'\n# drift');s=b.probe(state,spec,root,sup,1,True);assert s['status']=='FAIL_CLOSED' and 'SUPERVISOR_DRIFT' in s['failure_reason'];tests.append('supervisor_drift_closed')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'pass');s=b.load(state);assert s['status']=='PENDING_NOT_STARTED';assert b.close_check(state)['status']=='PENDING_NOT_STARTED';tests.append('pending_is_explicit_terminal')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'pass');s=b.probe(state,spec,root,sup,1,True);calls=s['supervisor_calls'];s2=b.probe(state,spec,root,sup,1,True);assert s2['supervisor_calls']==calls;tests.append('pass_never_relaunches')
 with tempfile.TemporaryDirectory() as td:
  spec,sup,state,root=mk(td,'fail');s=b.probe(state,spec,root,sup,1,True);calls=s['supervisor_calls'];s2=b.probe(state,spec,root,sup,1,True);assert s2['supervisor_calls']==calls;tests.append('fail_never_relaunches')
 print(json.dumps({'status':'PASS','count':len(tests),'tests':tests},sort_keys=True))
if __name__=='__main__':run()
