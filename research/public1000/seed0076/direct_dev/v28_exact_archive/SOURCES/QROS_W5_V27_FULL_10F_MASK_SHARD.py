#!/usr/bin/env python3
"""QROS W5 2026-09-24: pre-economic 10-family masks by frozen V209 identity.
Processes exactly one of 8 independent (side, ATR buffer) shards; all outputs
are atomic. No execution, PnL, OOS, selection or Gate A performed here.
"""
from __future__ import annotations
import os,sys,json,hashlib,argparse,time,io
from pathlib import Path
from collections import defaultdict
import numpy as np
R=Path(__file__).resolve().parent;P=Path('/mnt/data/qros_nonstall_v23/work/legacy/source_pins');sys.path[:0]=[str(P),str(R),'/mnt/data/qros_nonstall_v23/work']
from qros_seed0076_config_stream import canonical,filter_packages
import qros_seed0076_gate_engine_v221 as gate
from qros_w5_mtf_causal_adapter_v1 import causal_gate_context_class
from frozen_structural import structural_states,box_history4
SPECPIN='c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf';PINBLOB={'qros_seed0076_config_stream.py':'a01268bd8bab639977b22c419926d94306754bba','qros_seed0076_gate_engine_v221.py':'74290f11e7a95a25f54c5c9989af110de7dde4e2','qros_seed0076_structural_v220.py':'805044c9918a87456a95e150a1c9a1292112cf4c','QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json':SPECPIN}
SHA={'XAUUSD_M1_VALID_BID_BARS_V24.npy':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13','XAUUSD_M1_VALID_INDICATORS_V24.npz':'8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6','W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz':'8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0'}
BUFF={0:None,1:'0.05',2:'0.10',3:'0.25'};MODES={(0,1):None,(1,1):('1','TOUCH_RECLAIM'),(1,3):('3','TOUCH_RECLAIM'),(1,5):('5','TOUCH_RECLAIM'),(2,1):('1','CLOSE_RECLAIM'),(2,3):('3','CLOSE_RECLAIM'),(2,5):('5','CLOSE_RECLAIM')}
PIN_IDS={'BUY':'0dbaf56a5a8f0b1fce3b4c92fc44f0fc6146a237e9f23eaf6da75e4be82eecb5','SELL':'d2a130f42f4ab077437fe237363b863bf49c3631c2b9e482aa2121d93c9cc47b'}
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for x in iter(lambda:f.read(8<<20),b''):h.update(x)
 return h.hexdigest()
def blob(path):
 b=path.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def atomic_json(obj,path):
 temp=path.with_suffix(path.suffix+'.partial');temp.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n');os.replace(temp,path)
def ensure_authority():
 for name,pin in PINBLOB.items():assert blob(P/name)==pin,('SOURCE_BLOB_DRIFT',name)
 for name,pin in SHA.items():assert sha(R/name)==pin,('REAL_SOURCE_DRIFT',name)
 a=json.loads((R/'V26_ALL_56_FULL_REAL_STATEFUL_RETEST_INDEPENDENT_AUDIT.json').read_text());assert len(a['per_route_receipts'])==56 and a['new_W5_PnL']=='NOT_RUN'
 for rec in a['per_route_receipts']:
  p=R/rec['filename'];assert sha(p)==rec['receipt_sha256']
 progress=json.loads((R/'V26_MATERIALIZATION_PROGRESS.json').read_text());assert len(progress['verified_artifacts'])==8
 for rec in progress['verified_artifacts']:assert sha(R/rec['path'])==rec['sha256']
 return a

def load_context(side):
 # Route only to quote-validated caches; do not modify frozen V221 code.
 cv=R/'V27_VALID_CONTEXT_SYMLINKS';cv.mkdir(exist_ok=True)
 for tf in ('M1','M5','M15'):
  for suffix,src in [('BID_BARS.npy',R/f'XAUUSD_{tf}_VALID_BID_BARS_V24.npy'),('INDICATORS.npz',R/f'XAUUSD_{tf}_VALID_INDICATORS_V24.npz')]:
   dst=cv/f'XAUUSD_{tf}_{suffix}'
   if dst.is_symlink():assert dst.resolve()==src.resolve()
   elif dst.exists():assert sha(dst)==sha(src)
   else:dst.symlink_to(src)
 C=causal_gate_context_class(gate)
 return C('XAUUSD','M1',side,cv,cv,.01)

def get_route(p):
 buf=p.get('BREAKOUT_BUFFER');channel=0 if buf is None else int({'0.05':1,'0.10':2,'0.25':3}[buf['buffer_atr']])
 ret=p.get('RETEST_ENTRY');mode,window=(0,1) if ret is None else ((1 if ret['confirmation']=='TOUCH_RECLAIM' else 2),int(ret['window_bars']))
 return channel,mode,window

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--channel',type=int,required=True,choices=range(8));ap.add_argument('--force',action='store_true');ap.add_argument('--max-new-shards',type=int,default=0);a=ap.parse_args();ch=a.channel;side='BUY' if ch<4 else 'SELL';bufnum=ch%4;start=time.monotonic();output=R/f'V27_FULL10_PRE_ECON_CH{ch}';output.mkdir(exist_ok=True)
 final=output/'ALL_ROUTES_MANIFEST.json'
 if final.exists() and not a.force:
  j=json.loads(final.read_text());assert j['side']==side and j['channel']==ch
  for z in j['artifacts']:assert sha(output/z['name'])==z['sha256'],('CHUNK_HASH_DRIFT',z['name'])
  print(json.dumps({'channel':ch,'status':'SKIPPED_PRIOR_FULL_SHARD_SHA_VERIFIED','packages':j['packages']}),flush=True);return
 ensure_authority()
 spec=json.loads((P/'QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json').read_text());fps=filter_packages(spec);assert len(fps)==11176
 base=dict(asset='XAUUSD',side=side,timeframe='M1',fractal_window=5,tie_policy='SOURCE_ASYMMETRIC',rearm_mode='RETURN_INSIDE_OR_LEVEL_REPLACED',trigger='TICK_BREAK')
 all_id=hashlib.sha256();all_cfg=[]
 for p in fps:
  digest=hashlib.sha256(canonical({**base,'filters':p})).digest();all_id.update(digest);all_cfg.append(digest.hex())
 assert all_id.hexdigest()==PIN_IDS[side],('CONFIG_STREAM_DRIFT',all_id.hexdigest());assert len(set(all_cfg))==11176
 ctx=load_context(side);bars=ctx.bars;ind=ctx.ind
 sh,sl,hid,lid=structural_states(bars['high_bid'].astype(float)*.01,bars['low_bid'].astype(float)*.01,5,0);box=box_history4(sh,sl,hid,lid)
 tapes=np.load(R/f'W5_V27_EXECUTABLE_CANDIDATES_CH{ch}.npz')
 raw=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=[('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')],mode='r')
 expected_prefix='r';byroute=defaultdict(list)
 for i,p in enumerate(fps):
  channel,mode,window=get_route(p)
  if channel==bufnum:byroute[(mode,window)].append((i,p))
 assert sum(len(v) for v in byroute.values())>0
 artifacts=[];total=0;families=set();checked=0;manifest_routes=[];new_shards=0
 # Deterministic pre-economic batches of 400 packages; one SHA-pinned route artifact per batch.
 work=[]
 for mode,win in sorted(byroute):
  pair0=byroute[(mode,win)]
  if len(pair0)>400:
   for start_idx in range(0,len(pair0),400):work.append((mode,win,start_idx//400,pair0[start_idx:start_idx+400]))
  else:work.append((mode,win,-1,pair0))
 for mode,win,segment,pair in work:
  basekey=f'r{mode}_w{win}';routekey=basekey if segment<0 else f'{basekey}_batch{segment:03d}';si=tapes[basekey+'_source_idx'];bi=tapes[basekey+'_bar'];n=len(si)
  assert n==len(bi) and np.all(bi>=0) and np.all(bi<len(bars))
  assert np.all(si>=bars['first_source_index'][bi]) and np.all(si<=bars['last_source_index'][bi]),('NON_CAUSAL_BAR_ID',ch,routekey)
  tm=raw['ts'][si].copy();valid=(raw['ask'][si]>raw['bid'][si])&(raw['ask'][si]>0)&(raw['bid'][si]>0)
  assert bool(np.all(valid)),('INVALID_QUOTE_CANDIDATE',ch,routekey)
  sihash=hashlib.sha256(np.stack([si,bi.astype(np.int64)],axis=1).tobytes()).hexdigest()
  v27=json.loads((R/f'V27_EXECUTABLE_CANDIDATE_CH{ch}.json').read_bytes());ref=next(a for a in v27['routes'] if a['route']==basekey);assert sihash==ref['root_sha256']
  rp=output/f'{routekey}_RECEIPT.json'
  if rp.exists():
   old=json.loads(rp.read_text());assert old['route']==routekey and old['candidate_root_sha256']==sihash and old['packages']==len(pair),('FROZEN_PARTIAL_ROUTE_DRIFT',ch,routekey)
   for o in old['artifacts']:assert sha(output/o['name'])==o['sha256'],('FROZEN_PARTIAL_ARTIFACT_DRIFT',ch,o)
   artifacts.extend([{'name':o['name'],'bytes':o['bytes'],'sha256':o['sha256']} for o in old['artifacts']]);artifacts.append({'name':rp.name,'bytes':rp.stat().st_size,'sha256':sha(rp)})
   manifest_routes.append({'route':routekey,'packages':len(pair),'physical_masks':old['physical_masks'],'candidates':n,'candidate_root':sihash,'independent_gate_canaries_pass':old['independent_V221_canaries_pass']})
   total+=len(pair);checked+=old['independent_V221_canaries_pass'];families.update(f for _,p in pair for f in p)
   print(json.dumps({'channel':ch,'route':routekey,'status':'SKIP_FROZEN_EXISTING_SHA_AND_V27_ROOT_VERIFIED','packages':len(pair)}),flush=True)
   continue
  cache={};masks=[];ident={};semantic=[];phys=[];canaries=0
  # Fixed prospective canary set: stride on original global package stream + earliest family representatives.
  spots=set(np.linspace(0,len(fps)-1,128,dtype=np.int32).tolist())
  for family in spec['filter_families']:
   spots.add(next(i for i,p in enumerate(fps) if family in p))
  spots.add(pair[0][0]);spots.add(pair[-1][0])
  def pred(fam,var,trend):
   k=(fam,canonical(var),canonical(trend) if trend is not None and fam in ('GEOMETRY','MULTI_TF','EMA_CROSS_RECENCY') else b'')
   if k not in cache:
    v=ctx.eval_family(fam,var,si,bi,sh,sl,box,trend if fam in ('GEOMETRY','MULTI_TF','EMA_CROSS_RECENCY') else None,tm)
    assert v.shape==(n,),(fam,v.shape,n)
    cache[k]=np.asarray(v,dtype=bool)
   return cache[k]
  for idx,pkg in pair:
   gates={k:v for k,v in pkg.items() if k not in ('BREAKOUT_BUFFER','RETEST_ENTRY')}
   bits=np.ones(n,dtype=bool);trend=gates.get('TREND')
   for fam in sorted(gates):bits &= pred(fam,gates[fam],trend)
   if idx in spots:
    oracle=ctx.eval_gates(gates,si,bi,sh,sl,box,tm)
    assert np.array_equal(bits,oracle),('INDEPENDENT_FROZEN_V221_GATE_ORACLE_MISMATCH',side,ch,routekey,idx)
    canaries+=1
   packed=np.packbits(bits,bitorder='little');pid=hashlib.sha256(b'QROS_W5_V27_FULL10_PHYSMASK\0'+side.encode()+b'\0'+sihash.encode()+b'\0'+packed.tobytes()).hexdigest()
   if pid not in ident:
    ident[pid]=len(masks);masks.append(packed)
    phys.append({'physical_mask_id':pid,'route':routekey,'physical_index':len(masks)-1,'candidate_count':n,'accepted_signal_count':int(bits.sum()),'candidate_root_sha256':sihash})
   else:assert np.array_equal(masks[ident[pid]],packed)
   semantic.append({'config_index':idx,'config_id':all_cfg[idx],'physical_mask_id':pid,'filter_families':sorted(pkg),'signal_count':int(bits.sum()),'route':routekey,'source_provenance':'EXPOSED_DEV_NO_PNL'})
   families.update(pkg)
  masks=np.stack(masks) if masks else np.empty((0,(n+7)//8),np.uint8)
  # No overwrites of previously verified route artifacts.
  mp=output/f'{routekey}_PHYSICAL_MASKS.npz';sp=output/f'{routekey}_SEMANTIC.jsonl';pp=output/f'{routekey}_PHYSICAL.jsonl'
  if mp.exists() or sp.exists() or pp.exists():raise RuntimeError('UNRECONCILED_PARTIAL_OUTPUT_CHECK_BECAME_VERIFIED')
  f=mp.with_suffix('.npz.partial');
  with f.open('wb') as out:np.savez_compressed(out,masks=masks,mask_ids=np.asarray([p['physical_mask_id'] for p in phys],dtype='<U64'),candidate_root_sha256=sihash)
  os.replace(f,mp)
  for path,rows in [(sp,semantic),(pp,phys)]:
   tmp=path.with_suffix(path.suffix+'.partial')
   with tmp.open('w') as out:
    for row in rows:out.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
    out.flush();os.fsync(out.fileno())
   os.replace(tmp,path)
  receipt={'schema':'QROS_W5_V27_EXACT_10F_FILTER_MASK_ONE_ROUTE_V1','channel':ch,'side':side,'route':routekey,'packages':len(pair),'physical_masks':len(phys),'raw_candidates':n,'frozen_V209_config_ID_stream_SHA256':all_id.hexdigest(),'candidate_root_sha256':sihash,'frozen_V26_source_receipt_sha256':sha(R/f'V26_REAL_FULL_STATEFUL_CH{ch}_RETEST{mode}_WINDOW{win}.json'),'v27_corrected_executable_route_root_sha256':sihash,'v27_corrected_executable_source_SHA256':v27['source_correction_sha256'],'independent_V221_canaries_pass':canaries,'artifacts':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in [mp,sp,pp]],'holdout_open':False,'GA2_open':False,'PnL_read':False,'economic_results':'NOT_RUN','broker_cost_certified':False}
  rp=output/f'{routekey}_RECEIPT.json';atomic_json(receipt,rp)
  for x in [mp,sp,pp,rp]:artifacts.append({'name':x.name,'bytes':x.stat().st_size,'sha256':sha(x)})
  manifest_routes.append({'route':routekey,'packages':len(pair),'physical_masks':len(phys),'candidates':n,'candidate_root':sihash,'independent_gate_canaries_pass':canaries})
  total+=len(pair);checked+=canaries
  atomic_json({'schema':'QROS_W5_V27_PROGRESS','channel':ch,'side':side,'completed_packages':total,'routes':manifest_routes,'verified_artifacts':artifacts,'sequence':len(manifest_routes),'root_prereg_config_ID_SHA256':all_id.hexdigest()},output/'PROGRESS.json')
  new_shards+=1
  print(json.dumps({'channel':ch,'route':routekey,'packages':len(pair),'physical_masks':len(phys),'candidates':n,'gate_canaries':canaries,'seconds':round(time.monotonic()-start,2),'status':'ROUTE_SHA_VERIFIED'}),flush=True)
  if a.max_new_shards and new_shards>=a.max_new_shards:
   print(json.dumps({'channel':ch,'status':'PARTIAL_VERIFIED_CHECKPOINT_BOUND','new_shards':new_shards,'processed_packages':total,'seconds':round(time.monotonic()-start,2)}),flush=True);return
 # Final manifest written only after complete coverage in this channel.
 assert total==sum(len(v) for v in byroute.values()),('INCOMPLETE_FILTER_ROUTE_COVERAGE',ch,total)
 j={'schema':'QROS_W5_V27_FULL10_PRE_ECON_ONE_CHANNEL_MANIFEST','status':'PASS_ALL_7_BASE_ROUTES_BOUNDED_BATCHES','side':side,'channel':ch,'packages':total,'family_coverage':sorted(families),'routes':manifest_routes,'artifacts':artifacts,'batch_size':400,'source_code_sha256':sha(Path(__file__)),'frozen_spec_git_blob_SHA1':SPECPIN,'full_side_config_stream_SHA256':all_id.hexdigest(),'canaries_pass':checked,'raw_tick_sha256_pin':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','source_v26_checks':56,'source_v27_corrected_full_channel_root_SHA256':v27['archive_sha256'],'PnL_read':False,'holdout_open':False,'GA2_open':False,'broker_cost_certified':False,'seconds':round(time.monotonic()-start,2)}
 atomic_json(j,final)
 print(json.dumps({'channel':ch,'status':'PASS_CHANNEL_COMPLETE','packages':total,'routes':len(manifest_routes),'canaries':checked,'seconds':j['seconds'],'manifest_SHA256':sha(final)}),flush=True)
if __name__=='__main__':main()
