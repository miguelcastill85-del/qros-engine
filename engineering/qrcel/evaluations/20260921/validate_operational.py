#!/usr/bin/env python3
"""Pinned QRCEL 0.6 operational evaluation, synthetic, offline, bounded children.
This harness adds no release code. Fault hooks only run in disposable workers.
"""
import argparse, errno, hashlib, json, os, pathlib, resource, shutil, signal, sqlite3, subprocess, sys, tempfile, time, types
P=pathlib.Path
RELEASE='9cb67fe7e5051491d88b2c0e3197fce5e878feb6'
BLOB='e6451ecc267cac23898d4494567432db6bcae031'
LAUNCHER='5635677b6945e503fba52352799e33ec773fc7fdc88c399e2a0ed2d4fdd5e47a'
AUTH='5afce6279994b8625bd79fb2d5d13924e3c561e7'
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def load(source):
    path=source/'cognitive/trusted_bootstrap.py';raw=path.read_bytes()
    assert sha(raw)==LAUNCHER
    mod=types.ModuleType('pinned_bootstrap');mod.__file__=str(path)
    exec(compile(raw,str(path),'exec'),mod.__dict__)
    files=mod.capture(str(source),BLOB)
    sys.meta_path.insert(0,mod.VerifiedImporter(source,files))
    from cognitive import kernel, runtime
    return kernel,runtime

def make_plan(n=24,large=False):
    tasks=[]
    for i in range(n):
        parents=[] if large or i==0 else [f'T{i-1:03}']
        inputs={'numbers':['9'*64]*128 if large else [str(2*i+1)],'include_parent_sums':bool(parents)}
        tasks.append({'task_id':f'T{i:03}','parent_ids':parents,'objective':'Synthetic operational boundary only',
                      'operation':'EXACT_SUM','inputs':inputs,'inputs_sha256':sha(canonical(inputs)),'risk':'NORMAL'})
    plan={'schema':'QRCEL_LOCAL_TASK_PLAN_V1','scope':'NON_SCIENTIFIC_LOCAL','tasks':tasks}
    goal={'schema':'QRCEL_EXPLICIT_GOAL_CONTRACT_V1','scope':'EXPLICIT_LOCAL_REQUIREMENTS_ONLY','goal_id':'OPERATIONAL-VALIDATION',
          'description':'Synthetic finite exact arithmetic requirements',
          'requirements':[{'id':'R'+t['task_id'],'operation':t['operation'],'inputs_sha256':t['inputs_sha256'],
                           'parent_ids':['R'+p for p in t['parent_ids']],'minimum_risk':t['risk']} for t in tasks]}
    mapping={'R'+t['task_id']:t['task_id'] for t in tasks}
    return plan,goal,mapping

def prepare(root,source,n=24,large=False,full=False):
    root.mkdir(parents=True)
    (root/'cognitive').mkdir()
    if full:
        m=json.loads((source/'cognitive/COGNITIVE_MANIFEST.json').read_bytes())
        for p in ['cognitive/COGNITIVE_MANIFEST.json',*m['files_sha256']]:
            dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((source/p).read_bytes())
    shutil.copytree(source/'cognitive/tests/fixtures/v191',root,dirs_exist_ok=True)
    for name,data in zip(['plan.json','goal.json','mapping.json'],make_plan(n,large)):(root/name).write_bytes(canonical(data))

def open_kernel(root,k,v):
    p,g,m=[json.loads((root/name).read_bytes()) for name in ['plan.json','goal.json','mapping.json']]
    anchor=json.loads((root/'anchor.json').read_bytes()) if (root/'anchor.json').exists() else None
    return k.Kernel(root,p,sha(canonical(p)),AUTH,'eval',expected_resume_anchor=anchor,goal_contract=g,goal_sha256=sha(canonical(g)),goal_mapping=m)

def worker(a):
    resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2)
    # Diagnostic worker supports documented 4 MiB checkpoints; production limit tested separately.
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,)*2)
    k,v=load(a.source);obj=None
    try:
        obj=open_kernel(a.root,k,v)
        if a.mode=='inspect':
            rows,ledger=obj.integrity();anchor=obj.resume_anchor();(a.root/'anchor.json').write_bytes(canonical(anchor))
            print(json.dumps({'completed':len(rows),'events':len(ledger),'rows':rows,'anchor':anchor}));return 0
        if a.mode.startswith('commit_'):
            k.os._exit=lambda unused:os.kill(os.getpid(),signal.SIGKILL)
            result=obj.run((a.mode.split('_')[1],a.task))
        elif a.mode.startswith('checkpoint_'):
            stage=a.mode.split('_',1)[1]
            real_fsync=k.os.fsync;real_replace=k.os.replace;calls=[0]
            def fsync(fd):
                calls[0]+=1
                if calls[0]==1 and stage=='before_fsync':os.kill(os.getpid(),signal.SIGKILL)
                if calls[0]==1 and stage in ('ENOSPC','EIO'):raise OSError(getattr(errno,stage),stage)
                result=real_fsync(fd)
                if calls[0]==1 and stage=='after_fsync':os.kill(os.getpid(),signal.SIGKILL)
                return result
            def replace(*args,**kw):
                if stage=='before_rename':os.kill(os.getpid(),signal.SIGKILL)
                result=real_replace(*args,**kw)
                if stage=='after_rename':os.kill(os.getpid(),signal.SIGKILL)
                return result
            k.os.fsync=fsync;k.os.replace=replace;result=obj.run()
        else:result=obj.run()
        print(json.dumps(result));return 0
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e),'type':type(e).__name__}));return 2
    finally:
        if obj:obj.close()

def command(a,root,mode='run',task='T011'):
    return [sys.executable,'-I','-S','-B',str(P(__file__).resolve()),'--worker','--source',str(a.source),'--root',str(root),'--mode',mode,'--task',task]

def run_command(cmd,timeout=30):
    start=time.monotonic()
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       env={'PATH':os.defpath,'LANG':'C.UTF-8'},start_new_session=True)
    try:out,err=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate();return {'exit':124,'seconds':time.monotonic()-start,'stdout':out.decode(errors='replace'),'stderr':err.decode(errors='replace')}
    result={'exit':p.returncode,'seconds':time.monotonic()-start,'stdout':out.decode(errors='replace'),'stderr':err.decode(errors='replace')}
    try:result['json']=json.loads(out)
    except (ValueError,UnicodeError):pass
    return result

def evaluate(a):
    load(a.source);a.out.mkdir(parents=True,exist_ok=True)
    protocol={'schema':'QRCEL_OPERATIONAL_EVALUATION_V1','release_commit':RELEASE,'manifest_blob':BLOB,
              'scope':'SYNTHETIC_DEVELOPMENT_EXPOSED_NOT_MODEL_OR_BACKTEST_EVALUATION',
              'cases':[f'commit_{point}_{i}' for point in ('BEFORE','AFTER') for i in (11,23)]+[
                  'checkpoint_before_fsync','checkpoint_after_fsync','checkpoint_before_rename','checkpoint_after_rename','checkpoint_ENOSPC','checkpoint_EIO',
                  'four_writer_100_tasks','lock_timeout_and_recovery','accepted_large_plan_production_limits'],
              'oracle':'sum first n odd integers = n^2; large independent sums = 128*(10^64-1)',
              'criteria':['committed prefix preserved','exact outputs','no duplicate committed START/COMPLETE','all explicit requirements preserved',
                          'bounded return','production launcher completes accepted plan below kernel checkpoint limit'],
              'worker_wall_seconds':30,'worker_cpu_seconds':20,'worker_memory_mib':512,'diagnostic_file_mib':8,
              'production_limits':'unmodified pinned launcher','model_calls':0,'scientific_dispatches':0,'sealed':False}
    (a.out/'PROTOCOL.json').write_bytes(canonical(protocol))
    results=[]
    def record(case,data,ok):
        row={'case':case,'status':'PASS' if ok else 'FAIL','evidence':data};results.append(row)
        (a.out/'RESULTS.json.partial').write_bytes(canonical({'protocol_sha256':sha(canonical(protocol)),'results':results}))
        os.replace(a.out/'RESULTS.json.partial',a.out/'RESULTS.json')
        print(case,row['status'],flush=True)
    def recovered(root,expected_new,n=24):
        r=run_command(command(a,root));j=r.get('json',{})
        cp=root/'cognitive/runs/eval/checkpoint.json'
        obj=json.loads(cp.read_bytes()) if cp.exists() else {}
        rows=obj.get('completed',{});ledger=obj.get('ledger',[])
        sums=all(row['output']=={'fraction':str((int(t[1:])+1)**2)} for t,row in rows.items())
        ok=r['exit']==0 and j.get('newly_completed')==expected_new and len(rows)==n and len(ledger)==2*n and sums and j.get('goal_completion',{}).get('status')=='EXPLICIT_REQUIREMENTS_SATISFIED' and j.get('history_authentication')=='EXTERNAL_PREFIX_VERIFIED'
        r['oracle_exact']=sums;r['ledger_events']=len(ledger);return r,ok
    with tempfile.TemporaryDirectory(prefix='qrcel-op-eval-') as temp:
        base=P(temp)
        for point in ('BEFORE','AFTER'):
            for i in (11,23):
                case=f'commit_{point}_{i}';root=base/case;prepare(root,a.source)
                crash=run_command(command(a,root,'commit_'+point,f'T{i:03}'))
                inspect=run_command(command(a,root,'inspect'));count=i+(point=='AFTER')
                resumed,ok=recovered(root,24-count)
                record(case,{'crash':crash,'inspect':inspect,'resumed':resumed},ok and crash['exit']==-9 and inspect.get('json',{}).get('completed')==count)
        for stage in ('before_fsync','after_fsync','before_rename','after_rename','ENOSPC','EIO'):
            case='checkpoint_'+stage;root=base/case;prepare(root,a.source)
            crash=run_command(command(a,root,case));inspect=run_command(command(a,root,'inspect'));resumed,ok=recovered(root,0)
            record(case,{'fault':crash,'inspect':inspect,'resumed':resumed},ok and crash['exit']==(2 if stage in ('ENOSPC','EIO') else -9))
        root=base/'concurrent';prepare(root,a.source,n=100);children=[];started=time.monotonic()
        try:
            for _ in range(4):children.append(subprocess.Popen(command(a,root),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':os.defpath,'LANG':'C.UTF-8'},start_new_session=True))
            receipts=[]
            for p in children:
                out,err=p.communicate(timeout=max(.1,30-(time.monotonic()-started)))
                receipts.append({'exit':p.returncode,'json':json.loads(out),'stderr':err.decode(errors='replace')})
        finally:
            for p in children:
                if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        inspect=run_command(command(a,root,'inspect'));resumed,ok=recovered(root,0,100)
        record('four_writer_100_tasks',{'writers':receipts,'inspect':inspect,'resumed':resumed,'seconds':time.monotonic()-started},ok and all(x['exit']==0 for x in receipts) and sum(x['json'].get('newly_completed',0) for x in receipts)==100)
        root=base/'locked';prepare(root,a.source);first=run_command(command(a,root));inspect=run_command(command(a,root,'inspect'))
        db=sqlite3.connect(root/'cognitive/runs/eval/state.sqlite',isolation_level=None);db.execute('BEGIN IMMEDIATE')
        try:blocked=run_command(command(a,root),timeout=6)
        finally:db.rollback();db.close()
        resumed,ok=recovered(root,0)
        record('lock_timeout_and_recovery',{'blocked':blocked,'resumed':resumed},ok and blocked['exit']==2 and 'locked' in blocked.get('json',{}).get('error','') and blocked['seconds']<6)
        root=base/'large';prepare(root,a.source,n=100,large=True,full=True)
        p,g,_=make_plan(100,True)
        cmd=[sys.executable,'-I','-S','-B',str(root/'cognitive/trusted_bootstrap.py'),'--repo-root',str(root),'--release-blob',BLOB,'--entry','kernel','--',
             '--plan',str(root/'plan.json'),'--plan-sha256',sha(canonical(p)),'--authority-blob',AUTH,'--run-id','eval',
             '--goal-contract',str(root/'goal.json'),'--goal-sha256',sha(canonical(g)),'--goal-mapping',str(root/'mapping.json')]
        production=run_command(cmd,timeout=35)
        # Complete with diagnostic cap only to isolate storage cap from input validity.
        diagnostic=run_command(command(a,root));cp=root/'cognitive/runs/eval/checkpoint.json'
        val=json.loads(cp.read_bytes()) if cp.exists() else {};expected=str(128*(10**64-1))
        exact=len(val.get('completed',{}))==100 and all(x['output']=={'fraction':expected} for x in val.get('completed',{}).values())
        record('accepted_large_plan_production_limits',{'production':production,'diagnostic':diagnostic,'plan_bytes':len(canonical(p)),
            'checkpoint_bytes':cp.stat().st_size if cp.exists() else None,'diagnostic_exact_oracle':exact},production['exit']==0 and exact)
    print(json.dumps({'cases':len(results),'pass':sum(x['status']=='PASS' for x in results),'fail':sum(x['status']=='FAIL' for x in results)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=P,required=True);parser.add_argument('--root',type=P);parser.add_argument('--out',type=P);parser.add_argument('--worker',action='store_true');parser.add_argument('--mode',default='run');parser.add_argument('--task',default='T011');args=parser.parse_args();args.source=args.source.resolve()
    if args.worker:raise SystemExit(worker(args))
    evaluate(args)
