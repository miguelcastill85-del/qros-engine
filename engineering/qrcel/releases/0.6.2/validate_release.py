"""Reproducible final-release test: four large-plan writers and anchored restore."""
import argparse,base64,gzip,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
P=pathlib.Path
can=lambda x:(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
sha=lambda b:hashlib.sha256(b).hexdigest()
AUTH='5afce6279994b8625bd79fb2d5d13924e3c561e7'
p=argparse.ArgumentParser();p.add_argument('--source',type=P,required=True);p.add_argument('--anchors',type=P,required=True);p.add_argument('--out',type=P,required=True);a=p.parse_args();a.source=a.source.resolve();a.out.mkdir(exist_ok=True,parents=True);anchors=json.loads(a.anchors.read_bytes());mf=a.source/'cognitive/COGNITIVE_MANIFEST.json';raw=mf.read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==anchors['manifest_blob'];m=json.loads(raw)
assert sha((a.source/'cognitive/trusted_bootstrap.py').read_bytes())==anchors['launcher_sha256']
for n,h in m['files_sha256'].items():assert sha((a.source/n).read_bytes())==h,n
inputs={'numbers':['9'*64]*128,'include_parent_sums':False};tasks=[{'task_id':f'T{i:03}','parent_ids':[],'objective':'Synthetic admission validation','operation':'EXACT_SUM','inputs':inputs,'inputs_sha256':sha(can(inputs)),'risk':'NORMAL'} for i in range(100)]
plan={'schema':'QRCEL_LOCAL_TASK_PLAN_V1','scope':'NON_SCIENTIFIC_LOCAL','tasks':tasks};goal={'schema':'QRCEL_EXPLICIT_GOAL_CONTRACT_V1','scope':'EXPLICIT_LOCAL_REQUIREMENTS_ONLY','goal_id':'ADMISSION-100','description':'Synthetic arithmetic goal; no trading research','requirements':[{'id':'R'+t['task_id'],'operation':t['operation'],'inputs_sha256':t['inputs_sha256'],'parent_ids':[],'minimum_risk':'NORMAL'} for t in tasks]};mapping={'R'+t['task_id']:t['task_id'] for t in tasks}
protocol={'schema':'QRCEL_ADMISSION_FINAL_PROTOCOL_V1','manifest_blob':anchors['manifest_blob'],'workers':4,'tasks':100,'admission_wait_seconds':10,'wall_seconds_per_invocation':30,'oracle':'128*(10**64-1), independently for each task','criteria':['all four writers exit successfully','sum newly_completed=100','exact outputs=100','ledger_events=200','all checkpoint digests agree','fresh restore zero new tasks and same digest','external history prefix verified'],'scope':'SYNTHETIC_DEVELOPMENT','model_calls':0,'scientific_dispatches':0}
(a.out/'PROTOCOL.json').write_bytes(can(protocol))
def prepare(root):
 root.mkdir()
 for n in ['cognitive/COGNITIVE_MANIFEST.json',*m['files_sha256']]:
  path=root/n;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((a.source/n).read_bytes())
 shutil.copytree(root/'cognitive/tests/fixtures/v191',root,dirs_exist_ok=True)
 for n,v in [('PLAN.json',plan),('GOAL.json',goal),('MAPPING.json',mapping)]:(root/n).write_bytes(can(v))
def base(root):return [sys.executable,'-I','-S','-B',str(root/'cognitive/trusted_bootstrap.py'),'--repo-root',str(root),'--release-blob',anchors['manifest_blob']]
def command(root):return base(root)+['--entry','kernel','--','--plan',str(root/'PLAN.json'),'--plan-sha256',sha(can(plan)),'--authority-blob',AUTH,'--run-id','shared','--goal-contract',str(root/'GOAL.json'),'--goal-sha256',sha(can(goal)),'--goal-mapping',str(root/'MAPPING.json')]
def collect(p):
 out,err=p.communicate(timeout=35);r={'exit':p.returncode,'stdout':out,'stderr':err}
 try:r['receipt']=json.loads(out)
 except ValueError:pass
 return r
def start(cmd):return subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={'PATH':os.defpath,'LANG':'C.UTF-8'})
children=[];results=[]
try:
 with tempfile.TemporaryDirectory(prefix='qrcel-final-admission-') as td:
  root=P(td)/'first';prepare(root);started=time.monotonic()
  for _ in range(4):children.append(start(command(root)))
  for proc in children:
   results.append(collect(proc));(a.out/'PARTIAL_RESULTS.json').write_bytes(can(results))
  assert all(r['exit']==0 for r in results),results
  assert sum(r['receipt']['newly_completed'] for r in results)==100
  assert len({r['receipt']['checkpoint_sha256'] for r in results})==1
  cp=(root/'cognitive/runs/shared/checkpoint.json').read_bytes();obj=json.loads(cp);assert len(obj['completed'])==100 and len(obj['ledger'])==200
  assert all(v['output']=={'fraction':str(128*(10**64-1))} for v in obj['completed'].values())
  assert all(r['receipt']['goal_completion']['status']=='EXPLICIT_REQUIREMENTS_SATISFIED' for r in results)
  (a.out/'CHECKPOINT.json').write_bytes(cp);anchor=can(results[0]['receipt']['resume_anchor']);(a.out/'RESUME_ANCHOR.json').write_bytes(anchor)
  for n,v in [('PLAN.json',plan),('GOAL.json',goal),('MAPPING.json',mapping)]:(a.out/n).write_bytes(can(v))
  fresh=P(td)/'fresh';prepare(fresh);(fresh/'input.json').write_bytes(cp);(fresh/'anchor.json').write_bytes(anchor)
  proc=start(command(fresh)+['--restore',str(fresh/'input.json'),'--checkpoint-sha256',sha(cp),'--resume-anchor',str(fresh/'anchor.json'),'--resume-anchor-sha256',sha(anchor)]);children.append(proc);restored=collect(proc)
  assert restored['exit']==0,restored;r=restored['receipt'];assert r['newly_completed']==0 and r['checkpoint_sha256']==sha(cp) and r['history_authentication']=='EXTERNAL_PREFIX_VERIFIED'
  proc=start(base(fresh)+['--entry','session','--','--objective','Validate local admission and durable recovery','--depth','L2','--save']);children.append(proc);session=collect(proc);assert session['exit']==0,session
  directory=P(session['receipt']['checkpoint_directory'])
  (a.out/'SESSION.json').write_bytes((directory/'SESSION.json').read_bytes());(a.out/'SESSION_CHECKPOINT.json').write_bytes((directory/'CHECKPOINT.json').read_bytes())
  receipt={'schema':'QRCEL_ADMISSION_FINAL_VALIDATION_V1','status':'PASS','protocol_sha256':sha(can(protocol)),'source_anchors':anchors,'writers':results,'restored':restored,'session':session,'exact_outputs':100,'ledger_events':200,'checkpoint_bytes':len(cp),'seconds_diagnostic_only':time.monotonic()-started,'scientific_dispatches':0,'model_calls':0,'full_qrcel_complete':False}
  (a.out/'FRESH_VALIDATION.json').write_bytes(can(receipt))
finally:
 for proc in children:
  if proc.poll() is None:
   proc.terminate()
   try:proc.communicate(timeout=3)
   except subprocess.TimeoutExpired:proc.kill();proc.communicate(timeout=3)
capsule={'schema':'QRCEL_GZIP_BASE64_RECOVERY_CAPSULE_V1','scope':'SYNTHETIC_NON_SCIENTIFIC_LARGE_PLAN','decode_limit_bytes_per_file':4194304,'files':{}}
for n in ['PLAN.json','GOAL.json','MAPPING.json','CHECKPOINT.json','RESUME_ANCHOR.json']:
 b=(a.out/n).read_bytes();z=gzip.compress(b,mtime=0);assert gzip.decompress(z)==b;capsule['files'][n]={'encoding':'gzip+base64','uncompressed_bytes':len(b),'sha256':sha(b),'compressed_sha256':sha(z),'data':base64.b64encode(z).decode()}
(a.out/'RECOVERY_CAPSULE.json').write_bytes(can(capsule));print('PASS: four writers, 100 exact results, 200 events, same checkpoint, fresh restore zero new tasks, session capability')
