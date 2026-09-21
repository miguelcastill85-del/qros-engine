from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
import numpy as np,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_factor_ir import FactorIR
from qros_factor_ir_store import MAGIC,LEN,serialize,deserialize,atomic_write

rng=np.random.default_rng(912021);roundtrips=0;tamper_rejected=0
for seed in range(80):
    n=int(rng.integers(0,5000));src=np.cumsum(rng.integers(1,100,max(n,1),dtype=np.uint64))[:n]
    prims={f'p{i}':rng.random(n)<rng.random() for i in range(int(rng.integers(1,20)))}
    if prims:prims['dup']=next(iter(prims.values())).copy()
    keys=list(prims);recipes={f'r{i}':tuple(rng.choice(keys,size=int(rng.integers(0,min(5,len(keys))+1)),replace=False)) for i in range(int(rng.integers(1,30)))}
    ir=FactorIR.build(src,prims,recipes);ak=hashlib.sha256(f'action-{seed}'.encode()).hexdigest();prov={'action_key':ak,'domain':{'asset':'NQX','side':'BUY','timeframe':'M2'},'code_root_sha256':'a'*64,'input_root_sha256':'b'*64}
    blob=serialize(ir,provenance=prov);got,h=deserialize(blob,expected_action_key=ak)
    if got.manifest()!=ir.manifest():raise SystemExit('MANIFEST_ROUNDTRIP_MISMATCH')
    for rid in recipes:
        if not np.array_equal(got.selected_source_indices(rid),ir.selected_source_indices(rid)):raise SystemExit('RECIPE_ROUNDTRIP_MISMATCH')
        if got.class_hash(rid,prov['domain'])!=ir.class_hash(rid,prov['domain']):raise SystemExit('CLASS_HASH_ROUNDTRIP_MISMATCH')
    if serialize(got,provenance=h['provenance'])!=blob:raise SystemExit('STORE_NOT_BYTE_DETERMINISTIC')
    roundtrips+=1
    if seed==0:
        attacks=[]
        x=bytearray(blob);x[0]^=1;attacks.append(bytes(x));attacks.append(blob[:-1]);attacks.append(blob+b'X')
        pos=len(MAGIC);hlen=LEN.unpack_from(blob,pos)[0];source_start=pos+LEN.size+hlen
        if n:
            x=bytearray(blob);x[source_start]^=1;attacks.append(bytes(x))
        if len(blob)>source_start+n*8:
            x=bytearray(blob);x[-1]^=1;attacks.append(bytes(x))
        for bad in attacks:
            try:deserialize(bad,expected_action_key=ak);raise SystemExit('STORE_TAMPER_ACCEPTED')
            except ValueError:tamper_rejected+=1
        try:deserialize(blob,expected_action_key='f'*64);raise SystemExit('WRONG_ACTION_KEY_ACCEPTED')
        except ValueError:tamper_rejected+=1
src=np.array([1],dtype=np.uint64);ir=FactorIR.build(src,{'a':np.array([True])},{'r':['a']});ak='1'*64;prov={'action_key':ak};blob=bytearray(serialize(ir,provenance=prov));pos=len(MAGIC);hlen=LEN.unpack_from(blob,pos)[0];hs=pos+LEN.size;h=json.loads(bytes(blob[hs:hs+hlen]));data_start=hs+hlen+8
raw=bytearray(blob[data_start:]);raw[-1]|=0x80;newdig=hashlib.sha256(bytes(raw)).hexdigest();old=h['physical_bitmaps'][0]['sha256'];h['physical_bitmaps'][0]['sha256']=newdig;h['semantic_to_physical']['a']=newdig;hb=json.dumps(h,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();crafted=MAGIC+LEN.pack(len(hb))+hb+src.astype('<u8').tobytes()+bytes(raw)
try:deserialize(crafted,expected_action_key=ak);raise SystemExit('NONCANONICAL_PADDING_ACCEPTED')
except ValueError:tamper_rejected+=1
with tempfile.TemporaryDirectory() as td:
    final=Path(td)/'ir.bin'
    try:atomic_write(final,ir,provenance=prov,crash_before_rename=True)
    except RuntimeError:pass
    if final.exists():raise SystemExit('CRASH_PUBLISHED_FINAL')
    meta=atomic_write(final,ir,provenance=prov);got,_=deserialize(final.read_bytes(),expected_action_key=ak)
    if meta['sha256']!=hashlib.sha256(final.read_bytes()).hexdigest():raise SystemExit('ATOMIC_HASH_MISMATCH')
print(json.dumps({'status':'PASS','roundtrip_cases':roundtrips,'tamper_cases_rejected':tamper_rejected,'byte_deterministic':True,'atomic_crash_recovery_pass':True,'canonical_padding_enforced':True},sort_keys=True))
