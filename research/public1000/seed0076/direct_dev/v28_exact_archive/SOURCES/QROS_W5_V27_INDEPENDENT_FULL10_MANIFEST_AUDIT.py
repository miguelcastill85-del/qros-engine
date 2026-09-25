#!/usr/bin/env python3
"""Independent immutable-byte closure of one preregistered W5 cell. No PnL."""
import os, json,hashlib,numpy as np
from pathlib import Path
R=Path(__file__).resolve().parent
SIDE_SHA={'BUY':'0dbaf56a5a8f0b1fce3b4c92fc44f0fc6146a237e9f23eaf6da75e4be82eecb5','SELL':'d2a130f42f4ab077437fe237363b863bf49c3631c2b9e482aa2121d93c9cc47b'}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def atom(p,obj):
 tmp=p.with_suffix(p.suffix+'.partial');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.replace(tmp,p)
seen={'BUY':{},'SELL':{}};phys={};fam=set();artifacts=[];channel_rows=[];refs=0
for ch in range(8):
 side='BUY' if ch<4 else 'SELL';dr=R/f'V27_FULL10_PRE_ECON_CH{ch}';mp=dr/'ALL_ROUTES_MANIFEST.json';m=json.load(open(mp));assert m['side']==side and m['channel']==ch and m['PnL_read']==False
 assert m['packages']==(10645 if ch in (0,4) else 177)
 for a in m['artifacts']:
  fp=dr/a['name'];assert fp.stat().st_size==a['bytes'] and sha(fp)==a['sha256'],(ch,a)
 artifact_sha=sha(mp);nrows=0;dups=0
 for row in m['routes']:
  name=row['route'];r=next(a for a in m['artifacts'] if a['name']==name+'_PHYSICAL_MASKS.npz')
  with np.load(dr/r['name'],allow_pickle=False) as z:
   masks=z['masks'];ids=z['mask_ids'];candidate_root=str(z['candidate_root_sha256']);assert candidate_root==row['candidate_root']
   assert len(ids)==len(masks)==row['physical_masks']
   pj=dr/(name+'_PHYSICAL.jsonl')
   with pj.open() as f:
    for i,line in enumerate(f):
     rec=json.loads(line);pid=rec['physical_mask_id'];assert pid==ids[i] and rec['physical_index']==i
     key=(side,pid);bh=hashlib.sha256(masks[i].tobytes()).hexdigest()
     value=(candidate_root,bh,rec['accepted_signal_count'])
     if key in phys:
      assert phys[key]==value,('PHYSICAL_HASH_COLLISION_OR_DRIFT',key)
      dups+=1
     else:phys[key]=value
   sj=dr/(name+'_SEMANTIC.jsonl')
   with sj.open() as f:
    for line in f:
     rec=json.loads(line);idx=rec['config_index'];assert 0<=idx<11176 and rec['physical_mask_id'] in ids and rec['config_id'] and rec['route']==name
     assert idx not in seen[side],('REPEATED_CONFIG_ID',side,idx)
     seen[side][idx]=rec['config_id'];fam.update(rec['filter_families']);nrows+=1
 assert nrows==m['packages'],('MISSING_SEMANTICS',ch,nrows)
 artifacts.append({'channel':ch,'manifest_sha256':artifact_sha,'manifest_bytes':mp.stat().st_size,'packages':nrows,'physical_mask_duplicates_cross_chunks':dups,'verified_artifacts':len(m['artifacts'])});refs+=len(m['routes']);channel_rows.append(nrows)
for side in SIDE_SHA:
 assert set(seen[side])==set(range(11176)),('MISSING_CONFIG_INDEX',side)
 h=hashlib.sha256()
 for i in range(11176):h.update(bytes.fromhex(seen[side][i]))
 assert h.hexdigest()==SIDE_SHA[side],('ORIGINAL_PREREG_ID_STREAM_DRIFT',side,h.hexdigest())
h=hashlib.sha256()
for side in ['BUY','SELL']:
 for i in range(11176):h.update(bytes.fromhex(seen[side][i]))
assert h.hexdigest()=='bb1e97c99fc1eb3c1acab53f77232c00fae61feafb5b8b63941c1e68e0e53b75'
assert fam=={'BREAKOUT_BUFFER','EMA_CROSS_RECENCY','GEOMETRY','MOMENTUM','MULTI_TF','RETEST_ENTRY','SESSION','TREND','TREND_STRENGTH','VOLATILITY'}
r={'schema':'QROS_W5_V27_INDEPENDENT_EXACT_10F_BYTE_AND_ID_CLOSURE_V1','status':'PASS','semantic_configs_total':sum(channel_rows),'semantic_per_side':{k:len(v) for k,v in seen.items()},'expected_full_original_ID_stream_SHA256':h.hexdigest(),'all_ten_original_families':sorted(fam),'verified_source_route_mask_shards':refs,'unique_physical_masks_across_all_routes':len(phys),'channel_manifests':artifacts,'PnL_read':False,'holdout_open':False,'GA2_open':False,'broker_commission_certified':False,'next':'EXPLORATORY_ONLY_PRE_ECON_PROFILE_FREEZE_AND_CHUNKED_REAL_DEV_TRADES'}
out=R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json';atom(out,r)
print(json.dumps({'result':'PASS_INDEPENDENT_22352_CONFIGS_10F_MASKS','semantic':sum(channel_rows),'physical':len(phys),'routes':refs,'receipt_sha256':sha(out),'channels':channel_rows,'family_coverage':sorted(fam)}))
