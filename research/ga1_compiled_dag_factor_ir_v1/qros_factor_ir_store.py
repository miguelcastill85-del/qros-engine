from __future__ import annotations
import hashlib, json, os, struct, tempfile
from pathlib import Path
from typing import Any
import numpy as np
from qros_factor_ir import FactorIR, canonical_bytes

MAGIC=b'QROS_FACTOR_IR_STORE_V1\n'
LEN=struct.Struct('>Q')
SCHEMA='QROS_FACTOR_IR_STORE_1.1'

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _validate_hex64(v: str, label: str) -> None:
    if not isinstance(v,str) or len(v)!=64:
        raise ValueError(f'{label}_INVALID')
    try:int(v,16)
    except Exception as e:raise ValueError(f'{label}_INVALID') from e

def _bitmap_len(n: int) -> int:
    return (n+7)//8

def _validate_padding(raw: bytes, n: int) -> None:
    if len(raw)!=_bitmap_len(n):raise ValueError('BITMAP_LENGTH_INVALID')
    if n and n%8:
        used=n%8
        mask=(~((1<<used)-1))&0xff
        if raw[-1] & mask:raise ValueError('NONCANONICAL_BITMAP_PADDING')

def build_header(ir: FactorIR, *, provenance: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(provenance,dict):raise ValueError('PROVENANCE_REQUIRED')
    action_key=provenance.get('action_key')
    _validate_hex64(action_key,'ACTION_KEY')
    source=ir.source_idx.astype('<u8',copy=False).tobytes()
    physical=[]
    for digest,raw in sorted(ir.physical_bitmaps.items()):
        _validate_hex64(digest,'PHYSICAL_DIGEST')
        if _sha(raw)!=digest:raise ValueError('PHYSICAL_DIGEST_MISMATCH')
        _validate_padding(raw,len(ir.source_idx))
        physical.append({'sha256':digest,'bytes':len(raw)})
    for key,digest in ir.semantic_to_physical.items():
        if digest not in ir.physical_bitmaps:raise ValueError('SEMANTIC_REFERENCES_UNKNOWN_PHYSICAL')
    for rid,keys in ir.recipes.items():
        if any(k not in ir.semantic_to_physical for k in keys):raise ValueError('RECIPE_REFERENCES_UNKNOWN_SEMANTIC')
    return {
      'schema':SCHEMA,
      'source_count':int(len(ir.source_idx)),
      'source_bytes':len(source),
      'source_sha256':_sha(source),
      'semantic_to_physical':dict(sorted(ir.semantic_to_physical.items())),
      'physical_bitmaps':physical,
      'recipes':{k:list(v) for k,v in sorted(ir.recipes.items())},
      'provenance':provenance,
    }

def serialize(ir: FactorIR, *, provenance: dict[str, Any]) -> bytes:
    h=build_header(ir,provenance=provenance);hb=canonical_bytes(h)
    source=ir.source_idx.astype('<u8',copy=False).tobytes()
    chunks=[MAGIC,LEN.pack(len(hb)),hb,source]
    for row in h['physical_bitmaps']:
        chunks.append(ir.physical_bitmaps[row['sha256']])
    return b''.join(chunks)

def _fsync_dir(path: Path) -> None:
    dfd=os.open(path,os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)

def immutable_publish_bytes(path: str|Path, data: bytes, *, crash_before_publish: bool=False) -> dict[str,Any]:
    final=Path(path); final.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp_name=tempfile.mkstemp(prefix=final.name+'.staging.',dir=final.parent); tmp=Path(tmp_name)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if crash_before_publish:
            raise RuntimeError('INJECTED_CRASH_BEFORE_PUBLISH')
        try:
            os.link(tmp,final)
        except FileExistsError:
            existing=final.read_bytes()
            if existing!=data:
                raise FileExistsError('IMMUTABLE_ARTIFACT_CONFLICT')
            _fsync_dir(final.parent)
            return {'path':final.name,'bytes':len(data),'sha256':_sha(data),'publication':'IDEMPOTENT_EXISTING'}
        _fsync_dir(final.parent)
        return {'path':final.name,'bytes':len(data),'sha256':_sha(data),'publication':'PUBLISHED'}
    finally:
        try: tmp.unlink()
        except FileNotFoundError: pass

def atomic_write(path: str|Path, ir: FactorIR, *, provenance: dict[str,Any], crash_before_rename: bool=False) -> dict[str,Any]:
    data=serialize(ir,provenance=provenance)
    out=immutable_publish_bytes(path,data,crash_before_publish=crash_before_rename)
    out['action_key']=provenance['action_key']
    return out
