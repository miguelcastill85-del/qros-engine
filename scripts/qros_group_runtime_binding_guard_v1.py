#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,hashlib
from pathlib import Path

SCHEMA='QROS_GROUP_RUNTIME_BINDING_GUARD_1.0'

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256_file(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def fail(msg): raise RuntimeError(msg)

def validate(capsule_path:Path, wrapper_path:Path, job_spec_path:Path):
    c=json.loads(capsule_path.read_text()); j=json.loads(job_spec_path.read_text()); w=wrapper_path.read_text()
    n=int(c['subject']['structural_group_index']); tag=f'GROUP{n:02d}'; expected_schema=f'QROS_W09C_{tag}_WRAPPER_RECEIPT_1.0'
    checks={}
    def ck(name,cond): checks[name]=bool(cond); cond or fail(name)
    ck('capsule_pass_index', int(c['pass_criteria']['structural_group_index'])==n)
    ck('capsule_terminal_path_group', tag in c['terminal_receipt_path'].upper())
    prev=c['preconditions'].get('previous_group_receipt',{})
    if n>0:
        ck('previous_group_index', f'GROUP{n-1:02d}' in str(prev.get('path','')).upper())
        ck('previous_group_status', prev.get('status')=='PASS')
    ck('job_id_group', tag in str(j.get('job_id','')).upper())
    er=j.get('expected_receipt',{})
    ck('job_expected_index', er.get('structural_group_index')==n)
    ck('job_expected_schema', er.get('schema')==expected_schema)
    ck('job_expected_status', er.get('status')=='PASS')
    ck('job_no_pnl', er.get('economic_pnl_read') is False)
    ck('job_no_holdout', er.get('holdout_open') is False)
    ck('job_processed_count', er.get('processed_signal_configs')==c['pass_criteria']['processed_signal_configs'])
    ck('job_config_root', er.get('ordered_config_id_stream_root_sha256')==c['pass_criteria']['ordered_config_id_stream_root_sha256'])
    schemas=set(re.findall(r'QROS_W09C_GROUP\d{2}_WRAPPER_RECEIPT_1\.0',w))
    ck('wrapper_single_schema', schemas=={expected_schema})
    ix=[int(x) for x in re.findall(r"--structural-group-index['\"]\s*,\s*['\"](\d+)['\"]",w)]
    ck('wrapper_cli_index', ix==[n])
    dix=[int(x) for x in re.findall(r"['\"]structural_group_index['\"]\s*:\s*(\d+)",w)]
    ck('wrapper_dict_indices', len(dix)>=2 and set(dix)=={n})
    cmd=' '.join(map(str,j.get('command',[])))
    ck('job_command_wrapper_identity', wrapper_path.name in cmd)
    return {'schema':SCHEMA,'status':'PASS','group_index':n,'group_tag':tag,'expected_wrapper_schema':expected_schema,
            'capsule_sha256':sha256_file(capsule_path),'wrapper_sha256':sha256_file(wrapper_path),'job_spec_sha256':sha256_file(job_spec_path),'checks':checks}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--wrapper',type=Path,required=True);ap.add_argument('--job-spec',type=Path,required=True);a=ap.parse_args()
    try:r=validate(a.capsule,a.wrapper,a.job_spec);print(json.dumps(r,sort_keys=True));return 0
    except Exception as e:print(json.dumps({'schema':SCHEMA,'status':'FAIL_CLOSED','reason':f'{type(e).__name__}:{e}'},sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
