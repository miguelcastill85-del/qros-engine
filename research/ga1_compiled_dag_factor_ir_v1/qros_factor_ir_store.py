from __future__ import annotations
import hashlib, json, os, struct, tempfile
from pathlib import Path
from typing import Any
import numpy as np
from qros_factor_ir import FactorIR, canonical_bytes

MAGIC=b'QROS_FACTOR_IR_STORE_V1\n'
LEN=struct.Struct('>Q')
SCHEMA='QROS_FACTOR_IR_STORE_1.0'


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


def deserialize(data: bytes, *, expected_action_key: str|None=None) -> tuple[FactorIR,dict[str,Any]]:
    if not isinstance(data,(bytes,bytearray,memoryview)):raise ValueError('STORE_BYTES_REQUIRED')
    data=bytes(data);pos=0
    if not data.startswith(MAGIC):raise ValueError('STORE_MAGIC_MISMATCH')
    pos=len(MAGIC)
    if len(data)<pos+LEN.size:raise ValueError('STORE_TRUNCATED_HEADER_LENGTH')
    (hlen,)=LEN.unpack_from(data,pos);pos+=LEN.size
    if hlen<=0 or hlen>64*1024*1024:raise ValueError('HEADER_LENGTH_INVALID')
    if len(data)<pos+hlen:raise ValueError('STORE_TRUNCATED_HEADER')
    hb=data[pos:pos+hlen];pos+=hlen
    try:h=json.loads(hb.decode('utf-8'))
    except Exception as e:raise ValueError('HEADER_JSON_INVALID') from e
    if canonical_bytes(h)!=hb:raise ValueError('HEADER_NOT_CANONICAL')
    if h.get('schema')!=SCHEMA:raise ValueError('STORE_SCHEMA_MISMATCH')
    n=h.get('source_count');sb=h.get('source_bytes')
    if not isinstance(n,int) or isinstance(n,bool) or n<0:raise ValueError('SOURCE_COUNT_INVALID')
    if sb!=n*8:raise ValueError('SOURCE_BYTES_INVALID')
    if len(data)<pos+sb:raise ValueError('STORE_TRUNCATED_SOURCE')
    source_raw=data[pos:pos+sb];pos+=sb
    if _sha(source_raw)!=h.get('source_sha256'):raise ValueError('SOURCE_SHA_MISMATCH')
    source=np.frombuffer(source_raw,dtype='<u8').copy()
    if len(source)>1 and np.any(source[1:]<=source[:-1]):raise ValueError('SOURCE_NOT_STRICTLY_INCREASING')
    phys={};rows=h.get('physical_bitmaps')
    if not isinstance(rows,list):raise ValueError('PHYSICAL_LIST_INVALID')
    last=None
    for row in rows:
        if not isinstance(row,dict):raise ValueError('PHYSICAL_ROW_INVALID')
        digest=row.get('sha256');size=row.get('bytes');_validate_hex64(digest,'PHYSICAL_DIGEST')
        if last is not None and digest<=last:raise ValueError('PHYSICAL_ORDER_INVALID')
        last=digest
        if not isinstance(size,int) or isinstance(size,bool) or size<0:raise ValueError('PHYSICAL_SIZE_INVALID')
        if size!=_bitmap_len(n):raise ValueError('PHYSICAL_SIZE_NONCANONICAL')
        if len(data)<pos+size:raise ValueError('STORE_TRUNCATED_BITMAP')
        raw=data[pos:pos+size];pos+=size
        if _sha(raw)!=digest:raise ValueError('PHYSICAL_SHA_MISMATCH')
        _validate_padding(raw,n);phys[digest]=raw
    if pos!=len(data):raise ValueError('STORE_TRAILING_BYTES')
    sem=h.get('semantic_to_physical');recipes=h.get('recipes');prov=h.get('provenance')
    if not isinstance(sem,dict) or not isinstance(recipes,dict) or not isinstance(prov,dict):raise ValueError('HEADER_SECTION_INVALID')
    if list(sem)!=sorted(sem) or list(recipes)!=sorted(recipes):raise ValueError('HEADER_MAP_ORDER_INVALID')
    for k,d in sem.items():
        if not isinstance(k,str) or not k or d not in phys:raise ValueError('SEMANTIC_MAPPING_INVALID')
    rec={}
    for rid,keys in recipes.items():
        if not isinstance(rid,str) or not rid or not isinstance(keys,list) or any(k not in sem for k in keys):raise ValueError('RECIPE_INVALID')
        rec[rid]=tuple(keys)
    action_key=prov.get('action_key');_validate_hex64(action_key,'ACTION_KEY')
    if expected_action_key is not None and action_key!=expected_action_key:raise ValueError('ACTION_KEY_MISMATCH')
    ir=FactorIR(source_idx=source,semantic_to_physical=dict(sem),physical_bitmaps=phys,recipes=rec)
    rebuilt=build_header(ir,provenance=prov)
    if canonical_bytes(rebuilt)!=hb:raise ValueError('HEADER_REBUILD_MISMATCH')
    return ir,h


def atomic_write(path: str|Path, ir: FactorIR, *, provenance: dict[str,Any], crash_before_rename: bool=False) -> dict[str,Any]:
    final=Path(path);final.parent.mkdir(parents=True,exist_ok=True);data=serialize(ir,provenance=provenance)
    fd,tmp_name=tempfile.mkstemp(prefix=final.name+'.staging.',dir=final.parent);tmp=Path(tmp_name)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if crash_before_rename:raise RuntimeError('INJECTED_CRASH_BEFORE_RENAME')
        os.replace(tmp,final);dfd=os.open(final.parent,os.O_DIRECTORY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    except Exception:
        raise
    return {'path':final.name,'bytes':len(data),'sha256':_sha(data),'action_key':provenance['action_key']}
