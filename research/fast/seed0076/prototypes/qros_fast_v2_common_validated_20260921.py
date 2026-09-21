from __future__ import annotations
import sys,os,json,hashlib,sqlite3,tempfile,time,mmap,gc,struct,zlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/mnt/data/qros_fast_v2/scripts')
from qros_seed0076_config_stream import canonical,filter_packages,shard_base_rows,config_bytes
from qros_seed0076_structural_v220 import structural_states,box_history4,next_replacement_source,raw_close_crosses_four,filter_raw_to_candidates
from qros_seed0076_gate_engine_v221 import GateContext,TF_MIN
from qros_seed0076_carrier_masks_v221 import CarrierMaskEngine
TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);REARM_CODE={'RETURN_INSIDE_OR_LEVEL_REPLACED':0,'LEVEL_REPLACED_ONLY':1,'ONE_SIGNAL_PER_LEVEL':2};TIE_CODE={'SOURCE_ASYMMETRIC':0,'STRICT_ALL_NEIGHBORS':1};BUFFERS=(0.,.05,.10,.25);CLASS_HDR=struct.Struct('>32s32sIII')
def config_id(base,fp):return hashlib.sha256(config_bytes(base,fp)).digest()
def transform_key(fp):
 bm=float(fp.get('BREAKOUT_BUFFER',{}).get('buffer_atr',0.0))
 if 'RETEST_ENTRY' not in fp:return (bm,0,0)
 r=fp['RETEST_ENTRY'];return (bm,1 if r['confirmation']=='TOUCH_RECLAIM' else 2,int(r['window_bars']))
def package_partition(fps):
 d={}
 for i,fp in enumerate(fps):
  k=transform_key(fp);g={x:v for x,v in fp.items() if x not in ('BREAKOUT_BUFFER','RETEST_ENTRY')};d.setdefault(k,[]).append((i,g))
 return d
def raw_u64(ids):return np.asarray(ids,dtype='<u8').tobytes()
class DB:
 def __init__(self,path,domain):
  self.cx=sqlite3.connect(path);self.cx.execute('PRAGMA journal_mode=OFF');self.cx.execute('PRAGMA synchronous=OFF');self.cx.execute('PRAGMA temp_store=FILE');self.cx.execute('PRAGMA locking_mode=EXCLUSIVE');self.cx.execute('CREATE TABLE classes(class_hash BLOB PRIMARY KEY, raw_z BLOB NOT NULL, raw_len INTEGER NOT NULL, rep BLOB NOT NULL, alias_count INTEGER NOT NULL,event_count INTEGER NOT NULL) WITHOUT ROWID');self.cx.execute('CREATE TABLE aliases(config_id BLOB PRIMARY KEY,class_hash BLOB NOT NULL) WITHOUT ROWID');self.domain=domain;self.pending=0
 def register(self,ids,cfgs):
  raw=raw_u64(ids);ch=hashlib.sha256(self.domain+b'\0'+raw).digest();rz=zlib.compress(raw,1);rep=min(cfgs);n=len(ids);r=self.cx.execute('SELECT raw_z,raw_len,rep,alias_count,event_count FROM classes WHERE class_hash=?',(ch,)).fetchone()
  if r is None:self.cx.execute('INSERT INTO classes VALUES(?,?,?,?,?,?)',(ch,rz,len(raw),rep,len(cfgs),n))
  else:
   oldz,olen,orep,ac,ec=r
   if olen!=len(raw) or ec!=n or zlib.decompress(oldz)!=raw:raise RuntimeError('CLASS_COLLISION')
   self.cx.execute('UPDATE classes SET rep=?,alias_count=? WHERE class_hash=?',(rep if rep<orep else orep,ac+len(cfgs),ch))
  self.cx.executemany('INSERT INTO aliases VALUES(?,?)',((c,ch) for c in cfgs));self.pending+=len(cfgs)
  if self.pending>=100000:self.cx.commit();self.pending=0
 def close(self):self.cx.commit();self.cx.close()
def grouped(engine,pkgrows):
 masks={}; sig_to_idx={}
 for i,g in pkgrows:
  if not g:sig=('FULL',)
  else:
   trend=g.get('TREND');parts=[]
   for fam in sorted(g):
    p=engine.family(fam,g[fam],trend if fam in ('GEOMETRY','MULTI_TF','EMA_CROSS_RECENCY') else None);pb=p.tobytes();dh=hashlib.sha256(pb).digest();masks.setdefault(dh,pb);parts.append(dh)
   sig=tuple(parts)
  sig_to_idx.setdefault(sig,[]).append(i)
 outmap={}
 for sig,idxs in sig_to_idx.items():
  if sig==('FULL',):pb=engine.full.tobytes()
  else:
   arr=np.frombuffer(masks[sig[0]],dtype=np.uint8).copy()
   for dh in sig[1:]:np.bitwise_and(arr,np.frombuffer(masks[dh],dtype=np.uint8),out=arr)
   pb=arr.tobytes()
  h=hashlib.sha256(pb).digest();bucket=outmap.setdefault(h,[])
  for q,qq in bucket:
   if q==pb:qq.extend(idxs);break
  else:bucket.append((pb,list(idxs)))
 return [(h,pb,idxs) for h,b in outmap.items() for pb,idxs in b]
def session_ms(ticks,bars,cand,cbar,mode,tf):
 if len(cand)==0:return np.empty(0,np.int64)
 if mode=='TICK':return np.asarray(ticks['ts'][cand],dtype=np.int64)
 prev=np.asarray(cbar,np.int64)-1;return bars['bucket_ms'][prev].astype(np.int64)+np.int64(TF_MIN[tf]*60000)
def channels(C,prefix,si):
 off=C[prefix+'_offsets'];idx=C[prefix+'_idx'];bar=C[prefix+'_bar'];lid=C[prefix+'_lid'];o=[]
 for z in range(4):
  ch=si*4+z;a=int(off[ch]);b=int(off[ch+1]);o.append((idx[a:b],bar[a:b],lid[a:b]))
 return o
def finalize(path,domain,out):
 cx=sqlite3.connect(path);total=cx.execute('SELECT count(*) FROM aliases').fetchone()[0];distinct=cx.execute('SELECT count(*) FROM classes').fetchone()[0];hs=hashlib.sha256();ha=hashlib.sha256();zero=0;zero_rep=None;dups=0
 for ch,rawz,raw_len,rep,ac,ec in cx.execute('SELECT class_hash,raw_z,raw_len,rep,alias_count,event_count FROM classes ORDER BY class_hash'):
  ch=bytes(ch);raw=zlib.decompress(rawz);rep=bytes(rep)
  if ec==0:zero=int(ac);zero_rep=rep.hex()
  row={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':hashlib.sha256(raw).hexdigest()};hs.update(hashlib.sha256(canonical(row)).digest())
 for cfg,ch,rep in cx.execute('SELECT a.config_id,a.class_hash,c.rep FROM aliases a JOIN classes c ON a.class_hash=c.class_hash ORDER BY a.config_id'):
  cfg=bytes(cfg);ch=bytes(ch);rep=bytes(rep);ha.update(cfg);ha.update(ch);dups+=cfg!=rep
 cx.close();return {'processed_signal_configs':int(total),'distinct_mask_class_count':int(distinct),'duplicate_config_count':int(dups),'zero_event_class_alias_count':zero,'zero_event_representative_config_id':zero_rep,'semantic_class_root_sha256':hs.hexdigest(),'full_alias_mapping_root_sha256':ha.hexdigest()}
