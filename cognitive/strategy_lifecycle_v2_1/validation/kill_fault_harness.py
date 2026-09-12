from __future__ import annotations
from pathlib import Path
import os, signal, subprocess, sys, tempfile, json


def child(db: str, stage: str, idem: str, expected: int, token: int) -> None:
    from durable_store import DurableLifecycleStore
    import durable_store as ds
    class FatalCrash(BaseException):
        def __new__(cls, *a, **k):
            os.kill(os.getpid(), signal.SIGKILL)
            raise AssertionError('unreachable')
    ds.InjectedCrash = FatalCrash
    s=DurableLifecycleStore(Path(db))
    s.append_transition(
        campaign_id='KILL-C1', genealogy_id='GEN-KILL', command='STEP', actor='QROS',
        owner='worker', fencing_token=token, idempotency_key=idem,
        expected_version=expected, next_state={'phase':stage}, payload={'stage':stage},
        exposed_periods=['HOLDOUT-X'] if stage == 'after_commit' else [], fault_stage=stage,
    )


def run() -> dict:
    from durable_store import DurableLifecycleStore
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/'kill.sqlite'
        s=DurableLifecycleStore(db); token=s.acquire_lease('KILL-C1','worker'); s.close()
        p=subprocess.run([sys.executable,__file__,'--child',str(db),'after_projection_upsert','prekill','0',str(token)])
        if p.returncode >= 0: raise AssertionError(f'expected signal kill, got {p.returncode}')
        s=DurableLifecycleStore(db)
        if s.campaign_version('KILL-C1') != 0: raise AssertionError('precommit kill leaked projection')
        if s.conn.execute('SELECT COUNT(*) FROM events').fetchone()[0] != 0: raise AssertionError('precommit kill leaked event')
        s.validate_all(); s.close()
        s=DurableLifecycleStore(db)
        e=s.append_transition(campaign_id='KILL-C1',genealogy_id='GEN-KILL',command='STEP',actor='QROS',owner='worker',fencing_token=token,idempotency_key='normal1',expected_version=0,next_state={'phase':'v1'},payload={'n':1})
        if e.campaign_version != 1: raise AssertionError('normal commit failed')
        s.close()
        p2=subprocess.run([sys.executable,__file__,'--child',str(db),'after_commit','postkill','1',str(token)])
        if p2.returncode >= 0: raise AssertionError(f'expected signal kill postcommit, got {p2.returncode}')
        s=DurableLifecycleStore(db)
        if s.campaign_version('KILL-C1') != 2: raise AssertionError('postcommit transaction missing')
        count_before=s.conn.execute("SELECT COUNT(*) FROM events WHERE idempotency_key='postkill'").fetchone()[0]
        if count_before != 1: raise AssertionError('postcommit not exactly once before retry')
        e2=s.append_transition(campaign_id='KILL-C1',genealogy_id='GEN-KILL',command='STEP',actor='QROS',owner='worker',fencing_token=token,idempotency_key='postkill',expected_version=1,next_state={'phase':'after_commit'},payload={'stage':'after_commit'},exposed_periods=['HOLDOUT-X'])
        if e2.campaign_version != 2: raise AssertionError('retry did not resolve existing commit')
        count_after=s.conn.execute("SELECT COUNT(*) FROM events WHERE idempotency_key='postkill'").fetchone()[0]
        if count_after != 1: raise AssertionError('retry duplicated event')
        exposed=s.conn.execute("SELECT 1 FROM exposures WHERE genealogy_id='GEN-KILL' AND period='HOLDOUT-X'").fetchone()
        if exposed is None: raise AssertionError('exposure lost after postcommit kill')
        s.validate_all(); root=s.logical_root(); s.close()
        return {'status':'PASS','precommit_sigkill_rollback':'PASS','postcommit_sigkill_exactly_once':'PASS','events':2,'version':2,'logical_root':root}

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        child(sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5]),int(sys.argv[6]))
    else:
        print(json.dumps(run(),sort_keys=True))
