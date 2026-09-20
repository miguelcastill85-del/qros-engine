"""Verified, non-authorizing session bootstrap. No scientific or model dispatch."""
import argparse
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from . import runtime as v
from .verify_release import verify
from .validate_candidate import atomic_write
from .qros_controller_adapter import inspect as inspect_controller

CONFIG='cognitive/ACTIVATION.json'
MODULES={'L0':['CORE_CONSTITUTION','AUTHORITY_BOOTSTRAP','TOOL_POLICY'],
         'L1':['CORE_CONSTITUTION','AUTHORITY_BOOTSTRAP','TOOL_POLICY','COGNITIVE_PROTOCOL'],
         'L2':['CORE_CONSTITUTION','AUTHORITY_BOOTSTRAP','TOOL_POLICY','COGNITIVE_PROTOCOL'],
         'L3':['CORE_CONSTITUTION','AUTHORITY_BOOTSTRAP','TOOL_POLICY','COGNITIVE_PROTOCOL','SCIENTIFIC_PROTOCOL']}

def start(root,release_blob,objective,level='L1',mode='REFERENCE_ONLY',active_root=None,active_blob=None):
    root=Path(root).resolve()
    captured={}
    integrity=verify(root,release_blob,captured=captured)
    snapshot=v.FrozenSnapshot(captured);config,_=snapshot.json(CONFIG)
    v.require(config.get('schema')=='QRCEL_SESSION_ACTIVATION_V1','ACTIVATION_SCHEMA')
    v.require(config.get('scientific_dispatch') is False,'ACTIVATION_NOT_AUTHORITY')
    v.require(level in MODULES,'UNKNOWN_DEPTH')
    v.require(mode in ('REFERENCE_ONLY','ACTIVE_INSPECTION'),'UNKNOWN_SESSION_MODE')
    v.require(isinstance(objective,str) and 0<len(objective)<=16000,'TASK_OBJECTIVE')
    v.require((active_root is None)==(active_blob is None),'ACTIVE_ANCHOR_REQUIRED')
    v.require(mode!='REFERENCE_ONLY' or active_root is None,'REFERENCE_ACTIVE_ARGUMENTS')
    ref=config['reference'];v.require(ref.get('epoch')==191 and ref.get('role')=='HISTORICAL_ENGINEERING_REFERENCE','REFERENCE_ROLE')
    v.relative_parts(ref['local_root']);reference=root/ref['local_root']
    observation=v.observe_authority(v.Snapshot(reference),ref['manifest_blob_sha1'])
    v.require(observation.manifest['authority_epoch']==191,'REFERENCE_EPOCH')
    bootstrap=v.inspect_control_bootstrap(v.Snapshot(reference),ref['manifest_blob_sha1'])
    v.require(bootstrap['status']=='PASS','REFERENCE_BOOTSTRAP_FAILED')
    controller=inspect_controller(reference,ref['manifest_blob_sha1'],'next')
    active={'status':'NOT_REQUESTED','scientific_authority_selected':False}
    if mode=='ACTIVE_INSPECTION':
        v.require(active_root is not None,'ACTIVE_AUTHORITY_REQUIRED')
        checked=v.inspect_control_bootstrap(v.Snapshot(Path(active_root)),active_blob)
        v.require(checked.get('status')=='PASS','ACTIVE_BOOTSTRAP_UNSUPPORTED')
        active={'status':'VERIFIED_CONTROL_BYTES_ONLY','manifest_blob_sha1':active_blob,'dispatch_authorized':False}
    modules=[]
    for name in MODULES[level]:
        raw=snapshot.read('cognitive/prompts/'+name+'.md')
        modules.append({'id':name,'sha256':v.sha256(raw),'trust_zone':'PROJECT_SPEC_TRUST','text':raw.decode()})
    # Recompute narrow physical capability, never reuse an old runtime claim.
    with tempfile.TemporaryDirectory(prefix='qrcel-capability-') as temp:
        db=sqlite3.connect(str(Path(temp)/'probe.sqlite'))
        try:
            journal=db.execute('PRAGMA journal_mode=WAL').fetchone()[0]
            db.execute('CREATE TABLE probe(value INTEGER)');db.execute('INSERT INTO probe VALUES (1)');db.commit()
            v.require(db.execute('SELECT value FROM probe').fetchall()==[(1,)],'SQLITE_PROBE_FAILED')
        finally:db.close()
    return {'schema':'QRCEL_SESSION_V1','status':'ACTIVE_NON_SCIENTIFIC_ASSISTANCE','session_id':str(uuid.uuid4()),
        'observed_at_ns':time.time_ns(),'pid':os.getpid(),'release_manifest_blob_sha1':release_blob,
        'release_integrity':integrity,'reference':ref,'reference_bootstrap':bootstrap,'reference_controller':controller,'active_control':active,
        'mode':mode,'depth':level,'routing_reason':'Host-selected risk class; L3 requires existing scientific gates before any scientific action',
        'task_spec':{'objective':objective,'trust_zone':'USER_DATA','sha256':v.sha256(objective.encode())},
        'modules':modules,'capability':{'inheritable':False,'sqlite_transaction_observed':True,'journal_mode':journal,
            'model_route_verified':False,'network_access_tested':False,'trading_runtime_tested':False},
        'pending_state':snapshot.json('cognitive/COGNITIVE_STATE.json')[0],
        'scientific_dispatch_authorized':False,'qrcel_promoted':False,'background_running':False,
        'automatic_future_chat_execution_guaranteed':False}

def save(root,receipt):
    # New session-only output; no shared HEAD, queue, existing checkpoint or authority writes.
    base=Path(root).resolve()/'cognitive'
    v.require(base.is_dir() and not base.is_symlink(),'SESSION_NAMESPACE')
    parent=base/'sessions';v.require(not parent.is_symlink(),'SESSION_NAMESPACE');parent.mkdir(exist_ok=True)
    identity=receipt['session_id'];v.require(str(uuid.UUID(identity))==identity,'SESSION_ID')
    out=parent/identity;out.mkdir(exist_ok=False)
    raw=v.canonical(receipt);atomic_write(out/'SESSION.json',raw)
    atomic_write(out/'CHECKPOINT.json',v.canonical({'schema':'QRCEL_SESSION_CHECKPOINT_V1','session_sha256':v.sha256(raw),
        'release_manifest_blob_sha1':receipt['release_manifest_blob_sha1'],'scientific_authority':False,'runtime_capability_reusable':False}))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo-root',required=True,type=Path);p.add_argument('--release-blob',required=True)
    p.add_argument('--objective',required=True);p.add_argument('--depth',default='L1',choices=MODULES)
    p.add_argument('--mode',default='REFERENCE_ONLY',choices=['REFERENCE_ONLY','ACTIVE_INSPECTION'])
    p.add_argument('--active-root',type=Path);p.add_argument('--active-blob');p.add_argument('--save',action='store_true')
    a=p.parse_args()
    try:
        result=start(a.repo_root,a.release_blob,a.objective,a.depth,a.mode,a.active_root,a.active_blob)
        if a.save:result['checkpoint_directory']=str(save(a.repo_root,result))
        print(v.canonical(result).decode(),end='');return 0
    except v.ContractError as e:
        print(v.canonical({'status':'FAIL_CLOSED','error':e.code,'scientific_dispatch_authorized':False}).decode(),end='');return 2
if __name__=='__main__':raise SystemExit(main())
