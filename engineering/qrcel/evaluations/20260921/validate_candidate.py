"""Validate isolated storage-cap candidate and bounded retry; never changes active release."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time,types,difflib
P=pathlib.Path;E=P(__file__).resolve().parent;S=E/'verified_release'
raw=(E/'validate_operational.py').read_bytes();h=types.ModuleType('op');h.__file__=str(E/'validate_operational.py');exec(compile(raw,h.__file__,'exec'),h.__dict__)
k,v=h.load(S)
original=(S/'cognitive/trusted_bootstrap.py').read_text()
old="resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,)*2)"
new="resource.setrlimit(resource.RLIMIT_FSIZE,((8 if args.entry == 'kernel' else 1)*1024*1024,)*2)"
assert original.count(old)==1
candidate=original.replace(old,new)
(E/'STORAGE_CAP_CANDIDATE.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/cognitive/trusted_bootstrap.py',tofile='b/cognitive/trusted_bootstrap.py')))
protocol={'schema':'QRCEL_TARGETED_CANDIDATE_VALIDATION_V1','active_release_unchanged':True,'parent_results_sha256':h.sha((E/'RESULTS.json').read_bytes()),
          'change':'8 MiB per file only for kernel entry; session and verify stay 1 MiB; accepted stdout stays 1 MiB',
          'cases':['large_plan_candidate_launcher','large_checkpoint_fresh_restore','bounded_retry_after_lock_release'],
          'criteria':['100 exact independent sums','2 MiB checkpoint exported','fresh restore zero newly completed','same checkpoint digest','external history prefix verified','blocked writer recovers without duplicates'],
          'wall_seconds':35,'model_calls':0,'production_promotion':False,'scope':'DEVELOPMENT_CANDIDATE_ONLY'}
(E/'CANDIDATE_PROTOCOL.json').write_bytes(h.canonical(protocol));records={}
with tempfile.TemporaryDirectory(prefix='qrcel-candidate-') as td:
 base=P(td);roots=[]
 for i in range(2):
  root=base/str(i);h.prepare(root,S,100,True,True);roots.append(root)
  path=root/'cognitive/trusted_bootstrap.py';path.write_text(candidate)
  mf=root/'cognitive/COGNITIVE_MANIFEST.json';m=json.loads(mf.read_bytes());m['files_sha256']['cognitive/trusted_bootstrap.py']=h.sha(path.read_bytes());m['evaluation_candidate']={'active_release':False,'purpose':'storage_limit_compatibility','parent_commit':h.RELEASE}
  b=h.canonical(m);mf.write_bytes(b);blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  p,g,_=h.make_plan(100,True)
  cmd=[sys.executable,'-I','-S','-B',str(path),'--repo-root',str(root),'--release-blob',blob,'--entry','kernel','--',
       '--plan',str(root/'plan.json'),'--plan-sha256',h.sha(h.canonical(p)),'--authority-blob',h.AUTH,'--run-id','eval',
       '--goal-contract',str(root/'goal.json'),'--goal-sha256',h.sha(h.canonical(g)),'--goal-mapping',str(root/'mapping.json')]
  if i:
   first=records['large_plan_candidate_launcher']['json'];cp=(roots[0]/'cognitive/runs/eval/checkpoint.json').read_bytes();(root/'import.json').write_bytes(cp)
   anchor=h.canonical(first['resume_anchor']);(root/'anchor.json').write_bytes(anchor)
   cmd+=['--restore',str(root/'import.json'),'--checkpoint-sha256',h.sha(cp),'--resume-anchor',str(root/'anchor.json'),'--resume-anchor-sha256',h.sha(anchor)]
  r=h.run_command(cmd,35);j=r.get('json',{});cp_path=root/'cognitive/runs/eval/checkpoint.json';cp=json.loads(cp_path.read_bytes()) if cp_path.exists() else {}
  exact=len(cp.get('completed',{}))==100 and all(x['output']=={'fraction':str(128*(10**64-1))} for x in cp.get('completed',{}).values())
  r['oracle_exact']=exact;r['checkpoint_bytes']=cp_path.stat().st_size if cp_path.exists() else None
  r['pass']=r['exit']==0 and exact and j.get('goal_completion',{}).get('status')=='EXPLICIT_REQUIREMENTS_SATISFIED'
  if i:r['pass']=r['pass'] and j.get('newly_completed')==0 and j.get('checkpoint_sha256')==first['checkpoint_sha256'] and j.get('history_authentication')=='EXTERNAL_PREFIX_VERIFIED'
  records['large_checkpoint_fresh_restore' if i else 'large_plan_candidate_launcher']=r
  assert r['pass'],r
 # Deliberate lock exceeds 2-second busy timeout; exactly one retry after owner releases.
 root=base/'retry';h.prepare(root,S,n=100)
 args=types.SimpleNamespace(source=S)
 first=h.run_command(h.command(args,root));assert first['exit']==0
 inspect=h.run_command(h.command(args,root,'inspect'));assert inspect['exit']==0
 import sqlite3
 db=sqlite3.connect(root/'cognitive/runs/eval/state.sqlite',isolation_level=None);db.execute('BEGIN IMMEDIATE')
 try:blocked=h.run_command(h.command(args,root),6)
 finally:db.rollback();db.close()
 retried=h.run_command(h.command(args,root));j=retried.get('json',{})
 records['bounded_retry_after_lock_release']={'blocked':blocked,'retry':retried,'attempts':2,'pass':blocked['exit']==2 and retried['exit']==0 and j.get('newly_completed')==0 and j.get('completed_tasks')==100 and j.get('checkpoint_sha256')==first['json']['checkpoint_sha256']}
 assert records['bounded_retry_after_lock_release']['pass']
 records['candidate_identity']={'manifest_blob':blob,'launcher_sha256':h.sha(candidate.encode()),'patch_sha256':h.sha((E/'STORAGE_CAP_CANDIDATE.diff').read_bytes()),'promoted':False}
(E/'CANDIDATE_RESULTS.json').write_bytes(h.canonical({'protocol_sha256':h.sha(h.canonical(protocol)),'records':records,'active_release_changed':False}))
print(json.dumps({key:val.get('pass') for key,val in records.items() if 'pass' in val}))
