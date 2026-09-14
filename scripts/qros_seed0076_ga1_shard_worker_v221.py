#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, struct, tempfile, time
from pathlib import Path
import numpy as np
import zlib, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from qros_seed0076_config_stream import canonical, filter_packages, shard_base_rows, config_bytes
def config_id(base,filters): return hashlib.sha256(config_bytes(base,filters)).digest()
from qros_seed0076_structural_v220 import structural_states, box_history4, next_replacement_source, raw_tick_crosses_four, raw_close_crosses_four, filter_raw_to_candidates
from qros_seed0076_gate_engine_v221 import GateContext, TF_MIN
from qros_seed0076_carrier_masks_v221 import CarrierMaskEngine, group_packages_exact

TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
CLASS_HDR=struct.Struct('>32s32sIII')
REARM_CODE={'RETURN_INSIDE_OR_LEVEL_REPLACED':0,'LEVEL_REPLACED_ONLY':1,'ONE_SIGNAL_PER_LEVEL':2}
TIE_CODE={'SOURCE_ASYMMETRIC':0,'STRICT_ALL_NEIGHBORS':1}
BUFFERS=(0.0,0.05,0.10,0.25)

def sha256_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def domain_bytes(asset,side,tf):return canonical({'asset':asset,'side':side,'timeframe':tf})

def transform_key(fp):
    bm=0.0
    if 'BREAKOUT_BUFFER' in fp:bm=float(fp['BREAKOUT_BUFFER']['buffer_atr'])
    if 'RETEST_ENTRY' not in fp:return (bm,0,0)
    r=fp['RETEST_ENTRY'];code=1 if r['confirmation']=='TOUCH_RECLAIM' else 2
    return (bm,code,int(r['window_bars']))

def package_partition(fps):
    d={}
    for i,fp in enumerate(fps):
        key=transform_key(fp);g={k:v for k,v in fp.items() if k not in ('BREAKOUT_BUFFER','RETEST_ENTRY')}
        d.setdefault(key,[]).append((i,g))
    return d

def session_ms_for_candidates(ticks,bars,cand,cbar,mode,tf):
    if len(cand)==0:return np.empty(0,np.int64)
    if mode=='TICK':return np.asarray(ticks['ts'][cand],dtype=np.int64)
    prev=np.asarray(cbar,dtype=np.int64)-1
    if np.any(prev<0):raise RuntimeError('CLOSE_CANDIDATE_WITHOUT_PREVIOUS_BAR')
    return bars['bucket_ms'][prev].astype(np.int64)+np.int64(TF_MIN[tf]*60000)

def delta_u32_bytes(ids):
    ids=np.asarray(ids,dtype=np.uint64)
    if len(ids)==0:return b''
    if np.any(ids[1:]<=ids[:-1]):raise RuntimeError('MASK_SOURCE_INDICES_NOT_STRICTLY_INCREASING')
    d=np.diff(np.r_[np.uint64(0),ids])
    if np.any(d>np.iinfo(np.uint32).max):raise RuntimeError('DELTA_U32_OVERFLOW')
    return d.astype('<u4').tobytes()

def raw_u64_bytes(ids):return np.asarray(ids,dtype='<u8').tobytes()

class ClassDB:
    def __init__(self,path:Path,asset,side,tf):
        self.path=path;self.domain=domain_bytes(asset,side,tf)
        self.cx=sqlite3.connect(path);self.cx.execute('PRAGMA journal_mode=DELETE');self.cx.execute('PRAGMA synchronous=FULL');self.cx.execute('PRAGMA temp_store=FILE')
        self.cx.execute('CREATE TABLE classes(class_hash BLOB PRIMARY KEY, mask_z BLOB NOT NULL, raw_len INTEGER NOT NULL, rep BLOB NOT NULL, alias_count INTEGER NOT NULL, event_count INTEGER NOT NULL)')
        self.cx.execute('CREATE TABLE aliases(config_id BLOB PRIMARY KEY, class_hash BLOB NOT NULL)')
        self.pending=0
    def register(self,ids,config_ids):
        raw=raw_u64_bytes(ids); ch=hashlib.sha256(self.domain+b'\0'+raw).digest(); rz=zlib.compress(raw,1); n=len(ids)
        row=self.cx.execute('SELECT mask_z,raw_len,rep,alias_count,event_count FROM classes WHERE class_hash=?',(ch,)).fetchone()
        local_rep=min(config_ids)
        if row is None:self.cx.execute('INSERT INTO classes VALUES(?,?,?,?,?,?)',(ch,rz,len(raw),local_rep,len(config_ids),n))
        else:
            oz,olen,rep,ac,ec=row
            if olen!=len(raw) or ec!=n or zlib.decompress(oz)!=raw:raise RuntimeError('SHA256_MASK_CLASS_COLLISION')
            self.cx.execute('UPDATE classes SET rep=?,alias_count=? WHERE class_hash=?',(local_rep if local_rep<rep else rep,ac+len(config_ids),ch))
        try:self.cx.executemany('INSERT INTO aliases VALUES(?,?)',((c,ch) for c in config_ids))
        except sqlite3.IntegrityError as e:raise RuntimeError('DUPLICATE_CONFIG_ID') from e
        self.pending+=len(config_ids)
        if self.pending>=20000:self.cx.commit();self.pending=0
    def close(self):self.cx.commit();self.cx.close()

def base_key_without_rearm(base):
    return (base['fractal_window'],base['tie_policy'],base['trigger'])

def build_structural_cache(bars,point,spec):
    h=bars['high_bid'].astype(np.float64)*point;l=bars['low_bid'].astype(np.float64)*point
    out={}
    for w in spec['base_axes']['fractal_window']:
        for tie in spec['base_axes']['tie_policy']:
            sh,sl,hid,lid=structural_states(h,l,int(w),TIE_CODE[tie]);out[(int(w),tie)]={'sh':sh,'sl':sl,'hid':hid,'lid':lid,'boxhist':box_history4(sh,sl,hid,lid)}
    return h,l,out

def raw_cache_for(st,bars,ind,ticks,h,l,side_sign,point,trigger):
    first=bars['first_source_index'];last=bars['last_source_index'];c=bars['close_bid'].astype(np.float64)*point
    if side_sign==1:level,lid=st['sh'],st['hid'];opp_level,opp_lid=st['sl'],st['lid']
    else:level,lid=st['sl'],st['lid'];opp_level,opp_lid=st['sh'],st['hid']
    if trigger=='TICK_BREAK':
        ap=np.r_[np.nan,ind['ATR14'][:-1]]
        _,same=raw_tick_crosses_four(ticks['bid'],first,last,h,l,level,lid,ap,side_sign,point)
        _,opp=raw_tick_crosses_four(ticks['bid'],first,last,h,l,opp_level,opp_lid,ap,-side_sign,point)
    else:
        _,outs,barsx,lids=raw_close_crosses_four(first,c,level,lid,ind['ATR14'],side_sign)
        same=[(outs[i],barsx[i],lids[i]) for i in range(4)]
        _,oouts,obars,olids=raw_close_crosses_four(first,c,opp_level,opp_lid,ind['ATR14'],-side_sign)
        opp=[(oouts[i],obars[i],olids[i]) for i in range(4)]
    return level,lid,opp_level,opp_lid,same,opp

def finalize_artifacts(db_path:Path,out:Path,asset,side,tf):
    cx=sqlite3.connect(db_path)
    total=int(cx.execute('SELECT count(*) FROM aliases').fetchone()[0]);distinct=int(cx.execute('SELECT count(*) FROM classes').fetchone()[0])
    classes_bin=out/'mask_classes.delta_u32.bin'; index_jsonl=out/'mask_class_index.jsonl'; dup=out/'duplicate_alias_pairs.bin'
    hclass=hashlib.sha256();hsemantic=hashlib.sha256();zero_alias=0;zero_rep=None
    offset=0
    with classes_bin.open('wb') as bf,index_jsonl.open('wb') as jf:
        for ch,mz,raw_len,rep,ac,ec in cx.execute('SELECT class_hash,mask_z,raw_len,rep,alias_count,event_count FROM classes ORDER BY class_hash'):
            ch=bytes(ch);rep=bytes(rep);raw=zlib.decompress(mz);ids=np.frombuffer(raw,dtype='<u8');dbytes=delta_u32_bytes(ids)
            if ec==0:zero_alias=int(ac);zero_rep=rep.hex()
            hdr=CLASS_HDR.pack(ch,rep,int(ac),int(ec),len(dbytes));bf.write(hdr);bf.write(dbytes)
            row={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':hashlib.sha256(raw).hexdigest(),'blob_offset':offset,'delta_bytes':len(dbytes)}
            cb=canonical(row);jf.write(cb+b'\n');hclass.update(hashlib.sha256(cb).digest())
            semantic_row={'class_hash':ch.hex(),'representative_config_id':rep.hex(),'alias_count':int(ac),'event_count':int(ec),'mask_content_sha256':hashlib.sha256(raw).hexdigest()};sb=canonical(semantic_row);hsemantic.update(hashlib.sha256(sb).digest());offset+=CLASS_HDR.size+len(dbytes)
    halias=hashlib.sha256();duplicates=0
    with dup.open('wb') as f:
        q='SELECT a.config_id,a.class_hash,c.rep FROM aliases a JOIN classes c ON a.class_hash=c.class_hash ORDER BY a.config_id'
        for cfg,ch,rep in cx.execute(q):
            cfg=bytes(cfg);ch=bytes(ch);rep=bytes(rep);halias.update(cfg);halias.update(ch)
            if cfg!=rep:f.write(cfg);f.write(rep);duplicates+=1
    cx.close()
    return {'input_config_count':total,'distinct_mask_class_count':distinct,'duplicate_config_count':duplicates,'zero_event_class_alias_count':zero_alias,'zero_event_representative_config_id':zero_rep,'class_root_sha256':hclass.hexdigest(),'semantic_class_root_sha256':hsemantic.hexdigest(),'full_alias_mapping_root_sha256':halias.hexdigest(),'artifacts':[{'path':classes_bin.name,'bytes':classes_bin.stat().st_size,'sha256':sha256_file(classes_bin)},{'path':index_jsonl.name,'bytes':index_jsonl.stat().st_size,'sha256':sha256_file(index_jsonl)},{'path':dup.name,'bytes':dup.stat().st_size,'sha256':sha256_file(dup)}]}

def process(shard, spec_path, ticks_path, bar_root, ind_root, point, out, expected_config_root=None, only_base_index=None):
    d=shard['descriptor'];asset=d['asset'];side=d['side'];tf=d['timeframe'];side_sign=1 if side=='BUY' else -1
    if d['signal_configs']!=804672:raise RuntimeError('SHARD_SIGNAL_CONFIG_COUNT_NOT_804672')
    spec=json.loads(Path(spec_path).read_text(encoding='utf-8'));ticks=np.memmap(ticks_path,dtype=TICK_DTYPE,mode='r');bars=np.load(Path(bar_root)/f'{asset}_{tf}_BID_BARS.npy',mmap_mode='r',allow_pickle=False);z=np.load(Path(ind_root)/f'{asset}_{tf}_INDICATORS.npz',allow_pickle=False);ind={k:z[k] for k in z.files}
    fps=filter_packages(spec);bases=shard_base_rows(spec,asset,side,tf);parts=package_partition(fps)
    if len(fps)!=11176 or len(bases)!=72 or len(parts)!=28:raise RuntimeError('FROZEN_ENUMERATION_COUNT_MISMATCH')
    hr=hashlib.sha256();cfg_count=0
    for base in bases:
        for fp in fps:hr.update(config_id(base,fp));cfg_count+=1
    config_root=hr.hexdigest()
    if cfg_count!=804672:raise RuntimeError('CONFIG_STREAM_COUNT_MISMATCH')
    if expected_config_root and config_root!=expected_config_root:raise RuntimeError('CONFIG_STREAM_ROOT_MISMATCH')
    h,l,sc=build_structural_cache(bars,point,spec);c=bars['close_bid'].astype(np.float64)*point;first=bars['first_source_index'];last=bars['last_source_index'];ctx=GateContext(asset,tf,side,bar_root,ind_root,point)
    fd,tmp=tempfile.mkstemp(prefix='ga1_masks.',suffix='.sqlite',dir=out);os.close(fd);os.unlink(tmp);dbp=Path(tmp);db=ClassDB(dbp,asset,side,tf)
    base_groups={}
    for bi,base in enumerate(bases):base_groups.setdefault(base_key_without_rearm(base),[]).append((bi,base))
    metrics={'structural_trigger_groups':0,'transform_carriers':0,'candidate_union_total':0,'local_gate_groups_total':0,'base_transform_rearm_evaluations':0}
    t0=time.time()
    try:
        for gnum,(k,rows) in enumerate(sorted(base_groups.items(),key=lambda x:canonical({'fractal_window':x[0][0],'tie_policy':x[0][1],'trigger':x[0][2]}))):
            w,tie,trigger=k;st=sc[(int(w),tie)];level,lid,ol,olid,same,opp=raw_cache_for(st,bars,ind,ticks,h,l,side_sign,point,trigger);nr=next_replacement_source(lid,first);ap=np.r_[np.nan,ind['ATR14'][:-1]]
            row_by_rearm={b['rearm_mode']:b for _,b in rows}
            if set(row_by_rearm)!=set(REARM_CODE):raise RuntimeError('REARM_GROUP_INCOMPLETE')
            for tkey,pkgrows in sorted(parts.items()):
                bm,rcode,rwin=tkey;bidx=BUFFERS.index(float(bm));raw_idx,raw_bar,raw_lid=same[bidx];opp_idx=opp[bidx][0]
                cand_by={}
                for rname,rc in REARM_CODE.items():
                    cand,cbar=filter_raw_to_candidates(ticks['bid'],first,last,l,h,c,level,lid,nr,ap,raw_idx,raw_bar,raw_lid,opp_idx,side_sign,point,float(bm),rc,int(rcode),int(rwin))
                    if len(cand)>1 and np.any(cand[1:]<=cand[:-1]):raise RuntimeError('CANDIDATES_NOT_STRICTLY_INCREASING')
                    cand_by[rname]=(cand,cbar)
                union=np.unique(np.concatenate([v[0] for v in cand_by.values()])) if any(len(v[0]) for v in cand_by.values()) else np.empty(0,np.int64)
                ubar=np.searchsorted(first,union,side='right')-1 if len(union) else np.empty(0,np.int64)
                final_mode='TICK' if (rcode==1 or (rcode==0 and trigger=='TICK_BREAK')) else 'CLOSE'
                sms=session_ms_for_candidates(ticks,bars,union,ubar,final_mode,tf)
                eng=CarrierMaskEngine(ctx,union,ubar,st['sh'],st['sl'],st['boxhist'],sms)
                groups=group_packages_exact(eng,pkgrows)
                metrics['transform_carriers']+=1;metrics['candidate_union_total']+=len(union);metrics['local_gate_groups_total']+=len(groups)
                memberships={}
                for rname,(cand,_) in cand_by.items():
                    m=np.zeros(len(union),dtype=bool)
                    if len(cand):m[np.searchsorted(union,cand)]=True
                    memberships[rname]=np.packbits(m,bitorder='little')
                for rname,base in row_by_rearm.items():
                    if only_base_index is not None:
                        idx=bases.index(base)
                        if idx!=only_base_index:continue
                    mem=memberships[rname]
                    for _,packed_bytes,pidxs in groups:
                        p=np.frombuffer(packed_bytes,dtype=np.uint8);selp=np.bitwise_and(p,mem);ids=eng.selected_indices(selp)
                        cfgs=[config_id(base,fps[i]) for i in pidxs]
                        db.register(ids,cfgs)
                    metrics['base_transform_rearm_evaluations']+=1
            metrics['structural_trigger_groups']+=1
            if only_base_index is not None and any(bases.index(b)==only_base_index for _,b in rows):break
        db.close()
        result=finalize_artifacts(dbp,out,asset,side,tf)
    finally:
        try:db.close()
        except Exception:pass
        dbp.unlink(missing_ok=True)
    result.update({'ordered_config_id_stream_root_sha256':config_root,'elapsed_seconds':round(time.time()-t0,6),'metrics':metrics})
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--shard-json',required=True);ap.add_argument('--spec',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--ticks',required=True);ap.add_argument('--bar-root',required=True);ap.add_argument('--ind-root',required=True);ap.add_argument('--point',type=float,required=True);ap.add_argument('--expected-config-root');ap.add_argument('--only-base-index',type=int)
    a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);shard=json.loads(Path(a.shard_json).read_text());d=shard['descriptor']
    res=process(shard,a.spec,a.ticks,a.bar_root,a.ind_root,a.point,out,a.expected_config_root,a.only_base_index)
    expected=d['signal_configs'] if a.only_base_index is None else 11176
    status='PASS' if res['input_config_count']==expected else 'FAIL'
    receipt={'schema':'QROS_SEED0076_GA1_SHARD_WORKER_RECEIPT_1.0','status':status,'shard_id':shard['shard_id'],'descriptor_sha256':shard['descriptor_sha256'],'domain':{'asset':d['asset'],'side':d['side'],'timeframe':d['timeframe']},'processed_signal_configs':res['input_config_count'],'distinct_mask_class_count':res['distinct_mask_class_count'],'duplicate_config_count':res['duplicate_config_count'],'zero_event_class_alias_count':res['zero_event_class_alias_count'],'zero_event_representative_config_id':res['zero_event_representative_config_id'],'class_root_sha256':res['class_root_sha256'],'semantic_class_root_sha256':res['semantic_class_root_sha256'],'full_alias_mapping_root_sha256':res['full_alias_mapping_root_sha256'],'ordered_config_id_stream_root_sha256':res['ordered_config_id_stream_root_sha256'],'metrics':res['metrics'],'elapsed_seconds':res['elapsed_seconds'],'artifacts':res['artifacts'],'economic_pnl_read':False,'holdout_open':False,'worker_semantics':'V220 event-axis+geometry correction; V221 temporal/session/opposite-buffer closure; exact mask identity uses ordered uint64 source-record coordinates in fixed domain'}
    raw=canonical(receipt);receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest();Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':status,'processed':receipt['processed_signal_configs'],'distinct':receipt['distinct_mask_class_count'],'duplicates':receipt['duplicate_config_count'],'semantic_root':receipt['semantic_class_root_sha256'],'physical_root':receipt['class_root_sha256'],'elapsed':receipt['elapsed_seconds']}));return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
