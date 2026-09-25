#!/usr/bin/env python3
"""QROS SEED0076 W5 full-V209 PRE-ECONOMIC ONLY oracle.
No PnL; never claims actual Darwinex-data parity from synthetic fixtures.
Requires exact sha-pinned frozen V209/V220/V221 and official prereg before tests.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys, importlib.util
import numpy as np

HERE=pathlib.Path(__file__).resolve().parent
SOURCES=HERE/'legacy'/'source_pins'
V209=HERE/'v209'
PINS={
 'QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json':'c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf',
 'qros_seed0076_structural_v220.py':'805044c9918a87456a95e150a1c9a1292112cf4c',
 'qros_seed0076_gate_engine_v221.py':'74290f11e7a95a25f54c5c9989af110de7dde4e2',
 'qros_seed0076_config_stream.py':'a01268bd8bab639977b22c419926d94306754bba'}
EXPECTED={'spec':5291,'full_packages':11176,'config_ids':22352,'filter_root':'3c0dfe0adf69c2fd0e82f36df15fc3a0537cb0a90646008b2f7a95408394e5e9',
 'combined_id_root':'bb1e97c99fc1eb3c1acab53f77232c00fae61feafb5b8b63941c1e68e0e53b75'}
def sha(raw): return hashlib.sha256(raw).hexdigest()
def filehash(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def loadmodule(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def check_source():
 pins={}
 for name,pin in PINS.items():
  # Config stream is intentionally re-read from original W13 frozen source path
  p=SOURCES/name;raw=p.read_bytes();assert blob(raw)==pin,('PIN_MISMATCH',name)
  pins[name]={'git_blob_sha1':pin,'bytes':len(raw),'sha256':sha(raw)}
 prereg=json.loads((V209/'PREREG_W5_ASYM_REARM0_TICK_FULL_V209.json').read_bytes());assert prereg['scientific_state']=='PREREGISTERED_NO_RESULTS' and prereg['window']==5 and prereg['trigger']=='TICK_BREAK'
 assert not prereg['scientific_firewalls']['holdout_open'] and not prereg['scientific_firewalls']['GA2_open']
 return pins,prereg

def oracle_fractal(high,low,w=5):
 n=len(high);sh=np.full(n,np.nan);sl=np.full(n,np.nan);hi=np.full(n,-1,np.int64);li=np.full(n,-1,np.int64)
 for i in range(1,n):
  if i>=w:
   p=i-1-w//2;old=range(i-w,p);new=range(p+1,i)
   if all(high[p]>=high[q] for q in old) and all(high[p]>high[q] for q in new):sh[i]=high[p];hi[i]=p
   if all(low[p]<=low[q] for q in old) and all(low[p]<low[q] for q in new):sl[i]=low[p];li[i]=p
  if i>1:
   if hi[i]<0:hi[i]=hi[i-1];sh[i]=sh[i-1]
   if li[i]<0:li[i]=li[i-1];sl[i]=sl[i-1]
 return sh,sl,hi,li

def valid_quote(bid,ask):return (bid>0)&(ask>bid)
def guarded_raw_oracle(bid,ask,first,last,levels,level_id,atr_prev,side,point,buffers=(0.,.05,.10,.25)):
 """Independent causal reference with invalid/zero/crossed quotes removed entirely."""
 good=valid_quote(bid,ask);events=[[] for _ in buffers];previous=None
 for bi,(s,e) in enumerate(zip(first,last)):
  lv=levels[bi];atr=atr_prev[bi]
  for j in range(int(s),int(e)+1):
   if not good[j]:continue
   cur=int(bid[j])*point
   if previous is not None and np.isfinite(lv):
    for z,mult in enumerate(buffers):
     if mult!=0 and not np.isfinite(atr):continue
     threshold=lv+ (mult*atr if side==1 else -mult*atr)
     if (side==1 and previous<=threshold<cur) or (side==-1 and previous>=threshold>cur):events[z].append((j,bi,int(level_id[bi])))
   previous=cur
 return events

def original_compatible_raw_oracle(bid,first,last,bar_h,bar_l,level,lid,atr,side,point,buffers):
 """Second implementation of *original* V220 raw tape for all-valid quotes."""
 outs=[[] for _ in buffers]
 for bi in range(len(first)):
  for k in range(int(first[bi]),int(last[bi])+1):
   prev=int(bid[k-1])*point if k>0 else int(bid[k])*point;cur=int(bid[k])*point
   for z,b in enumerate(buffers):
    if not np.isfinite(level[bi]) or (b and not np.isfinite(atr[bi])):continue
    th=level[bi]+b*atr[bi]*(1 if side==1 else -1)
    if (side==1 and prev<=th<cur) or (side==-1 and prev>=th>cur):outs[z].append((k,bi,int(lid[bi])))
 return outs

def replacement_oracle(lid,first):
 out=np.full(len(lid),-1,np.int64)
 for i in range(len(lid)):
  for j in range(i+1,len(lid)):
   if lid[j]!=lid[i]:out[i]=first[j];break
 return out

def online_rearm_oracle(bid,first,last,levels,lids,raw,side,point):
 """Independent chronological rearm0 FSM, strictly later tick return or replacement."""
 emitted=[];consumed=None;armed=True;old_level=None;pos=0
 rows=sorted(raw);events_by_tick={i:(i,b,l) for i,b,l in rows}
 for bi in range(len(first)):
  lid=int(lids[bi])
  if consumed is not None and lid!=consumed:armed=True
  for j in range(int(first[bi]),int(last[bi])+1):
   if consumed is not None and not armed and old_level is not None:
    px=int(bid[j])*point
    if (side==1 and px<=old_level) or (side==-1 and px>=old_level):armed=True
   if j in events_by_tick:
    event=events_by_tick[j]
    if consumed!=lid or armed:
     emitted.append((j,bi));consumed=lid;old_level=float(levels[bi]);armed=False
 return emitted

def valid_tick_tests(structural):
 rng=np.random.default_rng(7605);N=90;K=5;first=np.arange(N,dtype=np.int64)*K;last=first+K-1
 x=np.zeros((N,K),dtype=np.int32);x[0]=[10100,10101,10104,10102,10103]
 for i in range(1,N):
  anchor=int(x[i-1,-1])+int(rng.integers(-11,12));x[i]=anchor+rng.integers(-17,18,size=K,dtype=np.int32)
 # Tie adversarial fixture: equal highs of neighboring bars, strict right inequality
 x[30,1]=max(int(x[28].max()),int(x[29].max()),int(x[30].max()),int(x[31].max()))+4
 x[31,1]=x[30,1]
 bid=x.ravel();ask=bid+2;high=x.max(axis=1).astype(float);low=x.min(axis=1).astype(float)
 sh,sl,hi,li=structural.structural_states(high,low,5,0)
 a=oracle_fractal(high,low)
 for k,(o,v) in enumerate(zip((sh,sl,hi,li),a)):
  assert np.array_equal(o,v,equal_nan=True),('FRACTAL_ORACLE',k)
 # Future mutation must not change availability of prior confirmed states.
 for end in (9,25,50,70):
  h2,l2=high[:end].copy(),low[:end].copy()
  o=structural.structural_states(h2,l2,5,0)
  assert all(np.array_equal(x[:end],y,equal_nan=True) for x,y in zip((sh,sl,hi,li),o))
 atr=np.full(N,10.,np.float64);atr[:5]=np.nan
 buffers=np.array([0.,.05,.10,.25])
 for side,lv,lid in ((1,sh,hi),(-1,sl,li)):
  counters,orig=structural.raw_tick_crosses_four(bid,first,last,high,low,lv,lid,atr,side,1.,buffers)
  ref=original_compatible_raw_oracle(bid,first,last,high,low,lv,lid,atr,side,1.,buffers)
  assert any(ref[0]),'SYNTHETIC_NO_RAW_EVENTS'
  for z,rows in enumerate(ref):
   observed=list(zip(orig[z][0].tolist(),orig[z][1].tolist(),orig[z][2].tolist()))
   assert int(counters[z])==len(rows) and observed==rows,('RAW_TICK_ORACLE',side,z)
  replacement=structural.next_replacement_source(lid,first)
  independent_replacement=replacement_oracle(lid,first)
  assert np.array_equal(replacement,independent_replacement)
  idx,bar,rawlid=orig[0]
  got=structural.filter_raw_to_candidates(bid,first,last,low,high,np.asarray(x[:,-1],float),lv,lid,replacement,atr,idx,bar,rawlid,np.array([],np.int64),side,1.,0.,0,0,1)
  expected=online_rearm_oracle(bid,first,last,lv,lid,ref[0],side,1.)
  observed=list(zip(got[0].tolist(),got[1].tolist()))
  assert observed==expected,('REARM_PARITY',side,observed[:8],expected[:8])
  # Inject invalid quotes into a known event and verify event is excluded.
  ix=ref[0][0][0];badask=ask.copy();badask[ix]=bid[ix]
  guarded=guarded_raw_oracle(bid,badask,first,last,lv,lid,atr,side,1.,buffers)
  assert ix not in [e[0] for e in guarded[0]],('BAD_QUOTE_EVENT_ACCEPTED',side)
  assert len(guarded_raw_oracle(bid,ask,first,last,lv,lid,atr,side,1.,buffers)[0])==len(ref[0])
  crossed=ask.copy();crossed[ix]=bid[ix]-1
  assert ix not in [e[0] for e in guarded_raw_oracle(bid,crossed,first,last,lv,lid,atr,side,1.,buffers)[0]]
 return {'structural_prefixes':4,'raw_buffers_per_side':4,'rearm_buy_sell':'PASS','zero_and_crossed_spread_exclusions':'PASS','synthetic_bars':N,'synthetic_ticks':N*K}

def check_mtf(gates):
 dtype=np.dtype([('first_source_index','<i8')]);bars=np.array([(10,),(60,),(115,),(170,)],dtype=dtype)
 source=np.array([9,10,59,60,114,115,169,170,171],np.int64)
 old=gates.mtf_context_index(bars,source)
 # Correct availability: bar j completes at first tick of bar j+1 (inclusive).
 comp=bars['first_source_index'][1:]
 corrected=np.searchsorted(comp,source,side='right')-1
 assert np.all(corrected<=np.maximum(-1,np.searchsorted(comp,source,side='right')-1))
 assert corrected.tolist()==[-1,-1,-1,0,0,1,1,2,2]
 # On boundary old V221 side='left' conservatively lags one bar; do not treat it as accurate current-context parity.
 assert int(old[3])==-1 and int(corrected[3])==0
 return {'original_v221_mtf_at_exact_completion':'ONE_COMPLETED_BAR_LATE','corrected_closed_bar_boundary':'PASS','no_lookahead':'PASS','needs_corrected_adapter_before_economic_run':True}

def verify_ids():
 spec=json.loads((V209/'FROZEN_ORIGINAL_V209_SPEC.json').read_bytes())
 from importlib.util import spec_from_file_location,module_from_spec
 m=loadmodule('original_config_stream',SOURCES/'qros_seed0076_config_stream.py');fp=m.filter_packages(spec)
 assert len(fp)==EXPECTED['full_packages'];root=sha(b''.join(bytes.fromhex(sha(canonical(x))) for x in fp))
 assert root==EXPECTED['filter_root']
 allids=[];ids_by_side={}
 for side in ('BUY','SELL'):
  base={'asset':'XAUUSD','side':side,'timeframe':'M1','fractal_window':5,'tie_policy':'SOURCE_ASYMMETRIC','rearm_mode':'RETURN_INSIDE_OR_LEVEL_REPLACED','trigger':'TICK_BREAK'}
  b=b''.join(hashlib.sha256(m.config_bytes(base,f)).digest() for f in fp)
  archive_ids=(V209/(side+'_CONFIG_IDS_11176.bin')).read_bytes();assert b==archive_ids
  ids_by_side[side]=len(b)//32;allids.append(b)
 assert sha(b''.join(allids))==EXPECTED['combined_id_root'];return {'packages_each_side':len(fp),'ids_each_side':ids_by_side,'combined_root':EXPECTED['combined_id_root']}

def audit():
 pins,p=check_source(); s=loadmodule('frozen_structural',SOURCES/'qros_seed0076_structural_v220.py');g=loadmodule('frozen_gates',SOURCES/'qros_seed0076_gate_engine_v221.py')
 proofs={'source_pins':pins,'fractal_tick_rearm':valid_tick_tests(s),'mtf_boundary':check_mtf(g),'canonical':verify_ids(),
 'unverified_real_data':True,'synthetic_not_historical':True,'holdout_open':False,'ga2_open':False,
 'full_10_family_live_filter_trade_parity':'PENDING_REAL_DATA','W5_economic_results':'NOT_RUN'}
 return proofs

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
 proof=audit();out=pathlib.Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 body={'schema':'QROS_W5_PRE_ECON_SYNTHETIC_SOURCE_AND_CAUSAL_FIXTURE_V1','status':'PASS_SYNTHETIC_ONLY','campaign':'QROS_WEB_SEED0076_XAUUSD_M1_W5_ASYM_REARM0_TICK_FULL_V209_20260924','proof':proof}
 out.write_bytes(json.dumps(body,indent=2,sort_keys=True,ensure_ascii=False).encode()+b'\n');print(json.dumps({'status':body['status'],'fixture':proof['fractal_tick_rearm'],'mtf':proof['mtf_boundary'],'config':proof['canonical']},sort_keys=True))
if __name__=='__main__': main()
