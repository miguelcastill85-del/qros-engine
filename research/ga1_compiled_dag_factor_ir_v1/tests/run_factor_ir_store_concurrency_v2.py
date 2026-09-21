from __future__ import annotations
import hashlib, json, multiprocessing as mp, tempfile, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_factor_ir import FactorIR
from qros_factor_ir_store import atomic_write, serialize

def mk_ir(seed):
    rng=np.random.default_rng(seed)
    src=np.cumsum(rng.integers(1,100,4000,dtype=np.uint64))
    prims={f'p{i}':rng.random(len(src))<rng.random() for i in range(12)}
    rec={f'r{i}':tuple(rng.choice(list(prims),size=int(rng.integers(0,5)),replace=False)) for i in range(20)}
    return FactorIR.build(src,prims,rec)

def worker(path, seed, action, q):
    try:
        ir=mk_ir(seed)
        meta=atomic_write(path,ir,provenance={'action_key':action})
        q.put(('ok',seed,meta['publication'],meta['sha256']))
    except Exception as e:
        q.put(('err',seed,type(e).__name__,str(e)))

if __name__=='__main__':
    ctx=mp.get_context('spawn')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        f=td/'crash.bin'; ir=mk_ir(1); ak=hashlib.sha256(b'a').hexdigest()
        try: atomic_write(f,ir,provenance={'action_key':ak},crash_before_rename=True)
        except RuntimeError: pass
        assert not f.exists()
        f=td/'same.bin'; q=ctx.Queue()
        ps=[ctx.Process(target=worker,args=(str(f),7,hashlib.sha256(b'same').hexdigest(),q)) for _ in range(8)]
        [p.start() for p in ps]; [p.join() for p in ps]
        rows=[q.get() for _ in ps]
        assert all(r[0]=='ok' for r in rows), rows
        pubs=sum(r[2]=='PUBLISHED' for r in rows); ids=sum(r[2]=='IDEMPOTENT_EXISTING' for r in rows)
        assert pubs==1 and ids==7, rows
        same_hashes={r[3] for r in rows}; assert len(same_hashes)==1
        f=td/'race.bin'; q=ctx.Queue()
        seeds=list(range(20,28))
        ps=[ctx.Process(target=worker,args=(str(f),s,hashlib.sha256(f'a{s}'.encode()).hexdigest(),q)) for s in seeds]
        [p.start() for p in ps]; [p.join() for p in ps]
        rows2=[q.get() for _ in ps]
        oks=[r for r in rows2 if r[0]=='ok']; errs=[r for r in rows2 if r[0]=='err']
        assert len(oks)==1 and oks[0][2]=='PUBLISHED', rows2
        assert len(errs)==7 and all(r[2]=='FileExistsError' and 'IMMUTABLE_ARTIFACT_CONFLICT' in r[3] for r in errs), rows2
        winner_seed=oks[0][1]; winner=mk_ir(winner_seed)
        want=serialize(winner,provenance={'action_key':hashlib.sha256(f'a{winner_seed}'.encode()).hexdigest()})
        assert f.read_bytes()==want
        meta=atomic_write(f,winner,provenance={'action_key':hashlib.sha256(f'a{winner_seed}'.encode()).hexdigest()})
        assert meta['publication']=='IDEMPOTENT_EXISTING'
        try:
            atomic_write(f,mk_ir(999),provenance={'action_key':hashlib.sha256(b'other').hexdigest()})
            raise AssertionError('CONFLICT_NOT_REJECTED')
        except FileExistsError as e:
            assert 'IMMUTABLE_ARTIFACT_CONFLICT' in str(e)
        assert f.read_bytes()==want
        print(json.dumps({'status':'PASS','identical_workers':8,'identical_one_published':pubs==1,'identical_idempotent_existing':ids,'conflicting_workers':8,'conflict_winner_count':len(oks),'conflicts_rejected':len(errs),'crash_before_publish_no_final':True,'sequential_idempotence_pass':True,'sequential_conflict_no_overwrite':True},sort_keys=True))
