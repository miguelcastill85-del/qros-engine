from __future__ import annotations
import hashlib,json,struct
from pathlib import Path
import numpy as np
from qros_seed0076_config_stream import canonical
REC=struct.Struct('>32s32s32sII')
def reduce(root: Path,total_expected: int):
 cpath=root/'class_occ.bin';apath=root/'aliases.bin'
 raw=cpath.read_bytes();n=len(raw)//REC.size
 arr=np.frombuffer(raw,dtype=np.dtype([('ch','V32'),('mh','V32'),('rep','V32'),('ac','>u4'),('ec','>u4')],align=False))
 order=np.argsort(arr['ch'],kind='stable');a=arr[order]
 hs=hashlib.sha256();distinct=0;zero=0;i=0
 while i<n:
  j=i+1
  while j<n and a['ch'][j]==a['ch'][i]:j+=1
  ch=bytes(a['ch'][i]);mh=bytes(a['mh'][i]);ec=int(a['ec'][i]);reps=[];ac=0
  for k in range(i,j):
   if bytes(a['mh'][k])!=mh or int(a['ec'][k])!=ec:raise RuntimeError('CLASS_COLLISION')
   reps.append(bytes(a['rep'][k]));ac+=int(a['ac'][k])
  rep=min(reps);row={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':ac,'event_count':ec,'mask_content_sha256':mh.hex()}
  hs.update(hashlib.sha256(canonical(row)).digest());distinct+=1
  if ec==0:zero=ac
  i=j
 b=apath.read_bytes();m=len(b)//64
 if m!=total_expected:raise RuntimeError(f'ALIAS_COUNT:{m}')
 aa=np.frombuffer(b,dtype=np.dtype([('cfg','V32'),('ch','V32')],align=False))
 o=np.argsort(aa['cfg'],kind='stable');sa=aa[o]
 if m>1 and np.any(sa['cfg'][1:]==sa['cfg'][:-1]):raise RuntimeError('DUPLICATE_CONFIG_ID')
 ha=hashlib.sha256()
 for chunk in np.array_split(sa,max(1,(m+99999)//100000)):ha.update(chunk.tobytes())
 return {
  'processed_signal_configs':m,
  'distinct_mask_class_count':distinct,
  'duplicate_config_count':m-distinct,
  'zero_event_class_alias_count':zero,
  'semantic_class_root_sha256':hs.hexdigest(),
  'full_alias_mapping_root_sha256':ha.hexdigest()
 }
