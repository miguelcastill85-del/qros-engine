#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, struct
from pathlib import Path
HDR=struct.Struct('>32s32sIII')
PAIR=64

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read_delta(gdir,row):
 p=gdir/'mask_classes.delta_u32.bin'
 with p.open('rb') as f:
  f.seek(int(row['blob_offset'])); h=f.read(HDR.size)
  if len(h)!=HDR.size: raise RuntimeError('TRUNCATED_CLASS_HEADER')
  ch,rep,ac,ec,n=HDR.unpack(h)
  if ch.hex()!=row['class_hash'] or rep.hex()!=row['representative_config_id'] or ac!=row['alias_count'] or ec!=row['event_count'] or n!=row['delta_bytes']:
   raise RuntimeError('CLASS_HEADER_INDEX_MISMATCH')
  d=f.read(n)
  if len(d)!=n: raise RuntimeError('TRUNCATED_DELTA')
  return d

def verify_artifacts(gdir,r):
 for a in r['artifacts']:
  p=gdir/a['path']
  if not p.is_file() or p.stat().st_size!=a['bytes'] or sha256_file(p)!=a['sha256']:
   raise RuntimeError(f"GROUP_ARTIFACT_INVALID:{gdir.name}:{a['path']}")

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--groups-root',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);a=ap.parse_args()
 root=Path(a.groups_root);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 dbp=out/'merge.sqlite'; dbp.unlink(missing_ok=True)
 cx=sqlite3.connect(dbp);cx.execute('PRAGMA journal_mode=DELETE');cx.execute('PRAGMA synchronous=FULL');cx.execute('PRAGMA temp_store=FILE')
 cx.execute('CREATE TABLE classes(class_hash BLOB PRIMARY KEY, source_group INTEGER NOT NULL, blob_offset INTEGER NOT NULL, delta_bytes INTEGER NOT NULL, rep BLOB NOT NULL, alias_count INTEGER NOT NULL, event_count INTEGER NOT NULL, mask_content_sha256 TEXT NOT NULL)')
 cx.execute('CREATE TABLE aliases(config_id BLOB PRIMARY KEY,class_hash BLOB NOT NULL)')
 total_groups=0; total_local_classes=0; group_receipts=[]
 domain=None; config_root=None; shard_id=None; descriptor_sha256=None
 for gi in range(24):
  gd=root/f'group{gi:02d}'; rp=gd/'worker_receipt.json'
  if not rp.is_file(): raise RuntimeError(f'MISSING_GROUP_RECEIPT:{gi}')
  r=json.load(rp.open());
  if r.get('status')!='PASS' or r.get('processed_signal_configs')!=33528: raise RuntimeError(f'INVALID_GROUP_RECEIPT:{gi}')
  if r.get('economic_pnl_read') or r.get('holdout_open'): raise RuntimeError('ECONOMIC_OR_HOLDOUT_CONTAMINATION')
  rd=r.get('domain'); rr=r.get('ordered_config_id_stream_root_sha256'); rs=r.get('shard_id'); rds=r.get('descriptor_sha256')
  if not isinstance(rd,dict) or not rr or not rs or not rds: raise RuntimeError(f'GROUP_IDENTITY_MISSING:{gi}')
  if domain is None: domain=rd; config_root=rr; shard_id=rs; descriptor_sha256=rds
  elif rd!=domain or rr!=config_root or rs!=shard_id or rds!=descriptor_sha256: raise RuntimeError(f'GROUP_IDENTITY_MISMATCH:{gi}')
  verify_artifacts(gd,r)
  rep_to_class={}; local_alias_sum=0; local_classes=0
  with (gd/'mask_class_index.jsonl').open('rb') as f:
   for line in f:
    row=json.loads(line); ch=bytes.fromhex(row['class_hash']); rep=bytes.fromhex(row['representative_config_id']); rep_to_class[rep]=ch; local_alias_sum+=int(row['alias_count']); local_classes+=1
    old=cx.execute('SELECT source_group,blob_offset,delta_bytes,rep,alias_count,event_count,mask_content_sha256 FROM classes WHERE class_hash=?',(ch,)).fetchone()
    if old is None:
     cx.execute('INSERT INTO classes VALUES(?,?,?,?,?,?,?,?)',(ch,gi,int(row['blob_offset']),int(row['delta_bytes']),rep,int(row['alias_count']),int(row['event_count']),row['mask_content_sha256']))
    else:
     og,oo,od,orep,oac,oec,omh=old
     if od!=row['delta_bytes'] or oec!=row['event_count'] or omh!=row['mask_content_sha256']:
      raise RuntimeError('CLASS_HASH_METADATA_COLLISION')
     ep=root/f'group{og:02d}'/'mask_classes.delta_u32.bin'
     with ep.open('rb') as ef: ef.seek(oo+HDR.size); ed=ef.read(od)
     nd=read_delta(gd,row)
     if ed!=nd: raise RuntimeError('SHA256_CLASS_HASH_COLLISION_EXACT_BYTES')
     nrep=rep if rep<orep else orep
     cx.execute('UPDATE classes SET rep=?,alias_count=? WHERE class_hash=?',(nrep,oac+int(row['alias_count']),ch))
    cx.execute('INSERT INTO aliases VALUES(?,?)',(rep,ch))
  if local_alias_sum!=33528 or local_classes!=r['distinct_mask_class_count']: raise RuntimeError(f'LOCAL_CLASS_ACCOUNTING_FAIL:{gi}')
  dp=gd/'duplicate_alias_pairs.bin'
  with dp.open('rb') as f:
   while True:
    b=f.read(PAIR)
    if not b:break
    if len(b)!=PAIR:raise RuntimeError('TRUNCATED_DUP_PAIR')
    cfg,rep=b[:32],b[32:]; ch=rep_to_class.get(rep)
    if ch is None:raise RuntimeError('DUP_REP_NOT_CLASS_REP')
    cx.execute('INSERT INTO aliases VALUES(?,?)',(cfg,ch))
  cx.commit();total_groups+=1;total_local_classes+=local_classes
  group_receipts.append({'group':gi,'receipt_sha256':r['receipt_sha256'],'distinct':r['distinct_mask_class_count'],'duplicates':r['duplicate_config_count']})
 total=int(cx.execute('SELECT count(*) FROM aliases').fetchone()[0]); distinct=int(cx.execute('SELECT count(*) FROM classes').fetchone()[0]); alias_sum=int(cx.execute('SELECT sum(alias_count) FROM classes').fetchone()[0])
 if total!=804672 or alias_sum!=804672:raise RuntimeError(f'GLOBAL_ACCOUNTING_FAIL:{total}:{alias_sum}')
 index=out/'global_mask_class_index.jsonl'; hsem=hashlib.sha256();hphys=hashlib.sha256();zero_alias=0;zero_rep=None
 with index.open('wb') as f:
  for ch,sg,bo,db,rep,ac,ec,mh in cx.execute('SELECT class_hash,source_group,blob_offset,delta_bytes,rep,alias_count,event_count,mask_content_sha256 FROM classes ORDER BY class_hash'):
   ch=bytes(ch);rep=bytes(rep)
   sem={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':mh}
   sb=canonical(sem);hsem.update(hashlib.sha256(sb).digest())
   phy={**sem,'source_group':int(sg),'source_path':f'group{int(sg):02d}/mask_classes.delta_u32.bin','source_blob_offset':int(bo),'delta_bytes':int(db)}
   pb=canonical(phy);f.write(pb+b'\n');hphys.update(hashlib.sha256(pb).digest())
   if ec==0:zero_alias=int(ac);zero_rep=rep.hex()
 dupout=out/'global_duplicate_alias_pairs.bin';halias=hashlib.sha256();dups=0
 with dupout.open('wb') as f:
  q='SELECT a.config_id,a.class_hash,c.rep FROM aliases a JOIN classes c ON a.class_hash=c.class_hash ORDER BY a.config_id'
  for cfg,ch,rep in cx.execute(q):
   cfg,ch,rep=bytes(cfg),bytes(ch),bytes(rep);halias.update(cfg);halias.update(ch)
   if cfg!=rep:f.write(cfg);f.write(rep);dups+=1
 if dups!=total-distinct:raise RuntimeError('GLOBAL_DUPLICATE_COUNT_MISMATCH')
 cx.close()
 receipt={'schema':'QROS_SEED0076_GA1_DISTRIBUTED_SHARD_MERGE_RECEIPT_1.1','status':'PASS','seed':'WEB_SEED_0076','domain':domain,'shard_id':shard_id,'descriptor_sha256':descriptor_sha256,'source_group_count':total_groups,'processed_signal_configs':total,'local_distinct_class_sum_before_cross_group_merge':total_local_classes,'distinct_mask_class_count':distinct,'duplicate_config_count':dups,'zero_event_class_alias_count':zero_alias,'zero_event_representative_config_id':zero_rep,'semantic_class_root_sha256':hsem.hexdigest(),'distributed_physical_index_root_sha256':hphys.hexdigest(),'full_alias_mapping_root_sha256':halias.hexdigest(),'ordered_config_id_stream_root_sha256':config_root,'identity_binding':'domain+shard_id+descriptor_sha256+config_root inferred from group00 and required identical across all 24 group receipts','storage':'exact distributed mask blobs retained in 24 group artifacts; global index references exact group+offset+length; class-hash duplicates were byte-compared exactly before merge','group_receipts':group_receipts,'artifacts':[{'path':index.name,'bytes':index.stat().st_size,'sha256':sha256_file(index)},{'path':dupout.name,'bytes':dupout.stat().st_size,'sha256':sha256_file(dupout)}],'economic_pnl_read':False,'holdout_open':False}
 receipt['receipt_sha256']=hashlib.sha256(canonical(receipt)).hexdigest();Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print(json.dumps({k:receipt[k] for k in ['status','domain','processed_signal_configs','distinct_mask_class_count','duplicate_config_count','semantic_class_root_sha256','full_alias_mapping_root_sha256','ordered_config_id_stream_root_sha256']}))
if __name__=='__main__':main()
