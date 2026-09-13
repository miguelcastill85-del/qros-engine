#!/usr/bin/env python3
import argparse, hashlib, importlib.util, json
from decimal import Decimal
from pathlib import Path

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def norm(x):
    if hasattr(x,'numerator') and hasattr(x,'denominator'): return Decimal(x.numerator)/Decimal(x.denominator)
    return Decimal(str(x))

def eq(a,b): return norm(a)==Decimal(str(b))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--contract',required=True); ap.add_argument('--out',required=True); ap.add_argument('--repo-root',default=str(Path(__file__).resolve().parents[1])); a=ap.parse_args()
    root=Path(a.repo_root); c=json.loads(Path(a.contract).read_text(encoding='utf-8'))
    A=load(root/'scripts/qros_seed0076_execution_units_primary.py','ua'); B=load(root/'scripts/qros_seed0076_execution_units_independent.py','ub')
    failures=[]; checks=[]
    tests=[
      ('XAU_PACKED',lambda m:m.quote_from_packed(234567,'0.01'),'2345.67'),
      ('NDX_PACKED',lambda m:m.quote_from_packed(250003,'0.1'),'25000.3'),
      ('XAU_ATR_STOP',lambda m:m.atr_stop('2.50','1.5'),'3.75'),
      ('NDX_ATR_STOP',lambda m:m.atr_stop('50.0','1.5'),'75.0'),
      ('STRUCT',lambda m:m.structural_stop('2000','1995'),'5'),
      ('TIGHTER',lambda m:m.mixed_stop('5','7.5','TIGHTER'),'5'),
      ('WIDER',lambda m:m.mixed_stop('5','7.5','WIDER'),'7.5'),
      ('TARGET2R',lambda m:m.target_distance('3.75','2'),'7.50'),
      ('XAU_POINTS',lambda m:m.qros_points('3.75','0.01'),'375'),
      ('NDX_POINTS',lambda m:m.qros_points('75','0.1'),'750'),
      ('XAU_TICK_USD',lambda m:m.usd_value_of_distance('0.01','100'),'1'),
      ('NDX_TICK_USD',lambda m:m.usd_value_of_distance('0.1','10'),'1'),
      ('NDX_COMM',lambda m:m.ndx_commission_per_order('1'),'2.75'),
      ('XAU_COMM_2000',lambda m:m.xau_commission_per_order('2000','1'),'5')]
    for name,fn,expected in tests:
        va,vb=fn(A),fn(B)
        ok=eq(va,expected) and eq(vb,expected) and norm(va)==norm(vb)
        checks.append({'id':name,'expected':expected,'primary':str(norm(va)),'independent':str(norm(vb)),'pass':ok})
        if not ok: failures.append(name)
    required={'OPPOSITE_FRACTAL','ATR_MULTIPLE','TIGHTER_STRUCT_OR_ATR','WIDER_STRUCT_OR_ATR','R','TARGET_R','BREAKEVEN_TRIGGER_R','TRAIL_ATR','TRAIL_FAST_EMA','PARTIAL_R'}
    missing=sorted(required-set(c.get('management_units',{})))
    if missing: failures.extend('MISSING:'+x for x in missing)
    receipt={'schema':'QROS_SEED0076_UNIT_BINDING_PREFLIGHT_RECEIPT_1.0','seed':'WEB_SEED_0076','status':'PASS' if not failures else 'FAIL','decision':'ECONOMIC_SCORING_UNIT_BINDING_AUTHORIZED' if not failures else 'ECONOMIC_SCORING_FORBIDDEN','primary_oracle':'scripts/qros_seed0076_execution_units_primary.py','independent_oracle':'scripts/qros_seed0076_execution_units_independent.py','checks':checks,'failures':failures,'physical_data_schema_verified':False,'physical_data_schema_note':'Separate DATA_EXECUTION_READY gate must verify materialized DEV bytes before Gate A; this receipt certifies dimensional semantics only.'}
    raw=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode(); receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest()
    Path(a.out).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8'); print(receipt['decision']); return 0 if not failures else 2
if __name__=='__main__': raise SystemExit(main())
