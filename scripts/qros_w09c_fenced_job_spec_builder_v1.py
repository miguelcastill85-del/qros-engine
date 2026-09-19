#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
SCHEMA='QROS_W09C_FENCED_JOB_SPEC_BUILDER_1.0'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--capsule-blob-sha1',required=True);ap.add_argument('--lease',type=Path,required=True);ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--shard-json',type=Path,required=True);ap.add_argument('--ticks',type=Path,required=True);ap.add_argument('--bar-root',type=Path,required=True);ap.add_argument('--ind-root',type=Path,required=True);ap.add_argument('--point',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 cap=json.loads(a.capsule.read_text());lease=json.loads(a.lease.read_text());gi=int(cap['subject']['structural_group_index'])
 if lease.get('state')!='ACTIVE' or lease.get('group_index')!=gi:raise SystemExit('LEASE_CAPSULE_BINDING_FAIL')
 er={'schema':'QROS_W09C_FENCED_GROUP_WRAPPER_RECEIPT_1.0','status':'PASS','job_id':lease['job_id'],'group_index':gi,'lease_epoch':lease['lease_epoch'],'lease_id':lease['lease_id'],'fence_token':lease['fence_token'],'capsule_blob_sha1':a.capsule_blob_sha1,'processed_signal_configs':cap['pass_criteria']['processed_signal_configs'],'structural_group_index':gi,'ordered_config_id_stream_root_sha256':cap['pass_criteria']['ordered_config_id_stream_root_sha256'],'economic_pnl_read':False,'holdout_open':False}
 cmd=[sys.executable,str(a.runner),'--capsule',str(a.capsule),'--capsule-blob-sha1',a.capsule_blob_sha1,'--lease',str(a.lease),'--source-root',str(a.source_root),'--shard-json',str(a.shard_json),'--ticks',str(a.ticks),'--bar-root',str(a.bar_root),'--ind-root',str(a.ind_root),'--point',str(a.point),'--out-dir','{out_dir}','--receipt','{receipt}']
 spec={'schema':'QROS_HEAVY_JOB_SPEC_1.0','job_id':lease['job_id'],'max_attempts':1,'artifacts_required':True,'expected_receipt':er,'command':cmd}
 a.out.write_text(json.dumps(spec,sort_keys=True,indent=2)+'\n');print(json.dumps({'schema':SCHEMA,'status':'PASS','job_id':lease['job_id'],'group_index':gi,'job_spec_sha256':hashlib.sha256(canonical(spec)).hexdigest()},sort_keys=True))
if __name__=='__main__':main()
