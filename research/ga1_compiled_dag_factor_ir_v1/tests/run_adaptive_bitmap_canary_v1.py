from __future__ import annotations
import hashlib,json,time
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qros_adaptive_bitmap as ab

rng=np.random.default_rng(7600764)
lengths=[0,1,7,8,9,11078,128538]
densities=[0.0,0.001,0.005,0.01,0.02,0.03,0.031,0.04,0.1,0.5,1.0]
roundtrips=sparse=dense=0
for n in lengths:
    for d in densities:
        k=min(n,int(round(n*d)))
        m=np.zeros(n,dtype=bool)
        if k:m[rng.choice(n,k,replace=False)]=True
        raw=ab.encode(m);meta=ab.inspect(raw);dec=ab.decode(raw)
        if not np.array_equal(m,dec):raise SystemExit('ROUNDTRIP_MISMATCH')
        expected_hash=hashlib.sha256(np.packbits(m,bitorder='little').tobytes()).hexdigest()
        if meta['canonical_sha256']!=expected_hash:raise SystemExit('CANONICAL_HASH_MISMATCH')
        expected='SPARSE_U32' if n<=np.iinfo(np.uint32).max and k*4 < (n+7)//8 else 'DENSE'
        if meta['codec']!=expected:raise SystemExit('CODEC_SELECTION_MISMATCH')
        roundtrips+=1;sparse+=int(meta['codec']=='SPARSE_U32');dense+=int(meta['codec']=='DENSE')

n=128538
source=np.arange(n,dtype=np.uint64)*3+11
m=np.zeros(n,dtype=bool);m[rng.choice(n,2500,replace=False)]=True
raw=ab.encode(m);dec=ab.decode(raw);domain=b'{"asset":"NQX","side":"BUY","timeframe":"M2"}'
h1=hashlib.sha256(domain+b'\0'+source[m].astype('<u8').tobytes()).hexdigest()
h2=hashlib.sha256(domain+b'\0'+source[dec].astype('<u8').tobytes()).hexdigest()
if h1!=h2:raise SystemExit('SEMANTIC_CLASS_HASH_CHANGED')

tamper_rejections=0;base=ab.encode(m)
for mutant in (base[:-1],base[:len(ab.MAGIC)]+bytes([9])+base[len(ab.MAGIC)+1:],base[:-1]+bytes([base[-1]^1])):
    try:ab.inspect(mutant);raise SystemExit('TAMPER_ACCEPTED')
    except ValueError:tamper_rejections+=1
m2=np.ones(9,dtype=bool);pad=bytearray(ab.encode(m2));pad[-1]|=0x80
try:ab.inspect(bytes(pad));raise SystemExit('NONCANONICAL_PADDING_ACCEPTED')
except ValueError:tamper_rejections+=1

bench={}
for n in (11078,128538):
    ds=[0.002]*40+[0.008]*40+[0.02]*40+[0.05]*40+[0.2]*25+[0.7]*15
    masks=[]
    for d in ds:
        k=int(n*d);mm=np.zeros(n,dtype=bool)
        if k:mm[rng.choice(n,k,replace=False)]=True
        masks.append(mm)
    t0=time.perf_counter();encoded=[ab.encode(x) for x in masks];enc=time.perf_counter()-t0
    t0=time.perf_counter();decoded=[ab.decode(x) for x in encoded];dec_t=time.perf_counter()-t0
    if not all(np.array_equal(a,b) for a,b in zip(masks,decoded)):raise SystemExit('BENCHMARK_ROUNDTRIP_MISMATCH')
    dense_payload=len(masks)*((n+7)//8)
    adaptive_payload=sum(ab.inspect(x)['payload_bytes'] for x in encoded)
    bench[str(n)]={'masks':len(masks),'dense_payload_bytes':dense_payload,'adaptive_payload_bytes':adaptive_payload,'payload_ratio':adaptive_payload/dense_payload,'encode_ms':enc*1000.0,'decode_ms':dec_t*1000.0}

out={'status':'PASS','classification':'SYNTHETIC_NON_ECONOMIC_RESEARCH_ONLY','roundtrips':roundtrips,'codec_cases':{'sparse':sparse,'dense':dense},'tamper_rejections':tamper_rejections,'semantic_class_hash_preserved':True,'selection_rule':'SPARSE_U32 iff 4*set_bits < ceil(n/8), else DENSE','benchmark':bench,'production_claim':False}
print(json.dumps(out,sort_keys=True,separators=(',',':')))
