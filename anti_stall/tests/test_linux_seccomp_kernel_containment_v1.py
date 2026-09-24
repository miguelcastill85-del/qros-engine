#!/usr/bin/env python3
"""Linux x86_64 non-economic kernel proof for the opt-in, pinned seccomp launcher.

No market data. No security claim for untrusted workers, OS isolation, or Windows.
"""
import errno, hashlib, json, os, pathlib, shutil, signal, subprocess, sys, tempfile, threading, time, unittest

SCRIPT_DIR=pathlib.Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPT_DIR))
from qros_linux_seccomp_single_owner_v1 import KernelContainmentFailure, attestation, launch, sha256_file

SKIP=not(sys.platform=="linux" and os.uname().machine.lower() in ("x86_64","amd64"))
@unittest.skipIf(SKIP,"Linux x86_64 required; not a Windows test")
class LinuxSingleProcessSeccomp(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.launcher="launcher.py"
        shutil.copyfile(SCRIPT_DIR/"qros_linux_seccomp_single_process_launcher_v1.py",self.root/self.launcher)
        self.sha=sha256_file(self.root/self.launcher)
        self.proc=None
    def tearDown(self):
        if self.proc is not None:
            try:os.killpg(self.proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
            for pipe in (self.proc.stdout,self.proc.stderr):
                if pipe and not pipe.closed:pipe.close()
        self.tmp.cleanup()
    def run_code(self,source,timeout=4):
        (self.root/"worker.py").write_text(source)
        self.proc,proof=launch([sys.executable,"worker.py"],self.root,self.launcher,self.sha)
        out,err=self.proc.communicate(timeout=timeout)
        return proof,out.decode(errors="replace"),err.decode(errors="replace"),self.proc.returncode
    def test_parent_verified_kernel_seccomp_and_exec(self):
        proof,out,err,rc=self.run_code("print('WORKER_RAN',flush=True)")
        self.assertEqual(rc,0,(out,err))
        self.assertIn("WORKER_RAN",out)
        self.assertTrue(proof["kernel_seccomp_verified"])
        self.assertEqual(proof["proc_no_new_privs"],1)
        self.assertEqual(proof["proc_seccomp"],2)
    def test_os_fork_is_forbidden_by_kernel(self):
        proof,out,err,rc=self.run_code(
            "import os,errno\n"
            "try:pid=os.fork();raise SystemExit('FORK_ESCAPED '+str(pid))\n"
            "except OSError as e:assert e.errno==errno.EPERM;print('FORK_DENIED',flush=True)\n")
        self.assertEqual(rc,0,(out,err));self.assertIn("FORK_DENIED",out)
    def test_c_libc_clone_process_is_forbidden(self):
        _,out,err,rc=self.run_code(
            "import ctypes,errno,signal\n"
            "lib=ctypes.CDLL(None,use_errno=True)\n"
            "v=lib.syscall(56,signal.SIGCHLD,0,0,0,0)\n"
            "assert v==-1 and ctypes.get_errno()==errno.EPERM,(v,ctypes.get_errno())\n"
            "print('CLONE_PROCESS_DENIED',flush=True)\n")
        self.assertEqual(rc,0,(out,err));self.assertIn("CLONE_PROCESS_DENIED",out)
    def test_clone3_is_forced_to_enosys_and_threads_work(self):
        _,out,err,rc=self.run_code(
            "import ctypes,errno,threading\n"
            "lib=ctypes.CDLL(None,use_errno=True)\n"
            "v=lib.syscall(435,0,0)\n"
            "assert v==-1 and ctypes.get_errno()==errno.ENOSYS,(v,ctypes.get_errno())\n"
            "q=[];t=threading.Thread(target=lambda:q.append(7));t.start();t.join(timeout=2)\n"
            "assert q==[7]\n"
            "print('CLONE3_DENIED_THREADS_WORK',flush=True)\n")
        self.assertEqual(rc,0,(out,err));self.assertIn("CLONE3_DENIED_THREADS_WORK",out)
    def test_setsid_and_setpgid_cannot_detach(self):
        _,out,err,rc=self.run_code(
            "import os,errno\n"
            "for f in (os.setsid,lambda:os.setpgid(0,0)):\n"
            " try:f();raise AssertionError('ESCAPED')\n"
            " except OSError as e:assert e.errno==errno.EPERM,e\n"
            "print('DETACH_DENIED',flush=True)\n")
        self.assertEqual(rc,0,(out,err));self.assertIn("DETACH_DENIED",out)
    def test_python_subprocess_cannot_create_child(self):
        _,out,err,rc=self.run_code(
            "import subprocess,errno,sys\n"
            "try:subprocess.Popen([sys.executable,'-c','print(999)']);raise AssertionError('CHILD_ESCAPED')\n"
            "except OSError as e:assert e.errno==errno.EPERM,e\n"
            "print('SUBPROCESS_DENIED',flush=True)\n")
        self.assertEqual(rc,0,(out,err));self.assertIn("SUBPROCESS_DENIED",out)
    def test_fake_or_modified_launcher_fails_before_launch(self):
        (self.root/self.launcher).write_text("print('malicious')")
        with self.assertRaisesRegex(KernelContainmentFailure,"LAUNCHER_PIN_MISMATCH"):
            launch([sys.executable,"worker.py"],self.root,self.launcher,self.sha)
    def test_symlink_launcher_fails_before_launch(self):
        (self.root/self.launcher).unlink()
        (self.root/"payload.py").write_text("print('not executed')")
        (self.root/self.launcher).symlink_to(self.root/"payload.py")
        with self.assertRaisesRegex(KernelContainmentFailure,"LAUNCHER_PIN_MISMATCH"):
            launch([sys.executable,"worker.py"],self.root,self.launcher,self.sha)
    def test_parent_kills_entire_seccomp_worker_group(self):
        (self.root/"worker.py").write_text("import time;print('SLEEPING',flush=True);time.sleep(30)\n")
        self.proc,proof=launch([sys.executable,"worker.py"],self.root,self.launcher,self.sha)
        self.assertTrue(proof["owns_process_group"])
        self.assertIn(b"SLEEPING",self.proc.stdout.readline())
        os.killpg(self.proc.pid,signal.SIGKILL)
        self.proc.wait(timeout=2)
        with self.assertRaises(ProcessLookupError):os.kill(self.proc.pid,0)

if __name__=="__main__":unittest.main(verbosity=2)
