from __future__ import annotations
import json,hashlib,sys
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_factor_ir import FactorIR,canonical_bytes,unpack_mask
import qros_adaptive_bitmap as ab

rng=np.random.default_rng(7600765)
assets=['XAUUSD','NQX'];sides=['BUY','SELL'];tfs=['M1','M2','M15','H1','H4']
domains=[{'asset':a,'side':s,'timeframe':tf} for a in assets for s in sides for tf in tfs]
lengths={'M1':4099,'M2':3571,'M15':2081,'H1':1543,'H4':1031}
recipe_checks=class_checks=adaptive_checks=0;domain_hashes={};physical_dedupe=0
for tf in tfs:
    n=lengths[tf];source=np.cumsum(rng.integers(1,5,n,dtype=np.uint64))+np.uint64(1000)
    pA=rng.random(n)<0.18;pB=rng.random(n)<0.43;pC=rng.random(n)<0.07;pD=(np.arange(n)%11)<3
    primitives={'A':pA,'A_ALIAS':pA.copy(),'B':pB,'C':pC,'D':pD}
    recipes={'ALL':(), 'A':('A',),'A_ALIAS':('A_ALIAS',),'AB':('A','B'),'BCD':('B','C','D'),'ACD':('A','C','D')}
    ir=FactorIR.build(source,primitives,recipes)
    if ir.semantic_to_physical['A']!=ir.semantic_to_physical['A_ALIAS']:raise SystemExit('PHYSICAL_DEDUPE_MISSING')
    if ir.manifest()['semantic_primitive_count']!=5 or ir.manifest()['physical_bitmap_count']!=4:raise SystemExit('PHYSICAL_DEDUPE_COUNT_BAD')
    physical_dedupe+=1
    for rid,keys in recipes.items():
        direct=np.ones(n,dtype=bool)
        for k in keys:direct&=primitives[k]
        got=ir.recipe_mask(rid)
        if not np.array_equal(got,direct):raise SystemExit('RECIPE_RECONSTRUCTION_MISMATCH')
        if not np.array_equal(ir.selected_source_indices(rid),source[direct]):raise SystemExit('SOURCE_INDEX_SELECTION_MISMATCH')
        recipe_checks+=1
    for digest,raw in ir.physical_bitmaps.items():
        mask=unpack_mask(raw,n);enc=ab.encode(mask);dec=ab.decode(enc)
        if not np.array_equal(mask,dec):raise SystemExit('ADAPTIVE_PHYSICAL_ROUNDTRIP_MISMATCH')
        if ab.inspect(enc)['canonical_sha256']!=digest:raise SystemExit('ADAPTIVE_CANONICAL_DIGEST_DRIFT')
        adaptive_checks+=1
    for d in [x for x in domains if x['timeframe']==tf]:
        for rid in recipes:
            ids=ir.selected_source_indices(rid).astype('<u8',copy=False).tobytes()
            expected=hashlib.sha256(canonical_bytes(d)+b'\0'+ids).hexdigest();got=ir.class_hash(rid,d)
            if got!=expected:raise SystemExit('CLASS_HASH_FORMULA_MISMATCH')
            domain_hashes[(d['asset'],d['side'],tf,rid)]=got;class_checks+=1
    for d in [x for x in domains if x['timeframe']==tf]:
        if ir.class_hash('A',d)!=ir.class_hash('A_ALIAS',d):raise SystemExit('MASK_ALIAS_CLASS_HASH_MISMATCH')
        if ir.recipes['A']==ir.recipes['A_ALIAS']:raise SystemExit('SEMANTIC_RECIPE_KEYS_COLLAPSED')
    shifted=FactorIR.build(source+np.uint64(1_000_000),primitives,recipes);d={'asset':'NQX','side':'BUY','timeframe':tf}
    if ir.class_hash('AB',d)==shifted.class_hash('AB',d):raise SystemExit('SOURCE_COORDINATE_HASH_INSENSITIVE')
for tf in tfs:
    vals=[domain_hashes[(a,s,tf,'AB')] for a in assets for s in sides]
    if len(set(vals))!=len(vals):raise SystemExit('DOMAIN_CLASS_HASH_COLLISION')
separation_checks=0
for rid in ['ALL','A','AB','BCD','ACD']:
    vals=[domain_hashes[(d['asset'],d['side'],d['timeframe'],rid)] for d in domains]
    if len(set(vals))!=len(vals):raise SystemExit('CROSS_DOMAIN_HASH_COLLISION')
    separation_checks+=len(vals)
out={'status':'PASS','classification':'SYNTHETIC_NON_ECONOMIC','domains':len(domains),'assets':assets,'sides':sides,'timeframes':tfs,'recipe_reconstruction_checks':recipe_checks,'class_hash_formula_checks':class_checks,'adaptive_physical_bitmap_checks':adaptive_checks,'physical_dedupe_timeframes':physical_dedupe,'cross_domain_separation_checks':separation_checks,'semantic_alias_preserved_without_domain_merge':True,'source_coordinate_identity_sensitive':True,'historical_claim':False,'retest_rearm_touched':False}
print(json.dumps(out,sort_keys=True,separators=(',',':')))
