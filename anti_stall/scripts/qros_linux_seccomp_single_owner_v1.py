#!/usr/bin/env python3
"""Independent /proc kernel attestation and gated seccomp worker launch.

Opt-in Linux x86_64 fixture/research route only. One parent owns the direct
worker process group; the launcher never starts a separate controller.
"""
from __future__ import annotations
import hashlib, os, pathlib, platform, select, signal, subprocess, sys, time

MARKER=b'QROS_SECCOMP_READY_V1'
class KernelContainmentFailure(RuntimeError):pass

def sha256_file(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def attestation(pid):
    if sys.platform!='linux' or platform.machine().lower() not in ('x86_64','amd64'):
        raise KernelContainmentFailure('LINUX_X86_64_REQUIRED')
    try:
        status=pathlib.Path('/proc')/str(pid)/'status'
        fields=dict(line.split(':',1) for line in status.read_text().splitlines() if ':' in line)
        seccomp=fields['Seccomp'].strip()
        no_new_privs=fields['NoNewPrivs'].strip()
        leader=(os.getpgid(pid)==pid)
    except (FileNotFoundError,KeyError,OSError,ValueError) as e:
        raise KernelContainmentFailure('KERNEL_STATUS_UNAVAILABLE:'+str(e)) from e
    if seccomp!='2' or no_new_privs!='1' or not leader:
        raise KernelContainmentFailure('KERNEL_SECCOMP_ATTESTATION_FAILED')
    return {'mode':'LINUX_X86_64_NO_FORK_SECCOMP_V1','kernel_seccomp_verified':True,
            'proc_seccomp':2,'proc_no_new_privs':1,'owns_process_group':True}

def launch(argv,work,launcher_name,launcher_sha256,ready_budget=2):
    root=pathlib.Path(work).resolve()
    launcher=root/launcher_name
    if (not launcher.is_file() or launcher.is_symlink() or
        not launcher.resolve().is_relative_to(root) or
        sha256_file(launcher)!=launcher_sha256):
        raise KernelContainmentFailure('LAUNCHER_PIN_MISMATCH')
    if not isinstance(argv,list) or not argv or not all(isinstance(a,str) and a for a in argv):
        raise KernelContainmentFailure('INVALID_DIRECT_WORKER_ARGV')
    if sys.platform!='linux' or platform.machine().lower() not in ('x86_64','amd64'):
        raise KernelContainmentFailure('LINUX_X86_64_REQUIRED')
    rr,rw=os.pipe();gr,gw=os.pipe()
    p=None
    try:
        env={**os.environ,'QROS_READY_FD':str(rw),'QROS_GATE_FD':str(gr)}
        p=subprocess.Popen([sys.executable,'-I','-S',str(launcher),'--',*argv],
                           cwd=root,env=env,pass_fds=(rw,gr),
                           stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,close_fds=True,
                           start_new_session=True)
        os.close(rw);rw=None
        os.close(gr);gr=None
        if not select.select([rr],[],[],max(0.01,min(float(ready_budget),2)))[0]:
            raise KernelContainmentFailure('LAUNCHER_READY_TIMEOUT')
        got=os.read(rr,len(MARKER)+1)
        if got!=MARKER:
            raise KernelContainmentFailure('LAUNCHER_READY_MARKER_MISMATCH')
        proof=attestation(p.pid)
        os.write(gw,b'G')
        os.close(gw);gw=None
        return p,proof
    except BaseException:
        if p is not None:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill();p.wait(timeout=2)
            for f in (p.stdout,p.stderr):
                if f and not f.closed:f.close()
        raise
    finally:
        for fd in (rr,rw,gr,gw):
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
