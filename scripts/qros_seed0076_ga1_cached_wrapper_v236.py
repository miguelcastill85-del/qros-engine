from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
WORKER_PATH=HERE/'qros_seed0076_ga1_shard_worker_v223.py'
EXPECTED_GIT_BLOB='c77e0a5156c5bb1a874d3c33fde49f162a2a3041'

def git_blob_sha1(p):
    b=p.read_bytes();h=hashlib.sha1();h.update(f'blob {len(b)}\0'.encode());h.update(b);return h.hexdigest()
if git_blob_sha1(WORKER_PATH)!=EXPECTED_GIT_BLOB: raise RuntimeError('V223_WORKER_BLOB_MISMATCH')
s=importlib.util.spec_from_file_location('qros_v223_worker',WORKER_PATH);w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
orig_build=w.build_structural_cache;orig_raw=w.raw_cache_for
CACHE=None;STRUCT_MAP=None

def patched_build(bars,point,spec):
    h,l,out=orig_build(bars,point,spec)
    mapping={(11,'SOURCE_ASYMMETRIC'):0,(11,'STRICT_ALL_NEIGHBORS'):1,(13,'SOURCE_ASYMMETRIC'):2,(13,'STRICT_ALL_NEIGHBORS'):3,(3,'SOURCE_ASYMMETRIC'):4,(3,'STRICT_ALL_NEIGHBORS'):5,(5,'SOURCE_ASYMMETRIC'):6,(5,'STRICT_ALL_NEIGHBORS'):7,(7,'SOURCE_ASYMMETRIC'):8,(7,'STRICT_ALL_NEIGHBORS'):9,(9,'SOURCE_ASYMMETRIC'):10,(9,'STRICT_ALL_NEIGHBORS'):11}
    for k,idx in mapping.items():out[k]['_tick_cache_struct_index']=idx
    return h,l,out

def _channels(prefix,si):
    off=CACHE[prefix+'_offsets'];idx=CACHE[prefix+'_idx'];bar=CACHE[prefix+'_bar'];lid=CACHE[prefix+'_lid'];out=[]
    for z in range(4):
        ch=si*4+z;a=int(off[ch]);b=int(off[ch+1]);out.append((idx[a:b],bar[a:b],lid[a:b]))
    return out

def patched_raw(st,bars,ind,ticks,h,l,side_sign,point,trigger):
    if trigger!='TICK_BREAK':return orig_raw(st,bars,ind,ticks,h,l,side_sign,point,trigger)
    si=int(st['_tick_cache_struct_index'])
    if side_sign==1:
        level,lid=st['sh'],st['hid'];ol,olid=st['sl'],st['lid'];same=_channels('up',si);opp=_channels('down',si)
    else:
        level,lid=st['sl'],st['lid'];ol,olid=st['sh'],st['hid'];same=_channels('down',si);opp=_channels('up',si)
    for arr in same:
        if len(arr[0]) and (not np.array_equal(arr[2],lid[arr[1]])):raise RuntimeError('TICK_CACHE_SAME_LEVEL_ID_MISMATCH')
    for arr in opp:
        if len(arr[0]) and (not np.array_equal(arr[2],olid[arr[1]])):raise RuntimeError('TICK_CACHE_OPP_LEVEL_ID_MISMATCH')
    return level,lid,ol,olid,same,opp

def main():
    global CACHE
    ap=argparse.ArgumentParser();ap.add_argument('--tick-raw-cache',required=True)
    ap.add_argument('--shard-json',required=True);ap.add_argument('--spec',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--ticks',required=True);ap.add_argument('--bar-root',required=True);ap.add_argument('--ind-root',required=True);ap.add_argument('--point',type=float,required=True);ap.add_argument('--expected-config-root');ap.add_argument('--only-base-index',type=int);ap.add_argument('--only-group-index',type=int)
    a=ap.parse_args();CACHE=np.load(a.tick_raw_cache,mmap_mode='r',allow_pickle=False)
    w.build_structural_cache=patched_build;w.raw_cache_for=patched_raw
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);shard=json.loads(Path(a.shard_json).read_text());d=shard['descriptor']
    res=w.process(shard,a.spec,a.ticks,a.bar_root,a.ind_root,a.point,out,a.expected_config_root,a.only_base_index,a.only_group_index)
    expected=d['signal_configs'] if (a.only_base_index is None and a.only_group_index is None) else (11176 if a.only_base_index is not None else 33528)
    status='PASS' if res['input_config_count']==expected else 'FAIL'
    receipt={'schema':'QROS_SEED0076_GA1_SHARD_WORKER_RECEIPT_1.0','status':status,'shard_id':shard['shard_id'],'descriptor_sha256':shard['descriptor_sha256'],'domain':{'asset':d['asset'],'side':d['side'],'timeframe':d['timeframe']},'processed_signal_configs':res['input_config_count'],'distinct_mask_class_count':res['distinct_mask_class_count'],'duplicate_config_count':res['duplicate_config_count'],'zero_event_class_alias_count':res['zero_event_class_alias_count'],'zero_event_representative_config_id':res['zero_event_representative_config_id'],'class_root_sha256':res['class_root_sha256'],'semantic_class_root_sha256':res['semantic_class_root_sha256'],'full_alias_mapping_root_sha256':res['full_alias_mapping_root_sha256'],'ordered_config_id_stream_root_sha256':res['ordered_config_id_stream_root_sha256'],'metrics':res['metrics'],'elapsed_seconds':res['elapsed_seconds'],'artifacts':res['artifacts'],'economic_pnl_read':False,'holdout_open':False,'worker_semantics':'V223 exact worker + lossless shared raw-tick cache; event semantics unchanged; V236 candidate corrects the repository-relative worker filename only and is non-authoritative until byte-exact parity certification','parent_worker_git_blob_sha1':EXPECTED_GIT_BLOB,'tick_raw_cache_sha256':hashlib.sha256(Path(a.tick_raw_cache).read_bytes()).hexdigest()}
    raw=w.canonical(receipt);receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest();Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':status,'processed':receipt['processed_signal_configs'],'distinct':receipt['distinct_mask_class_count'],'duplicates':receipt['duplicate_config_count'],'semantic_root':receipt['semantic_class_root_sha256'],'physical_root':receipt['class_root_sha256'],'elapsed':receipt['elapsed_seconds']}));return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
