"""Score submitted DEVELOPMENT JSON. Never infer model execution or parity."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('DUPLICATE_KEY')
            result[key]=value
        return result
    def bad(value):raise ValueError('NONFINITE_NUMBER')
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    json.dumps(obj,allow_nan=False)
    return obj


def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b


def score(raw):
    submitted=strict(raw)
    if not isinstance(submitted,dict):raise ValueError('RESPONSE_ROOT')
    case_bytes=(HERE/'CASES.json').read_bytes();cases=strict(case_bytes)['cases']
    expected_ids={c['id'] for c in cases}
    if set(submitted)-expected_ids:raise ValueError('UNKNOWN_CASE_ID')
    rows=[]
    for c in cases:
        correct=c['id'] in submitted and exact(submitted[c['id']],c['expected'])
        rows.append({'id':c['id'],'dimension':c['dimension'],'correct':correct,
                     'missing':c['id'] not in submitted,'critical_failure':c['critical'] and not correct})
    return {'schema':'QRCEL_SUBMITTED_DEVELOPMENT_SCORE_V1','scope':'SUBMITTED_BYTES_ONLY',
            'case_set_sha256':hashlib.sha256(case_bytes).hexdigest(),
            'response_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,
            'observed_model_id':None,'model_execution_verified':False,'sealed':False,
            'parity':'INSUFFICIENT_EVIDENCE'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--responses',type=Path,required=True);a=p.parse_args()
    try: print(json.dumps(score(a.responses.read_bytes()),sort_keys=True))
    except ValueError as e:
        print(json.dumps({'status':'INVALID_SUBMISSION','error':str(e),'model_execution_verified':False}))
        raise SystemExit(2)
