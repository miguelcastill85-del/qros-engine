#!/usr/bin/env python3
"""Content-addressed XAU DEV quote-quality index (no quote modification, no PnL).

Two sorted uint32 raw tick-index sets: CROSS (Ask<Bid), ZERO (Ask==Bid).
Immutable 0-based row indices preserve carrier sequence and same-ms physical order.
Only SOURCE_SHA-pin validated inputs are accepted; artifacts are atomically written.
"""
import argparse,hashlib,json,os,sys,tempfile,zlib
from pathlib import Path
import numpy as np

SOURCE_SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
RECORDS=151382388
RECORD_BYTES=17
DTYPE=np.dtype([('ms','<u8'),('bid','<i4'),('ask','<i4'),('flags','u1')],align=False)
assert DTYPE.itemsize==RECORD_BYTES

def canon(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest_bytes(b):return hashlib.sha256(b).hexdigest()
def digest_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def checked_encoded(index):
 index=np.asarray(index,dtype='<u4')
 if index.ndim!=1 or (index.size and (int(index[-1])>=RECORDS or np.any(index[1:]<=index[:-1]))):
  raise ValueError('UNSORTED_OR_BAD_GLOBAL_INDEX')
 raw=index.tobytes(order='C');compressed=zlib.compress(raw,level=9)
 return compressed,{'count':len(index),'raw_sha256':digest_bytes(raw),'raw_bytes':len(raw),'zlib_sha256':digest_bytes(compressed),'zlib_bytes':len(compressed),'first_index':int(index[0]) if index.size else None,'last_index':int(index[-1]) if index.size else None}
def decode_index(artifact,meta):
 blob=Path(artifact).read_bytes()
 if digest_bytes(blob)!=meta['zlib_sha256']:raise ValueError('INDEX_COMPRESSED_HASH_MISMATCH')
 data=zlib.decompress(blob)
 if digest_bytes(data)!=meta['raw_sha256'] or len(data)!=meta['raw_bytes']:
  raise ValueError('INDEX_RAW_HASH_MISMATCH')
 values=np.frombuffer(data,dtype='<u4')
 if len(values)!=meta['count'] or (len(values)>1 and np.any(values[1:]<=values[:-1])):
  raise ValueError('INDEX_FORMAT_UNSORTED')
 return values

def build(source,outdir,chunk_rows=2000000):
 source=Path(source);outdir=Path(outdir)
 if source.stat().st_size!=RECORDS*RECORD_BYTES or digest_file(source)!=SOURCE_SHA:raise ValueError('DEV_BYTES_IDENTITY_MISMATCH')
 if outdir.exists() and (outdir/'manifest.json').exists():
  old=json.loads((outdir/'manifest.json').read_text())
  if old['source_sha256']!=SOURCE_SHA:raise ValueError('STALE_ANOMALY_MANIFEST')
  for name,entry in old['artifacts'].items():decode_index(outdir/name,entry)
  return {'status':'IDEMPOTENT_EXISTING','counts':{k:v['count'] for k,v in old['artifacts'].items()}}
 if outdir.exists():raise ValueError('OUTPUT_UNCOMMITTED_OR_STALE')
 if not outdir.parent.is_dir():raise ValueError('OUTPUT_PARENT_MISSING')
 a=np.memmap(source,mode='r',dtype=DTYPE,shape=(RECORDS,))
 zero=[];cross=[];part_counts=[]
 for begin in range(0,RECORDS,chunk_rows):
  end=min(begin+chunk_rows,RECORDS)
  bid=a[begin:end]['bid'];ask=a[begin:end]['ask']
  z=np.flatnonzero(ask==bid).astype(np.uint32)+np.uint32(begin)
  c=np.flatnonzero(ask<bid).astype(np.uint32)+np.uint32(begin)
  zero.append(z);cross.append(c)
  part_counts.append({'start':begin,'end_exclusive':end,'zero':len(z),'crossed':len(c)})
 zero=np.concatenate(zero);cross=np.concatenate(cross)
 if len(zero)!=942184 or len(cross)!=74:raise ValueError('FROZEN_RAW_AUDIT_ANOMALY_COUNT_MISMATCH')
 if np.intersect1d(zero,cross).size:raise ValueError('ANOMALY_CLASSES_OVERLAP')
 maps={};payload={}
 for name,idx in [('zero_spread_indices.u32le.zlib',zero),('crossed_quote_indices.u32le.zlib',cross)]:
  payload[name],maps[name]=checked_encoded(idx)
 manifest={'schema':'QROS_XAU_DEV_QUOTE_ANOMALY_INDEX_1.0','status':'VERIFIED_RAW_QUOTE_CLASSIFICATION_NOT_FILL_AUTHORIZATION',
  'source_sha256':SOURCE_SHA,'records':RECORDS,'dtype':'<u8 timestamp_ms,<i4 bid,<i4 ask,u1 flags',
  'physical_sequence':'0-based raw row index, no sort or dedupe','artifacts':maps,
  'chunk_counts':part_counts,'zlib_version':zlib.ZLIB_VERSION,'numpy_version':np.__version__,
  'rules':{'zero_spread':'ask==bid; preserve original ticks; no zero-spread fill without source authenticity',
     'crossed':'ask<bid; preserve original ticks; fail closed for directly affected execution windows',
     'session_timezone':'UNBOUND','mask_overlap':'NOT_EVALUATED','economic_pnl_read':False}}
 stage=Path(tempfile.mkdtemp(prefix='.quote_index_staging_',dir=outdir.parent))
 try:
  for name,buf in payload.items():
   with (stage/name).open('wb') as f:f.write(buf);f.flush();os.fsync(f.fileno())
  with (stage/'manifest.json').open('w') as f:f.write(canon(manifest)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(stage,outdir)
 except BaseException:
  if stage.exists():
   import shutil;shutil.rmtree(stage)
  raise
 print(canon({'status':'PASS','zero_spread':len(zero),'crossed':len(cross),'compressed_bytes':sum(len(x) for x in payload.values())}),flush=True)
 return manifest

def intersects_sorted(sorted_indices,start,end_inclusive):
 """Research diagnostic only. A clean entry→exit path does NOT certify signal features."""
 i=int(np.searchsorted(sorted_indices,start,side='left'))
 return i<len(sorted_indices) and int(sorted_indices[i])<=end_inclusive

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args()
 print(canon(build(a.source,a.out_dir)),flush=True)
