"""Reproduce the authorized V190 -> V191 metadata-only reconciliation offline."""
import copy, hashlib, importlib.util, json, pathlib, platform, sqlite3, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
BASE = ROOT / 'baseline'
OUT = ROOT / 'candidate'
MF = 'control/CONTROL_AUTHORITY_MANIFEST_v3.json'
REG = 'control/QROS_ACTIVE_HASH_REGISTRY_V191_v1.json'
RECEIPT = 'control/reconciliation/V191/VALIDATION_RECEIPT.json'
ROLES = {'head':'control/HEAD.json','state':'control/persistent_execution/STATE.json','run_queue':'control/persistent_execution/RUN_QUEUE.json'}
LEGACY = ['control/CONTROL_AUTHORITY_MANIFEST_v1.json','control/CONTROL_AUTHORITY_MANIFEST_v2.json','control/SCIENTIFIC_HEAD.json','control/RUN_QUEUE.json','control/RUN_QUEUE_v2.json','control/RUN_QUEUE_v3.json','control/CURRENT_RUNTIME_DATA_IO_RECOVERY_v1.json']
def raw(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode()
def blob(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def read(path): return json.loads((BASE/path).read_bytes())
def write(root,path,data):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

def build():
    old=read(MF)
    assert old['authority_epoch']==190
    changes={}
    for role,path in ROLES.items():
        obj=read(path);obj['authority_epoch']=191
        obj['schema']=obj['schema'].replace('_V190','_V191')
        obj['scientific_execution_authorization_source']=MF
        changes[path]=raw(obj)
    for path in ['control/CONTROL_AUTHORITY_MANIFEST_v1.json','control/RUN_QUEUE.json','control/RUN_QUEUE_v3.json']:
        archive='control/legacy/authority_v191/'+path.split('/')[-1]+'.original.json'
        changes[archive]=(BASE/path).read_bytes()
        obj={'schema':'QROS_LEGACY_AUTHORITY_REDIRECT_V191','status':'DEPRECATED_REDIRECT_ONLY','active_authority':MF,'must_not_bootstrap':True,'must_not_execute':True,'scientific_execution_authorized':False,'archived_original':archive,'reason':'USER_AUTHORIZED_SINGLE_AUTHORITY_RECONCILIATION_V191'}
        if 'RUN_QUEUE' in path: obj['active_run_queue']=ROLES['run_queue']
        changes[path]=raw(obj)
    m=copy.deepcopy(old);m['authority_epoch']=191;m['scientific_execution_authorized']=False
    m['active_hash_registry']=REG
    m['reconciliation_receipt']=RECEIPT
    m['reconciliation_parent']={'manifest_blob_sha1':blob((BASE/MF).read_bytes()),'authority_epoch':190,'scientific_scope_change':False}
    m['legacy_redirects']=[{'path':p,'git_blob_sha1':blob(changes.get(p,(BASE/p).read_bytes()))} for p in LEGACY]
    for role,path in ROLES.items():m['single_active_authority'][role]['git_blob_sha1']=blob(changes[path])
    registry={'schema':'QROS_ACTIVE_HASH_REGISTRY_V191_V1','authority_epoch':191,'authority_blobs':{role+'_git_blob_sha1':blob(changes[path]) for role,path in ROLES.items()},'inherited_registry':{'path':old['active_hash_registry'],'git_blob_sha1':blob((BASE/old['active_hash_registry']).read_bytes())},'legacy_redirects':m['legacy_redirects'],'manifest_identity_policy':'Manifest blob is recorded by phase readback receipts, outside this registry to avoid a content-hash cycle.','scientific_scope_change':False}
    changes[REG]=raw(registry);m['active_hash_registry_git_blob_sha1']=blob(changes[REG]);changes[MF]=raw(m)
    for path,data in changes.items():write(OUT,path,data)
    for path in LEGACY:
        if path not in changes:write(OUT,path,(BASE/path).read_bytes())
    return changes

def validate(changes,validator_path):
    vm=read('control/QROS_CONTROL_AUTHORITY_VALIDATOR_V2_MANIFEST_v1.json')
    vb=validator_path.read_bytes();assert hashlib.sha256(vb).hexdigest()==vm['raw_sha256']
    compile(vb,str(validator_path),'exec')
    spec=importlib.util.spec_from_file_location('official_validator',validator_path);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    def run(docs,require=False):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            for p,b in docs.items():write(root,p,b)
            return v.validate(*[root/p for p in [MF,*ROLES.values()]],require_execution=require)
    tests=[]
    def case(name,docs,want,require=False,error=None):
        r=run(docs,require);assert r['status']==want,(name,r)
        if error:assert any(x.startswith(error) for x in r['errors']),(name,r)
        tests.append({'case':name,'expectation_met':True,'result':r})
    baseline={p:(BASE/p).read_bytes() for p in [MF,*ROLES.values()]}
    case('observed_v190_missing_head_delegation',baseline,'FAIL',error='AUTH_SOURCE_MISMATCH:head:None')
    case('valid_not_authorized',changes,'PASS')
    case('require_exec_rejects_false',changes,'FAIL',True,'EXECUTION_NOT_AUTHORIZED')
    enabled=dict(changes);m=json.loads(enabled[MF]);m['scientific_execution_authorized']=True;enabled[MF]=raw(m)
    case('valid_authorized',enabled,'PASS',True)
    for name,role,key,value,error in [('campaign_mismatch','head','campaign','OTHER','CAMPAIGN_MISMATCH'),('epoch_mismatch','state','authority_epoch',190,'EPOCH_MISMATCH'),('blob_mismatch','run_queue','extra','tampered','BLOB_MISMATCH'),('delegation_regression','head','scientific_execution_authorization_source','control/SCIENTIFIC_HEAD.json','AUTH_SOURCE_MISMATCH')]:
        d=dict(changes);o=json.loads(d[ROLES[role]]);o[key]=value;d[ROLES[role]]=raw(o);case(name,d,'FAIL',error=error)
    # Independent semantic oracle: only schema, epoch and delegation may change in roles.
    for role,path in ROLES.items():
        before=read(path);after=json.loads(changes[path])
        for o in (before,after):
            for k in ('schema','authority_epoch','scientific_execution_authorization_source'):o.pop(k,None)
        assert before==after,('SCIENTIFIC_SEMANTICS_CHANGED',role)
    before=read(MF);after=json.loads(changes[MF])
    for k in ('campaign','scientific_execution_scope','reason','non_promoted_evidence_rule','bootstrap_contract','audit_receipt','governance','validator_manifest','validator_selftest','runtime_capability'):assert before[k]==after[k],k
    for role,path in ROLES.items():assert 'scientific_execution_authorized' not in json.loads(changes[path])
    for ref in after['legacy_redirects']:
        b=changes.get(ref['path'],(BASE/ref['path']).read_bytes());o=json.loads(b)
        assert blob(b)==ref['git_blob_sha1'] and 'DEPRECATED' in o['status']
        if ref['path'].endswith('CURRENT_RUNTIME_DATA_IO_RECOVERY_v1.json'):assert o['runtime_capability_inheritable'] is False
        else:assert o['active_authority']==MF and o['must_not_bootstrap'] is True
    for path,b in changes.items():
        if '/legacy/authority_v191/' in path:
            original='control/'+path.split('/')[-1].replace('.original.json','');assert b==(BASE/original).read_bytes()
    # Physical current-session transaction probe, no inherited snapshot.
    with tempfile.TemporaryDirectory() as td:
        conn=sqlite3.connect(str(pathlib.Path(td)/'probe.sqlite'));conn.execute('CREATE TABLE probe(x)');conn.execute('INSERT INTO probe VALUES(1)');conn.commit();assert conn.execute('SELECT x FROM probe').fetchone()==(1,);conn.close()
    receipt={'schema':'QROS_AUTHORITY_RECONCILIATION_VALIDATION_V191','scope':'CONTROL_METADATA_ONLY_NO_SCIENTIFIC_RUN','status':'PASS','user_authorization':'Reconciliala tu mismo y sigue adelante','before_epoch':190,'candidate_epoch':191,'official_validator_sha256':vm['raw_sha256'],'cases':tests,'all_six_historical_selftest_cases_reexecuted':True,'missing_delegation_regression':True,'scientific_semantic_equality':True,'legacy_redirects_verified':len(LEGACY),'archives_byte_equal':True,'runtime':{'python':sys.version,'platform':platform.system(),'sqlite_local_transaction':'PASS','inheritable':False},'economic_reads':0,'scientific_dispatches':0,'mt5_executions':0,'additional_paid_services':0,'import_verifier':'UNVERIFIED_FULL_NATIVE_HANDOFF_MANIFEST_NOT_MATERIALIZED; control and validator bytes verified separately','changed_files':{p:blob(b) for p,b in changes.items()}}
    changes[RECEIPT]=raw(receipt);write(OUT,RECEIPT,changes[RECEIPT])
    return receipt

if __name__=='__main__':
    if not BASE.exists():
        bundle=json.loads((ROOT/'source_bundle.json').read_text())
        for item in bundle['files']:
            b=item['content'].encode();assert blob(b)==item['sha'];write(BASE,item['path'],b)
    changes=build();receipt=validate(changes,pathlib.Path(sys.argv[1]));
    (ROOT/'publish_disabled.json').write_text(json.dumps([{'path':p,'content':b.decode(),'sha':blob(b)} for p,b in changes.items()]))
    print(json.dumps({'status':receipt['status'],'cases':len(receipt['cases']),'files':len(changes),'semantic_equality':True,'legacy_redirects':len(LEGACY)}))
