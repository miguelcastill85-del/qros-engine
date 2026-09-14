from __future__ import annotations
import hashlib,json,zlib
import numpy as np
from qros_seed0076_gate_engine_v221 import GateContext

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def vkey(v):return canon(v)
class CarrierMaskEngine:
    def __init__(self,ctx:GateContext,source_idx,bar_idx,sh,sl,boxhist,session_server_ms=None):
        self.ctx=ctx;self.source_idx=np.asarray(source_idx,np.int64);self.bar_idx=np.asarray(bar_idx,np.int64);self.sh=sh;self.sl=sl;self.boxhist=boxhist;self.session_server_ms=None if session_server_ms is None else np.asarray(session_server_ms,np.int64);self.n=len(source_idx);self.cache={};self.full=np.packbits(np.ones(self.n,dtype=bool),bitorder='little')
    def _pack(self,b):return np.packbits(np.asarray(b,bool),bitorder='little')
    def family(self,fam,var,active_trend=None):
        dep=None
        if active_trend is not None:
            if fam=='GEOMETRY':dep=('FAST',int(active_trend['ema_triple'][0]))
            elif fam=='EMA_CROSS_RECENCY':dep=('PAIR',tuple(active_trend['ema_triple'][:2]))
            elif fam=='MULTI_TF' and var['rule'].endswith('TREND_ALIGN'):dep=('TREND',vkey(active_trend))
        key=(fam,vkey(var),dep)
        if key not in self.cache:
            b=self.ctx.eval_family(fam,var,self.source_idx,self.bar_idx,self.sh,self.sl,self.boxhist,active_trend if dep is not None else None,self.session_server_ms)
            self.cache[key]=self._pack(b)
        return self.cache[key]
    def package(self,gates):
        if not gates:return self.full
        trend=gates.get('TREND');parts=[]
        for fam in sorted(gates):parts.append(self.family(fam,gates[fam],trend if fam in ('GEOMETRY','MULTI_TF','EMA_CROSS_RECENCY') else None))
        out=parts[0].copy()
        for p in parts[1:]:np.bitwise_and(out,p,out=out)
        return out
    def selected_indices(self,packed):
        if self.n==0:return self.source_idx[:0]
        bits=np.unpackbits(packed,bitorder='little')[:self.n].astype(bool,copy=False);return self.source_idx[bits]
    def mask_digest(self,packed,domain_prefix=b''):
        ids=self.selected_indices(packed);h=hashlib.sha256();h.update(domain_prefix);h.update(ids.astype('<u8',copy=False).tobytes());return h.digest(),len(ids)

def group_packages_exact(engine, packages):
    groups={};rows=[]
    for i,g in packages:
        p=engine.package(g);h=hashlib.sha256(p.tobytes()).digest();z=zlib.compress(p.tobytes(),1)
        bucket=groups.get(h)
        if bucket is None:groups[h]=[(p.tobytes(),[i])]
        else:
            found=False
            for q,idxs in bucket:
                if q==p.tobytes():idxs.append(i);found=True;break
            if not found:bucket.append((p.tobytes(),[i]))
    for h,bucket in groups.items():
        for q,idxs in bucket:rows.append((h,q,idxs))
    return rows
