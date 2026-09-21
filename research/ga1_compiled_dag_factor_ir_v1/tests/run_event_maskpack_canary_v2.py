from __future__ import annotations
import hashlib, json, struct, tempfile
from pathlib import Path
import numpy as np, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_independent_event_canary import structural_states_scalar,structural_states_by_centers,tick_crosses_scalar,tick_crosses_alt
from qros_maskpack_regression import MAGIC,PACK_HDR,INDEX_REC,MAP_REC,canonical,verify_maskpack

rng=np.random.default_rng(760076)
struct_cases=0
for n in [40,101]:
  for w in [3,5,7,9,11,13]:
    for tie in [0,1]:
      h=np.cumsum(rng.normal(size=n));l=h-rng.uniform(.1,2,n)
      if n>20:h[10]=h[9];l[20]=l[19]
      a=structural_states_scalar(h,l,w,tie);b=structural_states_by_centers(h,l,w,tie)
      for x,y in zip(a,b):
        if np.issubdtype(x.dtype,np.floating):
          if not np.array_equal(x,y,equal_nan=True):raise SystemExit(f'STRUCT_MISMATCH:{n}:{w}:{tie}')
        elif not np.array_equal(x,y):raise SystemExit(f'STRUCT_MISMATCH:{n}:{w}:{tie}')
      struct_cases+=1
nb=50;per=7;nt=nb*per
first=np.arange(0,nt,per,dtype=np.int64);last=first+per-1
price=np.cumsum(rng.integers(-3,4,nt,dtype=np.int64))+10000
point=.01
bh=np.array([price[s:e+1].max()*point for s,e in zip(first,last)]);bl=np.array([price[s:e+1].min()*point for s,e in zip(first,last)])
level=np.linspace(99.5,101.5,nb);lid=np.arange(nb,dtype=np.int64);atr=np.linspace(.2,1.2,nb);atr[3]=np.nan
for side in [1,-1]:
  a=tick_crosses_scalar(price,first,last,bh,bl,level,lid,atr,side,point);b=tick_crosses_alt(price,first,last,bh,bl,level,lid,atr,side,point)
  if a!=b:raise SystemExit('TICK_CROSS_MISMATCH')
cut_bar=25;cut_tick=int(last[cut_bar]);base=tick_crosses_scalar(price,first,last,bh,bl,level,lid,atr,1,point)
price2=price.copy();price2[cut_tick+1:]+=rng.integers(-500,500,len(price2)-cut_tick-1)
bh2=bh.copy();bl2=bl.copy()
for bi in range(cut_bar+1,nb):
 s,e=first[bi],last[bi];bh2[bi]=price2[s:e+1].max()*point;bl2[bi]=price2[s:e+1].min()*point
alt=tick_crosses_scalar(price2,first,last,bh2,bl2,level,lid,atr,1,point)
for z in range(4):
  if [x for x in base[z] if x[0]<=cut_tick] != [x for x in alt[z] if x[0]<=cut_tick]:raise SystemExit('EVENT_FUTURE_PERTURBATION')
domain={'asset':'NQX','side':'BUY','timeframe':'M2'}
classes=[np.array([],dtype=np.uint64),np.array([2,5,9],dtype=np.uint64)]
rows=[];cfgs=[]
for i,ids in enumerate(classes):
 raw=ids.astype('<u8').tobytes();ch=hashlib.sha256(canonical(domain)+b'\0'+raw).digest();class_cfgs=[hashlib.sha256(b'cfg'+bytes([i,j])).digest() for j in range(2)];rep=min(class_cfgs);delta=np.diff(np.r_[np.uint64(0),ids]).astype('<u4').tobytes() if len(ids) else b'';masksha=hashlib.sha256(raw).digest();rows.append((ch,rep,2,len(ids),delta,masksha));cfgs.extend((c,ch) for c in class_cfgs)
rows.sort(key=lambda x:x[0])
with tempfile.TemporaryDirectory() as td:
 td=Path(td);pack=td/'m.maskpack';idx=td/'m.index';mp=td/'m.map'
 with pack.open('wb') as pf,idx.open('wb') as ix:
  pf.write(MAGIC)
  for ch,rep,ac,ec,delta,masksha in rows:
   off=pf.tell();pf.write(PACK_HDR.pack(ch,rep,ac,ec,len(delta)));pf.write(delta);ix.write(INDEX_REC.pack(ch,off,rep,ac,ec,len(delta),masksha))
 cfgs.sort(key=lambda x:x[0]);mp.write_bytes(b''.join(MAP_REC.pack(c,ch) for c,ch in cfgs))
 ok=verify_maskpack(pack,idx,mp,domain=domain)
 if ok['processed_signal_configs']!=4 or ok['distinct_mask_class_count']!=2:raise SystemExit('MASKPACK_COUNTS')
 bad=bytearray(pack.read_bytes());bad[-1]^=1;(td/'bad.maskpack').write_bytes(bad)
 try:verify_maskpack(td/'bad.maskpack',idx,mp,domain=domain);raise SystemExit('MASKPACK_TAMPER_ACCEPTED')
 except ValueError:pass
 ib=bytearray(idx.read_bytes()); first_rec=list(INDEX_REC.unpack_from(ib,0)); first_rec[3]=first_rec[3]+1; ib[:INDEX_REC.size]=INDEX_REC.pack(*first_rec); (td/'bad.index').write_bytes(ib)
 try:verify_maskpack(pack,td/'bad.index',mp,domain=domain);raise SystemExit('MASKPACK_ALIAS_TAMPER_ACCEPTED')
 except ValueError:pass
print(json.dumps({'status':'PASS','structural_independent_cases':struct_cases,'tick_cross_independent_sides':2,'event_future_perturbation_pass':True,'maskpack_regression_fixture_pass':True,'maskpack_tamper_rejected':True,'maskpack_alias_metadata_tamper_rejected':True},sort_keys=True))
