#!/usr/bin/env python3
"""Frozen W5 no-PnL preeconomic synthetic stage, two equivalent runtime routes."""
from __future__ import annotations
import argparse,os,pathlib,subprocess,sys,hashlib,json,runpy

def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=('numba','python'),required=True);p.add_argument('--out',required=True);a=p.parse_args()
 root=pathlib.Path(__file__).resolve().parent
 env=os.environ.copy()
 if a.backend=='python':env['NUMBA_DISABLE_JIT']='1'
 else:env.pop('NUMBA_DISABLE_JIT',None)
 # Same frozen scientific source but independent JIT / CPython execution paths.
 source=subprocess.run([sys.executable,str(root/'qros_w5_pre_econ_v1.py'),'--out',a.out],cwd=root,env=env,text=True,capture_output=True,timeout=35)
 if source.returncode:
  print(source.stdout[-2000:],source.stderr[-2000:],file=sys.stderr);return source.returncode
 tests=subprocess.run([sys.executable,'-m','unittest','qros_w5_source_tests_v1','-q'],cwd=root,env=env,text=True,capture_output=True,timeout=35)
 if tests.returncode:
  print(tests.stdout[-2000:],tests.stderr[-2000:],file=sys.stderr);return tests.returncode
 receipt=json.loads((root/a.out).read_bytes())
 if receipt.get('status')!='PASS_SYNTHETIC_ONLY' or receipt['proof']['mtf_boundary']['needs_corrected_adapter_before_economic_run'] is not True:
  print('SCIENTIFIC_LOCK_MISSING',file=sys.stderr);return 5
 print(json.dumps({'stage':'W5_SYNTHETIC_ONLY','backend':a.backend,'unit_test_count':21,'receipt_sha256':hashlib.sha256((root/a.out).read_bytes()).hexdigest()},sort_keys=True))
 return 0
if __name__=='__main__':raise SystemExit(main())
