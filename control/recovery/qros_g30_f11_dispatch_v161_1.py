"""Equivalent compiled signal loops; transactional F11 scoring remains chunked."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
from numba import njit
import qros_g30_f11_signal_primary_v159 as a
import qros_g30_f11_signal_independent_v159 as b
import qros_g30_f11_transactional_v161 as tx

EXPECTED={
 'qros_g30_f11_signal_primary_v159.py':'807b46d57c7d392af76cac46c913486b63487d980b641133a109d21c78c6728e',
 'qros_g30_f11_signal_independent_v159.py':'9359989e2beb1e9acdb96017156a4af01a4bfc494eab454dbc2778b0f307c535',
 'qros_g30_f10_exec_core_v127.py':'13e23e132d6e87bdda5931e09278ea7c98d55ca735d46c77314c4de0df8bfafc',
 'qros_g30_f11_transactional_v161.py':'755fea0cfacb29f0badd680c40b22afd68bb7fec1e38391b985bc5f1eb3b8fd1',
}

@njit(cache=True)
def first_compiled(mask,r):
    if r not in (1,2,3,5,8,13):raise ValueError('unfrozen refractory value')
    out=np.zeros(len(mask),dtype=np.bool_);idx=np.flatnonzero(mask)
    if not len(idx):return out
    last=-10**18
    for q in idx:
        if q-last>r:out[q]=True;last=int(q)
    return out

@njit(cache=True)
def scan_compiled(mask,r):
    if r not in (1,2,3,5,8,13):raise ValueError('unfrozen refractory value')
    out=np.zeros(len(mask),dtype=np.bool_);blocked_until=-1
    for i in range(len(mask)):
        if mask[i] and i>blocked_until:out[i]=True;blocked_until=i+r
    return out

def enable():
    root=Path(__file__).resolve().parent
    for name,sha in EXPECTED.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('source mismatch '+name)
    pa=a.refractory_first;pb=b.refractory_scan
    ca=first_compiled;cb=scan_compiled
    rng=np.random.default_rng(20260905);count=0;digest=hashlib.sha256()
    for n in (0,1,2,20,131,2049):
        for density in (0.,.01,.2,.8,1.):
            m=rng.random(n)<density
            for r in a.REFRACTORY:
                aa=pa(m,r);bb=pb(m,r);ac=ca(m,r);bc=cb(m,r)
                if not (np.array_equal(aa,bb) and np.array_equal(aa,ac) and np.array_equal(bb,bc)):
                    raise RuntimeError('compiled refractory parity mismatch')
                digest.update(aa.tobytes());count+=1
    a.refractory_first=ca;b.refractory_scan=cb
    return {'status':'PASS_EXACT_PYTHON_VS_COMPILED_PRIMARY_AND_INDEPENDENT','cases':count,'sha256':digest.hexdigest()}

def main():
    proof=enable()
    if len(sys.argv)>1 and sys.argv[1]=='synthetic':
        import runpy
        print(json.dumps(proof,sort_keys=True),flush=True)
        runpy.run_path(str(Path(__file__).with_name('qros_g30_f11_signal_parity_v161.py')),run_name='__main__')
        return
    original_specs=tx.specs
    def progress_specs():
        for i,sp in enumerate(original_specs()):
            if i%128==0:print(json.dumps({'phase':'signal_prepare','identities_completed':i,'total':tx.EXPECTED_RAW}),flush=True)
            yield sp
    tx.specs=progress_specs
    tx.main()

if __name__=='__main__':main()
