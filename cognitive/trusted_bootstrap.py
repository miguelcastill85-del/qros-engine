#!/usr/bin/env python3
"""Host-pinned launcher: python -I -S -B trusted_bootstrap.py ...

Trust this file and the interpreter independently before execution. Project imports
are compiled exclusively from captured, manifest-verified source bytes. This is
not a sandbox against a hostile interpreter, OS administrator or same-UID writer.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import resource
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time

MANIFEST='cognitive/COGNITIVE_MANIFEST.json'
MAX_FILE=4*1024*1024

def require(value,code):
    if not value:raise ValueError(code)

def pairs(items):
    out={}
    for k,v in items:
        require(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
    return out

def read(root,path):
    require(isinstance(path,str) and '\\' not in path and '\0' not in path,'UNSAFE_PATH')
    parts=path.split('/');require(all(x not in ('','.','..') for x in parts),'UNSAFE_PATH')
    handles=[]
    try:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);handles.append(fd)
        for p in parts[:-1]:
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);handles.append(fd)
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd);handles.append(fd)
        info=os.fstat(fd);require(stat.S_ISREG(info.st_mode) and info.st_size<=MAX_FILE,'FILE_BOUNDARY')
        data=b''
        while True:
            chunk=os.read(fd,min(65536,MAX_FILE+1-len(data)))
            if not chunk:return data
            data+=chunk;require(len(data)<=MAX_FILE,'FILE_BOUNDARY')
    finally:
        for fd in reversed(handles):os.close(fd)

def capture(root,anchor):
    raw=read(root,MANIFEST)
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    require(actual==anchor,'RELEASE_ANCHOR_MISMATCH')
    manifest=json.loads(raw,object_pairs_hook=pairs)
    require(manifest.get('schema')=='QRCEL_SOURCE_AND_ENGINEERING_EVIDENCE_MANIFEST_V1' and manifest.get('scientific_authority') is False,'RELEASE_SCHEMA')
    fs=manifest.get('files_sha256');require(isinstance(fs,dict) and 0<len(fs)<=2048,'RELEASE_FILES')
    captured={MANIFEST:raw};total=len(raw)
    for path,digest in fs.items():
        require(path.startswith('cognitive/') and path!=MANIFEST,'RELEASE_SCOPE')
        data=read(root,path);require(hashlib.sha256(data).hexdigest()==digest,'RELEASE_FILE_MISMATCH')
        captured[path]=data;total+=len(data);require(total<=64*1024*1024,'RELEASE_SIZE_LIMIT')
    # Reject executable extras even though the in-memory importer never loads them.
    for directory,dirs,names in os.walk(Path(root)/'cognitive',followlinks=False):
        for name in dirs+names:require(not (Path(directory)/name).is_symlink(),'RELEASE_SYMLINK')
        for name in names:
            rel=(Path(directory)/name).relative_to(root).as_posix()
            require(not name.lower().endswith(('.pyc','.pyo','.so','.pyd','.dll','.dylib','.zip','.pth')),'RELEASE_UNLISTED_CODE')
            require(not name.endswith('.py') or rel in captured,'RELEASE_UNLISTED_CODE')
    return captured

class VerifiedImporter(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,files):
        self.root=Path(root);self.modules={}
        for p,b in files.items():
            if p.endswith('.py'):
                package=p.endswith('/__init__.py')
                name=(p[:-12] if package else p[:-3]).replace('/','.')
                self.modules[name]=(p,b,package)
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='cognitive' or fullname.startswith('cognitive.'):
            namespace=fullname not in self.modules and any(n.startswith(fullname+'.') for n in self.modules)
            require(fullname in self.modules or namespace,'UNVERIFIED_IMPORT:'+fullname)
            return importlib.util.spec_from_loader(fullname,self,is_package=namespace or self.modules[fullname][2])
        return None
    def create_module(self,spec):return None
    def exec_module(self,module):
        if module.__name__ not in self.modules:
            require(any(n.startswith(module.__name__+'.') for n in self.modules),'UNVERIFIED_NAMESPACE')
            module.__path__=[]
            return
        path,data,package=self.modules[module.__name__]
        module.__file__=str(self.root/path)
        if package:module.__path__=[]
        exec(compile(data,module.__file__,'exec'),module.__dict__)

def entry_arguments(arguments, entry):
    # argparse in historical entrypoints accepts abbreviations. Reject reserved
    # identity prefixes here so the lock key and the eventual write target agree.
    for arg in arguments:
        key=arg.split('=')[0]
        if key.startswith('--'):
            require(not any(option.startswith(key) for option in
                            ('--repo-root','--release-blob','--manifest-blob')),
                    'ENTRY_IDENTITY_OVERRIDE')
            if entry=='kernel':
                require(not ('--run-id'.startswith(key) and key!='--run-id'),
                        'KERNEL_RUN_ID_ABBREVIATION')
    if entry!='kernel':return None
    parser=argparse.ArgumentParser(add_help=False,allow_abbrev=False)
    parser.add_argument('--run-id',required=True)
    parsed,_=parser.parse_known_args(arguments)
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',parsed.run_id) is not None,'KERNEL_RUN_ID')
    return parsed.run_id

@contextmanager
def kernel_admission(root, run_id, wait_seconds):
    """Local cooperative admission for this launcher, not distributed fencing.

    Keep the lock inode permanently: unlinking it could split concurrent owners.
    The OS releases flock when the worker closes or dies. No task is retried here.
    """
    require(isinstance(run_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id)
            is not None,'KERNEL_RUN_ID')
    require(type(wait_seconds) in (int,float) and 0<=wait_seconds<=15,'ADMISSION_BUDGET')
    handles=[]
    try:
        directory_flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
        fd=os.open(root,directory_flags);handles.append(fd)
        fd=os.open('cognitive',directory_flags,dir_fd=fd);handles.append(fd)
        try:os.mkdir('admission',mode=0o700,dir_fd=fd)
        except FileExistsError:pass
        fd=os.open('admission',directory_flags,dir_fd=fd);handles.append(fd)
        info=os.fstat(fd)
        require(info.st_uid==os.geteuid() and info.st_mode&0o077==0,'ADMISSION_DIRECTORY_UNSAFE')
        lock=os.open(run_id+'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,
                     0o600,dir_fd=fd);handles.append(lock)
        info=os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and
                info.st_nlink==1 and info.st_mode&0o077==0,'ADMISSION_LOCK_UNSAFE')
        deadline=time.monotonic()+wait_seconds
        while True:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining=deadline-time.monotonic()
                require(remaining>0,'KERNEL_ADMISSION_TIMEOUT')
                time.sleep(min(0.025,remaining))
        yield
    finally:
        for fd in reversed(handles):os.close(fd)

def worker(args):
    resource.setrlimit(resource.RLIMIT_CPU,(args.cpu,args.cpu))
    resource.setrlimit(resource.RLIMIT_AS,(args.memory_mib*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,((8 if args.entry == 'kernel' else 1)*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
    files=capture(args.repo_root,args.release_blob)
    require(not any(k=='cognitive' or k.startswith('cognitive.') for k in sys.modules),'PRELOADED_PROJECT_CODE')
    sys.meta_path.insert(0,VerifiedImporter(args.repo_root,files))
    module=__import__('cognitive.'+args.entry,fromlist=['main'])
    if args.entry=='verify_release':argv=['--repo-root',args.repo_root,'--manifest-blob',args.release_blob]
    else:argv=['--repo-root',args.repo_root,'--release-blob',args.release_blob]
    run_id=entry_arguments(args.arguments,args.entry)
    sys.argv=[module.__file__,*argv,*args.arguments]
    if args.entry=='kernel':
        with kernel_admission(args.repo_root,run_id,args.admission_wait):return module.main()
    return module.main()

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    p.add_argument('--repo-root',required=True);p.add_argument('--release-blob',required=True)
    p.add_argument('--entry',choices=['session','kernel','verify_release'],default='session')
    p.add_argument('--wall',type=int,default=30);p.add_argument('--cpu',type=int,default=20)
    p.add_argument('--memory-mib',type=int,default=512);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--admission-wait',type=float,default=10.0)
    p.add_argument('arguments',nargs=argparse.REMAINDER)
    args=p.parse_args();args.arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'REQUIRE_ISOLATED_NO_SITE_NO_BYTECODE_FLAGS')
    require(1<=args.wall<=300 and 1<=args.cpu<=300 and 64<=args.memory_mib<=2048,'RESOURCE_BUDGET')
    require(0<=args.admission_wait<=15,'ADMISSION_BUDGET')
    if args.worker:return worker(args)
    started=time.monotonic()
    command=[sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),'--worker',*sys.argv[1:]]
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
            env={'PATH':os.defpath,'LANG':'C.UTF-8'},start_new_session=True)
        def cancel(signum,frame):raise InterruptedError('SUPERVISOR_CANCELLED')
        old_signals={sig:signal.signal(sig,cancel) for sig in (signal.SIGTERM,signal.SIGINT)}
        try:
            try:code=child.wait(timeout=args.wall)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait();code=124
            out.seek(0);raw=out.read(1024*1024+1);err.seek(0);errors=err.read(4096)
            if code==0:
                require(len(raw)<=1024*1024,'OUTPUT_LIMIT');sys.stdout.buffer.write(raw)
            else:
                try:
                    failure=json.loads(raw) if len(raw)<=65536 else {}
                    child_error=str(failure.get('error',''))[:256] if isinstance(failure,dict) else ''
                except (ValueError,UnicodeError):child_error=''
                print(json.dumps({'status':'FAIL_CLOSED','child_exit':code,'wall_seconds':time.monotonic()-started,
                    'error':'WALL_BUDGET_EXCEEDED' if code==124 else 'BOUNDED_WORKER_FAILED','detail':errors.decode(errors='replace'),
                    'child_error':child_error,
                    'retryable_local_admission':child_error=='KERNEL_ADMISSION_TIMEOUT',
                    'background_running':False,'scientific_dispatch_authorized':False}))
            return code if 0<=code<=255 else 2
        finally:
            if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
            for sig,handler in old_signals.items():signal.signal(sig,handler)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(error),'scientific_dispatch_authorized':False}));raise SystemExit(2)
