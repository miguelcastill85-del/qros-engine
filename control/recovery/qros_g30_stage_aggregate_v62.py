from __future__ import annotations
import json, hashlib, sys
from pathlib import Path

def main(outpath, label, expected_candidates, *parts):
    primary={}; independent={}; parity=[]; groups=[]
    start=None; end=None; source_records=None
    for ps in parts:
        p=Path(ps); d=json.loads(p.read_text())
        if not d.get('parity_all'): raise SystemExit('GROUP_PARITY_FAIL '+str(p))
        if start is None:
            start=d['stage_start_ms']; end=d['stage_end_ms_exclusive']; source_records=d['source_records']
        if (start,end,source_records)!=(d['stage_start_ms'],d['stage_end_ms_exclusive'],d['source_records']):
            raise SystemExit('GROUP_SCOPE_MISMATCH '+str(p))
        overlap=set(primary).intersection(d['primary'])
        if overlap: raise SystemExit('DUPLICATE_CLUSTERS '+','.join(sorted(overlap)))
        primary.update(d['primary']); independent.update(d['independent']); parity.extend(d['parity'])
        groups.append({'group':d['group'],'candidates':d['candidates'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    if len(primary)!=int(expected_candidates):
        raise SystemExit(f'CANDIDATE_COUNT_MISMATCH {len(primary)} != {expected_candidates}')
    obj={'schema':'QROS_G30_SHARDED_STAGE_AGGREGATE_V62_OUTPUT_v1','label':label,'stage_start_ms':start,
         'stage_end_ms_exclusive':end,'source_records':source_records,'candidates':len(primary),'parity_all':True,
         'groups':groups,'primary':primary,'independent':independent,'parity':parity}
    Path(outpath).write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    print(json.dumps({'label':label,'candidates':len(primary),'groups':len(groups),'parity_all':True,
                      'sha256':hashlib.sha256(Path(outpath).read_bytes()).hexdigest()},sort_keys=True))
if __name__=='__main__': main(Path(sys.argv[1]),sys.argv[2],int(sys.argv[3]),*sys.argv[4:])
