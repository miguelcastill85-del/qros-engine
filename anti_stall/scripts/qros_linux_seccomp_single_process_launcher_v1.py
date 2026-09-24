#!/usr/bin/env python3
"""Opt-in, fail-closed Linux x86_64 seccomp launcher for TRUSTED, single-process QROS workers.

Blocks fork/vfork, process-form clone, clone3, setsid and setpgid; allows normal
CLONE_THREAD. Not a filesystem, network, memory or hostile-code sandbox.
The parent verifies /proc/<pid>/status AFTER installation and BEFORE worker exec.
"""
from __future__ import annotations
import ctypes
import errno
import os
import platform
import sys

ARCH=0xC000003E
LD_ABS=0x20; JEQ=0x15; JGE=0x35; RET=0x06; AND=0x54
ALLOW=0x7FFF0000
DENY=0x00050000|errno.EPERM
ENOSYS=0x00050000|errno.ENOSYS
KILL=0x80000000
CLONE_THREAD=0x00010000

class Filter(ctypes.Structure):
    _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),
              ('jf',ctypes.c_ubyte),('k',ctypes.c_uint32)]
class Prog(ctypes.Structure):
    _fields_=[('len',ctypes.c_ushort),('filter',ctypes.POINTER(Filter))]

def stmt(code,k):return Filter(code,0,0,k)
def jump(code,k,jt,jf):return Filter(code,jt,jf,k)

def install():
    if sys.platform!='linux' or platform.machine().lower() not in ('x86_64','amd64') or ctypes.sizeof(ctypes.c_void_p)!=8:
        raise RuntimeError('LINUX_X86_64_REQUIRED')
    filt=[stmt(LD_ABS,4),jump(JEQ,ARCH,1,0),stmt(RET,KILL),
          stmt(LD_ABS,0),jump(JGE,0x40000000,0,1),stmt(RET,DENY)]
    # Block process creation and moving an existing worker to a different group.
    for syscall in (57,58,112,109,272,308):  # fork,vfork,setsid,setpgid,unshare,setns
        filt.extend((jump(JEQ,syscall,0,1),stmt(RET,DENY)))
    # clone3 flags are behind a user-space pointer: return ENOSYS so glibc
    # retries clone(), whose flags we can inspect. EPERM would break pthread.
    filt.extend((jump(JEQ,435,0,1),stmt(RET,ENOSYS)))
    filt.extend((jump(JEQ,56,0,5),stmt(LD_ABS,16),stmt(AND,CLONE_THREAD),
                 jump(JEQ,CLONE_THREAD,1,0),stmt(RET,DENY),
                 stmt(RET,ALLOW),stmt(RET,ALLOW)))
    arr=(Filter*len(filt))(*filt)
    prog=Prog(len(filt),arr)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(38,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'PR_SET_NO_NEW_PRIVS')
    if libc.prctl(22,2,ctypes.byref(prog))!=0:raise OSError(ctypes.get_errno(),'PR_SET_SECCOMP_FILTER')

def main():
    if len(sys.argv)<3 or sys.argv[1]!='--':
        raise SystemExit('USAGE: launcher -- EXECUTABLE [ARGS...]')
    ready=int(os.environ.pop('QROS_READY_FD'))
    gate=int(os.environ.pop('QROS_GATE_FD'))
    install()
    os.write(ready,b'QROS_SECCOMP_READY_V1')
    os.close(ready)
    if os.read(gate,1)!=b'G':
        raise SystemExit('PARENT_DID_NOT_VERIFY_KERNEL_SECCOMP')
    os.close(gate)
    os.execvp(sys.argv[2],sys.argv[2:])

if __name__=='__main__':main()
