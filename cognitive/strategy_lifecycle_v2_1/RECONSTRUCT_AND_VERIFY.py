from __future__ import annotations
from pathlib import Path
import base64, hashlib, sys, zipfile, tempfile, subprocess, os

ZIP_NAME='QROS_STRATEGY_LIFECYCLE_ENGINE_v2_1_DURABLE_REFERENCE.zip'
ZIP_SHA256='accc29e249145ce98b918efde91fec96c3a1be4c1ea8f4ebad9488afd398d087'
PARTS={
'part000':(7000,'a4fa18431d311c637b924bebf368ccb83a3b34be452ea7284b9c318554e16461'),
'part001':(7000,'d437f360d53127b54d35d7220b53be9f97f85ae1b6ffb65df87d03a425312a93'),
'part002':(7000,'4061f9a7a54b487a304833157a5a35b7b53d6c0a0e2a209188206a861064c150'),
'part003':(7000,'70078c26a277866cdf8be098bd4ce015adecc8a730debd4ce87beeeabd3660a0'),
'part004':(7000,'ec0c109ecce67a33ec38ef4aea1c108d0f62f0c8ec6dde01bfcd3ad27657cd8e'),
'part005':(4232,'71b9c7de3dc22e1b6e0aa5e2fc86247295ef83b8b09d4cfa8d1449cbb2b11d22'),
}
PREFIX='QROS_STRATEGY_LIFECYCLE_ENGINE_v2_1_DURABLE_REFERENCE.zip.b64.'

def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def reconstruct(base:Path)->Path:
    chunks=[]
    for name,(size,sha) in PARTS.items():
        p=base/'package'/(PREFIX+name)
        b=p.read_bytes()
        if len(b)!=size or h(b)!=sha: raise RuntimeError(f'PART_MISMATCH:{name}')
        chunks.append(b)
    raw=base64.b64decode(b''.join(chunks),validate=True)
    if h(raw)!=ZIP_SHA256: raise RuntimeError('ARCHIVE_HASH_MISMATCH')
    out=base/ZIP_NAME; out.write_bytes(raw); return out

def audit(z:Path):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(z) as f:f.extractall(td)
        root=Path(td)/'qsle_v2_1'; env=dict(os.environ); env['PYTHONPATH']=str(root)
        subprocess.run([sys.executable,'-m','pytest','-q'],cwd=root,env=env,check=True)
        subprocess.run([sys.executable,'rise_q_persistence_audit.py'],cwd=root,env=env,check=True)
        subprocess.run([sys.executable,'-m','compileall','-q','.'],cwd=root,env=env,check=True)

if __name__=='__main__':
    base=Path(__file__).resolve().parent
    z=reconstruct(base)
    if '--audit' in sys.argv:audit(z)
    print('QSLE_REFERENCE_ARCHIVE_PASS',ZIP_SHA256)
