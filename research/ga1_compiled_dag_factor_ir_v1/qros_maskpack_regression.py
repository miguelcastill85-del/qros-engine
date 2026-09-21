from __future__ import annotations
import hashlib, json, struct
from pathlib import Path
import numpy as np

MAGIC=b'QROS_GA1_MASKPACK_V1\n'
PACK_HDR=struct.Struct('>32s32sIII')
INDEX_REC=struct.Struct('>32sQ32sIII32s')
MAP_REC=struct.Struct('>32s32s')


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')


def decode_delta(delta:bytes,event_count:int)->np.ndarray:
    if len(delta)!=event_count*4: raise ValueError('DELTA_LENGTH_EVENT_COUNT_MISMATCH')
    if event_count==0:return np.empty(0,dtype=np.uint64)
    d=np.frombuffer(delta,dtype='<u4').astype(np.uint64)
    ids=np.cumsum(d,dtype=np.uint64)
    if len(ids)>1 and np.any(ids[1:]<=ids[:-1]):raise ValueError('DECODED_IDS_NOT_STRICTLY_INCREASING')
    return ids


def verify_maskpack(pack_path: str|Path,index_path: str|Path,mapping_path: str|Path,*,domain:dict,expected:dict|None=None)->dict:
    pack_path=Path(pack_path);index_path=Path(index_path);mapping_path=Path(mapping_path)
    index_bytes=index_path.read_bytes();mapping_bytes=mapping_path.read_bytes()
    if len(index_bytes)%INDEX_REC.size:raise ValueError('INDEX_LENGTH_INVALID')
    if len(mapping_bytes)%MAP_REC.size:raise ValueError('MAPPING_LENGTH_INVALID')
    idx=[]
    for off in range(0,len(index_bytes),INDEX_REC.size):idx.append(INDEX_REC.unpack_from(index_bytes,off))
    seen=set();hsem=hashlib.sha256();event_total=0;zero_alias=0;prev=None
    with pack_path.open('rb') as f:
        if f.read(len(MAGIC))!=MAGIC:raise ValueError('MASKPACK_MAGIC_MISMATCH')
        for rec in idx:
            ch,pack_off,rep,ac,ec,db,masksha=rec
            if prev is not None and ch<=prev:raise ValueError('CLASS_ORDER_INVALID')
            prev=ch
            if f.tell()!=pack_off:raise ValueError('PACK_OFFSET_MISMATCH')
            hdr=f.read(PACK_HDR.size)
            if len(hdr)!=PACK_HDR.size:raise ValueError('PACK_HEADER_TRUNCATED')
            pch,prep,pac,pec,pdb=PACK_HDR.unpack(hdr)
            if (pch,prep,pac,pec,pdb)!=(ch,rep,ac,ec,db):raise ValueError('INDEX_PACK_METADATA_MISMATCH')
            delta=f.read(db)
            if len(delta)!=db:raise ValueError('PACK_DELTA_TRUNCATED')
            ids=decode_delta(delta,ec);raw=ids.astype('<u8',copy=False).tobytes()
            if hashlib.sha256(raw).digest()!=masksha:raise ValueError('MASK_CONTENT_SHA_MISMATCH')
            want=hashlib.sha256(canonical(domain)+b'\0'+raw).digest()
            if want!=ch:raise ValueError('DOMAIN_BOUND_CLASS_HASH_MISMATCH')
            semantic={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':masksha.hex()}
            hsem.update(hashlib.sha256(canonical(semantic)).digest());event_total+=int(ec);seen.add(ch)
            if ec==0:zero_alias+=int(ac)
        if f.read(1):raise ValueError('TRAILING_PACK_BYTES')
    hmap=hashlib.sha256();cfg_count=0;prev_cfg=None
    map_counts={ch:0 for ch in seen}; map_min={}
    for off in range(0,len(mapping_bytes),MAP_REC.size):
        cfg,ch=MAP_REC.unpack_from(mapping_bytes,off)
        if prev_cfg is not None and cfg<=prev_cfg:raise ValueError('CONFIG_ORDER_INVALID')
        prev_cfg=cfg
        if ch not in seen:raise ValueError('MAPPING_UNKNOWN_CLASS')
        map_counts[ch]+=1
        if ch not in map_min or cfg<map_min[ch]:map_min[ch]=cfg
        hmap.update(cfg);hmap.update(ch);cfg_count+=1
    zero_rep=None
    for ch,pack_off,rep,ac,ec,db,masksha in idx:
        if map_counts.get(ch,0)!=int(ac):raise ValueError('ALIAS_COUNT_MAPPING_MISMATCH')
        if map_min.get(ch)!=rep:raise ValueError('REPRESENTATIVE_NOT_MAPPING_MINIMUM')
        if int(ec)==0:zero_rep=rep.hex()
    result={'processed_signal_configs':cfg_count,'distinct_mask_class_count':len(idx),'duplicate_config_count':cfg_count-len(idx),'zero_event_class_alias_count':zero_alias,'zero_event_representative_config_id':zero_rep,'semantic_class_root_sha256':hsem.hexdigest(),'full_alias_mapping_root_sha256':hmap.hexdigest(),'mapping_file_sha256':hashlib.sha256(mapping_bytes).hexdigest(),'event_count_sum':event_total}
    if result['mapping_file_sha256']!=result['full_alias_mapping_root_sha256']:raise ValueError('MAPPING_FILE_ROOT_MISMATCH')
    if expected:
        unknown=sorted(set(expected)-set(result))
        if unknown:raise ValueError('UNSUPPORTED_EXPECTED_FIELDS:'+','.join(unknown))
        for k,v in expected.items():
            if result[k]!=v:raise ValueError('EXPECTED_MISMATCH:'+k)
    return result
