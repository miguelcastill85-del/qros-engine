"""Execute predeclared component experiments. Counts are not native-model scores."""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent


def digest(raw):return hashlib.sha256(raw).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def run(out):
    out.mkdir(exist_ok=False)
    prereg=json.loads((HERE/'PREREGISTRATION.json').read_bytes())
    spec={'nodes':prereg['nodes'],'base':prereg['base'],'step':prereg['step'],
          'worker_sha256':digest((HERE/'worker.py').read_bytes())}
    # Oracle does not run the worker recurrence: closed-form arithmetic progression.
    expected=[spec['base']*(i+1)+spec['step']*i*(i+1)//2 for i in range(spec['nodes'])]
    records=[]
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8'}
    for scenario in prereg['cases']:
        for variant in prereg['variants']:
            with tempfile.TemporaryDirectory(prefix='qrcel-dev-') as tmp:
                root=Path(tmp);spec_path=root/'spec.json';write(spec_path,spec)
                attempts=[]
                def invoke(fault='NONE'):
                    before=time.monotonic()
                    p=subprocess.run([sys.executable,str(HERE/'worker.py'),'--root',str(root),
                        '--variant',variant,'--spec',str(spec_path),'--expected-spec-sha256',digest(spec_path.read_bytes()),
                        '--fault',fault],env=env,capture_output=True,timeout=15)
                    a={'exit_code':p.returncode,'wall_seconds':time.monotonic()-before,
                       'stdout':p.stdout.decode(),'stderr':p.stderr.decode()};attempts.append(a);return a
                if scenario.startswith('CRASH_'):
                    first=invoke('AFTER' if scenario=='CRASH_AFTER_NODE_16' else 'BEFORE')
                    assert first['exit_code']==75,first
                    final=invoke()
                elif scenario in ('CORRUPT_DURABLE_OUTPUT','INPUT_IDENTITY_CHANGED'):
                    assert invoke()['exit_code']==0
                    if scenario=='INPUT_IDENTITY_CHANGED':
                        changed=dict(spec,base=spec['base']+1);write(spec_path,changed)
                    elif variant=='SQLITE_TRANSACTION_PREFIX':
                        db=sqlite3.connect(root/'state.sqlite');db.execute('UPDATE results SET value=value+1 WHERE idx=0');db.commit();db.close()
                    else:
                        state=json.loads((root/'state.json').read_bytes());state['records'][0]['value']+=1;write(root/'state.json',state)
                    final=invoke()
                else:final=invoke()
                negative=scenario in ('CORRUPT_DURABLE_OUTPUT','INPUT_IDENTITY_CHANGED')
                answer=json.loads(final['stdout']) if final['stdout'] else {}
                if negative:
                    correct=final['exit_code']==2 and answer.get('status')=='FAIL_CLOSED'
                    expected_error='INPUT_IDENTITY_MISMATCH' if scenario=='INPUT_IDENTITY_CHANGED' else 'DURABLE_OUTPUT_INVALID'
                    correct=correct and answer.get('error')==expected_error
                else:
                    result=json.loads((root/'output.json').read_bytes()) if (root/'output.json').exists() else {}
                    raw=(json.dumps(expected,sort_keys=True,separators=(',',':'))+'\n').encode()
                    correct=final['exit_code']==0 and result.get('values')==expected and result.get('sha256')==digest(raw)
                events=[json.loads(line)['event'] for line in (root/'events.jsonl').read_text().splitlines()]
                records.append({'scenario':scenario,'variant':variant,'correct':correct,'attempts':attempts,
                    'solver_calls':events.count('SOLVE'),'commit_count':events.count('COMMIT'),
                    'artifact_bytes':sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
                    'wall_seconds':sum(a['wall_seconds'] for a in attempts)})
                write(out/'PARTIAL_RESULTS.json',records)
    receipt={'schema':'QRCEL_CONTINUITY_COMPONENT_RESULTS_V1','scope':prereg['scope'],
        'preregistration_sha256':digest((HERE/'PREREGISTRATION.json').read_bytes()),
        'worker_sha256':spec['worker_sha256'],'scorer_sha256':digest(Path(__file__).read_bytes()),
        'python_version':sys.version,'sqlite_version':sqlite3.sqlite_version,'records':records,
        'correct':sum(r['correct'] for r in records),'total':len(records),
        'state':'PASS_COMPONENT_EXPERIMENT' if all(r['correct'] for r in records) else 'FAIL',
        'model_calls':0,'sealed_cases':0,'scientific_writes':0,'full_architecture_selected':False,
        'parity':'INSUFFICIENT_EVIDENCE'}
    write(out/'RESULTS.json',receipt)
    print(json.dumps({'state':receipt['state'],'correct':receipt['correct'],'total':receipt['total'],
          'summary':[{k:r[k] for k in ('scenario','variant','correct','solver_calls','commit_count')} for r in records]}))
    return 0 if all(r['correct'] for r in records) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    raise SystemExit(run(p.parse_args().output))
