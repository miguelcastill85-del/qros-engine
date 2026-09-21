import hashlib,json,multiprocessing as mp,os,tempfile,time,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_factor_ir import FactorIR
from qros_factor_ir_store import atomic_write,serialize,cleanup_stale_staging
def mk_ir(seed):
    rng=np.random.default_rng(seed);src=np.cumsum(rng.integers(1,100,1000,dtype=np.uint64));prims={f'p{i}':rng.random(len(src))<rng.random() for i in range(8)};rec={f'r{i}':tuple(rng.choice(list(prims),size=int(rng.integers(0,4)),replace=False)) for i in range(10)};return FactorIR.build(src,prims,rec)
def hard_after(path,data):
    final=Path(path);fd,tmp=tempfile.mkstemp(prefix=final.name+'.staging.',dir=final.parent)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.link(tmp,final);os._exit(17)
def hard_before(path,data):
    final=Path(path);fd,tmp=tempfile.mkstemp(prefix=final.name+'.staging.',dir=final.parent)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os._exit(19)
if __name__=='__main__':
    ctx=mp.get_context('fork')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);ir=mk_ir(42);ak=hashlib.sha256(b'42').hexdigest();prov={'action_key':ak};data=serialize(ir,provenance=prov)
        final=td/'after.bin';p=ctx.Process(target=hard_after,args=(str(final),data));p.start();p.join(5);assert p.exitcode==17
        stag=list(td.glob('after.bin.staging.*'));assert len(stag)==1 and final.read_bytes()==data and os.path.samefile(stag[0],final)
        meta=atomic_write(final,ir,provenance=prov);assert meta['publication']=='IDEMPOTENT_EXISTING' and meta['linked_staging_cleaned']>=1 and not list(td.glob('after.bin.staging.*'))
        final2=td/'before.bin';p=ctx.Process(target=hard_before,args=(str(final2),data));p.start();p.join(5);assert p.exitcode==19 and not final2.exists()
        orphan=list(td.glob('before.bin.staging.*'));assert len(orphan)==1 and orphan[0].read_bytes()==data
        assert atomic_write(final2,ir,provenance=prov)['publication']=='PUBLISHED'
        conflict=td/'before.bin.staging.conflict';conflict.write_bytes(b'not-the-final');old=time.time()-7200
        os.utime(orphan[0],(old,old));os.utime(conflict,(old,old))
        gc=cleanup_stale_staging(final2,min_age_seconds=3600);assert gc['removed_identical_old']==1 and gc['preserved_conflicts']==1 and not orphan[0].exists() and conflict.exists()
        recent=td/'before.bin.staging.recent';recent.write_bytes(data);gc2=cleanup_stale_staging(final2,min_age_seconds=3600);assert recent.exists() and gc2['preserved_recent']>=1
        print(json.dumps({'status':'PASS','hard_crash_after_link_final_valid':True,'retry_idempotent':True,'same_inode_orphan_cleaned':True,'hard_crash_before_link_no_final':True,'retry_after_prelink_crash_published':True,'old_identical_orphan_gc':True,'conflicting_orphan_preserved':True,'recent_orphan_preserved':True},sort_keys=True))
