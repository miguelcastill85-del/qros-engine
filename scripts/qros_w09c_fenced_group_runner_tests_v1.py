import json,tempfile,hashlib
from pathlib import Path
import qros_w09c_fenced_group_runner_v1 as r

def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def lease():
 x={'state':'ACTIVE','group_index':9,'job_id':'J','lease_epoch':1,'lease_id':'L','owner_runtime_id':'R'}
 bound={k:x[k] for k in ['job_id','group_index','lease_epoch','owner_runtime_id','lease_id']};x['fence_token']=hashlib.sha256(json.dumps(bound,sort_keys=True,separators=(',',':')).encode()).hexdigest();return x
def main():
 t=[]
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);p=root/'scripts/x.py';p.parent.mkdir();p.write_text('x=1\n');cap={'subject':{'structural_group_index':9},'exact_inputs':[{'path':'scripts/x.py','git_blob_sha1':blob(p.read_bytes())}]};assert len(r.validate_source_pins(cap,root))==1;t.append('source_pin_pass')
  cap['exact_inputs'][0]['git_blob_sha1']='0'*40
  try:r.validate_source_pins(cap,root);raise AssertionError
  except RuntimeError:pass
  t.append('source_pin_drift_fail_closed')
 cap={'subject':{'structural_group_index':9}};x=lease();assert r.validate_lease(cap,x)==9;t.append('lease_pass')
 for key,val in [('state','DEAD'),('group_index',8),('job_id',''),('lease_id',''),('owner_runtime_id','')]:
  y=dict(x);y[key]=val
  try:r.validate_lease(cap,y);raise AssertionError
  except RuntimeError:pass
  t.append('lease_'+key+'_fail_closed')
 y=dict(x);y['fence_token']='0'*64
 try:r.validate_lease(cap,y);raise AssertionError
 except RuntimeError:pass
 t.append('fence_tamper_fail_closed')
 print('PASS',len(t),'/'+str(len(t)),','.join(t))
if __name__=='__main__':main()
