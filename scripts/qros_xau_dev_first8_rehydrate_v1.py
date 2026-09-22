#!/usr/bin/env python3
"""Replay frozen Seed0076 XAU DEV PACKED17 from 8 ZIP parts, checkpointing by part.

No trading signals, no PnL, no timezone assumption. Requires exact source ZIP bytes.
Crash recovery truncates uncommitted append to the last authenticated checkpoint.
"""
import argparse,hashlib,json,os,zipfile
from pathlib import Path

SPEC=[
(1,102025545,"d8a9c2138b184db087c087b4b3297ca2f4ba9da4991c49fb3332ebad0016bb70"),
(2,100422805,"159087740e5196849adac1905a0cbea777544833692745c89c331a4238d3be3a"),
(3,99870071,"ada6d3c587e46d2deceb28795d15962aeac9949f8d83d360260c28a7698116a9"),
(4,101825467,"241b74428b584819b54c1cfc5e3093e2efdbddfcbf42250cb9111c7d713ae241"),
(5,101538275,"3328ec3ef844450eaf9757bfe64fe6d23c38970b002ce7d0bac2c244e68f2aad"),
(6,102849303,"9bb324c3d274d718be6a714f22df51f8785a1e4fe0117531a45b860395bf5ab8"),
(7,104515054,"ddaff24ab8ccacc59de256c09e24738ad360eaa45efa004089611285c49c0185"),
(8,104291866,"362a9b7d04f0dd89ed5348e30c286e9b028d3f38521a18299cfa0b61d611d44b")]
DEV_RECORDS=151382388
PACKED_SIZE=17
DEV_BYTES=2573500596
DEV_SHA256="3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53"
CHUNK=4*1024*1024

def canon(o):return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def hash_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(CHUNK),b''):h.update(b)
 return h.hexdigest()
def durable_json(path,obj):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.new')
 with tmp.open('wb') as f:
  f.write((canon(obj)+'\n').encode());f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def run(source_dir,out_dir):
 source_dir=Path(source_dir);out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
 target=out_dir/'XAUUSD_DEV_PACKED17_151382388.bin';tmp=out_dir/'XAUUSD_DEV_PACKED17_151382388.bin.partial'
 ckpt=out_dir/'XAUUSD_DEV_PACKED17_151382388.checkpoint.json'
 receipt=out_dir/'XAUUSD_DEV_PACKED17_151382388_RECEIPT.json'
 if target.exists():
  if target.stat().st_size!=DEV_BYTES or hash_file(target)!=DEV_SHA256:raise RuntimeError('EXISTING_TARGET_IDENTITY_MISMATCH')
  return {'status':'IDEMPOTENT_EXISTING','bytes':DEV_BYTES,'sha256':DEV_SHA256}
 completed=[];h=hashlib.sha256();written=0;meta_prev=None
 if ckpt.exists():
  c=json.loads(ckpt.read_text());completed=c['completed_parts'];written=c['bytes_done']
  if not tmp.exists() or tmp.stat().st_size<written:raise RuntimeError('CHECKPOINT_PAYLOAD_MISSING')
  with tmp.open('r+b') as f:f.truncate(written)
  with tmp.open('rb') as f:
   for b in iter(lambda:f.read(CHUNK),b''):h.update(b)
  if h.hexdigest()!=c['prefix_sha256']:raise RuntimeError('CHECKPOINT_PREFIX_TAMPERED')
  meta_prev=c['last_meta']
 else:
  if tmp.exists():raise RuntimeError('UNAUTHORIZED_PARTIAL_WITHOUT_CHECKPOINT')
  durable_json(ckpt,{'completed_parts':[], 'bytes_done':0,'prefix_sha256':h.hexdigest(),'last_meta':None})
 for number,byte_size,want_zip_sha in SPEC:
  p=source_dir/f'QROS_XAU_FULL_HISTORY_v2_part{number:03d}-of-035.zip'
  if number in completed:continue
  if number!=len(completed)+1:raise RuntimeError('NON_FIFO_PART')
  if p.stat().st_size!=byte_size or hash_file(p)!=want_zip_sha:raise RuntimeError(f'SOURCE_ZIP_MISMATCH_{number}')
  with zipfile.ZipFile(p) as z:
   meta=json.loads(z.read('PART_META.json'))
   expected_start=(number-1)*20000000
   if (meta['asset']!='XAU' or meta['index']!=number or meta['start_record']!=expected_start
       or meta['records']!=20000000 or meta['payload_bytes']!=340000000
       or meta['schema']!='QROS_PACKED17_ZIP_PART_2.0'
       or meta['first_timestamp_ms']>meta['last_timestamp_ms']):raise RuntimeError('PART_META_MISMATCH')
   if meta_prev and meta['first_timestamp_ms']<meta_prev['last_timestamp_ms']:raise RuntimeError('CROSS_PART_TIMESTAMP_BACKWARDS')
   member=meta['payload_member'];info=z.getinfo(member)
   if info.file_size!=meta['payload_bytes']:raise RuntimeError('PAYLOAD_MEMBER_SIZE_MISMATCH')
   payload_hash=hashlib.sha256();rows_needed=min(20000000,max(0,DEV_RECORDS-expected_start));remaining=rows_needed*PACKED_SIZE
   with z.open(member,'r') as stream,tmp.open('ab') as sink:
    while True:
     b=stream.read(CHUNK)
     if not b:break
     payload_hash.update(b)
     if remaining>0:
      part=b[:remaining];sink.write(part);h.update(part);written+=len(part);remaining-=len(part)
    sink.flush();os.fsync(sink.fileno())
   if payload_hash.hexdigest()!=meta['payload_sha256'] or remaining!=0:raise RuntimeError('PAYLOAD_HASH_OR_PREFIX_MISMATCH')
  completed.append(number);meta_prev=meta
  durable_json(ckpt,{'completed_parts':completed,'bytes_done':written,'prefix_sha256':h.hexdigest(),'last_meta':meta})
  print(canon({'part':number,'status':'PASS_CHECKPOINT','prefix_bytes':written,'payload_sha256':payload_hash.hexdigest()}),flush=True)
 if written!=DEV_BYTES or h.hexdigest()!=DEV_SHA256 or len(completed)!=8:raise RuntimeError('DEV_PREFIX_SHA_OR_LENGTH_MISMATCH')
 os.replace(tmp,target)
 receipt_obj={'schema':'QROS_SEED0076_XAU_DEV_FIRST8_REHYDRATION_RECEIPT_1.0','status':'PASS_EXACT_PREFIX',
     'dev_records':DEV_RECORDS,'dev_bytes':written,'dev_sha256':h.hexdigest(),
     'zip_parts':completed,'source_zip_sha256':{str(n):s for n,_,s in SPEC},
     'asset':'XAUUSD','packed_record_bytes':PACKED_SIZE,
     'broker_timezone':'UNRESOLVED_NOT_INFERRED_FROM_METADATA',
     'economic_pnl_read':False,'event_masks_recovered':False,'holdout_open':False,
     'first_gate_execution_authorized':False,
     'next_action':'Audit actual tick schema/order/BidAsk using frozen decode; recover exact GA1 mask carriers and provenance before economics.'}
 durable_json(receipt,receipt_obj)
 return receipt_obj

def main():
 p=argparse.ArgumentParser();p.add_argument('--source-dir',default='/mnt/data');p.add_argument('--out-dir',required=True)
 a=p.parse_args();print(canon(run(a.source_dir,a.out_dir)),flush=True)
if __name__=='__main__':main()
