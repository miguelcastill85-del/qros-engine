#!/usr/bin/env python3
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import qros_recursive_effect_executor_v1 as ex

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_worker(p:Path):
    p.write_text(r"""
import hashlib,json,sys
from pathlib import Path
d=Path(sys.argv[1]); r=Path(sys.argv[2])
a=d/'artifact.bin'; a.write_bytes(b'abc123')
receipt={
 'status':'PASS',
 'unit':'U',
 'artifacts':[{'path':'artifact.bin','bytes':a.stat().st_size,'sha256':hashlib.sha256(a.read_bytes()).hexdigest()}]
}
r.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
""")

def wait_dead(pid,timeout=25):
    end=time.time()+timeout
    while time.time()<end:
        if ex.process_birth(pid) is None:return
        time.sleep(0.02)
    raise AssertionError('BOOTSTRAP_NOT_EXITED')

with tempfile.TemporaryDirectory() as td:
    root=Path(td); worker=root/'worker.py'; write_worker(worker)
    intent={
      'schema':ex.INTENT_SCHEMA,
      'effect_id':'effect-0001',
      'command':[sys.executable,str(worker),'{effect_dir}','{receipt}'],
      'expected_receipt':{'status':'PASS','unit':'U'},
      'artifacts_required':True
    }
    ip=root/'intent.json'; ip.write_text(json.dumps(intent))
    work=root/'work'

    # deterministic intent identity
    assert ex.validate_intent(intent)==ex.validate_intent(dict(intent))

    # first invocation only launches
    a=ex.controller(ip,work)
    assert a['state']=='RUNNING' and a['action']=='LAUNCHED'
    effect=work/intent['effect_id']
    claim=json.loads((effect/'claim.json').read_text())
    token=claim['claim_token']

    # duplicate while live never creates a second claim/effect
    b=ex.controller(ip,work)
    assert b['action'] in {'ADOPT_LAUNCH','ADOPT_BOOTSTRAP','ADOPT_WORKER','PROMOTE_DONE'}
    assert json.loads((effect/'claim.json').read_text())['claim_token']==token

    if b['action']!='PROMOTE_DONE':
        wait_dead(a['bootstrap_pid'])
        c=ex.controller(ip,work)
        assert c['state']=='PASS' and c['action']=='PROMOTE_DONE'
    d=ex.controller(ip,work)
    assert d['state']=='PASS' and d['action']=='REUSE_DONE'

    # tamper after done is detected
    (effect/'artifact.bin').write_bytes(b'bad')
    e=ex.controller(ip,work)
    assert e['state']=='FAIL' and e['action']=='DONE_INVALID'

with tempfile.TemporaryDirectory() as td:
    root=Path(td); work=root/'work'; effect=work/'effect-0002'; effect.mkdir(parents=True)
    intent={
      'schema':ex.INTENT_SCHEMA,'effect_id':'effect-0002','command':['unused'],
      'expected_receipt':{'status':'PASS'},'artifacts_required':True}
    ip=root/'intent.json';ip.write_text(json.dumps(intent))
    # Crash-after-worker-before-exit: valid receipt/artifact with claim, no live identities, no exit.
    a=effect/'artifact.bin';a.write_bytes(b'xyz')
    (effect/'worker_receipt.json').write_text(json.dumps({'status':'PASS','artifacts':[{'path':'artifact.bin','bytes':3,'sha256':hashlib.sha256(b'xyz').hexdigest()}]}))
    spec=ex.validate_intent(intent)
    ex.atomic_json(effect/'claim.json',{'schema':ex.SCHEMA,'effect_id':'effect-0002','spec_sha256':spec,'claim_token':'t','command':['unused'],'command_sha256':'x','created_at':ex.utc_now()})
    x=ex.controller(ip,work)
    assert x['state']=='PASS' and x['action']=='PROMOTE_DONE'

# Invalid path traversal must fail receipt validation.
with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    intent={'schema':ex.INTENT_SCHEMA,'effect_id':'effect-0003','command':['unused'],'expected_receipt':{'status':'PASS'},'artifacts_required':True}
    (d/'worker_receipt.json').write_text(json.dumps({'status':'PASS','artifacts':[{'path':'../x','bytes':1,'sha256':'0'*64}]}))
    ok,why,_=ex.validate_receipt(d,intent)
    assert not ok and why=='ARTIFACT_PATH'

print('PASS executor lifecycle=1 duplicate=1 crash_resume=1 tamper=1 traversal=1')
