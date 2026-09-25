#!/usr/bin/env python3
"""TEST_ONLY: POSIX local group-kill vs nested start_new_session; cleans up both branches."""
import os,signal,subprocess,sys,time,json

def alive(pid):
    try:
        stat=open(f'/proc/{pid}/stat').read();return stat[stat.rfind(') ')+2:].split()[0] != 'Z'
    except FileNotFoundError:return False

def scenario(detached):
    program=('import subprocess,sys,time; '
            'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"], '
            f'start_new_session={detached!r}, stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); '
            'print(p.pid,flush=True); time.sleep(20)')
    outer=subprocess.Popen([sys.executable,'-c',program],stdout=subprocess.PIPE,start_new_session=True,text=True)
    inner=None
    try:
        inner=int(outer.stdout.readline().strip());time.sleep(.12)
        assert alive(outer.pid) and alive(inner)
        os.killpg(outer.pid,signal.SIGKILL)
        outer.wait(timeout=2);time.sleep(.12)
        still_alive=alive(inner)
        return {'nested_start_new_session':detached,'outer_killed':not alive(outer.pid),'nested_survived_outer_killpg':still_alive}
    finally:
        if inner and alive(inner):
            try:os.killpg(inner,signal.SIGKILL) if detached else os.kill(inner,signal.SIGKILL)
            except ProcessLookupError:pass
        try:outer.kill();outer.wait(timeout=2)
        except Exception:pass
        if outer.stdout:outer.stdout.close()

a=scenario(False);b=scenario(True)
assert a['nested_survived_outer_killpg'] is False
assert b['nested_survived_outer_killpg'] is True
print(json.dumps({'scope':'SYNTHETIC_POSIX_PROCESS_GROUP_BEHAVIOR_NOT_QROS_RUNTIME','shared_group':a,'detached_child':b,'tests':'2/2 PASS','children_cleanup':'SIGKILL_ISSUED'},sort_keys=True))
