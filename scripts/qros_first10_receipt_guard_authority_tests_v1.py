#!/usr/bin/env python3
"""Independent synthetic authority-invariant tests; no market data or PnL."""
import copy
import importlib.util
import json
import tempfile
from pathlib import Path

spec=importlib.util.spec_from_file_location('qguard',Path(__file__).with_name('qros_first10_receipt_guard_v1.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
COUNTS=[303572,165360,105642,80166,58647,317112,253230,248010,237636,296068]

def build(root,mutate=None):
    pointer={'campaign':q.CAMPAIGN,'current_version':'V259','scientific_state':'PREREGISTERED_NO_RESULTS',
             'verified_counts':{'ga1_formally_completed_shards':10},'economic_pnl_read':False,'holdout_open':False}
    scope={'campaign':q.CAMPAIGN,'source_main_commit':q.MAIN_COMMIT,'base_frontier_version':'V259',
           'shards':[{'ordinal':i+1,'expected_signal_configs':804672,'distinct_mask_classes':n} for i,n in enumerate(COUNTS)]}
    if mutate: mutate(pointer,scope)
    p=root/'pointer.json';s=root/'scope.json'
    p.write_text(json.dumps(pointer,sort_keys=True)+'\n');scope['base_pointer_blob_sha1']=q.git_blob(p)
    s.write_text(json.dumps(scope,sort_keys=True)+'\n')
    return s,p,(q.git_blob(s),q.git_blob(p))

def fail(name,fn,expected):
    try:fn()
    except q.PreflightError as e:
        assert str(e)==expected,(name,str(e),expected)
        return name
    raise AssertionError('FALSE_PASS_'+name)

def run():
    cases=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        s,p,pins=build(root);v=q.verify_authority(s,p,pins)
        assert len(v[0]['shards'])==10;cases.append('valid_fixture')
        p.write_text(p.read_text()+' ')
        cases.append(fail('stale_pointer_bytes',lambda:q.verify_authority(s,p,pins),'POINTER_BYTES_DRIFT'))
        s,p,pins=build(root);s.write_text(s.read_text()+' ')
        cases.append(fail('scope_bytes_tamper',lambda:q.verify_authority(s,p,pins),'SCOPE_BYTES_DRIFT'))
        s,p,pins=build(root,lambda p,s:s['shards'][0].update(distinct_mask_classes=303573))
        cases.append(fail('self_consistent_invalid_counts',lambda:q.verify_authority(s,p,pins),'SCOPE_MASK_DRIFT'))
        s,p,pins=build(root,lambda p,s:p.update(scientific_state='APPROVED_FINAL'))
        cases.append(fail('correct_hash_wrong_science',lambda:q.verify_authority(s,p,pins),'POINTER_STATE_DRIFT'))
        s,p,pins=build(root,lambda p,s:s['shards'][1].update(ordinal=1))
        cases.append(fail('duplicate_fifo_ordinal',lambda:q.verify_authority(s,p,pins),'SCOPE_FIFO_DRIFT'))
        assert q.PRODUCTION_GRANT_BLOB is None;cases.append('production_grant_still_null')
    print(json.dumps({'status':'PASS','cases':cases,'tests_passed':len(cases),'economic_pnl_read':False},sort_keys=True))
if __name__=='__main__':run()
