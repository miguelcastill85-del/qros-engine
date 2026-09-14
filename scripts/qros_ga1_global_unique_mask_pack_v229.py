from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, struct, tempfile, time
from pathlib import Path
import numpy as np

SRC_HDR=struct.Struct('>32s32sIII')
PACK_HDR=struct.Struct('>32s32sIII')
INDEX_REC=struct.Struct('>32sQ32sIII32s')
MAGIC=b'QROS_GA1_MASKPACK_V1\n'
MAP_REC=struct.Struct('>32s32s')

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def fsync_file(f):
    f.flush(); os.fsync(f.fileno())

def atomic_path(final:Path):
    final.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=final.name+'.tmp.',dir=final.parent)
    os.close(fd)
    return Path(tmp)

def decode_delta(delta:bytes,event_count:int):
    if len(delta)!=event_count*4: raise RuntimeError('DELTA_LENGTH_EVENT_COUNT_MISMATCH')
    if event_count==0: return np.empty(0,dtype=np.uint64)
    d=np.frombuffer(delta,dtype='<u4').astype(np.uint64)
    ids=np.cumsum(d,dtype=np.uint64)
    if len(ids)>1 and np.any(ids[1:]<=ids[:-1]): raise RuntimeError('DECODED_IDS_NOT_STRICTLY_INCREASING')
    return ids

def build(args):
    t0=time.time()
    group_root=Path(args.group_root); merge_root=Path(args.merge_root); out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    mr=json.loads((merge_root/'merge_receipt.json').read_text())
    if mr.get('status')!='PASS': raise RuntimeError('MERGE_RECEIPT_NOT_PASS')
    domain=mr['domain']; domain_b=canonical(domain)
    expected_classes=int(mr['distinct_mask_class_count']); expected_configs=int(mr['processed_signal_configs'])
    expected_sem=mr['semantic_class_root_sha256']; expected_maproot=mr['full_alias_mapping_root_sha256']
    expected_config_root=mr['ordered_config_id_stream_root_sha256']
    expected_shard=mr['shard_id']; expected_desc=mr['descriptor_sha256']
    pack_final=out/'global_unique_masks.maskpack'; index_final=out/'global_unique_masks.index.bin'; map_final=out/'global_config_to_class.bin'
    pack_tmp=atomic_path(pack_final); index_tmp=atomic_path(index_final); map_tmp=atomic_path(map_final)
    files={i:(group_root/f'group{i:02d}'/'mask_classes.delta_u32.bin').open('rb') for i in range(24)}
    hsem=hashlib.sha256(); class_count=0; event_total=0; delta_total=0; seen=set()
    try:
        with pack_tmp.open('wb') as pf,index_tmp.open('wb') as ix:
            pf.write(MAGIC)
            with (merge_root/'global_mask_class_index.jsonl').open('r',encoding='utf-8') as jf:
                prev=None
                for line in jf:
                    if not line.strip(): continue
                    row=json.loads(line); ch=bytes.fromhex(row['class_hash'])
                    if prev is not None and ch<=prev: raise RuntimeError('GLOBAL_INDEX_NOT_STRICT_CLASSHASH_ORDER')
                    prev=ch; gi=int(row['source_group']); off=int(row['source_blob_offset']); db=int(row['delta_bytes']); ec=int(row['event_count'])
                    sf=files[gi]; sf.seek(off); hdr=sf.read(SRC_HDR.size)
                    if len(hdr)!=SRC_HDR.size: raise RuntimeError('SOURCE_RECORD_HEADER_TRUNCATED')
                    sch,srep,sac,sec,sdb=SRC_HDR.unpack(hdr)
                    if sch!=ch: raise RuntimeError('SOURCE_CLASS_HASH_MISMATCH')
                    if int(sec)!=ec or int(sdb)!=db: raise RuntimeError('SOURCE_RECORD_METADATA_MISMATCH')
                    delta=sf.read(db)
                    if len(delta)!=db: raise RuntimeError('SOURCE_DELTA_TRUNCATED')
                    ids=decode_delta(delta,ec); raw=ids.astype('<u8',copy=False).tobytes(); masksha=hashlib.sha256(raw).hexdigest()
                    if masksha!=row['mask_content_sha256']: raise RuntimeError('MASK_CONTENT_SHA256_MISMATCH')
                    if hashlib.sha256(domain_b+b'\0'+raw).digest()!=ch: raise RuntimeError('DOMAIN_BOUND_CLASS_HASH_MISMATCH')
                    rep=bytes.fromhex(row['representative_config_id']); ac=int(row['alias_count']); pack_off=pf.tell()
                    pf.write(PACK_HDR.pack(ch,rep,ac,ec,db)); pf.write(delta)
                    ix.write(INDEX_REC.pack(ch,pack_off,rep,ac,ec,db,bytes.fromhex(masksha)))
                    semantic={'class_hash':row['class_hash'],'representative_config_id':row['representative_config_id'],'alias_count':ac,'event_count':ec,'mask_content_sha256':masksha}
                    hsem.update(hashlib.sha256(canonical(semantic)).digest()); class_count+=1; event_total+=ec; delta_total+=db; seen.add(ch)
            fsync_file(pf); fsync_file(ix)
        if class_count!=expected_classes: raise RuntimeError('CLASS_COUNT_MISMATCH')
        if hsem.hexdigest()!=expected_sem: raise RuntimeError('SEMANTIC_ROOT_MISMATCH')
        cx=sqlite3.connect(merge_root/'merge.sqlite'); hmap=hashlib.sha256(); cfg_count=0; prev=None
        with map_tmp.open('wb') as mf:
            for cfg,ch in cx.execute('SELECT config_id,class_hash FROM aliases ORDER BY config_id'):
                cfg=bytes(cfg); ch=bytes(ch)
                if prev is not None and cfg<=prev: raise RuntimeError('CONFIG_MAPPING_NOT_STRICTLY_ORDERED')
                prev=cfg
                if ch not in seen: raise RuntimeError('MAPPING_REFERENCES_UNKNOWN_CLASS')
                mf.write(MAP_REC.pack(cfg,ch)); hmap.update(cfg); hmap.update(ch); cfg_count+=1
            fsync_file(mf)
        cx.close()
        if cfg_count!=expected_configs: raise RuntimeError('CONFIG_MAPPING_COUNT_MISMATCH')
        if hmap.hexdigest()!=expected_maproot: raise RuntimeError('FULL_ALIAS_MAPPING_ROOT_MISMATCH')
        os.replace(pack_tmp,pack_final); os.replace(index_tmp,index_final); os.replace(map_tmp,map_final)
        dfd=os.open(out,os.O_DIRECTORY); os.fsync(dfd); os.close(dfd)
    finally:
        for f in files.values(): f.close()
        for p in [pack_tmp,index_tmp,map_tmp]:
            if p.exists(): p.unlink(missing_ok=True)
    rec={'schema':'QROS_SEED0076_GA1_GLOBAL_UNIQUE_MASK_PACK_RECEIPT_1.0','status':'PASS','seed':'WEB_SEED_0076','domain':domain,'shard_id':expected_shard,'descriptor_sha256':expected_desc,'processed_signal_configs':expected_configs,'distinct_mask_class_count':expected_classes,'duplicate_config_count':int(mr['duplicate_config_count']),'zero_event_class_alias_count':int(mr['zero_event_class_alias_count']),'semantic_class_root_sha256':expected_sem,'full_alias_mapping_root_sha256':expected_maproot,'ordered_config_id_stream_root_sha256':expected_config_root,'pack_format':{'magic_ascii':MAGIC.decode('ascii'),'record_struct':'>32s32sIII','record_fields':['class_hash','global_representative_config_id','alias_count','event_count','delta_bytes'],'delta_encoding':'uint32 little-endian differences of strictly increasing uint64 source-record indices; ids=cumsum(delta)','ordering':'class_hash ascending'},'index_format':{'record_struct':'>32sQ32sIII32s','record_fields':['class_hash','pack_record_offset','global_representative_config_id','alias_count','event_count','delta_bytes','mask_content_sha256'],'ordering':'class_hash ascending'},'mapping_format':{'record_struct':'>32s32s','record_fields':['config_id','class_hash'],'ordering':'config_id ascending','file_sha256_equals_full_alias_mapping_root':True},'event_count_sum_across_unique_classes':event_total,'delta_bytes_sum':delta_total,'artifacts':[{'path':pack_final.name,'bytes':pack_final.stat().st_size,'sha256':sha256_file(pack_final)},{'path':index_final.name,'bytes':index_final.stat().st_size,'sha256':sha256_file(index_final)},{'path':map_final.name,'bytes':map_final.stat().st_size,'sha256':sha256_file(map_final)}],'source_merge_receipt_sha256':mr['receipt_sha256'],'source_group_count':24,'economic_pnl_read':False,'holdout_open':False,'elapsed_seconds':round(time.time()-t0,6)}
    if rec['artifacts'][2]['sha256']!=expected_maproot: raise RuntimeError('MAPPING_FILE_SHA_NOT_EQUAL_ROOT')
    rr=rec.copy(); rec['receipt_sha256']=hashlib.sha256(canonical(rr)).hexdigest(); (out/'global_unique_mask_pack_receipt.json').write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n'); print(json.dumps(rec,sort_keys=True))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--group-root',required=True); ap.add_argument('--merge-root',required=True); ap.add_argument('--out-dir',required=True); build(ap.parse_args())
