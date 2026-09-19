import os,time,tempfile
from pathlib import Path
import qros_heavy_job_supervisor_v1 as v1
import qros_heavy_job_supervisor_v2 as v2
def test():
    with tempfile.TemporaryDirectory() as td:
        job=Path(td)/'j';job.mkdir();lock=job/'.controller.lock';lock.mkdir()
        assert v2.acquire_controller_lock(job,120) is None
        (lock/'owner.json').write_text('{bad')
        assert v2.acquire_controller_lock(job,120) is None
        old=time.time()-300;os.utime(lock,(old,old));p=v2.acquire_controller_lock(job,120);assert p is not None;v1.release_controller_lock(p)
    with tempfile.TemporaryDirectory() as td:
        job=Path(td)/'j';job.mkdir();lock=job/'.controller.lock';lock.mkdir()
        v1.atomic_write_json(lock/'owner.json',{'pid':os.getpid(),'created_at':v1.utc_now(),'birth':v1.process_birth(os.getpid())})
        old=time.time()-1000;os.utime(lock,(old,old));assert v2.acquire_controller_lock(job,1) is None
    with tempfile.TemporaryDirectory() as td:
        job=Path(td)/'j';job.mkdir();p=v2.acquire_controller_lock(job,120);assert p is not None;v1.release_controller_lock(p)
    return 5
if __name__=='__main__':print('PASS',test())
