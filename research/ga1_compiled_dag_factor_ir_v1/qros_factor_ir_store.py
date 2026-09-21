from __future__ import annotations
import hashlib, json, os, struct, tempfile, time
from pathlib import Path
from typing import Any
import numpy as np
from qros_factor_ir import FactorIR, canonical_bytes
MAGIC=b'QROS_FACTOR_IR_STORE_V1\n';LEN=struct.Struct('>Q');SCHEMA='QROS_FACTOR_IR_STORE_1.2'
def _sha(b): return hashlib.sha256(b).hexdigest()
def _validate_hex64(v,label):
    if not isinstance(v,str) or len(v)!=64: raise ValueError(f'{label}_INVALID')
    try:int(v,16)
    except Exception as e: raise ValueError(f'{label}_INVALID') from e
def _bitmap_len(n): return (n+7)//8
def _validate_padding(raw,n):
    if len(raw)!=_bitmap_len(n): raise ValueError('BITMAP_LENGTH_INVALID')
    if n and n%8:
        if raw[-1] & ((~((1<<(n%8))-1))&0xff): raise ValueError('NONCANONICAL_BITMAP_PADDING')
def build_header(ir,*,provenance):
    if not isinstance(provenance,dict): raise ValueError('PROVENANCE_REQUIRED')
    _validate_hex64(provenance.get('action_key'),'ACTION_KEY')
    source=ir.source_idx.astype('<u8',copy=False).tobytes();physical=[]
    for digest,raw in sorted(ir.physical_bitmaps.items()):
        _validate_hex64(digest,'PHYSICAL_DIGEST')
        if _sha(raw)!=digest: raise ValueError('PHYSICAL_DIGEST_MISMATCH')
        _validate_padding(raw,len(ir.source_idx));physical.append({'sha256':digest,'bytes':len(raw)})
    return {'schema':SCHEMA,'source_count':int(len(ir.source_idx)),'source_bytes':len(source),'source_sha256':_sha(source),'semantic_to_physical':dict(sorted(ir.semantic_to_physical.items())),'physical_bitmaps':physical,'recipes':{k:list(v) for k,v in sorted(ir.recipes.items())},'provenance':provenance}
def serialize(ir,*,provenance):
    h=build_header(ir,provenance=provenance);hb=canonical_bytes(h);source=ir.source_idx.astype('<u8',copy=False).tobytes();chunks=[MAGIC,LEN.pack(len(hb)),hb,source]
    for row in h['physical_bitmaps']: chunks.append(ir.physical_bitmaps[row['sha256']])
    return b''.join(chunks)
def _fsync_dir(path):
    dfd=os.open(path,os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)
def _staging_paths(final): return list(final.parent.glob(final.name+'.staging.*'))
def _cleanup_same_inode_staging(final):
    if not final.exists(): return 0
    removed=0
    for p in _staging_paths(final):
        try:
            if os.path.samefile(p,final): p.unlink();removed+=1
        except FileNotFoundError: pass
    if removed: _fsync_dir(final.parent)
    return removed
def cleanup_stale_staging(path,*,min_age_seconds=3600.0):
    final=Path(path)
    if not final.exists(): return {'removed_same_inode':0,'removed_identical_old':0,'preserved_conflicts':0,'preserved_recent':len(_staging_paths(final))}
    removed_same=_cleanup_same_inode_staging(final); final_bytes=final.read_bytes(); now=time.time();ri=co=re=0
    for p in _staging_paths(final):
        try: age=max(0.0,now-p.stat().st_mtime)
        except FileNotFoundError: continue
        if age<min_age_seconds: re+=1;continue
        try: raw=p.read_bytes()
        except FileNotFoundError: continue
        if raw==final_bytes:
            try:p.unlink();ri+=1
            except FileNotFoundError: pass
        else: co+=1
    if ri:_fsync_dir(final.parent)
    return {'removed_same_inode':removed_same,'removed_identical_old':ri,'preserved_conflicts':co,'preserved_recent':re}
def immutable_publish_bytes(path,data,*,crash_before_publish=False):
    final=Path(path);final.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp_name=tempfile.mkstemp(prefix=final.name+'.staging.',dir=final.parent);tmp=Path(tmp_name)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
        if crash_before_publish: raise RuntimeError('INJECTED_CRASH_BEFORE_PUBLISH')
        try: os.link(tmp,final)
        except FileExistsError:
            if final.read_bytes()!=data: raise FileExistsError('IMMUTABLE_ARTIFACT_CONFLICT')
            _fsync_dir(final.parent);cleaned=_cleanup_same_inode_staging(final)
            return {'path':final.name,'bytes':len(data),'sha256':_sha(data),'publication':'IDEMPOTENT_EXISTING','linked_staging_cleaned':cleaned}
        _fsync_dir(final.parent)
        return {'path':final.name,'bytes':len(data),'sha256':_sha(data),'publication':'PUBLISHED','linked_staging_cleaned':0}
    finally:
        try: tmp.unlink()
        except FileNotFoundError: pass
def atomic_write(path,ir,*,provenance,crash_before_rename=False):
    out=immutable_publish_bytes(path,serialize(ir,provenance=provenance),crash_before_publish=crash_before_rename);out['action_key']=provenance['action_key'];return out
