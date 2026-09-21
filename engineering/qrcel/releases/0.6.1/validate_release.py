"""Final frozen release launcher: large plan, fresh restore, session capability."""
import hashlib,json,pathlib,sys,tempfile,types
P=pathlib.Path;E=P(__file__).resolve().parent;S=E.parent/'qrcel_storage_061_20260921';A=json.loads((E/'RELEASE_061_ANCHORS.json').read_bytes())
h=types.ModuleType('op');h.__file__=str(E/'validate_operational.py');exec(compile(P(h.__file__).read_bytes(),h.__file__,'exec'),h.__dict__)
assert h.sha((S/'cognitive/trusted_bootstrap.py').read_bytes())==A['launcher_sha256']
results=[]
with tempfile.TemporaryDirectory(prefix='qrcel-release-061-') as td:
 roots=[]
 for i in range(2):
  root=P(td)/str(i);h.prepare(root,S,n=100,large=True,full=True);roots.append(root);p,g,_=h.make_plan(100,True)
  base=[sys.executable,'-I','-S','-B',str(root/'cognitive/trusted_bootstrap.py'),'--repo-root',str(root),'--release-blob',A['manifest_blob']]
  cmd=base+['--entry','kernel','--','--plan',str(root/'plan.json'),'--plan-sha256',h.sha(h.canonical(p)),'--authority-blob',h.AUTH,'--run-id','eval','--goal-contract',str(root/'goal.json'),'--goal-sha256',h.sha(h.canonical(g)),'--goal-mapping',str(root/'mapping.json')]
  if i:
   cp=(roots[0]/'cognitive/runs/eval/checkpoint.json').read_bytes();anchor=h.canonical(results[0]['json']['resume_anchor']);(root/'input.json').write_bytes(cp);(root/'anchor.json').write_bytes(anchor)
   cmd+=['--restore',str(root/'input.json'),'--checkpoint-sha256',h.sha(cp),'--resume-anchor',str(root/'anchor.json'),'--resume-anchor-sha256',h.sha(anchor)]
  r=h.run_command(cmd,35);assert r['exit']==0,r;j=r['json'];cp=(root/'cognitive/runs/eval/checkpoint.json').read_bytes();obj=json.loads(cp)
  assert len(obj['completed'])==100 and len(obj['ledger'])==200
  assert all(v['output']=={'fraction':str(128*(10**64-1))} for v in obj['completed'].values())
  assert j['goal_completion']['status']=='EXPLICIT_REQUIREMENTS_SATISFIED'
  if i:assert j['newly_completed']==0 and j['checkpoint_sha256']==results[0]['json']['checkpoint_sha256'] and j['history_authentication']=='EXTERNAL_PREFIX_VERIFIED'
  r['checkpoint_bytes']=len(cp);results.append(r)
  if not i:
   for name,data in [('LARGE_PLAN.json',h.canonical(p)),('LARGE_GOAL.json',h.canonical(g)),('LARGE_MAPPING.json',(root/'mapping.json').read_bytes()),('LARGE_CHECKPOINT.json',cp),('LARGE_RESUME_ANCHOR.json',h.canonical(j['resume_anchor']))]:(E/name).write_bytes(data)
 session=h.run_command(base+['--entry','session','--','--objective','Validate QRCEL 0.6.1 operational recovery; synthetic engineering only','--depth','L2','--save'],35)
 assert session['exit']==0,session
 (E/'RELEASE_061_SESSION.json').write_bytes(h.canonical(session['json']))
 # Copy only session checkpoint JSONs produced by this invocation.
 saved=[]
 for path in (roots[1]/'cognitive').rglob('*.json'):
  rel=path.relative_to(roots[1]).as_posix()
  if ('sessions/' in rel or 'session_runs/' in rel):saved.append({'path':rel,'sha256':h.sha(path.read_bytes())})
 receipt={'schema':'QRCEL_FINAL_RELEASE_061_VALIDATION_V1','status':'PASS','anchors':A,'large_plan_processes':results,'session':session,'saved_session_files':saved,'scientific_dispatches':0,'model_calls':0,'full_qrcel_complete':False}
 (E/'RELEASE_061_FRESH_VALIDATION.json').write_bytes(h.canonical(receipt))
print('Final frozen release: 100-task large plan, fresh anchored restore and session PASS')
