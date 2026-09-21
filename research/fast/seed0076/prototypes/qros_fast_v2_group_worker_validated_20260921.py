from __future__ import annotations
import sys,json,time,hashlib,struct,gc
from pathlib import Path
import numpy as np
sys.path.insert(0,'/mnt/data/qros_fast_v2/scripts');sys.path.insert(0,'/mnt/data/qros_fast_v2')
from qros_seed0076_config_stream import canonical,filter_packages,shard_base_rows
from qros_seed0076_structural_v220 import structural_states,box_history4,next_replacement_source,raw_close_crosses_four,filter_raw_to_candidates
from qros_seed0076_gate_engine_v221 import GateContext
from qros_seed0076_carrier_masks_v221 import CarrierMaskEngine
from fast_v2_engine import package_partition,channels,grouped,TIE_CODE,REARM_CODE,BUFFERS,session_ms,TICK_DTYPE,config_id
REC=struct.Struct('>32s32s32sII')
def main(gi):
 R=Path('/mnt/data/qros_fast_v2');od=R/'run_iso';od.mkdir(exist_ok=True);cf=open(od/f'g{gi:02d}.classes','wb');af=open(od/f'g{gi:02d}.aliases','wb');domain=canonical({'asset':'NQX','side':'BUY','timeframe':'M12'});spec=json.load(open(R/'research/machine_spec.json'));fps=filter_packages(spec);bases=shard_base_rows(spec,'NQX','BUY','M12');parts=package_partition(fps);groups={}
 for b in bases:groups.setdefault((b['fractal_window'],b['tie_policy'],b['trigger']),[]).append(b)
 ordered=sorted(groups.items(),key=lambda x:canonical({'fractal_window':x[0][0],'tie_policy':x[0][1],'trigger':x[0][2]}));(k,rows)=ordered[gi-1];w,tie,trigger=k
 ticks=np.memmap(R/'data/NQX_PACKED17_DEV_2018_2019.bin',dtype=TICK_DTYPE,mode='r');bars=np.load(R/'cache/bar/NQX_M12_BID_BARS.npy',mmap_mode='r',allow_pickle=False);z=np.load(R/'cache/ind/NQX_M12_INDICATORS.npz',allow_pickle=False);ind={k:z[k] for k in z.files};C=np.load(R/'cache/raw/NQX_M12_TICK_RAW_CACHE.npz',mmap_mode='r',allow_pickle=False);h=bars['high_bid'].astype(float)*.1;l=bars['low_bid'].astype(float)*.1;c=bars['close_bid'].astype(float)*.1;sh,sl,hid,lid=structural_states(h,l,int(w),TIE_CODE[tie]);box=box_history4(sh,sl,hid,lid);mapping={(11,'SOURCE_ASYMMETRIC'):0,(11,'STRICT_ALL_NEIGHBORS'):1,(13,'SOURCE_ASYMMETRIC'):2,(13,'STRICT_ALL_NEIGHBORS'):3,(3,'SOURCE_ASYMMETRIC'):4,(3,'STRICT_ALL_NEIGHBORS'):5,(5,'SOURCE_ASYMMETRIC'):6,(5,'STRICT_ALL_NEIGHBORS'):7,(7,'SOURCE_ASYMMETRIC'):8,(7,'STRICT_ALL_NEIGHBORS'):9,(9,'SOURCE_ASYMMETRIC'):10,(9,'STRICT_ALL_NEIGHBORS'):11};si=mapping[(int(w),tie)];first=bars['first_source_index'];last=bars['last_source_index'];level,lvlid=sh,hid;ol,olid=sl,lid
 if trigger=='TICK_BREAK':same=channels(C,'up',si);opp=channels(C,'down',si)
 else:
  _,outs,barsx,lids=raw_close_crosses_four(first,c,level,lvlid,ind['ATR14'],1);same=[(outs[i],barsx[i],lids[i]) for i in range(4)];_,oouts,obars,olids=raw_close_crosses_four(first,c,ol,olid,ind['ATR14'],-1);opp=[(oouts[i],obars[i],olids[i]) for i in range(4)]
 nr=next_replacement_source(lvlid,first);ap=np.r_[np.nan,ind['ATR14'][:-1]];row_by={b['rearm_mode']:b for b in rows};ctx=GateContext('NQX','M12','BUY',R/'cache/bar',R/'cache/ind',.1);aliases=0;occ=0;t0=time.time()
 for tkey,pkgrows in sorted(parts.items()):
  bm,rcode,rwin=tkey;bidx=BUFFERS.index(float(bm));raw_idx,raw_bar,raw_lid=same[bidx];opp_idx=opp[bidx][0];cand_by={}
  for rn,rc in REARM_CODE.items():cand_by[rn]=filter_raw_to_candidates(ticks['bid'],first,last,l,h,c,level,lvlid,nr,ap,raw_idx,raw_bar,raw_lid,opp_idx,1,.1,float(bm),rc,int(rcode),int(rwin))
  union=np.unique(np.concatenate([v[0] for v in cand_by.values()])) if any(len(v[0]) for v in cand_by.values()) else np.empty(0,np.int64);ubar=np.searchsorted(first,union,side='right')-1 if len(union) else np.empty(0,np.int64);mode='TICK' if (rcode==1 or (rcode==0 and trigger=='TICK_BREAK')) else 'CLOSE';sms=session_ms(ticks,bars,union,ubar,mode,'M12');eng=CarrierMaskEngine(ctx,union,ubar,sh,sl,box,sms);gg=grouped(eng,pkgrows);members={}
  for rn,(cand,_) in cand_by.items():
   m=np.zeros(len(union),bool)
   if len(cand):m[np.searchsorted(union,cand)]=True
   members[rn]=np.packbits(m,bitorder='little')
  for rn,base in row_by.items():
   mem=members[rn]
   for _,pb,pidxs in gg:
    sel=np.bitwise_and(np.frombuffer(pb,dtype=np.uint8),mem);ids=eng.selected_indices(sel);raw=np.asarray(ids,dtype='<u8').tobytes();ch=hashlib.sha256(domain+b'\0'+raw).digest();mh=hashlib.sha256(raw).digest();cfgs=[config_id(base,fps[i]) for i in pidxs];cf.write(REC.pack(ch,mh,min(cfgs),len(cfgs),len(ids)));af.write(b''.join(x+ch for x in cfgs));aliases+=len(cfgs);occ+=1
 cf.close();af.close();print(json.dumps({'group':gi,'key':k,'aliases':aliases,'occ':occ,'seconds':round(time.time()-t0,6)}))
if __name__=='__main__':main(int(sys.argv[1]))
