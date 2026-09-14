#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
SPEC='research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'; A='scripts/qros_seed_universe_enumerator_a_v2.py'; B='scripts/qros_seed_universe_enumerator_b_v2.py'
def loadmod(name,p):
    s=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(s); assert s.loader; s.loader.exec_module(m); return m
def c(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def root_canonical_order(rows):
    h=hashlib.sha256()
    for z in sorted(c(x) for x in rows): h.update(hashlib.sha256(z).digest())
    return h.hexdigest()
def root_digest_order(rows):
    h=hashlib.sha256()
    for z in sorted(hashlib.sha256(c(x)).digest() for x in rows): h.update(z)
    return h.hexdigest()
def sd(a,b):
    sa={c(x) for x in a}; sb={c(x) for x in b}; return len(sa-sb),len(sb-sa),len(sa),len(sb)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',required=True); ap.add_argument('--out',required=True); q=ap.parse_args(); root=Path(q.repo_root).resolve(); spec=json.load(open(root/SPEC,encoding='utf-8')); ma=loadmod('enum_a',root/A); mb=loadmod('enum_b',root/B)
    ar={'base':ma.product_rows(spec['base_axes'],spec['base_axis_order']),'filters':ma.filter_packages(spec),'management':ma.management(spec)}
    br={'base':mb.base_rows(spec),'filters':mb.filter_packages(spec),'management':mb.management(spec)}
    out={'schema':'QROS_SEED0076_ENUMERATOR_PARITY_DIAGNOSTIC_1.0','status':'PASS','sets':{},'root_cause_hypothesis':'ROOT_AGGREGATION_ORDER_ONLY'}
    for k in ('base','filters','management'):
        ab,ba,ac,bc=sd(ar[k],br[k]); rc_a=root_canonical_order(ar[k]); rc_b=root_canonical_order(br[k]); rd_a=root_digest_order(ar[k]); rd_b=root_digest_order(br[k])
        out['sets'][k]={'a_count':len(ar[k]),'b_count':len(br[k]),'a_minus_b':ab,'b_minus_a':ba,'canonical_set_equal':ab==0 and ba==0,'canonical_order_root_a':rc_a,'canonical_order_root_b':rc_b,'digest_order_root_a':rd_a,'digest_order_root_b':rd_b,'canonical_order_roots_equal':rc_a==rc_b,'digest_order_roots_equal':rd_a==rd_b,'a_native_root':ma.root(ar[k]),'b_native_root':mb.root(br[k])}
    out['semantic_set_parity_pass']=all(x['canonical_set_equal'] for x in out['sets'].values())
    out['root_definition_divergence_confirmed']=out['semantic_set_parity_pass'] and all(x['canonical_order_roots_equal'] and x['digest_order_roots_equal'] and x['a_native_root']==x['canonical_order_root_a'] and x['b_native_root']==x['digest_order_root_b'] for x in out['sets'].values())
    if not out['semantic_set_parity_pass'] or not out['root_definition_divergence_confirmed']:
        out['status']='FAIL'; Path(q.out).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n'); print(json.dumps(out,sort_keys=True)); return 2
    raw=json.dumps(out,sort_keys=True,separators=(',',':')).encode(); out['receipt_sha256']=hashlib.sha256(raw).hexdigest(); Path(q.out).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n'); print(json.dumps({'status':'PASS','semantic_set_parity_pass':True,'root_definition_divergence_confirmed':True,'receipt_sha256':out['receipt_sha256']},sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr); raise SystemExit(2)
