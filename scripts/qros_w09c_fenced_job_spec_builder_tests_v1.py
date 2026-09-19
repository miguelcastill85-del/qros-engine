import json,tempfile,subprocess,sys
from pathlib import Path
B=Path(__file__).with_name('qros_w09c_fenced_job_spec_builder_v1.py')
def main():
 with tempfile.TemporaryDirectory() as td:
  d=Path(td);cap=d/'c.json';lease=d/'l.json';out=d/'j.json';runner=d/'r.py';runner.write_text('')
  cap.write_text(json.dumps({'subject':{'structural_group_index':9},'pass_criteria':{'processed_signal_configs':33528,'ordered_config_id_stream_root_sha256':'ROOT'}}))
  lease.write_text(json.dumps({'state':'ACTIVE','group_index':9,'job_id':'J','lease_epoch':1,'lease_id':'L','fence_token':'F'}))
  cp=subprocess.run([sys.executable,str(B),'--capsule',str(cap),'--capsule-blob-sha1','CAP','--lease',str(lease),'--runner',str(runner),'--source-root',str(d),'--shard-json',str(d/'s'),'--ticks',str(d/'t'),'--bar-root',str(d/'b'),'--ind-root',str(d/'i'),'--point','0.01','--out',str(out)],capture_output=True,text=True);assert cp.returncode==0,cp.stderr;j=json.loads(out.read_text());e=j['expected_receipt'];assert e['schema']=='QROS_W09C_FENCED_GROUP_WRAPPER_RECEIPT_1.0' and e['group_index']==9 and e['job_id']=='J' and j['max_attempts']==1
  bad=json.loads(lease.read_text());bad['group_index']=8;lease.write_text(json.dumps(bad));cp=subprocess.run([sys.executable,str(B),'--capsule',str(cap),'--capsule-blob-sha1','CAP','--lease',str(lease),'--runner',str(runner),'--source-root',str(d),'--shard-json',str(d/'s'),'--ticks',str(d/'t'),'--bar-root',str(d/'b'),'--ind-root',str(d/'i'),'--point','0.01','--out',str(out)],capture_output=True,text=True);assert cp.returncode!=0
 print('PASS 2/2')
if __name__=='__main__':main()
