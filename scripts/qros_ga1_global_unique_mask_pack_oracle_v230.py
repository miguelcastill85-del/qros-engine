from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
import numpy as np
PACK_HDR=struct.Struct('>32s32sIII'); INDEX_REC=struct.Struct('>32sQ32sIII32s'); MAP_REC=struct.Struct('>32s32s')
MAGIC=b'QROS_GA1_MASKPACK_V1\n'
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(a):
 root=Path(a.pack_root); mr=json.load(open(Path(a.merge_root)/'merge_receipt.json')); br=json.load(open(root/'global_unique_mask_pack_receipt.json'))
 checks={}; domain_b=canonical(mr['domain']); pf=open(root/'global_unique_masks.maskpack','rb'); ix=open(root/'global_unique_masks.index.bin','rb'); checks['magic']=pf.read(len(MAGIC))==MAGIC
 hsem=hashlib.sha256(); n=0; prev=None; event_sum=0
 while True:
  ir=ix.read(INDEX_REC.size)
  if not ir: break
  if len(ir)!=INDEX_REC.size: raise RuntimeError('INDEX_TRUNCATED')
  ch,off,rep,ac,ec,db,msha=INDEX_REC.unpack(ir); checks.setdefault('class_order',True)
  if prev is not None and ch<=prev: checks['class_order']=False
  prev=ch; pf.seek(off); ph=pf.read(PACK_HDR.size)
  if len(ph)!=PACK_HDR.size: raise RuntimeError('PACK_HEADER_TRUNCATED')
  pch,prep,pac,pec,pdb=PACK_HDR.unpack(ph)
  if (pch,prep,pac,pec,pdb)!=(ch,rep,ac,ec,db): raise RuntimeError('PACK_INDEX_RECORD_MISMATCH')
  delta=pf.read(db)
  if len(delta)!=db: raise RuntimeError('PACK_DELTA_TRUNCATED')
  if db!=ec*4: raise RuntimeError('PACK_DELTA_EVENT_MISMATCH')
  d=np.frombuffer(delta,dtype='<u4').astype(np.uint64); ids=np.cumsum(d,dtype=np.uint64) if ec else np.empty(0,np.uint64)
  if ec>1 and np.any(ids[1:]<=ids[:-1]): raise RuntimeError('PACK_IDS_NOT_STRICT')
  raw=ids.astype('<u8',copy=False).tobytes()
  if hashlib.sha256(raw).digest()!=msha: raise RuntimeError('PACK_MASK_SHA_MISMATCH')
  if hashlib.sha256(domain_b+b'\0'+raw).digest()!=ch: raise RuntimeError('PACK_CLASS_BINDING_MISMATCH')
  sem={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':msha.hex()}; hsem.update(hashlib.sha256(canonical(sem)).digest()); n+=1; event_sum+=ec
 pf.close(); ix.close(); checks['class_count']=n==int(mr['distinct_mask_class_count'])==int(br['distinct_mask_class_count']); checks['semantic_root']=hsem.hexdigest()==mr['semantic_class_root_sha256']==br['semantic_class_root_sha256']; checks['event_sum']=event_sum==int(br['event_count_sum_across_unique_classes'])
 known=set()
 with open(root/'global_unique_masks.index.bin','rb') as f:
  while True:
   r=f.read(INDEX_REC.size)
   if not r: break
   known.add(INDEX_REC.unpack(r)[0])
 hm=hashlib.sha256(); cfg=0; prev=None
 with open(root/'global_config_to_class.bin','rb') as f:
  while True:
   r=f.read(MAP_REC.size)
   if not r:break
   if len(r)!=MAP_REC.size:raise RuntimeError('MAP_TRUNCATED')
   c,ch=MAP_REC.unpack(r)
   if prev is not None and c<=prev: raise RuntimeError('MAP_NOT_SORTED')
   prev=c
   if ch not in known: raise RuntimeError('MAP_UNKNOWN_CLASS')
   hm.update(c);hm.update(ch);cfg+=1
 checks['mapping_count']=cfg==int(mr['processed_signal_configs'])==int(br['processed_signal_configs']); checks['mapping_root']=hm.hexdigest()==mr['full_alias_mapping_root_sha256']==br['full_alias_mapping_root_sha256']; checks['mapping_file_sha']=sha256_file(root/'global_config_to_class.bin')==hm.hexdigest(); checks['artifact_hashes']=all(sha256_file(root/x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes'] for x in br['artifacts']); checks['domain']=br['domain']==mr['domain'] and set(br['domain'])=={'asset','side','timeframe'} and all(isinstance(br['domain'][k],str) and br['domain'][k] for k in ('asset','side','timeframe')); checks['shard']=br['shard_id']==mr['shard_id']; checks['descriptor']=br['descriptor_sha256']==mr['descriptor_sha256']; checks['config_root']=br['ordered_config_id_stream_root_sha256']==mr['ordered_config_id_stream_root_sha256']; checks['no_pnl']=br['economic_pnl_read'] is False and br['holdout_open'] is False
 status='PASS' if all(checks.values()) else 'FAIL'; rec={'schema':'QROS_SEED0076_GA1_GLOBAL_UNIQUE_MASK_PACK_ORACLE_1.0','status':status,'checks':checks,'domain':br['domain'],'shard_id':br['shard_id'],'distinct_mask_class_count':n,'processed_signal_configs':cfg,'semantic_class_root_sha256':hsem.hexdigest(),'full_alias_mapping_root_sha256':hm.hexdigest(),'pack_receipt_sha256':br['receipt_sha256'],'economic_pnl_read':False,'holdout_open':False}; rr=rec.copy();rec['receipt_sha256']=hashlib.sha256(canonical(rr)).hexdigest();Path(a.receipt).write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');print(json.dumps(rec,sort_keys=True));raise SystemExit(0 if status=='PASS' else 2)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--pack-root',required=True);ap.add_argument('--merge-root',required=True);ap.add_argument('--receipt',required=True);main(ap.parse_args())
