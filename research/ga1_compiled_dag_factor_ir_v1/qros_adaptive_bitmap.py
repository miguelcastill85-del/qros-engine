from __future__ import annotations
import hashlib, struct
import numpy as np

MAGIC=b'QROS_ADAPTIVE_BITMAP_V1\n'
HEADER=struct.Struct('>BQQQ32s')
CODEC_DENSE=0
CODEC_SPARSE_U32=1
UINT32_MAX=np.iinfo(np.uint32).max

def _dense(mask: np.ndarray) -> bytes:
    return np.packbits(np.asarray(mask,dtype=bool),bitorder='little').tobytes()

def canonical_sha256(mask: np.ndarray) -> str:
    return hashlib.sha256(_dense(mask)).hexdigest()

def _validate_padding(raw: bytes,n:int) -> None:
    expected=(n+7)//8
    if len(raw)!=expected: raise ValueError('DENSE_LENGTH_INVALID')
    if n and n%8 and (raw[-1] & ((~((1<<(n%8))-1))&0xff)):
        raise ValueError('NONCANONICAL_DENSE_PADDING')

def encode(mask: np.ndarray) -> bytes:
    m=np.asarray(mask,dtype=bool)
    if m.ndim!=1: raise ValueError('MASK_VECTOR_REQUIRED')
    n=int(len(m)); dense=_dense(m); count=int(np.count_nonzero(m))
    digest=hashlib.sha256(dense).digest()
    sparse_allowed=n<=int(UINT32_MAX)
    sparse_bytes=count*4 if sparse_allowed else (1<<63)
    if sparse_bytes < len(dense):
        codec=CODEC_SPARSE_U32
        pos=np.flatnonzero(m).astype('>u4',copy=False)
        payload=pos.tobytes()
    else:
        codec=CODEC_DENSE
        payload=dense
    return MAGIC+HEADER.pack(codec,n,count,len(payload),digest)+payload

def inspect(data: bytes) -> dict:
    if not isinstance(data,(bytes,bytearray,memoryview)): raise ValueError('BITMAP_BYTES_REQUIRED')
    data=bytes(data)
    if not data.startswith(MAGIC): raise ValueError('BITMAP_MAGIC_MISMATCH')
    p=len(MAGIC)
    if len(data)<p+HEADER.size: raise ValueError('BITMAP_HEADER_TRUNCATED')
    codec,n,count,payload_len,digest=HEADER.unpack_from(data,p);p+=HEADER.size
    if codec not in (CODEC_DENSE,CODEC_SPARSE_U32): raise ValueError('BITMAP_CODEC_INVALID')
    if count>n: raise ValueError('BITMAP_COUNT_GT_LENGTH')
    if len(data)!=p+payload_len: raise ValueError('BITMAP_PAYLOAD_LENGTH_MISMATCH')
    payload=data[p:]
    if codec==CODEC_DENSE:
        _validate_padding(payload,n)
        arr=np.unpackbits(np.frombuffer(payload,dtype=np.uint8),bitorder='little')[:n].astype(bool,copy=False)
        if int(np.count_nonzero(arr))!=count: raise ValueError('DENSE_COUNT_MISMATCH')
        dense=payload
    else:
        if n>int(UINT32_MAX): raise ValueError('SPARSE_U32_LENGTH_OVERFLOW')
        if payload_len!=count*4: raise ValueError('SPARSE_PAYLOAD_LENGTH_INVALID')
        pos=np.frombuffer(payload,dtype='>u4').astype(np.uint64,copy=False)
        if len(pos)>1 and np.any(pos[1:]<=pos[:-1]): raise ValueError('SPARSE_POSITIONS_NOT_STRICTLY_INCREASING')
        if len(pos) and int(pos[-1])>=n: raise ValueError('SPARSE_POSITION_OUT_OF_RANGE')
        arr=np.zeros(n,dtype=bool)
        if len(pos): arr[pos.astype(np.int64,copy=False)]=True
        dense=_dense(arr)
    if hashlib.sha256(dense).digest()!=digest: raise ValueError('CANONICAL_BITMAP_HASH_MISMATCH')
    return {'codec':'DENSE' if codec==CODEC_DENSE else 'SPARSE_U32','length':int(n),'count':int(count),'payload_bytes':int(payload_len),'canonical_sha256':digest.hex()}

def decode(data: bytes) -> np.ndarray:
    meta=inspect(data)
    p=len(MAGIC)+HEADER.size
    payload=bytes(data)[p:]
    n=meta['length']
    if meta['codec']=='DENSE':
        return np.unpackbits(np.frombuffer(payload,dtype=np.uint8),bitorder='little')[:n].astype(bool,copy=False)
    pos=np.frombuffer(payload,dtype='>u4').astype(np.int64,copy=False)
    out=np.zeros(n,dtype=bool)
    if len(pos): out[pos]=True
    return out
