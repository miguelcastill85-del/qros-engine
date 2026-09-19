#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

SCHEMA='QROS_W09C_GROUP09_WRAPPER_RECEIPT_1.0'
JOB_ID='W09C_XAUUSD_BUY_M1_GROUP09_RECOVERY_E1_20260919_v1'
CAPSULE_BLOB='4b8bf850d118eb31f6165f0fe7d3412204396bc3'
CONFIG_ROOT='96d664f4c4efb431dbd475355249b51aa49c8ac656ad5fd1caaf46d7086fc1c3'

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def write_receipt(path:Path,obj:dict)->None:
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--worker',required=True);ap.add_argument('--shard-json',required=True);ap.add_argument('--spec',required=True)
    ap.add_argument('--ticks',required=True);ap.add_argument('--bar-root',required=True);ap.add_argument('--ind-root',required=True)
    ap.add_argument('--lease',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True)
    a=ap.parse_args()
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);rp=Path(a.receipt)
    lease=json.loads(Path(a.lease).read_text(encoding='utf-8'))
    pre={
      'schema':SCHEMA,'status':'FAIL_CLOSED','job_id':JOB_ID,'group_index':9,'structural_group_index':9,
      'lease_epoch':lease.get('lease_epoch'),'lease_id':lease.get('lease_id'),'fence_token':lease.get('fence_token'),
      'capsule_blob_sha1':CAPSULE_BLOB,'processed_signal_configs':0,
      'ordered_config_id_stream_root_sha256':CONFIG_ROOT,'economic_pnl_read':False,'holdout_open':False,'artifacts':[]
    }
    binding={'structural_group_index':9}
    if binding['structural_group_index']!=9:
        pre['reason']='WRAPPER_GROUP_BINDING_INVALID';write_receipt(rp,pre);return 2
    required={'job_id':JOB_ID,'group_index':9,'state':'ACTIVE'}
    for k,v in required.items():
        if lease.get(k)!=v:
            pre['reason']='LEASE_MISMATCH:'+k;write_receipt(rp,pre);return 2
    inner=out/'inner_worker_receipt.json'
    cmd=[
      sys.executable,a.worker,'--shard-json',a.shard_json,'--spec',a.spec,'--out-dir',str(out),
      '--receipt',str(inner),'--ticks',a.ticks,'--bar-root',a.bar_root,'--ind-root',a.ind_root,
      '--point','0.01','--expected-config-root',CONFIG_ROOT,'--structural-group-index','9'
    ]
    cp=subprocess.run(cmd)
    if cp.returncode!=0 or not inner.is_file():
        pre['reason']=f'INNER_WORKER_EXIT_{cp.returncode}';write_receipt(rp,pre);return 2
    r=json.loads(inner.read_text(encoding='utf-8'))
    checks={
      'status':r.get('status')=='PASS',
      'structural_group_index':r.get('structural_group_index')==9,
      'processed_signal_configs':r.get('processed_signal_configs')==33528,
      'ordered_config_id_stream_root_sha256':r.get('ordered_config_id_stream_root_sha256')==CONFIG_ROOT,
      'economic_pnl_read':r.get('economic_pnl_read') is False,
      'holdout_open':r.get('holdout_open') is False,
      'artifacts':isinstance(r.get('artifacts'),list) and len(r.get('artifacts'))==4,
    }
    if not all(checks.values()):
        pre['reason']='INNER_RECEIPT_VALIDATION_FAIL';pre['checks']=checks;write_receipt(rp,pre);return 2
    pre.update({
      'status':'PASS','processed_signal_configs':33528,
      'distinct_mask_class_count':r['distinct_mask_class_count'],'duplicate_config_count':r['duplicate_config_count'],
      'zero_event_class_alias_count':r['zero_event_class_alias_count'],
      'zero_event_representative_config_id':r['zero_event_representative_config_id'],
      'class_root_sha256':r['class_root_sha256'],'semantic_class_root_sha256':r['semantic_class_root_sha256'],
      'full_alias_mapping_root_sha256':r['full_alias_mapping_root_sha256'],
      'group_config_root_sha256':r['group_config_root_sha256'],'structural_group_key':r['structural_group_key'],
      'metrics':r['metrics'],'inner_worker_receipt_sha256':sha256_file(inner),'artifacts':r['artifacts'],
      'checks':checks
    })
    write_receipt(rp,pre);return 0

if __name__=='__main__':raise SystemExit(main())
